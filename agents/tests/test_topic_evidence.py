"""get_topic_evidence: up to 5 articles per topic-week, never the URL, used for named topics."""

import datetime as dt

import polars as pl
import pytest

from agents import runtime, tools
from agents.llm import Reply

MONDAY = dt.date(2026, 10, 12)


@pytest.fixture
def evidence_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")
    path = tmp_path / "topic_evidence_weekly.parquet"
    pl.DataFrame(
        {
            "week": [MONDAY] * 6,
            "topic_id": ["org:nvidia"] * 6,
            "evidence_rank": [1, 2, 3, 4, 5, 6],
            "gkg_id": [f"g{i}" for i in range(6)],
            "dt": [MONDAY] * 6,
            "source": [
                "a.example",
                "b.example",
                "c.example",
                "d.example",
                "e.example",
                "f.example",
            ],
            "lang_bucket": ["spa", "eng", "eng", "por", "eng", "eng"],
            "title": ["Titular de prueba"] * 6,
            "url": [f"https://a.example/{i}" for i in range(6)],
            "tone": [0.1] * 6,
            "why_selected": ["regla"] * 6,
        }
    ).write_parquet(path)
    real_gold = tools.gold
    monkeypatch.setattr(
        tools, "gold", lambda name: path if name == "topic_evidence_weekly" else real_gold(name)
    )
    return path


@pytest.fixture
def sources_file(tmp_path, monkeypatch, evidence_file):
    path = tmp_path / "topic_sources_weekly.parquet"
    pl.DataFrame(
        {
            "topic_id": ["org:nvidia", "org:nvidia"],
            "week": [MONDAY, MONDAY - dt.timedelta(days=7)],
            "n_articles": [44, 10],
            "n_sources": [39, 9],
            "top_source_share": [0.0455, 0.2],
            "top3_source_share": [0.1364, 0.4],
            "top_theme_pattern_share": [0.3, 0.3],
        }
    ).write_parquet(path)
    gold_with_evidence = tools.gold
    monkeypatch.setattr(
        tools,
        "gold",
        lambda name: path if name == "topic_sources_weekly" else gold_with_evidence(name),
    )
    return path


@pytest.mark.unit
def test_the_tool_returns_at_most_5_articles_and_no_url(evidence_file):
    out = tools.get_topic_evidence("org:nvidia", "2026-W42")
    assert out["available"] and out["week"] == "2026-W42"
    assert out["articulos_mostrados"] == 5 and out["medios_entre_mostrados"] == 5
    assert all("url" not in a for a in out["articles"])
    assert "https://" not in str(out)
    assert not tools.get_topic_evidence("org:nvidia", "2026-W30")["available"]


class ScriptedChat:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools_):
        self.calls.append(messages)
        return Reply(content="Según 5 artículos de 5 medios.", model="scripted")


@pytest.mark.unit
def test_a_named_topic_question_reads_the_evidence_without_urls(evidence_file):
    model = ScriptedChat()
    response = runtime.run_turn("¿Qué pasa con Nvidia esta semana?", model=model)
    used = [s for s in response["trace"] if s.get("tool") == "get_topic_evidence"]
    assert used, "the signal analyst reads the evidence for a named topic"
    sent = str(model.calls)
    assert "https://" not in sent  # the URL never reaches the model


@pytest.mark.unit
def test_sources_tool_gives_outlets_not_articles(sources_file):
    out = tools.get_topic_sources("org:nvidia", "2026-W42")
    assert out["available"] and out["week"] == "2026-W42"
    assert out["n_medios"] == 39 and out["n_articulos"] == 44
    assert out["cuota_medio_principal"] == 0.05 and out["cuota_3_medios_principales"] == 0.14
    assert tools.get_topic_sources("org:nvidia")["n_medios"] == 39  # latest week by default
    assert not tools.get_topic_sources("org:nvidia", "2026-W30")["available"]


@pytest.mark.unit
def test_a_named_topic_reads_its_outlet_count(sources_file):
    response = runtime.run_turn(
        "¿Cuántos medios cubren a Nvidia esta semana?", model=ScriptedChat()
    )
    used = [s for s in response["trace"] if s.get("tool") == "get_topic_sources"]
    assert used and used[0]["agent"] == "signal_analyst"


@pytest.mark.unit
def test_an_evidence_question_gets_the_articles_written_by_code(sources_file):
    model = ScriptedChat()
    response = runtime.run_turn("¿Qué artículos respaldan a Nvidia esta semana?", model=model)
    answer = response["answer_es"]
    assert "44 artículos de 39 medios" in answer
    assert answer.count("«Titular de prueba»") == 5
    assert (
        "a.example, 2026-10-12, español" in answer and "d.example, 2026-10-12, portugués" in answer
    )
    assert "https://" not in answer
    assert "No los repitas" in str(model.calls) or "No la repitas" in str(model.calls)


@pytest.mark.unit
def test_other_questions_get_no_evidence_block(sources_file):
    answer = runtime.run_turn("¿Qué pasa con Nvidia esta semana?", model=ScriptedChat())[
        "answer_es"
    ]
    assert "«Titular de prueba»" not in answer


@pytest.mark.unit
def test_an_outlet_count_question_gets_the_count_by_code_and_a_wrong_count_is_flagged(
    sources_file,
):
    class WrongCount(ScriptedChat):
        def chat(self, messages, tools_):
            self.calls.append(messages)
            return Reply(content="44 medios distintos cubrieron a Nvidia.", model="scripted")

    answer = runtime.run_turn(
        "¿Cuántos medios distintos cubren a Nvidia esta semana?", model=WrongCount()
    )["answer_es"]
    assert "Medios distintos que cubrieron a" in answer and ": 39 (en 44 artículos)." in answer
    assert "el número de medios distintos medido es 39; no 44 medios" in answer
    # the evidence block's "44 artículos de 39 medios" is never flagged
    turn = runtime.Turn("t")
    turn.tool_results.append(
        {"tool": "get_topic_sources", "result": tools.get_topic_sources("org:nvidia", "2026-W42")}
    )
    assert runtime.wrong_outlet_counts("44 artículos de 39 medios; 39 medios.", turn) == []
    assert runtime.wrong_outlet_counts("Lo cubren 44 medios.", turn) == ["44 medios"]
