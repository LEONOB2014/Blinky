"""Write the daily_topic week span for the demo freshness line.

Reads parquet footer statistics only (no row scan). The JSON lands in
``web/public/data/``, which is git-ignored. A missing lake is not an error.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


def iso_week_count(start: date, end: date) -> int:
    seen: set[tuple[int, int]] = set()
    day = start
    while day <= end:
        iso = day.isocalendar()
        seen.add((iso.year, iso.week))
        day += timedelta(days=1)
    return len(seen)


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    out = repo / "web" / "public" / "data" / "coverage.json"
    try:
        import duckdb

        from radar.paths import lake
    except ImportError:
        return
    # The freshness line describes the public corpus. Dev-slice numbers are never reported.
    parquet = lake() / "gold" / "daily_topic.parquet"
    if not parquet.exists():
        return
    with duckdb.connect() as con:
        row = con.execute(
            """
            SELECT stats_min_value, stats_max_value
            FROM parquet_metadata(?)
            WHERE path_in_schema = 'dt'
            """,
            [str(parquet)],
        ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return
    start = date.fromisoformat(str(row[0])[:10])
    end = date.fromisoformat(str(row[1])[:10])
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dt_min": start.isoformat(),
        "dt_max": end.isoformat(),
        "span_weeks": iso_week_count(start, end),
    }
    out.write_text(json.dumps(payload) + "\n")


if __name__ == "__main__":
    main()
