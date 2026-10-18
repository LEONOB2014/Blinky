"""Each score on known dev-slice rows (week 2026-W42, subtopics)."""

import math

import polars as pl
import pytest

from models import features, scores

WEEK = "2026-W42"


@pytest.fixture(scope="module")
def roll() -> pl.DataFrame:
    return features.rolling(features.subtopic_daily(), features.load_totals())


@pytest.fixture(scope="module")
def scored(roll) -> pl.DataFrame:
    weights = {u: {u: 1.0} for u in roll["unit_id"].unique().to_list()}
    weights["ai_all"] = {}
    return scores.score(scores.weekly_panel(roll), weights)


@pytest.fixture(scope="module")
def w42(scored) -> dict[str, dict]:
    return {r["unit_id"]: r for r in scored.filter(pl.col("week") == WEEK).iter_rows(named=True)}


def _pct(values: dict[str, float | None]) -> dict[str, float]:
    """Average-rank percentile over the non-null values, written out by hand."""
    ok = {k: v for k, v in values.items() if v is not None and not math.isnan(v)}
    order = sorted(ok.values())
    out = {}
    for k, v in ok.items():
        lo, hi = order.index(v) + 1, len(order) - order[::-1].index(v)
        out[k] = (lo + hi) / 2 / len(order)
    return out


def test_week_uses_the_last_day_present(w42):
    assert {r["asof"].isoformat() for r in w42.values()} == {"2026-10-17"}


def test_ai_all_is_never_ranked(w42):
    assert "ai_all" not in w42
    assert len(w42) == 11


def test_emergence_is_the_percentile_of_the_mean_term_percentile(w42):
    terms = ("z_7d", "z_dow_7d", "growth_7d_log", "accel_7d")
    per = {t: _pct({u: r[t] for u, r in w42.items()}) for t in terms}
    raw = {u: sum(per[t][u] for t in terms if u in per[t]) / len(terms) for u in w42}
    expected = _pct(raw)
    for u, r in w42.items():
        assert r["emergence_pct"] == pytest.approx(100 * expected[u])


def test_emotional_charge_is_the_percentile_of_the_mean_self_z(w42):
    raw = {}
    for u, r in w42.items():
        vals = [r[t] for t in scores.CHARGE_TERMS if r[t] is not None]
        raw[u] = sum(vals) / len(vals) if vals else None
    expected = _pct(raw)
    for u, r in w42.items():
        assert r["emotional_charge_pct"] == pytest.approx(100 * expected[u])


def test_saturation_is_the_mean_of_hot_days_and_espt_onset_days(w42, roll):
    r = w42["jobs_work"]
    days = roll.filter(
        pl.col("unit_id") == "jobs_work",
        pl.col("dt") <= r["asof"],
        pl.col("dt") > r["asof"] - pl.duration(days=28),
    )
    eng_all = days.filter(pl.col("group") == "all", pl.col("z_7d_r").is_not_null())
    hot = (eng_all["z_7d_r"] > 1).mean()
    espt = days.filter(pl.col("group") == "espt").sort("dt").tail(7)
    onset = (espt["z_7d_r"] > 2).cast(pl.Float64).mean()
    assert r["saturation"] == pytest.approx((hot + onset) / 2)
    assert 0 <= r["saturation"] <= 1


def test_audience_fit_rewards_business_and_education(w42):
    for u, r in w42.items():
        assert 0.4 <= r["audience_fit"] <= 1.0
        assert (r["fit_subtopic"] == 1.0) == (u in scores.FIT_SUBTOPICS)
    assert w42["business_adoption"]["audience_fit"] >= 0.7
    assert w42["agents"]["audience_fit"] < 0.7


def test_priority_formula(w42):
    for r in w42.values():
        expected = (
            r["emergence_pct"] / 100
            * (1 - r["saturation"])
            * r["audience_fit"]
            * (1 + 0.25 * r["emotional_charge_pct"] / 100)
        )  # fmt: skip
        assert r["priority"] == pytest.approx(expected)


def test_rank_orders_priority(w42):
    ranked = sorted(w42.values(), key=lambda r: r["rank"])
    assert [r["rank"] for r in ranked] == list(range(1, 12))
    assert all(a["priority"] >= b["priority"] for a, b in zip(ranked, ranked[1:], strict=False))


def test_stage_follows_the_rule_table(w42):
    for r in w42.values():
        level = r["share_7d"] / r["share_7d_max56"]
        if r["growth_7d_log"] <= -0.15 and level < 0.85:
            assert r["stage"] == "en_declive"
        elif r["saturation"] >= 0.6:
            assert r["stage"] == "saturado"
        elif r["z_7d"] >= 2 and r["accel_7d"] <= 0:
            assert r["stage"] == "en_pico"
        elif r["z_7d"] >= 1 or (r["growth_7d_log"] >= 0.15 and r["accel_7d"] > 0):
            assert r["stage"] == "emergente"
    assert {r["stage"] for r in w42.values()} <= {s for s, _ in scores.STAGE_RULES}


def test_framing_angle_follows_the_rule_table(w42):
    names = [a for a, _ in scores.ANGLES]
    for r in w42.values():
        assert r["framing_angle"] in names
        if r["framing_angle"] == "Debate":
            assert r["z_controversy"] > 1.5
        if r["framing_angle"] == "Explicador neutral":
            assert not (r["z_controversy"] or 0) > 1.5
            assert not abs(r["z_tone_shift"] or 0) > 1.5


def test_ineligible_units_have_no_rank(roll):
    weights = {u: {u: 1.0} for u in roll["unit_id"].unique().to_list()}
    panel = scores.weekly_panel(roll).with_columns(
        pl.when(pl.col("unit_id") == "agents").then(5.0).otherwise(pl.col("n_7d")).alias("n_7d")
    )
    s = scores.score(panel, weights).filter(pl.col("week") == WEEK, pl.col("unit_id") == "agents")
    assert s["rank"].to_list() == [None]
    assert s["emergence_pct"].to_list() == [None]
