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
| `nodes[i].ring` | **name-list rule**, not `topic_daily.segment`. Every exported node comes from AI-segment articles, so `segment` is `ai` for all of them and is not used. UI legend: “Sector (regla por nombre): IA / TI / otros sectores”. Values: `ai` (IA), `it` (TI), `ai_domain` (otros sectores). Rule and lists below |
| `nodes[i].domain` | domain name (`business`, `climate`, `labour`, `health`, `education`, `elections_misinformation`, `law_regulation`, `security`, or null) |
| `nodes[i].x`, `y` | precomputed frozen 2D position in cosmos.gl space units (`[448, 3648]` inside `4096x4096`) |
| `nodes[i].show_label` | `true` for the top 30 nodes by PageRank over the span and every ranked top-10 topic |
| `nodes[i].deg_span` | weighted degree (sum of `n`) over the span on candidate edges |
| `nodes[i].pagerank[w]`, `pr_rank_delta[w]`, `deg_growth[w]` | weekly metrics from `node_metrics_weekly` (null when absent) |
| `nodes[i].importance[w]` | within-week percentile rank of `pagerank` in `[0, 1]` ($k / (M - 1)$ among non-null entries); uniform size metric across lenses |
| `nodes[i].betweenness[w]` | normalised Freeman betweenness on the week's pruned graph with edge distances $d = 1 / \text{NPMI}$: $B(v) / ((n_{\text{active}} - 1)(n_{\text{active}} - 2) / 2)$ |
| `nodes[i].cross_ring_share[w]` | **cruce de sector (regla)**: share of the node's incident edge weight (`n`) that touches a neighbour whose name-list sector differs: $\sum_{u \in \partial v, \text{ring}(u) \neq \text{ring}(v)} n(u, v) / \sum_{u \in \partial v} n(u, v)$. Not a read of `topic_daily.segment` |
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
| `edges.cross_ring[k]` | boolean **cruce de sector (regla)**: `true` when the name-list sectors of the two ends differ |

### `story.json`, `story_<slug>.json`, `stories_index.json` (sigma.js 3, `StoryGraph` / `story.html`)

One `story_<slug>.json` file is written per ranked top-10 topic of the latest scored week (plus
reference topics present in the 1-hop ring, e.g. Nvidia, Microsoft, Google, OpenAI, Anthropic,
TECH_AUTOMATION), and `story.json` holds the #1 topic (`--topic`/`--week` override it).
`stories_index.json` lists `top10` and maps every exported `topic_id` to its file and
metadata. Each story file is a graphology serialized graph with Spanish labels (`label`, `label_es`),
radial coordinates (`x`, `y`), `role` (`topic` / `ring`), `edges` (`kind` = `ring` / `among`),
`edge_state`, `n_growth`, `cross_ring` (cruce de sector, regla por nombre), and node attributes
(`ring`, `domain`, `betweenness`, `cross_ring_share`, `community_week`, `importance`, `momentum`,
`pagerank`, `kcore`, and `attributes.scores` from `topic_scores_weekly`).

### Sector (regla por nombre)

`node_ring_and_domain` assigns `ai` / `it` / `ai_domain` from the entity id and, for an org, its
primary subtopic. It does not read `topic_daily.segment`. Domain (`business`, `climate`, …) still
comes from `taxonomy.yaml` `domains` when a theme prefix or primary subtopic matches; that field is
separate from the sector.

Order:

1. Theme `TECH_AUTOMATION` or a theme code starting with `AI_` → `ai`.
2. Theme code starting with an IT prefix (below) → `it`.
3. Any other theme, and every `loc:` → `ai_domain`.
4. Org whose name is in the IA list, **or** whose primary subtopic is `agents`, `llms_models`, or
   `chips_infra` → `ai`. The subtopic check runs before the TI list, so a TI-list name can still
   be IA. Measured in the shipped `temporal.json`: `org:microsoft` is `ai` (the TI list alone
   would label it `it`).
5. Org whose name is in the TI list → `it`.
6. Every other org → `ai_domain`.

IA org names: openai, openai group, anthropic, google deepmind, deepmind, nvidia, nvidia
corporation, mistral, mistral ai, deepseek, hugging face, perplexity, xai, cohere, stability ai,
midjourney, scale ai, databricks, cerebras, groq, safe superintelligence, meta ai, data centers,
supermicro.

IA subtopics (primary subtopic of an org): agents, llms_models, chips_infra.

TI org names: google, alphabet, microsoft, apple, amazon, meta, meta platforms, facebook,
instagram, youtube, linkedin, ibm, intel, amd, advanced micro devices, qualcomm, tsmc, taiwan
semiconductor, samsung, samsung electronics, broadcom, micron, micron technology, sandisk, oracle,
salesforce, tesla, spacex, rocket lab, baidu, alibaba, tencent, huawei, bytedance, tiktok, sap,
cisco, dell, netflix, comcast, softbank, softbank group, mercadolibre, globant, nubank.

TI theme prefixes: `WB_133_`, `WB_2399_`, `WB_2381_`, `WB_652_`, `WB_658_`, `WB_661_`, `WB_662_`,
`WB_667_`, `WB_669_`, `WB_670_`, `WB_672_`, `WB_678_`, `WB_694_`, `TECH_BIGDATA`, `SOC_INNOVATION`,
`CYBER_ATTACK`, `MEDIA_SOCIAL`.
