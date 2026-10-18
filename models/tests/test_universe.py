"""The ranked universe and the primary subtopic.

The universe rules are tested on the real entity ids of the dev slice's `edges_weekly`; the
membership and the topic build need the lake (`data` marker: they skip when it is absent).
"""

import os

import polars as pl
import pytest

from models import scores, universe
from radar.paths import REPO_ROOT, lake

DEV = REPO_ROOT / "fixtures" / "dev"


@pytest.fixture(scope="module")
def dev_ids() -> list[str]:
    e = pl.read_parquet(DEV / "edges_weekly.parquet")
    return pl.concat([e["x"], e["y"]]).unique().sort().to_list()


def test_universe_reads_the_taxonomy(dev_ids):
    ok = pl.DataFrame({"topic_id": dev_ids}).filter(universe.in_universe())["topic_id"].to_list()
    deny = {f"org:{d}" for d in universe.RULES["org_deny"]}
    assert ok
    assert all(t.startswith(("org:", "thm:TECH_")) for t in ok)
    assert not deny & set(ok)
    # every org of the slice outside the deny list is in
    orgs = {t for t in dev_ids if t.startswith("org:")} - deny
    assert orgs <= set(ok)
    assert "org:cnn" in dev_ids and "org:cnn" not in ok  # a denied outlet that is in the slice
    assert not any(t.startswith(("per:", "loc:")) for t in ok)


def test_min_articles_comes_from_the_taxonomy():
    assert scores.MIN_ARTICLES_7D == universe.MIN_ARTICLES_WEEK == 20


needs_lake = pytest.mark.skipif(
    not (lake() / "gold" / "topic_subtopic_weekly.parquet").exists()
    or not (lake() / "gold" / "topic_daily.parquet").exists(),
    reason="needs the full lake",
)


@pytest.fixture
def full(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "full")


@pytest.mark.data
@needs_lake
def test_primary_subtopic_recounts_by_hand(full):
    mem = universe.membership(scores.FIT_SUBTOPICS)
    m = pl.read_parquet(lake() / "gold" / "topic_subtopic_weekly.parquet")
    row = mem.filter(pl.col("week") == "2026-W41", pl.col("unit_id") == "org:nvidia").row(
        0, named=True
    )
    # weeks t-3..t: the Mondays 2026-09-14 .. 2026-10-05
    win = m.filter(
        pl.col("topic_id") == "org:nvidia",
        pl.col("week").is_between(pl.date(2026, 9, 14), pl.date(2026, 10, 5)),
        pl.col("subtopic").is_not_null(),
    )
    counts = win.group_by("subtopic").agg(pl.col("n_articles").sum())
    top = counts["n_articles"].max()
    tied = set(counts.filter(pl.col("n_articles") == top)["subtopic"])
    expected = min(tied, key=universe.SUBTOPIC_ORDER.index)
    assert row["primary_subtopic"] == expected
    assert 0 <= row["fit_subtopic"] <= 1


@pytest.mark.data
@needs_lake
def test_topic_build_validates_and_ranks_the_universe(full):
    from models import build_scores
    from radar.contracts import validate_records

    records = build_scores.build("topic")
    assert validate_records("topic_scores_weekly", records) == []
    df = build_scores.to_frame(records)
    assert df["rank"].null_count() == 0
    assert df.filter(~universe.in_universe("topic_id")).is_empty()
    # the calendar starts with topic_daily (2025-11-01) + 5 warm-up weeks, never before
    assert df["week"].min() >= "2025-W49"
    per_week = df.group_by("week").len()["len"]
    assert per_week.min() > 10
    assert os.environ["RADAR_PROFILE"] == "full"


@pytest.mark.data
@pytest.mark.skipif(
    not (lake() / "gold" / "topic_sources_weekly.parquet").exists(), reason="needs the full lake"
)
def test_syndication_guard_holds_single_pattern_weeks(full):
    """Addendum 5: org:euronext in 2026-W42 (145 of 149 articles share one pattern) is held."""
    from models import build_scores

    s = pl.read_parquet(lake() / "gold" / "topic_scores_weekly.parquet")
    w = s.filter(pl.col("week") == "2026-W42")
    src = build_scores.sources().filter(pl.col("week") == "2026-W42")
    top = w.filter(pl.col("rank") <= 10).join(
        src.rename({"unit_id": "topic_id"}), on=["topic_id", "week"], how="left"
    )
    assert (top["n_sources"].fill_null(5) >= build_scores.MIN_SOURCES).all()
    assert (top["top_source_share"].fill_null(0) <= build_scores.MAX_TOP_SOURCE_SHARE).all()
    assert (top["top_theme_pattern_share"].fill_null(0) < build_scores.MAX_PATTERN_SHARE).all()
    eur = w.filter(pl.col("topic_id") == "org:euronext")
    assert eur["rank"].item() > 10
    assert any("patrón" in b for b in eur["why"].item())
