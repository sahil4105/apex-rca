from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_app_overview_and_incident_explorer_render_without_exception():
    """Verify that both Overview and Incident Explorer render cleanly without NameError or KeyError."""
    app_path = ROOT / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=30)
    at.run()

    # Verify Research Overview renders with zero exceptions
    assert len(at.exception) == 0, f"Overview raised exception: {at.exception}"

    # Navigate to Incident Explorer
    at.sidebar.radio[0].set_value("Incident explorer").run()

    # Verify Incident Explorer and LLM Diagnosis widgets render with zero exceptions
    assert len(at.exception) == 0, f"Incident explorer raised exception: {at.exception}"

    # Verify key widgets are present
    selectboxes = [sb.label for sb in at.selectbox]
    assert "Incident case" in selectboxes
    assert "Evidence Grounding Mode" in selectboxes
    assert "Candidate Set" in selectboxes

