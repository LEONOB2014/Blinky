# WS3: graph

Weekly co-occurrence snapshots (NPMI > 0.1), node metrics, the GPU tier-1 layout for Graphistry, and the story-view and ego-graph JSON for the web.

Plan: [MASTER_PLAN §15.1](../docs/plan/MASTER_PLAN.pdf). Status: [status/WS3.md](../status/WS3.md).

## Graph-view exports (WS3c + G phase, contract-free)

`RADAR_PROFILE=full uv run --extra graph python -m graph.export_views` writes to `lake/views/`
(git-ignored), copies `graph/views/temporal.html` and `story.html` next to the JSON, and copies
`*.json` to `web/public/data/views/` (also git-ignored) for the React UI. Persons (`per:`) and
deny-listed wire services (`ranked_universe.org_deny`) are dropped.

### `temporal.json` (cosmos.gl, `TemporalGraph` / `temporal.html`)

| Field | Meaning & Formula |
|---|---|
| `_meta.profile` | `dev` or `full` |
| `_meta.layout` | `frozen_fruchterman_reingold_space_4096` |
| `_meta.weeks`, `_meta.iso_weeks` | the last 13 weeks present in `edges_weekly` (Monday dates / ISO weeks); a missing week stays missing |
| `_meta.params` | `span_weeks`, `max_nodes` (default 1000), `min_n` (default 20), `min_npmi_exclusive` (0.1), `top_k_per_node` (default 5), `top_labels` (30), `leiden_seed` (42) |
| `_meta.n_nodes`, `n_labeled_nodes`, `n_edges`, `edges_per_week` | sizes after top-k NPMI pruning per node per week |
| `_meta.top_movers_per_week[w]` | ranked top-10 topics and fastest rising PageRank nodes for week `w` |
| `_meta.property_distributions_latest_week` | measured median, p90, and count for edge and node properties in the latest week |
| `nodes[i].id`, `label`, `label_es`, `etype` | `'<etype>:<entity>'`, Spanish display label, `org`/`thm`/`loc` |
| `nodes[i].ring` | taxonomy ring: `ai` (Ring 1: core AI lab/model/chip orgs or themes), `it` (Ring 2: ICT/software themes, cloud/telecom/tech orgs), `ai_domain` (Ring 3: domain themes, non-tech industry orgs, locations). Derived from `contracts/taxonomy.yaml`, `bq_sql/s2_monthly_insert.sql` (`f_org`, `f_ict`), and `bq_sql/s4a_article_segment.sql` (`tech_org`, `domains`) because `topic_daily` is filtered to Ring-1 articles (`segment = 'ai'`) |
| `nodes[i].domain` | domain name (`business`, `climate`, `labour`, `health`, `education`, `elections_misinformation`, `law_regulation`, `security`, or null) |
| `nodes[i].x`, `y` | precomputed frozen 2D position in cosmos.gl space units (`[448, 3648]` inside `4096x4096`) |
| `nodes[i].show_label` | `true` for the top 30 nodes by PageRank over the span and every ranked top-10 topic |
| `nodes[i].deg_span` | weighted degree (sum of `n`) over the span on candidate edges |
| `nodes[i].pagerank[w]`, `pr_rank_delta[w]`, `deg_growth[w]` | weekly metrics from `node_metrics_weekly` (null when absent) |
| `nodes[i].importance[w]` | within-week percentile rank of `pagerank` in `[0, 1]` ($k / (M - 1)$ among non-null entries); uniform size metric across lenses |
| `nodes[i].betweenness[w]` | normalised Freeman betweenness on the week's pruned graph with edge distances $d = 1 / \text{NPMI}$: $B(v) / ((n_{\text{active}} - 1)(n_{\text{active}} - 2) / 2)$ |
| `nodes[i].cross_ring_share[w]` | share of node incident edge weight going to neighbours of a different ring: $\sum_{u \in \partial v, \text{ring}(u) \neq \text{ring}(v)} n(u, v) / \sum_{u \in \partial v} n(u, v)$ |
| `nodes[i].momentum[w]` | mean of within-week percentiles of `pr_rank_delta` and `deg_growth`: $0.5 \times (\text{pct}(\text{pr\_rank\_delta}) + \text{pct}(\text{deg\_growth}))$ in `[0, 1]` |
| `nodes[i].community_week[w]` | Leiden community index ($0, 1, \dots$ sorted by community size descending) on the week's pruned graph with fixed seed 42; within-week only |
| `nodes[i].new_nbr_rate[w]`, `kcore[w]` | from `node_metrics_weekly` |
| `nodes[i].tone[w]` | weekly weighted mean article tone from `topic_daily` (null when absent) |
| `nodes[i].emotional_charge_pct[w]`, `window_state[w]` | from `topic_scores_weekly` (`window.state`, `emotional_charge_pct`) |
| `nodes[i].rank[w]`, `decision[w]` | from `topic_scores_weekly` when ranked that week, else null |
| `edges.source[k]`, `target[k]` | node indices (columnar arrays) |
| `edges.week[k]`, `n[k]`, `npmi[k]` | week index, co-mentions, NPMI (pruned per week to top-`top_k` by NPMI per node) |
| `edges.edge_state[k]` | weekly state against prior week: `new` ($n_{\text{prev}} = 0$), `growing` ($n \ge 1.5 n_{\text{prev}}$), `fading` ($n \le 0.5 n_{\text{prev}}$), `persisting` |
| `edges.n_growth[k]` | $\ln((n + 1) / (n_{\text{prev}} + 1))$ |
| `edges.cross_ring[k]` | boolean: `true` if $\text{ring}(\text{source}) \neq \text{ring}(\text{target})$ |

### `story.json`, `story_<slug>.json`, `stories_index.json` (sigma.js 3, `StoryGraph` / `story.html`)

One `story_<slug>.json` file is written per ranked top-10 topic of the latest scored week (plus
reference topics present in the 1-hop ring, e.g. Nvidia, Microsoft, Google, OpenAI, Anthropic,
TECH_AUTOMATION), and `story.json` holds the #1 topic (`--topic`/`--week` override it).
`stories_index.json` lists `top10` and maps every exported `topic_id` to its file and
metadata. Each story file is a graphology serialized graph with Spanish labels (`label`, `label_es`),
radial coordinates (`x`, `y`), `role` (`topic` / `ring`), `edges` (`kind` = `ring` / `among`),
`edge_state`, `n_growth`, `cross_ring`, and node attributes (`ring`, `domain`, `betweenness`,
`cross_ring_share`, `community_week`, `importance`, `momentum`, `pagerank`, `kcore`, and
`attributes.scores` from `topic_scores_weekly`).
