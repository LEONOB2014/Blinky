"""Daily Wikipedia pageviews for resolved articles (the backtest label's raw series).

Wikimedia REST ``per-article``, ``agent=user``, ``access=all-access``, daily, es/pt/en,
from 2025-10-01 through today. Missing days are left out; they are not filled with zero.
Responses are cached under ``lake/raw/pageviews/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import polars as pl
from entity.client import WikimediaClient
from entity.tables import write_parquet

from radar.contracts import validate_records
from radar.paths import lake

log = logging.getLogger(__name__)

BOGOTA = ZoneInfo("America/Bogota")
PAGEVIEW_START = date(2025, 10, 1)
DEV_CUT_START = date(2026, 8, 24)
DEV_CUT_END = date(2026, 10, 17)
PROJECT_COLUMNS = (
    ("es.wikipedia", "article_es"),
    ("pt.wikipedia", "article_pt"),
    ("en.wikipedia", "article_en"),
)
PAGE_SCHEMA: dict[str, pl.DataType] = {
    "qid": pl.String,
    "project": pl.String,
    "article": pl.String,
    "dt": pl.String,
    "views": pl.Int64,
}


def timestamp_to_date(timestamp: str) -> str:
    parsed = datetime.strptime(timestamp, "%Y%m%d%H").replace(tzinfo=UTC)
    return parsed.date().isoformat()


def parse_pageviews(payload: dict[str, Any], *, qid: str) -> list[dict[str, Any]]:
    """One row per item the API returned. Days the API omitted are not invented."""
    rows: list[dict[str, Any]] = []
    allowed = {project for project, _column in PROJECT_COLUMNS}
    for item in payload.get("items") or []:
        project = item.get("project")
        article = item.get("article")
        views = item.get("views")
        timestamp = item.get("timestamp")
        if project not in allowed or not isinstance(article, str) or timestamp is None:
            continue
        if isinstance(views, bool) or not isinstance(views, int) or views < 0:
            continue
        rows.append(
            {
                "qid": qid,
                "project": project,
                "article": article,
                "dt": timestamp_to_date(str(timestamp)),
                "views": views,
            }
        )
    return rows


def article_keys(
    records: list[dict[str, Any]],
    *,
    projects: frozenset[str] | set[str] | None = None,
) -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    keys: list[tuple[str, str, str]] = []
    for record in records:
        qid = record.get("qid")
        if not isinstance(qid, str) or not qid:
            continue
        for project, column in PROJECT_COLUMNS:
            if projects is not None and project not in projects:
                continue
            title = record.get(column)
            if not isinstance(title, str) or not title:
                continue
            key = (qid, project, title)
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def pageview_url(project: str, title: str, start: date, end: date) -> str:
    article = quote(title.replace(" ", "_"), safe="")
    return (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{project}/all-access/user/{article}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00"
    )


def _cache_path(project: str, title: str, start: date, end: date):
    digest = hashlib.sha256(title.encode()).hexdigest()[:16]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", title)[:60]
    name = f"{safe}_{digest}_{start:%Y%m%d}_{end:%Y%m%d}.json"
    return lake() / "raw" / "pageviews" / project / name


def _looks_like_bad_end(status: int, body: bytes) -> bool:
    if status != 400:
        return False
    text = body.lower()
    return b"date" in text or b"timestamp" in text or b"future" in text


def pin_end(
    client: WikimediaClient,
    articles: list[tuple[str, str, str]],
    today: date,
) -> date:
    """Step the end date back while the API calls it invalid. 404 is a missing article."""
    end = today
    for _qid, project, title in articles[:8]:
        for _attempt in range(5):
            if end < PAGEVIEW_START:
                return PAGEVIEW_START
            status, body = client.get_bytes(
                pageview_url(project, title, PAGEVIEW_START, end),
                _cache_path(project, title, PAGEVIEW_START, end),
            )
            if status == 200:
                return end
            if _looks_like_bad_end(status, body):
                end -= timedelta(days=1)
                continue
            break
    return min(end, today)


def fetch_pageviews(
    client: WikimediaClient,
    records: list[dict[str, Any]],
    *,
    today: date | None = None,
    projects: frozenset[str] | set[str] | None = None,
    on_checkpoint: Any = None,
    stats: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], date]:
    today = today or datetime.now(BOGOTA).date()
    articles = article_keys(records, projects=projects)
    if stats is not None:
        stats["attempted"] = 0
        stats["ok"] = 0
    if not articles:
        return [], today
    end = pin_end(client, articles, today)
    log.info("pageview window %s .. %s for %s articles", PAGEVIEW_START, end, len(articles))
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, (qid, project, title) in enumerate(articles, start=1):
        status, body = client.get_bytes(
            pageview_url(project, title, PAGEVIEW_START, end),
            _cache_path(project, title, PAGEVIEW_START, end),
        )
        if stats is not None:
            stats["attempted"] += 1
            if status == 200:
                stats["ok"] += 1
        if status == 200 and body:
            try:
                parsed = parse_pageviews(json.loads(body), qid=qid)
            except json.JSONDecodeError:
                parsed = []
            for row in parsed:
                key = (row["qid"], row["project"], row["article"], row["dt"])
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        if index % 25 == 0 or index == len(articles):
            log.info("pageviews %s/%s rows %s", index, len(articles), len(rows))
        if on_checkpoint is not None and (index % 50 == 0 or index == len(articles)):
            snapshot = sorted(rows, key=lambda row: (row["qid"], row["project"], row["dt"]))
            on_checkpoint(snapshot, end)
    rows.sort(key=lambda row: (row["qid"], row["project"], row["dt"]))
    return rows, end


def write_pageview_tables(
    rows: list[dict[str, Any]],
    dev_qids: set[str],
) -> tuple[int, int]:
    errors = validate_records("wiki_pageviews_daily", rows)
    if errors:
        raise RuntimeError("wiki_pageviews_daily failed validation:\n" + "\n".join(errors[:20]))
    write_parquet(lake() / "gold" / "wiki_pageviews_daily.parquet", rows, PAGE_SCHEMA)
    dev_rows = [
        row
        for row in rows
        if row["qid"] in dev_qids and DEV_CUT_START <= date.fromisoformat(row["dt"]) <= DEV_CUT_END
    ]
    dev_errors = validate_records("wiki_pageviews_daily", dev_rows)
    if dev_errors:
        raise RuntimeError("pageview dev cut failed validation:\n" + "\n".join(dev_errors[:20]))
    write_parquet(lake() / "devcut" / "wiki_pageviews_daily.parquet", dev_rows, PAGE_SCHEMA)
    return len(rows), len(dev_rows)


def fetch_and_write(
    client: WikimediaClient,
    records: list[dict[str, Any]],
    dev_ids: set[str],
    *,
    projects: frozenset[str] | set[str] | None = None,
    today: date | None = None,
    on_checkpoint: Any = None,
    stats: dict[str, int] | None = None,
) -> tuple[int, int, str]:
    dev_qids = {
        record["qid"] for record in records if record.get("qid") and record["topic_id"] in dev_ids
    }

    def _write(snapshot: list[dict[str, Any]], end: date) -> None:
        total, dev_total = write_pageview_tables(snapshot, dev_qids)
        if on_checkpoint is not None:
            on_checkpoint(total, dev_total, end)

    rows, end = fetch_pageviews(
        client,
        records,
        today=today,
        projects=projects,
        on_checkpoint=_write if on_checkpoint is not None else None,
        stats=stats,
    )
    total, dev_total = write_pageview_tables(rows, dev_qids)
    return total, dev_total, end.isoformat()
