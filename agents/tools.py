"""Tools the agents call. Every tool reads real tables through `radar.paths.gold` (dev or full
profile) and returns plain JSON. When the table a tool needs does not exist yet, it says so
(`available: false` and the reason) instead of returning anything invented.
"""

import datetime as dt
import functools
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
import yaml
from jsonschema import Draft202012Validator

from agents import trust
from agents.trust import (  # noqa: F401 - re-exported for the agents and tests
    BQ_FREE_TIB_PER_MONTH,
    BQ_PRICE_SOURCE,
    BQ_USD_PER_TIB,
    TIB,
    backtest_summary,
    ledger_costs,
)
from radar.contracts import load_schema
from radar.paths import REPO_ROOT, lake, profile
from radar.paths import gold as _gold

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
Z_DISPLAY_CAP = 10.0  # z-scores above this are shown as ">10": tiny 28-day baselines inflate them


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


# The AI radar (WP2): with RADAR_SOURCE=ai the agents and the briefs read the AI lexicon run's
# tables (models/source.py writes them); a table with no AI variant in the lake falls back to the
# shared one, so S13/S14 rows for ai: topics may live in either. Briefs are always written to the
# AI name, so v0.2's briefs are never overwritten.
AI_TABLES = {
    "topic_scores_weekly": "topic_ai_scores_weekly",
    "topic_daily": "topic_ai_daily",
    "topic_sources_weekly": "topic_ai_sources_weekly",
    "topic_evidence_weekly": "topic_ai_evidence_weekly",
    "topic_briefs_weekly": "topic_ai_briefs_weekly",
}


def ai_source() -> bool:
    return os.environ.get("RADAR_SOURCE") == "ai"


def gold(name: str, *, write: bool = False) -> Path:
    """radar.paths.gold, switched to the AI run's table under RADAR_SOURCE=ai."""
    alt = AI_TABLES.get(name) if ai_source() else None
    if alt and (write or _gold(alt).exists()):
        return _gold(alt)
    return _gold(name)


def _table(name: str) -> str | None:
    path = gold(name)
    return str(path) if path.exists() else None


def _rows(
    sql: str, params: list[Any] | None = None, con: duckdb.DuckDBPyConnection | None = None
) -> list[dict[str, Any]]:
    cur = (con or _con()).execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        rec = {}
        for c, v in zip(cols, row, strict=True):
            if isinstance(v, dt.date | dt.datetime):
                v = v.isoformat()
            elif isinstance(v, float):
                v = round(v, 4)
            rec[c] = v
        out.append(rec)
    return out


def _unavailable(table: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": f"la tabla {table} todavía no existe en el perfil {profile()}",
    }


def week_bounds(week: str | None) -> tuple[str, dt.date, dt.date]:
    """ISO week label and its Monday..Sunday. None or an unparseable label -> latest week with data."""
    match = WEEK_RE.match(week or "")
    if match:
        monday = dt.date.fromisocalendar(int(match[1]), int(match[2]), 1)
    else:
        rolling = _table("daily_topic_rolling")
        latest = (
            _con().execute(f"SELECT max(dt) FROM '{rolling}'").fetchone()[0]  # noqa: S608
            if rolling
            else dt.datetime.now(dt.UTC).date()
        )
        monday = latest - dt.timedelta(days=latest.weekday())
    iso = monday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}", monday, monday + dt.timedelta(days=6)


@functools.cache
def labels_es() -> dict[str, str]:
    tax = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
    return {"ai_all": "IA en general"} | {k: v["label_es"] for k, v in tax["subtopics"].items()}


@functools.cache
def _ai_lexicon() -> tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]:
    """Each AI lexicon entry as (topic id, its name matchers): the entry's patterns, its GDELT org
    aliases and its Spanish label, all whole-word and case-insensitive (contracts/ai_lexicon.yaml)."""
    lex = yaml.safe_load((REPO_ROOT / "contracts" / "ai_lexicon.yaml").read_text(encoding="utf-8"))
    out = []
    for e in lex["entries"]:
        names = [*(e.get("gdelt_orgs") or []), e["label_es"]]
        matchers = [re.compile(p, re.I) for p in e["patterns"]]
        matchers += [re.compile(rf"(?<!\w){re.escape(n.lower())}(?!\w)", re.I) for n in names]
        out.append((f"ai:{e['id']}", tuple(matchers)))
    return tuple(out)


def ai_topic_in(text: str) -> str | None:
    """The AI lexicon topic a text names ('¿Qué está pasando con Nvidia?' -> 'ai:infra:nvidia'),
    only among topics the AI run scored; the longest match wins, ties go to the lexicon order."""
    path = gold("topic_scores_weekly")
    scored = set(_known_topics(str(path), path.stat().st_mtime)) if path.exists() else None
    best: tuple[int, str] | None = None
    for topic_id, matchers in _ai_lexicon():
        if scored is not None and topic_id not in scored:
            continue
        span = max((len(m.group(0)) for p in matchers if (m := p.search(text))), default=0)
        if span and (best is None or span > best[0]):
            best = (span, topic_id)
    return best[1] if best else None


def _cap(z: float | None) -> float | str | None:
    if z is None:
        return None
    return f">{Z_DISPLAY_CAP:g}" if z > Z_DISPLAY_CAP else z


@functools.cache
def _scores_frame(path: str, mtime: float) -> pl.DataFrame:
    # DuckDB 1.5 cannot filter this Polars-written file (PlainSkip on an all-null column), so it is
    # read whole with Polars (about 1 MB) and queried in memory.
    return pl.read_parquet(path)


def _scores_con() -> duckdb.DuckDBPyConnection | None:
    """A connection with WS4's table registered as `scores`, or None when it does not exist."""
    path = gold("topic_scores_weekly")
    if not path.exists():
        return None
    con = _con()
    con.register("scores", _scores_frame(str(path), path.stat().st_mtime).to_arrow())
    return con


@functools.cache
def _known_topics(path: str, mtime: float) -> tuple[str, ...]:
    rows = _con().execute(f"SELECT DISTINCT topic_id FROM '{path}'").fetchall()  # noqa: S608
    return tuple(r[0] for r in rows if not r[0].startswith("per:"))


def known_topics() -> tuple[str, ...]:
    """Every org/thm topic id with a 1-hop ring (else every ranked topic): what names resolve to."""
    for name in ("topic_context_1hop", "topic_daily"):
        path = gold(name)
        if path.exists():
            return _known_topics(str(path), path.stat().st_mtime)
    return ()


def resolve_topic(name: str) -> str:
    """'Nvidia' -> 'org:nvidia', 'OpenAI' -> 'org:openai group' (GDELT's own name); ids pass through.

    Exact id, then 'org:'/'thm:' + the name, then the shortest id whose name starts with it. Persons
    never resolve. Unknown names are returned unchanged, so the tool says it found nothing.
    """
    raw = name.strip()
    if raw in labels_es() or raw.startswith("per:"):
        return raw
    topics = set(known_topics())
    low = raw.lower()
    if low in topics:
        return low
    for prefix in ("org:", "thm:"):
        if prefix + low in topics:
            return prefix + low
    body = low.split(":", 1)[1] if low.startswith(("org:", "thm:")) else low
    # only a company suffix may follow ('openai' -> 'openai inc'), never more words: GDELT has
    # artefacts like 'org:altman to microsoft corp' that would drag a person's name in
    starts = [
        t
        for t in topics
        if t.startswith("org:" + body + " ") and t[4 + len(body) + 1 :] in _ORG_SUFFIXES
    ]
    return min(starts, key=len) if starts else raw


_ORG_SUFFIXES = frozenset(
    [
        "inc",
        "corp",
        "corporation",
        "co",
        "company",
        "group",
        "ltd",
        "llc",
        "plc",
        "sa",
        "ag",
        "holdings",
        "technologies",
        "platforms",
        "labs",
        "ai",
    ]
)


# --- Signal analyst ---------------------------------------------------------------------------


def list_subtopic_trends(week: str | None = None, lang_bucket: str = "all") -> dict[str, Any]:
    """7-day signals of every subtopic on the last day of the week with data."""
    table = _table("daily_topic_rolling")
    if not table:
        return _unavailable("daily_topic_rolling")
    label, monday, sunday = week_bounds(week)
    lang_filter = "" if lang_bucket == "all" else "AND lang_bucket = ?"
    params: list[Any] = [monday, sunday] + ([] if lang_bucket == "all" else [lang_bucket])
    rows = _rows(
        f"""
        WITH last AS (SELECT max(dt) d FROM '{table}' WHERE dt BETWEEN ? AND ? AND NOT is_missing)
        SELECT topic, sum(n_7d) AS articles_7d, avg(z_7d) AS z_7d, avg(growth_7d_log) AS growth_7d_log,
               avg(mean_tone_7d) AS mean_tone_7d, avg(controversy_7d) AS controversy_7d,
               max(dt) AS as_of
        FROM '{table}', last WHERE dt = last.d AND NOT latam {lang_filter}
        GROUP BY topic ORDER BY growth_7d_log DESC NULLS LAST""",  # noqa: S608
        params,
    )
    for r in rows:
        r["z_7d"] = _cap(r["z_7d"])
        r["label_es"] = labels_es().get(r["topic"], r["topic"])
    subtopics = [r for r in rows if r["topic"] != "ai_all" and r["growth_7d_log"] is not None]
    leader = subtopics[0]["topic"] if subtopics else None
    return {
        "available": True,
        "week": label,
        "lang_bucket": lang_bucket,
        "ordered_by": "growth_7d_log, de mayor a menor (calculado por código)",
        "fastest_growing_subtopic": leader,
        "rows": rows,
    }


def get_topic_series(topic: str, lang_bucket: str = "all", weeks: int = 8) -> dict[str, Any]:
    """Weekly articles, share and tone of one subtopic (or `ai_all`) or one org/theme topic."""
    topic = resolve_topic(topic)
    if topic.startswith(("org:", "thm:", "ai:")):
        return _entity_series(topic, lang_bucket, weeks)
    table = _table("daily_topic")
    if not table:
        return _unavailable("daily_topic")
    lang_filter = "" if lang_bucket == "all" else "AND lang_bucket = ?"
    params: list[Any] = [topic] + ([] if lang_bucket == "all" else [lang_bucket])
    rows = _rows(
        f"""
        SELECT strftime(date_trunc('week', dt), '%G-W%V') AS week, sum(n_articles) AS articles,
               sum(n_articles) / NULLIF(sum(n_all_stream), 0) AS share,
               sum(sum_tone) / NULLIF(sum(n_tone), 0) AS mean_tone,
               sum(n_neg_x) / NULLIF(sum(n_tone), 0) AS negative_share,
               sum(n_pos_x) / NULLIF(sum(n_tone), 0) AS positive_share,
               sum(CASE WHEN latam THEN n_articles ELSE 0 END) / NULLIF(sum(n_articles), 0) AS latam_share
        FROM '{table}' WHERE topic = ? AND NOT is_missing {lang_filter}
        GROUP BY 1 ORDER BY 1 DESC LIMIT {int(weeks)}""",  # noqa: S608
        params,
    )
    return {"available": True, "topic": topic, "lang_bucket": lang_bucket, "rows": rows[::-1]}


def _entity_series(topic: str, lang_bucket: str, weeks: int) -> dict[str, Any]:
    table = _table("topic_daily")
    if not table:
        return _unavailable("topic_daily")
    lang_filter = "" if lang_bucket == "all" else "AND lang_bucket = ?"
    params: list[Any] = [topic] + ([] if lang_bucket == "all" else [lang_bucket])
    rows = _rows(
        f"""
        SELECT strftime(date_trunc('week', dt), '%G-W%V') AS week, sum(n_articles) AS articles,
               sum(n_articles * mean_tone) / NULLIF(sum(CASE WHEN mean_tone IS NOT NULL
                   THEN n_articles END), 0) AS mean_tone
        FROM '{table}' WHERE topic_id = ? AND NOT is_missing {lang_filter}
        GROUP BY 1 ORDER BY 1 DESC LIMIT {int(weeks)}""",  # noqa: S608
        params,
    )
    return {"available": bool(rows), "topic": topic, "lang_bucket": lang_bucket, "rows": rows[::-1]}


def _days_with_data(monday: dt.date, sunday: dt.date) -> int | None:
    """Days of the week with Spanish and Portuguese data (daily_totals, is_missing excluded)."""
    table = _table("daily_totals")
    if not table:
        return None
    row = _rows(
        f"SELECT count(DISTINCT dt) AS days FROM '{table}' "  # noqa: S608
        "WHERE dt BETWEEN ? AND ? AND lang_bucket IN ('spa', 'por') AND NOT is_missing",
        [monday, sunday],
    )
    return row[0]["days"] if row else None


def get_language_coverage(topic: str, week: str | None = None) -> dict[str, Any]:
    """Articles of a topic in Spanish and Portuguese in a week, from get_topic_series (0 when the
    topic has articles that week but none in that language), and the days with data behind it."""
    total = get_topic_series(topic, "all", weeks=60)
    if not total.get("available") or not total.get("rows"):
        return {"available": False, "reason": f"no hay serie para {topic}"}
    label = week if week in {r["week"] for r in total["rows"]} else total["rows"][-1]["week"]

    def articles(lang: str) -> int:
        rows = get_topic_series(topic, lang, weeks=60).get("rows") or []
        return int(next((r["articles"] for r in rows if r["week"] == label), 0) or 0)

    _, monday, sunday = week_bounds(label)
    return {
        "available": True,
        "topic": total["topic"],
        "week": label,
        "articulos_es": articles("spa"),
        "articulos_pt": articles("por"),
        "articulos_total": int(next(r["articles"] for r in total["rows"] if r["week"] == label)),
        "dias_con_datos": _days_with_data(monday, sunday),
    }


@functools.cache
def ai_lexicon_entries() -> dict[str, dict[str, Any]]:
    """ai: topic id -> label_es, family (and its Spanish name) and stance, from the lexicon."""
    lex = yaml.safe_load((REPO_ROOT / "contracts" / "ai_lexicon.yaml").read_text(encoding="utf-8"))
    families = lex.get("families") or {}
    return {
        f"ai:{e['id']}": {
            "label_es": e["label_es"],
            "family": e["family"],
            "family_es": families.get(e["family"], e["family"]),
            "stance": e.get("stance"),
        }
        for e in lex["entries"]
    }


# The AI community sensor (crosssource/community.py): what researchers, practitioners, builders,
# critics and the media publish, matched to the lexicon. An unvalidated signal: most feeds keep a
# short history, so it never enters the backtest. Item titles stay in the lake; only counts here.
COMMUNITY_CATEGORIES_ES = {
    "research": "investigación",
    "practitioners": "practicantes",
    "builders": "constructores y aceleradoras",
    "vision": "visión y estrategia",
    "media": "medios especializados",
    "critics": "críticos",
}
COMMUNITY_TOP = 3


def get_community_signal(
    topic_id: str | None = None, week: str | None = None, category: str | None = None
) -> dict[str, Any]:
    """Measured community counts for a week: items and topics per category, the top topics of
    each category, and (for the critics) the topics whose lexicon stance is critic. Optionally
    for one topic or one category. Never item titles."""
    path = _gold("community_topic_weekly")
    if not path.exists():
        return _unavailable("community_topic_weekly")
    if category is not None and category not in COMMUNITY_CATEGORIES_ES:
        return {"available": False, "reason": f"categoría desconocida: {category}"}
    c = pl.read_parquet(path)
    weeks = sorted(c["week"].unique().to_list())
    label = week if week in weeks else weeks[-1]
    c = c.filter(pl.col("week") == label)
    if topic_id is not None:
        c = c.filter(pl.col("topic_id") == topic_id)
    if category is not None:
        c = c.filter(pl.col("category") == category)
    if c.is_empty():
        what = topic_id or category or "la comunidad"
        return {
            "available": False,
            "reason": f"sin publicaciones de la comunidad sobre {what} en {label}",
        }
    lex = ai_lexicon_entries()

    def name(t: str) -> str:
        return lex.get(t, {}).get("label_es", t.split(":")[-1])

    per_cat = (
        c.group_by("category")
        .agg(
            pl.col("n_items").sum().alias("n_items"), pl.col("topic_id").n_unique().alias("n_temas")
        )
        .sort(["n_items", "category"], descending=[True, False])
    )
    top: dict[str, list[dict[str, Any]]] = {}
    for cat in per_cat["category"].to_list():
        rows = c.filter(pl.col("category") == cat).sort(
            ["n_items", "topic_id"], descending=[True, False]
        )
        top[cat] = [
            {"topic_id": r["topic_id"], "label_es": name(r["topic_id"]), "n_items": int(r["n_items"]),
             "n_sources": int(r["n_sources"])}
            for r in rows.head(COMMUNITY_TOP).to_dicts()
        ]  # fmt: skip
    out: dict[str, Any] = {
        "available": True,
        "week": label,
        "no_validada": "señal no validada: la mayoría de las fuentes guarda poco historial, por eso "
        "nunca entra en el backtest",
        "por_categoria": [
            {
                "category": r["category"],
                "category_es": COMMUNITY_CATEGORIES_ES[r["category"]],
                "n_items": int(r["n_items"]),
                "n_temas": int(r["n_temas"]),
            }
            for r in per_cat.to_dicts()
        ],  # fmt: skip
        "top_por_categoria": top,
    }
    if category == "critics":  # plus the lexicon's critic camp, whoever writes about it
        all_week = pl.read_parquet(path).filter(pl.col("week") == label)
        critic_ids = [t for t, e in lex.items() if e.get("stance") == "critic"]
        camp = (
            all_week.filter(pl.col("topic_id").is_in(critic_ids))
            .group_by("topic_id")
            .agg(pl.col("n_items").sum())
            .sort(["n_items", "topic_id"], descending=[True, False])
        )
        out["temas_de_postura_critica"] = [
            {
                "topic_id": r["topic_id"],
                "label_es": name(r["topic_id"]),
                "n_items": int(r["n_items"]),
            }
            for r in camp.head(COMMUNITY_TOP).to_dicts()
        ]
    return out


LEADERS_LIMIT = 15


def get_leaders(week: str | None = None, limit: int = LEADERS_LIMIT) -> dict[str, Any]:
    """The week's AI leaders by volume: the `ai:` topics with the most articles (all languages),
    unlike the emergence top 10, which ranks what is rising and leaves the giants out.

    Per topic: articles, the change vs the previous week per day with data (days flagged missing
    are left out, never counted as zero), the es+pt share, family and stance (lexicon), and its
    emergence rank and decision (`topic_ai_scores_weekly`). Reads the AI lexicon run's tables
    whatever RADAR_SOURCE says; unavailable when they are not in the lake.
    """
    daily_path, scores_path = _gold("topic_ai_daily"), _gold("topic_ai_scores_weekly")
    if not daily_path.exists():
        return _unavailable("topic_ai_daily")
    d = pl.read_parquet(daily_path).filter(~pl.col("is_missing"))
    if d.schema["dt"] == pl.String:
        d = d.with_columns(pl.col("dt").str.to_date())
    if week is None:
        week = (
            pl.read_parquet(scores_path)["week"].max()
            if scores_path.exists()
            else d["dt"].max().strftime("%G-W%V")
        )
    label, monday, sunday = week_bounds(week)
    prev_monday = monday - dt.timedelta(days=7)

    def window(start: dt.date) -> tuple[pl.DataFrame, int]:
        part = d.filter(pl.col("dt").is_between(start, start + dt.timedelta(days=6)))
        agg = part.group_by("topic_id").agg(
            pl.col("n_articles").sum().alias("n"),
            pl.col("n_articles")
            .filter(pl.col("lang_bucket").is_in(["spa", "por"]))
            .sum()
            .alias("n_espt"),
        )
        return agg, part["dt"].n_unique()

    cur, days = window(monday)
    prev, prev_days = window(prev_monday)
    if cur.is_empty():
        return {"available": False, "reason": f"no hay artículos de temas de IA en {label}"}
    top = cur.sort(["n", "topic_id"], descending=[True, False]).head(limit)
    top = top.join(prev.select("topic_id", pl.col("n").alias("n_prev")), on="topic_id", how="left")
    ranks: dict[str, dict[str, Any]] = {}
    if scores_path.exists():
        sc = pl.read_parquet(scores_path).filter(pl.col("week") == label)
        ranks = {r["topic_id"]: r for r in sc.select("topic_id", "rank", "decision").to_dicts()}
    lex = ai_lexicon_entries()
    rows = []
    for i, r in enumerate(top.to_dicts(), start=1):
        n_prev = r["n_prev"] or 0
        change = None
        if n_prev and days and prev_days:
            change = round((r["n"] / days) / (n_prev / prev_days) - 1, 4)
        meta = lex.get(r["topic_id"], {})
        score = ranks.get(r["topic_id"], {})
        rows.append(
            {
                "leader_rank": i,
                "topic_id": r["topic_id"],
                "label_es": meta.get("label_es", r["topic_id"].split(":")[-1]),
                "family": meta.get("family"),
                "family_es": meta.get("family_es"),
                "stance": meta.get("stance"),
                "articles": int(r["n"]),
                "articles_prev_week": int(n_prev),
                "change_vs_prev_week": change,
                "espt_share": round(r["n_espt"] / r["n"], 4) if r["n"] else None,
                "emergence_rank": score.get("rank"),
                "decision": score.get("decision"),
            }
        )
    return {
        "available": True,
        "week": label,
        "days_with_data": days,
        "prev_week_days_with_data": prev_days,
        "rows": rows,
    }


def get_top10(week: str | None = None) -> dict[str, Any]:
    """The weekly top 10 with the six scores and the decision, from WS4's table."""
    con = _scores_con()
    if not con:
        return _unavailable("topic_scores_weekly") | {
            "note": "las puntuaciones y decisiones formales aún no están calculadas (WS4); "
            "estas son las señales por subtema, que sí son reales",
            "fallback_subtopic_trends": list_subtopic_trends(week),
        }
    label, _, _ = week_bounds(week)
    if week is None:  # the latest scored week, which can trail the newest day of data
        label = con.execute("SELECT max(week) FROM scores").fetchone()[0]
    rows = _rows(
        "SELECT * FROM scores WHERE week = ? AND rank IS NOT NULL ORDER BY rank LIMIT 10",
        [label],
        con,
    )
    return {"available": True, "week": label, "rows": rows}


def get_topic_scores(topic_id: str, week: str | None = None) -> dict[str, Any]:
    """The six scores, window, decision and reasons of one topic."""
    con = _scores_con()
    if not con:
        return _unavailable("topic_scores_weekly")
    topic_id = resolve_topic(topic_id)
    label, _, _ = week_bounds(week)
    if week is None:
        label = con.execute("SELECT max(week) FROM scores").fetchone()[0]
    rows = _rows("SELECT * FROM scores WHERE week = ? AND topic_id = ?", [label, topic_id], con)
    return {"available": bool(rows), "week": label, "topic_id": topic_id, "rows": rows}


def brief_available() -> bool:
    """True when the Editor's pre-written briefs exist in the lake."""
    return gold("topic_briefs_weekly").exists()


def get_topic_brief(topic_id: str, week: str | None = None) -> dict[str, Any]:
    """The Editor's pre-written Spanish brief of a top-10 topic (agents/briefs.py), Auditor-checked."""
    path = gold("topic_briefs_weekly")
    if not path.exists():
        return _unavailable("topic_briefs_weekly")
    topic_id = resolve_topic(topic_id)
    frame = pl.read_parquet(path)
    if week is None and frame.height:
        week = frame["week"].max()
    rows = frame.filter((pl.col("topic_id") == topic_id) & (pl.col("week") == week)).drop(
        "generated_at", "model"
    )
    if not rows.height:
        return {
            "available": False,
            "reason": f"no hay brief para {topic_id} en {week}: solo el top 10 de las últimas semanas",
        }
    return {"available": True, "week": week, "topic_id": topic_id, "brief": rows.to_dicts()[0]}


def get_topic_sources(topic_id: str, week: str | None = None) -> dict[str, Any]:
    """How many articles and distinct outlets covered a topic in a week (WS1c), and how concentrated.

    ``n_medios`` is the count of distinct outlets, not of articles: "¿cuántos medios?" is answered
    with it, never with ``n_articulos``.
    """
    path = gold("topic_sources_weekly")
    if not path.exists():
        return _unavailable("topic_sources_weekly")
    topic_id = resolve_topic(topic_id)
    frame = pl.read_parquet(path).filter(pl.col("topic_id") == topic_id)
    if week:
        _, monday, _ = week_bounds(week)
        frame = frame.filter(pl.col("week") == monday)
    elif frame.height:
        frame = frame.filter(pl.col("week") == frame["week"].max())
    if not frame.height:
        return {
            "available": False,
            "reason": f"no hay conteo de medios para {topic_id} en esa semana",
        }
    row = frame.row(0, named=True)
    iso = row["week"].isocalendar()
    return {
        "available": True,
        "topic_id": topic_id,
        "week": f"{iso.year}-W{iso.week:02d}",
        "n_articulos": row["n_articles"],
        "n_medios": row["n_sources"],
        "cuota_medio_principal": round(row["top_source_share"], 2),
        "cuota_3_medios_principales": round(row["top3_source_share"], 2),
    }


def get_topic_evidence(topic_id: str, week: str | None = None) -> dict[str, Any]:
    """Up to 5 representative articles behind a ranked topic in a week (WS1d), without URLs.

    Returns outlet, date, language and title per article plus how many articles and outlets that is,
    so an answer can say "según N artículos de M medios". The URL never reaches the model.
    """
    path = gold("topic_evidence_weekly")
    if not path.exists():
        return _unavailable("topic_evidence_weekly")
    topic_id = resolve_topic(topic_id)
    frame = pl.read_parquet(path).filter(pl.col("topic_id") == topic_id)
    if week:
        _, monday, _ = week_bounds(week)
        frame = frame.filter(pl.col("week") == monday)
    elif frame.height:
        frame = frame.filter(pl.col("week") == frame["week"].max())
    if not frame.height:
        return {
            "available": False,
            "reason": f"no hay artículos de evidencia para {topic_id} en esa semana: solo el top 30",
        }
    rows = (
        frame.sort("evidence_rank")
        .head(5)
        .select("evidence_rank", "dt", "source", "lang_bucket", "title")
        .with_columns(pl.col("dt").cast(pl.String))
        .to_dicts()
    )
    iso = frame["week"][0].isocalendar()
    week_label = f"{iso.year}-W{iso.week:02d}"
    return {
        "available": True,
        "topic_id": topic_id,
        "week": week_label,
        # counts of the articles shown here, not the week's totals (get_topic_sources has those)
        "articulos_mostrados": len(rows),
        "medios_entre_mostrados": len({r["source"] for r in rows}),
        "articles": rows,
    }


# --- Cartographer -----------------------------------------------------------------------------


# The 1-hop ring's thresholds (graph/context.py, graph/metrics.py), restated so the model cites the
# real ones instead of inventing a cut-off; test_tools checks they still match graph/.
RING_MIN_N = 3
RING_MIN_NPMI = 0.1  # strict: NPMI > 0.1
RING_TOP_K = 20
RING_HUB_SHARE = 0.01


@functools.lru_cache(maxsize=2)
def _view_summary(path: str, mtime: float) -> tuple[dict[str, Any], list[int]]:
    """The view's _meta and, per week, how many nodes it draws (those with an edge that week);
    cached per file version, since the view is several MB."""
    view = json.loads(Path(path).read_text(encoding="utf-8"))
    drawn: list[set[int]] = [set() for _ in view["_meta"]["iso_weeks"]]
    edges = view["edges"]
    for a, b, w in zip(edges["source"], edges["target"], edges["week"], strict=True):
        drawn[w].update((a, b))
    return view["_meta"], [len(d) for d in drawn]


def get_graph_facts(week: str | None = None) -> dict[str, Any]:
    """How the weekly graph view is built, from the metadata graph/export_views.py writes
    (lake/views/temporal.json): per-node top-k, minimum co-mentions, the NPMI cut, and how many
    nodes and edges the view draws that week. Read, never restated, so the answer cites the real thresholds."""
    path = lake() / "views" / "temporal.json"
    if profile() == "dev" or not path.exists():
        return _unavailable("views/temporal.json")
    meta, present = _view_summary(str(path), path.stat().st_mtime)
    weeks = meta["iso_weeks"]
    label = week if week in weeks else weeks[-1]
    i = weeks.index(label)
    params = meta["params"]
    return {
        "available": True,
        "source": "views/temporal.json",
        "week": label,
        "conexiones_por_tema": params["top_k_per_node"],
        "min_coapariciones": params["min_n"],
        "npmi_mayor_que": params["min_npmi_exclusive"],
        "temas_semana": present[i],
        "conexiones_semana": meta["edges_per_week"][i],
    }


def ring_criteria(shown: int) -> dict[str, Any]:
    """How the ring was built, in the words and numbers the answer may cite."""
    return {
        "n_minimo_coapariciones": RING_MIN_N,
        "npmi_mayor_que": RING_MIN_NPMI,
        "hubs": f"excluidos: el {RING_HUB_SHARE:.0%} de los nodos con más conexiones esa semana",
        "personas": "excluidas",
        "top_por_tema": RING_TOP_K,
        "mostrados": shown,
        "orden": "npmi de mayor a menor",
        "nota": "no hay otro umbral: cualquier vecino listado ya pasó estos filtros",
    }


def get_context_1hop(entity: str, week: str | None = None, k: int = 10) -> dict[str, Any]:
    """Neighbours that explain an entity: WS3's 1-hop ring, or the raw weekly edges until it exists."""
    entity = resolve_topic(entity)
    label, monday, _ = week_bounds(week)
    ring = _table("topic_context_1hop")
    if ring:
        rows = _rows(
            f"SELECT neighbor, rank, n, npmi, neighbor_segment, neighbor_domain FROM '{ring}' "  # noqa: S608
            "WHERE topic_id = ? AND wk = (SELECT max(wk) FROM '" + ring + "' WHERE wk <= ?) "
            "AND neighbor NOT LIKE 'per:%' ORDER BY rank LIMIT ?",
            [entity, monday, k],
        )
        return {
            "available": True,
            "source": "topic_context_1hop",
            "entity": entity,
            "week": label,
            "criterios": ring_criteria(k),
            "rows": rows,
        }
    edges = _table("edges_weekly")
    if not edges:
        return _unavailable("edges_weekly")
    rows = _rows(
        f"""
        WITH w AS (SELECT * FROM '{edges}' WHERE wk = (SELECT max(wk) FROM '{edges}' WHERE wk <= ?)),
        deg AS (SELECT e, sum(n) d FROM (SELECT x e, n FROM w UNION ALL SELECT y, n FROM w) GROUP BY e),
        hubs AS (SELECT e FROM deg WHERE d >= (SELECT quantile_cont(d, 0.99) FROM deg))
        SELECT CASE WHEN x = ? THEN y ELSE x END AS neighbor, n, npmi
        FROM w WHERE (x = ? OR y = ?) AND npmi > 0.1 AND n >= 3
          AND (CASE WHEN x = ? THEN y ELSE x END) NOT IN (SELECT e FROM hubs)
        ORDER BY npmi DESC LIMIT ?""",  # noqa: S608
        [monday, entity, entity, entity, entity, k],
    )
    return {
        "available": True,
        "source": "edges_weekly (sin restringir a artículos de IA todavía)",
        "week": label,
        "criterios": ring_criteria(k) | {"top_por_tema": None},
        "rows": rows,
    }


@functools.cache
def _graph_nodes(path: str, monday: dt.date) -> frozenset[str]:
    rows = (
        _con()
        .execute(
            f"SELECT x FROM '{path}' WHERE wk = (SELECT max(wk) FROM '{path}' WHERE wk <= ?) "
            f"UNION SELECT y FROM '{path}' WHERE wk = (SELECT max(wk) FROM '{path}' WHERE wk <= ?)",
            [monday, monday],
        )
        .fetchall()
    )
    return frozenset(r[0] for r in rows if not r[0].startswith("per:"))


def graph_nodes(week: str | None = None) -> frozenset[str]:
    """Node ids of the week's graph (never persons), to recognise entities named in a question."""
    if known := known_topics():
        return frozenset(known)
    edges = _table("edges_weekly")
    return _graph_nodes(edges, week_bounds(week)[1]) if edges else frozenset()


_VIEW_VALIDATOR = Draft202012Validator(load_schema("view_command"))


def update_view(
    view: str,
    caption_es: str,
    color_by: str = "decision",
    week: str | None = None,
    focus_topic: str | None = None,
    highlight: list[str] | None = None,
    segment: list[str] | None = None,
    hops: int | None = None,
) -> dict[str, Any]:
    """Build a view command for the web (contract view_command); invalid commands are refused."""
    command: dict[str, Any] = {
        "view": view,
        "week": week_bounds(week)[0] if week else None,
        "focus_topic": focus_topic,
        "highlight": highlight or [],
        "color_by": color_by,
        "caption_es": caption_es,
    }
    filt = {k: v for k, v in {"segment": segment, "hops": hops}.items() if v}
    if filt:
        command["filter"] = filt
    errors = [e.message for e in _VIEW_VALIDATOR.iter_errors(command)]
    if errors:
        return {"available": False, "reason": "; ".join(errors)}
    return {"available": True, "view_command": command}


# --- Scout, Curator, Auditor ------------------------------------------------------------------


def get_freshness() -> dict[str, Any]:
    """Newest date in each gold table and the profile being served."""
    out = {}
    for name, col in [
        ("daily_totals", "dt"),
        ("daily_topic", "dt"),
        ("edges_weekly", "wk"),
        ("topic_scores_weekly", "week"),
    ]:
        table = _table(name)
        out[name] = (
            str(_con().execute(f"SELECT max({col}) FROM '{table}'").fetchone()[0])  # noqa: S608
            if table
            else None
        )
    return {"available": True, "profile": profile(), "newest": out}


def get_cost_ledger() -> dict[str, Any]:
    """What the radar has cost: BigQuery bytes billed (measured) with the free tier and the USD it
    implies (estimate), plus Jev's USD from its own ledger (measured). See agents/trust.py."""
    return {"available": True} | ledger_costs(REPO_ROOT / "reports")


def get_segment_mix(week: str | None = None) -> dict[str, Any]:
    """Articles per subtopic and language in a week (segments ai/it/ai_domain arrive with WS1)."""
    table = _table("daily_topic")
    if not table:
        return _unavailable("daily_topic")
    label, monday, sunday = week_bounds(week)
    rows = _rows(
        f"SELECT topic, lang_bucket, sum(n_articles) AS articles FROM '{table}' "  # noqa: S608
        "WHERE dt BETWEEN ? AND ? GROUP BY 1, 2 ORDER BY 3 DESC",
        [monday, sunday],
    )
    return {"available": True, "week": label, "rows": rows}


def _report(name: str) -> dict[str, Any]:
    path = REPO_ROOT / "reports" / name
    if not path.exists():
        return {"available": False, "reason": f"reports/{name} todavía no existe"}
    return {"available": True, "report": path.read_text(encoding="utf-8")[:4000]}


def get_backtest() -> dict[str, Any]:
    """The backtest report (WS4), with its headline numbers parsed for the trust line."""
    path = trust.backtest_report(REPO_ROOT / "reports")  # backtest_ai.md under RADAR_SOURCE=ai
    if not path.exists():
        return _report(path.name)
    text = path.read_text(encoding="utf-8")
    return {
        "available": True,
        "fuente": f"reports/{path.name}",
        "resumen": trust.report_summary(path),
        "report": text[:4000],
    }


def get_filter_quality() -> dict[str, Any]:
    """The filter precision/recall report (WS2), and whether human labels are still pending."""
    out = _report("label_quality.md")
    if out.get("available"):
        text = (REPO_ROOT / "reports" / "label_quality.md").read_text(encoding="utf-8")
        out = {"etiquetas_humanas_pendientes": "Pre-Human-Tally" in text} | out
    return out


# --- Registry ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[..., dict[str, Any]]
    description: str
    parameters: dict[str, Any]

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


WEEK = {
    "type": "string",
    "description": "semana ISO, p. ej. 2026-W41; omitir = la última con datos",
}
LANG = {"type": "string", "enum": ["all", "eng", "spa", "por", "other"]}
SUBTOPIC = {
    "type": "string",
    "description": "ai_all o un subtema: agents, llms_models, chips_infra, regulation_policy, "
    "education, jobs_work, business_adoption, safety_risk, creative_media, health_science, "
    "funding_markets, energy_climate",
}

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "list_subtopic_trends",
            list_subtopic_trends,
            "Señales de 7 días de cada subtema de IA: artículos, z_7d, crecimiento, tono, controversia.",
            {"type": "object", "properties": {"week": WEEK, "lang_bucket": LANG}},
        ),
        Tool(
            "get_topic_series",
            get_topic_series,
            "Serie semanal de un subtema: artículos, participación, tono, colas positiva/negativa, "
            "participación LatAm.",
            {
                "type": "object",
                "properties": {
                    "topic": SUBTOPIC,
                    "lang_bucket": LANG,
                    "weeks": {"type": "integer"},
                },
                "required": ["topic"],
            },
        ),
        Tool(
            "get_top10",
            get_top10,
            "El top 10 semanal con las seis puntuaciones y la decisión.",
            {"type": "object", "properties": {"week": WEEK}},
        ),
        Tool(
            "get_topic_evidence",
            get_topic_evidence,
            "Hasta 5 artículos representativos de un tema en una semana: medio, fecha, idioma y "
            "título (sin URL), con cuántos artículos y medios son.",
            {
                "type": "object",
                "properties": {"topic_id": {"type": "string"}, "week": WEEK},
                "required": ["topic_id"],
            },
        ),
        Tool(
            "get_topic_sources",
            get_topic_sources,
            "Cuántos artículos y cuántos medios distintos cubrieron un tema en una semana, y qué "
            "parte se lleva el medio principal. Para '¿cuántos medios?' usa n_medios, no "
            "n_articulos.",
            {
                "type": "object",
                "properties": {"topic_id": {"type": "string"}, "week": WEEK},
                "required": ["topic_id"],
            },
        ),
        Tool(
            "get_topic_brief",
            get_topic_brief,
            "El brief de adaptación en español ya escrito para un tema del top 10 (titular, qué pasó, "
            "por qué importa en LatAm, ángulo, gancho y formato), revisado por el Auditor.",
            {
                "type": "object",
                "properties": {"topic_id": {"type": "string"}, "week": WEEK},
                "required": ["topic_id"],
            },
        ),
        Tool(
            "get_community_signal",
            get_community_signal,
            "Lo que publica la comunidad IA (investigación, practicantes, constructores y "
            "aceleradoras, visión, medios, críticos) por categoría y tema esta semana: conteos "
            "medidos, señal no validada; nunca títulos.",
            {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string"},
                    "week": WEEK,
                    "category": {"type": "string", "enum": list(COMMUNITY_CATEGORIES_ES)},
                },
            },
        ),
        Tool(
            "get_leaders",
            get_leaders,
            "Los temas de IA más grandes de la semana por volumen de artículos (todos los "
            "idiomas): artículos, cambio frente a la semana previa, cuota en español y "
            "portugués, familia, postura y su puesto en emergencia.",
            {"type": "object", "properties": {"week": WEEK}},
        ),
        Tool(
            "get_topic_scores",
            get_topic_scores,
            "Puntuaciones, ventana y decisión de un tema.",
            {
                "type": "object",
                "properties": {"topic_id": {"type": "string"}, "week": WEEK},
                "required": ["topic_id"],
            },
        ),
        Tool(
            "get_language_coverage",
            get_language_coverage,
            "Cuántos artículos de un tema hay en español y en portugués esa semana (pueden ser 0), "
            "de cuántos en total y con cuántos días con datos.",
            {
                "type": "object",
                "properties": {"topic": {"type": "string"}, "week": WEEK},
                "required": ["topic"],
            },
        ),
        Tool(
            "get_graph_facts",
            get_graph_facts,
            "Cómo se arma el grafo semanal que ve el usuario: conexiones por tema, mínimo de "
            "co-menciones, corte de NPMI y cuántos temas y conexiones tiene la semana.",
            {"type": "object", "properties": {"week": WEEK}},
        ),
        Tool(
            "get_context_1hop",
            get_context_1hop,
            "Vecinos que explican una entidad (anillo de 1 salto), p. ej. 'org:openai'.",
            {
                "type": "object",
                "properties": {
                    "entity": {"type": "string"},
                    "week": WEEK,
                    "k": {"type": "integer"},
                },
                "required": ["entity"],
            },
        ),
        Tool(
            "update_view",
            update_view,
            "Cambia la vista del grafo o de las tarjetas en la web.",
            {
                "type": "object",
                "properties": {
                    "view": {"type": "string", "enum": ["story", "temporal", "cards"]},
                    "caption_es": {"type": "string"},
                    "color_by": {
                        "type": "string",
                        "enum": [
                            "tone",
                            "arousal",
                            "community",
                            "segment",
                            "decision",
                            "window",
                            "bridge",
                            "momentum",
                            "novelty",
                            "family",
                            "postura",
                        ],
                    },
                    "week": WEEK,
                    "focus_topic": {"type": "string"},
                    "highlight": {"type": "array", "items": {"type": "string"}},
                    "segment": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["ai", "it", "ai_domain"]},
                    },
                    "hops": {"type": "integer", "enum": [1, 2]},
                },
                "required": ["view", "caption_es"],
            },
        ),
        Tool(
            "get_freshness",
            get_freshness,
            "Fecha más reciente de cada tabla.",
            {"type": "object", "properties": {}},
        ),
        Tool(
            "get_cost_ledger",
            get_cost_ledger,
            "Bytes facturados en BigQuery (medido).",
            {"type": "object", "properties": {}},
        ),
        Tool(
            "get_segment_mix",
            get_segment_mix,
            "Artículos por subtema e idioma en una semana.",
            {"type": "object", "properties": {"week": WEEK}},
        ),
        Tool(
            "get_backtest",
            get_backtest,
            "Informe del backtest.",
            {"type": "object", "properties": {}},
        ),
        Tool(
            "get_filter_quality",
            get_filter_quality,
            "Informe de precisión y exhaustividad del filtro.",
            {"type": "object", "properties": {}},
        ),
    ]
}


def call(name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
    """Run a tool by name with JSON or dict arguments; errors come back as data, never raised."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"available": False, "reason": f"herramienta desconocida: {name}"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        return tool.fn(**args)
    except (TypeError, ValueError, duckdb.Error) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
