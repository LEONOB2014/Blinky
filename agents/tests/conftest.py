import pytest


@pytest.fixture(autouse=True)
def _traces_in_tmp(tmp_path, monkeypatch):
    """run_turn writes a trace per turn; tests keep them out of the shared lake."""
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
