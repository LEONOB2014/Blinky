"""es+pt Wikipedia pageviews for the AI lexicon's page titles (the AI run's primary backtest label).

    RADAR_PROFILE=full uv run --extra crosssource python -m crosssource.lexicon_pageviews --dry-run
    RADAR_PROFILE=full uv run --extra crosssource python -m crosssource.lexicon_pageviews

Reuses WS6's fetcher (`crosssource.pageviews.fetch_pageviews`): the same Wikimedia REST endpoint,
the same response cache under `lake/raw/pageviews/`, and the client's pageview rate of one
request per 6.5 s. Titles come from each entry's `wikipedia: {es, pt}` in
`contracts/ai_lexicon.yaml` (or `RADAR_AI_LEXICON`); there is no Wikidata step.

Output: `lake/gold/wiki_pageviews_ai_daily.parquet`, one row per topic, project and day
(`topic_id`, `project`, `article`, `dt`, `views`). It is keyed by `ai:` topic id, not QID, so it
is a separate table from `wiki_pageviews_daily` (whose contract requires a QID). Missing days are
left out, never filled with zero. The file is rewritten every 50 articles, so a stopped run keeps
what it fetched.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from radar.paths import lake

PROJECTS = frozenset({"es.wikipedia", "pt.wikipedia"})
OUT_NAME = "wiki_pageviews_ai_daily"
SCHEMA: dict[str, pl.DataType] = {
    "topic_id": pl.String,
    "project": pl.String,
    "article": pl.String,
    "dt": pl.String,
    "views": pl.Int64,
}
_TOPIC = re.compile(r"^ai:[a-z]+:[a-z0-9_.+-]+$")
log = logging.getLogger(__name__)


def records(lexicon: dict[str, Any]) -> list[dict[str, Any]]:
    """WS6's record shape: the topic id stands in for the QID, titles per language."""
    out = []
    for entry in lexicon["entries"]:
        wiki = entry.get("wikipedia") or {}
        if not (wiki.get("es") or wiki.get("pt")):
            continue
        out.append(
            {
                "qid": f"ai:{entry['id']}",
                "article_es": wiki.get("es") or None,
                "article_pt": wiki.get("pt") or None,
            }
        )
    return out


def check(rows: list[dict[str, Any]]) -> list[str]:
    """The table's rules (no contract yet: the orchestrator owns contracts/)."""
    errors = []
    for i, r in enumerate(rows):
        if not _TOPIC.match(r["topic_id"] or ""):
            errors.append(f"row {i}: topic_id {r['topic_id']!r} is not an ai: lexicon id")
        if r["project"] not in PROJECTS:
            errors.append(f"row {i}: project {r['project']!r} is not es or pt Wikipedia")
        if not isinstance(r["views"], int) or isinstance(r["views"], bool) or r["views"] < 0:
            errors.append(f"row {i}: views {r['views']!r} is not a count")
        try:
            date.fromisoformat(r["dt"])
        except (TypeError, ValueError):
            errors.append(f"row {i}: dt {r['dt']!r} is not an ISO date")
    return errors


def write(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    """`fetch_pageviews` rows (`qid` = topic id) -> the AI pageview table; returns its row count."""
    out = [
        {"topic_id": r["qid"], "project": r["project"], "article": r["article"]}
        | {"dt": r["dt"], "views": r["views"]}
        for r in rows
    ]
    if errors := check(out):
        raise RuntimeError(f"{OUT_NAME} failed its checks:\n" + "\n".join(errors[:20]))
    path = path or lake() / "gold" / f"{OUT_NAME}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(out, schema=SCHEMA).with_columns(pl.col("dt").str.to_date())
    tmp = path.with_suffix(".parquet.tmp")
    frame.write_parquet(tmp)
    tmp.replace(path)
    return frame.height


def main(argv: list[str] | None = None) -> int:
    from models.source import lexicon, lexicon_path

    from crosssource.pageviews import article_keys, fetch_pageviews

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="count the requests; fetch nothing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    recs = records(lexicon())
    keys = article_keys(recs, projects=PROJECTS)
    n_topics = len(lexicon()["entries"])
    print(  # noqa: T201
        f"lexicon {lexicon_path()}: {n_topics} entries, {len(recs)} with an es or pt title, "
        f"{len(keys)} pages -> about {len(keys) * 6.5 / 60:.0f} min at 6.5 s per request"
    )
    if args.dry_run:
        return 0

    from entity.client import WikimediaClient

    stats: dict[str, int] = {}
    with WikimediaClient.open() as client:
        rows, end = fetch_pageviews(
            client,
            recs,
            projects=PROJECTS,
            on_checkpoint=lambda snapshot, _end: write(snapshot),
            stats=stats,
        )
    n = write(rows)
    print(  # noqa: T201
        f"{OUT_NAME}: {n} rows through {end}; {stats.get('ok', 0)}/{stats.get('attempted', 0)} "
        "pages answered 200"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
