"""AI lexicon graph: labels, family, stance, and a separated critic camp."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from graph.export_views import (
    FAMILY_PALETTE,
    SPACE_PAD,
    SPACE_SIZE,
    _neighbors_from_edges,
    _seat_critics,
    export_temporal,
    load_lexicon,
)

pytestmark = pytest.mark.unit

W1 = date(2026, 10, 5)
W2 = date(2026, 10, 12)
OPENAI = "ai:lab:openai"
GPT = "ai:model:gpt"
ACT = "ai:policy:eu-ai-act"
RISK = "ai:risk:existential"


def _lexicon_yaml(path: Path) -> Path:
    path.write_text(
        """
version: 1
families:
  labs: Laboratorios
  models: Modelos
  policy: Política
  risk: Riesgo
entries:
  - id: lab:openai
    label_es: OpenAI
    family: labs
    stance: promoter
  - id: model:gpt
    label_es: GPT
    family: models
    stance: promoter
  - id: ai:policy:eu-ai-act
    label_es: Ley de IA de la UE
    family: policy
    stance: critic
  - id: risk:existential
    label_es: Riesgo existencial
    family: risk
    stance: critic
  - id: culture:meme
    label_es: Meme
    family: no-such
    stance: hostile
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _edges() -> pl.DataFrame:
    rows = [
        (W1, OPENAI, GPT, 30, 0.40),
        (W1, OPENAI, ACT, 24, 0.30),
        (W1, ACT, RISK, 20, 0.50),
        (W1, GPT, RISK, 22, 0.28),
        (W1, "org:giant", "org:other", 400, 0.80),
        (W2, OPENAI, GPT, 30, 0.40),
        (W2, OPENAI, ACT, 24, 0.30),
        (W2, ACT, RISK, 40, 0.55),
        (W2, GPT, RISK, 22, 0.28),
        (W2, "org:giant", "org:other", 400, 0.80),
    ]
    return pl.DataFrame(
        rows,
        schema={"wk": pl.Date, "x": pl.String, "y": pl.String, "n": pl.Int64, "npmi": pl.Float64},
        orient="row",
    )


def _empty_metrics() -> pl.DataFrame:
    return pl.DataFrame(schema={"wk": pl.Date, "entity_id": pl.String})


def test_load_lexicon_prefixes_ids_and_normalises_stance(tmp_path: Path):
    lex = load_lexicon(_lexicon_yaml(tmp_path / "ai_lexicon.yaml"))
    assert lex[OPENAI]["label_es"] == "OpenAI"
    assert lex[OPENAI]["family"] == "labs"
    assert lex[OPENAI]["family_es"] == "Laboratorios"
    assert lex[OPENAI]["stance"] == "promoter"
    assert lex[ACT]["label_es"] == "Ley de IA de la UE"
    assert lex[ACT]["stance"] == "critic"
    assert lex["ai:culture:meme"]["stance"] == "neutral"
    assert lex["ai:culture:meme"]["family_es"] == "no-such"
    assert load_lexicon(tmp_path / "missing.yaml") == {}


def test_seat_critics_puts_the_camp_on_the_left():
    coords = [(1000.0, 800.0), (3000.0, 900.0), (1200.0, 2000.0), (2800.0, 2500.0)]
    stances = ["critic", "promoter", "critic", "neutral"]
    seated = _seat_critics(coords, stances)
    assert _seat_critics(coords, ["critic", "promoter", None, None]) == coords
    left = SPACE_PAD + 0.28 * (SPACE_SIZE - 2.0 * SPACE_PAD)
    critic_x = [seated[i][0] for i, stance in enumerate(stances) if stance == "critic"]
    other_x = [seated[i][0] for i, stance in enumerate(stances) if stance != "critic"]
    assert max(critic_x) < left <= min(other_x)
    assert all(SPACE_PAD <= x <= SPACE_SIZE - SPACE_PAD for x, _y in seated)


def test_ai_export_keeps_computed_properties_and_separates_critics(tmp_path: Path):
    lex = load_lexicon(_lexicon_yaml(tmp_path / "ai_lexicon.yaml"))
    edges = _edges()
    metrics = _empty_metrics()
    tones = pl.DataFrame(
        {
            "topic_id": [RISK, OPENAI],
            "dt": [W2, W2],
            "mean_tone": [-3.5, 2.0],
            "n_articles": [12, 9],
        }
    )
    out = export_temporal(
        edges,
        metrics,
        lexicon=lex,
        ai_only=True,
        topic_daily=tones,
        max_nodes=10,
        min_n=1,
        min_npmi=0.05,
        top_k=5,
    )
    nodes = {n["id"]: n for n in out["nodes"]}
    assert set(nodes) == {OPENAI, GPT, ACT, RISK}
    assert nodes[OPENAI]["label_es"] == "OpenAI"
    assert nodes[OPENAI]["family"] == "labs"
    assert nodes[OPENAI]["family_es"] == "Laboratorios"
    assert nodes[OPENAI]["stance"] == "promoter"
    assert nodes[ACT]["stance"] == "critic"
    assert nodes[ACT]["show_label"] is True
    assert nodes[RISK]["show_label"] is True
    critic_x = max(nodes[ACT]["x"], nodes[RISK]["x"])
    other_x = min(nodes[OPENAI]["x"], nodes[GPT]["x"])
    assert critic_x < other_x
    assert out["_meta"]["default_color_by"] == "family"
    assert out["_meta"]["params"]["ai_only"] is True
    assert any(item["label_es"] == "Críticos" for item in out["_meta"]["stance_legend"])

    edges_out = out["edges"]
    assert edges_out["npmi"]
    assert min(edges_out["npmi"]) > 0.05
    assert set(edges_out["edge_state"]) <= {"new", "growing", "persisting", "fading"}
    assert "growing" in edges_out["edge_state"]
    n_weeks = len(out["_meta"]["weeks"])
    for node in nodes.values():
        assert len(node["betweenness"]) == n_weeks
        assert len(node["momentum"]) == n_weeks
        assert len(node["community_week"]) == n_weeks
        assert len(node["importance"]) == n_weeks
        assert any(value is not None for value in node["betweenness"])
        assert any(value is not None for value in node["community_week"])
    assert nodes[RISK]["tone"][out["_meta"]["weeks"].index(W2.isoformat())] == pytest.approx(-3.5)
    assert nodes[OPENAI]["tone"][out["_meta"]["weeks"].index(W2.isoformat())] == pytest.approx(2.0)

    mixed = export_temporal(
        edges,
        metrics,
        lexicon=lex,
        ai_only=False,
        max_nodes=10,
        min_n=1,
        min_npmi=0.05,
        top_k=5,
    )
    mixed_ids = {n["id"] for n in mixed["nodes"]}
    assert "org:giant" in mixed_ids
    assert mixed["_meta"]["default_color_by"] == "decision"


def test_language_buckets_do_not_double_count():
    """``edges_ai_weekly`` stores eng/spa/por/other plus the ``all`` total."""
    edges = pl.DataFrame(
        {
            "wk": [W1, W1, W2, W2],
            "lang_bucket": ["all", "eng", "all", "eng"],
            "x": [OPENAI, OPENAI, OPENAI, OPENAI],
            "y": [GPT, GPT, GPT, GPT],
            "n": [30, 30, 30, 30],
            "npmi": [0.4, 0.4, 0.4, 0.4],
        }
    )
    out = export_temporal(
        edges,
        _empty_metrics(),
        ai_only=True,
        max_nodes=10,
        min_n=1,
        min_npmi=0.05,
        top_k=5,
    )
    assert out["edges"]["n"] == [30, 30]
    assert out["_meta"]["n_edges"] == 2


def test_shipped_lexicon_families_have_colours():
    lex = load_lexicon()
    assert len(lex) == 117
    assert set(lex) >= {"ai:lab:openai", "ai:policy:eu_ai_act", "ai:critic:pause_ai"}
    families = {entry["family"] for entry in lex.values()}
    assert families <= set(FAMILY_PALETTE)
    for entry in lex.values():
        assert entry["family_es"] == FAMILY_PALETTE[entry["family"]][1]
        assert entry["stance"] in {"promoter", "critic", "neutral"}
    critics = [topic for topic, entry in lex.items() if entry["stance"] == "critic"]
    assert len(critics) >= 15


def test_story_neighbors_come_from_ai_edges_when_the_ring_is_empty():
    edges = pl.DataFrame(
        {
            "wk": [W1, W1, W1],
            "lang_bucket": ["all", "eng", "all"],
            "x": [OPENAI, OPENAI, OPENAI],
            "y": [GPT, GPT, ACT],
            "n": [12, 99, 4],
            "npmi": [0.2, 0.9, 0.5],
        }
    )
    nbrs = _neighbors_from_edges(edges, OPENAI, W1)
    assert nbrs["neighbor"].to_list() == [ACT, GPT]
    assert nbrs["n"].to_list() == [4, 12]
