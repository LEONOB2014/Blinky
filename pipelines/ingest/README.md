# WS1: BigQuery and ingestion

Wraps `bq_sql/` in `run_bq.py` (dry run first, abort above 1.5x the ledger, log bytes to `reports/bq_ledger.csv`), exports own tables to Parquet in `lake/gold/`, runs the 15-minute raw-file poller and the daily DQ table.

Plan: [MASTER_PLAN §15.1](../../docs/plan/MASTER_PLAN.pdf). Status: [status/WS1.md](../../status/WS1.md).

- `run_bq.py`: run one `bq_sql/` file with `--month`; dry run, guard (cap, 1.5x the last bill;
  multi-statement scripts use the last bill, not the dry run), ledger row, job id and billed bytes.
- `export_gold.py`: `daily_totals`, `daily_topic`, `daily_topic_rolling`, `topic_daily`,
  `edges_weekly` → `lake/gold/<name>.parquet`, through the free tabledata.list path, 1,000 sampled
  rows per table validated against the contract.
- Tests: `make test` (offline), `RADAR_PROFILE=full uv run pytest -m data` (the exported lake).
