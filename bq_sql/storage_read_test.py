"""Test: read ONE day of gkg_partitioned through the BigQuery Storage Read API with a server-side row filter.
Query bytes = 0. Read bytes count against the 300 TiB/month free Storage Read tier. Egress ($0.12/GiB outside
Google Cloud) applies only to the rows actually returned. pip install google-cloud-bigquery-storage pyarrow polars
Auth: gcloud auth application-default login.  Set PROJECT below."""

import time

import polars as pl
import pyarrow as pa
from google.cloud import bigquery_storage_v1 as bqs
from google.cloud.bigquery_storage_v1 import types

PROJECT = "YOUR_PROJECT_ID"
COLS = [
    "GKGRECORDID",
    "DATE",
    "SourceCommonName",
    "DocumentIdentifier",
    "TranslationInfo",
    "V2Tone",
    "V2Organizations",
    "V2Persons",
    "V2Themes",
    "V2Locations",
    "AllNames",
    "Extras",
]
# Try 1: REGEXP_CONTAINS. If the API rejects it, try 2: LIKE. If both are rejected, this path is not viable.
FILTERS = [
    "_PARTITIONTIME = TIMESTAMP('2026-10-16') AND REGEXP_CONTAINS(LOWER(DocumentIdentifier), r'openai|chatgpt|artificial-intelligence|inteligencia-artificial|anthropic|nvidia|generative-ai|ia-generativa|[/_-]ai[/_.-]')",
    "_PARTITIONTIME = TIMESTAMP('2026-10-16') AND (LOWER(DocumentIdentifier) LIKE '%openai%' OR LOWER(DocumentIdentifier) LIKE '%chatgpt%' OR LOWER(DocumentIdentifier) LIKE '%artificial-intelligence%' OR LOWER(DocumentIdentifier) LIKE '%inteligencia-artificial%')",
]
client = bqs.BigQueryReadClient()
for flt in FILTERS:
    try:
        t0 = time.time()
        session = client.create_read_session(
            parent=f"projects/{PROJECT}",
            read_session=types.ReadSession(
                table="projects/gdelt-bq/datasets/gdeltv2/tables/gkg_partitioned",
                data_format=types.DataFormat.ARROW,
                read_options=types.ReadSession.TableReadOptions(
                    selected_fields=COLS, row_restriction=flt
                ),
            ),
            max_stream_count=4,
        )
        tables = [client.read_rows(s.name).to_arrow(session) for s in session.streams]
        df = pl.from_arrow(pa.concat_tables(tables)) if tables else pl.DataFrame()
        print(
            "FILTER OK:",
            flt[:80],
            "| rows",
            df.height,
            "| MB",
            round(df.estimated_size("mb"), 1),
            "| est. bytes scanned by session",
            getattr(session, "estimated_total_bytes_scanned", "n/a"),
            "| s",
            round(time.time() - t0, 1),
        )
        df.write_parquet("storage_read_test.parquet")
        break
    except Exception as e:
        print("FILTER REJECTED:", flt[:80], "->", str(e)[:300])
