"""The Editor's briefs: JSON parsing, the Auditor's checks and the contract, with a scripted model."""

import json

import pytest

from agents import briefs
from agents.llm import Reply
from radar.contracts import validate_records

GOOD = {
    "headline_es": "Marsh & McLennan entra al radar de IA",
    "what_happened_es": "Pasó de 0 a 44 artículos en inglés en una semana, en 39 medios.",
    "why_latam_es": "Aún no aparece en español: hay tiempo para explicarlo primero.",
    "angle_es": "Explicador neutral: qué hace y por qué importa.",
    "hook_es": "Una aseguradora global aparece de golpe en las noticias de IA.",
    "format_es": "Post de texto: el tema es nuevo y pide contexto breve.",
}


def topic_data(decision: str = "preparar") -> briefs.TopicData:
    row = {"topic_id": "org:marsh mclennan", "rank": 1, "decision": decision,
           "label_es": "Marsh & McLennan Companies"}  # fmt: skip
    facts = {"tema": "Marsh & McLennan Companies", "articulos_semana": 44, "medios_semana": 39,
             "articulos_en_ingles_por_semana": [0, 0, 0, 44]}  # fmt: skip
    numbers = [
        briefs.Cited("articulos_semana", 44, "measured", "topic_sources_weekly"),
        briefs.Cited("medios_semana", 39, "measured", "topic_sources_weekly"),
    ]
    return briefs.TopicData(row, "2026-W42", facts, numbers)


class Scripted:
    model = "scripted"

    def __init__(self, *contents: str) -> None:
        self.contents = list(contents)
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        return Reply(content=self.contents.pop(0), model="scripted", tokens=100)


@pytest.mark.unit
def test_parse_reply_tolerates_fences_and_rejects_bad_replies():
    fenced = "Aquí está:\n```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
    assert briefs.parse_reply(fenced) == GOOD
    with pytest.raises(ValueError, match="JSON"):
        briefs.parse_reply("Lo siento, no puedo.")
    with pytest.raises(ValueError, match="faltan campos"):
        briefs.parse_reply(json.dumps({"headline_es": "x"}))
    with pytest.raises(json.JSONDecodeError):
        briefs.parse_reply("{headline_es: sin comillas}")


@pytest.mark.unit
def test_auditor_flags_an_invented_number_and_a_wrong_decision():
    invented = GOOD | {"what_happened_es": "Creció 380% y lo leyeron 5000 ejecutivos."}
    untraced, wrong, _ = briefs.audit(invented, topic_data())
    assert untraced == ["380%", "5000"]
    assert wrong == []
    contradicted = GOOD | {"angle_es": "Recomendación: publicar ahora."}
    _, wrong, _ = briefs.audit(contradicted, topic_data(decision="preparar"))
    assert wrong == ["publicar ahora"]
    assert briefs.audit(GOOD, topic_data()) == ([], [], [])


@pytest.mark.unit
def test_style_problems_are_reported():
    _, _, style = briefs.audit(GOOD | {"hook_es": "org:marsh mclennan se hará viral"}, topic_data())
    assert any("identificadores" in s for s in style) and any("viral" in s for s in style)


@pytest.mark.unit
def test_a_bad_reply_is_retried_once_and_the_brief_validates():
    model = Scripted("no es JSON", json.dumps(GOOD, ensure_ascii=False))
    result = briefs.write_brief(model, topic_data())
    assert model.calls == 2 and result.retried
    record = result.record
    assert record["auditor_ok"] and record["untraced_numbers"] == []
    assert {c["name"] for c in record["numbers_cited"]} == {"articulos_semana", "medios_semana"}
    assert validate_records("topic_briefs_weekly", [record]) == []


@pytest.mark.unit
def test_a_brief_that_fails_twice_is_kept_and_flagged():
    bad = json.dumps(GOOD | {"what_happened_es": "Subió 380% en un día."}, ensure_ascii=False)
    result = briefs.write_brief(Scripted(bad, bad), topic_data())
    assert result.retried and not result.record["auditor_ok"]
    assert result.record["untraced_numbers"] == ["380%"]
    assert validate_records("topic_briefs_weekly", [result.record]) == []


@pytest.mark.unit
def test_humanize_turns_codes_into_words():
    assert briefs.humanize("thm:WB_1649_UNEMPLOYMENT_BENEFITS") == "unemployment benefits"
    assert briefs.humanize("thm:TECH_AUTOMATION") == "automation"
    assert briefs.humanize("org:kroger") == "kroger"


@pytest.mark.unit
def test_overclaims_are_reported():
    hook = "En 12 días, Rocket Lab podría estar en todos los medios en español."
    _, _, style = briefs.audit(GOOD | {"hook_es": hook}, topic_data())
    assert any("todos los medios" in s for s in style)
