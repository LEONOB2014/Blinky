from agents.evals import run_evals as ev


def _resp(**kw):
    base = {
        "answer_es": "",
        "decision_cards": [],
        "view_commands": [],
        "trace": [],
        "latency_ms": 1200,
    }
    return base | kw


def test_question_set_is_frozen_and_well_formed():
    spec = ev.load_questions()
    ids = [q["id"] for q in spec["questions"]]
    assert spec["version"] == 1 and len(ids) == 25 and len(set(ids)) == 25
    assert all({"question", "kind", "agents", "decision"} <= q.keys() for q in spec["questions"])


def test_grounding_reads_the_auditor_veto():
    veto = {"agent": "auditor", "action": "veto", "result_summary": "números sin fuente: 7"}
    assert ev.grounding(_resp(trace=[veto]))["score"] == 0
    assert ev.grounding(_resp())["score"] == 1


def test_decision_invented_without_cards_fails():
    out = _resp(answer_es="Decisión: publicar ahora")
    assert ev.decision_faithful(out, {"decision": False})["score"] == 0
    card = {"decision": "preparar"}
    assert ev.decision_faithful(_resp(decision_cards=[card]), {"decision": True})["score"] == 1


def test_routing_and_entity():
    step = {"agent": "cartographer", "action": "tool_call", "arguments": {"entity": "org:nvidia"}}
    out = _resp(trace=[step])
    assert ev.routing(out, {"agents": ["cartographer", "signal_analyst"]})["score"] == 0.5
    assert ev.entity_resolved(out, {"entity": "org:nvidia"})["score"] == 1
    assert ev.entity_resolved(out, {"entity": None})["score"] is None
