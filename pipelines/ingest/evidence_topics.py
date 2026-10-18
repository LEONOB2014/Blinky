"""Load the topics that get evidence articles into BigQuery `radar.evidence_topics` (free load job).

The topics are the top 30 ranked topics of each of the last 8 scored weeks of
`lake/gold/topic_scores_weekly.parquet` (WS4). `bq_sql/s14_topic_evidence_weekly.sql` joins them.
A load job bills no bytes; it is printed, not logged in the query ledger.

    RADAR_PROFILE=full uv run python pipelines/ingest/evidence_topics.py
"""

import datetime as dt
import sys
import tempfile
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_bq  # noqa: E402

from radar.paths import gold, profile  # noqa: E402

TOP, WEEKS = 30, 8
TABLE = "radar.evidence_topics"


def monday(label: str) -> dt.date:
    year, week = label.split("-W")
    return dt.date.fromisocalendar(int(year), int(week), 1)


def evidence_topics(scores: pl.LazyFrame) -> pl.DataFrame:
    """(week Monday, topic_id) for the top TOP of each of the last WEEKS scored weeks."""
    ranked = scores.filter(pl.col("rank").is_not_null() & (pl.col("rank") <= TOP))
    weeks = ranked.select(pl.col("week").unique()).collect()["week"].sort().to_list()[-WEEKS:]
    out = (
        ranked.filter(pl.col("week").is_in(weeks))
        .select("week", "topic_id", "rank")
        .collect()
        .with_columns(pl.col("week").map_elements(monday, return_dtype=pl.Date))
        .sort(["week", "rank"])
    )
    return out.select("week", "topic_id")


def main() -> int:
    if profile() != "full":
        raise SystemExit("refusing: set RADAR_PROFILE=full")
    topics = evidence_topics(pl.scan_parquet(gold("topic_scores_weekly")))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_topics.csv"
        topics.write_csv(path, include_header=False)
        run_bq.bq(
            run_bq.project_id(),
            "load",
            "--replace",
            "--source_format=CSV",
            TABLE,
            str(path),
            "week:DATE,topic_id:STRING",
        )
    print(
        f"{TABLE}: {topics.height} rows, {topics['week'].n_unique()} weeks "
        f"({topics['week'].min()}..{topics['week'].max()}), loaded (0 bytes billed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
