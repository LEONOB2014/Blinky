"""Export the real dev slice from BigQuery into fixtures/dev/ (committed, each file under 1 MB).

8 weeks of the gold aggregates and a capped, stratified 7-day sample of radar.gkg_ai, with an
explicit column allow-list: no URLs, titles, person names, locations or free text. Uses the `bq`
CLI (gcloud login); every job's bytes are printed for reports/bq_ledger.csv.

    uv run python scripts/export_dev_slice.py --project <gcp-project-id>
"""

import argparse
import json
import subprocess

import polars as pl

from radar.fixtures import ALLOWED_COLUMNS, DEV_DIR

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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--retype-only", action="store_true", help="re-type existing files, no query")
    args = ap.parse_args()
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
