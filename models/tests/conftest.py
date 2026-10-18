import pytest


@pytest.fixture(autouse=True)
def _dev_profile(monkeypatch):
    """Every WS4 unit test reads the committed dev slice, whatever the shell exports."""
    monkeypatch.setenv("RADAR_PROFILE", "dev")
