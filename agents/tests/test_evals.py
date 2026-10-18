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


def test_entity_resolved_counts_false_positives():
    def turn(entity):
        step = {"agent": "media_master", "action": "delegate", "arguments": {"entity": entity}}
        return _resp(trace=[step])

    assert ev.entity_resolved(turn("org:nvidia"), {"entity": "org:nvidia"})["score"] == 1
    assert ev.entity_resolved(turn(None), {"entity": None})["score"] == 1
    assert ev.entity_resolved(_resp(), {"entity": None})["score"] == 1  # out of scope: no route
    assert ev.entity_resolved(turn("org:a co"), {"entity": None})["score"] == 0  # false positive
    assert ev.entity_resolved(turn("org:openai"), {"entity": "org:nvidia"})["score"] == 0
    assert ev.entity_resolved(turn(None), {"entity": "org:nvidia"})["score"] == 0


def test_summarize_reports_mean_and_repetition_spread():
    rows = [
        {"qid": "q01", "scores": {"usefulness": 0.5, "grounding": 1}},
        {"qid": "q02", "scores": {"usefulness": 1.0, "grounding": 1}},
        {"qid": "q01", "scores": {"usefulness": 0.0, "grounding": 0}},
        {"qid": "q02", "scores": {"usefulness": 0.5, "grounding": None}},
    ]
    s = ev.summarize(rows, repetitions=2)
    assert s["usefulness"] == {"mean": 0.5, "rep_min": 0.25, "rep_max": 0.75, "n": 4}
    assert s["grounding"]["n"] == 3 and s["grounding"]["rep_min"] == 0.0
    assert s["latency_s"]["mean"] is None


def test_judge_v2_sees_the_tool_data_and_today(monkeypatch):
    seen = {}

    class Judge:
        def chat(self, messages, tools):
            seen["system"], seen["user"] = messages[0]["content"], messages[1]["content"]
            from agents.llm import Reply

            return Reply(content='{"score": 4, "reason": "clara"}', model="judge")

    monkeypatch.setattr(ev, "_judge", lambda: Judge())
    step = {"agent": "scout", "action": "tool_result", "tool": "get_cost_ledger",
            "result_summary": '{"billed_gb": 376.83}'}  # fmt: skip
    out = ev.usefulness_v2(
        {"question": "¿Cuánto ha costado?"}, _resp(answer_es="377 GB", trace=[step])
    )
    assert out == {"key": "usefulness_v2", "score": 0.75, "comment": "clara"}
    assert "get_cost_ledger" in seen["user"] and "376.83" in seen["user"]
    assert "Hoy es 20" in seen["system"] and "no juzgues si los números" in seen["system"]
    assert "ninguna herramienta" in ev.tool_data(_resp())
    assert len(ev.tool_data(_resp(trace=[step] * 500))) <= ev.TOOL_DATA_CHARS
