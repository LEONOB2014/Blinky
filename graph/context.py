"""The 1-hop context ring of each ranked topic per week (P6, WS3 Cartographer).

For every ranked topic (an entity whose type is in ``ranked_entity_types`` of
``contracts/taxonomy.yaml``: organizations and themes, never persons) and week: its neighbours in
``edges_weekly`` with n >= 3 and NPMI > 0.1, persons and that week's hubs dropped, top 20 by NPMI
(ties by ``n``, then name). Persons are dropped before the top 20 is taken, so each topic still gets
up to 20 non-person neighbours; they never reach the ring, the API or the UI. Each neighbour
carries its segment and domain when a lookup is given; WS1's tables do not provide them yet, so
they are null until then.
"""

import polars as pl
import yaml

from radar.contracts import CONTRACTS_DIR

MIN_N = 3
MIN_NPMI = 0.1  # strict: NPMI > 0.1
TOP_K = 20
PERSON_PREFIX = "per:"  # never a ring neighbour (persons are not served)

COLUMNS = [
    "wk", "topic_id", "neighbor", "rank", "n", "npmi", "neighbor_segment", "neighbor_domain",
]  # fmt: skip


def ranked_entity_types() -> list[str]:
    taxonomy = yaml.safe_load((CONTRACTS_DIR / "taxonomy.yaml").read_text(encoding="utf-8"))
    return list(taxonomy["ranked_entity_types"])


def context_1hop(
    edges: pl.DataFrame,
    node_metrics: pl.DataFrame,
    segments: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """``topic_context_1hop`` rows.

    ``node_metrics`` supplies the weekly hub flags (``wk``, ``entity_id``, ``is_hub``).
    ``segments``, when given, maps ``entity_id`` to ``segment`` and ``domain``.
    """
    prefixes = tuple(f"{t}:" for t in ranked_entity_types())
    both = pl.concat(
        [
            edges.select("wk", pl.col("x").alias("topic_id"), pl.col("y").alias("neighbor"),
                         "n", "npmi"),
            edges.select("wk", pl.col("y").alias("topic_id"), pl.col("x").alias("neighbor"),
                         "n", "npmi"),
        ]
    )  # fmt: skip
    hubs = node_metrics.filter("is_hub").select("wk", pl.col("entity_id").alias("neighbor"))
    ring = (
        both.filter(
            pl.any_horizontal([pl.col("topic_id").str.starts_with(p) for p in prefixes]),
            ~pl.col("neighbor").str.starts_with(PERSON_PREFIX),
            pl.col("n") >= MIN_N,
            pl.col("npmi").is_not_null() & (pl.col("npmi") > MIN_NPMI),
        )
        .join(hubs, on=["wk", "neighbor"], how="anti")
        .sort(
            ["wk", "topic_id", "npmi", "n", "neighbor"],
            descending=[False, False, True, True, False],
        )
        .with_columns(rank=pl.int_range(1, pl.len() + 1).over("wk", "topic_id"))
        .filter(pl.col("rank") <= TOP_K)
    )
    if segments is None:
        ring = ring.with_columns(
            neighbor_segment=pl.lit(None, dtype=pl.Utf8),
            neighbor_domain=pl.lit(None, dtype=pl.Utf8),
        )
    else:
        ring = ring.join(
            segments.select(
                pl.col("entity_id").alias("neighbor"),
                pl.col("segment").alias("neighbor_segment"),
                pl.col("domain").alias("neighbor_domain"),
            ),
            on="neighbor",
            how="left",
        )
    return ring.with_columns(pl.col("rank").cast(pl.Int64), pl.col("n").cast(pl.Int64)).select(
        COLUMNS
    )
