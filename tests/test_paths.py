import pytest

from radar import paths


@pytest.mark.unit
def test_lake_defaults_to_repo(monkeypatch):
    monkeypatch.delenv("RADAR_LAKE", raising=False)
    assert paths.lake() == paths.REPO_ROOT / "lake"


@pytest.mark.unit
def test_lake_follows_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    assert paths.gold("daily_topic") == tmp_path / "gold" / "daily_topic.parquet"
