"""The week's AI leaders by volume (agents.tools.get_leaders), the API endpoint and the route."""

import datetime as dt

import polars as pl
import pytest

from agents import runtime, tools
from agents.llm import Reply

pytestmark = pytest.mark.unit
W41, W42 = dt.date(2026, 10, 5), dt.date(2026, 10, 12)


@pytest.fixture
def ai_lake(tmp_path, monkeypatch):
    """Nvidia leads by volume but not by emergence; W42 has a missing day (6 days with data)."""
    rows = []
    for k in range(7):
        rows.append(("ai:infra:nvidia", W41 + dt.timedelta(days=k), "eng", 70, False))
        rows.append(("ai:lab:openai", W41 + dt.timedelta(days=k), "eng", 40, False))
    for k in range(6):
        day = W42 + dt.timedelta(days=k)
        rows.append(("ai:infra:nvidia", day, "eng", 70, False))
        rows.append(("ai:infra:nvidia", day, "spa", 10, False))
        rows.append(("ai:lab:openai", day, "eng", 20, False))
    rows.append(("ai:infra:nvidia", W42 + dt.timedelta(days=6), "eng", 999, True))  # missing day
    rows.append(("ai:lab:anthropic", W42, "eng", 5, False))  # new this week: no change
    daily = pl.DataFrame(
        rows, schema=["topic_id", "dt", "lang_bucket", "n_articles", "is_missing"], orient="row"
    ).with_columns(pl.lit("ai").alias("segment"))
    gold = tmp_path / "gold"
    gold.mkdir()
    daily.write_parquet(gold / "topic_ai_daily.parquet")
    pl.DataFrame(
        {
            "week": ["2026-W42"] * 2,
            "topic_id": ["ai:infra:nvidia", "ai:lab:anthropic"],
            "rank": [54, 1],
            "decision": ["no_es_tema_caliente", "preparar"],
        }
    ).write_parquet(gold / "topic_ai_scores_weekly.parquet")
    monkeypatch.setenv("RADAR_PROFILE", "full")
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    return gold


def test_leaders_rank_by_volume_with_change_per_day_and_lexicon_fields(ai_lake):
    out = tools.get_leaders()
    assert out["week"] == "2026-W42" and out["days_with_data"] == 6  # the missing day is out
    assert out["prev_week_days_with_data"] == 7
    nvidia, openai, anthropic = out["rows"]
    assert [r["leader_rank"] for r in out["rows"]] == [1, 2, 3]
    assert nvidia["topic_id"] == "ai:infra:nvidia" and nvidia["articles"] == 480  # 999 not counted
    assert nvidia["articles_prev_week"] == 490
    assert nvidia["change_vs_prev_week"] == round((480 / 6) / (490 / 7) - 1, 4)  # per day
    assert nvidia["espt_share"] == 0.125
    assert nvidia["label_es"] == "Nvidia" and nvidia["family"] == "infra"
    assert nvidia["stance"] in {"promoter", "critic", "neutral"}
    assert (nvidia["emergence_rank"], nvidia["decision"]) == (54, "no_es_tema_caliente")
    assert openai["emergence_rank"] is None  # not scored that week
    assert anthropic["change_vs_prev_week"] is None  # no articles the week before
    assert tools.get_leaders("2026-W42", limit=1)["rows"] == [nvidia]
    assert not tools.get_leaders("2026-W30")["available"]


def test_leaders_are_unavailable_without_the_ai_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "full")
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    assert tools.get_leaders()["available"] is False


class Scripted:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools_):
        self.calls.append(messages)
        return Reply(content="Nota del equipo.", model="scripted")


def test_a_biggest_this_week_question_gets_the_leaders_written_by_code(ai_lake, monkeypatch):
    monkeypatch.setenv("RADAR_SOURCE", "ai")
    monkeypatch.setattr(runtime.tools, "get_top10", lambda week=None: {"available": False})
    answer = runtime.run_turn("¿Qué es lo más grande esta semana en IA?", model=Scripted())[
        "answer_es"
    ]
    assert answer.startswith("Lo más grande de la semana (2026-W42")
    assert "1. Nvidia (Infraestructura y chips): 480 artículos" in answer
    assert "en emergencia va en el puesto 54" in answer
    assert "Decisión del radar" not in answer  # the emergence #1 would mislead here
    assert runtime._LEADERS_Q.search("¿Qué es lo más importante de la semana?")
    assert not runtime._LEADERS_Q.search("¿Qué tema de IA está subiendo esta semana?")
