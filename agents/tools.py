"""Tools the agents call. Every tool reads real tables through `radar.paths.gold` (dev or full
profile) and returns plain JSON. When the table a tool needs does not exist yet, it says so
(`available: false` and the reason) instead of returning anything invented.
"""

import csv
import datetime as dt
import functools
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import duckdb
import polars as pl
import yaml
from jsonschema import Draft202012Validator

from radar.contracts import load_schema
from radar.paths import REPO_ROOT, gold, profile

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
Z_DISPLAY_CAP = 10.0  # z-scores above this are shown as ">10": tiny 28-day baselines inflate them


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


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


# --- Human-formatted fields: numbers already written the way an executive reads them, so the LLM
# copies them instead of re-computing (raw fields stay for code and the Auditor).

DECISION_ES = {
    "publicar_ahora": "Publicar ahora",
    "preparar": "Preparar",
    "esperar": "Esperar",
    "no_es_tema_caliente": "No es tema caliente",
}
LIST_PRICE_USD_PER_TIB = 6.25  # BigQuery on-demand list price (estimate for the cost line)


def human_name(topic_id: str) -> str:
    """'org:openai inc' -> 'openai inc', 'chips_infra' -> its Spanish label, 'domain:x' -> 'x'."""
    if topic_id in labels_es():
        return labels_es()[topic_id]
    return topic_id.split(":", 1)[1] if ":" in topic_id else topic_id


def pct(x: float | None, signed: bool = False) -> str | None:
    """0.6455 -> '65%'; signed: 3.648 -> '+365%' (no decimals, as an executive reads it)."""
    if x is None:
        return None
    return f"{x * 100:+.0f}%" if signed else f"{x * 100:.0f}%"


def tone_word(tone: float | None) -> str | None:
    if tone is None:
        return None
    return "negativo" if tone < -1.5 else "positivo" if tone > 1.5 else "neutral"


def _score_summary(r: dict[str, Any]) -> str:
    name = r.get("label_es") if r.get("label_es") not in (None, r.get("topic_id")) else None
    parts = [f"{name or human_name(r['topic_id'])}: {DECISION_ES.get(r.get('decision'), '?')}"]
    if r.get("stage"):
        parts.append(f"etapa {r['stage']}")
    if r.get("emergence_pct") is not None:
        parts.append(f"emergencia en el percentil {r['emergence_pct']:.0f} de la semana")
    if r.get("saturation") is not None:
        parts.append(f"saturación en español {pct(r['saturation'])}")
    if r.get("audience_fit") is not None:
        parts.append(f"encaje con ejecutivos de LatAm {pct(r['audience_fit'])}")
    days = (r.get("window") or {}).get("days_left")
    if days is not None:
        parts.append(f"unos {days} días antes de llegar al español (estimado)")
    return "; ".join(parts)


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
        r["label_es"] = labels_es().get(r["topic"], human_name(r["topic"]))
        g = r["growth_7d_log"]
        r["crecimiento_7d"] = pct(math.exp(g) - 1, signed=True) if g is not None else None
        r["tono"] = tone_word(r["mean_tone_7d"])
        r["resumen_es"] = (
            f"{r['label_es']}: {r['articles_7d']:.0f} artículos en 7 días, "
            f"{r['crecimiento_7d'] or 'sin variación medida'} vs. la semana anterior, tono {r['tono']}"
        )
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
    if topic.startswith(("org:", "thm:")):
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
    return _series_summary(
        {"available": True, "topic": topic, "lang_bucket": lang_bucket, "rows": rows[::-1]}
    )


def _series_summary(out: dict[str, Any]) -> dict[str, Any]:
    """Adds 'resumen_es': the last week's articles, change vs. the week before, tone, LatAm share."""
    rows = out.get("rows") or []
    if not rows:
        return out
    last = rows[-1]
    parts = [f"{human_name(out['topic'])}: {last['articles']:.0f} artículos en {last['week']}"]
    if len(rows) > 1 and rows[-2]["articles"]:
        parts.append(
            f"{pct(last['articles'] / rows[-2]['articles'] - 1, signed=True)} vs. la semana anterior"
        )
    if last.get("mean_tone") is not None:
        parts.append(f"tono {tone_word(last['mean_tone'])}")
    if last.get("latam_share") is not None:
        parts.append(f"{pct(last['latam_share'])} desde LatAm")
    out["resumen_es"] = ", ".join(parts)
    return out


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
    return _series_summary(
        {"available": bool(rows), "topic": topic, "lang_bucket": lang_bucket, "rows": rows[::-1]}
    )


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
    for r in rows:
        r["resumen_es"] = _score_summary(r)
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
    for r in rows:
        r["resumen_es"] = _score_summary(r)
    return {"available": bool(rows), "week": label, "topic_id": topic_id, "rows": rows}


# --- Cartographer -----------------------------------------------------------------------------


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
        for r in rows:
            r["nombre"] = human_name(r["neighbor"])
        top = ", ".join(f"{r['nombre']} ({r['n']} co-menciones)" for r in rows[:5])
        return {
            "available": True,
            "source": "topic_context_1hop",
            "entity": entity,
            "week": label,
            "rows": rows,
            "resumen_es": f"Lo que más aparece junto a {human_name(entity)} esta semana: {top}"
            if rows
            else f"No hay vecinos de {human_name(entity)} esta semana",
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
    color_by: str = "tone",
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
    today = dt.datetime.now(dt.UTC).date()
    days = {}
    for name, value in out.items():
        try:
            days[name] = (today - dt.date.fromisoformat(value)).days if value else None
        except ValueError:
            days[name] = None
    news = days.get("daily_topic")
    summary = (
        "Datos al día: las noticias llegan hasta hoy"
        if news == 0
        else f"Las noticias llegan hasta hace {news} días"
        if news is not None
        else "Sin fecha de noticias"
    )
    if out.get("topic_scores_weekly"):
        summary += f"; las puntuaciones son de la semana {out['topic_scores_weekly']}"
    return {
        "available": True,
        "profile": profile(),
        "newest": out,
        "dias_desde_ultimo_dato": days,
        "resumen_es": summary,
    }


def get_cost_ledger() -> dict[str, Any]:
    """BigQuery bytes billed so far, from reports/bq_ledger.csv (measured)."""
    path = REPO_ROOT / "reports" / "bq_ledger.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    billed = sum(int(r["billed_bytes"] or 0) for r in rows)
    usd = billed / 2**40 * LIST_PRICE_USD_PER_TIB
    return {
        "available": True,
        "jobs": len(rows),
        "billed_gb": round(billed / 1e9, 2),
        "free_tier_share": round(billed / 1e12, 4),
        "list_price_usd_estimate": round(usd, 2),
        "resumen_es": f"{billed / 1e9:.0f} GB procesados en {len(rows)} consultas, "
        f"{pct(billed / 1e12)} de la capa gratuita mensual de 1 TB; a precio de lista serían "
        f"unos US${usd:.2f} (estimado, US$6.25 por TiB)",
    }


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
    """The backtest report (WS4), verbatim."""
    return _report("backtest.md")


def get_filter_quality() -> dict[str, Any]:
    """The filter precision/recall report (WS2), verbatim."""
    return _report("label_quality.md")


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
                        "enum": ["tone", "arousal", "community", "segment"],
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
