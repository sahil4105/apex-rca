# APEX-RCA

**A Topology-Grounded Root Cause Analysis Pipeline for Microservices Using Dependency Graphs and Telemetry Data**

APEX-RCA investigates whether service dependency information improves telemetry-based root-cause identification compared with anomaly-only ranking, and whether logs and traces provide additional value.

The project includes a Python ranking pipeline, RCAEval experiments, statistical evaluation, unit tests and a local Streamlit dashboard.

## 1. Project status and scope

- **Primary benchmark:** RCAEval, covering 735 failure cases across three benchmark suites.
- **Task:** Retrospective root-cause diagnosis using the recorded fault-injection timestamp.
- **Main comparison:** Anomaly-only ranking versus dependency-graph-aware ranking.
- **Additional comparison:** The contribution of logs and traces.
- **Dashboard:** A local interface for inspecting saved results and incident evidence.

The repository includes baseline code and previously generated results. Re-running experiments may overwrite existing output files, so preserve important results before running new configurations.

## 2. Prerequisites

For Windows:

- Git
- Python 3.13
- PyCharm or another Python IDE (optional)
- Internet access to download datasets
- Several GB of free disk space for RCAEval; additional space is needed for extracted files and generated outputs

Open PowerShell in the directory where you want to keep the project.

## 3. Clone and install

Clone the repository:

```powershell
git clone https://github.com/sahil4105/apex-rca.git
cd apex-rca
```

Create and activate a virtual environment:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell cannot activate the virtual environment, you can run the project interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Obtain the datasets

Datasets are **not stored in this Git repository**. Each collaborator must download the required data separately.

### 4.1 RCAEval — required for the main experiments

Official sources:

- Hugging Face: https://huggingface.co/datasets/phamquiluan/RCAEval
- Official code and documentation: https://github.com/phamquiluan/RCAEval

RCAEval contains 735 failure cases across the RE1, RE2 and RE3 suites. The Hugging Face version uses Parquet files and is approximately 3.4 GB.

From the project root, run the project's dataset preparation script:

```powershell
.\.venv\Scripts\python.exe experiments\prepare_dataset.py
```

The project expects the prepared dataset under:

```text
data/
└── rcaeval/
```

The script is the first option to try because it belongs to this project's preparation workflow. Consult the script and its output if the download fails or the resulting directory differs from the expected layout.

**Manual download fallback:** The official Hugging Face dataset documents downloading with `huggingface_hub`. To download the full dataset directly into the expected directory:

```powershell
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='phamquiluan/RCAEval', repo_type='dataset', local_dir='data/rcaeval')"
```

This downloads the repository's dataset files, including its case index. It does not guarantee that the resulting layout matches every assumption in the APEX-RCA preparation code, so verify the directory structure before running experiments.

For a fresh installation, do not assume the existing local dataset is present just because the code and result files are available on GitHub.

### 4.2 OpenRCA — optional additional validation

Official repository:

https://github.com/microsoft/OpenRCA

OpenRCA provides additional telemetry data for systems including Bank, Telecom and Market. The official repository explains how to obtain the telemetry archives through its linked Google Drive resources.

Follow the official repository's dataset instructions and place the downloaded files in the structure expected by OpenRCA. A typical layout contains:

```text
dataset/
├── Bank/
│   ├── query.csv
│   ├── record.csv
│   └── telemetry/
├── Telecom/
│   ├── query.csv
│   ├── record.csv
│   └── telemetry/
└── Market/
```

**OpenRCA is optional.** The primary RCAEval experiments do not require it. Download it only when working on the additional validation workflow, and confirm query-to-record alignment before interpreting results.

Do not upload dataset archives, extracted telemetry, or private data to this repository.

## 5. Verify the installation

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Import-check the dashboard:

```powershell
.\.venv\Scripts\python.exe -c "import app; print('app import: OK')"
```

These checks verify the unit tests and basic application import. They do not replace a full experiment run or manual dashboard testing.

## 6. Run the dashboard

Start Streamlit:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed in the terminal.

The dashboard displays saved experiment results and incident information. It is a research inspection tool, not a production monitoring system. Missing telemetry should not be interpreted as evidence that a service is healthy.

## 7. Run experiments

Run commands from the repository root.

### Original anomaly-only baseline

This command may overwrite the original baseline CSV, so preserve the existing artifact first if you need to retain it.

```powershell
.\.venv\Scripts\python.exe experiments\baseline_rcaeval.py --limit 0
```

### Run packaged methods

A small smoke run is preferable before a full experiment:

```powershell
.\.venv\Scripts\python.exe experiments\run_rcaeval.py --method anomaly_only --tag smoke --limit 20
```

Run all supported methods on the full dataset:

```powershell
.\.venv\Scripts\python.exe experiments\run_rcaeval.py --method all --tag full2 --limit 0
```

Use a new tag for a new run whenever the script supports it. Check the script's arguments before choosing a tag or changing its configuration.

### Analysis and report scripts

```powershell
.\.venv\Scripts\python.exe experiments\analyze_re3.py
.\.venv\Scripts\python.exe experiments\compare_results.py
.\.venv\Scripts\python.exe experiments\analyze_graph_controls.py
.\.venv\Scripts\python.exe experiments\write_results_md.py
```

These scripts have different purposes: some analyze saved results, while others generate or update reports. Read their output paths before running them, because existing files may be overwritten.

The evaluated task uses the reference window `[time_start, inject_time)` and the observation window `[inject_time, time_end)`. The injection timestamp is treated as known.

## 8. Results and evaluation

The repository includes previously generated experiment artifacts under `results/`.

Metrics include:

- **Hit@1:** Whether the correct root-cause service ranks first.
- **Hit@3 and Hit@5:** Whether the correct service appears within the top three or five.
- **MRR:** Mean reciprocal rank of the correct service.
- **Paired statistical comparisons:** Tests and confidence intervals comparing methods on the same cases.

Always report the number of evaluated and skipped cases alongside the metrics. Results should be interpreted with the limitations documented in `docs/limitations.md` and `docs/experiment_protocol.md`.

Do not assume that the existing results were reproduced on your machine simply because they are committed to GitHub.

## 9. Repository layout

```text
apex-rca/
├── apex_rca/       # Core ranking and telemetry modules
├── data/           # Local datasets; not committed
├── docs/           # Methodology, architecture and handoff notes
├── experiments/    # Dataset preparation and experiment scripts
├── results/        # Saved experiment artifacts and reports
├── tests/          # Unit tests
├── app.py          # Streamlit dashboard
├── requirements.txt
└── README.md
```

## 10. Collaboration workflow

The repository is shared by the project collaborators. Keep the `main` branch as the stable baseline and do development on separate branches.

Current branch plan:

- `main` — published baseline
- `sahil` — Sahil's development branch
- `friend-work` — collaborator's development branch

Check your branch before editing:

```powershell
git branch --show-current
git status
```

Create a branch if you do not already have one:

```powershell
git switch -c your-branch-name
```

Save and push your changes:

```powershell
git add README.md
git commit -m "Update project documentation"
git push
```

Replace `README.md` with the files you actually intend to commit when adding code. Review `git status` before staging changes, and never commit `.venv`, datasets, secrets or large local archives.

When a task is complete, review the changes and merge them into `main` through a pull request or an explicitly reviewed merge. Do not develop directly on `main`.

## 11. Troubleshooting

- **Dataset missing:** Run the preparation script in Section 4 and verify the expected directory.
- **Missing Python package:** Activate `.venv` and run `pip install -r requirements.txt`.
- **Tests fail:** Check the error output and Python version before changing dependencies.
- **Dashboard opens but results are missing:** Verify the saved result files and the paths used by `app.py`.
- **Experiment overwrites an output:** Stop and inspect the script's output paths; use a new tag or back up the existing artifact before rerunning.
- **Collaborator cannot clone:** Confirm the invitation to the private GitHub repository has been accepted.

## 12. Research documentation

- `docs/methodology.md` — research methodology
- `docs/architecture.md` — system architecture
- `docs/experiment_protocol.md` — experiment procedure
- `docs/limitations.md` — known limitations
- `docs/HANDOFF.md` — project handoff and remaining work

Dataset citations and licensing information should be retained when using or redistributing benchmark data. Consult the original dataset documentation for citation details.
