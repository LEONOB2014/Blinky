# BRIEF: WS1 + WS2, the GDELT loop (Scout and Curator)

Account: **Claude #2** · Branch: `feat/ws1-gdelt-loop` · Worktree: `../radar-worktrees/feat-ws1-gdelt-loop`
Written by the orchestrator, 2026-10-17 20:40 UTC-5. Read `AGENTS.md`, then this file; nothing else is required.

## Goal

Turn the BigQuery extract into the three segments and the per-topic series the radar ranks, guarded by
a cost ledger, and backfill 12 months (minimum 6) so the backtest has history.

## Plan reference

`docs/designs/radar-build-plan.md`: "The GDELT loop", "Ring rules", "What is ranked"; `contracts/taxonomy.yaml`;
MASTER_PLAN §5, §8, §9.

## What already exists (measured tonight by the orchestrator, see `reports/bq_ledger.csv`)

- GCP project `project-fe4ffce1-541e-49b3-b9b` (in `.env` as `GCP_PROJECT_ID`), dataset `radar` (US). The
  `bq` CLI works with the gcloud login; Python ADC is NOT set up (use the `bq` CLI via `subprocess`, as
  `scripts/export_dev_slice.py` does).
- `radar.gkg_ai`: 4.31M rows, 2026-08-01..2026-10-18, from `bq_sql/s2_monthly_insert.sql` (wide net). S2 costs
  ~22.5 GB per month (Aug 22.7, Sep 22.4, measured).
- `daily_totals` (2 years), `article_entities`, `edges_weekly`, `article_topic`, `daily_topic`, view
  `daily_topic_rolling` (S3, S4, S8). S4 billed 14.2 GB vs a 10.6 GB dry run: multi-statement dry runs
  underestimate.
- Findings you must fix: (1) `f_ict` tags ~1.4M rows/month, so ring 2 is far too broad; (2) S4 builds
  entities and edges from every row (ring 1, ICT, control), but ranking and the 1-hop ring use ring-1
  articles only; (3) `daily_topic` has no `segment`/`domain`.

## Inputs

`contracts/` (read every schema you write), `contracts/taxonomy.yaml`, `bq_sql/`, `fixtures/dev/` (the
real dev slice; `RADAR_PROFILE=dev` reads it).

## Outputs

1. `pipelines/ingest/run_bq.py`: runs a `bq_sql/` file with month parameters; dry run first; aborts if the
   dry run exceeds the cap (default 50 GiB) or 1.5x the previous run of the same script; for scripts with
   several statements, uses 1.5x the last measured bill instead of trusting the dry run; appends one row
   per job to `reports/bq_ledger.csv` (same columns as today); prints job id and billed bytes.
2. `bq_sql/s4_aggregates.sql` (edit) and a new `bq_sql/s11_topic_daily.sql`:
   - segment and domain per article exactly as `contracts/taxonomy.yaml` (ring 1 iff the core-AI rule;
     ring 2 tightened: ICT theme AND (tech organization OR a second ICT theme), minus ring 1; ring 3 =
     domain theme group AND tech organization, minus rings 1-2);
   - `article_entities` and `edges_weekly` built from **ring-1 articles only**;
   - `daily_topic` with `segment` and `domain` (contract `daily_topic.schema.json`), `energy_climate` added
     to `topic_rules` (regex in `taxonomy.yaml`);
   - `radar.topic_daily` per `contracts/topic_daily.schema.json` (orgs and GKG themes in ring 1, never persons).
3. Backfill S2 for 2026-07 back to 2025-11 (newest first) through `run_bq.py`, then re-run S4, S8, S11.
4. `pipelines/ingest/export_gold.py`: writes every gold table of the contracts you own to
   `lake/gold/<name>.parquet` (`RADAR_PROFILE=full`), validating 1,000 sampled rows per table with
   `radar.contracts.validate_records`.
5. `status/WS1.md` updated at each sync.

## Files you may touch

`pipelines/ingest/**`, `pipelines/taxonomy/**`, `bq_sql/**`, `reports/bq_ledger.csv`, `status/WS1.md`,
`status/WS2.md`, tests under `pipelines/**/tests/`, and the `bq` extra in `pyproject.toml`/`uv.lock` if you
need a dependency.

## Out of scope

Contracts (ask the orchestrator), `fixtures/dev/` and `mocks/` (the orchestrator refreshes them from your
output), scores, graphs, the API. No LLM labelling in this brief (a second brief follows once the backfill
runs unattended).

## Steps

1. `make setup` once; `uv sync --extra bq`.
2. Write `run_bq.py` and its unit tests first (parse a real dry-run line such as `running this query will
   process upper bound of 12499550274 bytes of data`; guard logic; ledger row format). No network in tests.
3. Edit S4, add S11; run them on Aug-Oct through `run_bq.py`; check the loop checks below; iterate.
4. Backfill months newest first; re-run S4, S8, S11 once at the end.
5. Export gold to the lake.

## Acceptance

- `make check && make test` pass (tests need no network).
- GDELT loop checks, written to `status/WS1.md` with numbers marked measured: per-segment row counts per
  month; ring 2 under ~400k rows/month after tightening (target, report the real value); `is_missing` days
  are NULL in `daily_topic_rolling`; regex subtopic counts per month; `topic_daily` distinct topics per week
  with >= 20 articles (expected 150-400, report the real value).
- `RADAR_PROFILE=full uv run pytest -m data` passes on the exported lake (write these tests).

## Paid or outward actions needing approval (ask in the chat; the orchestrator relays)

- Any single job above 50 GiB, or the backfill total above 250 GB billed (expected ~9 x 22.5 = ~200 GB,
  estimate). `git push` and opening the PR.

## Deadlines (UTC-5)

Segments + ring-1 edges + `topic_daily` on Aug-Oct by **22:30** (WS3 and WS4 switch to them then). Backfill to
12 months by **01:30**. Lake export by **02:00**.

## Report

Update `status/WS1.md` at 22:00, 00:00 and when done; then open the PR as a **draft** against `develop` with
the template, and mark it ready only after the local gate passes (CI minutes are scarce).

## If blocked

Write `BLOCKED: <reason>` at the top of `status/WS1.md` and stop.
