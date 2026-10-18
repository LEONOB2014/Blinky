"""Graph-view exports on the committed dev slice (RADAR_PROFILE=dev): pruning and no persons."""

from collections import defaultdict
from datetime import date

import polars as pl
import pytest

pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from graph.build import build
from graph.export_views import (
    PERSON_PREFIX,
    SPACE_PAD,
    SPACE_SIZE,
    default_story_target,
    export_story,
    export_temporal,
    iso_week,
    story_filename,
    top_story_targets,
    week_monday,
)
from radar.fixtures import DEV_DIR

pytestmark = pytest.mark.unit

MAX_NODES, MIN_N, MIN_NPMI = 50, 5, 0.1


@pytest.fixture(scope="module")
def dev():
    # The dev slice has no person nodes, so the busiest org is relabelled as a person: the guard
    # must then actually remove something.
    edges = pl.read_parquet(DEV_DIR / "edges_weekly.parquet")
    deg = pl.concat([edges.select(e="x", n="n"), edges.select(e="y", n="n")]).group_by("e").sum()
    busiest = deg.filter(pl.col("e").str.starts_with("org:")).sort("n", descending=True)["e"][0]
    person = PERSON_PREFIX + "relabelled"
    edges = edges.with_columns(
        x=pl.when(pl.col("x") == busiest).then(pl.lit(person)).otherwise("x"),
        y=pl.when(pl.col("y") == busiest).then(pl.lit(person)).otherwise("y"),
    )
    metrics, ring = build(edges)
    return edges, metrics, ring, person


def test_temporal_respects_pruning_and_has_no_persons(dev):
    edges, metrics, _, person = dev
    assert edges.filter((pl.col("x") == person) | (pl.col("y") == person)).height > 0
    out = export_temporal(
        edges,
        metrics,
        max_nodes=MAX_NODES,
        min_n=MIN_N,
        min_npmi=MIN_NPMI,
        top_k=3,
    )
    ids = [n["id"] for n in out["nodes"]]
    assert not any(i.startswith(PERSON_PREFIX) for i in ids)
    assert len(ids) == len(set(ids)) <= MAX_NODES
    for n in out["nodes"]:
        assert SPACE_PAD <= n["x"] <= SPACE_SIZE - SPACE_PAD
        assert SPACE_PAD <= n["y"] <= SPACE_SIZE - SPACE_PAD
        assert isinstance(n["show_label"], bool)
        assert n["label_es"]
    e = out["edges"]
    assert len(e["source"]) == out["_meta"]["n_edges"] == sum(out["_meta"]["edges_per_week"])
    assert min(e["n"]) >= MIN_N and min(e["npmi"]) > MIN_NPMI
    assert max(e["source"] + e["target"]) < len(ids)
    weeks = out["_meta"]["weeks"]
    assert len(weeks) == edges["wk"].n_unique() <= 13  # 8 dev weeks, none filled
    assert all(len(n["pagerank"]) == len(weeks) for n in out["nodes"])
    assert len(out["_meta"]["top_movers_per_week"]) == len(weeks)
    assert out["_meta"]["profile"] == "dev"


def test_temporal_top_k_prunes_edges_per_node_per_week(dev):
    edges, metrics, _, _ = dev
    unpruned = export_temporal(
        edges,
        metrics,
        max_nodes=MAX_NODES,
        min_n=MIN_N,
        min_npmi=MIN_NPMI,
        top_k=0,
    )
    pruned = export_temporal(
        edges,
        metrics,
        max_nodes=MAX_NODES,
        min_n=MIN_N,
        min_npmi=MIN_NPMI,
        top_k=3,
    )
    assert pruned["_meta"]["n_edges"] < unpruned["_meta"]["n_edges"]
    ids = [n["id"] for n in unpruned["nodes"]]

    # Build the exact top-3 incident edges by (npmi DESC, n DESC, other_id ASC) from unpruned
    ue = unpruned["edges"]
    by_wk_node: dict[tuple[int, int], list[tuple[float, int, str, tuple[int, int]]]] = defaultdict(
        list
    )
    for s, t, w, n_val, npmi_val in zip(
        ue["source"], ue["target"], ue["week"], ue["n"], ue["npmi"], strict=True
    ):
        pair = (s, t) if s < t else (t, s)
        by_wk_node[(w, s)].append((-npmi_val, -n_val, ids[t], pair))
        by_wk_node[(w, t)].append((-npmi_val, -n_val, ids[s], pair))

    expected_pairs_by_wk: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for (w, _), inc in by_wk_node.items():
        inc.sort()
        for _, _, _, pair in inc[:3]:
            expected_pairs_by_wk[w].add(pair)

    pe = pruned["edges"]
    actual_pairs_by_wk: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for s, t, w in zip(pe["source"], pe["target"], pe["week"], strict=True):
        actual_pairs_by_wk[w].add((s, t) if s < t else (t, s))

    assert actual_pairs_by_wk == expected_pairs_by_wk


def test_temporal_keeps_the_top_nodes_by_weighted_degree(dev):
    edges, metrics, _, _ = dev
    out = export_temporal(edges, metrics, max_nodes=MAX_NODES, min_n=MIN_N, min_npmi=MIN_NPMI)
    degs = [n["deg_span"] for n in out["nodes"]]
    assert degs == sorted(degs, reverse=True)


def test_story_has_the_ring_its_edges_and_no_persons(dev):
    edges, metrics, ring, person = dev
    wk = ring["wk"].max()
    topic = (
        ring.filter(pl.col("wk") == wk).group_by("topic_id").len().sort("len", descending=True)
    )["topic_id"][0]
    # A person row in the ring input must still be dropped by the export.
    leaked = ring.head(1).with_columns(
        wk=pl.lit(wk), topic_id=pl.lit(topic), neighbor=pl.lit(person), rank=pl.lit(1, pl.Int64)
    )
    story = export_story(edges, pl.concat([leaked, ring]), topic, iso_week(wk))
    keys = [n["key"] for n in story["nodes"]]
    assert keys[0] == topic and not any(k.startswith(PERSON_PREFIX) for k in keys)
    assert all(n["attributes"].get("label_es") for n in story["nodes"])
    assert 1 <= story["_meta"]["n_ring"] <= 20
    assert all(e["source"] in keys and e["target"] in keys for e in story["edges"])
    ring_edges = [e for e in story["edges"] if e["attributes"]["kind"] == "ring"]
    assert len(ring_edges) == story["_meta"]["n_ring"]
    with pytest.raises(ValueError, match="persons"):
        export_story(edges, ring, person, iso_week(wk))


def test_default_story_target_reads_the_scores_table():
    scores = pl.DataFrame(
        {
            "week": ["2026-W41", "2026-W42", "2026-W42", "2026-W42"],
            "topic_id": ["org:a", "org:reuters", "org:b", "org:c"],
            "rank": [1, 1, 3, 2],
            "priority": [0.9, 0.99, 0.4, 0.8],
        }
    )
    assert default_story_target(scores) == ("org:c", "2026-W42")
    wk, top_rows = top_story_targets(scores, limit=10)
    assert wk == "2026-W42"
    assert [r["topic_id"] for r in top_rows] == ["org:c", "org:b"]
    assert story_filename("org:marsh mclennan") == "story_org_marsh_mclennan.json"
    assert week_monday("2026-W42") == date(2026, 10, 12)
    assert iso_week(date(2026, 10, 12)) == "2026-W42"


def test_temporal_and_story_carry_addendum3_properties(dev):
    edges, metrics, ring, _ = dev
    out = export_temporal(
        edges,
        metrics,
        max_nodes=MAX_NODES,
        min_n=MIN_N,
        min_npmi=MIN_NPMI,
        top_k=3,
    )
    e = out["edges"]
    assert "edge_state" in e and "n_growth" in e and "cross_ring" in e
    valid_states = {"new", "growing", "persisting", "fading"}
    assert set(e["edge_state"]).issubset(valid_states)
    assert len(e["edge_state"]) == len(e["n"])
    assert all(isinstance(x, bool) for x in e["cross_ring"])

    valid_rings = {"ai", "it", "ai_domain"}
    weeks_len = len(out["_meta"]["weeks"])
    for n in out["nodes"]:
        assert n["ring"] in valid_rings
        assert len(n["importance"]) == weeks_len
        assert len(n["momentum"]) == weeks_len
        assert len(n["betweenness"]) == weeks_len
        assert len(n["cross_ring_share"]) == weeks_len
        assert len(n["community_week"]) == weeks_len
        for b in n["betweenness"]:
            if b is not None:
                assert 0.0 <= b <= 1.0
        for cr in n["cross_ring_share"]:
            if cr is not None:
                assert 0.0 <= cr <= 1.0

    dists = out["_meta"]["property_distributions_latest_week"]
    assert "node_betweenness" in dists and "node_cross_ring_share" in dists
    assert "median" in dists["node_betweenness"] and "p90" in dists["node_betweenness"]

    wk = ring["wk"].max()
    topic = (
        ring.filter(pl.col("wk") == wk)
        .group_by("topic_id")
        .len()
        .sort("len", descending=True)["topic_id"][0]
    )
    st = export_story(edges, ring, topic, iso_week(wk))
    assert all(n["attributes"]["ring"] in valid_rings for n in st["nodes"])
    for edge in st["edges"]:
        attrs = edge["attributes"]
        assert attrs["edge_state"] in valid_states
        assert isinstance(attrs["n_growth"], float)
        assert isinstance(attrs["cross_ring"], bool)


def test_edge_state_uses_the_unpruned_previous_week():
    """An exported edge that lost top-k last week is not new if it still cleared n and NPMI."""
    prev = date(2026, 10, 5)
    cur = date(2026, 10, 12)
    rows = [
        # Previous week: a-c clears the thresholds but is not a top-1 edge for a or for c.
        (prev, "org:a", "org:b", 50, 0.9),
        (prev, "org:c", "org:d", 40, 0.85),
        (prev, "org:a", "org:c", 25, 0.3),
        # Current week: a-c is a top edge, so the export keeps it.
        (cur, "org:a", "org:c", 30, 0.95),
        (cur, "org:a", "org:b", 20, 0.2),
        (cur, "org:c", "org:d", 20, 0.2),
    ]
    edges = pl.DataFrame(
        {
            "wk": [row[0] for row in rows],
            "x": [row[1] for row in rows],
            "y": [row[2] for row in rows],
            "n": [row[3] for row in rows],
            "npmi": [row[4] for row in rows],
        }
    )
    metrics = pl.DataFrame(schema={"wk": pl.Date, "entity_id": pl.Utf8})
    out = export_temporal(edges, metrics, max_nodes=10, min_n=5, min_npmi=0.1, top_k=1, span=2)
    ids = [node["id"] for node in out["nodes"]]
    edges_out = out["edges"]
    found = None
    for source, target, week_i, state in zip(
        edges_out["source"],
        edges_out["target"],
        edges_out["week"],
        edges_out["edge_state"],
        strict=True,
    ):
        pair = {ids[source], ids[target]}
        if pair == {"org:a", "org:c"} and week_i == 1:
            found = state
    assert found == "persisting"
