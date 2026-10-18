"""Write the static fallback of the API to web/public/data/ from the full lake.

The UI reads these files when the live API is unreachable (web/src/api.ts). Every file is the body
the API itself returns: the export calls the real handlers in api/app.py through FastAPI's test
client, so the static and live answers cannot drift. Refuses unless RADAR_PROFILE=full (the dev
slice is never published). web/public/data/ is git-ignored and deployed with the web build.

    RADAR_PROFILE=full uv run --extra api python deploy/export_static.py

Layout (``slug`` = the topic id lowercased, every non [a-z0-9] run replaced by "_"):
    index.json                     weeks, latest week, topics and their slugs, generation time
    freshness.json                 GET /api/freshness
    radar/<week>.json, latest.json GET /api/radar?week=<week>&limit=10, every scored week
    timeline/<slug>.json           GET /api/topic/<id>/timeline
    context/<slug>/<week>.json     GET /api/topic/<id>/context?week=<week>, the last 4 weeks
    context/<slug>/latest.json     GET /api/topic/<id>/context
    evidence/*.json                the trust step offline (deploy/evidence.py): backtest and label
                                   quality reports as JSON, BigQuery and Jev ledger totals
    evidence/topics/<slug>.json    topic_evidence_weekly (up to 5 articles per week) for the top 10
                                   of the last 4 scored weeks; titles and URLs, so never in git
Topics: every topic in a top 10 of the last 4 weeks, the subtopics (timelines only) and the
entities the UI offers by default.
"""

import csv
import datetime as dt
import json
import os
import re
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from evidence import write_evidence

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "web" / "public" / "data"
TOP = 10
RECENT_WEEKS = 4
# The AI radar (RADAR_SOURCE=ai): the tables this export reads directly, switched the way the API
# and agents switch them (api/app.py, agents/tools.py), when the AI table exists.
AI_TABLES = {
    "topic_scores_weekly": "topic_ai_scores_weekly",
    "topic_briefs_weekly": "topic_ai_briefs_weekly",
}


def source_table(name: str) -> str:
    """The gold table to read for `name` under the active RADAR_SOURCE (default gdelt)."""
    from radar.paths import gold

    alt = AI_TABLES.get(name) if os.environ.get("RADAR_SOURCE") == "ai" else None
    return alt if alt and gold(alt).exists() else name


# The entities web/src/App.tsx offers in its context picker (CONTEXT_ENTITIES).
UI_ENTITIES = (
    "org:nvidia",
    "org:microsoft",
    "org:google",
    "org:openai group",
    "thm:TECH_AUTOMATION",
)


def slug(topic_id: str) -> str:
    """File-safe name; web/src/api.ts computes the same one."""
    return re.sub(r"[^a-z0-9]+", "_", topic_id.lower()).strip("_")


def require_full_profile() -> None:
    value = os.environ.get("RADAR_PROFILE", "dev")
    if value != "full":
        raise SystemExit(
            f"refusing: RADAR_PROFILE={value!r}; the static export is built from the full lake only"
        )


def _write(path: Path, body: object) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


EVIDENCE_TOP, EVIDENCE_WEEKS = 10, 4


def iso_week(day: dt.date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def topic_evidence_json(scores: Any, evidence: Any) -> dict[str, dict[str, Any]]:
    """slug -> {topic_id, weeks: {ISO week: [articles]}} for the top 10 of the last 4 scored weeks.

    `scores` is topic_scores_weekly, `evidence` is topic_evidence_weekly (Polars frames). Articles
    keep the contract's fields; weeks without evidence are left out, never invented.
    """
    import polars as pl

    ranked = scores.filter(pl.col("rank").is_not_null() & (pl.col("rank") <= EVIDENCE_TOP))
    weeks = sorted(ranked["week"].unique().to_list())[-EVIDENCE_WEEKS:]
    wanted = ranked.filter(pl.col("week").is_in(weeks)).select("week", "topic_id")
    ev = evidence.with_columns(
        pl.col("week").map_elements(iso_week, return_dtype=pl.String).alias("iso_week")
    ).join(wanted, left_on=["iso_week", "topic_id"], right_on=["week", "topic_id"], how="inner")
    out: dict[str, dict[str, Any]] = {}
    for row in ev.sort(["topic_id", "iso_week", "evidence_rank"]).iter_rows(named=True):
        body = out.setdefault(slug(row["topic_id"]), {"topic_id": row["topic_id"], "weeks": {}})
        article = {
            k: (v.isoformat() if isinstance(v, dt.date) else v)
            for k, v in row.items()
            if k not in {"iso_week", "topic_id", "week"}
        }
        body["weeks"].setdefault(row["iso_week"], []).append(article)
    return out


def export(out: Path = OUT) -> dict[str, int]:
    require_full_profile()
    import polars as pl
    from api.app import app
    from fastapi.testclient import TestClient

    from radar.paths import gold

    client = TestClient(app)

    def get(url: str) -> object:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()

    weeks = (
        pl.scan_parquet(gold(source_table("topic_scores_weekly")))
        .select(pl.col("week").unique())
        .collect()["week"]
        .sort()
        .to_list()
    )
    if not weeks:
        raise SystemExit("topic_scores_weekly has no weeks")
    recent = weeks[-RECENT_WEEKS:]

    tmp = out.with_name(out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    sizes = {"radar": 0, "timeline": 0, "context": 0, "other": 0, "evidence": 0}

    ranked: list[str] = []
    for week in weeks:
        rows = get(f"/api/radar?week={week}&limit={TOP}")
        sizes["radar"] += _write(tmp / "radar" / f"{week}.json", rows)
        if week in recent:
            ranked += [r["topic_id"] for r in rows if r["topic_id"] not in ranked]
    sizes["radar"] += _write(tmp / "radar" / "latest.json", get(f"/api/radar?limit={TOP}"))

    import yaml

    taxonomy = yaml.safe_load((REPO / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
    subtopics = ["ai_all", *taxonomy["subtopics"]]
    entities = [t for t in [*ranked, *UI_ENTITIES] if ":" in t]
    entities = list(dict.fromkeys(entities))
    topics = list(dict.fromkeys([*ranked, *subtopics, *UI_ENTITIES]))

    slugs = {t: slug(t) for t in topics}
    clashes = {s for s in slugs.values() if list(slugs.values()).count(s) > 1}
    if clashes:
        raise SystemExit(f"slug collision for {sorted(clashes)}")

    for topic in topics:
        body = get(f"/api/topic/{quote(topic, safe='')}/timeline")
        sizes["timeline"] += _write(tmp / "timeline" / f"{slugs[topic]}.json", body)
    for topic in entities:
        base = f"/api/topic/{quote(topic, safe='')}/context"
        for week in recent:
            body = get(f"{base}?week={week}")
            sizes["context"] += _write(tmp / "context" / slugs[topic] / f"{week}.json", body)
        sizes["context"] += _write(tmp / "context" / slugs[topic] / "latest.json", get(base))

    sizes["other"] += _write(tmp / "freshness.json", get("/api/freshness"))
    sizes["evidence"] = write_evidence(tmp / "evidence")
    evidence_path = gold("topic_evidence_weekly")
    if evidence_path.exists():
        evidence = topic_evidence_json(
            pl.read_parquet(
                gold(source_table("topic_scores_weekly")), columns=["week", "topic_id", "rank"]
            ),
            pl.read_parquet(evidence_path),
        )
        for name, body in evidence.items():
            sizes["evidence"] += _write(tmp / "evidence" / "topics" / f"{name}.json", body)
    # the UI's cards read these shapes; written last so they win over the summaries above
    for part, n in export_demo_cards(tmp).items():
        sizes[part] = sizes.get(part, 0) + n
    index = {
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": "full",
        "weeks": weeks,
        "latest_week": weeks[-1],
        "recent_weeks": recent,
        "topics": slugs,
        "context_topics": entities,
    }
    sizes["other"] += _write(tmp / "index.json", index)

    shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    print(
        f"{len(weeks)} weeks, {len(topics)} timelines, {len(entities)} rings x "
        f"{len(recent) + 1} weeks -> {out}"
    )
    for part, n in sizes.items():
        print(f"  {part:9s} {n / 2**20:6.2f} MiB")
    print(f"  {'total':9s} {sum(sizes.values()) / 2**20:6.2f} MiB")
    return sizes


def _iso_week(day: dt.date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _ledger_json(reports: Path) -> dict[str, object]:
    """Totals from the committed ledgers. The UI prints these fields; it does not retype them."""
    out: dict[str, object] = {}
    bq = reports / "bq_ledger.csv"
    if bq.exists():
        with bq.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        by_ws: dict[str, int] = defaultdict(int)
        for row in rows:
            billed = (row.get("billed_bytes") or "").strip()
            by_ws[row.get("workstream") or "?"] += int(billed) if billed.isdigit() else 0
        total = sum(by_ws.values())
        out["bigquery"] = {
            "source": "reports/bq_ledger.csv",
            "jobs": len(rows),
            "billed_bytes": total,
            "billed_gb": round(total / 1e9, 2),
            "billed_gb_by_workstream": {k: round(v / 1e9, 2) for k, v in sorted(by_ws.items())},
            "kind": "measured",
        }
    jev = reports / "jev_ledger.csv"
    if jev.exists():
        with jev.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms")]
        out["jev"] = {
            "source": "reports/jev_ledger.csv",
            "calls": len(rows),
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
            "cost_usd": round(sum(float(row.get("cost_usd") or 0) for row in rows), 6),
            "median_latency_ms": statistics.median(latencies) if latencies else None,
            "kind": "measured",
        }
    return out


def export_demo_cards(out: Path = OUT) -> dict[str, int]:
    """Write brief, article, and trust JSON under ``out``. Does not delete other files.

    Missing lake tables are skipped (the UI then says pendiente). Trust JSON is the
    report text and the ledger totals, not a hand-typed summary.
    """
    require_full_profile()
    import polars as pl

    from radar.paths import gold

    sizes = {"briefs": 0, "evidence_topics": 0, "evidence_trust": 0}
    reports = REPO / "reports"
    briefs_path = gold(source_table("topic_briefs_weekly"))
    if briefs_path.exists():
        frame = pl.read_parquet(briefs_path)
        for week in frame["week"].unique().to_list():
            rows = frame.filter(pl.col("week") == week).sort("rank").to_dicts()
            sizes["briefs"] += _write(out / "briefs" / f"{week}.json", rows)
    evidence_path = gold("topic_evidence_weekly")
    if evidence_path.exists():
        frame = pl.read_parquet(evidence_path)
        grouped: dict[str, dict[str, list[dict[str, object]]]] = {}
        ids: dict[str, str] = {}
        for row in frame.sort(["topic_id", "week", "evidence_rank"]).iter_rows(named=True):
            topic_id = str(row["topic_id"])
            name = slug(topic_id)
            ids[name] = topic_id
            weeks = grouped.setdefault(name, {})
            week_value = row["week"]
            week_key = _iso_week(week_value) if isinstance(week_value, dt.date) else str(week_value)
            article = {
                key: value.isoformat() if isinstance(value, dt.date) else value
                for key, value in row.items()
                if key not in {"topic_id", "week"}
            }
            weeks.setdefault(week_key, []).append(article)
        for name, weeks in grouped.items():
            body = {"topic_id": ids[name], "weeks": weeks}
            sizes["evidence_topics"] += _write(out / "evidence" / "topics" / f"{name}.json", body)
    for report_name in ("backtest.md", "label_quality.md"):
        path = reports / report_name
        stem = report_name.removesuffix(".md")
        if path.exists():
            body = {
                "available": True,
                "source": f"reports/{report_name}",
                "markdown": path.read_text(encoding="utf-8"),
                "kind": "measured",
            }
        else:
            body = {
                "available": False,
                "source": f"reports/{report_name}",
                "reason": "not written yet",
            }
        sizes["evidence_trust"] += _write(out / "evidence" / f"{stem}.json", body)
    sizes["evidence_trust"] += _write(out / "evidence" / "ledgers.json", _ledger_json(reports))
    return sizes


def main() -> int:
    if "--cards" in sys.argv:
        sizes = export_demo_cards()
        print(
            "cards -> "
            + ", ".join(f"{name} {n} bytes" for name, n in sizes.items())
            + f" under {OUT}"
        )
        return 0
    export()
    return 0


if __name__ == "__main__":
    sys.exit(main())
