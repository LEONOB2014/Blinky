# WS3 status

Owner: claude-home · Directories: `graph/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 12:04 UTC-5 · `feat/ws3-ai-graph-expressive` (end-to-end matrix of the AI graph, all pass) · committed locally (claude-work), not pushed

## End-to-end matrix of the AI graph (12:04 UTC-5, claude-work)

`graph/views/e2e_ai_matrix.mjs` drives headed Chrome (WebGL, ANGLE Metal on the M1 Pro, Retina viewport
1440x900) against a local build in AI mode (views from `export_views --ai` at ec78ba4, API with
`RADAR_SOURCE=ai`); `graph/views/e2e_ai_matrix.py` turns the run into this table. A cell passes with 0
console errors or warnings, 0 non-finite node positions (`window.__metrics.nan_positions`), a drawn canvas
(labels and legend hidden for the screenshot; at least 0.4% of pixels marked), the week's top 10 all
labelled, and the week badge on the week set. Cells show the top-10 labels. All *measured*, run finished at 12:01 UTC-5:

| Lens | W30 | W31 | W32 | W33 | W34 | W35 | W36 | W37 | W38 | W39 | W40 | W41 | W42 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Radar | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Historia | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Puente | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Momento | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Novedad | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Comunidades | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Emoción | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Ventana | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Familia | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |
| Postura | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 | pass 10/10 |

- **130 of 130 cells pass**: 0 errors, 0 non-finite positions, lowest drawn share 0.008, 10/10 of the
  top 10 labelled in every lens and week. The only log line of the run is a 404 for `favicon.ico`.
- **Play** (13 weeks): Familia ends at 2026-W42 at 116 fps, Postura at 2026-W42 at 121 fps; 0 errors.
- **Selection** (rail "Lo más grande"): Nvidia, OpenAI, Anthropic and Agentes de IA at W42 and at W30 all
  open in Historia with the topic labelled and its neighbourhood (11-24 labels); 0 errors.
- **Fixed on the way** (`TemporalGraph.tsx`, AI mode only): the first run labelled only 6-9 of the top 10 in
  71 cells, because the 26-label cap stopped placement before the remaining top-10 labels (PageRank put
  other topics first); must-show labels are now exempt from the cap. The checker compares full names
  (the label tooltip), since long labels are shortened on the graph.
- **Note:** an earlier claim of "no page errors" in my visual checks was not verified (the harness only
  kept exceptions without the prefix my filter looked for); this matrix records exceptions, console errors
  and warnings, and browser log errors explicitly.

Previous: 2026-10-18 09:56 UTC-5 · `feat/ws3-ai-graph` (community counts on the AI cards) · committed locally; the orchestrator pushes

## Done

- `graph/metrics.py` -> `node_metrics_weekly`: weighted degree (sum of `n`), `deg_growth`
  = ln(deg_w / last week's), new-neighbour rate vs the prior 4 weeks, weighted PageRank and
  `pr_rank_delta` (last week's rank minus this week's: positive = rising), k-core (unweighted
  coreness), Leiden (modularity, weight `n`, seed 42) matched across weeks at Jaccard >= 0.3 with
  birth/merge/split/continue, `is_hub` = top ceil(1%) of nodes by weighted degree (ties included).
- Missing weeks are never filled: `deg_growth`, `pr_rank_delta` and `community_event` are null
  when last week is absent from the data; `new_nbr_rate` is null unless all 4 prior weeks are
  present. The first week (and the week after a gap) has a null community event, not `birth`.
- `graph/context.py` -> `topic_context_1hop`: topics = `ranked_entity_types` of
  `contracts/taxonomy.yaml` (org, thm); n >= 3, NPMI > 0.1, that week's hubs dropped, top 20 by
  NPMI (ties by `n`, then name). `neighbor_segment` / `neighbor_domain` are null: WS1's tables
  do not provide them yet (`context_1hop(..., segments=)` joins them once they do).
- `graph/build.py`: runs both for the active profile, validates every row with
  `radar.contracts.validate_records` (aborts on any violation), writes `lake/gold/` on full,
  only to `--out` on dev.
- 12 unit tests on real dev-slice weeks (hub exclusion, NPMI/n/rank limits, top-20 equals the
  brute-force top NPMI, community matching 2026-10-05 -> 2026-10-12, gap handling, contract
  validation of both outputs). `make check && make test` pass locally.

## WS3c graph-view smoke test (done, 2026-10-17 23:48 UTC-5)

All numbers *(measured)* on this Mac (Apple M1 Pro; Chrome reports the WebGL renderer as
"ANGLE Metal Renderer: Apple M1 Pro", so both views run on the real GPU), full profile, unless marked
*(estimate)*. Nothing was uploaded; no cloud service or account.

**Exports** (`graph/export_views.py` -> `lake/views/`, fields in `graph/README.md`):

| export | nodes | edges | file | build time |
|---|---|---|---|---|
| temporal, 13 weeks (2026-07-20 .. 2026-10-12), top 2,000 nodes, n >= 5, NPMI > 0.1 | 2,000 | 1,869,221 (134,711-173,028 a week; 608,196 unique pairs) | 42.0 MB | 3.9 s (5.2 s with the story) |
| temporal "light": top 1,000 nodes, n >= 20 | 1,000 | 702,169 (50,039-66,979 a week; 206,278 unique pairs) | 15.8 MB | 1.6 s |
| story: `org:marsh mclennan`, 2026-W42 (the #1 of `topic_scores_weekly`, read, not hard-coded) | 21 | 162 (20 ring + 142 among neighbours) | 29.6 kB | 0.05 s |

No `per:` node in any export (guarded in code and by a unit test that injects one).

**GPU temporal view** (`lake/views/temporal.html`, cosmos.gl 3.5.1 from unpkg, force layout and drawing
on the GPU; 10 s of layout on the union of the 13 weeks, then frozen; play/pause and week slider;
node size = that week's PageRank, ranked topics coloured by decision). Headed Chrome, 1440x900:

| export | JSON parsed | first frame | fps during layout | fps playing the 13 weeks | week switch (median / max) |
|---|---|---|---|---|---|
| full (2,000 / 1.87M) | 0.31 s | 1.02 s | 16.6 | 107.0 | 14.8 / 25.2 ms |
| light (1,000 / 702k) | 0.12 s | 1.16 s | 45.6 | 119.6 | 4.5 / 14.5 ms |

Largest graph that stays smooth: the full export plays the sweep at 107 fps (about 140k edges a
week); only the layout phase drops below 30 fps, at 608k unique links. The light export stays above
45 fps throughout. So about 200k unique links is the limit for a smooth live layout on this Mac, and
a precomputed (frozen) layout removes that limit for the sweep.

**Story view** (`lake/views/story.html`, sigma.js 3.0.3 + graphology 0.26.0): rendered 75-98 ms after
load; topic in the centre, its 20 neighbours by rank, edge width by co-mentions, scores row as the side
panel.

**Screenshots (not committed):** `/Users/andresbecerra/Documents/30x_Blinky/radar/lake/views/temporal.png` (full), `/Users/andresbecerra/Documents/30x_Blinky/radar/lake/views/light/temporal.png`,
`/Users/andresbecerra/Documents/30x_Blinky/radar/lake/views/story.png`.

**What broke (and the fix in place):**
1. jsDelivr's `+esm` build of cosmos.gl loads two luma.gl versions (`@luma.gl/engine@9.3.6` imports
   `shadertools@9.3.5`); luma.gl throws "multiple versions detected". Fix: the self-contained UMD
   build `unpkg.com/@cosmos.gl/graph@3.5.1/dist/index.min.js` (global `Cosmos`). In `web/` the npm
   install must pin all four `@luma.gl/*` packages to one `~9.3` version (the README says so).
2. With `fitViewOnInit` and rescaled small coordinates the camera zoomed into empty space (zoom 9.7)
   and nothing was visible. Fix: positions in space units, `rescalePositions: false`, an explicit
   `fitView()` after `ready` and after the layout freezes. Control: cosmos.gl's own storybook example
   rendered in the same harness.
3. sigma.js 4.0.3 (latest) filled the whole canvas with a single node, even in a two-node example; sigma
   3.0.3 renders correctly. Pinned to 3.0.3.
4. The full temporal graph renders smoothly but reads as a hairball (dense co-occurrence, 140k edges a
   week among 2,000 nodes). Readability is G work: a precomputed layout per span, fewer edges per week
   (e.g. top-k by NPMI per node), and highlighting the ranked top 10.
5. The 10 s GPU layout does not converge on 608k links (it took 139 s to end on its own).

**Hours G needs to move both views into `web/`** *(estimate)*: about 4.5 h in total. That covers a
cosmos.gl React component with pinned luma.gl, a frozen layout and the week player (1.5 h),
readability (1.5 h), a sigma 3 story component reading the same JSON (1 h), and a static export or
API path for the JSON (0.5 h). That fits the gate's "full G" branch only if G starts by 06:30.

**Not done:** item 5 of the brief (precomputed layout with pygraphistry/networkx); the frozen GPU
layout covers the sweep for now.

## Addendum 22:30 (done)

1. `per:` neighbours are dropped from `topic_context_1hop` before the top-20 selection, so each topic
   still gets up to 20 non-person neighbours. `per:` nodes stay in `node_metrics_weekly` as graph
   structure only. Full rerun: ring 4,773,204 rows (was 4,849,854), 0 person neighbours; metrics
   473,275 rows, unchanged; 518 s, 2.44 GB peak (measured).
2. Ranked topics: no change; the ring keeps covering every org/thm node (`ranked_entity_types`) and
   the API filters by `ranked_universe`.
3. Community continuity, tried once (measured, 876 community-weeks with a previous week, 51 weeks):
   - full membership, Jaccard >= 0.3: 842 birth, 34 continue: 3.9% non-birth;
   - nodes in the top 10% by weighted degree in both weeks, Jaccard >= 0.3: 697 birth, 174 continue,
     4 split, 1 merge: 20.4% non-birth.
   Continuity stays under 50%, so `community_event` and `community_id` stay as computed (full
   membership) and **agents must not use them**. No further iteration tonight.
4. `ci.yml` untouched; the graph tests skip in CI and run locally with `uv sync --extra graph`.

## In progress

- Nothing. `origin/develop` is merged (lexicon PR #66 and the community sensor
  PR #67). The AI graph export below is committed locally; the orchestrator pushes.

## Blocked on

- Nothing. `topic_context_1hop` has no `ai:` rows (measured, 0). Stories take
  their ring from `edges_ai_weekly` until that table is rebuilt.

## Notes for the lead

- The `develop` merge changed `uv.lock`; plain `uv run` then drops the `graph` extra and the graph
  tests skip silently. Use `uv sync --extra graph` (or `uv run --extra graph`) in this worktree.

## Numbers (each marked measured or estimate)

Full profile, `RADAR_PROFILE=full uv run --extra graph python -m graph.build`, 2026-10-17 22:45 UTC-5
(persons out of the ring): 51 weeks (2025-10-27 .. 2026-10-12, contiguous), 37,766,030 edges in;
473,275 `node_metrics_weekly` rows and 4,773,204 `topic_context_1hop` rows written to `lake/gold/`,
every row contract-valid; 321,586 topic-weeks, 184,681 of them at the 20-neighbour cap. Run time
518 s, peak memory 2.44 GB (measured). The first week (2025-10-27) is partial (2,603 nodes against
6,301-11,365 afterwards), so 2025-11-03's `deg_growth` and rank deltas compare against a partial week.

Per week (measured; `ring_topics` = org/thm topics with at least one ring neighbour):

| wk | nodes | edges | communities | hubs | ring_topics | ring_rows |
|---|---|---|---|---|---|---|
| 2025-10-27 | 2603 | 182482 | 9 | 27 | 2143 | 34324 |
| 2025-11-03 | 9802 | 798741 | 21 | 99 | 6556 | 97145 |
| 2025-11-10 | 9301 | 723598 | 23 | 94 | 6237 | 91228 |
| 2025-11-17 | 10860 | 849909 | 28 | 109 | 7165 | 104860 |
| 2025-11-24 | 8257 | 655890 | 16 | 83 | 5744 | 86794 |
| 2025-12-01 | 8714 | 659506 | 17 | 88 | 5978 | 88369 |
| 2025-12-08 | 9272 | 745845 | 18 | 93 | 6237 | 93752 |
| 2025-12-15 | 8383 | 700955 | 17 | 84 | 5728 | 87309 |
| 2025-12-22 | 6451 | 573536 | 17 | 65 | 4720 | 74112 |
| 2025-12-29 | 6301 | 545081 | 13 | 64 | 4676 | 72290 |
| 2026-01-05 | 8648 | 717306 | 14 | 87 | 5945 | 89990 |
| 2026-01-12 | 8819 | 741257 | 20 | 89 | 6022 | 90859 |
| 2026-01-19 | 8916 | 728918 | 17 | 90 | 5953 | 89631 |
| 2026-01-26 | 9276 | 742416 | 20 | 93 | 6236 | 92590 |
| 2026-02-02 | 8844 | 698014 | 23 | 89 | 5953 | 87923 |
| 2026-02-09 | 9593 | 745200 | 21 | 96 | 6310 | 93474 |
| 2026-02-16 | 9886 | 801902 | 17 | 99 | 6446 | 95901 |
| 2026-02-23 | 10328 | 837759 | 15 | 104 | 6861 | 101036 |
| 2026-03-02 | 9096 | 751511 | 14 | 91 | 6405 | 95730 |
| 2026-03-09 | 9271 | 730309 | 19 | 93 | 6465 | 94704 |
| 2026-03-16 | 9805 | 775509 | 19 | 99 | 6543 | 97833 |
| 2026-03-23 | 9155 | 713106 | 16 | 92 | 6299 | 92353 |
| 2026-03-30 | 7988 | 627373 | 24 | 80 | 5622 | 84870 |
| 2026-04-06 | 8165 | 627417 | 20 | 82 | 5626 | 84316 |
| 2026-04-13 | 9028 | 716451 | 19 | 91 | 6234 | 93894 |
| 2026-04-20 | 9617 | 721893 | 17 | 97 | 6314 | 92454 |
| 2026-04-27 | 9909 | 796885 | 22 | 100 | 6555 | 96367 |
| 2026-05-04 | 9484 | 716758 | 16 | 95 | 6145 | 88850 |
| 2026-05-11 | 10484 | 883393 | 18 | 105 | 6982 | 103777 |
| 2026-05-18 | 10637 | 844559 | 13 | 107 | 7105 | 104266 |
| 2026-05-25 | 10205 | 834821 | 16 | 103 | 6828 | 102131 |
| 2026-06-01 | 10691 | 838932 | 20 | 107 | 7208 | 104449 |
| 2026-06-08 | 9997 | 789336 | 14 | 100 | 6951 | 101100 |
| 2026-06-15 | 8977 | 701425 | 23 | 90 | 6190 | 91181 |
| 2026-06-22 | 9992 | 766247 | 12 | 100 | 6762 | 99571 |
| 2026-06-29 | 8980 | 695386 | 21 | 90 | 6183 | 91196 |
| 2026-07-06 | 9389 | 725132 | 10 | 94 | 6486 | 94895 |
| 2026-07-13 | 9897 | 799004 | 16 | 99 | 6805 | 101178 |
| 2026-07-20 | 9758 | 759401 | 13 | 98 | 6630 | 96532 |
| 2026-07-27 | 9863 | 767030 | 21 | 99 | 6710 | 99805 |
| 2026-08-03 | 9206 | 720385 | 16 | 93 | 6331 | 93518 |
| 2026-08-10 | 8827 | 670624 | 16 | 89 | 6067 | 88890 |
| 2026-08-17 | 8832 | 692544 | 17 | 89 | 6113 | 91337 |
| 2026-08-24 | 9684 | 783057 | 16 | 97 | 6717 | 101065 |
| 2026-08-31 | 9330 | 705039 | 16 | 94 | 6370 | 92881 |
| 2026-09-07 | 10268 | 804099 | 16 | 103 | 6922 | 101960 |
| 2026-09-14 | 11365 | 975857 | 12 | 114 | 7410 | 110040 |
| 2026-09-21 | 10955 | 958995 | 14 | 110 | 7362 | 108632 |
| 2026-09-28 | 10176 | 825854 | 16 | 102 | 6783 | 101086 |
| 2026-10-05 | 9630 | 776470 | 16 | 97 | 6530 | 97159 |
| 2026-10-12 | 10360 | 822913 | 21 | 104 | 7023 | 103597 |

Community matching across weeks (measured): of 876 community-weeks with a previous week, 842 are
`birth` and 34 `continue` (no merge or split); 9 first-week communities have a null event. So at
Jaccard >= 0.3 `community_id` has almost no continuity on full data. Diagnosis on 2026-09-28 ->
10-05 and 10-05 -> 10-12 (measured):
- Leiden is stable within a week: seed 42 vs seed 7 reproduce 12/14 and 18/24 communities at
  Jaccard >= 0.3.
- The node set churns: consecutive weeks share 32% of nodes (node Jaccard 0.321, 0.318); 33% of
  `org:` and 22% of `per:` nodes recur against 83% of `thm:`; 95% of the p90-99 and 100% of the top
  1% by weighted degree recur, but only 32% of the bottom half.
- Partitions also reshuffle: restricted to nodes present in both weeks, only 5/16 and 6/21 match.
  Communities are large (largest 2,997 and 3,217 nodes) on a dense graph (~800k edges, ~10k nodes).

Distributions over node-weeks (measured): median `new_nbr_rate` 0.606, median `deg_growth` -0.008.

## WP3 AI graph (2026-10-18 09:05 UTC-5)

`graph/export_views.py` takes `--edges`, `--topics`, `--scores`, `--lexicon` and `--ai`.
`--ai` reads `edges_ai_weekly` and `topic_ai_daily`, keeps only `ai:` nodes, overlays
`label_es` from the lexicon, and writes `family`, `family_es`, `stance`, `default_color_by`
and the Spanish legends. NPMI, edge state, betweenness, momentum, community and importance
are still computed on the pruned edges. With two or more critics, the layout seats that camp
on the left. The org graph stays on the decision lens when the yaml is present.

The Postura lens colours by stance and sizes by the absolute weekly GDELT tone. Questions
"¿quién se opone?", "críticos" and "regulación" select it, after tone so a tone question
still wins. The rail and the topic card show a family chip when the id is `ai:` or the card
has `family`. The Comunidad IA line reads `community` when WP4 sends it, and otherwise says
there is no signal this week. It does not invent paper or talk counts.

Tests (measured, this machine): `uv run --extra graph pytest graph/tests/test_ai_graph.py
graph/tests/test_export_views.py agents/tests/test_runtime.py` — 48 passed. The AI-export
test is a 4-node fixture, not the lake. `bun install` then `tsc -b` in `web/` passed with
no errors. The UI was not opened in a browser.

### Lexicon coverage (second opinion)

Read of `contracts/ai_lexicon.yaml` at `024938e` on `feat/ws0-ai-lexicon` (measured):
110 entries. Stances: 64 promoter, 28 neutral, 18 critic. The file is not on this branch.

Already covered, so not gaps: Chinese labs DeepSeek, Qwen, Kimi, Zhipu/GLM, ERNIE,
Doubao, Hunyuan, MiniMax and Huawei/Pangu; `model:open_chinese` and
`model:deepseek_models`; Hugging Face (`research:hugging_face`); open-source patterns
for PyTorch, LangChain, LlamaIndex, vLLM, Ollama and llama.cpp; agents as `tech:agents`
plus MCP; the critics' camp (pause, FLI/CAIS/MIRI, protests, artists including SAG-AFTRA,
copyright, jobs, existential risk, the EU AI Act).

Gaps an editor would still miss:

1. No pattern for 01.AI / Yi, Baichuan, StepFun, SenseTime / SenseNova, or iFlytek / Spark.
   A headline that only names Yi or SenseNova matches neither those labs nor
   `model:open_chinese`.
2. No node for the EU AI Office, AI Factories, EuroHPC, InvestAI, or the GPAI Code of
   Practice. `policy:eu_ai_act` matches `eu ai` and "European Commission … AI", so those
   stories collapse into the Act.
3. Agent frameworks are not nodes. `tech:agents` matches "ai agent" / "agentic", not
   LangGraph, CrewAI, AutoGen, smolagents, Dify or n8n. LangChain only sits inside
   `research:open_source_projects`.
4. Open-source runtimes absent from that pattern list: SGLang, Unsloth, MLX, Open WebUI,
   LM Studio. vLLM, Ollama and llama.cpp are present.
5. Named regulators are not entries: FTC, UK CMA, CNIL, ICO, Ofcom, NIST. "Safety
   institute" matches `risk:ai_safety`, so a UK or US AISI story does not land on a
   regulator node in the critics' camp.
6. No LMSYS / Chatbot Arena entry. "leaderboard" only matches
   `research:papers_benchmarks`.
7. Empty `wikipedia.es` on Moonshot, Zhipu, ByteDance, Tencent, MiniMax and Huawei, so
   those labs get no Spanish pageview series until a title is added.

Family ids in that yaml are `techniques`, `business`, `safety`, `opposition` and
`society` (35 of 110 entries: 11 + 8 + 6 + 5 + 5). The graph palette uses those ids.

### Real export (measured, 2026-10-18 09:12 UTC-5)

`RADAR_PROFILE=full uv run --extra graph python -m graph.export_views --ai`
on this Mac. `edges_ai_weekly` has a language row and an `all` total (one pair,
Anthropic–cyber, week 2026-10-12: eng 2 + spa 3 + por 1 + other 2 = all 8). The
export keeps `all` only, and reads `topic_ai_scores_weekly`.

Result: 84 nodes, all `ai:` and all in the lexicon; 811 edges over 13 weeks
(2026-07-20 .. 2026-10-12); 0.50 s. 16 critics sit on the left (max x 1200.5,
min other x 1344.0), including pause, regulation, copyright, jobs and existential
risk. Latest week rank 1 is Alianzas y adquisiciones en IA (`esperar`). The
2026-W42 story of that topic has 7 neighbours taken from the edges. The EU AI Act
has no co-mention with n ≥ 20 inside these 13 weeks (its two such edges are both
2026-01-26, n = 59 and 61), so it is not in this graph. JSON is in `lake/views/`
and `web/public/data/views/` (git-ignored). The UI was not opened in a browser.

### Community counts on the AI cards (measured, 2026-10-18 09:56 UTC-5)

`lake/gold/community_topic_weekly.parquet`: 1,041 rows over 15 weeks (2026-W28 .. 2026-W42).
2026-W42 is 79 rows and 54 topics. Category totals that week: research 35 rows / 452 items,
builders 25 / 63, vision 12 / 12, critics 3 / 3, media 2 / 2, practitioners 2 / 7.

`GET /api/community?week=2026-W42` returns those rows and only the six schema fields.
`GET /api/radar` for the same week returns the lexicon top 10 from `topic_ai_scores_weekly`
(the dev slice has no that table, so the default profile still reads `topic_scores_weekly`).
The radar body has no community fields. Both payloads validate against their contracts.

Top 10 lines rendered in headless Chrome at `http://127.0.0.1:5184/` (API on 8014; 8010 and
5180 were left running):

| rank | topic | line |
|---|---|---|
| 1 | Alianzas y adquisiciones en IA | Comunidad IA: sin señal de esta semana |
| 2 | Google DeepMind | Comunidad IA: sin señal de esta semana |
| 3 | Bolsa y acciones de IA | Comunidad IA: sin señal de esta semana |
| 4 | Fichajes, salidas y spin-offs | Comunidad IA: sin señal de esta semana |
| 5 | Protestas y rechazo social a la IA | Comunidad IA: sin señal de esta semana |
| 6 | Artistas y creadores contra la IA | La comunidad IA lo discute: 1 pieza de construcción |
| 7 | Rondas y valuaciones de IA | Comunidad IA: sin señal de esta semana |
| 8 | Ajuste fino y entrenamiento | La comunidad IA lo discute: 61 de investigación, 2 de construcción |
| 9 | Pesos abiertos y open source | La comunidad IA lo discute: 4 piezas de investigación |
| 10 | Robótica e IA física | La comunidad IA lo discute: 7 piezas de investigación |

The rail was ten `ai:` cards. No non-`ai:` card was on that screen. `communityFromRows`
returns null for an `org:` id, and the line is rendered only when `topic_id` starts with `ai:`.
