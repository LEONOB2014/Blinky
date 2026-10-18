"""Build ``node_metrics_weekly`` and ``topic_context_1hop`` for the active profile.

    RADAR_PROFILE=full uv run python -m graph.build           # writes lake/gold/*.parquet
    uv run python -m graph.build --out <dir>                  # dev: writes only where asked

Every row is validated against its contract before anything is written; a violation aborts the
run. The per-week summary (nodes, edges, communities, hubs, ring rows) goes to stdout as a
Markdown table. Numbers from the dev profile are never reported.
"""

import argparse
import sys
from pathlib import Path

import polars as pl

from graph.context import context_1hop
from graph.metrics import node_metrics
from radar import paths
from radar.contracts import validate_records


def validate(name: str, df: pl.DataFrame) -> None:
    records = df.with_columns(pl.col("wk").cast(pl.Utf8)).to_dicts()
    errors = validate_records(name, records)
    if errors:
        head = "\n".join(errors[:20])
        raise ValueError(f"{name}: {len(errors)} contract violations, first ones:\n{head}")


def build(edges: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    metrics = node_metrics(edges)
    ring = context_1hop(edges, metrics)
    validate("node_metrics_weekly", metrics)
    validate("topic_context_1hop", ring)
    return metrics, ring


def summary(edges: pl.DataFrame, metrics: pl.DataFrame, ring: pl.DataFrame) -> pl.DataFrame:
    e = edges.group_by("wk").agg(edges=pl.len())
    m = metrics.group_by("wk").agg(
        nodes=pl.len(),
        communities=pl.col("community_id").n_unique(),
        hubs=pl.col("is_hub").sum(),
        births=(pl.col("community_event") == "birth").sum(),
    )
    r = ring.group_by("wk").agg(ring_topics=pl.col("topic_id").n_unique(), ring_rows=pl.len())
    return (
        e.join(m, on="wk", how="left")
        .join(r, on="wk", how="left")
        .sort("wk")
        .select("wk", "nodes", "edges", "communities", "hubs", "ring_topics", "ring_rows")
    )


def markdown(df: pl.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.iter_rows()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, help="output directory (full default: lake/gold)")
    args = parser.parse_args(argv)

    out = args.out
    if out is None and paths.profile() == "full":
        out = paths.lake() / "gold"

    edges = pl.read_parquet(paths.gold("edges_weekly"))
    metrics, ring = build(edges)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        metrics.write_parquet(out / "node_metrics_weekly.parquet")
        ring.write_parquet(out / "topic_context_1hop.parquet")
    sys.stdout.write(f"profile={paths.profile()} written_to={out}\n")
    sys.stdout.write(markdown(summary(edges, metrics, ring)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
