"""The Python port of the S8 rolling view reproduces the real view on the dev slice."""

import datetime as dt

import polars as pl
import pytest

from models import features
from radar.paths import REPO_ROOT

DEV = REPO_ROOT / "fixtures" / "dev"
# The slice starts 2026-08-24; the port needs 41 days of history (34 back + the 7-day window)
# before z_7d is comparable, so the comparison starts on 2026-10-04.
FROM = dt.date(2026, 10, 4)
COLS = (
    "n", "share", "n_sources", "n_7d", "share_7d", "z_dow", "z_7d", "growth_7d_log", "accel_7d",
    "mean_tone_7d", "extremity_7d", "mean_polarity_7d", "positive_share_7d", "negative_share_7d",
    "controversy_7d", "tone_shift_7d",
)  # fmt: skip


@pytest.fixture(scope="module")
def joined() -> pl.DataFrame:
    key = (pl.col("topic") + "|" + pl.col("latam").cast(pl.String)).alias("k")
    daily = pl.read_parquet(DEV / "daily_topic.parquet").with_columns(key)
    daily = daily.rename({"n_articles": "n"})
    per_stream = {b: (b,) for b in ("eng", "spa", "por", "other")}
    port = features.rolling(daily, features.load_totals(), groups=per_stream, key="k")
    s8 = pl.read_parquet(DEV / "daily_topic_rolling.parquet").with_columns(key)
    s8 = s8.rename({"lang_bucket": "group"})
    return port.join(s8, on=["k", "group", "dt"], suffix="_s8").filter(pl.col("dt") >= FROM)


def test_port_covers_every_view_row(joined):
    # 12 series x 2 LatAm flags x 4 streams x 14 days
    assert joined.height == 12 * 2 * 4 * 14


@pytest.mark.parametrize("col", COLS)
def test_port_matches_the_view(joined, col):
    diff = joined.select(
        (pl.col(col) - pl.col(f"{col}_s8")).abs().max().alias("max_abs"),
        (pl.col(col).is_null() != pl.col(f"{col}_s8").is_null()).sum().alias("null_mismatch"),
    ).row(0, named=True)
    assert diff["null_mismatch"] == 0
    assert (diff["max_abs"] or 0.0) < 1e-9


def test_language_groups_sum_their_streams():
    roll = features.rolling(features.subtopic_daily(), features.load_totals())
    day = roll.filter(pl.col("unit_id") == "ai_all", pl.col("dt") == dt.date(2026, 10, 17))
    n = dict(zip(day["group"], day["n"], strict=True))
    raw = pl.read_parquet(DEV / "daily_topic.parquet").filter(
        pl.col("topic") == "ai_all", pl.col("dt") == dt.date(2026, 10, 17)
    )
    by = dict(raw.group_by("lang_bucket").agg(pl.col("n_articles").sum()).iter_rows())
    assert n["all"] == sum(by.values())
    assert n["eng"] == by["eng"]
    assert n["espt"] == by["spa"] + by["por"]
