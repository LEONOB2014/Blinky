"""Which input the scores, window, decision and backtest run on: the GDELT org/theme topics
(`topic_daily`, the default) or the AI lexicon topics (`topic_ai_daily`, `ai:<lexicon id>`).

Both tables share `topic_daily`'s schema, so the pipeline is the same; what differs is listed in
`Source`. The active source comes from `RADAR_SOURCE` (`gdelt` or `ai`) or `use()`, which the
`--source` flag of `models.build_scores` and `models.backtest` calls.

AI run (orchestrator's WP2, 2026-10-18):
- ranked universe = every `ai:` topic with at least one article in the week (no 20-article
  floor); the eligibility gate holds by construction (curated lexicon entries), the syndication
  guard is kept;
- each topic's group is its lexicon `family` (the window's lag pool and the audience fit), in
  place of WS1's subtopic mapping, which covers only GDELT topics;
- `new_nbr_rate` comes from `edges_ai_weekly` (`ai_new_nbr_rate`, the same rule as WS3's);
- the pageview label reads the lexicon's `wikipedia` titles (`crosssource/lexicon_pageviews.py`).
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from radar.paths import REPO_ROOT, gold


@dataclass(frozen=True)
class Source:
    name: str
    topic_table: str  # daily topic series, topic_daily's schema
    scores_table: str  # output of models.build_scores (topics)
    report: str  # output of models.backtest, under reports/
    prefix: str | None  # topic ids that may rank (None: the taxonomy's ranked_universe)
    min_articles_week: int | None  # None: the taxonomy's min_articles_week
    gate_by_construction: bool  # True: every ranked topic passes the eligibility gate
    sources_tables: tuple[str, ...]  # first one that exists feeds the syndication guard
    edges_table: str | None  # None: WS3's node_metrics_weekly feeds new_nbr_rate
    pageviews_table: str


SOURCES = {
    "gdelt": Source(
        name="gdelt",
        topic_table="topic_daily",
        scores_table="topic_scores_weekly",
        report="backtest.md",
        prefix=None,
        min_articles_week=None,
        gate_by_construction=False,
        sources_tables=("topic_sources_weekly",),
        edges_table=None,
        pageviews_table="wiki_pageviews_daily",
    ),
    "ai": Source(
        name="ai",
        topic_table="topic_ai_daily",
        scores_table="topic_ai_scores_weekly",
        report="backtest_ai.md",
        prefix="ai:",
        min_articles_week=1,
        gate_by_construction=True,
        sources_tables=("topic_ai_sources_weekly", "topic_sources_weekly"),
        edges_table="edges_ai_weekly",
        pageviews_table="wiki_pageviews_ai_daily",
    ),
}

_active: list[str] = []


def use(name: str) -> Source:
    """Make `name` the active source for this process (the CLIs' `--source`)."""
    if name not in SOURCES:
        raise ValueError(f"unknown source {name!r}; one of {sorted(SOURCES)}")
    _active[:] = [name]
    return SOURCES[name]


def current() -> Source:
    return SOURCES[_active[0] if _active else os.environ.get("RADAR_SOURCE", "gdelt")]


# --- the AI lexicon -----------------------------------------------------------------------------


def lexicon_path() -> Path:
    """contracts/ai_lexicon.yaml, or RADAR_AI_LEXICON (a lexicon not merged here yet)."""
    return Path(os.environ.get("RADAR_AI_LEXICON") or REPO_ROOT / "contracts" / "ai_lexicon.yaml")


@cache
def _lexicon(path: str) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def lexicon() -> dict[str, Any]:
    return _lexicon(str(lexicon_path()))


def entries() -> pl.DataFrame:
    """One row per lexicon entry: topic id (`ai:<id>`), label, family, stance and titles."""
    rows = []
    for e in lexicon()["entries"]:
        wiki = e.get("wikipedia") or {}
        rows.append(
            {
                "topic_id": f"ai:{e['id']}",
                "label_es": e["label_es"],
                "family": e["family"],
                "stance": e.get("stance"),
                "article_es": wiki.get("es"),
                "article_pt": wiki.get("pt"),
            }
        )
    schema = dict.fromkeys(("topic_id", "label_es", "family", "stance"), pl.String)
    schema |= {"article_es": pl.String, "article_pt": pl.String}
    return pl.DataFrame(rows, schema=schema)


# Families whose topics fit 30X's business audience, as WS1's business, funding and education
# subtopics do for GDELT topics (scores.FIT_SUBTOPICS). Hand-set, estimate.
FIT_FAMILIES = {"biz", "business"}


def family_membership(panel: pl.DataFrame) -> pl.DataFrame:
    """Per AI topic x week: its family as primary subtopic (the window's lag pool) and the fit share
    (1 for a business family, else 0), in the shape of `universe.membership`."""
    lex = entries().select(pl.col("topic_id").alias("unit_id"), "family")
    weeks = panel.select("unit_id", "week").unique()
    return weeks.join(lex, on="unit_id", how="inner").select(
        "unit_id",
        "week",
        pl.col("family").alias("primary_subtopic"),
        pl.concat_list(pl.col("family")).alias("subtopics"),
        pl.col("family").is_in(list(FIT_FAMILIES)).cast(pl.Float64).alias("fit_subtopic"),
    )


# --- new-neighbour rate from the AI co-mention edges ----------------------------------------------

NEW_NBR_WEEKS = 4  # graph.metrics.NEW_NBR_WEEKS (test_source checks they agree)
MIN_EDGE_N = 3  # bq_sql/s4_aggregates.sql S4b keeps co-mentions with n >= 3


def ai_new_nbr_rate(edges: pl.DataFrame) -> pl.DataFrame:
    """`new_nbr_rate` per node and ISO week, WS3's rule on `edges_ai_weekly`: the share of this
    week's neighbours that were not neighbours in any of the NEW_NBR_WEEKS weeks before (NULL
    unless all of them are in the table). Language buckets are summed; edges need n >= 3."""
    if "lang_bucket" in edges.columns or edges.select("wk", "x", "y").is_duplicated().any():
        edges = edges.group_by("wk", "x", "y").agg(pl.col("n").sum())
    edges = edges.filter(pl.col("n") >= MIN_EDGE_N)
    prefixed = pl.col("x").str.starts_with("ai:")  # S16 may write bare lexicon ids
    if not edges.is_empty() and not edges.select(prefixed.all()).item():
        edges = edges.with_columns(
            pl.when(pl.col(c).str.starts_with("ai:")).then(pl.col(c)).otherwise("ai:" + pl.col(c))
            for c in ("x", "y")
        )
    if edges.schema["wk"] == pl.String:
        edges = edges.with_columns(pl.col("wk").str.to_date())
    both = pl.concat(
        [
            edges.select("wk", pl.col("x").alias("a"), pl.col("y").alias("b")),
            edges.select("wk", pl.col("y").alias("a"), pl.col("x").alias("b")),
        ]
    )
    present = set(both["wk"].unique().to_list())
    nbrs: dict[dt.date, dict[str, set[str]]] = {}
    for wk, a, bs in both.group_by("wk", "a").agg("b").iter_rows():
        nbrs.setdefault(wk, {})[a] = set(bs)
    rows = []
    week = dt.timedelta(days=7)
    for wk in sorted(nbrs):
        back = [wk - week * k for k in range(1, NEW_NBR_WEEKS + 1)]
        ok = all(w in present for w in back)
        for node, now in nbrs[wk].items():
            rate = None
            if ok:
                seen = set().union(*(nbrs.get(w, {}).get(node, set()) for w in back))
                rate = len(now - seen) / len(now)
            rows.append({"unit_id": node, "wk": wk, "new_nbr_rate": rate})
    out = pl.DataFrame(
        rows, schema={"unit_id": pl.String, "wk": pl.Date, "new_nbr_rate": pl.Float64}
    )
    return out.select("unit_id", pl.col("wk").dt.strftime("%G-W%V").alias("week"), "new_nbr_rate")


def first_existing(names: tuple[str, ...]) -> Path | None:
    return next((gold(n) for n in names if gold(n).exists()), None)
