"""Export the real dev slice from BigQuery into fixtures/dev/ (committed, each file under 1 MB).

8 weeks of the gold aggregates and a capped, stratified 7-day sample of radar.gkg_ai, with an
explicit column allow-list: no URLs, titles, person names, locations or free text. Uses the `bq`
CLI (gcloud login); every job's bytes are printed for reports/bq_ledger.csv.

    uv run python scripts/export_dev_slice.py --project <gcp-project-id>
    RADAR_PROFILE=full uv run python scripts/export_dev_slice.py --topics-from-lake

`--sources-from-lake` cuts `topic_sources_weekly` from the lake for the same weeks and the same
topic ids as the committed `topic_daily` dev cut (no query, nothing billed).

`--topics-from-lake` cuts `topic_daily` and `topic_subtopic_weekly` from the exported lake (no
query, nothing billed): the same 8 weeks, ranked universe only (contracts/taxonomy.yaml
`ranked_universe`), cut to the top topics by articles until each file is under 1 MB.
"""

import argparse
import json
import subprocess

import polars as pl
import yaml

from radar.contracts import CONTRACTS_DIR
from radar.fixtures import ALLOWED_COLUMNS, DEV_DIR
from radar.paths import lake

START, END = "2026-08-24", "2026-10-18"  # 8 Monday weeks: 2026-08-24 .. 2026-10-18 (exclusive)
EDGES_PER_WEEK = 1500
SAMPLE = {"ring1": 900, "ict_only": 300, "control": 300}
CORE_AI = "(f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict))"

QUERIES = {
    "daily_totals": f"""
        SELECT dt, lang_bucket, n_all, n_all_med28, is_missing
        FROM `radar.daily_totals` WHERE dt >= '{START}' AND dt < '{END}'""",
    "daily_topic": f"""
        SELECT * EXCEPT (n_all_stream), n_all_stream FROM `radar.daily_topic`
        WHERE dt >= '{START}' AND dt < '{END}'""",
    "daily_topic_rolling": f"""
        SELECT * FROM `radar.daily_topic_rolling` WHERE dt >= '{START}' AND dt < '{END}'""",
    "edges_weekly": f"""
        SELECT wk, x, y, n, n_src, nx, ny, n_docs, npmi FROM `radar.edges_weekly`
        WHERE wk >= '{START}' AND wk < '{END}'
          AND NOT STARTS_WITH(x, 'per:') AND NOT STARTS_WITH(y, 'per:')
        QUALIFY ROW_NUMBER() OVER (PARTITION BY wk ORDER BY n DESC, x, y) <= {EDGES_PER_WEEK}""",
    "gkg_ai_sample": f"""
        WITH s AS (
          SELECT *, CASE WHEN {CORE_AI} THEN 'ring1' WHEN f_control THEN 'control'
                         WHEN f_ict THEN 'ict_only' END AS stratum
          FROM `radar.gkg_ai` WHERE dt >= '2026-10-11' AND dt < '2026-10-18')
        SELECT gkg_id, ts, dt, source, lang, tone, pos_score, neg_score, polarity,
          activity_density, self_group_ref_density, word_count, orgs, themes,
          f_url, f_url_short, f_title_strong, f_title_weak, f_org, f_latam_loc, f_latam_src,
          f_ict, f_control, stratum
        FROM s WHERE stratum IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY stratum ORDER BY FARM_FINGERPRINT(gkg_id)) <=
          CASE stratum WHEN 'ring1' THEN {SAMPLE["ring1"]} WHEN 'ict_only' THEN {SAMPLE["ict_only"]}
                       ELSE {SAMPLE["control"]} END""",
}


def run(project: str, sql: str) -> list[dict]:
    cmd = [
        "bq",
        f"--project_id={project}",
        "--location=US",
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "--max_rows=1000000",
        "--maximum_bytes_billed=21474836480",
        sql,
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return json.loads(out[out.index("[") :]) if "[" in out else []


def coerce(frame: pl.DataFrame) -> pl.DataFrame:
    """`bq --format=json` returns every value as a string: restore booleans, numbers and dates."""
    out = []
    for name in frame.columns:
        col = frame[name]
        if col.dtype != pl.String:
            out.append(col)
            continue
        vals = col.drop_nulls()
        if name in {"dt", "wk"}:
            out.append(col.str.to_date())
        elif name == "ts":
            out.append(col.str.to_datetime("%Y-%m-%d %H:%M:%S", time_zone="UTC"))
        elif vals.len() and vals.is_in(["true", "false"]).all():
            out.append(col == "true")
        elif vals.len() and vals.str.contains(r"^-?[0-9]+$").all():
            out.append(col.cast(pl.Int64))
        elif vals.len() and vals.str.contains(r"^-?[0-9.]+([eE][-+]?[0-9]+)?$").all():
            out.append(col.cast(pl.Float64))
        else:
            out.append(col)
    return pl.DataFrame(out)


MAX_BYTES = 950_000  # margin under the 1 MB fixture limit


def ranked_universe(weekly_articles: pl.DataFrame) -> pl.Series:
    """Ranked-universe topic_ids: allowed orgs and theme prefixes that reach the weekly floor."""
    spec = yaml.safe_load((CONTRACTS_DIR / "taxonomy.yaml").read_text(encoding="utf-8"))
    spec = spec["ranked_universe"]
    deny = [f"org:{name}" for name in spec["org_deny"]]
    kinds = []
    if spec.get("org"):
        kinds.append(pl.col("topic_id").str.starts_with("org:") & ~pl.col("topic_id").is_in(deny))
    for prefix in spec.get("thm_prefixes", []):
        kinds.append(pl.col("topic_id").str.starts_with(f"thm:{prefix}"))
    eligible = weekly_articles.filter(
        pl.any_horizontal(kinds) & (pl.col("n") >= spec["min_articles_week"])
    )
    return eligible["topic_id"].unique()


def topics_from_lake() -> None:
    start, end = pl.lit(START).str.to_date(), pl.lit(END).str.to_date()
    daily = pl.read_parquet(lake() / "gold" / "topic_daily.parquet").filter(
        (pl.col("dt") >= start) & (pl.col("dt") < end)
    )
    weekly = pl.read_parquet(lake() / "gold" / "topic_subtopic_weekly.parquet").filter(
        (pl.col("week") >= start) & (pl.col("week") < end)
    )
    week_totals = daily.group_by("topic_id", pl.col("dt").dt.truncate("1w").alias("week")).agg(
        pl.col("n_articles").sum().alias("n")
    )
    universe = ranked_universe(week_totals)
    by_volume = (
        daily.filter(pl.col("topic_id").is_in(universe.to_list()))
        .group_by("topic_id")
        .agg(pl.col("n_articles").sum().alias("n"))
        .sort(["n", "topic_id"], descending=[True, False])["topic_id"]
    )
    keep = by_volume.len()
    while True:
        top = by_volume.head(keep)
        files = {
            "topic_daily": daily.filter(pl.col("topic_id").is_in(top.to_list())).sort(
                ["topic_id", "dt", "lang_bucket"]
            ),
            "topic_subtopic_weekly": weekly.filter(pl.col("topic_id").is_in(top.to_list())).sort(
                ["topic_id", "week", "subtopic"], nulls_last=True
            ),
        }
        sizes = {}
        for name, frame in files.items():
            extra = set(frame.columns) - ALLOWED_COLUMNS[name]
            if extra:
                raise SystemExit(f"{name}: columns outside the allow-list: {sorted(extra)}")
            path = DEV_DIR / f"{name}.parquet"
            frame.write_parquet(path, compression="zstd", compression_level=19)
            sizes[name] = path.stat().st_size
        if max(sizes.values()) < MAX_BYTES:
            break
        keep = int(keep * 0.9)
    print(f"ranked universe in the window: {by_volume.len()} topics; kept the top {keep}")
    for name, frame in files.items():
        print(f"{name}: {frame.height} rows, {sizes[name] / 1024:.0f} KiB")


def sources_from_lake() -> None:
    """topic_sources_weekly for the topics and weeks of the committed topic_daily dev cut."""
    topics = pl.read_parquet(DEV_DIR / "topic_daily.parquet", columns=["topic_id"])["topic_id"]
    start, end = pl.lit(START).str.to_date(), pl.lit(END).str.to_date()
    frame = (
        pl.scan_parquet(lake() / "gold" / "topic_sources_weekly.parquet")
        .filter(
            (pl.col("week") >= start)
            & (pl.col("week") < end)
            & pl.col("topic_id").is_in(topics.unique().to_list())
        )
        .sort(["topic_id", "week"])
        .collect()
    )
    extra = set(frame.columns) - ALLOWED_COLUMNS["topic_sources_weekly"]
    if extra:
        raise SystemExit(f"topic_sources_weekly: columns outside the allow-list: {sorted(extra)}")
    path = DEV_DIR / "topic_sources_weekly.parquet"
    frame.write_parquet(path, compression="zstd", compression_level=19)
    size = path.stat().st_size
    if size >= MAX_BYTES:
        raise SystemExit(f"{path.name} is {size} bytes, over the fixture limit")
    print(
        f"topic_sources_weekly: {frame.height} rows, {frame['topic_id'].n_unique()} topics, "
        f"{size / 1024:.0f} KiB"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project")
    ap.add_argument("--retype-only", action="store_true", help="re-type existing files, no query")
    ap.add_argument(
        "--topics-from-lake", action="store_true", help="cut the topic tables from lake/gold"
    )
    ap.add_argument(
        "--sources-from-lake",
        action="store_true",
        help="cut topic_sources_weekly from lake/gold for the topic_daily dev cut",
    )
    args = ap.parse_args()
    if args.sources_from_lake:
        sources_from_lake()
        return
    if args.topics_from_lake:
        topics_from_lake()
        return
    if not args.project:
        ap.error("--project is required to query BigQuery")
    if args.retype_only:
        for path in sorted(DEV_DIR.glob("*.parquet")):
            coerce(pl.read_parquet(path)).write_parquet(
                path, compression="zstd", compression_level=19
            )
            print(f"retyped {path.name}")
        return
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    for name, sql in QUERIES.items():
        frame = coerce(pl.DataFrame(run(args.project, sql), infer_schema_length=None))
        extra = set(frame.columns) - ALLOWED_COLUMNS[name]
        if extra:
            raise SystemExit(f"{name}: columns outside the allow-list: {sorted(extra)}")
        path = DEV_DIR / f"{name}.parquet"
        frame.write_parquet(path, compression="zstd", compression_level=19)
        print(f"{name}: {frame.height} rows, {path.stat().st_size / 1024:.0f} KiB -> {path}")


if __name__ == "__main__":
    main()
