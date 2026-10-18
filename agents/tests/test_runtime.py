"""The runtime's code paths: routing, data plans, decision guard, Auditor and contract shapes.

The model is a scripted stand-in for the HTTP transport (no network); every data value comes from
the real dev slice through the tools.
"""

import pytest
from jsonschema import Draft202012Validator

from agents import runtime
from agents.llm import Reply
from radar.contracts import load_schema


class ScriptedChat:
    """Returns a fixed final text for the Media Master and a short note for each specialist."""

    def __init__(self, master_text: str) -> None:
        self.master_text = master_text
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools):
        self.calls.append(messages)
        if messages[0]["content"].startswith("Eres el Maestro de Medios"):
            return Reply(content=self.master_text, model="scripted")
        return Reply(content="Nota del especialista.", model="scripted")


@pytest.fixture(autouse=True)
def _dev(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")


@pytest.mark.unit
def test_route_finds_the_specialists_a_question_needs():
    assert runtime.route("muéstramelo en el grafo") == ["cartographer"]
    needed = runtime.route("¿qué tema publico esta semana para ejecutivos de LatAm?")
    assert {"signal_analyst", "audience_strategist"} <= set(needed)


@pytest.mark.unit
def test_auditor_flags_numbers_no_tool_returned():
    results = [{"result": {"articles_7d": 592.0, "growth_7d_log": 0.5192, "share": 0.6216}}]
    answer = "592 artículos, crecimiento 0.52, 62.16% en LatAm y 9999 inventados"
    assert runtime.untraced_numbers(answer, results, "") == ["9999"]


@pytest.mark.unit
def test_a_turn_vetoes_invented_decisions_and_numbers():
    model = ScriptedChat("Decisión: Publicar ahora. Son 987654 artículos.")
    response = runtime.run_turn("¿Qué tema sube esta semana? muéstramelo en el grafo", model=model)
    assert "publicar ahora" not in response["answer_es"].lower()
    assert "987654" in response["answer_es"] and "no verificados" in response["answer_es"]
    vetoes = [s for s in response["trace"] if s["action"] == "veto"]
    assert len(vetoes) == 2  # the decision and the number
    assert response["view_commands"], "the graph was asked for, so code emits a view"


@pytest.mark.unit
def test_a_turn_matches_the_api_contract_shapes():
    response = runtime.run_turn(
        "¿Qué tema sube esta semana?", model=ScriptedChat("Decisión: PENDIENTE")
    )
    trace = Draft202012Validator(load_schema("agent_trace"))
    view = Draft202012Validator(load_schema("view_command"))
    assert all(trace.is_valid(step) for step in response["trace"])
    assert all(view.is_valid(cmd) for cmd in response["view_commands"])
    agents = {s["agent"] for s in response["trace"]}
    assert {"media_master", "signal_analyst", "auditor"} <= agents


def test_cost_questions_reach_the_scout():
    from agents.runtime import route

    assert "scout" in route("¿Cuánto ha costado BigQuery hasta ahora?")
    assert "scout" in route("¿Cuánto se ha gastado?")


def _turn_with(rows, tool="get_top10"):
    turn = runtime.Turn("t")
    turn.tool_results.append(
        {"source": "t:1", "tool": tool, "args": {}, "result": {"available": True, "rows": rows}}
    )
    return turn


_ROWS = [
    {"topic_id": "org:marsh mclennan", "label_es": "Marsh & McLennan", "rank": 1,
     "decision": "preparar"},
    {"topic_id": "org:euronext", "label_es": "org:euronext", "rank": 2, "decision": "esperar"},
    {"topic_id": "chips_infra", "label_es": None, "rank": 3, "decision": "publicar_ahora"},
]  # fmt: skip


@pytest.mark.unit
def test_decision_line_is_plain_words_for_what_was_asked():
    turn = _turn_with(_ROWS)
    one = runtime.decision_line(turn, None, "¿Qué tema sube esta semana?")
    assert one == "Decisión del radar: Preparar — Marsh & McLennan."
    three = runtime.decision_line(turn, None, "Dame el top 3")
    assert three.endswith("Esperar — euronext; Publicar ahora — Chips e infraestructura.")
    assert "org:" not in three and "_" not in three
    mine = runtime.decision_line(turn, "org:euronext", "¿Euronext es tema caliente?")
    assert mine == "Decisión del radar para euronext: Esperar."
    none = runtime.decision_line(turn, "org:nvidia", "¿Qué pasa con Nvidia?")
    assert "nvidia no está entre los temas puntuados" in none
    assert "pendiente" in runtime.decision_line(runtime.Turn("t"), None, "¿Qué sube?")


@pytest.mark.unit
def test_the_answer_starts_with_the_code_decision_line():
    model = ScriptedChat("Por qué:\n- crece rápido\nQué hacer: un carrusel.")
    response = runtime.run_turn("¿Qué tema sube esta semana?", model=model)
    first = response["answer_es"].splitlines()[0]
    assert first.startswith("Decisión del radar:")  # dev slice: no scores -> pendiente
    master = [m for m in model.calls if m[0]["content"].startswith("Eres el Maestro")][-1]
    assert "No la repitas" in master[1]["content"] and "z_7d" in master[1]["content"]


@pytest.mark.unit
def test_out_of_scope_questions_get_an_honest_answer_without_the_llm():
    model = ScriptedChat("no debería llamarse")
    for q in [
        "¿Cuántos likes tendrá mi próximo post en LinkedIn?",
        "¿Qué opina Sam Altman de la IA?",
    ]:
        response = runtime.run_turn(q, model=model)
        assert response["answer_es"].startswith("Eso no lo puede responder el radar")
        assert not runtime._numbers(response["answer_es"])
        assert response["decision_cards"] == [] and response["view_commands"] == []
    assert model.calls == []
    assert runtime.out_of_scope("Escribe un gancho para un post de LinkedIn") is None
    assert runtime.out_of_scope("¿Qué debería publicar 30X esta semana?") is None


@pytest.mark.unit
def test_specialists_are_asked_for_short_plain_notes():
    model = ScriptedChat("Por qué: crece.")
    runtime.run_turn("¿Qué tema sube esta semana?", model=model)
    specialist = [m for m in model.calls if not m[0]["content"].startswith("Eres el Maestro")]
    assert specialist and all(runtime.NOTE_STYLE in m[0]["content"] for m in specialist)
