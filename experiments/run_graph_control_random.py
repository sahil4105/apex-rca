"""Unconstrained random-graph control for graph-aware RCA."""

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


def random_graph_rewire(
    graph: nx.DiGraph,
    seed: int,
    attempts: int = 200,
) -> nx.DiGraph | None:
    """Generate a directed random graph with the same nodes and edge count.

    Self-loops and duplicate edges are excluded. Node degrees are not
    preserved, so this is an unconstrained random-graph control.
    """
    nodes = sorted(graph.nodes(), key=str)
    original_edges = set(graph.edges())
    edge_count = len(original_edges)

    if edge_count == 0 or edge_count > len(nodes) * (len(nodes) - 1):
        return None

    possible_edges = [
        (u, v)
        for u in nodes
        for v in nodes
        if u != v
    ]

    rng = random.Random(seed)
    original_weights = [
        float(graph[u][v].get("weight", 1.0))
        for u, v in sorted(original_edges, key=lambda e: (str(e[0]), str(e[1])))
    ]

    for _ in range(attempts):
        selected = rng.sample(possible_edges, edge_count)
        if set(selected) == original_edges:
            continue

        candidate = nx.DiGraph()
        candidate.add_nodes_from(graph.nodes(data=True))

        # Sort before assigning weights so results are reproducible.
        selected = sorted(selected, key=lambda e: (str(e[0]), str(e[1])))
        weights = original_weights.copy()
        rng.shuffle(weights)

        for (u, v), weight in zip(selected, weights):
            candidate.add_edge(u, v, weight=weight)

        if (
            candidate.number_of_nodes() == graph.number_of_nodes()
            and candidate.number_of_edges() == edge_count
            and nx.number_of_selfloops(candidate) == 0
            and set(candidate.edges()) != original_edges
        ):
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
                "reason": "no_edges_available_for_random_graph",
            })
            continue

        for repetition in range(N_SHUFFLES):
            shuffled = random_graph_rewire(
                graph.graph,
                seed=SEED + i * N_SHUFFLES + repetition,
            )

            if shuffled is None:
                skipped.append({
                    "case": real.case,
                    "reason": "random_graph_generation_failed",
                })
                continue

            from apex_rca.dependency_graph import DependencyGraph

            shuffled_dep = DependencyGraph(
                graph=shuffled,
                provenance="unconstrained_random_graph",
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
                "condition": "random_graph",
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

    output = results_dir / "graph_control_random_long.csv"
    pd.DataFrame(records).to_csv(output, index=False)

    skipped_path = results_dir / "graph_control_random_skipped.csv"
    pd.DataFrame(skipped).to_csv(skipped_path, index=False)

    print("\nResults saved:", output)
    print("Skipped/shuffle failures saved:", skipped_path)

    frame = pd.DataFrame(records)
    if not frame.empty:
        metric_cols = ["hit1", "hit3", "hit5", "mrr"]

        # Average randomized graph runs within each case first.
        shuffled = frame[frame["condition"] == "random_graph"]
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
            columns={metric: f"{metric}_random_graph" for metric in metric_cols}
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
        for condition in ["anomaly_only", "real_graph", "random_graph"]:
            row = {"condition": condition, "n_cases": len(comparison)}
            for metric in metric_cols:
                row[metric] = comparison[f"{metric}_{condition}"].mean()
            summary_rows.append(row)

        summary = pd.DataFrame(summary_rows)
        print(summary.set_index("condition").round(4).to_string())

        print("\nReal graph minus unconstrained random graph, paired mean differences:")
        for metric in metric_cols:
            delta = (
                comparison[f"{metric}_real_graph"]
                - comparison[f"{metric}_random_graph"]
            ).mean()
            print(f"{metric}: {delta:+.4f}")

        comparison.to_csv(results_dir / "graph_control_random_paired_cases.csv", index=False)
        summary.to_csv(results_dir / "graph_control_random_summary.csv", index=False)

        print("\nPaired case results saved:", results_dir / "graph_control_random_paired_cases.csv")
        print("Summary saved:", results_dir / "graph_control_random_summary.csv")

if __name__ == "__main__":
    main()



