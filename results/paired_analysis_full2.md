# Paired Statistical Analysis - RCAEval full2

This report analyses existing per-case CSV outputs; it does not rerun experiments.

- Bootstrap resamples: 10000
- Random seed: 42
- Confidence intervals: paired percentile bootstrap, 95%.
- Hit@k tests: exact two-sided McNemar.
- MRR test: Wilcoxon signed-rank.
- Multiplicity: Holm correction across the four metrics within each method comparison.

Positive mean deltas favor the method named in the comparison.

| Baseline | Method | Metric | Paired n | Mean delta | 95% CI low | 95% CI high | Raw p | Holm p | Wins | Losses | Ties |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| anomaly_only | metrics_graph | hit1 | 733 | 0.039563 | 0.020464 | 0.058663 | 0.000038 | 0.000154 | 39 | 10 | 684 |
| anomaly_only | metrics_graph | hit3 | 733 | 0.002729 | -0.005457 | 0.010914 | 0.753906 | 1.000000 | 6 | 4 | 723 |
| anomaly_only | metrics_graph | hit5 | 733 | 0.001364 | -0.004093 | 0.008186 | 1.000000 | 1.000000 | 3 | 2 | 728 |
| anomaly_only | metrics_graph | mrr | 733 | 0.021000 | 0.011110 | 0.031197 | 0.000109 | 0.000327 | 62 | 34 | 637 |
| anomaly_only | metrics_logs_traces | hit1 | 733 | 0.004093 | -0.009550 | 0.017735 | 0.690038 | 1.000000 | 14 | 11 | 708 |
| anomaly_only | metrics_logs_traces | hit3 | 733 | 0.005457 | -0.001364 | 0.013643 | 0.289062 | 1.000000 | 6 | 2 | 725 |
| anomaly_only | metrics_logs_traces | hit5 | 733 | 0.004093 | 0.000000 | 0.009550 | 0.250000 | 1.000000 | 3 | 0 | 730 |
| anomaly_only | metrics_logs_traces | mrr | 733 | 0.002362 | -0.005420 | 0.010320 | 0.525902 | 1.000000 | 25 | 23 | 685 |
| anomaly_only | full | hit1 | 733 | 0.043656 | 0.025921 | 0.062756 | 0.000003 | 0.000010 | 40 | 8 | 685 |
| anomaly_only | full | hit3 | 733 | 0.006821 | -0.002729 | 0.017735 | 0.301758 | 0.603516 | 10 | 5 | 718 |
| anomaly_only | full | hit5 | 733 | 0.004093 | -0.002729 | 0.010914 | 0.453125 | 0.603516 | 5 | 2 | 726 |
| anomaly_only | full | mrr | 733 | 0.024790 | 0.015026 | 0.035147 | 0.000001 | 0.000005 | 70 | 26 | 637 |
| metrics_graph | full | hit1 | 733 | 0.004093 | -0.006821 | 0.016371 | 0.647606 | 1.000000 | 11 | 8 | 714 |
| metrics_graph | full | hit3 | 733 | 0.004093 | -0.001364 | 0.010914 | 0.375000 | 1.000000 | 4 | 1 | 728 |
| metrics_graph | full | hit5 | 733 | 0.002729 | -0.002729 | 0.008186 | 0.625000 | 1.000000 | 3 | 1 | 729 |
| metrics_graph | full | mrr | 733 | 0.003790 | -0.003082 | 0.010990 | 0.163792 | 0.655167 | 24 | 19 | 690 |

## Interpretation notes

- Confidence intervals describe uncertainty in the paired mean difference.
- Holm-adjusted p-values address multiple testing within each method's four-metric family.
- Statistical significance does not establish practical importance or causal validity.
- This analysis only covers the cases present in both files for each comparison.
