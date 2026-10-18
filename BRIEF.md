# BRIEF: WS3, graph metrics and the 1-hop context ring (Cartographer)

Account: **Claude #4** · Branch: `feat/ws3-graph-metrics` · Worktree: `../radar-worktrees/feat-ws3-graph-metrics`
Written by the orchestrator, 2026-10-17 20:45 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Compute the weekly graph metrics that feed Emergence and the 1-hop context ring that explains each
topic. **No visualization in this brief**: the graph views come last, in a later brief, after the gate.

## Plan reference

`docs/designs/radar-build-plan.md`: "1-hop context ring (P6)", "Gate for G"; MASTER_PLAN §11.

## Inputs

- Now: `fixtures/dev/edges_weekly.parquet` (8 weeks, top 1,500 edges per week, no persons; built today
  from every row, so it is noisier than the final ring-1 edges).
- From **22:30**: WS1's ring-1 `edges_weekly` in the lake (`RADAR_PROFILE=full`).

## Outputs

1. `graph/metrics.py`: per week, weighted degree, degree growth, new-neighbour rate vs the prior 4 weeks,
   PageRank and its rank delta, k-core, Leiden communities (igraph + leidenalg) matched across weeks by
   Jaccard >= 0.3 with birth/merge/split/continue events, hub flag (top 1% weighted degree). Writes
   `node_metrics_weekly` (contract `node_metrics_weekly.schema.json`).
2. `graph/context.py`: `topic_context_1hop` per contract: n >= 3, NPMI > 0.1, hubs dropped, top 20 by NPMI,
   each neighbour tagged with its segment/domain when WS1's tables provide it (null until then).
3. `graph/build.py`: runs both for the active profile and validates every row with
   `radar.contracts.validate_records`; writes to `lake/gold/` for full.
4. `models/tgnn/baselines.py` + `reports/tgnn.md`: EdgeBank and persistence on new-edge prediction
   (week t -> t+1), MRR with the counts, as the baseline table (P2). Only after 1-3 pass.

## Files you may touch

`graph/**`, `models/tgnn/**`, `reports/tgnn.md`, `status/WS3.md`, `status/WS7.md`, the `graph` extra in
`pyproject.toml`/`uv.lock`.

## Out of scope

Graphistry, sigma.js, any rendering or upload (later brief, after the gate); contracts; SQL.

## Acceptance

- `make check && make test` pass on the dev slice.
- Unit tests on dev-slice weeks: hub exclusion, NPMI and rank limits of the 1-hop ring, community
  matching across two real consecutive weeks, contract validation of both outputs.
- Full-profile run writes both tables for every week; `status/WS3.md` reports nodes, edges and
  communities per week (measured).

## Paid or outward actions needing approval

`git push`, opening the PR. No GPU or Modal.

## Deadlines (UTC-5)

Metrics + 1-hop on the dev slice by **23:00**; on the lake by **01:00** (WS4 reads them); baselines by **06:00**.

## Report

`status/WS3.md` at each sync; PR as a **draft** against `develop`, ready only after the local gate passes.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS3.md`, then stop.

## Addendum (orchestrator, 22:30 UTC-5): persons out of the ring, one community check

1. **Drop `per:` neighbours from `topic_context_1hop`** (and from the NPMI top-20 selection, so each
   topic still gets up to 20 non-person neighbours). Persons never reach the lake's ring, the API or
   the UI. Keep `per:` nodes in `node_metrics_weekly` only as graph structure (they are not served).
   Re-run the full profile and report the new row counts.
2. **Ranked topics** are now `ranked_universe` in `contracts/taxonomy.yaml` (PR #8): every org except
   `org_deny`, plus `thm:TECH_*`. The ring can keep covering every org/thm node (the API filters).
3. **Community continuity:** try once matching on nodes present in both weeks, restricted to the top
   10% by weighted degree, Jaccard >= 0.3. Report the birth/continue split. If continuity stays
   under 50% of community-weeks, leave `community_event` as computed and say the agents must not use
   it; do not iterate further tonight (graph views are last).
4. CI does not install extras; leave `ci.yml` as it is (Actions minutes).
5. Same gate; commit; update `status/WS3.md`. The push waits for the maintainer.

Deadline: **00:30**.
