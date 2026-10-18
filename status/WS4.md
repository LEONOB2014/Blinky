# WS4 status

BLOCKED: switching to topic units needs a topic -> subtopic mapping that no contract provides.
`topic_daily` (contract, and WS1's brief) has no subtopic column, and no other table carries one.
Every remaining deliverable depends on topic units: the 150-400 ranked topics, a backtest that
means something (on 12 subtopics a top 10 is the base rate) and the W42 editor sheet. Proposed
fix, for the lead to decide: WS1 adds `topic_subtopic_daily` (`topic_id`, `subtopic`, `dt`,
`lang_bucket`, `n_articles`: ring-1 articles of the topic that carry the subtopic), or a
`subtopic` column in `topic_daily`. With it, the primary subtopic and the pooled window lags
follow the design, and `models/build_scores.py` needs only its `topic` branch.

Owner: claude-cacho · Directories: `models/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:30 UTC-5 · branch `feat/ws4-scores` (local commits, not pushed: the push and draft PR wait for the maintainer) · no PR yet

## Done

- `models/features.py`: the S8 rolling view ported to Python at any grain (all languages, `eng`,
  es+pt, WS1 topics). A test checks it against the real view on every comparable dev row.
- Robust z (addendum): `z_7d_r` / `z_dow_r` floor the SD at 10% of the baseline mean (estimate);
  the scores and the window chip read them. Note for the orchestrator: the addendum's row
  (regulation_policy, spa, non-LatAm; the peak is on 2026-09-17, not 10-17) is a real burst, with
  the 7-day share several times its baseline, not a tiny SD; the floor binds on the warm-up and
  low-volume rows instead.
- `models/scores.py`: Emergence, Stage and Saturation, Audience fit v1 (rules), Emotional charge
  (§10.4 without the two GCAM terms), framing angle (§10.5), Priority (§12). Thresholds and weights
  sit in one table at the top of the file, all hand-set (estimate).
- `models/window.py`: the window chip as designed. The tests cover all four states on real dev
  topics. `en_cualquier_momento` lowers the 3-onset threshold to 1. `dias_restantes` has no real
  case in the slice even with the threshold lowered (every complete English -> es/pt pair has a
  0-1 day lag except llms_models, 13 days), so its test lowers the threshold and pools that one
  real lag. Both tests say so.
- `models/decision.py`: one documented five-row table; a test covers every row.
- `models/build_scores.py`: builds `topic_scores_weekly`, validates every row against the contract
  and writes it to the lake on the full profile. The first 5 weeks of the span are warm-up and are
  not scored.
- `models/backtest.py`: the design's protocol (mapped topics only, top-quartile 2-week es+pt
  pageview growth, precision@10 with base rate, raw-count-growth and persistence baselines,
  paired bootstrap over weeks, lead time, evaluable-week counts, a verdict). It writes
  `reports/backtest.md` on the full profile only. The tests run the mechanics on the dev slice
  with the secondary label (es+pt GDELT growth).
- `models/editor_sheet.py`: the blind sheet for 2026-W42 (overlap shown once, seeded order, key in
  the git-ignored lake) and a `--tally`.
- Gate: `ruff check`/`ruff format` clean on `models/`; `uv run pytest models` passes (70 tests).

- Full profile, subtopics: `RADAR_PROFILE=full uv run python -m models.build_scores` wrote
  `lake/gold/topic_scores_weekly.parquet`. 1,200 rows, every one valid against the contract: 100
  weeks (2024-W47..2026-W42, after the 5 warm-up weeks) x 12 subtopics. The lake has
  `daily_totals`, `daily_topic` and `daily_topic_rolling` for 2024-10-17..2026-10-18. The
  `domain:*` and `it_all` rows of `daily_topic` are excluded from the ranking (segment != ai).
  The agent runtime can read this table now; its top 10 is subtopics.

## In progress

- Stopped (BLOCKED above). Still missing in the lake at 21:30: WS1 `topic_daily`, WS3
  `node_metrics_weekly`, WS6 `topic_wikidata` and `wiki_pageviews_daily`.
- Not run: `models.backtest` (needs pageviews, and on subtopics its top 10 would equal the base
  rate) and `models.editor_sheet` (on 12 subtopics the two top 10s overlap almost entirely).

## Blocked on

- The topic -> subtopic mapping (BLOCKED, top of this file).
- Evidence ids: `topic_scores_weekly.evidence_ids` is empty for now. No contract gives gkg_id per
  topic in the lake; the dev `gkg_ai_sample` is a sample.

## Numbers (each marked measured or estimate)

- Full profile: 1,200 rows of `topic_scores_weekly`, 100 weeks x 12 subtopics, 0 contract
  violations (measured). No backtest numbers yet.
- All score weights and thresholds are hand-set (estimate), to be tuned on the backtest.
