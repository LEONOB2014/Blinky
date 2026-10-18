"""The 'Cómo se arma el grafo' line: written by code from the view's metadata or the ring's criteria."""

import json

import pytest

from agents import runtime, tools
from agents.llm import Reply


@pytest.fixture
def view(tmp_path, monkeypatch):
    """A two-week temporal view: week 1 draws 3 nodes and 2 edges (node 3 has no edge then)."""
    views = tmp_path / "views"
    views.mkdir()
    (views / "temporal.json").write_text(
        json.dumps(
            {
                "_meta": {
                    "iso_weeks": ["2026-W41", "2026-W42"],
                    "params": {"top_k_per_node": 5, "min_n": 20, "min_npmi_exclusive": 0.1},
                    "edges_per_week": [1, 2],
                },
                "nodes": [{"id": f"n{i}", "importance": [0.5, 0.5]} for i in range(4)],
                "edges": {"source": [0, 0, 1], "target": [1, 1, 2], "week": [0, 1, 1]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    monkeypatch.setattr(tools, "profile", lambda: "full")
    return views


@pytest.mark.unit
def test_graph_facts_come_from_the_view_metadata(view):
    out = tools.get_graph_facts("2026-W41")
    assert out["available"] and out["week"] == "2026-W41"
    assert (out["conexiones_por_tema"], out["min_coapariciones"], out["npmi_mayor_que"]) == (
        5,
        20,
        0.1,
    )
    assert out["temas_semana"] == 2 and out["conexiones_semana"] == 1  # drawn nodes, not all
    latest = tools.get_graph_facts()
    assert latest["week"] == "2026-W42" and latest["temas_semana"] == 3
    assert latest["conexiones_semana"] == 2


@pytest.mark.unit
def test_graph_facts_are_unavailable_without_the_view(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    monkeypatch.setattr(tools, "profile", lambda: "full")
    assert tools.get_graph_facts()["available"] is False


def _turn(*results):
    turn = runtime.Turn("t")
    for name, result in results:
        turn.tool_results.append({"source": 0, "tool": name, "args": {}, "result": result})
    return turn


VIEW = {
    "available": True,
    "week": "2026-W42",
    "conexiones_por_tema": 5,
    "min_coapariciones": 20,
    "npmi_mayor_que": 0.1,
    "temas_semana": 930,
    "conexiones_semana": 3463,
}
RING = {
    "available": True,
    "week": "2026-W42",
    "criterios": tools.ring_criteria(10),
    "rows": [{"neighbor": "org:x", "n": 29, "npmi": 0.875}] * 10,
}


@pytest.mark.unit
def test_the_line_cites_the_real_values_and_the_auditor_traces_them():
    turn = _turn(("get_graph_facts", VIEW))
    line = runtime.graph_facts_line(turn, None)
    assert "5 conexiones" in line and "20 co-menciones" in line and "NPMI mayor que 0,1" in line
    assert "930 temas y 3463 conexiones" in line
    assert runtime.untraced_numbers(line, turn.tool_results, "") == []
    # an invented threshold next to it is still caught
    assert runtime.untraced_numbers(line + " Con nPMI > 0.85.", turn.tool_results, "") == ["0.85"]

    turn = _turn(("get_context_1hop", RING))
    line = runtime.graph_facts_line(turn, "org:google")
    assert "20 vecinos" in line and "3 co-menciones" in line and "se muestran 10" in line
    assert runtime.untraced_numbers(line, turn.tool_results, "") == []
    assert runtime.graph_facts_line(_turn(), None) == ""


class ScriptedChat:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools_):
        self.calls.append(messages)
        return Reply(content="El grafo muestra los temas de la semana.", model="scripted")


@pytest.mark.unit
def test_a_graph_question_gets_the_line_and_the_model_is_told_not_to_add_thresholds(
    view, monkeypatch
):
    monkeypatch.setenv("RADAR_PROFILE", "dev")  # data from the dev slice, view from the fixture
    model = ScriptedChat()
    response = runtime.run_turn("Muéstrame el grafo de la semana", model=model)
    answer = response["answer_es"]
    assert (
        answer.startswith("Cómo se arma el grafo (2026-W42)") or "Cómo se arma el grafo" in answer
    )
    assert "NPMI mayor que 0,1" in answer and "⚠️" not in answer
    master = [m for m in model.calls if m[0]["content"].startswith("Eres el Maestro de Medios")]
    assert "no menciones otros umbrales" in master[-1][1]["content"]
