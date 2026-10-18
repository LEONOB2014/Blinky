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


@pytest.mark.unit
def test_context_ring_states_the_thresholds_it_used():
    result = tools.get_context_1hop("org:google", "2026-W41", k=5)
    crit = result["criterios"]
    assert crit["n_minimo_coapariciones"] == 3 and crit["npmi_mayor_que"] == 0.1
    ring = result["source"] == "topic_context_1hop"  # the dev slice falls back to edges_weekly
    assert crit["top_por_tema"] == (20 if ring else None) and crit["mostrados"] == 5
    assert "1%" in crit["hubs"] and crit["personas"] == "excluidas"


@pytest.mark.unit
def test_ring_thresholds_match_the_graph_code():
    from graph import context

    assert (tools.RING_MIN_N, tools.RING_MIN_NPMI, tools.RING_TOP_K) == (
        context.MIN_N,
        context.MIN_NPMI,
        context.TOP_K,
    )
    metrics = (tools.REPO_ROOT / "graph" / "metrics.py").read_text(encoding="utf-8")
    assert f"HUB_SHARE = {tools.RING_HUB_SHARE}" in metrics


@pytest.mark.unit
def test_cost_ledger_gives_free_tier_share_estimated_usd_and_jev(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "bq_ledger.csv").write_text(
        "ts_utc,job_id,script,workstream,dry_run_bytes,billed_bytes,cap_gib,note\n"
        f"2026-09-30T23:00:00Z,a,s.sql,WS1,0,{2**40},50,old month\n"
        f"2026-10-01T01:00:00Z,b,s.sql,WS1,0,{2**39},50,\n"
        f"2026-10-02T01:00:00Z,c,s.sql,WS1,0,{2**40},50,\n",
        encoding="utf-8",
    )
    (reports / "jev_ledger.csv").write_text(
        "ts_utc,model,input_tokens,cost_usd,latency_ms\n"
        "2026-10-18T04:35:30Z,jev,1053,0.00004423,867\n"
        "2026-10-18T04:35:31Z,jev,1050,0.00004410,874\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tools, "REPO_ROOT", tmp_path)
    bq = tools.get_cost_ledger()["bigquery"]
    assert bq["jobs"] == 3 and bq["billed_tib"] == 2.5
    assert bq["mes"] == "2026-10" and bq["billed_tib_mes"] == 1.5
    assert bq["cuota_gratuita_usada"] == 1.5
    assert bq["costo_usd_con_cuota_gratuita"] == 3.12  # 0.5 TiB over the free tier x 6.25
    assert bq["costo_usd_sin_cuota_gratuita"] == 15.62  # 2.5 TiB x 6.25
    assert bq["precio_usd_por_tib"] == 6.25 and "bigquery/pricing" in bq["fuente_precio"]
    assert "estimado" in bq and "medido" in bq
    jev = tools.get_cost_ledger()["jev"]
    assert jev == {
        "available": True,
        "medido": "suma de cost_usd en reports/jev_ledger.csv",
        "llamadas": 2,
        "costo_usd": 0.0001,
    }
    (reports / "jev_ledger.csv").unlink()
    assert tools.get_cost_ledger()["jev"]["available"] is False


@pytest.mark.unit
def test_the_ai_source_switches_tables_and_falls_back_to_the_shared_one(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "full")
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    (tmp_path / "gold").mkdir()
    assert tools.gold("topic_scores_weekly").name == "topic_scores_weekly.parquet"
    monkeypatch.setenv("RADAR_SOURCE", "ai")
    # no AI variant yet: the shared table (S13/S14 rows for ai: topics may live there)
    assert tools.gold("topic_sources_weekly").name == "topic_sources_weekly.parquet"
    (tmp_path / "gold" / "topic_ai_scores_weekly.parquet").write_bytes(b"")
    assert tools.gold("topic_scores_weekly").name == "topic_ai_scores_weekly.parquet"
    # briefs are written under the AI name, so v0.2's briefs are never overwritten
    assert tools.gold("topic_briefs_weekly", write=True).name == "topic_ai_briefs_weekly.parquet"
    assert tools.gold("edges_weekly").name == "edges_weekly.parquet"  # not switched
