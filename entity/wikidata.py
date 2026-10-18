"""Resolve ranked topics to Wikidata and to es/pt/en Wikipedia articles.

Uses the Wikidata ``wbsearchentities`` API in Spanish, English and Portuguese, then a P31
(instance of) check. Persons are never resolved. Responses are cached under ``lake/raw/wikidata/``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from entity.claims import claim_ids
from entity.client import WikimediaClient
from entity.tables import write_parquet
from radar.contracts import validate_records
from radar.paths import REPO_ROOT, lake

log = logging.getLogger(__name__)

BOGOTA = ZoneInfo("America/Bogota")

# P31 / P279 roots. Labels were read from Wikidata on 2026-10-17 (measured).
# Company-like classes are the ones Wikidata actually puts on companies.
ALLOWED_ROOTS = frozenset(
    {
        "Q43229",  # organization
        "Q783794",  # company
        "Q4830453",  # business
        "Q891723",  # public company
        "Q6881511",  # enterprise
        "Q18388277",  # technology company
        "Q21980538",  # commercial organization
        "Q7397",  # software
        "Q166142",  # application software
        "Q151885",  # concept
        "Q11862829",  # academic discipline
        "Q1047113",  # field of study
        # Label measured 2026-10-17: artificial intelligence. Its parents are computer
        # science, emerging technology and reasoning, so the bounded walk never reaches
        # field-of-study. Subclasses (AI agent, AI in healthcare) are the topic itself.
        "Q11660",
    }
)
# Direct P31 values that are not an organization, company, software or concept.
REJECT_ROOTS = frozenset(
    {
        "Q5",  # human
        "Q6256",  # country
        "Q3624078",  # sovereign state
    }
)
# Rule-assigned match scores (estimate), not a calibrated probability.
EXACT_CONFIDENCE = 0.9
ALIAS_CONFIDENCE = 0.6

# Search strings in addition to the taxonomy's Spanish label. Not QIDs.
SUBTOPIC_QUERIES: dict[str, tuple[tuple[str, str], ...]] = {
    "agents": (("en", "AI agent"), ("pt", "agente de IA")),
    "llms_models": (
        ("es", "gran modelo de lenguaje"),
        ("en", "large language model"),
        ("pt", "grande modelo de linguagem"),
    ),
    "chips_infra": (("en", "AI accelerator"), ("pt", "acelerador de IA")),
    "regulation_policy": (
        ("es", "regulación de la inteligencia artificial"),
        ("en", "regulation of artificial intelligence"),
        ("pt", "regulação da inteligência artificial"),
    ),
    "education": (("en", "education"), ("pt", "educação")),
    "jobs_work": (("es", "empleo"), ("en", "employment"), ("pt", "emprego")),
    "business_adoption": (
        ("es", "adopción de tecnología"),
        ("en", "technology adoption"),
        ("pt", "adoção de tecnologia"),
    ),
    "safety_risk": (
        ("es", "seguridad de la inteligencia artificial"),
        ("en", "AI safety"),
        ("pt", "segurança da inteligência artificial"),
    ),
    "creative_media": (
        ("es", "inteligencia artificial generativa"),
        ("en", "generative artificial intelligence"),
        ("pt", "inteligência artificial generativa"),
    ),
    "health_science": (
        ("es", "inteligencia artificial en la medicina"),
        ("en", "artificial intelligence in healthcare"),
        ("pt", "inteligência artificial na saúde"),
    ),
    "funding_markets": (
        ("es", "capital riesgo"),
        ("en", "venture capital"),
        ("pt", "capital de risco"),
    ),
    "energy_climate": (
        ("es", "impacto ambiental de la inteligencia artificial"),
        ("en", "environmental impact of artificial intelligence"),
        ("pt", "impacto ambiental da inteligência artificial"),
    ),
}

TOPIC_SCHEMA: dict[str, pl.DataType] = {
    "topic_id": pl.String,
    "qid": pl.String,
    "label_es": pl.String,
    "article_es": pl.String,
    "article_pt": pl.String,
    "article_en": pl.String,
    "match": pl.String,
    "confidence": pl.Float64,
}


@dataclass(frozen=True)
class SearchHit:
    qid: str
    label: str
    match_type: str
    match_text: str
    language: str
    query: str


@dataclass(frozen=True)
class EntityView:
    qid: str
    label_es: str | None
    article_es: str | None
    article_pt: str | None
    article_en: str | None
    p31: tuple[str, ...]
    p279: tuple[str, ...]


@dataclass(frozen=True, order=True)
class Topic:
    priority: int
    sort_count: int
    topic_id: str
    kind: str
    queries: tuple[tuple[str, str], ...]


def norm(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold().strip()
    return re.sub(r"\s+", " ", folded)


def parse_search(payload: dict[str, Any]) -> list[SearchHit]:
    """Turn one ``wbsearchentities`` payload into hits. The query is the one the API echoed."""
    query = str((payload.get("searchinfo") or {}).get("search") or "")
    hits: list[SearchHit] = []
    for item in payload.get("search") or []:
        qid = item.get("id")
        match = item.get("match") or {}
        if not isinstance(qid, str) or not qid.startswith("Q"):
            continue
        hits.append(
            SearchHit(
                qid=qid,
                label=str(item.get("label") or ""),
                match_type=str(match.get("type") or ""),
                match_text=str(match.get("text") or ""),
                language=str(match.get("language") or ""),
                query=query,
            )
        )
    return hits


def match_kind(hit: SearchHit) -> str:
    """``exact`` when the Wikidata label itself equals the query; otherwise ``alias``."""
    same_label = norm(hit.label) == norm(hit.query)
    same_text = norm(hit.match_text) == norm(hit.query)
    if hit.match_type == "label" and (same_label or same_text):
        return "exact"
    return "alias"


def order_hits(hits: list[SearchHit]) -> list[SearchHit]:
    """One hit per QID, exact label matches first, keeping the API's order on ties."""
    best: dict[str, tuple[int, SearchHit]] = {}
    for index, hit in enumerate(hits):
        current = best.get(hit.qid)
        if current is None or _rank(hit) < _rank(current[1]):
            best[hit.qid] = (index, hit)
    ordered = sorted(best, key=lambda qid: (_rank(best[qid][1]), best[qid][0]))
    return [best[qid][1] for qid in ordered]


def _rank(hit: SearchHit) -> tuple[int, int]:
    return (0 if match_kind(hit) == "exact" else 1, 0 if hit.match_type == "label" else 1)


def parse_entity_payload(payload: dict[str, Any], qid: str | None = None) -> EntityView | None:
    entities = payload.get("entities") or {}
    if qid is None:
        if len(entities) != 1:
            return None
        qid = next(iter(entities))
    entity = entities.get(qid)
    if not isinstance(entity, dict) or entity.get("missing"):
        return None
    labels = entity.get("labels") or {}
    sitelinks = entity.get("sitelinks") or {}

    def title(site: str) -> str | None:
        node = sitelinks.get(site)
        if isinstance(node, dict) and isinstance(node.get("title"), str):
            return node["title"]
        return None

    label_es = labels.get("es") if isinstance(labels, dict) else None
    return EntityView(
        qid=qid,
        label_es=label_es.get("value") if isinstance(label_es, dict) else None,
        article_es=title("eswiki"),
        article_pt=title("ptwiki"),
        article_en=title("enwiki"),
        p31=claim_ids(entity, "P31"),
        p279=claim_ids(entity, "P279"),
    )


# Labels measured on Wikidata, 2026-10-17. Walking through these makes every item a type of thing.
_META_CLASSES = frozenset({"Q21146257", "Q16889133", "Q19478619"})
_MAX_WALK_NODES = 40


def classify(p31: tuple[str, ...], p279: tuple[str, ...], parents) -> str:
    """``ok``, ``person`` or ``reject``. Persons are rejected even when another class matches."""
    direct = set(p31)
    if "Q5" in direct:
        return "person"
    if direct & REJECT_ROOTS:
        return "reject"
    # A direct organization, company, software or concept needs no superclass walk.
    if direct & ALLOWED_ROOTS:
        return "ok"
    # One bounded walk. A class is often typed on P279 as well as on P31.
    frontier = {qid for qid in (*p31, *p279) if qid not in _META_CLASSES}
    seen: set[str] = set()
    for _ in range(5):
        if "Q5" in frontier:
            return "person"
        if frontier & ALLOWED_ROOTS:
            return "ok"
        if len(seen | frontier) > _MAX_WALK_NODES:
            return "reject"
        seen |= frontier
        nxt: set[str] = set()
        for qid in frontier:
            nxt.update(parents(qid))
        nxt -= seen
        nxt -= _META_CLASSES
        if not nxt:
            return "reject"
        frontier = nxt
    return "reject"


def confidence(kind: str, hit: SearchHit, hits: list[SearchHit]) -> float:
    base = EXACT_CONFIDENCE if kind == "exact" else ALIAS_CONFIDENCE
    languages = {item.language for item in hits if item.qid == hit.qid and item.language}
    if len(languages) >= 2:
        return min(1.0, base + 0.05 * (len(languages) - 1))
    return base


def to_record(topic_id: str, entity: EntityView, match: str, score: float) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "qid": entity.qid,
        "label_es": entity.label_es,
        "article_es": entity.article_es,
        "article_pt": entity.article_pt,
        "article_en": entity.article_en,
        "match": match,
        "confidence": score,
    }


def none_record(topic_id: str) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "qid": None,
        "label_es": None,
        "article_es": None,
        "article_pt": None,
        "article_en": None,
        "match": "none",
        "confidence": 0.0,
    }


def _subtopic_queries(key: str, label_es: str) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    queries: list[tuple[str, str]] = []
    for lang, text in (("es", label_es), *SUBTOPIC_QUERIES.get(key, ())):
        token = (lang, norm(text))
        if not text.strip() or token in seen:
            continue
        seen.add(token)
        queries.append((lang, text.strip()))
    return tuple(queries)


def _org_counts(path: Path) -> Counter[str]:
    frame = pl.read_parquet(path, columns=["orgs"])
    counts: Counter[str] = Counter()
    for value in frame["orgs"].to_list():
        if not value:
            continue
        for part in str(value).split(";"):
            name = part.split(",", 1)[0].strip().lower()
            if name:
                counts[name] += 1
    return counts


def _edge_orgs(path: Path) -> set[str]:
    frame = pl.read_parquet(path, columns=["x", "y"])
    names: set[str] = set()
    for column in ("x", "y"):
        for value in frame[column].to_list():
            if isinstance(value, str) and value.startswith("org:"):
                name = value.removeprefix("org:").strip().lower()
                if name:
                    names.add(name)
    return names


def _org_topic(name: str, priority: int, count: int) -> Topic:
    return Topic(
        priority=priority,
        sort_count=-count,
        topic_id=f"org:{name}",
        kind="org",
        queries=(("en", name),),
    )


def load_dev_topics() -> list[Topic]:
    """The 12 subtopics plus organizations in the dev-slice fixtures."""
    tax = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
    topics: list[Topic] = []
    for index, (key, spec) in enumerate(tax["subtopics"].items()):
        topics.append(
            Topic(
                priority=0,
                sort_count=index,
                topic_id=key,
                kind="subtopic",
                queries=_subtopic_queries(key, spec["label_es"]),
            )
        )
    dev = REPO_ROOT / "fixtures" / "dev"
    counts = _org_counts(dev / "gkg_ai_sample.parquet")
    edges = _edge_orgs(dev / "edges_weekly.parquet")
    for name in sorted(edges | set(counts)):
        priority = 1 if name in edges else 2
        topics.append(_org_topic(name, priority, counts[name]))
    return sorted(topics)


def load_topic_daily_topics() -> list[Topic]:
    """Full ranked list, once WS1 has written ``lake/gold/topic_daily.parquet``."""
    path = lake() / "gold" / "topic_daily.parquet"
    if not path.exists():
        return []
    frame = pl.read_parquet(path, columns=["topic_id"])
    topics: list[Topic] = []
    for topic_id in frame["topic_id"].unique().to_list():
        if not isinstance(topic_id, str) or topic_id.startswith("per:"):
            continue
        if topic_id.startswith("org:"):
            name = topic_id.removeprefix("org:").strip().lower()
            if name:
                topics.append(_org_topic(name, 3, 0))
        elif topic_id.startswith("thm:"):
            text = topic_id.removeprefix("thm:").replace("_", " ").strip()
            if not text:
                continue
            topics.append(
                Topic(
                    priority=3,
                    sort_count=0,
                    topic_id=topic_id,
                    kind="theme",
                    queries=(("en", text), ("es", text), ("pt", text)),
                )
            )
    return topics


PRIORITY_PAGEVIEW_END = date(2026, 10, 18)
PRIORITY_PROJECTS = frozenset({"es.wikipedia", "pt.wikipedia"})
TOPIC_FIELDS = (
    "topic_id",
    "qid",
    "label_es",
    "article_es",
    "article_pt",
    "article_en",
    "match",
    "confidence",
)


def _ids_from_label(name: str) -> list[str]:
    frame = pl.read_parquet(lake() / "labels" / name, columns=["topic_id"])
    seen: set[str] = set()
    ids: list[str] = []
    for topic_id in frame["topic_id"].to_list():
        if isinstance(topic_id, str) and topic_id not in seen:
            seen.add(topic_id)
            ids.append(topic_id)
    return ids


def load_priority_ids() -> list[str]:
    """Topics the backtest actually scores: each method's weekly top 10."""
    return _ids_from_label("backtest_priority_topics.parquet")


def load_needed_ids() -> list[str]:
    """Topics the primary backtest still lacks after the priority list."""
    return _ids_from_label("ws4_backtest_needed_missing.parquet")


def order_exact_first(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exact matches, then aliases. Order inside each class stays as it was."""
    rank = {"exact": 0, "alias": 1}
    return sorted(records, key=lambda record: rank.get(str(record.get("match")), 2))


def topic_from_id(topic_id: str, subtopics: dict[str, Any]) -> Topic | None:
    """One ranked id, with the same search rules as the full resolver. Persons are skipped."""
    if topic_id.startswith("per:"):
        return None
    if topic_id.startswith("org:"):
        name = topic_id.removeprefix("org:").strip().lower()
        if not name:
            return None
        return _org_topic(name, 0, 0)
    if topic_id.startswith("thm:"):
        text = topic_id.removeprefix("thm:").replace("_", " ").strip()
        if not text:
            return None
        return Topic(
            priority=0,
            sort_count=0,
            topic_id=topic_id,
            kind="theme",
            queries=(("en", text), ("es", text), ("pt", text)),
        )
    spec = subtopics.get(topic_id)
    if isinstance(spec, dict):
        return Topic(
            priority=0,
            sort_count=0,
            topic_id=topic_id,
            kind="subtopic",
            queries=_subtopic_queries(topic_id, str(spec.get("label_es") or topic_id)),
        )
    return None


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {field: record.get(field) for field in TOPIC_FIELDS}
    if not cleaned.get("qid"):
        cleaned["qid"] = None
        cleaned["match"] = "none"
        cleaned["confidence"] = 0.0
    return cleaned


def _unresolved(record: dict[str, Any] | None) -> bool:
    return record is None or record.get("match") == "none" or not record.get("qid")


def load_topics() -> tuple[list[Topic], set[str]]:
    dev = load_dev_topics()
    by_id = {topic.topic_id: topic for topic in dev}
    dev_ids = set(by_id)
    for topic in load_topic_daily_topics():
        by_id.setdefault(topic.topic_id, topic)
    return sorted(by_id.values()), dev_ids


def _accept(
    client: WikimediaClient,
    topics: list[Topic],
    hit_lists: list[list[SearchHit]],
) -> list[tuple[SearchHit, EntityView] | None]:
    chosen: list[tuple[SearchHit, EntityView] | None] = [None] * len(topics)
    resolved = [False] * len(topics)
    verdicts: dict[tuple[tuple[str, ...], tuple[str, ...]], str] = {}
    rounds = max((len(hits) for hits in hit_lists), default=0)
    rounds = min(rounds, 3)
    for round_index in range(rounds):
        wanted: list[tuple[int, SearchHit]] = []
        for index, hits in enumerate(hit_lists):
            if resolved[index] or round_index >= len(hits):
                continue
            wanted.append((index, hits[round_index]))
        if not wanted:
            continue
        payloads = client.entities([hit.qid for _, hit in wanted])
        for index, hit in wanted:
            payload = payloads.get(hit.qid)
            entity = None if payload is None else parse_entity_payload(payload, hit.qid)
            if entity is None:
                continue
            key = (entity.p31, entity.p279)
            if key not in verdicts:
                verdicts[key] = classify(entity.p31, entity.p279, client.parents)
            if verdicts[key] != "ok":
                continue
            chosen[index] = (hit, entity)
            resolved[index] = True
        log.info("entity round %s: accepted %s/%s", round_index + 1, sum(resolved), len(topics))
    return chosen


def _fallback_topic(topic: Topic) -> Topic:
    name = topic.topic_id.removeprefix("org:")
    seen = {(lang, norm(text)) for lang, text in topic.queries}
    extra = [(lang, name) for lang in ("es", "pt") if (lang, norm(name)) not in seen]
    return Topic(
        priority=topic.priority,
        sort_count=topic.sort_count,
        topic_id=topic.topic_id,
        kind=topic.kind,
        queries=topic.queries + tuple(extra),
    )


def _record_for(
    topic: Topic,
    choice: tuple[SearchHit, EntityView] | None,
    hits: list[SearchHit],
) -> dict[str, Any]:
    if choice is None:
        return none_record(topic.topic_id)
    hit, entity = choice
    kind = match_kind(hit)
    return to_record(topic.topic_id, entity, kind, confidence(kind, hit, hits))


def _search_raw(client: WikimediaClient, topic: Topic) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for language, query in topic.queries:
        payload = client.search(query, language)
        if payload is not None:
            hits.extend(parse_search(payload))
    return hits


def resolve_topics(client: WikimediaClient, topics: list[Topic]) -> list[dict[str, Any]]:
    raw_lists: list[list[SearchHit]] = []
    hit_lists: list[list[SearchHit]] = []
    for index, topic in enumerate(topics, start=1):
        raw = _search_raw(client, topic)
        raw_lists.append(raw)
        hit_lists.append(order_hits(raw)[:3])
        if index % 25 == 0 or index == len(topics):
            log.info("searched %s/%s", index, len(topics))
    chosen = _accept(client, topics, hit_lists)
    retry = [
        index
        for index, topic in enumerate(topics)
        if chosen[index] is None and topic.kind == "org" and not raw_lists[index]
    ]
    if retry:
        log.info("no English hit for %s orgs; searching es and pt", len(retry))
        retry_topics = [_fallback_topic(topics[index]) for index in retry]
        retry_raw = [_search_raw(client, topic) for topic in retry_topics]
        retry_hits = [order_hits(hits)[:3] for hits in retry_raw]
        retry_choice = _accept(client, retry_topics, retry_hits)
        for index, raw, choice in zip(retry, retry_raw, retry_choice, strict=True):
            raw_lists[index] = raw
            chosen[index] = choice
    return [
        _record_for(topic, choice, raw)
        for topic, choice, raw in zip(topics, chosen, raw_lists, strict=True)
    ]


def write_topic_tables(records: list[dict[str, Any]], dev_ids: set[str]) -> None:
    errors = validate_records("topic_wikidata", records)
    if errors:
        raise RuntimeError("topic_wikidata failed validation:\n" + "\n".join(errors[:20]))
    write_parquet(lake() / "gold" / "topic_wikidata.parquet", records, TOPIC_SCHEMA)
    dev_records = [record for record in records if record["topic_id"] in dev_ids]
    dev_errors = validate_records("topic_wikidata", dev_records)
    if dev_errors:
        raise RuntimeError("dev cut failed validation:\n" + "\n".join(dev_errors[:20]))
    write_parquet(lake() / "devcut" / "topic_wikidata.parquet", dev_records, TOPIC_SCHEMA)


def summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "attempted": len(records),
        "exact": sum(record["match"] == "exact" for record in records),
        "alias": sum(record["match"] == "alias" for record in records),
        "none": sum(record["match"] == "none" for record in records),
        "article_es": sum(bool(record["article_es"]) for record in records),
        "article_pt": sum(bool(record["article_pt"]) for record in records),
        "article_en": sum(bool(record["article_en"]) for record in records),
    }


def write_status(
    records: list[dict[str, Any]],
    *,
    pageview_rows: int | None,
    devcut_rows: int | None,
    failed: int,
    pageview_end: str | None,
    done: bool,
    note: str = "",
    extra: list[str] | None = None,
) -> None:
    counts = summary(records) if records else {}
    now = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M UTC-5")
    pageviews = "not fetched yet" if pageview_rows is None else str(pageview_rows)
    dev_pageviews = "not fetched yet" if devcut_rows is None else str(devcut_rows)
    end = pageview_end or "not fetched yet"
    state = "Done" if done else "In progress"
    if done:
        running = note or "Dev-slice topics and their pageviews are written."
    else:
        running = f"{note} Rerun is safe: responses are cached.".strip()
    daily = lake() / "gold" / "topic_daily.parquet"
    daily_state = "present" if daily.exists() else "absent"
    es = counts.get("article_es", 0)
    pt = counts.get("article_pt", 0)
    en = counts.get("article_en", 0)
    lines = [
        "# WS6 status",
        "",
        "Owner: Grok CLI · Directories: `entity/, crosssource/`",
        "",
        "Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).",
        "",
        "## Last update",
        "",
        f"{now}, branch `feat/ws6-wikipedia-pageviews`, PR not opened (needs approval)",
        "",
        "## Done",
        "",
        "- `entity/wikidata.py` resolves topics with wbsearchentities (es/en/pt) and a P31 check.",
        "- Persons are never resolved.",
        "- `crosssource/pageviews.py` fetches daily `agent=user` pageviews from 2025-10-01.",
        "- Gold and the 8-week dev cut (2026-08-24 .. 2026-10-17) land in the lake.",
        "- Unit tests parse one real cached response per endpoint.",
        "",
        "## In progress",
        "",
        f"- {running}",
        f"- Full `topic_daily` is included when the lake file exists. It was {daily_state}.",
        "",
        "## Blocked on",
        "",
        "## Numbers (each marked measured or estimate)",
        "",
        f"Phase: {state}.",
        "",
        f"- topics attempted: {counts.get('attempted', 0)} (measured)",
        f"- resolved exact: {counts.get('exact', 0)} (measured)",
        f"- resolved alias: {counts.get('alias', 0)} (measured)",
        f"- resolved none: {counts.get('none', 0)} (measured)",
        f"- articles found, es / pt / en: {es} / {pt} / {en} (measured)",
        f"- pageview rows in gold: {pageviews} (measured)",
        f"- pageview rows in the 8-week dev cut: {dev_pageviews} (measured)",
        f"- pageview end date returned by the API: {end} (measured)",
        f"- failed requests (final non-200): {failed} (measured)",
        *(extra or []),
        (
            f"- confidence rule: {EXACT_CONFIDENCE} exact, {ALIAS_CONFIDENCE} alias, "
            "+0.05 per extra language, cap 1 (estimate, not calibrated)"
        ),
        "",
    ]
    (REPO_ROOT / "status" / "WS6.md").write_text("\n".join(lines), encoding="utf-8")


def _records_from_gold() -> list[dict[str, Any]]:
    path = lake() / "gold" / "topic_wikidata.parquet"
    if not path.exists():
        return []
    frame = pl.read_parquet(path)
    records = frame.to_dicts()
    for record in records:
        if record.get("qid") is None:
            record["match"] = record.get("match") or "none"
    return records


def _priority_lines(
    priority_ids: list[str],
    priority_records: list[dict[str, Any]],
    pending: list[Topic],
    page_stats: dict[str, int],
    client: WikimediaClient,
    writes: list[str],
) -> list[str]:
    counts = summary(priority_records)
    return [
        f"- priority topics: {len(priority_ids)} (measured)",
        (
            f"- priority exact / alias / none: {counts['exact']} / "
            f"{counts['alias']} / {counts['none']} (measured)"
        ),
        f"- priority topics sent to Wikidata this run: {len(pending)} (measured)",
        (
            "- priority articles found, es / pt / en: "
            f"{counts['article_es']} / {counts['article_pt']} / {counts['article_en']} (measured)"
        ),
        (
            "- priority pageview articles attempted / HTTP 200: "
            f"{page_stats.get('attempted', 0)} / {page_stats.get('ok', 0)} (measured)"
        ),
        "- priority pageviews: es.wikipedia and pt.wikipedia, 2025-10-01 .. 2026-10-18",
        f"- HTTP 429: {client.stats['http_429']} (measured)",
        "- write times:",
        *[f"  - {line} (measured)" for line in writes],
    ]


def run_priority(
    client: WikimediaClient,
    dev_ids: set[str],
    hold: dict[str, Any],
) -> tuple[list[dict[str, Any]], int | None, int | None, str | None, str, list[str]]:
    """Resolve priority topics that are still `none`, then es/pt pageviews only."""
    from crosssource.pageviews import fetch_and_write

    priority_ids = load_priority_ids()
    by_id: dict[str, dict[str, Any]] = {}
    for row in _records_from_gold():
        cleaned = _clean_record(row)
        by_id[cleaned["topic_id"]] = cleaned
    tax = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
    subtopics = tax.get("subtopics") or {}
    pending: list[Topic] = []
    for topic_id in priority_ids:
        if not _unresolved(by_id.get(topic_id)):
            continue
        topic = topic_from_id(topic_id, subtopics)
        if topic is None:
            by_id[topic_id] = none_record(topic_id)
            continue
        pending.append(topic)
    log.info("priority topics %s still unresolved %s", len(priority_ids), len(pending))
    if pending:
        for record in resolve_topics(client, pending):
            by_id[record["topic_id"]] = record
    merged = list(by_id.values())
    write_topic_tables(merged, dev_ids)
    stamp = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M UTC-5")
    writes = [f"{stamp} topic_wikidata rows {len(merged)}"]
    log.info("wrote topic_wikidata rows %s at %s", len(merged), stamp)
    priority_records = [by_id[topic_id] for topic_id in priority_ids if topic_id in by_id]
    page_stats: dict[str, int] = {}
    progress_note = "Priority topics are written. es/pt pageviews have not started."

    def publish(
        *,
        done_flag: bool,
        note_text: str,
        rows: int | None,
        dev_rows: int | None,
        end: str | None,
    ) -> None:
        hold["records"] = merged
        hold["pageview_rows"] = rows
        hold["devcut_rows"] = dev_rows
        hold["pageview_end"] = end
        hold["done"] = done_flag
        hold["note"] = note_text
        hold["extra"] = _priority_lines(
            priority_ids,
            priority_records,
            pending,
            page_stats,
            client,
            writes,
        )

    publish(done_flag=False, note_text=progress_note, rows=None, dev_rows=None, end=None)

    def on_checkpoint(total: int, dev_total: int, end: date) -> None:
        write_topic_tables(merged, dev_ids)
        written = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M UTC-5")
        line = (
            f"{written} wiki_pageviews_daily rows {total} "
            f"(dev cut {dev_total}, end {end.isoformat()})"
        )
        writes.append(line)
        log.info("checkpoint %s", line)
        note_text = "Priority es/pt pageviews are in progress."
        publish(
            done_flag=False,
            note_text=note_text,
            rows=total,
            dev_rows=dev_total,
            end=end.isoformat(),
        )
        write_status(
            merged,
            pageview_rows=total,
            devcut_rows=dev_total,
            failed=client.stats["failed"],
            pageview_end=end.isoformat(),
            done=False,
            note=note_text,
            extra=hold["extra"],
        )

    pageview_rows, devcut_rows, pageview_end = fetch_and_write(
        client,
        priority_records,
        dev_ids,
        projects=PRIORITY_PROJECTS,
        today=PRIORITY_PAGEVIEW_END,
        on_checkpoint=on_checkpoint,
        stats=page_stats,
    )
    note = "Priority es/pt pageviews are written. Extras pageviews were not started."
    publish(
        done_flag=True,
        note_text=note,
        rows=pageview_rows,
        dev_rows=devcut_rows,
        end=pageview_end,
    )
    return merged, pageview_rows, devcut_rows, pageview_end, note, hold["extra"]


def _needed_lines(
    needed_ids: list[str],
    needed_records: list[dict[str, Any]],
    page_stats: dict[str, int],
    client: WikimediaClient,
    writes: list[str],
) -> list[str]:
    counts = summary(needed_records)
    return [
        f"- ws4 missing topics: {len(needed_ids)} (measured)",
        (
            f"- ws4 missing exact / alias / none: {counts['exact']} / "
            f"{counts['alias']} / {counts['none']} (measured)"
        ),
        (
            "- ws4 missing articles found, es / pt / en: "
            f"{counts['article_es']} / {counts['article_pt']} / {counts['article_en']} (measured)"
        ),
        (
            "- ws4 missing pageview articles attempted / HTTP 200: "
            f"{page_stats.get('attempted', 0)} / {page_stats.get('ok', 0)} (measured)"
        ),
        "- ws4 missing pageviews: exact matches first, then aliases; es and pt only",
        "- ws4 missing window: 2025-10-01 .. 2026-10-18",
        f"- HTTP 429: {client.stats['http_429']} (measured)",
        "- write times:",
        *[f"  - {line} (measured)" for line in writes],
    ]


def run_needed(
    client: WikimediaClient,
    dev_ids: set[str],
    hold: dict[str, Any],
) -> tuple[list[dict[str, Any]], int | None, int | None, str | None, str, list[str]]:
    """Pageviews for the 336 topics, exact matches first. Existing gold rows stay."""
    from crosssource.pageviews import fetch_and_write

    needed_ids = load_needed_ids()
    by_id = {record["topic_id"]: _clean_record(record) for record in _records_from_gold()}
    needed_records = order_exact_first(
        [by_id[topic_id] for topic_id in needed_ids if topic_id in by_id]
    )
    merged = list(by_id.values())
    absent = len(needed_ids) - len(needed_records)
    log.info(
        "ws4 missing topics %s ordered %s absent %s",
        len(needed_ids),
        summary(needed_records),
        absent,
    )
    write_topic_tables(merged, dev_ids)
    stamp = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M UTC-5")
    writes = [f"{stamp} topic_wikidata rows {len(merged)}"]
    log.info("wrote topic_wikidata rows %s at %s", len(merged), stamp)
    page_stats: dict[str, int] = {}

    def publish(
        *,
        done_flag: bool,
        note_text: str,
        rows: int | None,
        dev_rows: int | None,
        end: str | None,
    ) -> None:
        hold["records"] = merged
        hold["pageview_rows"] = rows
        hold["devcut_rows"] = dev_rows
        hold["pageview_end"] = end
        hold["done"] = done_flag
        hold["note"] = note_text
        hold["extra"] = _needed_lines(needed_ids, needed_records, page_stats, client, writes)

    publish(
        done_flag=False,
        note_text="WS4 missing es/pt pageviews have not started.",
        rows=None,
        dev_rows=None,
        end=None,
    )

    def on_checkpoint(total: int, dev_total: int, end: date) -> None:
        written = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M UTC-5")
        line = (
            f"{written} wiki_pageviews_daily rows {total} "
            f"(dev cut {dev_total}, end {end.isoformat()})"
        )
        writes.append(line)
        log.info("checkpoint %s", line)
        note_text = "WS4 missing es/pt pageviews are in progress. Exact matches go first."
        publish(
            done_flag=False,
            note_text=note_text,
            rows=total,
            dev_rows=dev_total,
            end=end.isoformat(),
        )
        write_status(
            merged,
            pageview_rows=total,
            devcut_rows=dev_total,
            failed=client.stats["failed"],
            pageview_end=end.isoformat(),
            done=False,
            note=note_text,
            extra=hold["extra"],
        )

    pageview_rows, devcut_rows, pageview_end = fetch_and_write(
        client,
        needed_records,
        dev_ids,
        projects=PRIORITY_PROJECTS,
        today=PRIORITY_PAGEVIEW_END,
        on_checkpoint=on_checkpoint,
        stats=page_stats,
        merge=True,
    )
    note = "WS4 missing es/pt pageviews are written. Exact matches were fetched first."
    publish(
        done_flag=True,
        note_text=note,
        rows=pageview_rows,
        dev_rows=devcut_rows,
        end=pageview_end,
    )
    return merged, pageview_rows, devcut_rows, pageview_end, note, hold["extra"]


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Resolve topics and fetch Wikipedia pageviews")
    parser.add_argument("--limit", type=int, default=0, help="resolve at most this many topics")
    parser.add_argument("--pageviews-only", action="store_true")
    parser.add_argument("--topics-only", action="store_true")
    parser.add_argument(
        "--priority",
        action="store_true",
        help="resolve unresolved backtest priority topics, then es/pt pageviews",
    )
    parser.add_argument(
        "--needed",
        action="store_true",
        help="es/pt pageviews for ws4_backtest_needed_missing, exact matches first",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    from crosssource.pageviews import fetch_and_write

    topics: list[Topic] = []
    dev_ids: set[str] = set()
    dev_topics: list[Topic] = []
    extra_topics: list[Topic] = []
    if not args.priority and not args.needed:
        topics, dev_ids = load_topics()
        if args.limit:
            topics = topics[: args.limit]
            dev_ids = {topic.topic_id for topic in topics}
        dev_topics = [topic for topic in topics if topic.topic_id in dev_ids]
        extra_topics = [topic for topic in topics if topic.topic_id not in dev_ids]
        log.info(
            "topics %s (dev %s, topic_daily extra %s)",
            len(topics),
            len(dev_topics),
            len(extra_topics),
        )
    records: list[dict[str, Any]] = []
    pageview_rows = None
    devcut_rows = None
    pageview_end = None
    done = False
    note = "Full resolve has not started."
    extra_lines: list[str] | None = None
    # Priority checkpoints mutate this so a later failure still reports them.
    hold: dict[str, Any] = {
        "records": records,
        "pageview_rows": pageview_rows,
        "devcut_rows": devcut_rows,
        "pageview_end": pageview_end,
        "done": done,
        "note": note,
        "extra": extra_lines,
    }
    with WikimediaClient.open() as client:
        try:
            if args.needed:
                dev_ids = {topic.topic_id for topic in load_dev_topics()}
                (
                    records,
                    pageview_rows,
                    devcut_rows,
                    pageview_end,
                    note,
                    extra_lines,
                ) = run_needed(client, dev_ids, hold)
                done = True
            elif args.priority:
                dev_ids = {topic.topic_id for topic in load_dev_topics()}
                (
                    records,
                    pageview_rows,
                    devcut_rows,
                    pageview_end,
                    note,
                    extra_lines,
                ) = run_priority(client, dev_ids, hold)
                done = True
            elif args.pageviews_only:
                records = _records_from_gold()
                note = "Pageviews only, using the gold topic table."
            else:
                # Wikidata first. Pageviews are on a slower limiter, so the topic
                # table does not wait behind a year of article fetches.
                records = resolve_topics(client, dev_topics)
                write_topic_tables(records, dev_ids)
                log.info("dev topic tables written: %s", summary(records))
                note = "Dev-slice topics are written. Pageviews have not been fetched."
                if extra_topics:
                    extra_records = resolve_topics(client, extra_topics)
                    records = records + extra_records
                    write_topic_tables(records, dev_ids)
                    log.info("full topic tables written: %s", summary(records))
                    note = "Full topic table is written. Pageviews have not been fetched."
            if not args.topics_only and not args.priority and not args.needed:
                dev_records = [row for row in records if row["topic_id"] in dev_ids]
                pageview_rows, devcut_rows, pageview_end = fetch_and_write(
                    client, dev_records, dev_ids
                )
                note = "Dev-slice pageviews are written."
                if len(dev_records) != len(records):
                    pageview_rows, devcut_rows, pageview_end = fetch_and_write(
                        client, records, dev_ids
                    )
                    note = "Full topic list and pageviews are written."
            done = True
        finally:
            if args.priority or args.needed:
                records = hold["records"]
                pageview_rows = hold["pageview_rows"]
                devcut_rows = hold["devcut_rows"]
                pageview_end = hold["pageview_end"]
                done = bool(hold["done"])
                note = str(hold["note"])
                extra_lines = hold["extra"]
            write_status(
                records,
                pageview_rows=pageview_rows,
                devcut_rows=devcut_rows,
                failed=client.stats["failed"],
                pageview_end=pageview_end,
                done=done,
                note=note,
                extra=extra_lines,
            )
            log.info("stats %s", dict(client.stats))


if __name__ == "__main__":
    main()
