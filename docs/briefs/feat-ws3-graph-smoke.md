# BRIEF: WS3c, the graph-view smoke test (de-risk G, do not build it yet)

Account: **Claude #4 (claude-cacho)** · Branch: `feat/ws3-graph-smoke` · Worktree: `../radar-worktrees/feat-ws3-graph-smoke`
Written by the orchestrator, 2026-10-17 23:20 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Prove, on a small real slice, that the demo's graph views can be produced in time: the data export for
the temporal view and the story view, and one working GPU-rendered temporal view, with no cloud service and no account. The full graph phase
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
2. **GPU temporal view, no cloud service** (`lake/views/temporal.html` + its JSON): the maintainer
   rejected the Graphistry cloud, and a self-hosted Graphistry server is a licensed product, so the live
   graph uses **cosmos.gl** (`@cosmos.gl/graph`, MIT, verified): force layout and drawing both run on the
   viewer's GPU through WebGL. Load the 13-week export, play the weeks in order (edges of week t shown,
   node size by that week's PageRank, ranked topics coloured by decision), with a week slider and
   play/pause. Load it from a CDN allowed by the page (jsDelivr or unpkg); serve with
   `python -m http.server`. Measure on this Mac: nodes/edges loaded, time to first frame, frames per
   second while playing (the browser's performance panel or `requestAnimationFrame` timing).
3. **Story view** (`lake/views/story.html`): the story JSON rendered with sigma.js (WebGL, MIT): the topic
   in the centre, its ring, edge width by co-mentions, the scores row as a side panel. A screenshot path
   in the status. Smoke tests only, not the final UI (WS5 owns `web/`).
4. `status/WS3.md` (WS3c section): sizes, timings (export, first frame, fps), what broke, the largest
   graph that stays smooth, and the hours G needs to move both views into `web/` (estimate).
5. Optional, only if outputs 1-4 are done: pre-compute a stable layout per week with `pygraphistry`'s
   local (CPU) tools or networkx, so the sweep does not re-layout from scratch each week. No server, no
   upload.

## Files you may touch

`graph/**`, `status/WS3.md`, the `graph` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

`web/`, `api/`, contracts, the final views, the video. No person nodes anywhere.

## Acceptance

- `make check && make test` pass; a unit test runs the exports on the dev slice and checks there are
  no `per:` nodes and that sizes respect the pruning.
- The status reports measured sizes and timings.

## Paid or outward actions needing approval

None: everything runs locally, nothing is uploaded. `git push` and the PR: the orchestrator.

## Deadline (UTC-5)

**01:30**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS3.md`, then stop (except the credentials case above).
