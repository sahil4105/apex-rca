# Historical LLM evaluation audit (corrected)

This audit uses the raw per-incident records under `results/llm_evaluation/llm_per_incident_results.csv` and preserves the original artifacts byte-for-byte.

## Summary

- Total unique incidents: 30
- Total rows across all conditions: 150
- Live LLM rows: 68
- Fallback rows: 82
- Every condition evaluates the same 30 incidents; the condition sets are aligned.
- No historical failure_category or API error reason is recorded in the source CSV, so failure reasons are reported as unavailable rather than inferred.

## Live vs fallback accuracy by condition

| Condition | Total | Live LLM | Fallback | Overall accuracy | Live accuracy | Fallback accuracy |
|---|---:|---:|---:|---:|---:|---:|
| baseline_raw_logs | 30 | 9 | 21 | 0.4000 | 0.8889 | 0.1905 |
| method_anomaly_only | 30 | 16 | 14 | 0.4000 | 0.7500 | 0.0000 |
| proposed_topology_anomaly | 30 | 14 | 16 | 0.3667 | 0.7857 | 0.0000 |
| ranking_oracle_control | 30 | 14 | 16 | 0.3667 | 0.7857 | 0.0000 |
| ranking_top1_evidence | 30 | 15 | 15 | 0.3333 | 0.6667 | 0.0000 |

## Incident-overlap assessment

- All conditions share the same 30 incidents: True
- baseline_raw_logs vs method_anomaly_only: 30 shared incidents out of 30 unioned incidents.
- baseline_raw_logs vs proposed_topology_anomaly: 30 shared incidents out of 30 unioned incidents.
- baseline_raw_logs vs ranking_oracle_control: 30 shared incidents out of 30 unioned incidents.
- baseline_raw_logs vs ranking_top1_evidence: 30 shared incidents out of 30 unioned incidents.
- method_anomaly_only vs proposed_topology_anomaly: 30 shared incidents out of 30 unioned incidents.
- method_anomaly_only vs ranking_oracle_control: 30 shared incidents out of 30 unioned incidents.
- method_anomaly_only vs ranking_top1_evidence: 30 shared incidents out of 30 unioned incidents.
- proposed_topology_anomaly vs ranking_oracle_control: 30 shared incidents out of 30 unioned incidents.
- proposed_topology_anomaly vs ranking_top1_evidence: 30 shared incidents out of 30 unioned incidents.
- ranking_oracle_control vs ranking_top1_evidence: 30 shared incidents out of 30 unioned incidents.

## Key conclusions

- The summary JSON in the historical artifact is not a pure live-LLM accuracy table: it mixes live and fallback outcomes under the same aggregated accuracy figure.
- The historical CSV permits a strict separation of live LLM rows from fallback rows. When separated, live LLM accuracy is materially higher than fallback accuracy for each condition.
- The conditions are not biased by different incident subsets; each condition uses the same 30 case IDs. This supports within-condition comparisons, but it does not justify claiming superiority without caveats about the live-only sample size and fallback prevalence.
- Oracle control is explicitly an evaluation-only control and should not be conflated with ordinary live-model results.
- Failure reasons are unavailable in the saved historical data; any API failure analysis must be reported as unavailable rather than inferred.

## What cannot be concluded from the historical record

- A per-case causal explanation for every fallback row cannot be recovered because the dataset does not retain failure category or API error text.
- Statistical significance or superiority claims are not justified without a fresh, controlled experiment and a consistent live-only comparison design.
- The historical evaluation is a benchmark of the deployed workflow, not a clean, isolated measurement of raw model quality.
