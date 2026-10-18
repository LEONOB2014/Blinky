"""Backtest mechanics on the dev slice.

The dev slice has no pageviews, so these tests use the design's secondary label (es+pt GDELT
article growth of the same unit) and score every week, warm-up included, to have weeks with a
complete label window. Numbers from the dev profile are never reported.
"""

import datetime as dt
import math

import polars as pl
import pytest

from models import backtest as bt
from models import features, scores


@pytest.fixture(scope="module")
def inputs():
    roll = features.rolling(features.subtopic_daily(), features.load_totals())
    w = {u: {u: 1.0} for u in roll["unit_id"].unique().to_list()}
    w["ai_all"] = {}
    s = scores.score(scores.weekly_panel(roll), w)
    allg = roll.filter(pl.col("group") == "all").sort("unit_id", "dt")
    allg = allg.with_columns(
        ((pl.col("n_7d") + 1) / (pl.col("n_7d").shift(7).over("unit_id") + 1))
        .log()
        .alias("raw_growth")
    )
    raw = s.select("unit_id", "week", "asof").join(
        allg.select("unit_id", pl.col("dt").alias("asof"), "raw_growth"),
        on=["unit_id", "asof"],
        how="left",
    )
    daily = bt.gdelt_espt_label(roll)
    return s, raw.select("unit_id", "week", "raw_growth"), daily


@pytest.fixture(scope="module")
def res(inputs):
    s, raw, daily = inputs
    return bt.evaluate(s, raw, daily, set(s["unit_id"].to_list()), "gdelt_espt")


def test_weeks_without_a_complete_label_window_are_excluded(res):
    # the slice ends 2026-10-17: as-of days after 2026-10-03 have no 14 days of label after them
    for w in ("2026-W40", "2026-W41", "2026-W42"):
        assert res.excluded[w] == "label window not complete"
    assert res.weeks == ["2026-W36", "2026-W37", "2026-W38", "2026-W39"]


def test_positives_are_the_top_quartile(res):
    for r in res.per_week.iter_rows(named=True):
        assert r["n_pos"] == math.ceil(r["n_mapped"] / 4)
        assert len(r["positives"]) == r["n_pos"]


def test_hits_recount_by_hand(res, inputs):
    s, _, daily = inputs
    r = res.per_week.row(0, named=True)
    t = r["asof"]
    nxt = bt.window_sum(daily, t + dt.timedelta(days=1), t + dt.timedelta(days=14))
    cur = bt.window_sum(daily, t - dt.timedelta(days=13), t)
    g = nxt.join(cur, on="unit_id", suffix="_cur").filter(pl.col("unit_id") != "ai_all")
    g = g.with_columns(((pl.col("s") + 1) / (pl.col("s_cur") + 1)).log().alias("growth"))
    positives = set(g.sort("growth", descending=True).head(r["n_pos"])["unit_id"])
    assert positives == set(r["positives"])
    week = s.filter(pl.col("week") == r["week"], pl.col("rank").is_not_null())
    top = set(week.sort("priority", descending=True).head(10)["unit_id"])
    assert r["hits_radar"] == len(top & positives)


def test_pooled_precision_is_positives_over_total(res):
    for name in bt.RANKERS:
        e = res.pooled[name]
        assert e["total"] == 10 * len(res.weeks)
        assert e["precision"] == e["hits"] / e["total"]
        assert "ci" not in e  # fewer than 10 weeks: counts without an interval


def test_gap_weeks_are_excluded(inputs, monkeypatch):
    s, raw, daily = inputs
    monkeypatch.setattr(bt, "GAP", (dt.date(2026, 9, 20), dt.date(2026, 9, 21)))
    r = bt.evaluate(s, raw, daily, set(s["unit_id"].to_list()), "gdelt_espt")
    assert all("gap" in r.excluded[w] for w in ("2026-W36", "2026-W37", "2026-W38", "2026-W39"))


def test_unmapped_units_are_left_out_and_counted(inputs):
    s, raw, daily = inputs
    r = bt.evaluate(s, raw, daily, {"agents", "education"}, "gdelt_espt")
    assert r.weeks == []
    assert r.n_mapped_units == 2
    assert (
        r.n_unmapped_rows
        == s.filter(
            pl.col("rank").is_not_null(), ~pl.col("unit_id").is_in(["agents", "education"])
        ).height
    )


def test_lead_time_is_weeks_to_the_peak(inputs, monkeypatch):
    _, _, daily = inputs
    monkeypatch.setattr(bt, "LEAD_WEEKS", 2)
    lead = bt.weekly_peak_lead(daily, "education", dt.date(2026, 9, 27))
    assert lead in (1, 2)
    assert bt.weekly_peak_lead(daily, "education", dt.date(2026, 10, 11)) is None


def test_report_says_when_the_radar_does_not_beat_the_baselines(res):
    text = bt.render(res)
    assert "does not beat both baselines" in text
    assert "(measured)" in text
    assert "Evaluable weeks: 4" in text
