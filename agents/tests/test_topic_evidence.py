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


@pytest.mark.unit
def test_the_tool_returns_at_most_5_articles_and_no_url(evidence_file):
    out = tools.get_topic_evidence("org:nvidia", "2026-W42")
    assert out["available"] and out["week"] == "2026-W42"
    assert out["n_articulos"] == 5 and out["n_medios"] == 5
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
