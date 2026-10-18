# BRIEF: WS5b, the API and UI on the full lake

Account: **Claude #4 (claude-cacho), after its WS3 addendum** · Branch: `feat/ws5-full-lake` · Worktree: `../radar-worktrees/feat-ws5-full-lake`
Written by the orchestrator, 2026-10-17 22:55 UTC-5. Read `AGENTS.md` (or `GEMINI.md`), then this file.
WS5 (PR #9, by Gemini) is merged; this branch starts from `develop` with it. Read `api/` and `web/` first.

## Goal

Make the merged API and UI work fast and safely on the **full lake** (`RADAR_PROFILE=full`, real data,
51 weeks), so the demo runs on real numbers. No new contracts, no visual polish (Lovable later).

## Inputs (all real, in `lake/gold/`, sizes measured at 22:50)

- `topic_daily` (29 MB, 2,012,823 rows), `topic_context_1hop` (33 MB, 4,849,854 rows),
  `edges_weekly` (432 MB, 37.8M rows), `node_metrics_weekly` (10 MB), `daily_topic`,
  `daily_topic_rolling`, `daily_totals`.
- `topic_scores_weekly` (1,200 rows today: 12 subtopics x 100 weeks). From ~01:30 WS4 adds rows whose
  `topic_id` is `org:<name>` or `thm:TECH_*` (same contract). Handle both.
- `contracts/taxonomy.yaml` `ranked_universe` (new in PR #8): the org deny-list and theme prefixes.
- WS3 is removing `per:` neighbours from `topic_context_1hop` tonight; until then the lake has them.

## Outputs

1. **Full-profile performance.** Every endpoint answers on the full lake without loading whole tables
   into memory (DuckDB over Parquet with filters pushed down; never read `edges_weekly` in a request
   when `topic_context_1hop` exists). Measure p50/p95 latency of `/api/radar`,
   `/api/topic/{id}/timeline` and `/api/topic/{id}/context` over 20 calls each on real topic ids
   (for example `org:nvidia`, `org:openai`, `thm:TECH_AUTOMATION`); target p95 < 300 ms (estimate).
2. **Privacy guard (defence in depth).** `/context` never returns a `per:` neighbour, whatever the
   lake holds; `/api/radar` never returns a deny-listed org (read the list from the taxonomy).
   A test for each, on rows where the guard actually binds.
3. **Radar cards on real rows.** `/api/radar?week=` with an ISO-week selector in the UI (default: the
   latest scored week); subtopic rows labelled with `label_es` from the taxonomy; `org:`/`thm:` rows
   shown by name. Clicking a card loads its timeline and 1-hop ring.
4. **Chat on the full profile.** Run 3 questions through the UI against the full lake (for example
   "¿Qué tema de IA sube esta semana y por qué?", "¿Qué está pasando con Nvidia?", "¿Cuánto ha costado
   en BigQuery?"), report each turn's latency and Auditor flags from the trace. Traces stay in the lake.
5. A screenshot on the full profile, path in `status/WS5.md` (not committed).

## Files you may touch

`api/**`, `web/**`, `status/WS5.md`, WS5 targets in `Makefile`.

## Out of scope

Contracts, agents (`agents/**`: report agent problems in the status file, the orchestrator fixes
them), scores, graphs and graph views, deployment, visual design.

## Acceptance

- `make check && make test` pass; `uv run --extra api pytest api` passes; `cd web && bun run build` passes.
- Latency table and the 3 chat turns in `status/WS5.md`, each number marked measured.

## Paid or outward actions needing approval

`git push`, opening the PR, deployment. The 3 chat turns call Nebius (approved, about 3-6 LLM calls each).

## Deadline (UTC-5)

**01:00**.

## Report

`status/WS5.md`; commit locally and stop. The orchestrator pushes and opens the PR.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS5.md`, then stop.
