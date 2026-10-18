"""Upload the lake tables the API reads to the Modal Volume `radar-lake` (as gold/<name>.parquet).

Only the listed tables: public GDELT aggregates, no persons as ranked topics, no titles or URLs.
`edges_weekly` (~440 MB) is never uploaded: the API reads the precomputed 1-hop ring instead.

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
)
NEVER = {"edges_weekly"}


def plan() -> list[tuple[str, int]]:
    """(table, bytes) per listed table; exits if one is missing or the profile is not full."""
    if profile() != "full":
        raise SystemExit("refusing: set RADAR_PROFILE=full (the dev slice is never deployed)")
    if NEVER & set(TABLES):
        raise SystemExit(f"never uploaded: {sorted(NEVER & set(TABLES))}")
    missing = [t for t in TABLES if not gold(t).exists()]
    if missing:
        raise SystemExit(f"missing in the lake: {missing}")
    return [(t, gold(t).stat().st_size) for t in TABLES]


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
