from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.telecom_adapter import deduplicate_exact_source_rows


def test_exact_duplicate_rows_are_removed():
    import pandas as pd

    source = pd.DataFrame({
        "timestamp": [1000, 1000, 1000],
        "cmdb_id": ["docker_1", "docker_1", "docker_1"],
        "name": ["container_cpu_used"] * 3,
        "itemid": ["cpu_1"] * 3,
        "value": [59.0, 59.0, 2.0],
    })

    result = deduplicate_exact_source_rows(source)

    assert len(result) == 2
    assert sorted(result["value"].tolist()) == [2.0, 59.0]


def test_conflicting_values_are_not_aggregated_or_discarded():
    import pandas as pd

    source = pd.DataFrame({
        "timestamp": [1000, 1000],
        "cmdb_id": ["docker_1", "docker_1"],
        "name": ["container_cpu_used"] * 2,
        "itemid": ["cpu_1"] * 2,
        "value": [59.0, 2.0],
    })

    result = deduplicate_exact_source_rows(source)

    assert len(result) == 2
    assert set(result["value"]) == {2.0, 59.0}
from apex_rca.telecom_adapter import load_telecom_incident


def test_telecom_incident_excludes_conflicting_canonical_observations():
    data_dir = ROOT / "data" / "openrca" / "processed" / "Telecom"

    incident, _ = load_telecom_incident(data_dir, 19)

    keys = ["timestamp", "service", "metric"]

    assert incident.metadata["conflicting_canonical_keys_excluded"] >= 1
    assert incident.metadata["conflicting_observations_excluded"] >= 2
    assert not incident.metrics.duplicated(keys, keep=False).any()
    assert incident.validate() == []
