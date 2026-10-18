"""Weekly metrics of the entity co-occurrence graph (WS3 Cartographer) -> ``node_metrics_weekly``.

One undirected graph per week from ``edges_weekly``: nodes are ``'<etype>:<entity>'``, edge weight
is the co-mention count ``n``. Per node and week: weighted degree, degree growth, new-neighbour
rate against the prior 4 weeks, weighted PageRank and its rank delta, k-core, the Leiden community
matched across weeks, and the hub flag. These feed Emergence (WS4) and the 1-hop ring.

Missing weeks are never filled: a metric that needs an earlier week is null when that week is not
in the data (or the node was absent from it).
"""

import math
from collections import Counter, defaultdict
from datetime import date, timedelta

import igraph as ig
import leidenalg
import polars as pl

HUB_SHARE = 0.01  # hubs: the top 1% of nodes by weighted degree that week
NEW_NBR_WEEKS = 4  # new-neighbour rate looks back this many weeks
JACCARD_MIN = 0.3  # two communities in consecutive weeks match at Jaccard >= 0.3
LEIDEN_SEED = 42
WEEK = timedelta(days=7)

COLUMNS = [
    "wk", "entity_id", "deg_w", "deg_growth", "new_nbr_rate", "pagerank", "pr_rank_delta",
    "kcore", "community_id", "community_event", "is_hub",
]  # fmt: skip


def week_graph(edges_wk: pl.DataFrame) -> ig.Graph:
    """The undirected weighted graph of one week (weight = co-mentions ``n``)."""
    return ig.Graph.TupleList(
        edges_wk.select("x", "y", "n").iter_rows(), directed=False, weights=False, edge_attrs=["n"]
    )


def hub_set(deg_w: dict[str, float], share: float = HUB_SHARE) -> set[str]:
    """Nodes at or above the k-th largest weighted degree, k = ceil(share * nodes)."""
    if not deg_w:
        return set()
    k = max(1, math.ceil(share * len(deg_w)))
    cutoff = sorted(deg_w.values(), reverse=True)[k - 1]
    return {node for node, d in deg_w.items() if d >= cutoff}


def leiden_communities(g: ig.Graph, seed: int = LEIDEN_SEED) -> list[set[str]]:
    """Leiden (modularity, weighted by ``n``) communities as sets of node names, largest first."""
    part = leidenalg.find_partition(g, leidenalg.ModularityVertexPartition, weights="n", seed=seed)
    names = g.vs["name"]
    comms = [{names[v] for v in members} for members in part]
    return sorted(comms, key=lambda c: (-len(c), min(c)))


def match_communities(
    prev: dict[str, set[str]] | None,
    cur: list[set[str]],
    wk: date,
    threshold: float = JACCARD_MIN,
) -> tuple[list[str], list[str | None]]:
    """Give this week's communities ids and events by Jaccard overlap with last week's.

    ``prev`` maps last week's ids to members (None when last week is not in the data: every
    community gets a new id and a null event, since its history is unknown). A pair matches at
    Jaccard >= ``threshold``. Events: ``birth`` (no match), ``merge`` (>= 2 predecessors),
    ``split`` (its predecessor has >= 2 successors), else ``continue``. A community keeps its
    predecessor's id when each is the other's best match; otherwise it gets a new id, so an id
    is never used twice in one week.
    """
    new_ids = [f"{wk.isoformat()}/c{k:03d}" for k in range(len(cur))]
    if prev is None:
        return new_ids, [None] * len(cur)

    prev_of = {node: cid for cid, members in prev.items() for node in members}
    jac: dict[tuple[str, int], float] = {}
    for j, members in enumerate(cur):
        inter = Counter(prev_of[node] for node in members if node in prev_of)
        for cid, n_common in inter.items():
            score = n_common / (len(prev[cid]) + len(members) - n_common)
            if score >= threshold:
                jac[(cid, j)] = score

    preds: dict[int, list[str]] = defaultdict(list)
    succs: dict[str, list[int]] = defaultdict(list)
    for cid, j in jac:
        preds[j].append(cid)
        succs[cid].append(j)
    best_succ = {cid: max(js, key=lambda j: (jac[(cid, j)], -j)) for cid, js in succs.items()}

    ids, events = [], []
    for j in range(len(cur)):
        if not preds[j]:
            ids.append(new_ids[j])
            events.append("birth")
            continue
        best_pred = max(preds[j], key=lambda c: (jac[(c, j)], c))
        ids.append(best_pred if best_succ[best_pred] == j else new_ids[j])
        if len(preds[j]) >= 2:
            events.append("merge")
        elif len(succs[best_pred]) >= 2:
            events.append("split")
        else:
            events.append("continue")
    return ids, events


def _neighbours(edges: pl.DataFrame) -> dict[date, dict[str, set[str]]]:
    both = pl.concat(
        [
            edges.select("wk", pl.col("x").alias("a"), pl.col("y").alias("b")),
            edges.select("wk", pl.col("y").alias("a"), pl.col("x").alias("b")),
        ]
    )
    out: dict[date, dict[str, set[str]]] = defaultdict(dict)
    for wk, a, bs in both.group_by("wk", "a").agg("b").iter_rows():
        out[wk][a] = set(bs)
    return out


def edge_weeks(edges: pl.DataFrame | pl.LazyFrame) -> list[date]:
    return sorted(edges.lazy().select(pl.col("wk").unique()).collect()["wk"].to_list())


def node_metrics(edges: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    """``node_metrics_weekly`` rows for every node of every week in ``edges``.

    Reads one week at a time (``edges`` may be a lazy scan of the full table) and keeps only the
    weeks the look-backs need in memory.
    """
    lf = edges.lazy()
    weeks = edge_weeks(lf)
    present = set(weeks)
    nbrs: dict[date, dict[str, set[str]]] = {}
    deg: dict[date, dict[str, float]] = {}
    pr_rank: dict[date, dict[str, int]] = {}
    comms_prev: dict[str, set[str]] | None = None
    rows = []

    for wk in weeks:
        week = lf.filter(pl.col("wk") == wk).collect()
        nbrs[wk] = _neighbours(week).get(wk, {})
        g = week_graph(week)
        names = g.vs["name"]
        deg_w = dict(zip(names, g.strength(weights="n"), strict=True))
        pagerank = dict(zip(names, g.pagerank(weights="n", directed=False), strict=True))
        kcore = dict(zip(names, g.coreness(), strict=True))
        hubs = hub_set(deg_w)

        order = sorted(names, key=lambda v: (-pagerank[v], v))
        rank = {v: i + 1 for i, v in enumerate(order)}

        comms = leiden_communities(g)
        prev_wk = wk - WEEK
        ids, events = match_communities(comms_prev if prev_wk in present else None, comms, wk)
        comm_of = {v: (cid, ev) for members, cid, ev in zip(comms, ids, events, strict=True)
                   for v in members}  # fmt: skip
        comms_prev = dict(zip(ids, comms, strict=True))

        lookback = [wk - WEEK * k for k in range(1, NEW_NBR_WEEKS + 1)]
        has_lookback = all(w in present for w in lookback)

        for v in names:
            d_prev = deg.get(prev_wk, {}).get(v) if prev_wk in present else None
            r_prev = pr_rank.get(prev_wk, {}).get(v) if prev_wk in present else None
            new_rate = None
            if has_lookback:
                seen = set().union(*(nbrs[w].get(v, set()) for w in lookback))
                now = nbrs[wk][v]
                new_rate = len(now - seen) / len(now)
            rows.append(
                {
                    "wk": wk,
                    "entity_id": v,
                    "deg_w": float(deg_w[v]),
                    "deg_growth": math.log(deg_w[v] / d_prev) if d_prev else None,
                    "new_nbr_rate": new_rate,
                    "pagerank": pagerank[v],
                    "pr_rank_delta": r_prev - rank[v] if r_prev is not None else None,
                    "kcore": kcore[v],
                    "community_id": comm_of[v][0],
                    "community_event": comm_of[v][1],
                    "is_hub": v in hubs,
                }
            )
        deg = {wk: deg_w}
        pr_rank = {wk: rank}
        nbrs = {w: nb for w, nb in nbrs.items() if w > wk - WEEK * NEW_NBR_WEEKS}

    schema = {
        "wk": pl.Date, "entity_id": pl.Utf8, "deg_w": pl.Float64, "deg_growth": pl.Float64,
        "new_nbr_rate": pl.Float64, "pagerank": pl.Float64, "pr_rank_delta": pl.Int64,
        "kcore": pl.Int64, "community_id": pl.Utf8, "community_event": pl.Utf8,
        "is_hub": pl.Boolean,
    }  # fmt: skip
    return pl.DataFrame(rows, schema=schema).select(COLUMNS)
