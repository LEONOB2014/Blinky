"""Download OUR small tables to Parquet. Default = free tabledata.list path (no Storage API, slower).
Set FAST=True to use the Storage Read API (read bytes within 300 TiB free; egress ~$0.12/GiB outside GCP)."""

import polars as pl
from google.cloud import bigquery

PROJECT, FAST = "YOUR_PROJECT_ID", False
client = bigquery.Client(project=PROJECT)
for t in [
    "gkg_ai",
    "daily_totals",
    "article_entities",
    "edges_weekly",
    "article_topic",
    "daily_topic",
]:
    tbl = client.get_table(f"{PROJECT}.radar.{t}")
    arrow = client.list_rows(tbl).to_arrow(create_bqstorage_client=FAST)
    pl.from_arrow(arrow).write_parquet(f"{t}.parquet", compression="zstd")
    print(t, tbl.num_rows, "rows,", round(tbl.num_bytes / 2**30, 2), "GiB logical")
