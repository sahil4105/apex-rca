# Existing APEX-RCA Experiment Comparison

Generated from existing summary JSON and configuration artifacts.
This report does not rerun experiments or modify their CSV outputs.

| Tag | Indexed | Method | Evaluated | Skipped | Hit@1 | MRR |
|---|---:|---|---:|---:|---:|---:|
| audit1 | 20 | anomaly_only | 20 | 0 | 0.9000 | 0.9417 |
| audit1 | 20 | metrics_graph | 20 | 0 | 0.9000 | 0.9417 |
| audit1 | 20 | metrics_logs_traces | 20 | 0 | 0.9000 | 0.9417 |
| audit1 | 20 | full | 20 | 0 | 0.9000 | 0.9417 |

**audit1 configuration:** graph mode `auto`, graph weight `0.3`, extra weight `0.25`, seed `42`, graph time scope `None`.

| full2 | 735 | anomaly_only | 733 | 2 | 0.7572 | 0.8447 |
| full2 | 735 | metrics_graph | 733 | 2 | 0.7967 | 0.8657 |
| full2 | 735 | metrics_logs_traces | 733 | 2 | 0.7613 | 0.8471 |
| full2 | 735 | full | 733 | 2 | 0.8008 | 0.8695 |

**full2 configuration:** graph mode `auto`, graph weight `0.3`, extra weight `0.25`, seed `42`, graph time scope `None`.

| re1_gw010 | 375 | metrics_graph | 373 | 2 | 0.7855 | 0.8761 |

**re1_gw010 configuration:** graph mode `auto`, graph weight `0.1`, extra weight `0.25`, seed `42`, graph time scope `None`.

| re1_gw020 | 375 | metrics_graph | 373 | 2 | 0.7989 | 0.8838 |

**re1_gw020 configuration:** graph mode `auto`, graph weight `0.2`, extra weight `0.25`, seed `42`, graph time scope `None`.

| re1_gw030 | 375 | metrics_graph | 373 | 2 | 0.8097 | 0.8881 |

**re1_gw030 configuration:** graph mode `auto`, graph weight `0.3`, extra weight `0.25`, seed `42`, graph time scope `None`.

| re2_gw020 | 270 | metrics_graph | 270 | 0 | 0.9111 | 0.9413 |

**re2_gw020 configuration:** graph mode `auto`, graph weight `0.2`, extra weight `0.25`, seed `42`, graph time scope `None`.

| re3_gw020 | 90 | metrics_graph | 90 | 0 | 0.4111 | 0.5527 |

**re3_gw020 configuration:** graph mode `auto`, graph weight `0.2`, extra weight `0.25`, seed `42`, graph time scope `None`.

| v1 | 735 | anomaly_only | 733 | 2 | 0.7572 | 0.8447 |

**v1 configuration:** graph mode `auto`, graph weight `0.3`, extra weight `0.25`, seed `42`, graph time scope `None`.

