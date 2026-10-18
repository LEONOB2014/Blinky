# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (0.x until the hackathon submission).
Entries are generated from Conventional Commits by commitizen; see
[docs/development/releasing.md](docs/development/releasing.md).

## v0.3.1 (2026-10-18)

### Highlights (every number measured)

- **An expressive AI graph.** ForceAtlas2 layout seeded by Leiden, node size by importance (5-24 px), fine
  translucent curves whose width and brightness follow co-mentions and NPMI, frameless labels. 2026-W42: 86
  topics and 147 links (was 38 and 51).
- **Guaranteed in every configuration.** An end-to-end browser matrix (`graph/views/e2e_ai_matrix.mjs`): 130 of
  130 lens x week cells pass with the week's top 10 labelled 10/10, 0 console errors and 0 broken positions;
  playing 13 weeks ends at 2026-W42 at 116-121 fps.
- **No blank canvas.** Browsers without WebGL2 now get the fallback image of the AI graph (checked with
  `--disable-webgl2` on the live site).
- **README media** re-recorded from the live site.

### Feat

- **graph**: guarantee every week, lens and important topic of the ai graph
- **graph**: an expressive ai graph: metrics, forceatlas2, sizes and frameless labels

### Fix

- **web**: show the fallback image when the browser lacks webgl2 (#87)
- **web**: recapture the fallback graph with the fine curves
- **web**: never cut the ai graph's must-show labels at the label cap
- **web**: draw the ai graph with fine translucent curves
- **web**: render the expressive ai graph at its intended sizes

## v0.3.0 (2026-10-18)

### Highlights (every number measured unless marked)

- **An AI radar.** v0.2 ranked GDELT's extracted organisations, and GDELT does not extract AI-native ones (no `org:openai` in 2026-W42), so its top 10 was banks and retailers. The ranked unit is now a curated lexicon: 110 AI topics in 11 families, including the opposition to AI. W41 and W42 top 10: 10/10 AI topics.
- **Two lists.** "Despegando" (emergence) and "Lo más grande" (volume). W42 leaders: Nvidia 4,718 · OpenAI 2,691 · Microsoft 2,153 · Google 2,116 · Anthropic 1,938 articles.
- **The AI community sensor.** 3,636 items from 23 of 24 public sources over 15 weeks: HF papers and model releases, AI Engineer, DataTalksClub, Vanishing Gradients, Gradient Dissent, W&B, YC (RFS and videos), The Batch, safety and critic organisations. It feeds the card community line, the agents and the Postura lens (promoters vs critics). Unvalidated, kept out of the backtest.
- **Honest backtest of the AI run.** Secondary label 25.6% (22.3–28.8) vs base 25.4%. It beats persistence, not raw-count growth. The primary label is below the coverage rule. The ranking is relevant; it is not yet better than chance on its labels. The trust answer and panel say so.
- **Agents.** Leaders and community tools; Auditor checks for coverage claims, outlet counts and "30X". Release eval v3 (28 questions × 3): grounding 0.964 (0.93–1.00), decisions and routing 1.000.
- **Live** in AI mode on Cloud Run with min-instances 1 for the demo; demo-check 8/8 with a chat turn. README and a living master plan (`docs/plan/MASTER_PLAN.md`). BigQuery 389.7 GB over 74 jobs, inside the free tier.

### BREAKING CHANGE

- topic ids become ai:<entry id>, read from
topic_ai_daily (s15); the v0.2 org universe stays only for the
backtest comparison.

### Feat

- **crosssource**: keep only live streams for a channel and add a refresh target
- **graph**: build the 1-hop ring of the ai topics
- **web**: rail toggle between rising topics and the week's ai leaders
- show measured community counts on the AI cards
- **graph**: colour the AI graph by family and add Postura
- **agents**: answer what the ai community discusses, by code
- **deploy**: select the radar source in the redeploy
- **deploy**: ship the ai radar tables in the api image
- **api**: rank the week's ai leaders by volume
- **crosssource**: add the ai community sensor
- **ingest**: take ai evidence topics from the ws4 scores
- **contracts**: add mocks for topic_ai_daily and edges_ai_weekly
- **bq**: add s15 and s16 generated from the ai lexicon
- **contracts**: add topic_ai_daily and edges_ai_weekly
- **ingest**: generate the ai-lexicon bigquery scripts
- **agents**: resolve ai: topics and add the v2 eval set
- **api**: serve ai lexicon scores when RADAR_SOURCE=ai
- **agents**: read the ai lexicon run's tables under RADAR_SOURCE=ai
- **contracts**: rank a curated ai lexicon instead of gdelt orgs
- **scores**: run scores and backtest on a chosen input source
- **agents**: say which article filter feeds the radar
- **web**: open the trust panel with a calibrated spanish summary
- **agents**: build the trust summary from the chat's trust parsers

### Fix

- **agents**: read the ai backtest for trust under RADAR_SOURCE=ai
- **web**: recapture the fallback graph with the ai leaders labelled
- **web**: label the ai leaders and keep the ai graph's layout
- **web**: replace the fallback graph image with the ai graph
- **graph**: use the ring's co-mention floor for the ai graph
- **graph**: export the AI graph from the all-language edges
- **agents**: route community questions to the signal analyst alone
- **agents**: answer community questions from the community line only
- **crosssource**: keep other sources' items on a partial community fetch
- **agents**: keep the topic name in a corrected brief headline
- **agents**: check brief coverage claims against their es+pt count
- **agents**: stop the auditor reading 30 out of 30X
- **ingest**: check the lexicon id shape, not a copy of its prefixes
- **scores**: apply the 20-article floor to ai topics
- **scores**: use the all bucket of edges_ai_weekly for new neighbours
- **web**: fit the graph and its labels after a view change
- **web**: raise the chat dock above the netlify badge
- keep the brief field name out of the editor role
- trace named weeks in the auditor and drop the editor's duration
- write a calibrated trust line by code and veto overclaims

## v0.2.0 (2026-10-18)

### Highlights (every number measured unless marked)

- **Live radar on the full lake.** UI on Netlify, API and agents on Google Cloud Run; the public chat is rate-limited; the static fallback carries every panel except chat, plus the evidence and trust numbers.
- **GDELT loop.** 4.03M AI, IT and AI × domain articles segmented, Nov 2025 → Oct 2026; 384.3 GB billed over 69 BigQuery jobs, inside the free tier.
- **What is ranked.** Organisations and `TECH_*` themes with ≥ 20 AI articles a week (median 376 topics a week), gated to established or exact-Wikidata entities and guarded against wire syndication.
- **Backtest, both labels, with their limits.** Wikipedia es+pt pageview growth (exact matches, 43 weeks): published radar precision@10 29.2% (24.4–34.0) vs base rate 25.4%; beats persistence even in the worst case (+6.4, 0.7–12.0) but not raw-count growth (31.7%). GDELT es+pt growth: 13.3% vs base 6.7%, a tie with persistence; median lead 3.0 weeks (2.0–4.0).
- **Article classifier.** Two-family teacher panel (96.8% agreement), local student F1 0.964 against the panel; Jev (TypeSafe) only for doubtful articles, $0.044 spent. Human verification of the 300-row sheet pending.
- **Agents.** Eight agents on Qwen3-30B; code computes every decision; a deterministic Auditor; LangSmith traces and a frozen 25-question set (3 repetitions): release eval on develop: grounding 1.000 (75/75 runs), routing 1.000, usefulness (judge that sees the data) 0.383 → 0.663 (0.63–0.70); the decision, evidence and graph-construction lines are written by code; readers' thumbs up/down recorded per turn.
- **Spanish briefs.** One brief per top-10 topic (20 for W41–W42), 20/20 pass the Auditor, with up to 5 evidence articles per topic, one per outlet and one per title (0 duplicate titles over 240 topic-weeks).
- **GPU graph.** cosmos.gl temporal graph (13 weeks, 1,000 nodes, 120 fps on an M1 Pro) and sigma.js story view; question-driven lenses (decision, ring, bridge, momentum, novelty, community, tone, window) with per-week betweenness, sector crossing and edge state; a one-screen demo layout (top-10 rail, graph, chat dock) and a graph image for browsers without WebGL.

### Feat

- **deploy**: stage the briefs, evidence, sources and subtopic tables
- give the agents the evidence articles of a named topic
- **contracts**: mock topic_briefs_weekly from the first agent run
- let the editor read the pre-written brief first
- write a spanish brief per top-10 topic, checked by the auditor
- **deploy**: trace the live agents and accept feedback on cloud run
- **api**: record readers' thumbs up or down on a chat turn in langsmith
- show the decision line when asked or for a named topic
- show the decision line only when a decision is asked
- add a v2 usefulness judge that sees the tool data
- **deploy**: add the ordered final redeploy with a dry run
- **deploy**: carry the trust evidence in the static fallback
- **deploy**: write each top topic's evidence for the static site
- **bq**: pick up to five evidence articles per ranked topic-week
- **contracts**: add topic_briefs_weekly and topic_evidence_weekly (#28)
- **backtest**: report precision with bounds below the coverage rule
- append es/pt pageviews for the ws4 missing topics
- **crosssource**: fetch daily wikipedia pageviews
- **entity**: resolve topics against wikidata
- **web**: add brief evidence and trust cards
- **web**: keep named topics on the gpu story lens
- **web**: drive the graph lens from view_command color_by
- **web**: add split view, full-screen graph mode, and query-driven lenses
- **graph**: compute graph lens properties and re-export top-10 stories
- **contracts**: add the bridge, momentum and novelty graph lenses (#27)
- **contracts**: let the cartographer pick the graph lens per question (#26)
- **submission**: check the public site and api before the demo
- **contracts**: copy the topic_sources_weekly mock from the dev slice
- add the topic sources dev cut to the dev slice
- **bq**: measure source diversity and copy patterns per topic-week
- **contracts**: add topic_sources_weekly and the brief for the syndication guard
- give every routed specialist real data
- ask specialists for short plain-spanish notes
- give the agents numbers already formatted for executives
- answer out-of-scope questions honestly by code
- write the decision line in code and answer in plain spanish
- repeat eval runs and summarize each evaluator's spread
- **backtest**: use exact wikidata matches for the primary label
- **scores**: hold syndicated and one-outlet weeks out of the top 10
- **backtest**: add the secondary-label run and the coverage gate
- **api**: rate limit the public chat per client and per day
- **deploy**: package the api for cloud run with its lake tables
- **deploy**: serve a static export when the api is unreachable
- **deploy**: run the api on modal over a volume of lake tables
- **scores**: gate the top 10 to established or wikidata topics
- **backtest**: run the backtest and editor sheet on the topic universe
- **scores**: rank the taxonomy's topic universe with weekly subtopics
- **scores**: add the blind editor-test sheet and the models readme
- **backtest**: add the precision@10 and lead-time backtest
- **scores**: add the six scores, the window chip and the decision
- **web**: add cosmos.gl temporal graph and sigma story graph components
- **viz**: prune temporal edges top-k and export top-10 stories
- **graph**: export the temporal and story views and smoke-test them
- **contracts**: add the hand-filled 30x social posts sheet (#17)
- trace the agents in langsmith and evaluate them on a frozen set
- **contracts**: add the topic mocks and deny two news outlets
- add the topic dev cut of the ranked universe to the dev slice
- **bq**: add the weekly topic to subtopic table and export it
- **web**: pick the radar week and load a card's timeline and ring
- **labels**: generate 300-row blind gold sheet and label quality report
- **labels**: train calibrated student with active learning and jev cascade
- **labels**: implement multi-family teacher panel and label 4k sample
- **labels**: sample stratified articles and active-learning pool
- **api**: serve radar endpoints over duckdb and add contract-driven web ui
- **ingest**: export the gold tables to the lake, checked by contract
- **bq**: segment articles into rings and build ring-1 topic series
- **ingest**: run bq_sql scripts through a dry-run guard and the ledger
- **tgnn**: add edgebank and persistence link-prediction baselines
- **graph**: add weekly node metrics and the 1-hop context ring
- **contracts**: define the ranked universe and topic_subtopic_weekly (#8)
- add the multi-agent runtime with the media master and a code auditor
- **contracts**: add the wikipedia and graph-metric contracts
- add the real dev slice, the dev and full profiles and mocks from it
- **bq**: widen the s2 net to all ict news and large tech companies
- **contracts**: add the data, agent and api contracts

### Fix

- write the outlet count by code and flag a wrong one
- narrow the latam claim check and trace thousands separators
- drop echoed decision lines and audit unbacked latam claims
- **bq**: treat titles with a site suffix as the same evidence story
- **design**: refresh the no-webgl graph image
- **design**: collapse the idle chat dock to a pill
- **design**: give the graph its full width
- **design**: close the trust panel on escape
- **design**: raise the chat decision card contrast
- **design**: keep the graph clear of the chat dock
- **deploy**: stage the graph view metadata for get_graph_facts
- write how the graph is built by code, from the view and the ring
- **deploy**: keep the graph image across the static wipe
- read dates whole when the auditor traces numbers
- name the topic in the evidence block as the scores do
- answer outlet counts, list evidence by code and forbid stories
- read the cost ledger on the trust route only when asked about cost
- **bq**: keep one evidence article per normalized title
- let only percentages match a share in the auditor
- give the agents the real cost and ring thresholds to cite
- veto decisions no card shows and count entity false positives
- resolve topics named in a question only as whole words
- **deploy**: clear ARGS before the live check in the redeploy
- **deploy**: count one container start per cold start
- **graph**: classify edge state against the unpruned previous week
- **web**: show degree growth as a ratio
- **web**: type the measured reheat samples
- refuse only social-metric questions, not radar forecasts
- **deploy**: take the image packages from pyproject
- **scores**: floor the z-score sd so low-volume baselines do not inflate it
- make the agents work on the full lake
- **graph**: drop person neighbours from the 1-hop ring
- **api**: serve the radar on the full lake and guard persons and deny-listed orgs

### Perf

- **scores**: build topics in chunks so the full lake fits in 1.1 GB
- **tgnn**: stream weeks and count memory hits once per node
- **graph**: stream weeks so the full lake fits in memory

## v0.1.0 (2026-10-17)

### Highlights

- Repository scaffold: one directory per workstream (WS0–WS7), the shared `radar` core
  (lake paths, contract validation), the BigQuery scripts Q1–Q4 and S1–S10, and the master plan.
- Engineering practices: Conventional Commits enforced by commitizen, pre-commit hooks run
  identically in CI, a conventional PR title check, worktree-per-branch workflow and agent rules
  (`AGENTS.md`, imported by `CLAUDE.md` and `GEMINI.md`).
