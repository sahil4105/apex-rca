# Limitations and threats to validity

1. **Retrospective windows.** Evaluation conditions on `inject_time`. A production detector would need change-point estimation.
2. **Two RCAEval timing defects.** Those cases are skipped, not repaired by guessing timestamps.
3. **Canonical graphs are not case-specific.** Online Boutique and Sock Shop fallbacks come from public demo architectures. They may omit runtime edges (sidecars, `main`, exporters) present in metrics.
4. **Train Ticket topology is incomplete without traces.** No full canonical graph is shipped. RE1 Train Ticket therefore has no dependency evidence.
5. **Name alignment is partial.** `frontendservice` maps to `frontend`. Other mismatches (for example `main`) stay unmatched.
6. **Log features are keyword-based.** They miss silent code-level faults and can fire on noisy error strings.
7. **Trace `statusCode` is often null** on Train Ticket, reducing that signal.
8. **RE3 faults are code-level (F1–F5)** rather than resource faults. Metric median shifts can be weak, especially on Train Ticket.
9. **Hyperparameters are a priori.** λ and extra-weight were not nested-validated. Do not treat them as optimally tuned.
10. **High RE1/RE2 anomaly-only scores** may indicate easily separable resource faults in this benchmark, not general RCA difficulty.
11. **OpenRCA is a different task.** Queries, components, and metric files do not share RCAEval’s service-column schema.
12. **No literature citations are invented here.** Related-work names to verify later include MonitorRank, MicroRCA, BARO, CIRCA, and the RCAEval paper. Confirm bibliographic details before a dissertation chapter.
13. **Graph time scope is case-level.** Trace-derived topology currently uses the full recorded trace file for a case, while metric/log/trace evidence scores use the declared half-open case interval. This is an explicit protocol choice, not evidence that topology would be available before the incident.
14. **Statistical comparisons are paired and family-corrected.** The additive comparison report covers the configured method/metric family with paired bootstrap intervals, exact McNemar tests for Hit@k, Wilcoxon tests for MRR, and Holm-adjusted p-values. It does not eliminate dependence from repeated cases within a benchmark system.
15. **Existing result artifacts predate the boundary/reporting changes.** The current stored CSVs and summaries are preserved. New full-suite results should be generated under a new tag if the boundary behavior changes any case.
