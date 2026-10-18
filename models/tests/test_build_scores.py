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
        return build_scores.build("subtopic")
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def topics() -> pl.DataFrame:
    """The topic build on the dev cut of topic_daily and topic_subtopic_weekly (real data)."""
    mp = pytest.MonkeyPatch()
    mp.setenv("RADAR_PROFILE", "dev")
    try:
        recs = build_scores.build("topic")
    finally:
        mp.undo()
    assert validate_records("topic_scores_weekly", recs) == []
    return build_scores.to_frame(recs)


def test_topic_rows_rank_gated_topics_first(topics):
    for (_week,), w in topics.group_by("week"):
        w = w.sort("rank")
        assert w["rank"].to_list() == list(range(1, w.height + 1))
        seed = w["why"].list.eval(pl.element().str.starts_with("Semilla a vigilar")).list.any()
        # every gated (headline) topic ranks above every seed
        first_seed = seed.arg_true().min()
        if first_seed is not None:
            assert seed[first_seed:].all()
            assert (w["stage"][first_seed:] == "semilla").all()


def test_decisions_follow_the_rank(topics):
    """Addendum 3: no publicar_ahora below a no_es_tema_caliente without a stated reason."""
    for (_week,), w in topics.group_by("week"):
        pub = w.filter(pl.col("decision") == "publicar_ahora")
        no = w.filter(pl.col("decision") == "no_es_tema_caliente")
        if pub.is_empty() or no.is_empty():
            continue
        above = no.filter(pl.col("priority") > pub["priority"].min())
        # the stated reason is decision rule 1 (declining or low emergence), in the why
        assert above["why"].list.first().str.contains("regla 1").all()
        assert (above["stage"] == "en_declive").all()
        # and every publicar_ahora is in the top decile of the week's priority
        assert pub["why"].list.first().str.contains("regla 3").all()


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
    assert build_scores.main(["--unit", "subtopic", "--out", str(out)]) == 0
    back = pl.read_parquet(out).to_dicts()
    assert validate_records("topic_scores_weekly", back) == []
