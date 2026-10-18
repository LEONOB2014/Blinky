# WS4 status

Owner: claude-cacho · Directories: `models/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:05 UTC-5 · branch `feat/ws4-scores` (local commits, not pushed) · no PR yet

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

## In progress

- Waiting for the full-profile inputs: WS1 `topic_daily` (22:30), WS3 `node_metrics_weekly`, WS6
  `topic_wikidata` and `wiki_pageviews_daily` (22:00). `lake/gold/` is empty at 21:05.

## Blocked on

- Not blocked yet. **Needed at 22:30:** the switch to topic units needs each topic's subtopics
  (the design's primary subtopic = the subtopic with most of the topic's articles over 28 days).
  No contract carries a topic -> subtopic mapping (`topic_daily` has no subtopic column), and
  I cannot add one (contracts are out of scope). Until a contract provides it, `build_scores` and
  the backtest run on subtopics only, where a top 10 of 11 says nothing (design, "What is ranked").
- Evidence ids: `topic_scores_weekly.evidence_ids` is empty for now. No contract gives gkg_id per
  topic in the lake; the dev `gkg_ai_sample` is a sample.

## Numbers (each marked measured or estimate)

- None reported: everything so far ran on the dev profile, whose numbers are never reported.
- All score weights and thresholds are hand-set (estimate), to be tuned on the backtest.
