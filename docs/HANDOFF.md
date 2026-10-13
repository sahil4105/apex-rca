# APEX-RCA — Project Handover

## Project status

APEX-RCA evaluates topology-grounded root-cause identification for microservices using retrospective telemetry data. It is a research pipeline and inspection dashboard, not a production monitoring or automated remediation platform.

## Completed

- RCAEval index and telemetry availability audited across 735 indexed cases.
- Main RCAEval full run completed: 733 cases evaluated; 2 skipped because injection timestamps fell outside metric windows.
- Anomaly-only, graph-aware, logs/traces, and full methods evaluated.
- Paired statistical analysis generated for the main benchmark.
- OpenRCA Bank and Telecom evaluation pipelines implemented.
- Bank and Telecom results and Telecom sensitivity analyses saved under `results/`.
- Canonical incident representation and scoring modules implemented.
- Tests added for canonical scoring and Telecom adapter behavior.
- Reproducibility manifest updated.

## Main RCAEval full-run results

| Method | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---:|---:|---:|---:|
| Anomaly-only | 0.7572 | 0.9222 | 0.9550 | 0.8447 |
| Metrics + graph | 0.7967 | 0.9250 | 0.9563 | 0.8657 |
| Metrics, logs and traces | 0.7613 | 0.9277 | 0.9591 | 0.8471 |
| Full method | 0.8008 | 0.9291 | 0.9591 | 0.8695 |

These are saved results. A collaborator must rerun the workflow before claiming independent reproduction.

## OpenRCA validation

- **Bank:** 135 evaluated incidents; 1 incident had no scored components. Strict Hit@1: 0.17037; tie-aware Hit@1: 0.28148; tie-aware MRR: 0.37242.
- **Telecom primary v2:** 47 evaluated incidents; 3 had no scored components and 1 had unscoreable ground truth. Strict Hit@1: 0.04255; tie-aware Hit@1: 0.06383; MRR: 0.14807.
- Telecom sensitivity outputs are stored in `results/telecom_sensitivity_5_*` and `results/telecom_sensitivity_30_*`.

OpenRCA results are dataset-specific and should not be directly treated as equivalent to RCAEval results. Consider telemetry coverage, scoreability, and dataset assumptions when interpreting them.

## Data and reproducibility requirements

- RCAEval dataset: local under `data/rcaeval/`.
- OpenRCA working dataset: local under `data/openrca/processed/`.
- Bank evaluation uses the generated cache under `results/bank_metric_cache/`. It can be regenerated from processed Bank telemetry using `experiments/build_bank_metric_cache.py`; the script refuses to overwrite existing cache files.
- Telecom evaluation expects `telemetry/<date>/metric/` beneath the Telecom dataset folder.
- `data/` is excluded from ordinary Git commits. Follow `README.md` for official dataset sources and preparation instructions.
- `data/openrca/processed_curated/` has a different metric layout and must not replace `processed/` for the current Telecom adapter without code changes and validation.

The OpenRCA preparation script can be slow because it counts rows in large CSV files. If it is interrupted, inspect the output and validate the required files; do not assume preparation completed.

## Key files

- `experiments/run_rcaeval.py` — main RCAEval experiments.
- `experiments/paired_analysis.py` — paired statistical analysis.
- `experiments/evaluate_openrca_bank.py` — Bank evaluation.
- `experiments/evaluate_openrca_telecom.py` — Telecom evaluation.
- `experiments/prepare_openrca_bank_telecom.py` — processed OpenRCA preparation and audit.
- `experiments/build_bank_metric_cache.py` — Bank cache generation.
- `results/` — saved experiment outputs and summaries.
- `docs/limitations.md` — research limitations.
- `docs/experiment_protocol.md` — experimental procedure.
- `docs/openrca_protocol.md` — OpenRCA evaluation protocol.

## Remaining work

1. Run the test suite and record the actual result.
2. Check that the README and handover match the scripts and saved outputs.
3. Verify that a collaborator can restore the required datasets and reproduce selected results.
4. Review the complete staged change set and integrate the completed work into `main`.
5. Optional: perform the Train Ticket graph-quality audit if time permits.
