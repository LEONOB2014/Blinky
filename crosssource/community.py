"""The AI community sensor: what researchers, practitioners, builders and critics publish,
matched to the AI lexicon (contracts/ai_lexicon.yaml).

Public APIs and feeds only, at a polite rate with an identifying User-Agent:
- RSS/Atom feeds (newsletters, lab and NVIDIA blogs, safety and critic organisations);
- the Hugging Face daily papers API (by date, with upvotes) and models API (new releases);
- the YouTube Data API (a channel's uploads; YOUTUBE_API_KEY), else the channel's public RSS;
- Y Combinator's Requests for Startups (the current page plus quarterly Wayback snapshots);
- The Batch's issue links from the deeplearning.ai sitemap (robots.txt allows general agents).

The source registry lives in the git-ignored lake (lake/manual/community_sources.yaml), because
some sources are named after people: person names never enter git. Item titles stay in the lake.

Output: lake/raw/community/items.parquet and lake/gold/community_topic_weekly.parquet
(topic_id, week, category, n_items, n_sources, score). A separate, unvalidated signal: most feeds
keep a short history, so it is never part of the backtest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl
import yaml
from defusedxml.ElementTree import ParseError as XMLParseError
from defusedxml.ElementTree import fromstring as safe_fromstring

from radar import paths

UA = "radar-30x/0.3 (+https://radar-senal-temprana.netlify.app; public feeds only)"
LEXICON = Path(__file__).resolve().parents[1] / "contracts" / "ai_lexicon.yaml"
PAUSE_S = 1.0


def _today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _get(client: httpx.Client, endpoint: str, **params: Any) -> httpx.Response | None:
    try:
        r = client.get(endpoint, params=params or None, timeout=30, follow_redirects=True)
    except httpx.HTTPError:
        return None
    time.sleep(PAUSE_S)
    return r if r.status_code == 200 else None


def _date(text: str | None) -> dt.date | None:
    if not text:
        return None
    text = text.strip()
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError):
        pass
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clean(text: str | None, limit: int = 600) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _item(
    src: dict, day: dt.date | None, title: str, summary: str = "", url: str = "", score: float = 0.0
) -> dict:
    return {
        "source_id": src["id"],
        "category": src["category"],
        "kind": src["kind"],
        "day": day,
        "title": _clean(title, 300),
        "summary": _clean(summary),
        "url": url,
        "score": float(score or 0),
    }


def fetch_rss(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    r = _get(client, src["url"])
    if r is None:
        return []
    try:
        root = safe_fromstring(r.content)
    except (XMLParseError, ValueError):
        return []
    out = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue
        get = {c.tag.rsplit("}", 1)[-1]: c for c in node}
        title = (get["title"].text if "title" in get else "") or ""
        day = None
        for key in ("pubDate", "published", "updated", "date"):
            if key in get:
                day = _date(get[key].text)
                break
        summary = ""
        for key in ("description", "summary", "content"):
            if key in get:
                summary = get[key].text or ""
                break
        link = get.get("link")
        url = (link.get("href") or link.text or "") if link is not None else ""
        if day and day >= since:
            out.append(_item(src, day, title, summary, url))
    return out


def fetch_hf_papers(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    out, day = [], since
    while day <= _today():
        r = _get(client, "https://huggingface.co/api/daily_papers", date=day.isoformat())
        for p in r.json() if r is not None else []:
            paper = p.get("paper", {})
            out.append(
                _item(
                    src,
                    day,
                    paper.get("title", ""),
                    paper.get("summary", ""),
                    f"https://huggingface.co/papers/{paper.get('id', '')}",
                    paper.get("upvotes", 0),
                )
            )
        day += dt.timedelta(days=1)
    return out


def fetch_hf_models(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    out = []
    for author in src["authors"]:
        r = _get(
            client,
            "https://huggingface.co/api/models",
            author=author,
            sort="createdAt",
            direction=-1,
            limit=100,
        )
        for m in r.json() if r is not None else []:
            day = _date(m.get("createdAt"))
            if day and day >= since:
                tags = " ".join(m.get("tags", [])[:15])
                out.append(
                    _item(
                        src,
                        day,
                        f"{author} releases {m.get('id', '')}",
                        f"{m.get('pipeline_tag', '')} {tags}",
                        f"https://huggingface.co/{m.get('id', '')}",
                        m.get("likes", 0),
                    )
                )
    return out


def fetch_youtube(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:  # fallback: the channel's public RSS feed (its latest 15 videos)
        feed = {
            **src,
            "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={src['channel_id']}",
        }
        return fetch_rss(client, feed, since) if src.get("channel_id") else []
    api = "https://www.googleapis.com/youtube/v3"
    r = _get(
        client,
        f"{api}/channels",
        part="contentDetails",
        forHandle="@" + src["handle"].lstrip("@"),
        key=key,
    )
    items = r.json().get("items", []) if r is not None else []
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out, token = [], None
    for _ in range(20):
        params = {"part": "snippet", "playlistId": uploads, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        r = _get(client, f"{api}/playlistItems", **params)
        if r is None:
            break
        data = r.json()
        oldest = None
        for v in data.get("items", []):
            s = v["snippet"]
            day = _date(s.get("publishedAt"))
            oldest = day
            if day and day >= since:
                out.append(
                    _item(
                        src,
                        day,
                        s.get("title", ""),
                        s.get("description", "")[:600],
                        "https://www.youtube.com/watch?v="
                        + s.get("resourceId", {}).get("videoId", ""),
                    )
                )
        token = data.get("nextPageToken")
        if not token or (oldest and oldest < since):
            break
    return out


_RFS_SKIP = re.compile(r"^(we'd love|if you're|so if|we want|there has never)", re.I)


def _rfs_items(page: str) -> list[tuple[str, str]]:
    """(title, body) per RFS request; author names (short lines after a title) are dropped."""
    s = html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S))
    lines = [ln.strip() for ln in re.sub(r"<[^>]+>", "\n", s).split("\n") if len(ln.strip()) > 1]
    out, i = [], 0
    while i < len(lines) - 3:
        title, a, b = lines[i], lines[i + 1], lines[i + 2]
        nav = re.match(r"^(fall|summer|spring|winter) \d{4}$|^startup jobs$|^log in$", title, re.I)
        is_title = (
            not nav
            and 2 <= len(title.split()) <= 9
            and not title.endswith((".", "!", "?", ":"))
            and title[0].isupper()
        )
        names = len(a.split()) <= 3 and len(b.split()) <= 6 and not a.endswith(".")
        if is_title and names:
            j = i + 3
            while j < min(i + 5, len(lines)) and len(lines[j].split()) <= 9:
                j += 1  # author names and titles: dropped, persons never enter the data
            body = []
            while j < len(lines) and len(lines[j].split()) > 9:
                if not _RFS_SKIP.match(lines[j]):
                    body.append(lines[j])
                j += 1
            if body:
                out.append((title, " ".join(body)[:1500]))
                i = j
                continue
        i += 1
    return out


def fetch_yc_rfs(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    out = []
    r = _get(client, "https://www.ycombinator.com/rfs")
    if r is not None:
        out += [
            _item(src, _today(), t, b, "https://www.ycombinator.com/rfs")
            for t, b in _rfs_items(r.text)
        ]
    cdx = _get(
        client,
        "http://web.archive.org/cdx/search/cdx",
        url="ycombinator.com/rfs",
        output="json",
        filter="statuscode:200",
        collapse="timestamp:6",
        **{"from": since.strftime("%Y%m")},
    )
    rows = cdx.json()[1:] if cdx is not None else []
    seen = {i["title"] for i in out}
    for row in rows[::3]:  # about one snapshot per quarter
        snap = _get(
            client, f"http://web.archive.org/web/{row[1]}id_/https://www.ycombinator.com/rfs"
        )
        if snap is None:
            continue
        day = dt.datetime.strptime(row[1][:8] + "+0000", "%Y%m%d%z").date()
        for t, b in _rfs_items(snap.text):
            if t not in seen:
                seen.add(t)
                out.append(_item(src, day, t, b, "https://www.ycombinator.com/rfs"))
    return out


def fetch_sitemap(client: httpx.Client, src: dict, since: dt.date) -> list[dict]:
    r = _get(client, src["url"])
    if r is None:
        return []
    out = []
    for loc, lastmod in re.findall(r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", r.text):
        if src["path"] not in loc:
            continue
        day = _date(lastmod)
        slug = loc.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        if day is None or day >= since:
            out.append(_item(src, day, slug, "", loc))
    return out


FETCHERS = {
    "rss": fetch_rss,
    "hf_papers": fetch_hf_papers,
    "hf_models": fetch_hf_models,
    "youtube": fetch_youtube,
    "yc_rfs": fetch_yc_rfs,
    "sitemap": fetch_sitemap,
}


def match_lexicon(items: pl.DataFrame, lexicon_path: Path = LEXICON) -> pl.DataFrame:
    """One row per (item, lexicon entry) whose pattern matches the item's title and summary."""
    entries = yaml.safe_load(lexicon_path.read_text(encoding="utf-8"))["entries"]
    compiled = [(f"ai:{e['id']}", [re.compile(p) for p in e["patterns"]]) for e in entries]
    rows = []
    for it in items.iter_rows(named=True):
        text = (
            f"{it['title']} {it['summary']}".lower()
        )  # not the URL: every HF paper URL says huggingface
        for topic_id, pats in compiled:
            if any(p.search(text) for p in pats):
                rows.append({**it, "topic_id": topic_id})
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def weekly(matched: pl.DataFrame) -> pl.DataFrame:
    """community_topic_weekly: items, sources and score per topic, week and category."""
    if matched.is_empty():
        return matched
    dated = matched.filter(pl.col("day").is_not_null()).with_columns(
        pl.col("day")
        .map_elements(
            lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}", return_dtype=pl.Utf8
        )
        .alias("week")
    )
    return (
        dated.group_by("topic_id", "week", "category")
        .agg(
            pl.len().alias("n_items"),
            pl.col("source_id").n_unique().alias("n_sources"),
            pl.col("score").sum(),
        )
        .sort("week", "topic_id")
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", default=str(paths.lake() / "manual" / "community_sources.yaml"))
    ap.add_argument("--weeks", type=int, default=13)
    ap.add_argument("--only", nargs="*", help="source ids to fetch (default: all)")
    ap.add_argument("--rematch", action="store_true", help="re-match the saved items, no fetching")
    args = ap.parse_args()
    raw = paths.lake() / "raw" / "community"
    if args.rematch:
        out = weekly(match_lexicon(pl.read_parquet(raw / "items.parquet")))
        out.write_parquet(paths.lake() / "gold" / "community_topic_weekly.parquet")
        print(f"{out.height} topic-week-category rows (measured)")
        return
    since = _today() - dt.timedelta(weeks=args.weeks)
    sources = yaml.safe_load(Path(args.sources).read_text(encoding="utf-8"))["sources"]
    items: list[dict] = []
    with httpx.Client(headers={"User-Agent": UA}) as client:
        for src in sources:
            if args.only and src["id"] not in args.only:
                continue
            got = FETCHERS[src["kind"]](client, src, since)
            print(f"{src['id']:28s} {src['category']:13s} {len(got):5d} items (measured)")
            items += got
    df = pl.DataFrame(items)
    raw.mkdir(parents=True, exist_ok=True)
    saved = raw / "items.parquet"
    if args.only and saved.exists():  # a partial fetch replaces only those sources' items
        kept = pl.read_parquet(saved).filter(~pl.col("source_id").is_in(args.only))
        df = pl.concat([kept, df], how="diagonal_relaxed") if df.height else kept
    df.write_parquet(raw / "items.parquet")
    matched = match_lexicon(df)
    out = weekly(matched)
    out.write_parquet(paths.lake() / "gold" / "community_topic_weekly.parquet")
    print(
        f"{df.height} items; {matched.height} item-topic matches; "
        f"{out.height} topic-week-category rows (measured)"
    )


if __name__ == "__main__":
    main()
