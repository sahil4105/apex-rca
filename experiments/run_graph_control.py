"""Standalone negative control for graph-aware RCA."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.config import ExperimentConfig
from apex_rca.data_loader import load_case, load_index
from apex_rca.dependency_graph import (
    build_dependency_graph,
    pagerank_from_anomaly,
)
from apex_rca.evaluation import case_metrics
from apex_rca.pipeline import diagnose_case
from apex_rca.ranking import combine_anomaly_and_graph, rank_services


SEED = 20261011
N_SHUFFLES = 20


def degree_preserving_shuffle(
    graph: nx.DiGraph,
    seed: int,
    attempts: int = 200,
) -> nx.DiGraph | None:
    """Randomize edge endpoints while preserving directed degrees.

    Returns None if a valid non-identical shuffle cannot be obtained.
    """
    original_edges = set(graph.edges())
    if len(original_edges) < 2:
        return None

    rng = random.Random(seed)
    nodes = list(graph.nodes())

    for _ in range(attempts):
        candidate = graph.copy()
        try:
            # Directed swaps preserve in-degree and out-degree.
            nx.directed_edge_swap(
                candidate,
                nswap=max(1, len(original_edges)),
                max_tries=max(100, len(original_edges) * 20),
                seed=rng,
            )
        except (nx.NetworkXError, nx.NetworkXAlgorithmError):
            continue

        if (
            set(candidate.nodes()) == set(nodes)
            and candidate.number_of_edges() == len(original_edges)
            and set(candidate.edges()) != original_edges
            and nx.number_of_selfloops(candidate) == 0
        ):
            # Preserve the edge-weight distribution while randomizing which
            # shuffled connections receive each weight.
            weights = [
                float(graph[u][v].get("weight", 1.0))
                for u, v in original_edges
            ]
            rng.shuffle(weights)
            for edge, weight in zip(candidate.edges(), weights):
                candidate.edges[edge]["weight"] = weight
            return candidate

    return None


def main() -> None:
    data_dir = ROOT / "data" / "rcaeval"
    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    index = load_index(data_dir).sort_values("case").reset_index(drop=True)
    config = ExperimentConfig(
        name="graph_negative_control",
        graph_mode="auto",
        graph_weight=0.30,
        seed=SEED,
    )

    records: list[dict] = []
    skipped: list[dict] = []

    for i, (_, row) in enumerate(index.iterrows(), start=1):
        bundle = load_case(
            data_dir,
            row,
            load_logs=False,
            load_traces=True,
            traces_for_graph_only=True,
        )

        # Existing real-graph method is the reference.
        real = diagnose_case(bundle, config, "metrics_graph")
        if real.skip_reason:
            skipped.append({"case": real.case, "reason": real.skip_reason})
            continue

        # Anomaly-only scores are the graph-independent baseline.
        anomaly = diagnose_case(bundle, config, "anomaly_only")
        if anomaly.skip_reason:
            skipped.append({"case": anomaly.case, "reason": anomaly.skip_reason})
            continue

        services = list(real.extras["metric_scores"].keys())
        graph = build_dependency_graph(
            system_name=real.system,
            traces=bundle.traces if bundle.traces_loaded else None,
            services=services,
            mode=config.graph_mode,
            min_trace_edge_count=config.min_trace_edge_count,
        )

        # Record the baseline methods on exactly the same evaluated cases.
        for label, result in [
            ("anomaly_only", anomaly),
            ("real_graph", real),
        ]:
            records.append({
                "case": result.case,
                "suite": result.suite,
                "system": result.system,
                "condition": label,
                "hit1": result.hit1,
                "hit3": result.hit3,
                "hit5": result.hit5,
                "mrr": result.mrr,
                "graph_provenance": result.graph_provenance,
            })

        if graph.n_edges == 0:
            skipped.append({
                "case": real.case,
                "reason": "no_edges_available_for_graph_shuffle",
            })
            continue

        for repetition in range(N_SHUFFLES):
            shuffled = degree_preserving_shuffle(
                graph.graph,
                seed=SEED + i * N_SHUFFLES + repetition,
            )

            if shuffled is None:
                skipped.append({
                    "case": real.case,
                    "reason": "degree_preserving_shuffle_failed",
                })
                continue

            from apex_rca.dependency_graph import DependencyGraph

            shuffled_dep = DependencyGraph(
                graph=shuffled,
                provenance="degree_preserving_shuffle",
                notes=[],
            )
            scores = pagerank_from_anomaly(
                shuffled_dep,
                real.extras["metric_scores"],
                damping=config.pagerank_damping,
            )
            combined = combine_anomaly_and_graph(
                real.extras["metric_scores"],
                scores,
                graph_weight=config.graph_weight,
            )
            ranked = [name for name, _ in rank_services(combined)]
            metrics = case_metrics(ranked, real.root_cause)

            records.append({
                "case": real.case,
                "suite": real.suite,
                "system": real.system,
                "condition": "shuffled_graph",
                "shuffle": repetition,
                "hit1": int(metrics["hit1"]),
                "hit3": int(metrics["hit3"]),
                "hit5": int(metrics["hit5"]),
                "mrr": float(metrics["mrr"]),
                "graph_provenance": graph.provenance,
                "n_nodes": graph.n_nodes,
                "n_edges": graph.n_edges,
            })

        if i % 25 == 0 or i == len(index):
            print(f"Processed {i}/{len(index)} cases")

    output = results_dir / "graph_control_long.csv"
    pd.DataFrame(records).to_csv(output, index=False)

    skipped_path = results_dir / "graph_control_skipped.csv"
    pd.DataFrame(skipped).to_csv(skipped_path, index=False)

    print("\nResults saved:", output)
    print("Skipped/shuffle failures saved:", skipped_path)

    frame = pd.DataFrame(records)
    if not frame.empty:
        metric_cols = ["hit1", "hit3", "hit5", "mrr"]

        # Average randomized graph runs within each case first.
        shuffled = frame[frame["condition"] == "shuffled_graph"]
        shuffled_case = (
            shuffled.groupby(["case", "suite", "system"], as_index=False)[metric_cols]
            .mean()
        )

        # Only compare conditions on cases with at least one valid shuffle.
        eligible = set(shuffled_case["case"])
        paired = frame[
            frame["condition"].isin(["anomaly_only", "real_graph"])
            & frame["case"].isin(eligible)
        ]

        baseline_case = (
            paired.groupby(["case", "suite", "system", "condition"], as_index=False)[metric_cols]
            .mean()
        )
        baseline_wide = baseline_case.pivot(
            index=["case", "suite", "system"],
            columns="condition",
            values=metric_cols,
        )
        baseline_wide.columns = [
            f"{metric}_{condition}" for metric, condition in baseline_wide.columns
        ]
        baseline_wide = baseline_wide.reset_index()

        shuffled_case = shuffled_case.rename(
            columns={metric: f"{metric}_shuffled_graph" for metric in metric_cols}
        )
        comparison = baseline_wide.merge(
            shuffled_case,
            on=["case", "suite", "system"],
            how="inner",
        )

        print(f"\nCases with at least one valid shuffled graph: {len(comparison)}")
        print(f"Cases in the original index: {len(index)}")
        print(f"Shuffle repetitions requested per eligible case: {N_SHUFFLES}")

        print("\nPaired comparison — same eligible cases; shuffled scores averaged per case:")
        summary_rows = []
        for condition in ["anomaly_only", "real_graph", "shuffled_graph"]:
            row = {"condition": condition, "n_cases": len(comparison)}
            for metric in metric_cols:
                row[metric] = comparison[f"{metric}_{condition}"].mean()
            summary_rows.append(row)

        summary = pd.DataFrame(summary_rows)
        print(summary.set_index("condition").round(4).to_string())

        print("\nReal graph minus shuffled graph, paired mean differences:")
        for metric in metric_cols:
            delta = (
                comparison[f"{metric}_real_graph"]
                - comparison[f"{metric}_shuffled_graph"]
            ).mean()
            print(f"{metric}: {delta:+.4f}")

        comparison.to_csv(results_dir / "graph_control_paired_cases.csv", index=False)
        summary.to_csv(results_dir / "graph_control_summary.csv", index=False)

        print("\nPaired case results saved:", results_dir / "graph_control_paired_cases.csv")
        print("Summary saved:", results_dir / "graph_control_summary.csv")

if __name__ == "__main__":
    main()

