# WS4 status

Owner: claude-cacho · Directories: `models/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 22:50 UTC-5 · branch `feat/ws4-scores` · draft PR #6 (into `develop`)

## Done

- Unblocked by Addendum 2. Merged `origin/develop` (PR #8: `ranked_universe`,
  `topic_subtopic_weekly`).
- **Topic scores in the lake** (`RADAR_PROFILE=full uv run python -m models.build_scores`):
  - `lake/gold/topic_scores_weekly.parquet`: 17,285 rows over 46 weeks (2025-W49..2026-W42) and
    4,947 topics; every row is valid against the contract.
  - Ranked universe from the taxonomy: org topics minus `org_deny`, plus `thm:TECH_*`, with at
    least 20 ring-1 articles in the ISO week. Median 376 topics a week; 436 in 2026-W42.
  - Primary subtopic from `topic_subtopic_weekly` over weeks t-3..t, ties broken by taxonomy order.
    It is set for 415 of 436 topics in W42. A topic without one gets `primary_subtopic` = ""
    (empty), a `sin_estimacion` chip, and a fit from its own series only.
  - Window chip in W42: 216 of 436 topics have an estimate (138 `dias_restantes`, 68
    `en_cualquier_momento`, 10 `ya_en_espanol`).
  - The 12-subtopic table is kept, same contract, in `lake/gold/subtopic_scores_weekly.parquet`:
    552 rows, 46 weeks.
  - Run time 16 s, 2.4 GB peak.
- **Fix:** the rolling calendar now starts at the input's own first day. `daily_topic` and
  `topic_daily` start 2025-11-01, a year after `daily_totals`. The 21:28 subtopic build had
  counted that year as zero articles. It is replaced.
- **Editor sheet** for 2026-W42 in `reports/editor_test.md`: 9 radar items, 9 raw-count-growth
  items, 1 on both lists. The key is in `lake/editor_test/2026-W42_key.json`; tally with
  `--tally`.
- The backtest runs on topics through the same scoring step. Its report states the coverage
  (mapped / ranked) and that the evidence ids are empty. A smoke test at topic scale with the
  secondary label ran in 10 s; its numbers are not reported.
- Tests: `uv run pytest models -m "not data"`: 79 passed. Lake tests (`-m data`): the topic build
  validates, and the primary subtopic is recounted by hand for `org:nvidia`, 2026-W41.

## In progress

- **Backtest:** waiting for WS6's `wiki_pageviews_daily`. WS6 is fetching pageviews at 22:36 after
  an HTTP 429. Coverage so far: 278 of 4,947 ranked topics have an es or pt article. WS6 is still
  resolving the 8,385 `topic_daily` extras.

## Blocked on

- Nothing.

## For the orchestrator (findings, W42 top 10 and editor sheet)

- **Outlets and retailers still rank.** `org:big news network` (and the artefact
  `org:big new network`), plus `org:king soopers`, `org:ralphs` and `org:fred meyer` (a Kroger
  news cluster), are in the W42 lists. Adding them to `org_deny` is a taxonomy change (yours or
  WS2's).
- **New topics rank high.** A topic that appears from near zero gets a huge `growth_7d_log`:
  `org:marsh mclennan`, rank 1 in W42, shows +25,815% share and has no z history. The Emergence
  weights are hand-set placeholders (estimate). I will not retune them before the backtest
  measures them.
- `evidence_ids` stays empty (no contract tonight), and the backtest report says so.

## Numbers (each marked measured or estimate)

- `topic_scores_weekly`: 17,285 rows, 46 weeks, 4,947 topics, 0 contract violations (measured).
- Ranked topics a week: median 376; 436 in 2026-W42 (measured).
- W42: primary subtopic for 415/436 and a window estimate for 216/436 (measured).
- Wikipedia es/pt coverage so far: 278/4,947 ranked topics (measured, resolution in progress).
- Editor sheet W42: 19 items = 9 radar + 9 baseline + 1 overlap (measured).
- All score weights and thresholds are hand-set (estimate).
