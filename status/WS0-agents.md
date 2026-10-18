# WS0-agents status (answer quality, measured with LangSmith)

Owner: Claude #4 (claude-cacho) · Branch: `feat/ws0-agents-quality` · Directories: `agents/`

## Last update

2026-10-18 01:15 UTC-5 · committed locally; the orchestrator pushes.

## Done

- `run_evals.py --repetitions N --change "..."`: LangSmith `num_repetitions`, git sha and the scores
  file's timestamp in the metadata, per-question scores and judge reasons in `lake/evals/`.
- 6 experiments of 25 questions x 3 repetitions (the brief's maximum), one change each, table and
  diagnosis in `agents/README.md`. Kept: plain decision line written by code, out-of-scope route,
  routing gaps closed. Reverted (no win, measured): human-formatted tool fields, shorter notes.
- Final vs. 3-repetition baseline (measured, n = 75 runs each): usefulness 0.443 [0.40-0.48] -> 0.520
  [0.48-0.57]; grounding 0.947 -> 1.000; decision faithfulness 1.00 -> 1.00; routing 0.960 -> 1.000;
  tokens per turn 6,395 -> 5,814.

## Blocked on

- None.

## Notes for the orchestrator

- Next change to try: show the decision line only for "what to publish / what is rising" questions
  (q12, q15, q16 are penalised for an unrequested decision).
- The judge does not see tool data or today's date: it calls real numbers "no verificables" and 2026
  dates future. Consider a judge v2 that gets the tool results, then re-score the baseline with it.
- One of 75 runs in out-of-scope-r3 failed on a DNS error (empty answer, counted as is).
