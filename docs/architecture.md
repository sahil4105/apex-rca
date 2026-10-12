# Architecture

```
RCAEval case directory
        │
        ▼
apex_rca.data_loader   → metrics, optional logs/traces
        │
        ├─ metric_parsing / preprocessing / anomaly_scoring
        ├─ logs_traces (optional)
        ├─ dependency_graph (traces and/or canonical)
        ├─ ranking
        └─ evidence
                │
                ▼
        experiments/run_rcaeval.py   evaluation CSVs / JSON
        app.py                       Streamlit demo
```

| Module | Responsibility |
|---|---|
| `metric_parsing.py` | Service names from metric columns; trace/log aliases |
| `preprocessing.py` | Inject-time windows; timestamp unit coercion |
| `anomaly_scoring.py` | Robust metric effect sizes and service aggregation |
| `dependency_graph.py` | Parent-child graphs, canonical fallback, PageRank |
| `topologies.py` | Documented Online Boutique and Sock Shop edges |
| `logs_traces.py` | Windowed log-error and trace duration/status scores |
| `ranking.py` | Score fusion and deterministic ranking |
| `evaluation.py` | Hit@k, MRR, bootstrap CI, McNemar |
| `pipeline.py` | Single-case orchestration for all methods |
| `evidence.py` | Explanations from computed scores only |

The PyCharm template `main.py` is unused.
