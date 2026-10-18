# BRIEF: the Spanish adaptation brief per top-10 topic (Editor agent)

Account: **Claude #2 (claude-work)** (reassigned 03:30: claude-cacho runs the backtest) · Branch: `feat/ws0-spanish-briefs` · Worktree: `../radar-worktrees/feat-ws0-spanish-briefs`
Written by the orchestrator, 2026-10-18 02:35 UTC-5. Read `AGENTS.md`, `agents/README.md`, then this file.

## Goal

The demo's step 3 ("why and adapt") shows, on each top-10 card, a short Spanish brief an editor at 30X
could act on today: what happened, why it matters to LatAm executives, the angle, an opening hook and
a format. Written ahead of time (no waiting in the demo), from tool data only, and checked by the Auditor.

## Inputs

- Contract `contracts/topic_briefs_weekly.schema.json` (merged, PR #28).
- The agents' tools (`agents/tools.py`): `get_top10`, `get_topic_scores`, `get_topic_series` (en vs es/pt),
  `get_context_1hop` (the ring's strongest neighbours), and the window chip, stage, decision and
  `framing_angle` of `topic_scores_weekly`. `lake/gold/topic_evidence_weekly.parquet` arrives from WS1
  (claude-work) around 04:00: when it exists, the brief may say "según N artículos de M medios" using its
  counts, never quoting titles.
- `agents/runtime.py`: the Auditor (`untraced_numbers`, the decision veto), `PLAIN` writing rules,
  `topic_name()`. Qwen3-30B on Nebius (the agents' model).

## Outputs

1. `agents/briefs.py` + `uv run python -m agents.briefs --weeks 2`: for the top 10 of the latest 2 scored
   weeks, gather the tool data in code, ask the Editor (Qwen3-30B) for the six text fields as JSON
   (Spanish, plain, no internal ids or field names, every number copied from the data you pass), then run
   the Auditor on the text: `numbers_cited` holds every number passed and used (with `kind` and `source`);
   `untraced_numbers` lists any number in the text not in it; `auditor_ok` false when any appears or a
   decision word contradicts the code's decision. Retry once with the Auditor's complaint when it fails;
   keep the second result even if it still fails (flagged). Write `lake/gold/topic_briefs_weekly.parquet`,
   validated against the contract.
2. Copy the latest records to `mocks/topic_briefs_weekly.json` (2-3 records) and set the contract's
   `x-mock` to `first-agent-run` (allowed in this brief).
3. A tool `get_topic_brief(topic_id, week)` in `agents/tools.py`, and the Editor specialist uses it first
   when it exists (so the chat's "¿qué contenido preparo?" answers from the brief).
4. Offline tests (scripted model): the Auditor flags an invented number; the JSON parsing handles a bad
   reply; the contract validates.
5. Report in `status/WS0-agents.md` (a briefs section): briefs written, auditor_ok count, retries, tokens,
   time, and 2 briefs pasted as examples (they hold no titles, URLs or person names).

## Rules

Spanish for LatAm executives; no hype; no claims beyond the data; no person names; never say a topic will
"go viral"; the decision line is the code's. Numbers rounded as an executive reads them, but traceable.

## Files you may touch

`agents/**`, `mocks/topic_briefs_weekly.json`, `contracts/topic_briefs_weekly.schema.json` (`x-mock`
only), `status/WS0-agents.md`.

## Acceptance

`make check && make test` pass; the lake file validates; at least 18 of the 20 briefs `auditor_ok`
(measured; report the real count either way).

## Paid or outward actions needing approval

Approved: about 20-40 Nebius calls for the briefs. `git push`: the orchestrator.

## Deadline (UTC-5)

Briefs in the lake by **04:30**; regenerate once at **06:00** after the final scores if they changed.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS0-agents.md`, then stop.
