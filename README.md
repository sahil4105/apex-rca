# APEX-RCA

**APEX-RCA: An Evidence-Grounded Approach to Root Cause Analysis in Microservices Using Dependency Graphs and Telemetry Data**

Research question: Does incorporating service dependency information into telemetry-based anomaly ranking improve root-cause identification compared with an anomaly-only baseline, and how much additional value can be obtained from logs and traces?

This repository is a reproducible RCAEval experiment plus a local Streamlit demo. The main contribution is a measurable ranking pipeline, not an LLM wrapper.

## Setup (Windows)

Python 3.13, existing `.venv`. From `D:\apex-rca`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

RCAEval is expected at `data/rcaeval` (735 cases). Re-download only if missing:

```powershell
.venv\Scripts\python.exe experiments\prepare_dataset.py
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

## Experiments

Frozen original baseline (do not overwrite its CSV unless you intend to replace the historical artifact):

```powershell
.venv\Scripts\python.exe experiments\baseline_rcaeval.py --limit 0
```

Packaged methods (writes `results/*_v1.csv` and `results/summary_v1.json`):

```powershell
.venv\Scripts\python.exe experiments\run_rcaeval.py --method anomaly_only --tag v1 --limit 0
.venv\Scripts\python.exe experiments\run_rcaeval.py --method all --tag v1 --limit 0
.venv\Scripts\python.exe experiments\analyze_re3.py
.venv\Scripts\python.exe experiments\write_results_md.py
.venv\Scripts\python.exe experiments\compare_results.py
.venv\Scripts\python.exe experiments\analyze_graph_controls.py
```

Use `--limit 20` for a smoke run. The evaluated task is retrospective post-injection diagnosis: reference window `[time_start, inject_time)`, observation window `[inject_time, time_end)`.

`compare_results.py` reads existing `summary_*.json` and `config_*.json`
artifacts without rerunning experiments. `analyze_graph_controls.py` reads
the existing graph-control paired CSVs and writes a new inferential JSON
report; it averages randomized runs within each case before paired inference.

## Demo

```powershell
.venv\Scripts\streamlit.exe run app.py
```

Select a case. Rankings are produced from that case’s files only. Ground truth is labelled separately from predictions. Missing logs/traces are shown as missing, not as evidence of health.

## Documentation

- `docs/methodology.md`
- `docs/architecture.md`
- `docs/experiment_protocol.md`
- `docs/results.md` (generated from CSVs)
- `docs/limitations.md`
- `docs/HANDOFF.md`

## Layout

- `apex_rca/` algorithm modules
- `experiments/` runners
- `tests/` unit tests
- `results/` generated metrics (gitignored CSVs)
- `data/` datasets (not source-controlled)
