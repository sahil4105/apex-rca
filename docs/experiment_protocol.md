# Experiment protocol

## Primary benchmark: RCAEval

Path: `data/rcaeval` (735 indexed cases). Do not re-download unless the index is missing.

Suites: RE1 375, RE2 270, RE3 90. Systems: Online Boutique, Sock Shop, Train Ticket (245 each).

## Frozen original baseline

Artifact: `results/baseline_rcaeval.csv` (733 evaluated, 2 skipped).

Skipped originally:

- `re1ob_currencyservice_loss_1` — `inject_time=16933142` is outside `[time_start, time_end]` (truncated timestamp also stored in `inject_time.txt`).
- `re1ob_productcatalogservice_cpu_3` — `inject_time` is after `time_end`; zero post-injection metric rows.

Do not overwrite that CSV when running new methods.

## Commands

From `D:\apex-rca`, using `.venv`:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe experiments\run_rcaeval.py --method anomaly_only --tag v1 --limit 0
.venv\Scripts\python.exe experiments\run_rcaeval.py --method all --tag v1 --limit 0
.venv\Scripts\python.exe experiments\analyze_re3.py
.venv\Scripts\streamlit.exe run app.py
```

`--limit 20` runs a smoke sample. `--suite RE3` restricts to RE3.

## Ablations

| Method | Metrics | Graph | Logs/traces |
|---|---|---|---|
| `anomaly_only` | yes | no | no |
| `metrics_graph` | yes | yes | no |
| `metrics_logs_traces` | yes | no | yes if present |
| `full` | yes | yes | yes if present |

Comparisons among methods use the intersection of successfully evaluated cases.

## OpenRCA

Processed Bank/Telecom metrics live under `data/openrca/processed`. Labels and schemas differ from RCAEval and must not be pooled into one accuracy number. External validation is a follow-on experiment; see the handoff note for status.
