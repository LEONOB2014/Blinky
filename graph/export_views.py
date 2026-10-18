"""Graph-view exports for the smoke test (WS3c): the temporal sweep and the story of one topic.

    RADAR_PROFILE=full uv run python -m graph.export_views             # writes lake/views/*.json
    RADAR_PROFILE=full uv run python -m graph.export_views --topic org:nvidia --week 2026-W42

- ``temporal.json``: the last 13 weeks (about 90 days) of ``edges_weekly``, pruned for a laptop:
  the top ``max_nodes`` nodes by weighted degree over the span (on the kept edges), and their
  edges with n >= ``min_n`` and NPMI > ``min_npmi``. Each edge carries its week; each node its
  weekly PageRank and, when ``topic_scores_weekly`` ranks it, its weekly rank and decision.
- ``story.json``: one topic and week (default: the #1 topic of the latest scored week, read from
  ``topic_scores_weekly``, never hard-coded): the topic, its 1-hop ring, the edges among them and
  the scores row, as a graphology/sigma.js serialized graph with a radial layout.

Persons (``per:``) never leave the lake: they are dropped from every node and edge here. Fields are
documented in ``graph/README.md``. Outputs are contract-free smoke-test files in ``lake/views/``.
"""

import argparse
import json
import math
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from radar import paths

VIEWS_DIR = Path(__file__).resolve().parent / "views"  # the HTML pages copied next to the JSON
PERSON_PREFIX = "per:"
SPAN_WEEKS = 13
MAX_NODES = 2000
MIN_N = 5
MIN_NPMI = 0.1
DECISIONS = ["publicar_ahora", "preparar", "esperar", "no_es_tema_caliente"]


def iso_week(monday: date) -> str:
    y, w, _ = monday.isocalendar()
    return f"{y}-W{w:02d}"


def week_monday(week: str) -> date:
    y, w = week.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def _no_persons(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.filter(
        ~pl.col("x").str.starts_with(PERSON_PREFIX) & ~pl.col("y").str.starts_with(PERSON_PREFIX)
    )


def _label(entity_id: str) -> str:
    return entity_id.split(":", 1)[1] if ":" in entity_id else entity_id


def _clean(v: Any) -> Any:
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_clean(x) for x in v]
    return v


def span_weeks(edges: pl.LazyFrame, span: int = SPAN_WEEKS) -> list[date]:
    """The last ``span`` weeks present in the data (a missing week stays missing, never filled)."""
    weeks = sorted(edges.select(pl.col("wk").unique()).collect()["wk"].to_list())
    last = weeks[-1]
    wanted = {last - timedelta(weeks=k) for k in range(span)}
    return [w for w in weeks if w in wanted]


def export_temporal(
    edges: pl.LazyFrame | pl.DataFrame,
    node_metrics: pl.LazyFrame | pl.DataFrame,
    scores: pl.LazyFrame | pl.DataFrame | None = None,
    *,
    span: int = SPAN_WEEKS,
    max_nodes: int = MAX_NODES,
    min_n: int = MIN_N,
    min_npmi: float = MIN_NPMI,
) -> dict[str, Any]:
    edges, node_metrics = edges.lazy(), node_metrics.lazy()
    weeks = span_weeks(edges, span)
    widx = {w: i for i, w in enumerate(weeks)}
    kept = (
        _no_persons(edges)
        .filter(
            pl.col("wk").is_in(weeks),
            pl.col("n") >= min_n,
            pl.col("npmi").is_not_null() & (pl.col("npmi") > min_npmi),
        )
        .select("wk", "x", "y", "n", "npmi")
        .collect()
    )
    deg = (
        pl.concat([kept.select(e=pl.col("x"), n="n"), kept.select(e=pl.col("y"), n="n")])
        .group_by("e")
        .agg(pl.col("n").sum().alias("deg"))
        .sort(["deg", "e"], descending=[True, False])
        .head(max_nodes)
    )
    ids = deg["e"].to_list()
    idx = {v: i for i, v in enumerate(ids)}
    kept = kept.filter(pl.col("x").is_in(ids) & pl.col("y").is_in(ids)).sort("wk", "x", "y")

    pr = (
        node_metrics.filter(pl.col("wk").is_in(weeks) & pl.col("entity_id").is_in(ids))
        .select("wk", "entity_id", "pagerank")
        .collect()
    )
    pagerank = {v: [None] * len(weeks) for v in ids}
    for wk, v, p in pr.iter_rows():
        pagerank[v][widx[wk]] = p

    rank = {v: [None] * len(weeks) for v in ids}
    decision = {v: [None] * len(weeks) for v in ids}
    if scores is not None:
        wk_names = {iso_week(w): i for i, w in enumerate(weeks)}
        sc = (
            scores.lazy()
            .filter(pl.col("week").is_in(list(wk_names)) & pl.col("topic_id").is_in(ids))
            .select("week", "topic_id", "rank", "decision")
            .collect()
        )
        for week, v, r, d in sc.iter_rows():
            rank[v][wk_names[week]] = r
            decision[v][wk_names[week]] = d

    nodes = [
        {
            "id": v,
            "label": _label(v),
            "etype": v.split(":", 1)[0],
            "deg_span": int(d),
            "pagerank": pagerank[v],
            "rank": rank[v],
            "decision": decision[v],
        }
        for v, d in deg.iter_rows()
    ]
    return _clean(
        {
            "_meta": {
                "profile": paths.profile(),
                "view": "temporal",
                "weeks": [w.isoformat() for w in weeks],
                "iso_weeks": [iso_week(w) for w in weeks],
                "params": {
                    "span_weeks": span,
                    "max_nodes": max_nodes,
                    "min_n": min_n,
                    "min_npmi_exclusive": min_npmi,
                },  # fmt: skip
                "n_nodes": len(nodes),
                "n_edges": kept.height,
                "edges_per_week": [
                    kept.filter(pl.col("wk") == w).height for w in weeks
                ],  # fmt: skip
                "decisions": DECISIONS,
            },
            "nodes": nodes,
            "edges": {
                "source": [idx[x] for x in kept["x"]],
                "target": [idx[y] for y in kept["y"]],
                "week": [widx[w] for w in kept["wk"]],
                "n": kept["n"].to_list(),
                "npmi": kept["npmi"].to_list(),
            },
        }
    )


def default_story_target(scores: pl.LazyFrame | pl.DataFrame) -> tuple[str, str]:
    """The #1 non-person topic of the latest scored week (read, never hard-coded)."""
    lf = scores.lazy()
    week = lf.select(pl.col("week").max()).collect().item()
    top = (
        lf.filter((pl.col("week") == week) & ~pl.col("topic_id").str.starts_with(PERSON_PREFIX))
        .sort(pl.col("rank").fill_null(999_999))
        .select("topic_id")
        .head(1)
        .collect()
    )
    return top.item(), week


def export_story(
    edges: pl.LazyFrame | pl.DataFrame,
    ring: pl.LazyFrame | pl.DataFrame,
    topic_id: str,
    week: str,
    scores: pl.LazyFrame | pl.DataFrame | None = None,
) -> dict[str, Any]:
    if topic_id.startswith(PERSON_PREFIX):
        raise ValueError("persons are never exported")
    monday = week_monday(week)
    nbrs = (
        ring.lazy()
        .filter(
            (pl.col("wk") == monday)
            & (pl.col("topic_id") == topic_id)
            & ~pl.col("neighbor").str.starts_with(PERSON_PREFIX)
        )
        .sort("rank")
        .head(20)
        .collect()
    )
    members = [topic_id, *nbrs["neighbor"].to_list()]
    among = (
        _no_persons(edges.lazy())
        .filter(
            (pl.col("wk") == monday)
            & pl.col("x").is_in(members)
            & pl.col("y").is_in(members)
            & (pl.col("x") != topic_id)
            & (pl.col("y") != topic_id)
        )
        .select("x", "y", "n", "npmi")
        .collect()
    )
    score_row = None
    if scores is not None:
        rows = (
            scores.lazy()
            .filter((pl.col("week") == week) & (pl.col("topic_id") == topic_id))
            .collect()
            .to_dicts()
        )
        score_row = _clean(rows[0]) if rows else None

    k = max(1, nbrs.height)
    n_max = max([1, *nbrs["n"].to_list()])
    nodes = [{"key": topic_id, "attributes": {
        "label": _label(topic_id), "x": 0.0, "y": 0.0, "size": 18, "role": "topic",
        "etype": topic_id.split(":", 1)[0]}}]  # fmt: skip
    edge_list = []
    for i, (nb, rk, n, npmi) in enumerate(nbrs.select("neighbor", "rank", "n", "npmi").iter_rows()):
        angle = 2 * math.pi * i / k
        nodes.append({"key": nb, "attributes": {
            "label": _label(nb), "x": round(math.cos(angle), 6), "y": round(math.sin(angle), 6),
            "size": 6 + 8 * n / n_max, "role": "ring", "rank": rk, "n": n, "npmi": npmi,
            "etype": nb.split(":", 1)[0]}})  # fmt: skip
        edge_list.append({"key": f"t{i}", "source": topic_id, "target": nb, "attributes": {
            "n": n, "npmi": npmi, "size": 1 + 7 * n / n_max, "kind": "ring"}})  # fmt: skip
    for j, (x, y, n, npmi) in enumerate(among.iter_rows()):
        width = 0.3 + 1.2 * min(n, n_max) / n_max  # thinner than ring edges, so the ring reads
        edge_list.append({"key": f"a{j}", "source": x, "target": y, "attributes": {
            "n": n, "npmi": npmi, "size": width, "kind": "among"}})  # fmt: skip
    return _clean(
        {
            "_meta": {
                "profile": paths.profile(),
                "view": "story",
                "topic_id": topic_id,
                "week": week,
                "wk": monday.isoformat(),
                "n_ring": nbrs.height,
                "n_among_edges": among.height,
            },  # fmt: skip
            "attributes": {"topic_id": topic_id, "week": week, "scores": score_row},
            "options": {"type": "undirected", "multi": False},
            "nodes": nodes,
            "edges": edge_list,
        }
    )


def _write(obj: dict[str, Any], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=paths.lake() / "views")
    parser.add_argument("--topic", help="story topic id (default: #1 of the latest scored week)")
    parser.add_argument("--week", help="story ISO week, e.g. 2026-W42 (default: latest scored)")
    parser.add_argument("--max-nodes", type=int, default=MAX_NODES)
    parser.add_argument("--min-n", type=int, default=MIN_N)
    args = parser.parse_args(argv)

    edges = pl.scan_parquet(paths.gold("edges_weekly"))
    metrics = pl.scan_parquet(paths.gold("node_metrics_weekly"))
    ring = pl.scan_parquet(paths.gold("topic_context_1hop"))
    scores_path = paths.gold("topic_scores_weekly")
    scores = pl.scan_parquet(scores_path) if scores_path.exists() else None

    t0 = time.perf_counter()
    temporal = export_temporal(edges, metrics, scores, max_nodes=args.max_nodes, min_n=args.min_n)
    t1 = time.perf_counter()
    size_t = _write(temporal, args.out / "temporal.json")

    topic, week = args.topic, args.week
    if topic is None or week is None:
        if scores is None:
            raise SystemExit("no topic_scores_weekly: pass --topic and --week")
        d_topic, d_week = default_story_target(scores)
        topic, week = topic or d_topic, week or d_week
    t2 = time.perf_counter()
    story = export_story(edges, ring, topic, week, scores)
    t3 = time.perf_counter()
    size_s = _write(story, args.out / "story.json")

    for page in ("temporal.html", "story.html"):
        shutil.copy(VIEWS_DIR / page, args.out / page)

    m = temporal["_meta"]
    sys.stdout.write(
        f"temporal: {m['n_nodes']} nodes, {m['n_edges']} edges over {len(m['weeks'])} weeks "
        f"({m['weeks'][0]} .. {m['weeks'][-1]}), per week {m['edges_per_week']}, "
        f"{size_t / 1e6:.1f} MB, {t1 - t0:.1f} s\n"
        f"story: {topic} {week}: {story['_meta']['n_ring']} ring, "
        f"{story['_meta']['n_among_edges']} edges among them, {size_s / 1e3:.1f} kB, "
        f"{t3 - t2:.2f} s\n"
        f"serve: cd {args.out} && python -m http.server 8765  (temporal.html, story.html)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
