"""The ranked universe and each topic's subtopics, read from the contracts (never hard-coded).

Ranked universe (`contracts/taxonomy.yaml` `ranked_universe`, orchestrator's Addendum 2): every
`org:` topic of `topic_daily` except `org_deny`, plus the `thm:` topics whose theme starts with one
of `thm_prefixes`, with at least `min_articles_week` ring-1 articles in the ISO week.

Primary subtopic of a topic in week t (from WS1's `topic_subtopic_weekly`): the non-null subtopic
with the most articles over weeks t-3..t, ties broken by the subtopic's order in the taxonomy. A
topic with none has primary subtopic "" (empty): its window chip says `sin_estimacion` and its
audience fit uses its own series only.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import yaml

from radar.paths import REPO_ROOT, gold

TAXONOMY = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
RULES = TAXONOMY["ranked_universe"]
MIN_ARTICLES_WEEK: int = RULES["min_articles_week"]
SUBTOPIC_ORDER: list[str] = list(TAXONOMY["subtopics"])
PRIMARY_WEEKS = 4  # weeks t-3..t
NO_SUBTOPIC = ""


def in_universe(col: str = "topic_id") -> pl.Expr:
    """True for the topic ids the radar may rank (before the weekly article minimum)."""
    c = pl.col(col)
    deny = [f"org:{name}" for name in RULES.get("org_deny") or []]
    org = c.str.starts_with("org:") & ~c.is_in(deny) if RULES.get("org") else pl.lit(False)
    thm = pl.lit(False)
    for prefix in RULES.get("thm_prefixes") or []:
        thm = thm | c.str.starts_with(f"thm:{prefix}")
    return org | thm


def mapping_available() -> bool:
    return gold("topic_subtopic_weekly").exists()


def membership(fit_subtopics: set[str]) -> pl.DataFrame | None:
    """Per topic x ISO week: primary subtopic, its subtopics and the business/education share.

    Returns None when `topic_subtopic_weekly` is not in the active profile yet.
    """
    if not mapping_available():
        return None
    m = pl.scan_parquet(gold("topic_subtopic_weekly")).filter(in_universe("topic_id"))
    if m.collect_schema()["week"] == pl.String:
        m = m.with_columns(pl.col("week").str.to_date())
    # each source week counts toward itself and the 3 weeks after it (window t-3..t); lazy, so
    # the 4x copy is never held in memory at once
    spread = pl.concat(
        [
            m.with_columns((pl.col("week") + dt.timedelta(days=7 * k)).alias("target"))
            for k in range(PRIMARY_WEEKS)
        ]
    ).with_columns(pl.col("target").dt.strftime("%G-W%V").alias("iso_week"))
    denom = (
        spread.select("topic_id", "iso_week", "week", "n_topic_articles")
        .unique(["topic_id", "iso_week", "week"])
        .group_by("topic_id", "iso_week")
        .agg(pl.col("n_topic_articles").sum().alias("n_topic"))
        .collect()
    )
    sub = (
        spread.filter(pl.col("subtopic").is_not_null())
        .group_by("topic_id", "iso_week", "subtopic")
        .agg(pl.col("n_articles").sum())
        .collect()
        .with_columns(
            pl.col("subtopic")
            .replace_strict(
                {s: i for i, s in enumerate(SUBTOPIC_ORDER)},
                default=len(SUBTOPIC_ORDER),
                return_dtype=pl.Int64,
            )
            .alias("order")
        )
        .sort(
            ["topic_id", "iso_week", "n_articles", "order"], descending=[False, False, True, False]
        )
    )
    agg = sub.group_by("topic_id", "iso_week", maintain_order=True).agg(
        pl.col("subtopic").first().alias("primary_subtopic"),
        pl.col("subtopic").alias("subtopics"),
        pl.col("n_articles")
        .filter(pl.col("subtopic").is_in(list(fit_subtopics)))
        .sum()
        .alias("n_fit"),
    )
    return agg.join(denom, on=["topic_id", "iso_week"], how="left").select(
        pl.col("topic_id").alias("unit_id"),
        pl.col("iso_week").alias("week"),
        "primary_subtopic",
        "subtopics",
        (pl.col("n_fit") / pl.col("n_topic")).clip(0, 1).alias("fit_subtopic"),
    )
