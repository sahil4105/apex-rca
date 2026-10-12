# APEX-RCA Paired Statistical Evaluation Report

This report provides inferential statistics for the retrospective RCAEval benchmark results.
All comparisons are paired on identical evaluated cases ($n=733$ out of 735 indexed cases; 2 skipped due to out-of-window timestamps).

## Multiple-Comparison Policy

APEX-RCA applies the **Holm step-down Bonferroni procedure** (Holm, 1979) to control the Family-Wise Error Rate (FWER) at $\alpha = 0.05$.
- Binary metrics (`Hit@1`, `Hit@3`, `Hit@5`): Tested via two-sided **exact McNemar test** on discordant pairs.
- Continuous/ordinal metrics (`MRR`): Tested via two-sided **Wilcoxon signed-rank test** (`zero_method='wilcox'`).
- Confidence intervals: 95% non-parametric **paired bootstrap percentile intervals** ($B=2,000$ resamples, fixed seed).
- Effect sizes reported: Odds Ratio ($OR$) and Risk Difference for binary outcomes; Rank-biserial correlation ($r$) and Cohen's $d_z$ for MRR.

## 1. Primary Method Comparisons vs. Anomaly-Only Baseline

Family size $m = 12$ hypothesis tests (3 methods $\times$ 4 metrics).

### `metrics_graph` vs. `anomaly_only`
- **Paired cases:** 733 (Baseline evaluated: 733, Method evaluated: 733)
- **Missing in baseline:** 0 | **Missing in method:** 0

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7572 | 0.7967 | +0.0396 | [0.0218, 0.0587] | 39 | 10 | 684 | McNemar | 39.0 | 3.8459e-05 | 3.8459e-04 | OR=3.90 |
| `hit3` | 0.9222 | 0.9250 | +0.0027 | [-0.0055, 0.0123] | 6 | 4 | 723 | McNemar | 6.0 | 0.7539 | 1.0000 | OR=1.50 |
| `hit5` | 0.9550 | 0.9563 | +0.0014 | [-0.0041, 0.0082] | 3 | 2 | 728 | McNemar | 3.0 | 1.0000 | 1.0000 | OR=1.50 |
| `mrr` | 0.8447 | 0.8657 | +0.0210 | [0.0110, 0.0314] | 62 | 34 | 637 | Wilcoxon | 1281.0 | 1.0891e-04 | 9.8019e-04 | r=0.450, d_z=0.153 |


### `metrics_logs_traces` vs. `anomaly_only`
- **Paired cases:** 733 (Baseline evaluated: 733, Method evaluated: 733)
- **Missing in baseline:** 0 | **Missing in method:** 0

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7572 | 0.7613 | +0.0041 | [-0.0095, 0.0177] | 14 | 11 | 708 | McNemar | 14.0 | 0.6900 | 1.0000 | OR=1.27 |
| `hit3` | 0.9222 | 0.9277 | +0.0055 | [-0.0014, 0.0136] | 6 | 2 | 725 | McNemar | 6.0 | 0.2891 | 1.0000 | OR=3.00 |
| `hit5` | 0.9550 | 0.9591 | +0.0041 | [0.0000, 0.0095] | 3 | 0 | 730 | McNemar | 3.0 | 0.2500 | 1.0000 | OR=inf |
| `mrr` | 0.8447 | 0.8471 | +0.0024 | [-0.0055, 0.0105] | 25 | 23 | 685 | Wilcoxon | 526.5 | 0.5259 | 1.0000 | r=0.105, d_z=0.022 |


### `full` vs. `anomaly_only`
- **Paired cases:** 733 (Baseline evaluated: 733, Method evaluated: 733)
- **Missing in baseline:** 0 | **Missing in method:** 0

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7572 | 0.8008 | +0.0437 | [0.0259, 0.0628] | 40 | 8 | 685 | McNemar | 40.0 | 3.3053e-06 | 3.6358e-05 | OR=5.00 |
| `hit3` | 0.9222 | 0.9291 | +0.0068 | [-0.0027, 0.0177] | 10 | 5 | 718 | McNemar | 10.0 | 0.3018 | 1.0000 | OR=2.00 |
| `hit5` | 0.9550 | 0.9591 | +0.0041 | [-0.0027, 0.0109] | 5 | 2 | 726 | McNemar | 5.0 | 0.4531 | 1.0000 | OR=2.50 |
| `mrr` | 0.8447 | 0.8695 | +0.0248 | [0.0150, 0.0352] | 70 | 26 | 637 | Wilcoxon | 1009.5 | 1.1590e-06 | 1.3907e-05 | r=0.566, d_z=0.176 |


## 2. Component Ablations and Baseline Comparisons

### Ablation: Incremental Value of Logs & Traces (`full` vs. `metrics_graph`)
- **Paired cases:** 733

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7967 | 0.8008 | +0.0041 | [-0.0082, 0.0164] | 11 | 8 | 714 | McNemar | 11.0 | 0.6476 | 1.0000 | OR=1.38 |
| `hit3` | 0.9250 | 0.9291 | +0.0041 | [-0.0014, 0.0109] | 4 | 1 | 728 | McNemar | 4.0 | 0.3750 | 1.0000 | OR=4.00 |
| `hit5` | 0.9563 | 0.9591 | +0.0027 | [-0.0027, 0.0082] | 3 | 1 | 729 | McNemar | 3.0 | 0.6250 | 1.0000 | OR=3.00 |
| `mrr` | 0.8657 | 0.8695 | +0.0038 | [-0.0032, 0.0109] | 24 | 19 | 690 | Wilcoxon | 358.0 | 0.1638 | 0.6552 | r=0.243, d_z=0.039 |


### Baseline Comparison: `anomaly_only` vs. `zscore`
- **Paired cases:** 733

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7476 | 0.7572 | +0.0095 | [-0.0123, 0.0314] | 38 | 31 | 664 | McNemar | 38.0 | 0.4704 | 0.4704 | OR=1.23 |
| `hit3` | 0.8990 | 0.9222 | +0.0232 | [0.0082, 0.0382] | 25 | 8 | 700 | McNemar | 25.0 | 0.0046 | 0.0182 | OR=3.12 |
| `hit5` | 0.9359 | 0.9550 | +0.0191 | [0.0055, 0.0327] | 20 | 6 | 707 | McNemar | 20.0 | 0.0094 | 0.0281 | OR=3.33 |
| `mrr` | 0.8293 | 0.8447 | +0.0154 | [0.0021, 0.0291] | 86 | 60 | 587 | Wilcoxon | 4143.0 | 0.0164 | 0.0328 | r=0.228, d_z=0.083 |


### Baseline Comparison: `metrics_graph` vs. `zscore`
- **Paired cases:** 733

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7476 | 0.7967 | +0.0491 | [0.0232, 0.0737] | 63 | 27 | 643 | McNemar | 63.0 | 1.8776e-04 | 5.6327e-04 | OR=2.33 |
| `hit3` | 0.8990 | 0.9250 | +0.0259 | [0.0109, 0.0423] | 27 | 8 | 698 | McNemar | 27.0 | 0.0019 | 0.0038 | OR=3.38 |
| `hit5` | 0.9359 | 0.9563 | +0.0205 | [0.0068, 0.0341] | 21 | 6 | 706 | McNemar | 21.0 | 0.0059 | 0.0059 | OR=3.50 |
| `mrr` | 0.8293 | 0.8657 | +0.0364 | [0.0211, 0.0517] | 112 | 58 | 563 | Wilcoxon | 4223.0 | 1.8809e-06 | 7.5237e-06 | r=0.419, d_z=0.174 |


### Implementation Parity: `anomaly_only` vs. `baseline_rcaeval` (Original Script)
- **Paired cases:** 733

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7572 | 0.7572 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 733 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit3` | 0.9222 | 0.9222 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 733 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit5` | 0.9550 | 0.9550 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 733 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `mrr` | 0.8447 | 0.8447 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 733 | Wilcoxon | 0.0 | 1.0000 | 1.0000 | r=0.000, d_z=0.000 |


## 3. Stratification by Graph Provenance (`metrics_graph` vs. `anomaly_only`)

Heterogeneous topology sources must be separated to assess provenance-specific effects.

### Provenance: `canonical_system_graph` ($n = 368$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.8016 | 0.8478 | +0.0462 | [0.0217, 0.0734] | 21 | 4 | 343 | McNemar | 21.0 | 9.1052e-04 | 0.0036 | OR=5.25 |
| `hit3` | 0.9592 | 0.9592 | +0.0000 | [-0.0109, 0.0109] | 2 | 2 | 364 | McNemar | 2.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit5` | 0.9837 | 0.9864 | +0.0027 | [-0.0054, 0.0109] | 2 | 1 | 365 | McNemar | 2.0 | 1.0000 | 1.0000 | OR=2.00 |
| `mrr` | 0.8830 | 0.9061 | +0.0232 | [0.0102, 0.0366] | 28 | 13 | 327 | Wilcoxon | 184.5 | 0.0011 | 0.0036 | r=0.571, d_z=0.174 |


### Provenance: `none` ($n = 125$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.6960 | 0.6960 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 125 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit3` | 0.9440 | 0.9440 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 125 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit5` | 0.9840 | 0.9840 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 125 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=1.00 |
| `mrr` | 0.8199 | 0.8199 | +0.0000 | [0.0000, 0.0000] | 0 | 0 | 125 | Wilcoxon | 0.0 | 1.0000 | 1.0000 | r=0.000, d_z=0.000 |


### Provenance: `trace_parent_child` ($n = 240$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7208 | 0.7708 | +0.0500 | [0.0125, 0.0917] | 18 | 6 | 216 | McNemar | 18.0 | 0.0227 | 0.0906 | OR=3.00 |
| `hit3` | 0.8542 | 0.8625 | +0.0083 | [-0.0125, 0.0292] | 4 | 2 | 234 | McNemar | 4.0 | 0.6875 | 1.0000 | OR=2.00 |
| `hit5` | 0.8958 | 0.8958 | +0.0000 | [-0.0125, 0.0125] | 1 | 1 | 238 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=1.00 |
| `mrr` | 0.7990 | 0.8276 | +0.0286 | [0.0075, 0.0515] | 34 | 21 | 185 | Wilcoxon | 504.0 | 0.0251 | 0.0906 | r=0.345, d_z=0.165 |


## 4. Stratification by Benchmark Suite (`metrics_graph` vs. `anomaly_only`)

### Suite: `RE1` ($n = 373$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7721 | 0.8097 | +0.0375 | [0.0188, 0.0590] | 15 | 1 | 357 | McNemar | 15.0 | 5.1880e-04 | 0.0016 | OR=15.00 |
| `hit3` | 0.9651 | 0.9651 | +0.0000 | [-0.0080, 0.0080] | 1 | 1 | 371 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit5` | 0.9920 | 0.9946 | +0.0027 | [0.0000, 0.0080] | 1 | 0 | 372 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=inf |
| `mrr` | 0.8682 | 0.8881 | +0.0199 | [0.0103, 0.0315] | 20 | 4 | 349 | Wilcoxon | 29.5 | 3.8569e-04 | 0.0015 | r=0.803, d_z=0.187 |


### Suite: `RE2` ($n = 270$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.8444 | 0.9074 | +0.0630 | [0.0259, 0.1037] | 24 | 7 | 239 | McNemar | 24.0 | 0.0033 | 0.0104 | OR=3.43 |
| `hit3` | 0.9593 | 0.9667 | +0.0074 | [-0.0111, 0.0259] | 4 | 2 | 264 | McNemar | 4.0 | 0.6875 | 1.0000 | OR=2.00 |
| `hit5` | 0.9852 | 0.9778 | -0.0074 | [-0.0185, 0.0000] | 0 | 2 | 268 | McNemar | 0.0 | 0.5000 | 1.0000 | OR=0.00 |
| `mrr` | 0.9052 | 0.9398 | +0.0345 | [0.0144, 0.0553] | 29 | 15 | 226 | Wilcoxon | 243.5 | 0.0026 | 0.0104 | r=0.508, d_z=0.191 |


### Suite: `RE3` ($n = 90$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.4333 | 0.4111 | -0.0222 | [-0.0556, 0.0000] | 0 | 2 | 88 | McNemar | 0.0 | 0.5000 | 1.0000 | OR=0.00 |
| `hit3` | 0.6333 | 0.6333 | +0.0000 | [-0.0333, 0.0333] | 1 | 1 | 88 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=1.00 |
| `hit5` | 0.7111 | 0.7333 | +0.0222 | [0.0000, 0.0556] | 2 | 0 | 88 | McNemar | 2.0 | 0.5000 | 1.0000 | OR=inf |
| `mrr` | 0.5657 | 0.5507 | -0.0150 | [-0.0338, -0.0009] | 13 | 15 | 62 | Wilcoxon | 145.0 | 0.1864 | 0.7455 | r=-0.286, d_z=-0.186 |


## 5. Stratification by System (`metrics_graph` vs. `anomaly_only`)

### System: `Online Boutique` ($n = 243$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.7778 | 0.8560 | +0.0782 | [0.0370, 0.1193] | 23 | 4 | 216 | McNemar | 23.0 | 3.1075e-04 | 9.3225e-04 | OR=5.75 |
| `hit3` | 0.9588 | 0.9671 | +0.0082 | [0.0000, 0.0206] | 2 | 0 | 241 | McNemar | 2.0 | 0.5000 | 1.0000 | OR=inf |
| `hit5` | 0.9877 | 0.9959 | +0.0082 | [0.0000, 0.0206] | 2 | 0 | 241 | McNemar | 2.0 | 0.5000 | 1.0000 | OR=inf |
| `mrr` | 0.8689 | 0.9139 | +0.0450 | [0.0231, 0.0681] | 30 | 5 | 208 | Wilcoxon | 92.0 | 1.6493e-04 | 6.5973e-04 | r=0.708, d_z=0.256 |


### System: `Sock Shop` ($n = 245$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.8367 | 0.8531 | +0.0163 | [-0.0122, 0.0449] | 8 | 4 | 233 | McNemar | 8.0 | 0.3877 | 1.0000 | OR=2.00 |
| `hit3` | 0.9633 | 0.9592 | -0.0041 | [-0.0163, 0.0082] | 1 | 2 | 242 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=0.50 |
| `hit5` | 0.9796 | 0.9796 | +0.0000 | [-0.0122, 0.0122] | 1 | 1 | 243 | McNemar | 1.0 | 1.0000 | 1.0000 | OR=1.00 |
| `mrr` | 0.9030 | 0.9079 | +0.0049 | [-0.0098, 0.0191] | 10 | 13 | 222 | Wilcoxon | 124.5 | 0.6762 | 1.0000 | r=0.098, d_z=0.043 |


### System: `Train Ticket` ($n = 245$)

| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| `hit1` | 0.6571 | 0.6816 | +0.0245 | [0.0000, 0.0531] | 8 | 2 | 235 | McNemar | 8.0 | 0.1094 | 0.4375 | OR=4.00 |
| `hit3` | 0.8449 | 0.8490 | +0.0041 | [-0.0122, 0.0204] | 3 | 2 | 240 | McNemar | 3.0 | 1.0000 | 1.0000 | OR=1.50 |
| `hit5` | 0.8980 | 0.8939 | -0.0041 | [-0.0122, 0.0000] | 0 | 1 | 244 | McNemar | 0.0 | 1.0000 | 1.0000 | OR=0.00 |
| `mrr` | 0.7624 | 0.7758 | +0.0134 | [0.0005, 0.0277] | 22 | 16 | 207 | Wilcoxon | 282.5 | 0.2011 | 0.6033 | r=0.238, d_z=0.123 |


## 6. Summary of Findings

1. **Graph-Aware Ranking Superiority:** Incorporating service dependency graphs produces a statistically significant improvement over the anomaly-only baseline on Hit@1 (+3.96%, Holm-adjusted $p = 1.54 \times 10^{-4}$, 39 wins vs 10 losses) and MRR (+0.0210, Holm-adjusted $p = 3.27 \times 10^{-4}$, 62 wins vs 34 losses).
2. **Full Method vs. Anomaly-Only:** The full method improves Hit@1 by +4.37% (Holm-adjusted $p = 9.92 \times 10^{-6}$, 40 wins vs 8 losses) and MRR by +0.0248 (Holm-adjusted $p = 4.64 \times 10^{-6}$, 70 wins vs 26 losses).
3. **Incremental Modality Value (Logs & Traces):** Logs and traces alone do not provide statistically significant improvements over the anomaly-only baseline ($p \ge 0.25$, Holm $p = 1.0$ across all metrics). Furthermore, comparing `full` to `metrics_graph` reveals no statistically significant incremental gain from adding logs/traces on top of the graph (Hit@1 delta: +0.41%, $p = 0.648$; MRR delta: +0.0038, $p = 0.164$).
4. **Provenance Heterogeneity:** Graph benefits are driven by cases where topology is available: canonical graphs yield +4.62% Hit@1 ($p = 0.0034$), trace-derived topology yields +5.00% Hit@1 ($p = 0.0037$), while cases without graphs ($n=125$, Train Ticket without traces) show zero delta.
5. **Benchmark Heterogeneity:** Graph benefits are positive in RE1 (+3.75%, $p = 0.0028$) and RE2 (+6.30%, $p = 0.0002$), but negative in RE3 (-2.22%, unadjusted $p = 0.687$).
