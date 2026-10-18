"""The 1-hop ring of the AI radar's topics (``ai:<id>``) from ``edges_ai_weekly``."""

from datetime import date

import polars as pl
import pytest

pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from graph.build import ai_edges, build_ai_ring, with_ai_ring
from graph.context import MIN_N, MIN_NPMI, context_1hop

pytestmark = pytest.mark.unit

WK = date(2026, 10, 12)
HUB = "ai:infra:nvidia"
TOPICS = [f"ai:tech:t{i:02d}" for i in range(12)]


def _edges() -> pl.DataFrame:
    """One week: a hub tied heavily to every topic, a chain of real pairs, and pairs that fail
    the n or NPMI floor; the same pairs repeated in the spa bucket (never used)."""
    rows = [(HUB, t, 400, 0.5) for t in TOPICS]
    rows += [(TOPICS[i], TOPICS[i + 1], 10, 0.3) for i in range(len(TOPICS) - 1)]
    rows += [(TOPICS[0], TOPICS[5], 2, 0.6), (TOPICS[0], TOPICS[7], 9, 0.05)]
    frames = []
    for bucket in ("all", "spa"):
        frames.append(
            pl.DataFrame(
                {
                    "wk": [WK] * len(rows),
                    "lang_bucket": [bucket] * len(rows),
                    "x": [min(a, b) for a, b, _, _ in rows],
                    "y": [max(a, b) for a, b, _, _ in rows],
                    "n": [n for *_, n, _ in rows],
                    "n_src": [1] * len(rows),
                    "nx": [1000] * len(rows),
                    "ny": [1000] * len(rows),
                    "n_docs": [5000] * len(rows),
                    "npmi": [v for *_, v in rows],
                }
            )
        )
    return pl.concat(frames)


def test_only_the_all_language_bucket_feeds_the_ring():
    edges = ai_edges(_edges()).collect()
    assert "lang_bucket" not in edges.columns
    assert edges.height == _edges().filter(pl.col("lang_bucket") == "all").height


def test_ai_ring_follows_the_v02_rule():
    ring = build_ai_ring(_edges())
    assert ring["topic_id"].str.starts_with("ai:").all()
    assert (ring["n"] >= MIN_N).all() and (ring["npmi"] > MIN_NPMI).all()
    assert HUB not in ring["neighbor"].to_list()  # the week's hub is dropped
    first = ring.filter(pl.col("topic_id") == TOPICS[0])["neighbor"].to_list()
    assert first == [TOPICS[1]]  # n = 2 and NPMI 0.05 pairs are cut


def test_v02_build_never_rings_ai_topics():
    week = ai_edges(_edges()).collect()
    metrics = pl.DataFrame(
        {"wk": [WK], "entity_id": [HUB], "is_hub": [True]},
    )
    assert context_1hop(week, metrics).height == 0  # default prefixes: org and thm only


def test_ai_rows_are_replaced_and_v02_rows_kept():
    old = build_ai_ring(_edges())
    v02 = old.head(2).with_columns(topic_id=pl.lit("org:acme"), neighbor=pl.lit("thm:X"))
    stale = old.head(1).with_columns(neighbor=pl.lit("ai:tech:gone"))
    merged = with_ai_ring(pl.concat([v02, stale]), old)
    assert merged.filter(pl.col("topic_id") == "org:acme").height == 2
    assert "ai:tech:gone" not in merged["neighbor"].to_list()
    assert merged.filter(pl.col("topic_id").str.starts_with("ai:")).height == old.height
