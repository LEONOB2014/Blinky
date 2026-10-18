# BRIEF: WS1c, source diversity per topic-week (the syndication guard)

Account: **Claude #2 (claude-work)** · Branch: `feat/ws1-topic-sources` · Worktree: `../radar-worktrees/feat-ws1-topic-sources`
Written by the orchestrator, 2026-10-18 01:25 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Measure, for every ranked topic and week, how many distinct outlets carry it and how concentrated it
is, so WS4 can keep wire-syndication bursts out of the top 10. Your WS9 diagnostic found 5 of the
2026-W42 top 10 at >= 90% single-pattern concentration (Euronext 145 of 149 articles share one
feed, measured).

## Inputs

- BigQuery `radar.article_segment` (ring-1 `segment = 'ai'`, `source`, the ring-1 org/theme arrays,
  `dt`), the ids of `radar.topic_daily`. The contract is in this branch:
  `contracts/topic_sources_weekly.schema.json` (committed by the orchestrator).
- `pipelines/ingest/run_bq.py` (dry run, ledger, guard) and `export_gold.py`, as in WS1.

## Outputs

1. `bq_sql/s13_topic_sources_weekly.sql` -> `radar.topic_sources_weekly`, exactly the contract.
   `top_theme_pattern_share`: compute it if cheap (for example the share of the topic-week's articles
   whose sorted top-5 co-mentioned entities equal the most common such set); otherwise null and say
   why. Dry run first; cap 10 GiB for this job unless the dry run says otherwise (then ask).
2. Export to `lake/gold/topic_sources_weekly.parquet` in `export_gold.py`, contract-checked; a dev cut
   in `fixtures/dev/` (same weeks and ranked universe as `topic_daily`'s dev cut, under 1 MB; you may
   touch `src/radar/fixtures.py` `ALLOWED_COLUMNS` and `scripts/export_dev_slice.py` for it).
3. In `status/WS1.md` (a WS1c section): the bill, rows, and for 2026-W42's current top 10 the
   n_sources, top_source_share and pattern share of each topic, plus the distribution over all ranked
   topic-weeks (median, p10, p90), so WS4 can pick thresholds from data.
4. Write `READY FOR WS4` at the top of `status/WS1.md` when the lake file exists.

## Files you may touch

`bq_sql/s13_topic_sources_weekly.sql`, `pipelines/ingest/**`, `fixtures/dev/`, `src/radar/fixtures.py`
(`ALLOWED_COLUMNS` only), `scripts/export_dev_slice.py`, `reports/bq_ledger.csv`, `status/WS1.md`.

## Out of scope

The gate itself (WS4 adds the penalty), contracts (already written), the API.

## Acceptance

`make check && make test` pass; `RADAR_PROFILE=full uv run pytest -m data` includes a check that the
lake file validates and that `n_sources <= n_articles`.

## Paid or outward actions needing approval

Approved: the S13 BigQuery job up to 10 GiB billed and its check queries. `git push`: the orchestrator.

## Machine limits

Memory is short until ~03:00: BigQuery does the work; the export reads pages, never the whole table
into memory twice.

## Deadline (UTC-5)

Lake file by **02:30**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS1.md`, then stop.
