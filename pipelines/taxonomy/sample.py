"""Stratified Aug-Oct 2026 article sampler for WS2b teacher distillation and active learning.

Runs ``pipelines/taxonomy/sample.sql`` through ``pipelines/ingest/run_bq.py`` (dry run first,
30 GiB cap, logged to ``reports/bq_ledger.csv``) and exports ``radar.label_sample`` via the free
``tabledata.list`` (``bq head``) path to:
- ``lake/labels/sample.parquet`` (4,000 stratified articles: 1,500 ring 1, 1,000 ring 2, 500 ring 3,
  1,000 rejected ``f_control``, >=30% es/pt)
- ``lake/labels/pool.parquet`` (8,000 additional stratified articles for active learning)
- ``lake/labels/sample_meta.json`` (population denominators N_acc, N_rej and sample breakdown)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

from radar.paths import REPO_ROOT, lake

sys.path.insert(0, str(REPO_ROOT / "pipelines" / "ingest"))
import run_bq  # noqa: E402

SQL_PATH = Path(__file__).resolve().parent / "sample.sql"
BQ_TABLE = "radar.label_sample"
CAP_GIB = 30.0
PAGE_SIZE = 50_000

SCHEMA: dict[str, pl.DataType] = {
    "gkg_id": pl.String,
    "dt": pl.Date,
    "source": pl.String,
    "url": pl.String,
    "title": pl.String,
    "lang": pl.String,
    "lang_bucket": pl.String,
    "is_es_pt": pl.Boolean,
    "stratum": pl.String,
    "segment": pl.String,
    "raw_segment": pl.String,
    "domains": pl.String,
    "regex_subtopics": pl.String,
    "top_themes": pl.String,
    "top_orgs": pl.String,
    "tone": pl.Float64,
    "polarity": pl.Float64,
    "word_count": pl.Int64,
    "f_url": pl.Boolean,
    "f_url_short": pl.Boolean,
    "f_title_strong": pl.Boolean,
    "f_title_weak": pl.Boolean,
    "f_org": pl.Boolean,
    "f_latam_loc": pl.Boolean,
    "f_latam_src": pl.Boolean,
    "f_ict": pl.Boolean,
    "f_control": pl.Boolean,
    "tech_org": pl.Boolean,
    "n_ict_themes": pl.Int64,
    "tech_themed": pl.Boolean,
    "rn_stratum": pl.Int64,
    "pool_split": pl.String,
    "pop_n_ring1": pl.Int64,
    "pop_n_ring2": pl.Int64,
    "pop_n_ring3": pl.Int64,
    "pop_n_control_rej": pl.Int64,
    "pop_n_acc_tech_ctrl": pl.Int64,
    "pop_n_rej_tech_ctrl": pl.Int64,
    "pop_n_acc_all_ctrl": pl.Int64,
    "pop_n_rej_all_ctrl": pl.Int64,
}


def cast_rows(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Cast stringified bq head JSON rows to the typed Polars schema."""
    if not rows:
        return pl.DataFrame(schema=SCHEMA)
    raw = pl.DataFrame(rows, schema=dict.fromkeys(SCHEMA, pl.String), strict=False)
    cols = []
    for col, dtype in SCHEMA.items():
        s = raw[col]
        if dtype == pl.Boolean:
            s = s.str.to_lowercase().replace_strict(
                {"true": True, "false": False}, default=False, return_dtype=pl.Boolean
            )
        elif dtype == pl.Date:
            s = s.str.to_date("%Y-%m-%d")
        elif dtype == pl.Int64:
            s = s.cast(pl.Float64).cast(pl.Int64)
        elif dtype == pl.Float64:
            s = s.cast(pl.Float64)
        else:
            s = s.fill_null("")
        cols.append(s.alias(col))
    return pl.DataFrame(cols)


def fetch_table(project: str, table: str = BQ_TABLE) -> pl.DataFrame:
    """Read all rows from radar.label_sample via free tabledata.list (bq head, 0 bytes billed)."""
    info = json.loads(run_bq.bq(project, "--format=json", "show", table))
    total = int(info["numRows"])
    cols = list(SCHEMA.keys())
    frames: list[pl.DataFrame] = []
    for start in range(0, max(total, 1), PAGE_SIZE):
        out = run_bq.bq(
            project,
            "--format=json",
            "head",
            "-n",
            str(PAGE_SIZE),
            "-s",
            str(start),
            "-c",
            ",".join(cols),
            table,
        )
        page_rows = json.loads(out) if out.strip() else []
        if page_rows:
            frames.append(cast_rows(page_rows))
    return pl.concat(frames) if frames else cast_rows([])


def summarize_sample(df: pl.DataFrame) -> dict[str, Any]:
    """Compute summary counts and language shares for reporting and validation."""
    sample_df = df.filter(pl.col("pool_split") == "sample")
    pool_df = df.filter(pl.col("pool_split") == "pool")

    by_stratum = {
        row["stratum"]: {
            "n": int(row["len"]),
            "es_pt_n": int(row["es_pt_n"]),
            "es_pt_share": round(float(row["es_pt_n"]) / max(1, int(row["len"])), 4),
        }
        for row in sample_df.group_by("stratum")
        .agg(pl.len(), pl.col("is_es_pt").sum().alias("es_pt_n"))
        .to_dicts()
    }
    by_lang = {
        row["lang_bucket"]: int(row["len"])
        for row in sample_df.group_by("lang_bucket").len().to_dicts()
    }
    pop_cols = [c for c in SCHEMA if c.startswith("pop_n_")]
    first_row = df.row(0, named=True) if df.height > 0 else {}
    population = {c: int(first_row.get(c) or 0) for c in pop_cols}

    es_pt_total = int(sample_df["is_es_pt"].sum()) if sample_df.height else 0
    return {
        "sample_rows": sample_df.height,
        "pool_rows": pool_df.height,
        "total_exported_rows": df.height,
        "es_pt_rows": es_pt_total,
        "es_pt_share": round(es_pt_total / max(1, sample_df.height), 4),
        "by_stratum": by_stratum,
        "by_lang_bucket": by_lang,
        "population_aug_oct_2026": population,
    }


def write_outputs(df: pl.DataFrame, out_dir: Path | None = None) -> dict[str, Any]:
    """Write sample.parquet, pool.parquet, and sample_meta.json under lake/labels/."""
    labels_dir = out_dir or (lake() / "labels")
    labels_dir.mkdir(parents=True, exist_ok=True)

    sample_df = df.filter(pl.col("pool_split") == "sample").sort(["stratum", "rn_stratum"])
    pool_df = df.filter(pl.col("pool_split") == "pool").sort(["stratum", "rn_stratum"])

    sample_path = labels_dir / "sample.parquet"
    pool_path = labels_dir / "pool.parquet"
    meta_path = labels_dir / "sample_meta.json"

    sample_df.write_parquet(sample_path, compression="zstd")
    pool_df.write_parquet(pool_path, compression="zstd")

    summary = summarize_sample(df)
    meta_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run-only", action="store_true", help="only dry-run sample.sql")
    ap.add_argument(
        "--export-only", action="store_true", help="skip query and export existing table"
    )
    ap.add_argument("--cap-gib", type=float, default=CAP_GIB)
    args = ap.parse_args(argv)

    if not args.export_only:
        bq_args = [
            str(SQL_PATH),
            "--workstream",
            "WS2",
            "--cap-gib",
            str(args.cap_gib),
            "--note",
            "WS2b stratified sample Aug-Oct 2026 + active learning pool",
        ]
        if args.dry_run_only:
            bq_args.append("--dry-run-only")
        rc = run_bq.main(bq_args)
        if rc != 0 or args.dry_run_only:
            return rc

    project = run_bq.project_id()
    df = fetch_table(project, BQ_TABLE)
    summary = write_outputs(df)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
