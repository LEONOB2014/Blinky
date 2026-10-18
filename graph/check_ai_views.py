"""Guarantee the AI temporal graph is complete for every week, every lens and the important topics.

    RADAR_PROFILE=full uv run python -m graph.check_ai_views [lake/views/temporal.json]

Checks, per week of the 13-week player:
- structure: finite coordinates for every node, edges pointing at real nodes, per-week arrays of the
  right length, at least one edge;
- important topics: every topic ranked 1-10 that week (topic_ai_scores_weekly) and the 8 largest by
  volume are nodes of the graph, have importance and are marked for a label in the last week;
- lenses: each lens reads its fields for the week's active nodes (nodes with an edge):
  decision/rank (Radar), family (Familia), stance (Postura), community_week (Comunidades),
  momentum (Momento), betweenness and cross_ring_share (Puente), new_nbr_rate (Novedad),
  tone (Emoción), window_state (Ventana).
A field may be missing only when the source has no data that week (for example a topic not scored
that week has no decision); the check reports coverage and fails on structural gaps or on an
important topic left out. Exit 1 on any failure, so the deploy can gate on it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import polars as pl

from radar import paths

LENS_FIELDS = {
    "Familia": ["family"],
    "Postura": ["stance"],
    "Comunidades": ["community_week"],
    "Momento": ["momentum"],
    "Puente": ["betweenness", "cross_ring_share"],
    "Novedad": ["new_nbr_rate"],
    "Emoción": ["tone"],
    "Ventana": ["window_state"],
    "Radar": ["decision", "rank"],
    "Tamaño": ["importance"],
}
# Fields that must cover every active node every week (computed from the edges themselves).
MUST_COVER = {"family", "stance", "community_week", "betweenness", "importance"}


def _per_week(node: dict, field: str, wi: int):
    val = node.get(field)
    return val[wi] if isinstance(val, list) else val


def check(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta, nodes, e = data["_meta"], data["nodes"], data["edges"]
    weeks, iso = meta["weeks"], meta.get("iso_weeks", meta["weeks"])
    n_weeks, n_nodes = len(weeks), len(nodes)
    ids = {n["id"]: i for i, n in enumerate(nodes)}
    fails: list[str] = []

    for n in nodes:
        if not (math.isfinite(n["x"]) and math.isfinite(n["y"])):
            fails.append(f"{n['id']}: non-finite coordinates")
        for f in ("importance", "pagerank", "community_week", "momentum", "betweenness"):
            if isinstance(n.get(f), list) and len(n[f]) != n_weeks:
                fails.append(f"{n['id']}: {f} has {len(n[f])} weeks, expected {n_weeks}")
    for k in ("source", "target", "week", "n", "npmi"):
        if len(e[k]) != len(e["source"]):
            fails.append(f"edges: column {k} length differs")
    if any(not 0 <= s < n_nodes for s in e["source"] + e["target"]):
        fails.append("edges: an endpoint is not a node")

    scores_path = paths.gold("topic_ai_scores_weekly")
    daily_path = paths.gold("topic_ai_daily")
    scores = pl.read_parquet(scores_path) if scores_path.exists() else None
    daily = pl.read_parquet(daily_path) if daily_path.exists() else None

    print(
        f"{'week':9s} {'edges':>5s} {'active':>6s} " + " ".join(f"{k[:8]:>8s}" for k in LENS_FIELDS)
    )
    for wi in range(n_weeks):
        idx = [i for i, w in enumerate(e["week"]) if w == wi]
        active = {e["source"][i] for i in idx} | {e["target"][i] for i in idx}
        if not idx:
            fails.append(f"{iso[wi]}: no edges")
        cov = {}
        for lens, fields in LENS_FIELDS.items():
            got = sum(
                1 for i in active if all(_per_week(nodes[i], f, wi) is not None for f in fields)
            )
            cov[lens] = got / len(active) if active else 0.0
            for f in fields:
                if f in MUST_COVER:
                    missing = [nodes[i]["id"] for i in active if _per_week(nodes[i], f, wi) is None]
                    if missing:
                        fails.append(
                            f"{iso[wi]}: {f} missing for {len(missing)} active nodes, "
                            f"e.g. {missing[:3]}"
                        )
        print(
            f"{iso[wi]:9s} {len(idx):5d} {len(active):6d} "
            + " ".join(f"{cov[k]:8.0%}" for k in LENS_FIELDS)
        )

        important: set[str] = set()
        if scores is not None:
            important |= set(
                scores.filter((pl.col("week") == iso[wi]) & (pl.col("rank") <= 10))["topic_id"]
            )
        if daily is not None:
            start = pl.lit(weeks[wi]).str.to_date()
            top_vol = (
                daily.filter((pl.col("dt") >= start) & (pl.col("dt") < start + pl.duration(days=7)))
                .group_by("topic_id")
                .agg(pl.col("n_articles").sum())
                .sort("n_articles", descending=True)
                .head(8)["topic_id"]
            )
            important |= set(top_vol)
        for t in sorted(important):
            if t not in ids:
                fails.append(f"{iso[wi]}: important topic {t} is not a node of the graph")
            elif _per_week(nodes[ids[t]], "importance", wi) is None:
                fails.append(
                    f"{iso[wi]}: important topic {t} has no importance (no edge that week)"
                )
        if wi == n_weeks - 1:
            unlabeled = [t for t in important if t in ids and not nodes[ids[t]].get("show_label")]
            if unlabeled:
                fails.append(f"{iso[wi]}: important topics without a label: {unlabeled}")
    return fails


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else paths.lake() / "views" / "temporal.json"
    fails = check(path)
    if fails:
        print(f"\nFAIL: {len(fails)} problems")
        for f in fails[:40]:
            print(" -", f)
        sys.exit(1)
    print("\nPASS: every week, lens and important topic is covered")


if __name__ == "__main__":
    main()
