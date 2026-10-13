from pathlib import Path
import sys
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.telecom_adapter import (
    deduplicate_exact_source_rows,
    load_telecom_incident,
)


def test_exact_duplicate_rows_are_removed():
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


def test_telecom_incident_excludes_conflicting_canonical_observations_fixture(tmp_path: Path):
    """Dataset-independent unit test verifying conflicting observation exclusion logic.

    Uses a temporary directory structure mimicking the OpenRCA Telecom telemetry layout,
    injecting one unambiguous metric and two conflicting values for the same canonical
    key (timestamp, service, metric) to confirm they are excluded rather than aggregated.
    """
    record_df = pd.DataFrame([{
        "component": "docker_001",
        "timestamp": 1616241600.0,
        "datetime": "2021-03-20 12:00:00",
        "reason": "Network latency",
        "level": "pod",
    }])
    record_df.to_csv(tmp_path / "record.csv", index=False)

    metric_dir = tmp_path / "telemetry" / "2021_03_20" / "metric"
    metric_dir.mkdir(parents=True)

    # 1 unambiguous row (value=10.0), plus 2 conflicting rows at 1616241605000 (value=25.0 and 85.0),
    # plus 1 exact duplicate row (value=85.0) to test deduplication concurrently
    metric_df = pd.DataFrame([
        {
            "timestamp": 1616241600000,
            "value": 10.0,
            "cmdb_id": "docker_001",
            "name": "container_cpu",
            "itemid": "item_1",
        },
        {
            "timestamp": 1616241605000,
            "value": 25.0,
            "cmdb_id": "docker_001",
            "name": "container_cpu",
            "itemid": "item_1",
        },
        {
            "timestamp": 1616241605000,
            "value": 85.0,
            "cmdb_id": "docker_001",
            "name": "container_cpu",
            "itemid": "item_1",
        },
        {
            "timestamp": 1616241605000,
            "value": 85.0,
            "cmdb_id": "docker_001",
            "name": "container_cpu",
            "itemid": "item_1",
        },
    ])
    metric_df.to_csv(metric_dir / "metric_container.csv", index=False)

    incident, truth = load_telecom_incident(
        tmp_path,
        incident_index=0,
        reference_seconds=10.0,
        observed_seconds=10.0,
    )

    keys = ["timestamp", "service", "metric"]

    assert incident.metadata["conflicting_canonical_keys_excluded"] >= 1
    assert incident.metadata["conflicting_observations_excluded"] >= 2
    assert not incident.metrics.duplicated(keys, keep=False).any()
    assert incident.validate() == []
    assert truth["component"] == "docker_001"


REAL_TELECOM_DATA_DIR = ROOT / "data" / "openrca" / "processed" / "Telecom"


@pytest.mark.skipif(
    not (REAL_TELECOM_DATA_DIR / "record.csv").is_file(),
    reason="Requires optional OpenRCA Telecom dataset under data/openrca/processed/Telecom/",
)
def test_telecom_incident_excludes_conflicting_canonical_observations_real_dataset():
    """Integration test against local OpenRCA Telecom dataset when installed."""
    incident, _ = load_telecom_incident(REAL_TELECOM_DATA_DIR, 19)

    keys = ["timestamp", "service", "metric"]

    assert incident.metadata["conflicting_canonical_keys_excluded"] >= 1
    assert incident.metadata["conflicting_observations_excluded"] >= 2
    assert not incident.metrics.duplicated(keys, keep=False).any()
    assert incident.validate() == []
