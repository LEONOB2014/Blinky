"""Agent tools on the real dev slice (RADAR_PROFILE=dev, no network)."""

import pytest

from agents import tools


@pytest.fixture(autouse=True)
def _dev(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")


@pytest.mark.unit
def test_trends_mark_the_fastest_growing_subtopic():
    result = tools.list_subtopic_trends("2026-W41")
    subtopics = [
        r for r in result["rows"] if r["topic"] != "ai_all" and r["growth_7d_log"] is not None
    ]
    assert result["fastest_growing_subtopic"] == subtopics[0]["topic"]
    growth = [r["growth_7d_log"] for r in subtopics]
    assert growth == sorted(growth, reverse=True)
    assert all("label_es" in r for r in result["rows"])


@pytest.mark.unit
def test_top10_without_scores_says_so_and_returns_real_trends():
    result = tools.get_top10()
    assert result["available"] is False
    assert result["fallback_subtopic_trends"]["rows"]


@pytest.mark.unit
def test_unparseable_week_resolves_to_latest_week_with_data():
    assert tools.week_bounds("this_week")[0] == tools.week_bounds(None)[0]


@pytest.mark.unit
def test_view_commands_are_validated_against_the_contract():
    ok = tools.update_view("story", "Vecinos de Google", focus_topic="org:google")
    assert ok["available"] and ok["view_command"]["view"] == "story"
    assert tools.update_view("map", "x")["available"] is False


@pytest.mark.unit
def test_context_ring_drops_hubs_and_weak_edges():
    result = tools.get_context_1hop("org:google", "2026-W41")
    assert result["rows"], "google has neighbours in the dev slice"
    assert all(r["npmi"] > 0.1 and r["n"] >= 3 for r in result["rows"])
    assert "org:united states" not in {r["neighbor"] for r in result["rows"]}  # the week's top hub


@pytest.mark.unit
def test_graph_nodes_never_include_persons():
    nodes = tools.graph_nodes("2026-W41")
    assert nodes and not any(n.startswith("per:") for n in nodes)


@pytest.mark.unit
def test_unknown_tool_and_bad_arguments_come_back_as_data():
    assert tools.call("nope", {})["available"] is False
    assert tools.call("get_topic_series", "{not json")["available"] is False


def test_names_resolve_to_graph_ids():
    # real dev-slice ids: a plain name, a capitalised name, and an id that passes through
    known = set(tools.known_topics())
    assert "org:google" in known
    assert tools.resolve_topic("Google") == "org:google"
    assert tools.resolve_topic("org:google") == "org:google"
    assert tools.resolve_topic("regulation_policy") == "regulation_policy"
    assert tools.resolve_topic("per:anyone") == "per:anyone"


def test_entity_series_reads_topic_daily():
    out = tools.get_topic_series("Google")
    assert out["available"] and out["topic"] == "org:google"
    assert all(r["articles"] > 0 for r in out["rows"])


def test_prefix_resolution_only_adds_a_company_suffix(monkeypatch):
    topics = ("org:openai inc", "org:altman to microsoft corp", "org:google")
    monkeypatch.setattr(tools, "known_topics", lambda: topics)
    assert tools.resolve_topic("OpenAI") == "org:openai inc"
    assert tools.resolve_topic("Altman") == "Altman"


def test_human_formatted_fields():
    from agents import tools

    assert tools.pct(0.6455) == "65%" and tools.pct(3.648, signed=True) == "+365%"
    assert tools.tone_word(-3.4) == "negativo" and tools.tone_word(0.2) == "neutral"
    assert tools.human_name("org:openai inc") == "openai inc"
    assert tools.human_name("chips_infra") == "Chips e infraestructura"
    row = {"topic_id": "org:x", "label_es": "X Corp", "decision": "preparar", "stage": "semilla",
           "emergence_pct": 92.39, "saturation": 0.0, "audience_fit": 0.6455,
           "window": {"days_left": 12}}  # fmt: skip
    s = tools._score_summary(row)
    assert s.startswith("X Corp: Preparar") and "percentil 92" in s and "65%" in s
    assert "12 días" in s and "audience_fit" not in s


def test_cost_and_freshness_carry_plain_summaries():
    from agents import tools

    cost = tools.get_cost_ledger()
    assert "GB procesados" in cost["resumen_es"] and cost["list_price_usd_estimate"] >= 0
    fresh = tools.get_freshness()
    assert "resumen_es" in fresh and set(fresh["dias_desde_ultimo_dato"]) == set(fresh["newest"])
