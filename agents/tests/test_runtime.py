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
