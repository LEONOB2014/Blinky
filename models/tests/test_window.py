"""The window chip's four states on real dev-slice topics.

Onsets come from the real S8 view (`fixtures/dev/daily_topic_rolling.parquet`, non-LatAm
streams), whose z_7d has BigQuery history before the slice starts; English = `eng`, es/pt =
`spa` + `por`.
"""

import datetime as dt

import polars as pl
import pytest

from models import window
from radar.paths import REPO_ROOT

D = dt.date


@pytest.fixture(scope="module")
def s8_onsets() -> dict[str, dict[str, list[dt.date]]]:
    s8 = pl.read_parquet(REPO_ROOT / "fixtures" / "dev" / "daily_topic_rolling.parquet")
    s8 = s8.filter(~pl.col("latam"))
    out: dict[str, dict[str, list[dt.date]]] = {}
    for (topic, bucket), g in s8.group_by("topic", "lang_bucket"):
        g = g.sort("dt")
        group = {"eng": "eng", "spa": "espt", "por": "espt"}.get(bucket)
        if group:
            o = out.setdefault(topic, {"eng": [], "espt": []})
            o[group] += window.onsets(g["dt"].to_list(), g["z_7d"].to_list())
    return out


def _chip(o, topic, asof, min_onsets=window.MIN_ONSETS, pooled=None):
    t = o[topic]
    lags = window.lag_pairs(t["eng"], t["espt"], asof) if pooled is None else pooled
    return window.chip(t["eng"], t["espt"], lags, asof, min_onsets)


def test_onsets_need_an_observed_quiet_spell():
    days = [D(2026, 9, 1) + dt.timedelta(days=i) for i in range(20)]
    # a series that starts above 2 has no onset until it cools for REARM_DAYS observed days
    z = [None, 3.0, 3.0] + [0.0] * 7 + [2.5, 2.6] + [None] * 3 + [0.0] * 5
    assert window.onsets(days, z) == [D(2026, 9, 11)]


def test_ya_en_espanol(s8_onsets):
    # safety_risk: English onset 2026-09-09, Spanish onset 2026-09-10 (real)
    assert s8_onsets["safety_risk"]["eng"] == [D(2026, 9, 9)]
    w = _chip(s8_onsets, "safety_risk", D(2026, 9, 12))
    assert (w.state, w.days_left) == ("ya_en_espanol", None)


def test_sin_estimacion_without_an_english_onset(s8_onsets):
    # chips_infra never crosses z_7d > 2 in English in the slice (real)
    assert s8_onsets["chips_infra"]["eng"] == []
    assert _chip(s8_onsets, "chips_infra", D(2026, 10, 17)).state == "sin_estimacion"


def test_sin_estimacion_with_fewer_than_three_onsets(s8_onsets):
    # llms_models: English onset 2026-09-19 and no complete English -> es/pt pair yet (real)
    w = _chip(s8_onsets, "llms_models", D(2026, 9, 20))
    assert (w.state, w.n_onsets) == ("sin_estimacion", 0)


def test_en_cualquier_momento_lowers_the_threshold(s8_onsets):
    """No dev topic has 3 historical onsets, so this test lowers the threshold from 3 to 1.

    education: English onsets 2026-09-03 and 09-17; the 09-03 pair has a 0-day lag (real), so
    on 2026-09-18 the typical lag (0) has already passed and es/pt has not started yet.
    """
    w = _chip(s8_onsets, "education", D(2026, 9, 18), min_onsets=1)
    assert (w.state, w.n_onsets, w.typical_lag_days) == ("en_cualquier_momento", 1, 0.0)
    assert _chip(s8_onsets, "education", D(2026, 9, 18)).state == "sin_estimacion"


def test_dias_restantes_lowers_the_threshold_and_borrows_a_real_lag(s8_onsets):
    """No dev topic has a real case of this state, even with the threshold lowered.

    Every complete pair in the slice has a lag of 0 or 1 day, except llms_models (English
    2026-09-19 -> Portuguese 2026-10-02, 13 days, real). This test lowers the threshold from
    3 to 1 and pools that one real lag for agents, one day after its real English onset.
    """
    llms = s8_onsets["llms_models"]
    lag = window.lag_pairs(llms["eng"], llms["espt"], D(2026, 10, 17))
    assert lag == [13]
    assert s8_onsets["agents"]["eng"] == [D(2026, 9, 24)]
    w = _chip(s8_onsets, "agents", D(2026, 9, 25), min_onsets=1, pooled=lag)
    assert (w.state, w.days_left, w.n_onsets) == ("dias_restantes", 12, 1)


def test_pairs_ignore_onsets_after_the_asof_day(s8_onsets):
    llms = s8_onsets["llms_models"]
    assert window.lag_pairs(llms["eng"], llms["espt"], D(2026, 10, 1)) == []


def test_chip_record_matches_the_contract_fields():
    rec = window.Window("dias_restantes", 4, 6.0, 3).as_record()
    assert set(rec) == {"state", "days_left", "typical_lag_days", "n_onsets"}
