# WS3: graph

Weekly co-occurrence snapshots (NPMI > 0.1), node metrics, the GPU tier-1 layout for Graphistry, and the story-view and ego-graph JSON for the web.

Plan: [MASTER_PLAN §15.1](../docs/plan/MASTER_PLAN.pdf). Status: [status/WS3.md](../status/WS3.md).

## Graph-view exports (WS3c smoke test, contract-free)

`uv run python -m graph.export_views` (`RADAR_PROFILE=full`) writes to `lake/views/` (git-ignored)
and copies `graph/views/temporal.html` and `story.html` next to the JSON. Serve with
`cd lake/views && python -m http.server 8765`. Persons (`per:`) are dropped from every node and edge.
`bun graph/views/measure.mjs <url> <png> [seconds] [--headed]` opens a page in local Chrome and prints
the page's `window.__metrics` (load, first frame, fps) plus a screenshot.

### `temporal.json` (cosmos.gl, `temporal.html`)

| Field | Meaning |
|---|---|
| `_meta.profile` | `dev` or `full` |
| `_meta.weeks`, `_meta.iso_weeks` | the last 13 weeks present in `edges_weekly` (Monday dates / ISO weeks); a missing week stays missing |
| `_meta.params` | `span_weeks`, `max_nodes` (default 2000), `min_n` (default 5), `min_npmi_exclusive` (0.1) |
| `_meta.n_nodes`, `n_edges`, `edges_per_week` | sizes after pruning |
| `nodes[i].id`, `label`, `etype` | `'<etype>:<entity>'`, the name, `org`/`thm`/`loc` |
| `nodes[i].deg_span` | weighted degree (sum of `n`) over the span on the kept edges; nodes are the top `max_nodes` by it |
| `nodes[i].pagerank[w]` | that week's PageRank from `node_metrics_weekly` (null when absent) |
| `nodes[i].rank[w]`, `decision[w]` | from `topic_scores_weekly` when the node is ranked that week, else null |
| `edges.source[k]`, `target[k]` | node indices (columnar arrays) |
| `edges.week[k]`, `n[k]`, `npmi[k]` | week index, co-mentions, NPMI (n >= `min_n`, NPMI > 0.1) |

### `story.json` (sigma.js 3, `story.html`)

A graphology serialized graph: `attributes` (`topic_id`, `week`, `scores` = the full
`topic_scores_weekly` row or null), `nodes[]` (`key`, `attributes`: `label`, `x`, `y` on a radial
layout, `size`, `role` = `topic`/`ring`, `rank`, `n`, `npmi`, `etype`) and `edges[]` (`key`,
`source`, `target`, `attributes`: `n`, `npmi`, `size`, `kind` = `ring` for topic-neighbour edges or
`among` for edges between neighbours that week). `_meta` holds `profile`, `topic_id`, `week`,
`n_ring`, `n_among_edges`. The default topic is the #1 of the latest scored week, read from
`topic_scores_weekly` (`--topic`/`--week` override it).
