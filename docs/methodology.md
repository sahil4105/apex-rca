# Methodology

## Research objective

Working title: **APEX-RCA: An Evidence-Grounded Approach to Root Cause Analysis in Microservices Using Dependency Graphs and Telemetry Data**

Research question: Does incorporating service dependency information into telemetry-based anomaly ranking improve root-cause identification compared with an anomaly-only baseline, and how much additional value can be obtained from logs and traces?

## Task definition

The evaluated task is **retrospective post-injection diagnosis**.

For each RCAEval case:

1. The fault injection timestamp `inject_time` is treated as known.
2. Rows with `time < inject_time` form the **reference window**.
3. Rows with `time >= inject_time` form the **observation window**.
4. Services are ranked from those windows, then compared with `root_cause_service`.

This is not a real-time detector and is not claimed to be leakage-free for online diagnosis. The protocol uses post-fault telemetry that would be available after an incident has been observed, given a known change point.

All metric, log, and trace evidence uses the half-open recorded case interval
`[time_start, time_end)`. The reference interval is
`[time_start, inject_time)` and the observation interval is
`[inject_time, time_end)`. This makes the case-end boundary explicit and
prevents a terminal sample from being included inconsistently across
modalities.

Cases where `inject_time` lies outside `[time_start, time_end]` are skipped and reported. They are not counted as successes.

## Baseline (`anomaly_only`, version aligned with `experiments/baseline_rcaeval.py`)

1. Parse metric columns with longest-suffix matching (`latency-90` before `latency`).
2. For each numeric service metric, compute a robust effect size: absolute median shift divided by a MAD scale (`1.4826 * MAD`), with standard-deviation and relative-median fallbacks for near-constant series, capped at 20.
3. Aggregate a service as the mean of its strongest three metric effects so services with more columns do not automatically dominate.
4. Rank services by that score (ties broken by service name).

The original runner `experiments/baseline_rcaeval.py` is retained so historical `results/baseline_rcaeval.csv` remains comparable. The packaged `anomaly_only` method reproduces the same scoring; the only skip-reason wording change is the explicit out-of-window inject-time check, which matches the two previously skipped cases.

## Dependency-aware ranking (`metrics_graph`)

Directed edges are **caller → callee**.

The declared graph protocol is `graph_time_scope =
full_recorded_case_trace`: when trace files are available, parent-child
topology is derived from the full recorded trace file for that case. This is
treated as case-level topology evidence, not as a pre-injection-only signal.
Canonical Online Boutique and Sock Shop graphs are static public architecture
priors. The graph scope is recorded in each serialized experiment
configuration so that a future pre-injection or observation-window graph
variant is a distinct protocol rather than an unreported implementation
change.

Graph provenance is recorded per case and is one of:

- `trace_parent_child`: parent span service → child span service, after validating `spanID` / `parentSpanID` joins. Same-trace co-occurrence is not an edge.
- `canonical_system_graph`: published Online Boutique and Sock Shop call graphs, used only when traces do not yield edges (typical for RE1).
- `none`: no edges. Train Ticket has no canonical graph in this repository. Ranking then equals the telemetry scores.

Ranking formula, with λ = 0.30 chosen a priori (not grid-searched on RCAEval labels):

`S(s) = (1-λ) Â(s) + λ π̂(s)`

where `Â` is min-max normalized anomaly score within the case and `π` is Personalized PageRank on the caller→callee graph with damping 0.85 and personalization proportional to anomaly scores. Anomalous callers therefore spread mass toward services they depend on.

## Logs and traces (`metrics_logs_traces` and `full`)

Used only when files exist for that case. Missing modalities contribute nothing and are not interpreted as health.

- Logs: change in error-like message rate (`error|exception|fail|timeout|…`) per container, mapped onto metric service names.
- Traces: robust duration shift plus increase in non-zero `statusCode` rate, when those fields are populated.

Extra scores are added as `metric_score + extra_weight * extra`, with `extra_weight = 0.25` chosen a priori. The `full` method then applies the same graph combination as `metrics_graph`.

## Evaluation

Metrics: Hit@1, Hit@3, Hit@5, MRR. Denominators are evaluated cases only. Skips are stored with reasons. Breakdowns are reported by suite, system, and fault type. Per-method bootstrap 95% intervals use 2000 resamples and seed 42. Paired binary Hit@k comparisons use exact McNemar tests; paired MRR comparisons use a two-sided Wilcoxon signed-rank test. Paired mean-difference confidence intervals are percentile bootstrap intervals over case-level paired differences. The additive comparison output applies Holm step-down correction across the declared method/metric comparison family.

Paired comparisons are formed by an inner join on unique case IDs and record
the method-specific counts, intersection count, mean delta, confidence
interval, raw p-value, adjusted p-value, and test name. Repeated randomized
graph runs are averaged within case before inference and are never treated as
independent cases.

## Hyperparameters

`graph_weight`, `extra_weight`, PageRank damping, and minimum trace-edge count are documented defaults. They were not nested-cross-validated on RCAEval because the public benchmark is commonly used as a whole. That is a limitation: these values could overfit if later tuned on the same labels.
