# WS3: graph

Weekly co-occurrence snapshots (NPMI > 0.1), node metrics, the GPU tier-1 layout for Graphistry, and the story-view and ego-graph JSON for the web.

Plan: [MASTER_PLAN §15.1](../docs/plan/MASTER_PLAN.pdf). Status: [status/WS3.md](../status/WS3.md).

## Graph-view exports (WS3c + G phase, contract-free)

`RADAR_PROFILE=full uv run --extra graph python -m graph.export_views` writes to `lake/views/`
(git-ignored), copies `graph/views/temporal.html` and `story.html` next to the JSON, and copies
`*.json` to `web/public/data/views/` (also git-ignored) for the React UI. Persons (`per:`) and
deny-listed wire services (`ranked_universe.org_deny`) are dropped.

### `temporal.json` (cosmos.gl, `TemporalGraph` / `temporal.html`)

| Field | Meaning |
|---|---|
| `_meta.profile` | `dev` or `full` |
| `_meta.layout` | `frozen_fruchterman_reingold_space_4096` |
| `_meta.weeks`, `_meta.iso_weeks` | the last 13 weeks present in `edges_weekly` (Monday dates / ISO weeks); a missing week stays missing |
| `_meta.params` | `span_weeks`, `max_nodes` (default 1000), `min_n` (default 20), `min_npmi_exclusive` (0.1), `top_k_per_node` (default 5), `top_labels` (30) |
| `_meta.n_nodes`, `n_labeled_nodes`, `n_edges`, `edges_per_week` | sizes after top-k NPMI pruning per node per week |
| `_meta.top_movers_per_week[w]` | ranked top-10 topics and fastest rising PageRank nodes for week `w` |
| `nodes[i].id`, `label`, `label_es`, `etype` | `'<etype>:<entity>'`, Spanish display label, `org`/`thm`/`loc` |
| `nodes[i].x`, `y` | precomputed frozen 2D position in cosmos.gl space units (`[448, 3648]` inside `4096x4096`) |
| `nodes[i].show_label` | `true` for the top 30 nodes by PageRank over the span and every ranked top-10 topic |
| `nodes[i].deg_span` | weighted degree (sum of `n`) over the span on the candidate edges |
| `nodes[i].pagerank[w]`, `pr_rank_delta[w]`, `deg_growth[w]` | weekly metrics from `node_metrics_weekly` (null when absent) |
| `nodes[i].rank[w]`, `decision[w]` | from `topic_scores_weekly` when ranked that week, else null |
| `edges.source[k]`, `target[k]` | node indices (columnar arrays) |
| `edges.week[k]`, `n[k]`, `npmi[k]` | week index, co-mentions, NPMI (pruned per week to top-`top_k` by NPMI per node) |

### `story.json`, `story_<slug>.json`, `stories_index.json` (sigma.js 3, `StoryGraph` / `story.html`)

One `story_<slug>.json` file is written per ranked top-10 topic of the latest scored week (plus
reference topics present in the 1-hop ring), and `story.json` holds the #1 topic (`--topic`/`--week`
override it). `stories_index.json` lists `top10` and maps every exported `topic_id` to its file and
metadata. Each story file is a graphology serialized graph with Spanish labels (`label`, `label_es`),
radial coordinates (`x`, `y`), `role` (`topic` / `ring`), `edges` (`kind` = `ring` / `among`), and
`attributes.scores` (`topic_scores_weekly` row).
