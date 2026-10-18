# BigQuery scripts

Run order (plan §20 and WS0): guardrails, then Q1–Q4, then S1 → S3 → S2 and S4a per month
(newest month first) → S4 → S8 → S11. GCAM (S7, S7d, S9) and the viz export (S10) only after a dry
run approved by the lead. Every job goes through `pipelines/ingest/run_bq.py`, so its bytes reach
`reports/bq_ledger.csv`:

```bash
uv run python pipelines/ingest/run_bq.py bq_sql/s2_monthly_insert.sql --month 2026-07
uv run python pipelines/ingest/run_bq.py bq_sql/s4a_article_segment.sql --month 2026-07
uv run python pipelines/ingest/run_bq.py bq_sql/s4_aggregates.sql
uv run python pipelines/ingest/run_bq.py bq_sql/s8_daily_topic_rolling.sql
uv run python pipelines/ingest/run_bq.py bq_sql/s11_topic_daily.sql
RADAR_PROFILE=full uv run python pipelines/ingest/export_gold.py
```

S2 is not idempotent (it appends a month): never run the same month twice. S4a is (it deletes the
month first). When an input grew on purpose (a backfill), pass `--baseline-scale` so the 1.5x guard
compares against the expected size; a script with no history and a lower-bound dry run needs
`--expect-gib`.

| Script | Purpose |
|---|---|
| `q1`–`q4` | Reconciliation, column budget, 7-day pilot, embed/GEG probe |
| `s1_setup.sql` | `radar` dataset (US) and `gkg_ai` |
| `s2_monthly_insert.sql` | Monthly backfill into `gkg_ai` |
| `s3_daily_totals.sql` | Normalization denominators |
| `s4a_article_segment.sql` | Monthly: the three rings per article, ring-1 entity arrays (`article_segment`) |
| `s4_aggregates.sql` | Topic rules, ring-1 entities and edges, article topics, `daily_topic` (with `segment`, `domain`) |
| `s5_export.sql`, `export_own_tables.py` | Export own tables to Parquet |
| `s6_scheduled_merge.sql` | Daily scheduled merge (06:00 UTC) |
| `s7_gcam_monthly.sql`, `s7d_gcam_daily.sql`, `s9_gcam_topic.sql` | GCAM emotions |
| `s8_daily_topic_rolling.sql` | Rolling view |
| `s10_graph_viz_export.sql` | Pruned weekly graph for the viz |
| `s11_topic_daily.sql` | `topic_daily`: the per-topic (org, theme) series in ring 1 |
| `storage_read_test.py` | Storage Read API test |
| `lex.txt` | URL lexicon |

The Python helpers read `PROJECT = "YOUR_PROJECT_ID"`; set it locally, never commit a real
project id. The production versions read `GCP_PROJECT_ID` from `.env`.
