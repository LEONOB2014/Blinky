# BRIEF: make the Media Master's answers useful to an executive, measured with LangSmith

Account: **Claude #4 (claude-cacho)** · Branch: `feat/ws0-agents-quality` · Worktree: `../radar-worktrees/feat-ws0-agents-quality`
Written by the orchestrator, 2026-10-18 01:30 UTC-5. Read `AGENTS.md`, `agents/README.md`, then this file.

## Goal

Raise the usefulness of the agents' answers for a LatAm media executive (LangSmith judge score ~0.40
today) without losing grounding or decision faithfulness, and prove each change with an experiment
on the frozen question set. This is what 30X's executives will try first on Tuesday.

## Inputs

- `agents/` (runtime, tools, the Auditor), `agents/evals/questions.yaml` (25 frozen questions, v1:
  never edit it), `agents/evals/run_evals.py` (LangSmith experiments; code evaluators + Qwen3-235B
  judge).
- LangSmith project `radar-agents`, dataset `radar-agents-v1`; experiments so far (n = 25, one
  repetition, measured): baseline-qwen3-30b (grounding 0.88, usefulness 0.40, entity 0.50),
  entity-routing-v2 (grounding 0.76, usefulness 0.38, entity 1.00, 7.7 s, ~5,900 tokens a turn).
  Open the low-usefulness runs in LangSmith and read the judge's reasons first.
- The full lake (`RADAR_PROFILE=full`). WS4 is rebuilding `topic_scores_weekly` tonight; your
  experiments read whatever is in the lake when they run: note the scores file's timestamp in each
  experiment's metadata.

## Steps

1. **Baseline with repetitions:** rerun the current `develop` code with `num_repetitions=3` (add a
   `--repetitions` flag to `run_evals.py`) so differences can be told from noise. Report means and the
   spread across repetitions per evaluator.
2. **Diagnose** from the judge's reasons and the traces: too long, data dumps, KPI jargon, no clear
   recommendation, ignores the question, out-of-scope questions answered with numbers (LinkedIn likes,
   a person's opinion), English leaks.
3. **Change one thing per experiment**, each with its own `--prefix`. Candidates:
   - the Media Master's final format: one line with the decision (copied from code), then why in
     2-3 plain bullets, then one concrete content suggestion; no internal field names (`z_7d`,
     `emergence_pct`), numbers rounded the way an executive reads them;
   - an explicit out-of-scope route (code, not the LLM): questions about engagement predictions,
     people's opinions or anything no tool covers get a short honest answer naming what the radar can
     do instead, with no numbers;
   - specialists' notes shorter and in plain Spanish;
   - pass the tools' numbers already formatted for humans (for example "+258%" instead of 2.58) so the
     LLM copies instead of re-computing (helps grounding).
4. Keep what wins, drop what does not. Stop when usefulness improves beyond the repetition spread
   with grounding and decision faithfulness not worse, or at the deadline.

## Outputs

- Changes in `agents/runtime.py` (prompts, routing, the out-of-scope route), `agents/tools.py` only
  for human-formatted fields, `agents/evals/run_evals.py` (`--repetitions`), tests for any new code
  path (offline, scripted model).
- `agents/README.md`: the experiments table (name, change, each evaluator's mean and spread, tokens,
  latency), all measured.

## Files you may touch

`agents/**` (not `agents/evals/questions.yaml`), `status/WS0-agents.md` (new, your status).

## Out of scope

The Auditor's rules (never loosen them to raise grounding), decisions or scores (code computes them),
the API, the UI, contracts, the model choice for the answering agents (Qwen3-30B stays; a model
comparison can be one extra experiment at the end if time remains, reported, not switched).

## Acceptance

- `make check && make test` pass; new code paths have offline tests.
- The experiments table with repetitions; the final experiment's usefulness, grounding and decision
  faithfulness compared against the 3-repetition baseline.

## Paid or outward actions needing approval

Approved: LangSmith experiments and their Nebius calls (about 25 questions x 3 repetitions x ~6
calls per experiment; keep it to at most 6 experiments). `git push` and the PR: the orchestrator.

## Machine limits

This Mac is short of memory tonight (swap nearly full until a Google Drive copy ends ~03:00). Eval
runs are light (network-bound), but keep `--concurrency` at 4 or less and never run a full-lake build.

## Deadline (UTC-5)

Baseline with repetitions by **02:30**; best change committed with its table by **04:30**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS0-agents.md`, then stop.

## Addendum (orchestrator, 01:25 UTC-5): a fairer judge, then the decision line's scope

Reviewed and kept: the code-written decision line, the out-of-scope route (narrowed by the
orchestrator: it refused "¿Qué predice el radar?" and "¿Cuántos días tendrá la ventana?"; tests now
cover both directions), the routing fixes. Your two notes become the next steps:

1. **Judge v2:** give the judge the tool results the answer was built from (trimmed) and today's date,
   and ask it to score only usefulness to the executive given that data (not whether numbers are
   "verificables"). Keep v1 in the code; name the evaluator `usefulness_v2`. Re-score the 3-repetition
   baseline and your final experiment with v2 (LangSmith can re-run evaluators on an existing
   experiment) so both judges are reported side by side.
2. **Decision line only when asked:** show it for what-to-publish / what-is-rising / entity-decision
   questions, not for graph, audience-only or tone questions (q12, q15, q16). One experiment, 3
   repetitions, v2 judge; keep it only if usefulness improves beyond the spread without hurting
   grounding or decision faithfulness.
3. Update `agents/README.md`'s table and `status/WS0-agents.md`. At most 3 more experiments.

The merged agents reach the public site only after a Cloud Run redeploy: the orchestrator arranges it.

Deadline: **03:30**.
