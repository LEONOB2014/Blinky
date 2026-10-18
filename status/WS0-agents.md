# WS0-agents status (answer quality, measured with LangSmith)

Owner: Claude #4 (claude-cacho) · Branch: `feat/ws0-agents-quality` · Directories: `agents/`

## Last update

2026-10-18 01:45 UTC-5 · addendum 2 step 1 done · committed locally; the orchestrator pushes.

## Done

- `run_evals.py --repetitions N --change "..."`: LangSmith `num_repetitions`, git sha and the scores
  file's timestamp in the metadata, per-question scores and judge reasons in `lake/evals/`.
- 6 experiments of 25 questions x 3 repetitions (the brief's maximum), one change each, table and
  diagnosis in `agents/README.md`. Kept: plain decision line written by code, out-of-scope route,
  routing gaps closed. Reverted (no win, measured): human-formatted tool fields, shorter notes.
- Final vs. 3-repetition baseline (measured, n = 75 runs each): usefulness 0.443 [0.40-0.48] -> 0.520
  [0.48-0.57]; grounding 0.947 -> 1.000; decision faithfulness 1.00 -> 1.00; routing 0.960 -> 1.000;
  tokens per turn 6,395 -> 5,814.

## Addendum 01:25 (done)

- Judge v2 (`usefulness_v2`, tool data + today's date; v1 kept) and `--rescore`. Baseline and the first
  round's final re-scored with it (measured, n = 75 each): baseline 0.383 [0.36-0.41], route-gaps
  0.567 [0.50-0.60].
- 3 experiments (the addendum's maximum): decision line scoped to decision questions (no win,
  reverted), whole-word entity matching (kept: 7 of 25 questions were answered about a topic nobody
  named; v2 0.567 [0.55-0.59]), decision line for decision questions and named topics (no win,
  reverted).
- Final vs. baseline: usefulness_v2 0.383 -> 0.567 and v1 0.443 -> 0.497; grounding 0.947 -> 1.000;
  routing 0.960 -> 1.000; decision faithfulness 1.00 -> 0.987 (one q22 run; Auditor gap below).

## Addendum 2, step 1 (done)

- The Auditor keeps a decision phrase only when the turn emits a card with that decision;
  `entity_resolved` counts false positives over all 25 questions.
- auditor-cards-r3 (measured, n = 75): decision faithfulness 1.000 (was 0.987), entities 1.00 over 75
  runs, grounding 1.000, routing 1.000, usefulness_v2 0.550 [0.50-0.59] (was 0.567 [0.55-0.59]:
  within the spread), v1 0.500.

## Blocked on

- None.

## Notes for the orchestrator


- One of 75 runs in out-of-scope-r3 failed on a DNS error (empty answer, counted as is).
