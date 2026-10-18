import os

import pytest

# Set before the agents package loads .env, so tests never send anything to LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    """Tests keep traces out of the shared lake."""
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
