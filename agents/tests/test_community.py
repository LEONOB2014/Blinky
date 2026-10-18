"""The AI community sensor in the agents: get_community_signal, the route and the code line."""

import polars as pl
import pytest

from agents import runtime, tools
from agents.llm import Reply

pytestmark = pytest.mark.unit


@pytest.fixture
def community(tmp_path, monkeypatch):
    gold = tmp_path / "gold"
    gold.mkdir()
    rows = [
        ("ai:tech:llm", "2026-W42", "research", 76, 1, 4334.0),
        ("ai:tech:agents", "2026-W42", "research", 50, 2, 2453.0),
        ("ai:tech:agents", "2026-W42", "builders", 21, 2, 0.0),
        ("ai:risk:ai_safety", "2026-W42", "critics", 2, 1, 0.0),
        ("ai:risk:ai_safety", "2026-W42", "research", 14, 1, 10.0),
        ("ai:tech:llm", "2026-W41", "research", 30, 1, 5.0),
    ]
    pl.DataFrame(
        rows,
        schema=["topic_id", "week", "category", "n_items", "n_sources", "score"],
        orient="row",
    ).write_parquet(gold / "community_topic_weekly.parquet")
    monkeypatch.setenv("RADAR_PROFILE", "full")
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    return gold


def test_counts_per_category_and_top_topics_never_titles(community):
    out = tools.get_community_signal()
    assert out["week"] == "2026-W42" and "no validada" in out["no_validada"]
    assert out["por_categoria"][0] == {
        "category": "research",
        "category_es": "investigación",
        "n_items": 140,
        "n_temas": 3,
    }
    assert [t["topic_id"] for t in out["top_por_categoria"]["research"]] == [
        "ai:tech:llm",
        "ai:tech:agents",
        "ai:risk:ai_safety",
    ]
    assert "title" not in str(out) and "temas_de_postura_critica" not in out
    assert tools.get_community_signal(week="2026-W41")["por_categoria"][0]["n_items"] == 30
    one = tools.get_community_signal(topic_id="ai:tech:agents")
    assert {c["category"] for c in one["por_categoria"]} == {"research", "builders"}
    assert tools.get_community_signal(category="media")["available"] is False
    assert tools.get_community_signal(category="nope")["available"] is False


def test_the_critics_add_the_lexicons_critic_camp(community):
    out = tools.get_community_signal(category="critics")
    assert [c["category"] for c in out["por_categoria"]] == ["critics"]
    camp = out["temas_de_postura_critica"]
    assert camp[0]["topic_id"] == "ai:risk:ai_safety" and camp[0]["n_items"] == 16  # all categories


class Scripted:
    def chat(self, messages, tools_):
        return Reply(content="Nota del equipo.", model="scripted")


@pytest.mark.parametrize(
    ("question", "category", "starts"),
    [
        ("¿Qué está discutiendo la comunidad IA esta semana?", None, "La comunidad IA esta semana"),
        (
            "¿Qué piden las aceleradoras como Y Combinator?",
            "builders",
            "La comunidad IA esta semana",
        ),
        ("¿Qué dicen los críticos de la IA?", "critics", "Los críticos de la IA esta semana"),
    ],
)
def test_community_questions_get_the_code_written_line(
    community, monkeypatch, question, category, starts
):
    monkeypatch.setenv("RADAR_SOURCE", "ai")
    monkeypatch.setattr(runtime.tools, "get_top10", lambda week=None: {"available": False})
    assert runtime.community_category(question) == category
    response = runtime.run_turn(question, model=Scripted())
    answer = response["answer_es"]
    assert answer.startswith(starts) and "señal no validada" in answer
    assert "Decisión del radar" not in answer
    assert not [s for s in response["trace"] if s["action"] == "veto"]  # every number traced
    calls = [s for s in response["trace"] if s.get("tool") == "get_community_signal"]
    assert calls and calls[0]["agent"] == "signal_analyst"
    assert not [s for s in response["trace"] if s["agent"] == "cartographer"]  # no graph drift


def test_graph_communities_are_not_the_ai_community():
    assert not runtime._COMMUNITY_Q.search("¿Qué comunidades de temas se están formando?")
    assert runtime._COMMUNITY_Q.search("¿Qué está discutiendo la comunidad IA esta semana?")
