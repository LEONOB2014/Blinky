"""Checks on the exported lake (RADAR_PROFILE=full pytest -m data); skip when a table is absent."""

import export_gold
import polars as pl
import pytest
import yaml

from radar import paths
from radar.contracts import load_schema, validate_records

pytestmark = pytest.mark.data
TABLES = list(export_gold.TABLES)


def _gold(name: str) -> pl.LazyFrame:
    if paths.profile() != "full":
        pytest.skip("data tests read the full lake: set RADAR_PROFILE=full")
    path = paths.gold(name)
    if not path.exists():
        pytest.skip(f"{path} not exported")
    return pl.scan_parquet(path)


@pytest.mark.parametrize("name", TABLES)
def test_columns_and_a_sample_match_the_contract(name):
    lf = _gold(name)
    schema = load_schema(name)
    cols = lf.collect_schema().names()
    assert set(cols) <= set(schema["properties"])
    assert set(schema["required"]) <= set(cols)
    frame = lf.collect()
    assert frame.height > 0
    sample = export_gold.sample_for_validation(frame, 1000, seed=11)
    assert validate_records(name, export_gold.records_for_validation(sample)) == []


@pytest.mark.parametrize("name", TABLES)
def test_required_columns_have_no_nulls_unless_nullable(name):
    lf = _gold(name)
    props = load_schema(name)["properties"]
    required = load_schema(name)["required"]
    strict = [c for c in required if "null" not in str(props[c].get("type", ""))]
    nulls = lf.select(pl.col(strict).null_count()).collect().row(0, named=True)
    assert {c: n for c, n in nulls.items() if n} == {}


def test_missing_days_are_null_in_rolling():
    lf = _gold("daily_topic_rolling")
    bad = lf.filter(
        pl.col("is_missing")
        & pl.any_horizontal(pl.col(c).is_not_null() for c in ("n", "n_all", "share", "n_sources"))
    )
    assert bad.select(pl.len()).collect().item() == 0
    # ... and present days are counted, zero when there was no article (never NULL).
    present = lf.filter(~pl.col("is_missing") & pl.col("n").is_null())
    assert present.select(pl.len()).collect().item() == 0


def test_rolling_is_one_row_per_key_and_day():
    lf = _gold("daily_topic_rolling")
    keys = ["topic", "segment", "lang_bucket", "latam", "dt"]
    dup = lf.group_by(keys).len().filter(pl.col("len") > 1)
    assert dup.select(pl.len()).collect().item() == 0


def test_daily_topic_domain_only_in_ring_three():
    lf = _gold("daily_topic")
    wrong = lf.filter((pl.col("segment") == "ai_domain") != pl.col("domain").is_not_null())
    assert wrong.select(pl.len()).collect().item() == 0
    seg = lf.select(pl.col("segment").unique()).collect()["segment"].to_list()
    assert set(seg) == {"ai", "it", "ai_domain"}


def test_subtopics_only_in_ring_one():
    lf = _gold("daily_topic")
    other = lf.filter(pl.col("segment") != "ai").select(pl.col("topic").unique()).collect()
    assert all(t == "it_all" or t.startswith("domain:") for t in other["topic"].to_list())


def test_topic_daily_ranks_orgs_and_themes_never_persons():
    lf = _gold("topic_daily")
    prefixes = lf.select(pl.col("topic_id").str.extract(r"^([a-z]+):").unique()).collect()
    assert set(prefixes["topic_id"].to_list()) <= {"org", "thm"}
    assert lf.filter(pl.col("segment") != "ai").select(pl.len()).collect().item() == 0
    missing = lf.filter(pl.col("is_missing") & pl.col("share_of_day").is_not_null())
    assert missing.select(pl.len()).collect().item() == 0


def test_edges_meet_the_contract_floor():
    lf = _gold("edges_weekly")
    stats = lf.select(
        pl.col("n").min().alias("n_min"),
        pl.col("npmi").min().alias("npmi_min"),
        pl.col("npmi").max().alias("npmi_max"),
        (pl.col("x") >= pl.col("y")).sum().alias("unordered"),
    ).collect()
    row = stats.row(0, named=True)
    assert row["n_min"] >= 3
    assert row["unordered"] == 0
    assert row["npmi_min"] >= -1.0 - 1e-9 and row["npmi_max"] <= 1.0 + 1e-9


def test_lake_spans_the_backfill():
    lf = _gold("daily_topic")
    span = lf.select(pl.col("dt").min().alias("lo"), pl.col("dt").max().alias("hi")).collect()
    lo, hi = span.row(0)
    assert (hi - lo).days >= 180  # at least 6 months of history for the backtest


def test_topic_subtopic_weekly_is_consistent():
    lf = _gold("topic_subtopic_weekly")
    bad = lf.filter(pl.col("n_articles") > pl.col("n_topic_articles"))
    assert bad.select(pl.len()).collect().item() == 0
    dup = lf.group_by(["topic_id", "week", "subtopic"]).len().filter(pl.col("len") > 1)
    assert dup.select(pl.len()).collect().item() == 0
    # One denominator per topic and week, whatever the subtopic.
    denoms = lf.group_by(["topic_id", "week"]).agg(pl.col("n_topic_articles").n_unique().alias("k"))
    assert denoms.filter(pl.col("k") > 1).select(pl.len()).collect().item() == 0
    # Weeks are Mondays (the edges_weekly key) and topics are topic_daily ids.
    assert lf.filter(pl.col("week").dt.weekday() != 1).select(pl.len()).collect().item() == 0
    subs = lf.select(pl.col("subtopic").drop_nulls().unique()).collect()["subtopic"].to_list()
    taxonomy = yaml.safe_load((paths.REPO_ROOT / "contracts" / "taxonomy.yaml").read_text())
    assert set(subs) <= set(taxonomy["subtopics"])
    topics = _gold("topic_daily").select(pl.col("topic_id").unique())
    orphans = lf.select(pl.col("topic_id").unique()).join(topics, on="topic_id", how="anti")
    assert orphans.select(pl.len()).collect().item() == 0
