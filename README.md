# APEX-RCA

**A Topology-Grounded Root Cause Analysis Pipeline for Microservices Using Dependency Graphs and Telemetry Data**

APEX-RCA studies whether service-dependency information improves telemetry-based root-cause identification compared with anomaly-only ranking, and whether logs and traces add further value.

The project includes a Python ranking pipeline, benchmark experiments, statistical analysis, tests, and a local Streamlit dashboard. It is a retrospective research tool, not a production monitoring or automated remediation platform.

## 1. Project status and scope

- **Primary benchmark:** RCAEval, with 735 indexed failure cases across RE1, RE2, and RE3.
- **Task:** Retrospective root-cause diagnosis using the recorded fault-injection timestamp.
- **Main comparison:** Anomaly-only ranking versus dependency-graph-aware ranking.
- **Additional comparison:** The contribution of logs and traces.
- **Additional validation:** OpenRCA Bank and Telecom, evaluated separately from RCAEval.
- **Dashboard:** A local interface for inspecting saved results and incident evidence.
- **Saved outputs:** Per-incident CSVs, summary JSON files, sensitivity analyses, and statistical reports are stored under `results/`.

Existing results are committed research artifacts; their presence does not mean a new collaborator has independently reproduced them. Some experiment commands can overwrite outputs. Use a new tag where supported, and back up important artifacts before rerunning experiments.

## 2. Prerequisites

For Windows:

- Git
- Python 3.13
- PyCharm or another Python IDE (optional)
- Internet access to obtain datasets
- Several GB of free disk space for RCAEval, plus space for working data and generated outputs

Run the following commands from PowerShell at the repository root unless stated otherwise.

## 3. Clone and install

```powershell
git clone https://github.com/sahil4105/apex-rca.git
cd apex-rca
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked or inconvenient, call the project interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Datasets

Datasets are not stored in the ordinary Git repository. Downloaded data belongs under `data/`, which is ignored by Git. Follow the dataset owners' instructions and licensing terms; do not commit raw archives or extracted telemetry.

### 4.1 RCAEval — primary benchmark

Official sources:

- Dataset: https://huggingface.co/datasets/phamquiluan/RCAEval
- Code and documentation: https://github.com/phamquiluan/RCAEval

The project has indexed 735 failure cases across RE1, RE2, and RE3. The downloaded dataset is several GB, depending on the files and local representation.

From the repository root, run the preparation workflow:

```powershell
.\.venv\Scripts\python.exe experiments\prepare_dataset.py
```

The project expects prepared data under `data/rcaeval/`. Inspect the script output and resulting layout before running experiments. If you download the dataset manually, the Hugging Face repository can be fetched with:

```powershell
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='phamquiluan/RCAEval', repo_type='dataset', local_dir='data/rcaeval')"
```

A direct snapshot download does not guarantee that every local layout assumption in the project preparation code has been met. Verify the prepared structure before running a benchmark.

### 4.2 OpenRCA — additional validation

Official repository and dataset instructions:

- https://github.com/microsoft/OpenRCA

The current OpenRCA evaluation scripts expect the prepared dataset under:

```text
data/
└── openrca/
    └── processed/
        ├── Bank/
        │   ├── query.csv
        │   ├── record.csv
        │   └── telemetry/
        │       └── <date>/
        │           └── metric/
        └── Telecom/
            ├── query.csv
            ├── record.csv
            └── telemetry/
                └── <date>/
                    └── metric/
```

The `processed/` layout is important. In particular, the Telecom adapter expects `telemetry/<date>/metric/`; the `processed_curated/` preparation output uses a different metric-folder layout and must not be substituted without changing and testing the adapter.

The preparation script creates `data/openrca/processed_curated/` and writes an audit report and inventories. It copies and hash-verifies the selected metric files, but it can be slow because it reads large CSVs to count rows. If it is interrupted, do not assume the preparation completed. Inspect its output and validate required files before using the curated folder.

```powershell
.\.venv\Scripts\python.exe experiments\prepare_openrca_bank_telecom.py
```

#### Bank metric cache

The Bank evaluator reads `record.csv` from the processed Bank directory and loads metric observations from `results/bank_metric_cache/`. This cache is a generated evaluation artifact; the current cache is small enough to keep with the research results. To rebuild it from the processed Bank telemetry, first ensure the cache directory does not already contain files, because the script intentionally refuses to overwrite existing cache files:

```powershell
.\.venv\Scripts\python.exe experiments\build_bank_metric_cache.py
```

Do not delete the source processed dataset if you may need to rebuild the cache.

## 5. Verify the installation

Run the unit tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Import-check the dashboard:

```powershell
.\.venv\Scripts\python.exe -c "import app; print('app import: OK')"
```

These checks verify the test suite and basic application import. They do not replace a full experiment run or manual dashboard testing. Record the actual output from your machine; do not rely on an earlier reported test count.

## 6. Run the dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit.

The dashboard is for research inspection of saved results and incident evidence. It is not a live monitoring service, an incident-management system, or an automatic remediation tool. Missing telemetry must not be interpreted as proof that a service is healthy.

## 7. Run experiments

Run commands from the repository root. Inspect each script's arguments and output paths before execution.

### RCAEval baseline

This may overwrite the baseline output. Back up the existing artifact first if it must be preserved.

```powershell
.\.venv\Scripts\python.exe experiments\baseline_rcaeval.py --limit 0
```

### RCAEval methods

Run a small smoke test first:

```powershell
.\.venv\Scripts\python.exe experiments\run_rcaeval.py --method anomaly_only --tag smoke --limit 20
```

Run all supported methods on the full dataset:

```powershell
.\.venv\Scripts\python.exe experiments\run_rcaeval.py --method all --tag full2 --limit 0
```

Use a new tag for new runs where supported. Reusing a tag may overwrite existing results.

### Analysis scripts

```powershell
.\.venv\Scripts\python.exe experiments\analyze_re3.py
.\.venv\Scripts\python.exe experiments\compare_results.py
.\.venv\Scripts\python.exe experiments\analyze_graph_controls.py
.\.venv\Scripts\python.exe experiments\write_results_md.py
.\.venv\Scripts\python.exe experiments\paired_analysis.py
```

Some scripts generate or update reports; check their output paths before running them.

The main evaluation uses the reference window `[time_start, inject_time)` and the observation window `[inject_time, time_end)`. The injection timestamp is treated as known.

### OpenRCA evaluation

The Bank and Telecom evaluators use the dataset layout described in Section 4.2:

```powershell
.\.venv\Scripts\python.exe experiments\evaluate_openrca_bank.py
.\.venv\Scripts\python.exe experiments\evaluate_openrca_telecom.py
```

Check each script's `--help` output if you need to change its options. Do not overwrite the saved primary outputs without backing them up or selecting a supported new output name.

## 8. Results and evaluation

The `results/` directory contains previously generated outputs. Common metrics include:

- **Hit@1:** Whether a correct root-cause service ranks first.
- **Hit@3 / Hit@5:** Whether a correct service appears in the top three or five.
- **MRR:** Mean reciprocal rank of the correct service.
- **Paired statistical comparisons:** Comparisons on the same evaluated cases.

Always report evaluated, skipped, and unscoreable case counts alongside scores. Interpret findings with `docs/limitations.md` and `docs/experiment_protocol.md`.

### Main RCAEval full-run results

The saved `full2` run reports the following values:

| Method | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---:|---:|---:|---:|
| Anomaly-only | 0.7572 | 0.9222 | 0.9550 | 0.8447 |
| Metrics + graph | 0.7967 | 0.9250 | 0.9563 | 0.8657 |
| Metrics, logs and traces | 0.7613 | 0.9277 | 0.9591 | 0.8471 |
| Full method | 0.8008 | 0.9291 | 0.9591 | 0.8695 |

The full run evaluated 733 cases; 2 were skipped because injection timestamps fell outside the available metric windows. These are saved results, not a claim that a new machine has reproduced the run.

### Additional OpenRCA results

- Bank summary: `results/bank_canonical_v1_summary.json`
- Bank per-incident results: `results/bank_canonical_v1_per_incident.csv`
- Telecom primary v2 summary: `results/telecom_canonical_v2_summary.json`
- Telecom primary v2 per-incident results: `results/telecom_canonical_v2_per_incident.csv`
- Telecom sensitivity analyses: `results/telecom_sensitivity_5_summary.json` and `results/telecom_sensitivity_30_summary.json`
- Paired statistical report: `results/paired_analysis_full2.md`

The recorded Bank run evaluated 135 incidents, with one incident having no scored components. Its strict Hit@1 was 0.17037, tie-aware Hit@1 was 0.28148, and tie-aware MRR was 0.37242.

The recorded Telecom primary v2 run evaluated 47 incidents; three had no scored components and one had unscoreable ground truth. Its strict Hit@1 was 0.04255, tie-aware Hit@1 was 0.06383, and MRR was 0.14807.

OpenRCA and RCAEval results should be interpreted separately. Their telemetry, coverage, scoreability, and dataset-specific assumptions differ. Read the corresponding summaries and limitations before drawing cross-dataset conclusions.

## 9. Repository layout

```text
apex-rca/
├── apex_rca/       # Core scoring, graph, telemetry, and ranking modules
├── data/           # Local datasets; ignored by Git
├── docs/           # Methodology, architecture, limitations, and handover
├── experiments/    # Dataset preparation and experiment scripts
├── results/        # Saved results, reports, and small generated cache
├── tests/          # Unit tests
├── app.py          # Streamlit research dashboard
├── requirements.txt
└── README.md
```

## 10. Collaboration workflow

Keep `main` as the stable branch and develop on separate branches. Check the current branch and working tree before editing:

```powershell
git branch --show-current
git status
```

Stage only files intended for the commit, then inspect the staged diff:

```powershell
git add <intended-files>
git diff --cached --check
git diff --cached --stat
```

Commit and push to your working branch:

```powershell
git commit -m "Describe the change"
git push -u origin <your-branch>
```

Review changes before merging into `main`. Never commit `.venv`, datasets, secrets, raw archives, or temporary backups. The repository's `.gitignore` excludes local `data/`; verify `git status` before committing.

## 11. Troubleshooting

- **Dataset missing:** Follow Section 4 and verify the expected local folder structure.
- **Preparation script seems stuck:** Row counting and CSV parsing can be slow on large files. Check whether it is actively running before interrupting it. After interruption, validate the output rather than assuming the preparation completed.
- **Missing Python package:** Use the project interpreter to install `requirements.txt`.
- **Tests fail:** Review the traceback and Python version before changing dependencies.
- **Dashboard opens without results:** Check the result paths used by `app.py` and verify the expected result files exist.
- **Experiment overwrites an output:** Stop and inspect the script's output paths. Back up important files and use a new tag or output name where supported.
- **Collaborator cannot clone:** Confirm repository access has been granted and accepted.

## 12. Research documentation

- `docs/methodology.md` — research methodology
- `docs/architecture.md` — system architecture
- `docs/experiment_protocol.md` — experiment procedure
- `docs/limitations.md` — known limitations
- `docs/openrca_protocol.md` — OpenRCA evaluation protocol
- `docs/HANDOFF.md` — project handover and remaining work
- `docs/related_work_to_verify.md` — related-work claims requiring verification

Retain dataset citations and licensing information when using or redistributing benchmark data. Consult the original dataset documentation for citation requirements and redistribution restrictions.
