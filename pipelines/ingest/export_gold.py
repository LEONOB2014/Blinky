"""Export WS1's gold tables from BigQuery to lake/gold/<name>.parquet, typed by the contracts.

Tables are read through the free tabledata.list path (``bq head``, no bytes billed) in parallel
pages; the one view (``daily_topic_rolling``) through a small query whose bytes go to the ledger.
Only the contract's columns are read. 1,000 sampled rows per table are validated with
``radar.contracts.validate_records``; any violation aborts before the file is replaced. Uses the
``bq`` CLI (gcloud login).

    uv run python pipelines/ingest/export_gold.py               # every table
    uv run python pipelines/ingest/export_gold.py edges_weekly  # one table
"""

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_bq  # noqa: E402

from radar.contracts import load_schema, validate_records  # noqa: E402
from radar.paths import lake  # noqa: E402

# name -> (BigQuery object, is_view)
TABLES = {
    "daily_totals": ("radar.daily_totals", False),
    "daily_topic": ("radar.daily_topic", False),
    "daily_topic_rolling": ("radar.daily_topic_rolling", True),
    "topic_daily": ("radar.topic_daily", False),
    "edges_weekly": ("radar.edges_weekly", False),
    "topic_subtopic_weekly": ("radar.topic_subtopic_weekly", False),
    "topic_sources_weekly": ("radar.topic_sources_weekly", False),
    # Titles and URLs: lake and deployed site only, never git (contract x-mock: private).
    "topic_evidence_weekly": ("radar.topic_evidence_weekly", False),
}
PAGE = 100_000
WORKERS = 8
SAMPLE = 1_000


def _json_type(spec: dict) -> str:
    kinds = spec.get("type", "string")
    kinds = [kinds] if isinstance(kinds, str) else kinds
    kind = next((k for k in kinds if k != "null"), "string")
    if kind == "string" and spec.get("format") == "date":
        return "date"
    if "const" in spec and kind == "string":
        return "string"
    return kind


def polars_schema(name: str) -> dict[str, pl.DataType]:
    """Column -> polars dtype from the contract's JSON Schema (property order kept)."""
    mapping = {
        "integer": pl.Int64,
        "number": pl.Float64,
        "boolean": pl.Boolean,
        "date": pl.Date,
        "string": pl.String,
    }
    props = load_schema(name)["properties"]
    return {col: mapping[_json_type(spec)] for col, spec in props.items()}


def typed(rows: list[dict], schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """bq JSON values are strings (or absent when NULL): cast each column to its contract type."""
    raw = pl.DataFrame(rows, schema=dict.fromkeys(schema, pl.String), strict=False)
    out = []
    for col, dtype in schema.items():
        s = raw[col]
        if dtype == pl.Boolean:
            s = s.str.to_lowercase().replace_strict(
                {"true": True, "false": False}, default=None, return_dtype=pl.Boolean
            )
        elif dtype == pl.Date:
            s = s.str.to_date("%Y-%m-%d")
        elif dtype == pl.Int64:
            s = s.cast(pl.Float64).cast(pl.Int64)  # bq may print integers as "12.0" in views
        else:
            s = s.cast(dtype)
        out.append(s.alias(col))
    return pl.DataFrame(out)


def records_for_validation(frame: pl.DataFrame) -> list[dict]:
    """JSON-like records: dates as ISO strings, NaN as None (JSON Schema has no NaN)."""
    recs = []
    for rec in frame.to_dicts():
        clean = {}
        for key, value in rec.items():
            if isinstance(value, dt.date):
                value = value.isoformat()
            elif isinstance(value, float) and value != value:
                value = None
            clean[key] = value
        recs.append(clean)
    return recs


def sample_for_validation(frame: pl.DataFrame, n: int = SAMPLE, seed: int = 7) -> pl.DataFrame:
    return frame if frame.height <= n else frame.sample(n=n, seed=seed)


def present_columns(project: str, table: str, wanted: list[str]) -> list[str]:
    info = json.loads(run_bq.bq(project, "--format=json", "show", table))
    have = {f["name"] for f in info["schema"]["fields"]}
    return [c for c in wanted if c in have]


def num_rows(project: str, table: str) -> int:
    return int(json.loads(run_bq.bq(project, "--format=json", "show", table))["numRows"])


def read_page(project: str, table: str, cols: list[str], start: int) -> list[dict]:
    out = run_bq.bq(
        project,
        "--format=json",
        "head",
        "-n",
        str(PAGE),
        "-s",
        str(start),
        "-c",
        ",".join(cols),
        table,
    )
    return json.loads(out) if out.strip() else []


def read_view(project: str, view: str, cols: list[str]) -> list[dict]:
    """A view has no tabledata: query it (small: it reads only our aggregate tables) and log it."""
    sql = f"SELECT {', '.join(cols)} FROM `{view}`"
    job_id = run_bq.new_job_id(Path("export_gold.py"), None)
    dry, _ = run_bq.dry_run(project, sql)
    cap = int(run_bq.default_cap_gib() * run_bq.GIB)
    if dry > cap:
        raise run_bq.GuardError(f"{view}: dry run {dry} bytes exceeds the cap")
    out = run_bq.bq(
        project,
        "--format=json",
        "query",
        "--use_legacy_sql=false",
        "--max_rows=100000000",
        f"--job_id={job_id}",
        f"--maximum_bytes_billed={cap}",
        sql,
    )
    billed = run_bq.billed_bytes(project, job_id)
    run_bq.append_ledger(
        run_bq.ledger_row(
            job_id,
            f"export_gold.py ({view})",
            "WS1",
            dry,
            billed,
            run_bq.default_cap_gib(),
            "gold export of a view (measured)",
        )
    )
    return json.loads(out[out.index("[") :]) if "[" in out else []


def export(project: str, name: str) -> Path:
    """Write lake/gold/<name>.parquet. Table pages stream to part files, so memory stays flat."""
    table, is_view = TABLES[name]
    schema = polars_schema(name)
    cols = list(schema) if is_view else present_columns(project, table, list(schema))
    types = {c: schema[c] for c in cols}
    path = lake() / "gold" / f"{name}.parquet"
    parts = path.parent / f".parts_{name}"
    shutil.rmtree(parts, ignore_errors=True)
    parts.mkdir(parents=True)
    try:
        if is_view:
            frame = typed(read_view(project, table, cols), types)
            frame.write_parquet(parts / "part-00000.parquet")
            total, samples = frame.height, [sample_for_validation(frame)]
        else:
            total = num_rows(project, table)
            starts = list(range(0, total, PAGE))
            per_page = -(-SAMPLE // max(1, len(starts)))

            def fetch(i_start: tuple[int, int]) -> tuple[int, pl.DataFrame]:
                i, start = i_start
                frame = typed(read_page(project, table, cols, start), types)
                frame.write_parquet(parts / f"part-{i:05d}.parquet")
                return frame.height, sample_for_validation(frame, per_page, seed=i)

            with ThreadPoolExecutor(WORKERS) as pool:
                results = list(pool.map(fetch, enumerate(starts)))
            read = sum(h for h, _ in results)
            if read != total:
                raise RuntimeError(f"{table}: read {read:,} rows, table has {total:,}")
            samples = [smp for _, smp in results]
        sample = sample_for_validation(pl.concat(samples))
        errors = validate_records(name, records_for_validation(sample))
        if errors:
            raise SystemExit(f"{name}: {len(errors)} contract violations, e.g. {errors[:3]}")
        tmp = path.with_suffix(".parquet.tmp")
        pl.scan_parquet(parts / "*.parquet").sink_parquet(tmp, compression="zstd")
        tmp.replace(path)
    finally:
        shutil.rmtree(parts, ignore_errors=True)
    print(
        f"{name}: {total:,} rows, {path.stat().st_size / 2**20:.1f} MiB, "
        f"{sample.height} sampled rows valid -> {path}"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("names", nargs="*", help=f"subset of {sorted(TABLES)} (default: all)")
    args = ap.parse_args(argv)
    unknown = set(args.names) - TABLES.keys()
    if unknown:
        ap.error(f"unknown tables {sorted(unknown)}")
    if os.environ.get("RADAR_PROFILE", "dev") != "full":
        print("note: writing the full lake (RADAR_PROFILE=full is what reads it back)")
    project = run_bq.project_id()
    for name in args.names or list(TABLES):
        export(project, name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
