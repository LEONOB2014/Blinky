# WS1: BigQuery and ingestion

Wraps `bq_sql/` in `run_bq.py` (dry run first, abort above 1.5x the ledger, log bytes to `reports/bq_ledger.csv`), exports own tables to Parquet in `lake/gold/`, runs the 15-minute raw-file poller and the daily DQ table.

Plan: [MASTER_PLAN §15.1](../../docs/plan/MASTER_PLAN.pdf). Status: [status/WS1.md](../../status/WS1.md).
