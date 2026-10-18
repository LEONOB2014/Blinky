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
        assert r["n_pos"] <= math.ceil(r["n_mapped"] / 4)
        assert len(r["positives"]) == r["n_pos"]


def test_positives_do_not_depend_on_row_order(inputs, res):
    """Ties in label growth must not be broken by row order (which favoured the radar's rows)."""
    s, raw, daily = inputs
    shuffled = s.sample(fraction=1.0, shuffle=True, seed=7)
    r2 = bt.evaluate(shuffled, raw, daily, set(s["unit_id"].to_list()), "gdelt_espt")
    rows = zip(res.per_week.iter_rows(named=True), r2.per_week.iter_rows(named=True), strict=True)
    for a, b in rows:
        assert set(a["positives"]) == set(b["positives"])
        assert a["hits_radar"] == b["hits_radar"]


def test_hits_recount_by_hand(res, inputs):
    s, _, daily = inputs
    r = res.per_week.row(0, named=True)
    t = r["asof"]
    nxt = bt.window_sum(daily, t + dt.timedelta(days=1), t + dt.timedelta(days=14))
    cur = bt.window_sum(daily, t - dt.timedelta(days=13), t)
    g = nxt.join(cur, on="unit_id", suffix="_cur").filter(pl.col("unit_id") != "ai_all")
    g = g.with_columns(((pl.col("s") + 1) / (pl.col("s_cur") + 1)).log().alias("growth"))
    g = g.with_columns(pl.col("growth").rank("average", descending=True).alias("r"))
    positives = set(g.filter(pl.col("r") <= math.ceil(g.height / 4))["unit_id"])
    assert positives == set(r["positives"])
    week = s.filter(pl.col("week") == r["week"], pl.col("rank").is_not_null())
    top = set(week.sort("priority", descending=True).head(10)["unit_id"])
    assert r["hits_radar"] == len(top & positives)


def test_pooled_precision_is_positives_over_total(res):
    for name in res.coverage:
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


def test_coverage_counts_each_rankers_top_10(res):
    # weeks that pass the calendar checks count. W35's label window is too thin at the start of
    # the slice, so the radar's W35 top 10 counts as needed but unlabelled; the baselines have
    # no W35 top 10 (no raw growth or past growth yet)
    thin = [w for w, why in res.excluded.items() if "mapped units with a label" in why]
    assert thin == ["2026-W35"]
    assert res.coverage["radar"] == (10 * len(res.weeks), 10 * (len(res.weeks) + 1))
    for name in ("raw_count_growth", "persistence"):
        have, need = res.coverage[name]
        assert have == need <= 10 * len(res.weeks)


def test_below_the_coverage_threshold_precision_is_bounded(inputs):
    s, raw, daily = inputs
    r = bt.evaluate(s, raw, daily, set(s["unit_id"].to_list()), "gdelt_espt", min_coverage=1.01)
    assert r.refused
    assert r.pooled == {}  # no unbounded precision below the rule
    text = "\n".join(bt.render_section(r))
    assert "Below the 90.0% coverage rule" in text and "Worst case" in text
    for name, e in r.bounded.items():
        if name == "base_rate":
            continue
        assert e["worst"] <= (e["precision"] or 0) <= e["best"] or e["labelled"] == 0
        assert e["worst"] == e["hits"] / e["slots"]
        assert e["best"] == (e["hits"] + e["slots"] - e["labelled"]) / e["slots"]
    # the radar's unlabelled W35 slots make its bounds differ; the baselines are fully labelled
    assert r.bounded["radar"]["worst"] < r.bounded["radar"]["best"]
    assert r.bounded["persistence"]["worst"] == r.bounded["persistence"]["best"]
    assert "radar|raw_count_growth" in r.worst_vs


def test_worst_case_comparison_uses_the_radars_worst_and_the_baselines_best():
    res = bt.Result(label="pageviews")
    res.worst_vs["radar_gated|raw_count_growth"] = {"diff": 0.05, "ci": (0.01, 0.09)}
    assert bt.worst_case_holds(res)
    res.worst_vs["radar_gated|raw_count_growth"] = {"diff": 0.05, "ci": (-0.01, 0.09)}
    assert not bt.worst_case_holds(res)
    assert not bt.worst_case_holds(bt.Result(label="pageviews"))


def test_gated_ranker_reads_the_published_rank(inputs):
    s, raw, daily = inputs
    gated = s.filter(pl.col("rank").is_not_null()).select("unit_id", "week", "rank")
    r = bt.evaluate(s, raw, daily, set(s["unit_id"].to_list()), "gdelt_espt", gated)
    # with the published rank equal to Priority's order, the two radars pick the same top 10
    assert r.pooled["radar_gated"]["hits"] == r.pooled["radar"]["hits"]
    assert "radar_gated|radar" in r.diffs
    assert r.diffs["radar_gated|radar"]["diff"] == 0
