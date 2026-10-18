import pytest

from radar import paths


@pytest.mark.unit
def test_lake_defaults_to_repo(monkeypatch):
    monkeypatch.delenv("RADAR_LAKE", raising=False)
    assert paths.lake() == paths.REPO_ROOT / "lake"


@pytest.mark.unit
def test_full_profile_reads_the_lake(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_PROFILE", "full")
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    assert paths.gold("daily_topic") == tmp_path / "gold" / "daily_topic.parquet"


@pytest.mark.unit
def test_dev_profile_is_the_default_and_reads_fixtures(monkeypatch):
    monkeypatch.delenv("RADAR_PROFILE", raising=False)
    assert paths.gold("daily_topic") == paths.REPO_ROOT / "fixtures" / "dev" / "daily_topic.parquet"


@pytest.mark.unit
def test_unknown_profile_is_refused(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "prod")
    with pytest.raises(ValueError, match="RADAR_PROFILE"):
        paths.profile()
