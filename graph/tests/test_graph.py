"""Graph metrics and the 1-hop ring on the committed dev slice (real weeks, RADAR_PROFILE=dev)."""

import math
from datetime import date

import polars as pl
import pytest

# The graph extra (igraph, leidenalg) is not in the base env CI installs: skip, visibly, without it.
pytest.importorskip("igraph")
pytest.importorskip("leidenalg")

from graph.build import build, validate
from graph.context import MIN_NPMI, TOP_K, context_1hop, ranked_entity_types
from graph.metrics import (
    JACCARD_MIN,
    hub_set,
    leiden_communities,
    match_communities,
    node_metrics,
    week_graph,
)
from radar.contracts import validate_records
from radar.fixtures import DEV_DIR

pytestmark = pytest.mark.unit

WK_A, WK_B = date(2026, 10, 5), date(2026, 10, 12)  # two real consecutive dev-slice weeks


@pytest.fixture(scope="module")
def edges():
    return pl.read_parquet(DEV_DIR / "edges_weekly.parquet")


@pytest.fixture(scope="module")
def outputs(edges):
    return build(edges)


def _records(df):
    return df.with_columns(pl.col("wk").cast(pl.Utf8)).to_dicts()


def test_both_outputs_match_their_contracts(outputs):
    metrics, ring = outputs
    assert metrics.height > 0 and ring.height > 0
    assert validate_records("node_metrics_weekly", _records(metrics)) == []
    assert validate_records("topic_context_1hop", _records(ring)) == []


def test_validation_rejects_a_broken_row(outputs):
    _, ring = outputs
    with pytest.raises(ValueError, match="contract violations"):
        validate("topic_context_1hop", ring.head(1).with_columns(rank=pl.lit(21, pl.Int64)))


def test_hubs_are_the_top_one_percent_by_weighted_degree(outputs):
    metrics, _ = outputs
    for (wk,), week in metrics.group_by("wk"):
        k = math.ceil(0.01 * week.height)
        cutoff = week["deg_w"].sort(descending=True)[k - 1]
        hubs = week.filter("is_hub")
        assert hubs.height >= k, wk
        assert hubs["deg_w"].min() >= cutoff
        assert week.filter(~pl.col("is_hub"))["deg_w"].max() < cutoff


def test_hubs_are_never_in_the_ring(outputs):
    metrics, ring = outputs
    hubs = metrics.filter("is_hub").select("wk", pl.col("entity_id").alias("neighbor"))
    assert hubs.height > 0
    assert ring.join(hubs, on=["wk", "neighbor"]).height == 0


def test_ring_npmi_n_and_rank_limits(outputs):
    _, ring = outputs
    assert ring["npmi"].min() > MIN_NPMI
    assert ring["n"].min() >= 3
    per_topic = ring.group_by("wk", "topic_id").agg(
        k=pl.len(), rmin=pl.col("rank").min(), rmax=pl.col("rank").max(),
        ranks_unique=pl.col("rank").n_unique(),
    )  # fmt: skip
    assert per_topic["k"].max() == TOP_K  # the cap binds on real weeks
    assert (per_topic["rmin"] == 1).all()
    assert (per_topic["rmax"] == per_topic["k"]).all()
    assert (per_topic["ranks_unique"] == per_topic["k"]).all()
    prefixes = tuple(f"{t}:" for t in ranked_entity_types())
    assert all(t.startswith(prefixes) for t in ring["topic_id"].unique())


def test_ring_keeps_the_top_npmi_neighbours(edges, outputs):
    metrics, ring = outputs
    topic = (
        ring.filter(pl.col("wk") == WK_B)
        .group_by("topic_id")
        .len()
        .filter(pl.col("len") == TOP_K)["topic_id"]
        .sort()[0]
    )
    hubs = set(metrics.filter((pl.col("wk") == WK_B) & pl.col("is_hub"))["entity_id"])
    week = edges.filter(pl.col("wk") == WK_B)
    eligible = pl.concat(
        [
            week.filter(pl.col("x") == topic).select(pl.col("y").alias("nb"), "npmi"),
            week.filter(pl.col("y") == topic).select(pl.col("x").alias("nb"), "npmi"),
        ]
    ).filter((pl.col("npmi") > MIN_NPMI) & ~pl.col("nb").is_in(hubs))
    assert eligible.height > TOP_K
    got = ring.filter((pl.col("wk") == WK_B) & (pl.col("topic_id") == topic)).sort("rank")
    assert got["npmi"].to_list() == sorted(eligible["npmi"].to_list(), reverse=True)[:TOP_K]


def test_community_matching_across_two_real_weeks(edges):
    week_a = edges.filter(pl.col("wk") == WK_A)
    week_b = edges.filter(pl.col("wk") == WK_B)
    comms_a = leiden_communities(week_graph(week_a))
    comms_b = leiden_communities(week_graph(week_b))
    ids_a, _ = match_communities(None, comms_a, WK_A)
    prev = dict(zip(ids_a, comms_a, strict=True))
    ids_b, events_b = match_communities(prev, comms_b, WK_B)

    def jac(a, b):
        return len(a & b) / len(a | b)

    assert len(set(ids_b)) == len(ids_b)  # an id is used once per week
    carried = 0
    for cid, ev, members in zip(ids_b, events_b, comms_b, strict=True):
        best = max(jac(m, members) for m in comms_a)
        if ev == "birth":
            assert best < JACCARD_MIN
            assert cid.startswith(WK_B.isoformat())
        else:
            assert best >= JACCARD_MIN
        if cid in prev:
            carried += 1
            assert jac(prev[cid], members) >= JACCARD_MIN
    assert carried > 0  # real consecutive weeks keep at least one community


def test_match_events_merge_split_and_null_without_history():
    wk = date(2026, 10, 12)
    prev = {"p1": {"a", "b", "c"}, "p2": {"d", "e", "f"}, "p3": {"g", "h", "i", "j", "k", "l"}}
    cur = [{"a", "b", "c", "d", "e", "f"}, {"g", "h", "i"}, {"j", "k", "l"}, {"x", "y"}]
    ids, events = match_communities(prev, cur, wk)
    assert events == ["merge", "split", "split", "birth"]
    assert ids[0] in {"p1", "p2"}
    assert sum(i == "p3" for i in ids) == 1
    assert ids[3] == "2026-10-12/c003"
    _, none_events = match_communities(None, cur, wk)
    assert none_events == [None] * len(cur)


def test_a_missing_week_is_never_filled(edges):
    gap = edges.filter(pl.col("wk") != WK_A)
    after = node_metrics(gap).filter(pl.col("wk") == WK_B)
    assert after["deg_growth"].null_count() == after.height
    assert after["pr_rank_delta"].null_count() == after.height
    assert after["new_nbr_rate"].null_count() == after.height
    assert after["community_event"].null_count() == after.height


def test_lookback_metrics_on_full_history(outputs):
    metrics, _ = outputs
    weeks = sorted(metrics["wk"].unique())
    first = metrics.filter(pl.col("wk") == weeks[0])
    assert first["deg_growth"].null_count() == first.height
    fifth = metrics.filter(pl.col("wk") == weeks[4])
    assert fifth["new_nbr_rate"].null_count() == 0
    assert fifth["new_nbr_rate"].is_between(0, 1).all()


def test_hub_set_includes_ties():
    assert hub_set({"a": 5, "b": 5, "c": 1}, share=0.01) == {"a", "b"}
    assert hub_set({}) == set()


def test_segments_join_when_provided(edges, outputs):
    metrics, _ = outputs
    week = edges.filter(pl.col("wk") == WK_B)
    nb = context_1hop(week, metrics)["neighbor"][0]
    seg = pl.DataFrame(
        {"entity_id": [nb], "segment": ["it"], "domain": [None]},
        schema={"entity_id": pl.Utf8, "segment": pl.Utf8, "domain": pl.Utf8},
    )
    ring = context_1hop(week, metrics, seg)
    assert ring.filter(pl.col("neighbor") == nb)["neighbor_segment"].unique().to_list() == ["it"]
    assert validate_records("topic_context_1hop", _records(ring)) == []
