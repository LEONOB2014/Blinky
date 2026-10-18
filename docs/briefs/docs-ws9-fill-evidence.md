# BRIEF: fill the submission's pending numbers from the measured reports

Account: **Grok (the WS6 session, now free)** · Branch: `docs/ws9-fill-evidence` · Worktree: `../radar-worktrees/docs-ws9-fill-evidence`
Written by the orchestrator, 2026-10-18 03:35 UTC-5. Read `AGENTS.md`, then this file.

## Goal

`docs/submission/demo_script.md`, `submission_text.md` and `stories.md` have `[PENDIENTE: ...]` slots.
Fill them only from measured reports, with denominators and intervals, in Spanish, honestly.

## Sources (read them; never retype a number you did not find there)

- `reports/backtest.md`: primary label (es+pt Wikipedia pageviews, exact matches, 43 weeks): published
  radar precision@10 29.2% (24.4..34.0, coverage 92.7%, worst 27.0 / best 34.3), raw-count growth 31.7%,
  persistence 18.1%, base rate 25.4%; the radar beats persistence under the worst case (+6.4, 0.7..12.0)
  but not raw-count growth; the syndication guard costs precision on this label. Secondary label (es+pt
  GDELT growth): radar 13.3% (9.5..17.2) vs base 6.7%, persistence 12.8%, raw growth 0.2%; lead time
  median 3.0 weeks (2.0..4.0). Check every number against the file.
- The hook rule (`docs/designs/radar-build-plan.md`, "Hook (P4)"): the primary result may NOT headline
  (the advantage over raw-count growth fails under the worst case), so the hook is the fallback: "Qué tema
  de IA está subiendo esta semana, por qué y desde qué ángulo contarlo, solo con fuentes públicas".
- `reports/label_quality.md`: filter precision/recall against the **teacher panel** (the maintainer's
  300 human labels are pending; say "referencia: panel de modelos; verificación humana pendiente").
- `reports/bq_ledger.csv` and `reports/jev_ledger.csv` totals; `agents/README.md` eval table.

## Rules

Our own measured numbers only, each with its denominator; say plainly where the radar does not beat a
baseline; never compare with other teams or name outside material; no headlines, URLs or person names.

## Output

The three files updated; every `[PENDIENTE]` resolved or replaced by a stated reason. Commit on this
branch; the orchestrator pushes. Docs only.

## Deadline

**04:30**.
