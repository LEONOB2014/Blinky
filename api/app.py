"""Read-only FastAPI over the lake (DuckDB over Parquet) plus the Media Master chat endpoint.

Implements every path in `contracts/api.yaml`:
- `GET /api/radar`
- `GET /api/topic/{topic_id}/timeline`
- `GET /api/topic/{topic_id}/context`
- `GET /api/freshness`
- `POST /api/chat`
"""

import datetime as dt
import json
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import duckdb
import polars as pl
import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.llm import ChatModel, NebiusChat, model_config
from agents.runtime import run_turn
from agents.tools import week_bounds
from radar.contracts import CONTRACTS_DIR, load_schema
from radar.paths import REPO_ROOT, gold, profile

load_dotenv(REPO_ROOT / ".env")

app = FastAPI(
    title="Radar API",
    version="0.1.0",
    description="Read-only API over the lake (DuckDB over Parquet) plus the agent chat.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Radar-Empty-Reason", "X-Radar-Status"],
)

_SCORE_PROPS = frozenset(load_schema("topic_scores_weekly")["properties"].keys())
_WINDOW_PROPS = frozenset(
    load_schema("topic_scores_weekly")["properties"]["window"]["properties"].keys()
)
_FRESHNESS_TABLES: tuple[tuple[str, str], ...] = (
    ("daily_totals", "dt"),
    ("daily_topic", "dt"),
    ("daily_topic_rolling", "dt"),
    ("edges_weekly", "wk"),
    ("topic_scores_weekly", "week"),
    ("topic_daily", "dt"),
    ("topic_context_1hop", "wk"),
)


PERSON_PREFIX = "per:"  # persons are never served (privacy guard, whatever the lake holds)

# The AI lexicon run writes parallel tables. The default stays the v0.2 GDELT ranking.
_AI_TABLES = {
    "topic_scores_weekly": "topic_ai_scores_weekly",
    "topic_daily": "topic_ai_daily",
}


def _lake_table(name: str) -> str:
    """Table the API reads. `RADAR_SOURCE=ai` uses the lexicon run when that file exists."""
    if os.environ.get("RADAR_SOURCE") != "ai":
        return name
    alt = _AI_TABLES.get(name)
    if alt is not None and gold(alt).exists():
        return alt
    return name


@lru_cache(maxsize=1)
def _taxonomy() -> dict[str, Any]:
    return yaml.safe_load((CONTRACTS_DIR / "taxonomy.yaml").read_text(encoding="utf-8"))


def denied_topic_ids() -> frozenset[str]:
    """``org:<name>`` ids on the ranked-universe deny list (wire services, outlets, artefacts)."""
    deny = _taxonomy().get("ranked_universe", {}).get("org_deny") or []
    return frozenset(f"org:{name.strip().lower()}" for name in deny)


def subtopic_labels() -> dict[str, str]:
    """Subtopic id -> its Spanish label from the taxonomy."""
    return {k: v["label_es"] for k, v in (_taxonomy().get("subtopics") or {}).items()}


def is_person(entity_id: str | None) -> bool:
    return bool(entity_id) and entity_id.lower().startswith(PERSON_PREFIX)


def _clean_value(val: Any) -> Any:
    if isinstance(val, dt.date | dt.datetime):
        return val.isoformat()
    if isinstance(val, float):
        return None if math.isnan(val) or math.isinf(val) else round(val, 6)
    if isinstance(val, tuple):
        return [_clean_value(x) for x in val]
    if isinstance(val, list):
        return [_clean_value(x) for x in val]
    if isinstance(val, dict):
        return {k: _clean_value(v) for k, v in val.items()}
    return val


def _query_rows(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    with duckdb.connect() as con:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return [{col: _clean_value(val) for col, val in zip(cols, row, strict=True)} for row in rows]


def _normalize_score_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in row.items():
        if key not in _SCORE_PROPS:
            continue
        if key in {"subtopics", "why", "evidence_ids"} and isinstance(val, str):
            val = json.loads(val)
        elif key == "window":
            if isinstance(val, str):
                val = json.loads(val)
            if isinstance(val, dict):
                val = {k: v for k, v in val.items() if k in _WINDOW_PROPS}
                if val.get("days_left") is not None:
                    val["days_left"] = int(val["days_left"])
                if val.get("n_onsets") is not None:
                    val["n_onsets"] = int(val["n_onsets"])
        out[key] = val
    if "profile" not in out or out["profile"] is None:
        out["profile"] = profile()
    return out


@app.get("/api/radar")
def get_radar(
    response: Response,
    week: Annotated[str | None, Query(pattern=r"^[0-9]{4}-W[0-9]{2}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    """Weekly top ranked topics from WS4's `topic_scores_weekly` table.

    Rows may be subtopics (``agents``) or ``org:``/``thm:`` topics. Deny-listed orgs from the
    taxonomy's ``ranked_universe.org_deny`` are never returned. The table is small and DuckDB
    1.5.6 cannot filter the Polars-written file ("PlainSkip not implemented"), so it is scanned
    with Polars and the week filter pushed down.
    """
    table = _lake_table("topic_scores_weekly")
    path = gold(table)
    if not path.exists():
        reason = f"{table} not available yet in profile {profile()} (pending WS4)"
        response.headers["X-Radar-Empty-Reason"] = reason
        response.headers["X-Radar-Status"] = "pending-ws4"
        return []

    lf = pl.scan_parquet(path)
    if week is None:
        week = lf.select(pl.col("week").max()).collect().item()
    df = (
        lf.filter(
            (pl.col("week") == week)
            & ~pl.col("topic_id").str.to_lowercase().is_in(sorted(denied_topic_ids()))
            & ~pl.col("topic_id").str.to_lowercase().str.starts_with(PERSON_PREFIX)
        )
        .sort(
            [pl.col("rank").fill_null(999_999), pl.col("priority")],
            descending=[False, True],
            nulls_last=True,
        )
        .head(limit)
        .collect()
    )
    if df.is_empty():
        response.headers["X-Radar-Empty-Reason"] = f"no scored topics for week {week}"
        return []
    labels = subtopic_labels()
    rows = []
    for raw in df.to_dicts():
        row = _normalize_score_row({k: _clean_value(v) for k, v in raw.items()})
        if row.get("topic_id") in labels:
            row["label_es"] = labels[row["topic_id"]]
        rows.append(row)
    return rows


@app.get("/api/topic/{topic_id}/timeline")
def get_topic_timeline(topic_id: str) -> list[dict[str, Any]]:
    """Daily series of one topic by language (`topic_daily.schema.json`)."""
    if is_person(topic_id):
        return []
    topic_daily_path = gold(_lake_table("topic_daily"))
    if topic_daily_path.exists():
        file_path = str(topic_daily_path)
        rows = _query_rows(
            """
            SELECT
                topic_id,
                CAST(dt AS VARCHAR) AS dt,
                lang_bucket,
                'ai' AS segment,
                CAST(n_articles AS INTEGER) AS n_articles,
                CAST(share_of_day AS DOUBLE) AS share_of_day,
                CAST(mean_tone AS DOUBLE) AS mean_tone,
                CAST(mean_polarity AS DOUBLE) AS mean_polarity,
                CAST(is_missing AS BOOLEAN) AS is_missing
            FROM read_parquet(?)
            WHERE topic_id = ?
            ORDER BY dt ASC, lang_bucket ASC
            """,
            [file_path, topic_id],
        )
        if rows:
            return rows

    daily_topic_path = gold("daily_topic")
    if not daily_topic_path.exists():
        return []

    file_path = str(daily_topic_path)
    return _query_rows(
        """
        SELECT
            topic AS topic_id,
            CAST(dt AS VARCHAR) AS dt,
            lang_bucket,
            'ai' AS segment,
            CAST(SUM(n_articles) AS INTEGER) AS n_articles,
            CASE
                WHEN BOOL_AND(is_missing) THEN NULL
                ELSE CAST(SUM(n_articles) AS DOUBLE) / NULLIF(MAX(n_all_stream), 0)
            END AS share_of_day,
            CASE
                WHEN BOOL_AND(is_missing) THEN NULL
                ELSE CAST(SUM(sum_tone) AS DOUBLE) / NULLIF(SUM(n_tone), 0)
            END AS mean_tone,
            CASE
                WHEN BOOL_AND(is_missing) THEN NULL
                ELSE CAST(SUM(sum_polarity) AS DOUBLE) / NULLIF(SUM(n_tone), 0)
            END AS mean_polarity,
            BOOL_AND(is_missing) AS is_missing
        FROM read_parquet(?)
        WHERE topic = ?
        GROUP BY dt, topic, lang_bucket
        ORDER BY dt ASC, lang_bucket ASC
        """,
        [file_path, topic_id],
    )


@app.get("/api/topic/{topic_id}/context")
def get_topic_context(
    topic_id: str,
    week: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """The 1-hop context ring of a topic (`topic_context_1hop.schema.json`).

    Privacy guard: no ``per:`` neighbour is ever returned (filtered in SQL and again here), and a
    person is never a topic. Ranks are renumbered after the filter so they stay 1..n.
    """
    if is_person(topic_id):
        return []
    return _guard_ring(_query_context(topic_id, week))


def _guard_ring(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = [r for r in rows if not is_person(r.get("neighbor"))]
    kept.sort(key=lambda r: r["rank"])
    for i, r in enumerate(kept, start=1):
        r["rank"] = i
    return kept[:20]


def _query_context(topic_id: str, week: str | None) -> list[dict[str, Any]]:
    _, monday, _ = week_bounds(week)
    ring_path = gold("topic_context_1hop")
    if ring_path.exists():
        file_path = str(ring_path)
        return _query_rows(
            """
            WITH target_wk AS (
                SELECT max(wk) AS wk FROM read_parquet(?) WHERE wk <= ?
            )
            SELECT
                CAST(r.wk AS VARCHAR) AS wk,
                r.topic_id,
                r.neighbor,
                CAST(r.rank AS INTEGER) AS rank,
                CAST(r.n AS INTEGER) AS n,
                CAST(r.npmi AS DOUBLE) AS npmi,
                r.neighbor_segment,
                r.neighbor_domain
            FROM read_parquet(?) AS r, target_wk
            WHERE r.topic_id = ? AND r.wk = target_wk.wk
              AND NOT starts_with(lower(r.neighbor), 'per:')
            ORDER BY r.rank ASC
            LIMIT 20
            """,
            [file_path, monday, file_path, topic_id],
        )

    edges_path = gold("edges_weekly")
    if not edges_path.exists():
        return []

    file_path = str(edges_path)
    return _query_rows(
        """
        WITH w AS (
            SELECT * FROM read_parquet(?)
            WHERE wk = (SELECT max(wk) FROM read_parquet(?) WHERE wk <= ?)
        ),
        deg AS (
            SELECT e, sum(n) AS d
            FROM (SELECT x AS e, n FROM w UNION ALL SELECT y AS e, n FROM w)
            GROUP BY e
        ),
        hubs AS (
            SELECT e FROM deg
            WHERE d >= (SELECT quantile_cont(d, 0.99) FROM deg)
        ),
        filtered AS (
            SELECT
                CAST(wk AS VARCHAR) AS wk,
                ? AS topic_id,
                CASE WHEN x = ? THEN y ELSE x END AS neighbor,
                CAST(n AS INTEGER) AS n,
                CAST(npmi AS DOUBLE) AS npmi
            FROM w
            WHERE (x = ? OR y = ?)
              AND npmi > 0.1
              AND n >= 3
              AND (CASE WHEN x = ? THEN y ELSE x END) NOT IN (SELECT e FROM hubs)
              AND NOT starts_with(lower(CASE WHEN x = ? THEN y ELSE x END), 'per:')
        )
        SELECT
            wk,
            topic_id,
            neighbor,
            CAST(ROW_NUMBER() OVER (ORDER BY npmi DESC, n DESC, neighbor ASC) AS INTEGER) AS rank,
            n,
            npmi,
            NULL AS neighbor_segment,
            NULL AS neighbor_domain
        FROM filtered
        ORDER BY rank ASC
        LIMIT 20
        """,
        [file_path, file_path, monday, topic_id, topic_id, topic_id, topic_id, topic_id, topic_id],
    )


@app.get("/api/freshness")
def get_freshness() -> dict[str, Any]:
    """Newest date per table and the active profile (`dev` or `full`)."""
    tables: dict[str, str | None] = {}
    with duckdb.connect() as con:
        for name, col in _FRESHNESS_TABLES:
            path = gold(name)
            if not path.exists():
                tables[name] = None
                continue
            # Footer statistics first: no request scans a large table (edges_weekly is 37.8M rows).
            val = con.execute(
                "SELECT max(stats_max_value) FROM parquet_metadata(?) WHERE path_in_schema = ?",
                [str(path), col],
            ).fetchone()
            if not val or val[0] is None:
                val = con.execute(
                    f"SELECT max({col}) FROM read_parquet(?)",  # noqa: S608
                    [str(path)],
                ).fetchone()
            tables[name] = str(val[0]) if val and val[0] is not None else None
    return {
        "profile": profile(),
        "tables": tables,
        "newest": tables,
    }


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    week: str | None = None


def get_chat_model() -> ChatModel:
    override: ChatModel | None = getattr(app.state, "chat_model", None)
    if override is not None:
        return override
    cfg = model_config()
    if not os.environ.get(cfg["auth_env"]):
        raise HTTPException(status_code=503, detail="agents runtime not deployed yet")
    return NebiusChat()


@dataclass(frozen=True)
class ChatLimits:
    per_client: int  # turns per client per window
    window_s: int
    daily_cap: int  # turns per UTC day, all clients together


def chat_limits() -> ChatLimits:
    """Config: RADAR_CHAT_PER_CLIENT (10), RADAR_CHAT_WINDOW_S (600), RADAR_CHAT_DAILY_CAP (500)."""
    return ChatLimits(
        per_client=int(os.environ.get("RADAR_CHAT_PER_CLIENT", "10")),
        window_s=int(os.environ.get("RADAR_CHAT_WINDOW_S", "600")),
        daily_cap=int(os.environ.get("RADAR_CHAT_DAILY_CAP", "500")),
    )


class ChatQuota:
    """In-memory chat quota: a sliding window per client and a global UTC-day cap.

    Each turn spends Nebius credit and the endpoint is public. The state lives in one process, so
    with N instances (Cloud Run: at most 3) the effective limits are up to N times the configured
    ones; deploy/README.md says so.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._day = ""
        self._day_count = 0

    def admit(self, client: str, limits: ChatLimits, now: float | None = None) -> str | None:
        """Record one turn and return None, or return the Spanish refusal without recording it."""
        now = time.time() if now is None else now
        day = dt.datetime.fromtimestamp(now, dt.UTC).date().isoformat()
        with self._lock:
            if day != self._day:
                self._day, self._day_count = day, 0
            hits = self._hits.setdefault(client, deque())
            while hits and hits[0] <= now - limits.window_s:
                hits.popleft()
            if len(hits) >= limits.per_client:
                wait_min = max(1, math.ceil((hits[0] + limits.window_s - now) / 60))
                return (
                    f"Límite de preguntas alcanzado: {limits.per_client} cada "
                    f"{round(limits.window_s / 60)} minutos por visitante. "
                    f"Vuelve a intentarlo en {wait_min} min."
                )
            if self._day_count >= limits.daily_cap:
                return (
                    f"El chat llegó a su límite diario de {limits.daily_cap} preguntas. "
                    "Las tarjetas, las series y el anillo de contexto siguen disponibles; "
                    "vuelve a intentarlo mañana."
                )
            hits.append(now)
            self._day_count += 1
            return None

    def retry_after_s(self, client: str, limits: ChatLimits, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self._lock:
            hits = self._hits.get(client)
            if hits and len(hits) >= limits.per_client:
                return max(1, math.ceil(hits[0] + limits.window_s - now))
        tomorrow = dt.datetime.fromtimestamp(now, dt.UTC).date() + dt.timedelta(days=1)
        midnight = dt.datetime.combine(tomorrow, dt.time(), dt.UTC).timestamp()
        return max(1, math.ceil(midnight - now))


chat_quota = ChatQuota()


def client_key(request: Request) -> str:
    """The caller's IP. Behind Cloud Run the real client is the *last* X-Forwarded-For entry
    (Google appends it), so a client cannot dodge the limit by sending its own header."""
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


class FeedbackRequest(BaseModel):
    trace_id: str = Field(
        ..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    score: int = Field(..., ge=0, le=1, description="1 = útil, 0 = no útil")
    comment: str | None = Field(None, max_length=500)


def feedback_client() -> Any:
    """A LangSmith client when tracing is configured, else None (the endpoint answers 503)."""
    override = getattr(app.state, "feedback_client", None)
    if override is not None:
        return override
    if not os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGSMITH_TRACING") != "true":
        return None
    from langsmith import Client

    return Client()


@app.post("/api/feedback", status_code=202)
def post_feedback(req: FeedbackRequest, request: Request) -> dict[str, Any]:
    """A reader's thumbs up or down on one chat turn, recorded on its LangSmith trace."""
    client = feedback_client()
    if client is None:
        raise HTTPException(status_code=503, detail="la retroalimentación no está configurada")
    limits = chat_limits()
    if chat_quota.admit(client_key(request), limits) is not None:
        raise HTTPException(status_code=429, detail="demasiadas valoraciones seguidas")
    client.create_feedback(
        run_id=req.trace_id, key="user_thumbs", score=req.score, comment=req.comment
    )
    return {"recorded": True, "trace_id": req.trace_id}


@app.post("/api/chat")
def post_chat(
    req: ChatRequest,
    request: Request,
    model: Annotated[ChatModel, Depends(get_chat_model)],
) -> dict[str, Any]:
    """One turn with the Media Master (`contracts/api.yaml`), rate limited (HTTP 429)."""
    limits = chat_limits()
    client = client_key(request)
    refusal = chat_quota.admit(client, limits)
    if refusal is not None:
        raise HTTPException(
            status_code=429,
            detail=refusal,
            headers={"Retry-After": str(chat_quota.retry_after_s(client, limits))},
        )
    return run_turn(
        req.message,
        conversation_id=req.conversation_id,
        model=model,
        week=req.week,
    )
