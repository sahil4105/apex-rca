from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from apex_rca.config import ExperimentConfig, default_rcaeval_dir
from apex_rca.data_loader import load_case, load_index
from apex_rca.llm_client import generate_incident_diagnosis, get_groq_client
from apex_rca.llm_evidence import build_evidence_package
from apex_rca.llm_validation import validate_report
from apex_rca.metric_parsing import service_metric_columns
from apex_rca.pipeline import diagnose_case

ROOT = Path(__file__).resolve().parent
DATA = default_rcaeval_dir()
RESULTS = ROOT / "results"

METHOD_FILES = {
    "Z-score baseline": "zscore_zscore_full1.csv",
    "Anomaly-only": "anomaly_only_full2.csv",
    "Metrics + graph": "metrics_graph_full2.csv",
    "Metrics + logs/traces": "metrics_logs_traces_full2.csv",
    "Full pipeline": "full_full2.csv",
}

METHOD_COLORS = {
    "Z-score baseline": "#8b95a5",
    "Anomaly-only": "#70a1ff",
    "Metrics + graph": "#53c6a8",
    "Metrics + logs/traces": "#c49bff",
    "Full pipeline": "#f0b45b",
}


st.set_page_config(
    page_title="APEX-RCA | Research Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def cached_index(data_dir: str) -> pd.DataFrame:
    return load_index(Path(data_dir))


@st.cache_data(show_spinner=False)
def cached_csv(path: str, modified: float) -> pd.DataFrame:
    del modified
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def cached_json(path: str, modified: float) -> dict:
    del modified
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_result_file(filename: str) -> pd.DataFrame | None:
    path = RESULTS / filename
    if not path.exists():
        return None
    return cached_csv(str(path), path.stat().st_mtime)


def load_summary() -> dict | None:
    path = RESULTS / "summary_full2.json"
    if not path.exists():
        return None
    return cached_json(str(path), path.stat().st_mtime)


def percent(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def metric_value(result: dict, metric: str) -> float | None:
    try:
        return float(result["summary"][metric]["mean"])
    except (KeyError, TypeError, ValueError):
        return None


def apply_app_styles() -> None:
    """Apply presentation-only styling to the Streamlit dashboard."""
    st.markdown(
        """
        <style>
        :root {
            --apex-ink: #172b3a;
            --apex-muted: #60717d;
            --apex-teal: #187e78;
            --apex-border: #dce5e7;
            --apex-surface: #ffffff;
        }
        .stApp { background: #f6f8f7; color: var(--apex-ink); }
        .block-container { padding-top: 2.1rem; padding-bottom: 3rem; max-width: 1440px; }
        [data-testid="stHeader"] { background: rgba(246,248,247,.94); }
        [data-testid="stSidebar"] { background: #eef3f2; border-right: 1px solid var(--apex-border); }
        [data-testid="stSidebar"] [data-testid="stRadio"] label { font-weight: 600; }
        h1, h2, h3 { color: var(--apex-ink); letter-spacing: -0.02em; }
        h1 { font-size: 2rem !important; }
        [data-testid="stMetric"] { background: var(--apex-surface); border: 1px solid var(--apex-border); border-radius: 8px; padding: 14px 16px; }
        [data-testid="stMetricLabel"] p { color: var(--apex-muted); font-size: .82rem; }
        [data-testid="stMetricValue"] { color: var(--apex-ink); font-size: 1.55rem; }
        [data-testid="stTabs"] button[aria-selected="true"] { color: var(--apex-teal); border-bottom-color: var(--apex-teal); }
        [data-testid="stDataFrame"] { border: 1px solid var(--apex-border); border-radius: 7px; overflow: hidden; }
        [data-testid="stVerticalBlockBorderWrapper"] { background: #fff; border-color: var(--apex-border); border-radius: 10px; }
        [data-testid="stAlert"] { border-radius: 8px; }
        [data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label { color: var(--apex-muted); font-size: .86rem; font-weight: 600; }
        div.stButton > button[kind="primary"] { background: var(--apex-teal); border-color: var(--apex-teal); }
        div.stButton > button:focus-visible { outline: 3px solid #79bcb6; outline-offset: 2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_overview(index: pd.DataFrame) -> None:
    st.title("Research overview")
    st.caption("APEX-RCA · Evidence-grounded root-cause ranking for microservices")

    summary = load_summary()
    if summary is None:
        st.warning(
            "Saved summary_full2.json was not found. The overview can still "
            "show the available per-case CSV results."
        )

    evaluated = (
        summary.get("methods", {}).get("full", {}).get("n_evaluated")
        if summary else None
    )
    skipped = (
        summary.get("methods", {}).get("full", {}).get("n_skipped")
        if summary else None
    )

    with st.container(border=True):
        st.caption("BENCHMARK COVERAGE")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Indexed cases", f"{len(index):,}")
        k2.metric("Evaluated cases", f"{evaluated:,}" if evaluated is not None else "N/A")
        k3.metric("Skipped cases", str(skipped) if skipped is not None else "N/A")
        k4.metric("Benchmark suites", str(index["suite"].nunique()))

    st.info(
        "Evaluation mode: retrospective diagnosis. The benchmark uses the "
        "recorded fault-injection time to distinguish reference and observation "
        "windows. These results are not a live production-monitoring measurement."
    )

    st.subheader("Method comparison")
    st.caption("Compare saved benchmark scores across anomaly and evidence-grounded ranking methods.")

    rows = []
    for label, filename in METHOD_FILES.items():
        result = summary.get("methods", {}).get(
            {
                "Anomaly-only": "anomaly_only",
                "Metrics + graph": "metrics_graph",
                "Metrics + logs/traces": "metrics_logs_traces",
                "Full pipeline": "full",
            }.get(label, ""),
            {},
        ) if summary else {}

        frame = load_result_file(filename)
        if frame is not None and not frame.empty:
            row = {"Method": label}
            for metric in ["hit1", "hit3", "hit5", "mrr"]:
                val = metric_value(result, metric) if result else None
                if val is None and metric in frame.columns:
                    val = pd.to_numeric(frame[metric], errors="coerce").mean()
                row[metric] = val
            rows.append(row)

    if rows:
        perf = pd.DataFrame(rows)
        pretty = perf.rename(
            columns={
                "hit1": "Hit@1",
                "hit3": "Hit@3",
                "hit5": "Hit@5",
                "mrr": "MRR",
            }
        ).set_index("Method")
        with st.container(border=True):
            chart_head, chart_control = st.columns([3, 1])
            chart_head.markdown("#### Overall benchmark scores")
            chart_head.caption("Higher values indicate stronger ranking performance.")
            selected_metrics = chart_control.multiselect(
                "Metrics",
                ["Hit@1", "Hit@3", "Hit@5", "MRR"],
                default=["Hit@1", "Hit@3"],
            )
            if selected_metrics:
                chart_data = pretty[selected_metrics].reset_index().melt(
                    id_vars="Method", var_name="Metric", value_name="Score"
                )
                fig = px.bar(
                    chart_data, x="Method", y="Score", color="Metric",
                    barmode="group", range_y=[0, 1],
                    color_discrete_sequence=["#187e78", "#496a83", "#88aaa5", "#9aa7b2"],
                )
                fig.update_layout(
                    height=390, margin=dict(l=10, r=10, t=20, b=10),
                    legend_title_text="Metric", xaxis_title="", yaxis_title="Score (0–1)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#52636f"), yaxis=dict(gridcolor="#e7edef", zeroline=False),
                )
                st.plotly_chart(fig, use_container_width=True)
        with st.expander("Detailed benchmark results", expanded=False):
            st.dataframe(
                pretty.style.format("{:.4f}", na_rep="N/A"),
                use_container_width=True,
            )
    else:
        st.warning("No recognized saved method CSVs were found in the results folder.")

    st.subheader("Suite-level performance")
    st.caption("Explore how ranking quality varies across the RCAEval benchmark suites.")
    if summary:
        suite_rows = []
        for label, method_key in [
            ("Anomaly-only", "anomaly_only"),
            ("Metrics + graph", "metrics_graph"),
            ("Metrics + logs/traces", "metrics_logs_traces"),
            ("Full pipeline", "full"),
        ]:
            groups = (
                summary.get("methods", {})
                .get(method_key, {})
                .get("summary", {})
                .get("by", {})
                .get("suite", [])
            )
            for item in groups:
                suite_rows.append({
                    "Method": label,
                    "Suite": item.get("group"),
                    "Cases": item.get("n"),
                    "Hit@1": item.get("hit1"),
                    "Hit@3": item.get("hit3"),
                    "Hit@5": item.get("hit5"),
                    "MRR": item.get("mrr"),
                })

        if suite_rows:
            suite_df = pd.DataFrame(suite_rows)
            with st.container(border=True):
                suite_control, suite_help = st.columns([1, 3])
                suite_metric = suite_control.selectbox(
                    "Metric to inspect", ["Hit@1", "Hit@3", "Hit@5", "MRR"], key="suite_metric"
                )
                suite_help.caption("Select a metric to focus the comparison across suites.")
                suite_fig = px.bar(
                    suite_df, x="Suite", y=suite_metric, color="Method",
                    barmode="group", range_y=[0, 1],
                    color_discrete_map={
                        "Anomaly-only": "#496a83",
                        "Metrics + graph": "#187e78",
                        "Metrics + logs/traces": "#88aaa5",
                        "Full pipeline": "#172b3a",
                    },
                )
                suite_fig.update_layout(
                    height=360, margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#52636f"), yaxis=dict(gridcolor="#e7edef", zeroline=False),
                )
                st.plotly_chart(suite_fig, use_container_width=True)
            with st.expander("Suite-level result table", expanded=False):
                st.dataframe(
                    suite_df.style.format(
                        {"Hit@1": "{:.3f}", "Hit@3": "{:.3f}", "Hit@5": "{:.3f}", "MRR": "{:.3f}"}
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

    llm_summary_file = RESULTS / "llm_evaluation" / "llm_summary.json"
    if llm_summary_file.exists():
        llm_sum = cached_json(str(llm_summary_file), llm_summary_file.stat().st_mtime)
        llm_rows = []
        labels = {
            "baseline_raw_logs": "Baseline A (Raw Logs)",
            "method_anomaly_only": "Method B (Anomaly-Only)",
            "proposed_topology_anomaly": "Proposed Method C (Topology + Anomaly)",
            "ranking_top1_evidence": "Top-1 Evidence Only",
            "ranking_oracle_control": "Oracle Candidate Control (Eval-Only)",
        }
        for k, name in labels.items():
            if k in llm_sum:
                d = llm_sum[k]
                llm_rows.append({
                    "Condition": name,
                    "Cases": d.get("sample_size"),
                    "Diagnosis Accuracy": f"{d.get('accuracy', 0.0)*100:.1f}%",
                    "Valid Citation %": f"{d.get('mean_citation_validity', 0.0)*100:.1f}%",
                    "Unsupported Claims %": f"{d.get('mean_unsupported_claim_ratio', 0.0)*100:.1f}%",
                    "Mean Latency": f"{d.get('mean_latency_s', 0.0):.2f}s",
                })
        if llm_rows:
            with st.expander("LLM diagnosis evaluation", expanded=False):
                st.caption("Evaluation across raw-log prompting, anomaly-only and topology-grounded evidence. Oracle control is evaluation-only.")
                st.dataframe(pd.DataFrame(llm_rows), hide_index=True, use_container_width=True)

    with st.expander("Score definitions and research limitations", expanded=False):
        st.markdown(
            """
            - **Hit@1, Hit@3 and Hit@5** indicate whether the labelled root-cause service appears among the first 1, 3 or 5 ranked candidates.
            - **MRR** rewards ranking the labelled service higher.
            - Missing logs or traces mean that evidence source is unavailable; absence is not proof of system health.
            - A ranked service is a diagnostic candidate, not proof of causality.
            - Results apply to the evaluated RCAEval cases and configuration; they do not establish performance on unseen production incidents.
            """
        )


def rank_table(result, label: str) -> pd.DataFrame:
    rows = []
    for rank, (service, score) in enumerate(result.ranked, start=1):
        rows.append({
            "Method": label,
            "Rank": rank,
            "Service": service,
            "Score": score,
            "Ground truth": service == result.root_cause,
        })
    return pd.DataFrame(rows)


def show_diagnosis(index: pd.DataFrame) -> None:
    st.title("Incident explorer")
    st.caption("Investigate one recorded RCAEval incident across rankings, evidence and telemetry.")

    suites = ["All"] + sorted(index["suite"].astype(str).unique().tolist())
    with st.container(border=True):
        st.caption("FIND AN INCIDENT")
        f1, f2, f3 = st.columns(3)
        suite = f1.selectbox("Benchmark suite", suites, key="case_suite")
        filtered = index if suite == "All" else index[index["suite"].astype(str) == suite]

        systems = ["All"] + sorted(filtered["system_name"].astype(str).unique().tolist())
        system = f2.selectbox("Application", systems, key="case_system")
        if system != "All":
            filtered = filtered[filtered["system_name"].astype(str) == system]

        faults = ["All"] + sorted(filtered["fault"].astype(str).unique().tolist())
        fault = f3.selectbox("Fault category", faults, key="case_fault")
        if fault != "All":
            filtered = filtered[filtered["fault"].astype(str) == fault]

    case_ids = sorted(filtered["case"].astype(str).tolist())
    if not case_ids:
        st.info("No incidents match the selected filters. Adjust the suite, application or fault category to continue.")
        return

    pick, count = st.columns([3, 1])
    case_id = pick.selectbox("Incident", case_ids, key="case_id")
    count.metric("Matching incidents", f"{len(case_ids):,}")
    row = index[index["case"].astype(str) == case_id].iloc[0]

    st.subheader("Incident summary")
    with st.container(border=True):
        a, b, c, d = st.columns(4)
        a.metric("Application", str(row["system_name"]))
        b.metric("Benchmark suite", str(row["suite"]))
        c.metric("Logs", "Available" if bool(row["has_logs"]) else "Unavailable")
        d.metric("Traces", "Available" if bool(row["has_traces"]) else "Unavailable")
        st.markdown(f"**Fault category:** {row['fault']} &nbsp;&nbsp; · &nbsp;&nbsp; **Case:** `{case_id}`")

    with st.expander("Case metadata", expanded=False):
        st.write("**Case:**", case_id)
        st.write("**Fault description:**", row.get("fault_description", "Not recorded"))
        st.write("**Recorded injection time:**", row["inject_time"])
        st.write("**Metric window:**", f"{row['time_start']} – {row['time_end']}")
        st.write(
            "**Ground-truth service:**",
            str(row["root_cause_service"]),
        )
        st.caption(
            "Ground truth is displayed for retrospective benchmark evaluation. "
            "It is not supplied to the ranking functions."
        )

    config = ExperimentConfig(graph_mode="auto")
    with st.spinner("Loading telemetry and scoring this case…"):
        bundle = load_case(
            DATA,
            row,
            load_logs=True,
            load_traces=True,
            traces_for_graph_only=False,
        )
        anomaly = diagnose_case(bundle, config, "anomaly_only")
        graph = diagnose_case(bundle, config, "metrics_graph")
        full = diagnose_case(bundle, config, "full")

    if anomaly.skip_reason:
        st.error(f"This case could not be evaluated: {anomaly.skip_reason}")
        return

    if graph.skip_reason:
        st.warning(f"Dependency-aware method unavailable: {graph.skip_reason}")
    if full.skip_reason:
        st.warning(f"Full method unavailable: {full.skip_reason}")

    tab_rank, tab_evidence, tab_llm, tab_telemetry, tab_raw = st.tabs(
        ["Ranking", "Evidence", "LLM diagnosis", "Telemetry", "Raw data"]
    )

    with tab_rank:
        st.markdown("#### Candidate ranking")
        st.caption("Compare methods one at a time. A high-ranked candidate is a lead for investigation, not proof of causality.")
        methods = {
            "Full pipeline": full,
            "Metrics + graph": graph,
            "Anomaly-only": anomaly,
        }
        label = st.selectbox("Ranking method", list(methods), key=f"rank_method_{case_id}")
        result = methods[label]
        if result.skip_reason:
            st.warning(result.skip_reason)
        else:
            with st.container(border=True):
                r1, r2, r3 = st.columns(3)
                r1.metric("Hit@1", percent(result.hit1))
                r2.metric("Hit@3", percent(result.hit3))
                r3.metric("MRR", f"{result.mrr:.3f}")
                st.caption(f"Ground-truth rank: {result.rank if result.rank is not None else 'Not ranked'} · Case-level evaluation values")
                st.dataframe(rank_table(result, label).head(10), hide_index=True, use_container_width=True)

        if not graph.skip_reason and not full.skip_reason:
            delta = (full.hit1 or 0) - (graph.hit1 or 0)
            st.caption(
                f"Full-pipeline Hit@1 minus graph-method Hit@1 for this case: "
                f"{delta:+.0f} (case-level outcome, not a population estimate)."
            )

    with tab_evidence:
        result = full if not full.skip_reason else graph
        st.markdown("#### Evidence used by the ranking")
        st.caption("Available evidence is summarized below. Missing sources are shown as unavailable, not as evidence of healthy behavior.")
        st.caption(
            f"Graph provenance: {result.graph_provenance or 'not available'} · "
            f"Graph edges: {result.extras.get('graph_n_edges', 'not reported')} · "
            f"Logs available to pipeline: {result.extras.get('logs_available', 'unknown')} · "
            f"Traces available to pipeline: {result.extras.get('traces_available', 'unknown')}"
        )

        explanations = result.extras.get("explanations") or []
        if explanations:
            for item in explanations:
                with st.expander(
                    f"{item.get('service', 'Unknown service')} — "
                    f"metric score {item.get('metric_score', 'N/A')}"
                ):
                    for reason in item.get("reasons", []):
                        st.write(f"- {reason}")
        else:
            st.info("No evidence explanation objects were produced for this case.")

        if result.extras.get("graph_n_edges", 0) == 0:
            st.warning(
                "No dependency edges were used for this diagnosis. The result should "
                "be interpreted as telemetry-led ranking rather than graph-supported ranking."
            )

        st.caption(
            "Evidence summaries support investigation; they are not causal proof."
        )

    with tab_llm:
        st.markdown("#### Diagnosis workspace")
        st.caption("Generate an evidence-grounded report from the selected incident. The diagnosis uses the existing ranking and evidence pipeline.")

        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                method_variant = st.selectbox(
                    "Evidence grounding mode",
                    [
                        ("Proposed: Topology + Anomaly", "topology_anomaly"),
                        ("Method B: Anomaly-only (No Graph)", "anomaly_only"),
                        ("Baseline A: Raw Logs", "raw_logs"),
                    ],
                    format_func=lambda x: x[0],
                    key=f"llm_variant_{case_id}",
                )[1]
            with c2:
                candidate_k = st.selectbox(
                    "Candidate set", [3, 1],
                    format_func=lambda k: f"Top-{k} candidates",
                    key=f"llm_k_{case_id}",
                )
            with c3:
                st.write("")
                st.write("")
                generate_clicked = st.button("Generate diagnosis", key=f"btn_gen_{case_id}", type="primary", use_container_width=True)

        cache_key = f"report_{case_id}_{method_variant}_{candidate_k}"
        upstream_diag = full if not full.skip_reason else graph

        if generate_clicked or cache_key in st.session_state:
            if generate_clicked:
                with st.spinner("Analyzing telemetry evidence and generating diagnosis..."):
                    client = get_groq_client()
                    package = build_evidence_package(
                        bundle,
                        upstream_diag,
                        method_variant=method_variant,  # type: ignore[arg-type]
                        candidate_k=candidate_k,
                    )
                    report, meta = generate_incident_diagnosis(
                        package,
                        client=client,
                        deterministic_fallback_explanations=upstream_diag.extras.get("explanations", []),
                    )
                    audit = validate_report(report, package)
                    st.session_state[cache_key] = (report, meta, audit, package)

            report, meta, audit, package = st.session_state[cache_key]

            if meta.get("fallback_used"):
                st.warning(f"Deterministic fallback active: {meta.get('error', 'API unavailable')}")
            else:
                st.success(f"LLM response · `{meta.get('model')}` · {meta.get('latency_s', 0.0):.2f}s")

            v_col1, v_col2, v_col3 = st.columns(3)
            with v_col1:
                st.metric("Suspected Root Cause", report.suspected_root_cause)
            with v_col2:
                st.metric("Confidence", report.confidence.upper())
            with v_col3:
                st.metric("Suspected Fault Type", report.possible_fault_type or "Unspecified")

            st.write(f"**Reasoning Summary:** {report.reasoning_summary}")

            st.markdown("##### Evidence Grounding & Validation Audit")
            aud_c1, aud_c2, aud_c3, aud_c4 = st.columns(4)
            aud_c1.metric("Structure Valid", "Yes" if audit.is_valid_structure else "No")
            aud_c2.metric("In Candidate Set", "Yes" if audit.is_valid_candidate else "No")
            aud_c3.metric("Citation Validity", f"{audit.citation_validity_ratio * 100:.1f}%")
            aud_c4.metric("Unsupported Claims", str(audit.unsupported_claim_count))

            if audit.warnings:
                for w in audit.warnings:
                    st.warning(f"Validation Warning: {w}")

            st.markdown("##### Supporting Claims & Telemetry Citations")
            for idx, claim in enumerate(report.supporting_claims):
                cites = ", ".join(f"`{cid}`" for cid in claim.evidence_ids) if claim.evidence_ids else "None"
                st.markdown(f"- **Claim {idx+1}:** {claim.claim_text} *(Cites: {cites})*")

            exp_c1, exp_c2 = st.columns(2)
            with exp_c1:
                st.markdown("##### Alternative Candidates")
                if report.alternative_candidates:
                    for alt in report.alternative_candidates:
                        st.markdown(f"- **{alt.service}:** {alt.rationale}")
                else:
                    st.caption("No alternative candidates analyzed.")

            with exp_c2:
                st.markdown("##### Contradictions & Limitations")
                for c in report.contradictory_evidence:
                    st.markdown(f"- *Contradiction:* {c}")
                for u in report.uncertainty_and_limitations:
                    st.markdown(f"- *Uncertainty:* {u}")

            with st.expander("Inspected Evidence Package Sent to Model"):
                st.text(package.format_for_prompt())

        else:
            st.info("Click 'Generate Report' to execute or view the grounded LLM diagnosis for this case.")

    with tab_telemetry:
        st.markdown("#### Metric telemetry")
        st.caption("The dashed marker is the recorded fault-injection time for this retrospective case.")
        metrics = bundle.metrics
        mapping = service_metric_columns(metrics)
        focus = [name for name, _ in anomaly.ranked[:4]]
        available_metrics = []
        for service in focus:
            available_metrics.extend(mapping.get(service, [])[:2])

        available_metrics = list(dict.fromkeys(available_metrics))
        if "time" in metrics.columns and available_metrics:
            plot_cols = ["time"] + [
                col for col in available_metrics if col in metrics.columns
            ][:8]
            plot_df = metrics[plot_cols].melt(
                id_vars="time",
                var_name="Metric",
                value_name="Value",
            )
            fig = px.line(
                plot_df,
                x="time",
                y="Value",
                color="Metric",
                title="Selected service metrics over time",
            )
            try:
                fig.add_vline(
                    x=float(row["inject_time"]),
                    line_dash="dash",
                    annotation_text="Injection time",
                )
            except (TypeError, ValueError):
                pass
            fig.update_layout(height=420, margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "The dashed line marks the recorded injection time. "
                "The plot shows available metric samples; it does not itself prove causation."
            )
        else:
            st.info("No compatible service metrics are available to plot for this case.")

    with tab_raw:
        st.markdown("#### Raw incident data")
        st.caption("Detailed records are kept secondary to the investigation summary.")
        with st.expander("Logs", expanded=False):
            if bundle.logs_loaded and bundle.logs is not None and not bundle.logs.empty:
                logs = bundle.logs.copy()
                if "timestamp" in logs.columns:
                    timestamps = pd.to_numeric(logs["timestamp"], errors="coerce")
                    logs = logs.loc[timestamps >= float(row["inject_time"])]
                st.write(f"Post-injection log rows shown: {min(len(logs), 100)}")
                st.dataframe(logs.head(100), hide_index=True, use_container_width=True)
            else:
                st.info("Logs are unavailable or empty for this case.")

        with st.expander("Trace data", expanded=False):
            if bundle.traces_loaded and bundle.traces is not None and not bundle.traces.empty:
                st.write(f"Trace rows available: {len(bundle.traces):,}")
                st.dataframe(bundle.traces.head(100), hide_index=True, use_container_width=True)
            else:
                st.info("Traces are unavailable or empty for this case.")


def main() -> None:
    apply_app_styles()
    st.sidebar.title("APEX-RCA")
    st.sidebar.caption("Research prototype · RCAEval")
    page = st.sidebar.radio(
        "Workspace",
        ["Research overview", "Incident explorer"],
    )

    if not (DATA / "cases.parquet").exists():
        st.error(f"RCAEval index not found at {DATA / 'cases.parquet'}")
        st.caption(f"Expected dataset directory: {DATA}")
        return

    index = cached_index(str(DATA))

    if page == "Research overview":
        show_overview(index)
    else:
        show_diagnosis(index)

    st.sidebar.divider()
    st.sidebar.caption("APEX-RCA · Retrospective diagnosis")
    if st.sidebar.button("Refresh saved results"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
