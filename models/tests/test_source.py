"""The AI lexicon source (models/source.py): universe, family groups, new-neighbour rate, gate and
the pageview label. A small lexicon in tmp_path stands in for contracts/ai_lexicon.yaml."""

import datetime as dt

import polars as pl
import pytest

from models import backtest, build_scores, source, universe

pytestmark = pytest.mark.unit

LEXICON = """
version: 1
families: {labs: Laboratorios, biz: Negocio e inversión, tech: Técnicas}
entries:
  - id: lab:openai
    label_es: OpenAI
    family: labs
    stance: promoter
    patterns: ['\\bopenai\\b']
    wikipedia: {es: OpenAI, pt: OpenAI}
  - id: biz:ai_funding
    label_es: Inversión en IA
    family: biz
    stance: neutral
    patterns: ['ai funding']
  - id: tech:agents
    label_es: Agentes de IA
    family: tech
    stance: neutral
    patterns: ['\\bai agents?\\b']
    wikipedia: {es: Agente inteligente}
"""


@pytest.fixture
def ai(tmp_path, monkeypatch):
    path = tmp_path / "ai_lexicon.yaml"
    path.write_text(LEXICON, encoding="utf-8")
    monkeypatch.setenv("RADAR_AI_LEXICON", str(path))
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path / "lake"))
    yield source.use("ai")
    source._active.clear()


def test_the_default_source_is_gdelt_and_unknown_sources_fail():
    source._active.clear()
    assert source.current().name == "gdelt" and source.current().topic_table == "topic_daily"
    assert universe.min_articles_week() == universe.MIN_ARTICLES_WEEK == 20
    with pytest.raises(ValueError, match="unknown source"):
        source.use("bing")


def test_the_ai_universe_is_every_ai_topic_with_one_article(ai):
    ids = pl.DataFrame({"topic_id": ["ai:lab:openai", "org:kroger", "thm:TECH_AI", "ai:x:y"]})
    assert ids.filter(universe.in_universe())["topic_id"].to_list() == ["ai:lab:openai", "ai:x:y"]
    assert universe.min_articles_week() == 20  # taxonomy floor, not 1
    assert ai.scores_table == "topic_ai_scores_weekly" and ai.report == "backtest_ai.md"


CONTEXT_ENTRY = """
  - id: biz:ai_smes
    label_es: IA para pymes
    family: biz
    stance: neutral
    ranked: false
    patterns: ['\\bpymes?\\b']
"""


@pytest.fixture
def ai_with_context(tmp_path, monkeypatch):
    path = tmp_path / "ai_lexicon.yaml"
    path.write_text(LEXICON + CONTEXT_ENTRY, encoding="utf-8")
    monkeypatch.setenv("RADAR_AI_LEXICON", str(path))
    monkeypatch.setenv("RADAR_LAKE", str(tmp_path / "lake"))
    yield source.use("ai")
    source._active.clear()


def test_context_only_entries_are_never_ranked(ai_with_context):
    assert source.unranked_ids() == {"ai:biz:ai_smes"}
    ids = pl.DataFrame({"topic_id": ["ai:lab:openai", "ai:biz:ai_smes"]})
    assert ids.filter(universe.in_universe())["topic_id"].to_list() == ["ai:lab:openai"]
    assert "ai:biz:ai_smes" in source.entries()["topic_id"].to_list()  # still a lexicon topic


def test_a_link_to_a_context_entry_does_not_make_a_topic_new(ai_with_context):
    w = [dt.date(2026, 9, 7) + dt.timedelta(days=7 * k) for k in range(5)]
    rows = [(w[k], "lab:openai", "tech:agents", "all", 5) for k in range(5)]
    rows.append((w[4], "lab:openai", "biz:ai_smes", "all", 9))  # new, but context only
    edges = pl.DataFrame(rows, schema=["wk", "x", "y", "lang_bucket", "n"], orient="row")
    got = {
        (r["unit_id"], r["week"]): r["new_nbr_rate"]
        for r in source.ai_new_nbr_rate(edges).iter_rows(named=True)
    }
    assert got[("ai:lab:openai", "2026-W41")] == 0.0
    assert not any(u == "ai:biz:ai_smes" for u, _ in got)


def test_labels_titles_and_family_groups_come_from_the_lexicon(ai):
    labels, mapped = build_scores.labels_and_mapped()
    assert labels["ai:lab:openai"] == "OpenAI" and labels["ai:tech:agents"] == "Agentes de IA"
    assert mapped == {"ai:lab:openai", "ai:tech:agents"}  # biz:ai_funding has no page
    panel = pl.DataFrame(
        {"unit_id": ["ai:lab:openai", "ai:biz:ai_funding", "ai_all"], "week": ["2026-W42"] * 3}
    )
    mem = source.family_membership(panel).sort("unit_id")
    assert mem["unit_id"].to_list() == ["ai:biz:ai_funding", "ai:lab:openai"]  # ai_all: no row
    assert mem["primary_subtopic"].to_list() == ["biz", "labs"]
    assert mem["fit_subtopic"].to_list() == [1.0, 0.0]
    assert build_scores._wikidata() is None  # no Wikidata step for lexicon topics


def test_new_neighbour_rate_follows_ws3s_rule_on_the_ai_edges():
    w = [dt.date(2026, 9, 7) + dt.timedelta(days=7 * k) for k in range(6)]
    rows = []
    for k in range(4):  # weeks 0-3: openai-agents, every week, in two language buckets
        rows += [
            (w[k], "lab:openai", "tech:agents", "eng", 2),
            (w[k], "lab:openai", "tech:agents", "spa", 2),
        ]
    rows += [
        (w[4], "lab:openai", "tech:agents", "eng", 5),  # old neighbour
        (w[4], "lab:openai", "biz:ai_funding", "eng", 3),  # new neighbour
        (w[4], "lab:openai", "infra:gpu", "eng", 2),  # n < 3: not an edge
        (w[5], "lab:openai", "tech:agents", "eng", 4),
    ]
    edges = pl.DataFrame(rows, schema=["wk", "x", "y", "lang_bucket", "n"], orient="row")
    rate = source.ai_new_nbr_rate(edges)
    got = {(r["unit_id"], r["week"]): r["new_nbr_rate"] for r in rate.iter_rows(named=True)}
    assert got[("ai:lab:openai", "2026-W41")] == 0.5  # 1 of its 2 neighbours is new
    assert got[("ai:biz:ai_funding", "2026-W41")] == 1.0
    assert got[("ai:lab:openai", "2026-W37")] is None  # look-back not complete
    assert ("ai:infra:gpu", "2026-W41") not in got
    assert all(u.startswith("ai:") for u in rate["unit_id"])
    # S16's "all" bucket is used alone: summing it with the per-language rows would double n
    totals = (
        edges.group_by("wk", "x", "y")
        .agg(pl.col("n").sum())
        .with_columns(pl.lit("all").alias("lang_bucket"))
    )
    with_all = pl.concat([edges, totals.select(edges.columns)])
    key = ["unit_id", "week"]
    assert source.ai_new_nbr_rate(with_all).sort(key).equals(rate.sort(key))


def test_the_new_neighbour_look_back_matches_ws3():
    metrics = pytest.importorskip("graph.metrics")  # needs the graph extra (igraph)
    assert source.NEW_NBR_WEEKS == metrics.NEW_NBR_WEEKS


def test_the_gate_holds_by_construction_and_the_syndication_guard_stays(ai, monkeypatch):
    scored = pl.DataFrame(
        {
            "unit_id": ["ai:lab:openai", "ai:tech:agents"],
            "week": ["2026-W42"] * 2,
            "n7raw": [40, 30],
            "priority": [0.5, 0.9],
            "stage": ["emergente", "emergente"],
        }
    )
    own = pl.DataFrame(  # one week of history: GDELT topics would fail the gate
        {
            "unit_id": ["ai:lab:openai", "ai:tech:agents"],
            "group": ["all", "all"],
            "dt": [dt.date(2026, 10, 12)] * 2,
            "n": [40, 30],
        }
    )
    monkeypatch.setattr(
        build_scores,
        "sources",
        lambda: pl.DataFrame(
            {
                "unit_id": ["ai:tech:agents"],
                "week": ["2026-W42"],
                "n_sources": [2],  # one-outlet week: the guard holds it back
                "top_source_share": [0.9],
                "top_theme_pattern_share": [0.2],
            }
        ),
    )
    out = build_scores.gate(scored, own).sort("rank")
    assert out["unit_id"].to_list() == ["ai:lab:openai", "ai:tech:agents"]
    assert out["known"].to_list() == [True, True]
    assert out["headline_ok"].to_list() == [True, False]
    assert "solo 2 fuentes" in out["seed_reason"][1]


def test_the_ai_pageview_label_reads_the_lexicon_titles(ai, tmp_path):
    gold = tmp_path / "lake" / "gold"
    gold.mkdir(parents=True)
    pl.DataFrame(
        {
            "topic_id": ["ai:lab:openai"] * 3,
            "project": ["es.wikipedia", "pt.wikipedia", "en.wikipedia"],
            "article": ["OpenAI"] * 3,
            "dt": [dt.date(2026, 10, 12)] * 3,
            "views": [100, 20, 999],
        }
    ).write_parquet(gold / "wiki_pageviews_ai_daily.parquet")
    monkeypatch_profile = pytest.MonkeyPatch()
    monkeypatch_profile.setenv("RADAR_PROFILE", "full")
    try:
        daily, mapped = backtest.ai_pageview_label()
    finally:
        monkeypatch_profile.undo()
    assert mapped == {"ai:lab:openai", "ai:tech:agents"}
    assert daily.to_dicts() == [
        {"unit_id": "ai:lab:openai", "dt": dt.date(2026, 10, 12), "value": 120.0}
    ]  # es + pt only
    assert backtest.label_title("pageviews").endswith("(the AI lexicon's page titles)")
