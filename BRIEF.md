# BRIEF: WS3c, the graph-view smoke test (de-risk G, do not build it yet)

Account: **Claude #4 (claude-cacho)** · Branch: `feat/ws3-graph-smoke` · Worktree: `../radar-worktrees/feat-ws3-graph-smoke`
Written by the orchestrator, 2026-10-17 23:20 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Prove, on a small real slice, that the demo's graph views can be produced in time: the data export for
the temporal view and the story view, and one working GPU-rendered temporal view. The full graph phase
(G) still starts only after the gate; this lane measures how long it will take and finds the blockers now.

## Plan reference

`docs/designs/radar-build-plan.md`: "G graph", the gate thresholds (Graphistry path estimated at about
3 hours, untested: review findings R2-9 and R3-1 ask for this smoke test), demo step 5 ("the live GPU
temporal graph sweep over 90 days, then the story view of the #1 topic").

## Inputs (real, in `lake/gold/`)

`edges_weekly` (37.8M rows, ring 1 only), `node_metrics_weekly` (473,275 rows: degree, PageRank,
k-core, community, `is_hub`), `topic_context_1hop` (persons dropped), `topic_scores_weekly` (decisions;
WS4 is changing the top 10 tonight, so read it, never hard-code topics). Persons never leave the lake.

## Outputs

1. `graph/export_views.py`:
   - **temporal**: nodes and edges for the last 13 weeks (about 90 days), pruned for a laptop (for
     example the top 2,000 nodes by weighted degree across the span and edges with n >= 5 and NPMI > 0.1;
     measure and report the sizes), each edge with its week, each node with its weekly PageRank and its
     ranked-topic flag and decision when it has one. No `per:` nodes.
   - **story**: for one topic and week, the topic, its 1-hop ring (up to 20), the edges among those
     neighbours, and the scores row. JSON shaped for sigma.js (`nodes`, `edges`, attributes).
   Written to `lake/views/` (git-ignored). Contract-free for now; document the fields in `graph/README.md`.
2. **Graphistry smoke test** (`graph/graphistry_smoke.py`): upload the temporal export of the last 4
   weeks to Graphistry Hub with the time column set, and record the upload time, node/edge counts and
   whether the timebar animates. Credentials: `GRAPHISTRY_USERNAME` / `GRAPHISTRY_PASSWORD` in `.env`
   (**empty today**: if they are still empty when you get here, write `BLOCKED: Graphistry credentials`
   for this output only and continue with output 3).
3. **Local fallback that needs no account:** one HTML page under `lake/views/` that renders the story
   JSON with sigma.js (WebGL, so the GPU draws it) from a CDN, opened with `python -m http.server`. A
   screenshot path in the status. This is a smoke test, not the final UI (WS5 owns `web/`).
4. `status/WS3.md` (WS3c section): sizes, timings (export, upload, first render), what broke, and a
   recommendation for G: Graphistry, sigma.js, or both, with the hours each needs (estimate).

## Files you may touch

`graph/**`, `status/WS3.md`, the `graph` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

`web/`, `api/`, contracts, the final views, the video. No person nodes anywhere.

## Acceptance

- `make check && make test` pass; a unit test runs the exports on the dev slice and checks there are
  no `per:` nodes and that sizes respect the pruning.
- The status reports measured sizes and timings.

## Paid or outward actions needing approval

The Graphistry upload sends public GDELT entity names (orgs and themes, no persons) to Graphistry Hub:
**approved for the 4-week smoke test only.** `git push` and the PR: the orchestrator.

## Deadline (UTC-5)

**01:30**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS3.md`, then stop (except the credentials case above).
