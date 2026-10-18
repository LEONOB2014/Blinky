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
Topics: every topic in a top 10 of the last 4 weeks, the subtopics (timelines only) and the
entities the UI offers by default.
"""

import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "web" / "public" / "data"
TOP = 10
RECENT_WEEKS = 4
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
        pl.scan_parquet(gold("topic_scores_weekly"))
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
    sizes = {"radar": 0, "timeline": 0, "context": 0, "other": 0}

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


def main() -> int:
    export()
    return 0


if __name__ == "__main__":
    sys.exit(main())
