# BigQuery scripts

Run order (plan §20 and WS0): guardrails, then Q1–Q4, then S1 → S3 → S2 (newest month first) →
S4 → S8. GCAM (S7, S7d, S9) and the viz export (S10) only after a dry run approved by the lead.
Every job goes through `pipelines/ingest/run_bq.py` once it exists, so its bytes reach
`reports/bq_ledger.csv`.

| Script | Purpose |
|---|---|
| `q1`–`q4` | Reconciliation, column budget, 7-day pilot, embed/GEG probe |
| `s1_setup.sql` | `radar` dataset (US) and `gkg_ai` |
| `s2_monthly_insert.sql` | Monthly backfill into `gkg_ai` |
| `s3_daily_totals.sql` | Normalization denominators |
| `s4_aggregates.sql` | Entities, edges, article topics, `daily_topic` |
| `s5_export.sql`, `export_own_tables.py` | Export own tables to Parquet |
| `s6_scheduled_merge.sql` | Daily scheduled merge (06:00 UTC) |
| `s7_gcam_monthly.sql`, `s7d_gcam_daily.sql`, `s9_gcam_topic.sql` | GCAM emotions |
| `s8_daily_topic_rolling.sql` | Rolling view |
| `s10_graph_viz_export.sql` | Pruned weekly graph for the viz |
| `storage_read_test.py` | Storage Read API test |
| `lex.txt` | URL lexicon |

The Python helpers read `PROJECT = "YOUR_PROJECT_ID"`; set it locally, never commit a real
project id. The production versions read `GCP_PROJECT_ID` from `.env`.
