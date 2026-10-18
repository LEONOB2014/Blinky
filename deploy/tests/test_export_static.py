import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import export_static  # noqa: E402


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "dev"])
def test_export_refuses_outside_the_full_profile(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("RADAR_PROFILE", raising=False)
    else:
        monkeypatch.setenv("RADAR_PROFILE", value)
    with pytest.raises(SystemExit, match="refusing"):
        export_static.export(tmp_path / "data")
    assert not (tmp_path / "data").exists()


@pytest.mark.unit
def test_slug_matches_the_web_rule():
    # web/src/api.ts: id.toLowerCase().replace(/[^a-z0-9]+/g, "_"), trimmed of "_"
    assert export_static.slug("org:openai group") == "org_openai_group"
    assert export_static.slug("thm:TECH_AUTOMATION") == "thm_tech_automation"
    assert export_static.slug("regulation_policy") == "regulation_policy"
    assert export_static.slug("org:at&t") == "org_at_t"


@pytest.mark.unit
def test_topic_evidence_json_keeps_the_top_10_of_the_last_4_weeks():
    import datetime as dt

    import polars as pl

    weeks = ["2026-W38", "2026-W39", "2026-W40", "2026-W41", "2026-W42"]
    scores = pl.DataFrame(
        {
            "week": [w for w in weeks for _ in range(2)],
            "topic_id": ["org:a", "org:b"] * 5,
            "rank": [1, 11] * 5,
        }
    )
    mondays = [dt.date.fromisocalendar(2026, int(w[-2:]), 1) for w in weeks]
    evidence = pl.DataFrame(
        {
            "week": [m for m in mondays for _ in range(2)],
            "topic_id": ["org:a", "org:b"] * 5,
            "evidence_rank": [1, 1] * 5,
            "gkg_id": [f"g{i}" for i in range(10)],
            "dt": [m for m in mondays for _ in range(2)],
            "source": ["s.example"] * 10,
            "lang_bucket": ["spa"] * 10,
            "title": [None] * 10,
            "url": ["https://s.example/x"] * 10,
            "tone": [0.5] * 10,
            "why_selected": ["rule"] * 10,
        }
    )
    out = export_static.topic_evidence_json(scores, evidence)
    assert set(out) == {"org_a"}  # org:b is ranked 11th: not in the top 10
    assert sorted(out["org_a"]["weeks"]) == weeks[-4:]  # the oldest week is dropped
    article = out["org_a"]["weeks"]["2026-W42"][0]
    assert article["url"].startswith("https://") and article["dt"] == "2026-10-12"
    assert "week" not in article and "topic_id" not in article
