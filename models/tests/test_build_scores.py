"""`build_scores` output validates against the topic_scores_weekly contract."""

import polars as pl
import pytest

from models import build_scores
from radar.contracts import validate_records


@pytest.fixture(scope="module")
def records() -> list[dict]:
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_PROFILE", "dev")
    try:
        return build_scores.build()
    finally:
        mp.undo()


def test_every_record_matches_the_contract(records):
    assert records
    assert validate_records("topic_scores_weekly", records) == []


def test_one_row_per_unit_and_scored_week(records):
    df = build_scores.to_frame(records)
    # 8-week slice minus the 5 warm-up weeks: W40, W41, W42; 11 subtopics each
    assert sorted(df["week"].unique()) == ["2026-W40", "2026-W41", "2026-W42"]
    assert df.group_by("week").len()["len"].to_list() == [11, 11, 11]
    assert df.select(pl.struct("week", "topic_id").is_unique().all()).item()


def test_profile_and_labels(records):
    assert {r["profile"] for r in records} == {"dev"}
    assert {r["label_es"] for r in records if r["topic_id"] == "education"} == {"Educación"}
    assert all(1 <= len(r["why"]) <= 5 for r in records)


def test_main_writes_a_parquet_that_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")
    out = tmp_path / "topic_scores_weekly.parquet"
    assert build_scores.main(["--out", str(out)]) == 0
    back = pl.read_parquet(out).to_dicts()
    assert validate_records("topic_scores_weekly", back) == []
