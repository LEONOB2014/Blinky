"""Upload the lake tables the API reads to the Modal Volume `radar-lake` (as gold/<name>.parquet).

`TABLES` is also the list the Cloud Run image stages (deploy/cloudrun_stage.py).

Only the listed tables: public GDELT aggregates, no persons as ranked topics, no titles or URLs
(except the evidence table). `plan()` checks both before anything is staged. `edges_weekly` (~440
MB) is never uploaded: the API reads the precomputed 1-hop ring instead. `edges_ai_weekly` is left
out too: no live reader (the agents' graph tools still read `edges_weekly`, which is absent on the
service), and the AI graph is exported offline into `views/` by `graph/export_views.py`.

    RADAR_PROFILE=full uv run --extra deploy python deploy/push_lake.py
    RADAR_PROFILE=full uv run --extra deploy python deploy/push_lake.py --dry-run
"""

import argparse
import sys

from radar.paths import gold, profile

VOLUME_NAME = "radar-lake"
TABLES = (
    "topic_scores_weekly",
    "topic_daily",
    "topic_context_1hop",
    "daily_topic",
    "daily_topic_rolling",
    "daily_totals",
    "node_metrics_weekly",
    # Read by the agents' tools on the live API (briefs and evidence for the Editor and the Signal
    # analyst, source diversity, the topic's subtopics). topic_evidence_weekly holds public news
    # titles and URLs: they reach the image and the deployed site, never git.
    "topic_briefs_weekly",
    "topic_evidence_weekly",
    "topic_sources_weekly",
    "topic_subtopic_weekly",
    # The AI radar (RADAR_SOURCE=ai): scores, series and briefs of the AI-lexicon run, the Wikipedia
    # pageviews behind its backtest label, and the AI community signal (/api/community). Sources and
    # evidence for ai: topics are rows of the shared tables above.
    "topic_ai_scores_weekly",
    "topic_ai_daily",
    "topic_ai_briefs_weekly",
    "wiki_pageviews_ai_daily",
    "community_topic_weekly",
)
NEVER = {"edges_weekly", "edges_ai_weekly"}
# Tables allowed to carry article titles and URLs (public news, image and deployed site, never git).
TEXT_ALLOWED = {"topic_evidence_weekly"}
TEXT_COLUMNS = ("title", "url")


def plan() -> list[tuple[str, int]]:
    """(table, bytes) per listed table; exits if one is missing or the profile is not full."""
    if profile() != "full":
        raise SystemExit("refusing: set RADAR_PROFILE=full (the dev slice is never deployed)")
    if NEVER & set(TABLES):
        raise SystemExit(f"never uploaded: {sorted(NEVER & set(TABLES))}")
    missing = [t for t in TABLES if not gold(t).exists()]
    if missing:
        raise SystemExit(f"missing in the lake: {missing}")
    for t in TABLES:
        guard(t)
    return [(t, gold(t).stat().st_size) for t in TABLES]


def guard(table: str) -> None:
    """Refuse a table with persons as topics, or with title/URL columns it may not carry."""
    import polars as pl

    frame = pl.scan_parquet(gold(table))
    cols = frame.collect_schema().names()
    text = [c for c in cols if c.lower() in TEXT_COLUMNS]
    if text and table not in TEXT_ALLOWED:
        raise SystemExit(f"refusing: {table} has title/URL columns {text}")
    if "topic_id" in cols:
        persons = frame.select(pl.col("topic_id").str.starts_with("per:").sum()).collect().item()
        if persons:
            raise SystemExit(f"refusing: {table} has {persons} person rows (per:)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="list what would be uploaded")
    args = ap.parse_args(argv)
    files = plan()
    for name, size in files:
        print(f"{name:24s} {size / 2**20:7.1f} MiB")
    print(f"{'total':24s} {sum(s for _, s in files) / 2**20:7.1f} MiB -> volume {VOLUME_NAME}")
    if args.dry_run:
        return 0

    import modal

    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    with volume.batch_upload(force=True) as batch:
        for name, _ in files:
            batch.put_file(str(gold(name)), f"/gold/{name}.parquet")
    listed = sorted(e.path for e in volume.listdir("/gold"))
    print("volume /gold:", ", ".join(listed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
