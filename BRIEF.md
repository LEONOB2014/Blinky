# BRIEF: WS4, the scores, the decision and the backtest (Signal analyst + Audience strategist)

Account: **Claude #3** · Branch: `feat/ws4-scores` · Worktree: `../radar-worktrees/feat-ws4-scores`
Written by the orchestrator, 2026-10-17 20:45 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Compute, for every ranked topic and week, the six scores, the window chip and the decision
(`publicar_ahora` / `preparar` / `esperar` / `no_es_tema_caliente`), and the backtest that says how much
to trust them. Code decides; no LLM in this lane.

## Plan reference

`docs/designs/radar-build-plan.md`: "What is ranked", "Evaluation" (Backtest, Window chip, Editor test,
Hook); MASTER_PLAN §10 (sentiment), §12 (scoring), §13 (evaluation).

## Inputs (all real; `radar.paths.gold(name)` resolves dev or full)

- Now, dev slice (`fixtures/dev/`): `daily_topic`, `daily_topic_rolling`, `daily_totals`, `edges_weekly`.
  Build and test every function here, at **subtopic** level (12 subtopics + `ai_all`).
- From **22:30**: WS1's `topic_daily` (entity/theme topics) and WS3's `node_metrics_weekly`,
  `topic_context_1hop` in the lake. Switch the ranked unit to topics then.
- From **22:00**: WS6's `topic_wikidata` and `wiki_pageviews_daily` (the backtest label).

## Outputs

1. `models/scores.py`: emergence percentile (z_7d, z_dow, growth_7d_log, accel_7d, plus new-neighbour
   rate when available), stage (`semilla`/`emergente`/`en_pico`/`saturado`/`en_declive`) and saturation,
   emotional charge percentile (extremity, polarity, controversy, tails, tone shift: MASTER_PLAN §10.4),
   audience fit v1 **rule-based** (LatAm share, education/business subtopics; Jev is optional and
   approval-gated), priority = Emergence_pct x (1 - Saturation) x Fit x (1 + 0.25 x EmotionalCharge_pct).
2. `models/window.py`: the window chip exactly as the design (primary subtopic, pooled median lag
   English onset -> es/pt onset, onset = first day z_7d > 2, four states).
3. `models/decision.py`: the decision from the scores with thresholds in one documented table.
4. `models/build_scores.py`: writes `topic_scores_weekly` (contract `topic_scores_weekly.schema.json`) to
   the lake for the full profile; validates every row with `radar.contracts.validate_records`.
5. `models/backtest.py` + `reports/backtest.md`: exactly the design's protocol (mapped topics only, top
   quartile of 2-week es+pt pageview growth, precision@10 with base rate and baselines raw-count growth and
   persistence, lead time, evaluable-week counts, bootstrap intervals over weeks). If the radar does not
   beat the baselines, the report says so.
6. `models/editor_sheet.py`: the blind editor-test sheet (design protocol) for 2026-W42, by 08:30.

## Files you may touch

`models/**` (not `models/tgnn/`), `reports/backtest.md`, `reports/editor_test.md`, `status/WS4.md`, the
`models` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

Contracts, the GDELT SQL, graphs, the API and the agents. No synthetic data: tests use the dev slice;
where a state has no real case in the dev slice, lower the threshold inside that test and say so.

## Acceptance

- `make check && make test` pass on the dev slice.
- Unit tests: each score on known dev-slice rows; the window chip's four states; the decision table;
  `build_scores` output validates against the contract.
- `RADAR_PROFILE=full` run writes `topic_scores_weekly` for every week of the lake; `reports/backtest.md`
  lists weeks, topics, precision@10 (with base rate and both baselines), lead time, all marked measured.

## Paid or outward actions needing approval

Jev (OpenRouter) calls, `git push`, opening the PR.

## Deadlines (UTC-5)

Scores + window + decision on the dev slice by **23:30**; on topics in the lake by **03:00**; backtest
report by **05:00**; editor sheet by **08:30**.

## Report

`status/WS4.md` at each sync; PR as a **draft** against `develop`, ready only after the local gate passes.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS4.md`, then stop.

## Addendum (orchestrator, 21:10 UTC-5): measured on the dev slice

- `z_7d` reaches 46 for `regulation_policy` on 2026-10-17: the 28-day baseline's SD is tiny for low-volume
  subtopics. Use a robust z (median/MAD, or a floor on the SD) or a percentile, and test it on that row.
- `energy_climate` has no rows yet (WS1 adds its rule in S4); do not special-case it.
- The agent runtime (`agents/`, merged) reads `topic_scores_weekly` through `get_top10` and
  `get_topic_scores`: once your table validates, decision cards appear in the Media Master's answers.

## Addendum 2 (orchestrator, 22:30 UTC-5): unblocked

- **Ranked unit** (PR #8, `contracts/taxonomy.yaml` `ranked_universe`): every `org:` topic of
  `topic_daily` except `org_deny`, plus `thm:TECH_*`, with at least `min_articles_week` (20) ring-1
  articles in the week. Measured: orgs alone median 382 a week over 50 weeks. Read the lists from
  the taxonomy; never hard-code them.
- **Primary subtopic:** WS1 builds `topic_subtopic_weekly` (contract in PR #8; lake by 00:00, dev cut
  by 00:30). Primary subtopic of a topic in week t = the non-null subtopic with the most articles over
  weeks t-3..t (ties: the subtopic's id order in the taxonomy); none -> the window chip says
  `sin_estimacion` and fit uses the topic's own series only.
- Build the `topic` branch now against `lake/gold/topic_daily.parquet` (it is there: 2,012,823 rows,
  measured); plug the mapping in when it lands. Keep the 12-subtopic table as it is (the agents use it
  for the overview).
- **Evidence ids** stay empty; say so in the report. No contract change for them tonight.
- Backtest: as soon as WS6 lands `topic_wikidata` + `wiki_pageviews_daily` (Grok is still resolving;
  ETA in `status/WS6.md`). Run it on mapped topics only and report the coverage (mapped / ranked).
- New deadlines: topic scores in the lake by **01:30**; backtest by **05:00**; editor sheet by 08:30.
