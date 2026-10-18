# Radar de Señal Temprana: Master Plan (living document)

This is the living version of [`MASTER_PLAN.pdf`](MASTER_PLAN.pdf). The PDF is the plan as written
on Saturday, Oct 17, 2026, 18:35 UTC-5, and stays unchanged. This file is the project's real state
at the hackathon delivery: **v0.3.0, Sunday, Oct 18, 2026, 10:30 UTC-5**. Update it as the project
moves; it replaces the PDF as the source of truth.

Markers, as in the PDF:
- *(measured)*: we ran it.
- *(estimate)*: our projection.
- *(reported)*: stated by the orchestrator or a lane, not re-run for this file.

Plan items carry a status: **done**, **changed** (shipped differently, with the reason), **dropped**
or **not built** (with what is known), or **next**.

---

## 1. What it is

**The brief** (Reto 30X "Radar de contenido"): discover, reliably and without spending a fortune,
which AI topics and formats are taking off; explain why they work, whether a trend is starting or
already copied, and whether it fits LatAm executives and teams learning AI. It must use public
content only, no personal data, nothing against terms of service and nothing behind logins.
LinkedIn is never scraped.

**The radar's answer:** a weekly radar of AI topics, measured upstream of LinkedIn on open sources.
- **Two lists:**
  - **"Despegando"**: the emergence top 10, what is rising faster than expected before it saturates;
  - **"Lo más grande"**: the week's leaders by article volume.
- **Each topic** ships with:
  - its **why**, every reason marked measured or estimate;
  - its **stage**, **saturation** and **window** (days until it reaches Spanish and Portuguese,
    estimate);
  - the **emotional angle** (alerta, oportunidad, debate, giro, explicador) to tell it to executives;
  - a **Spanish brief** checked by an Auditor;
  - **evidence** (articles and outlets);
  - a separate **AI community** line.
- **Chat:** a multi-agent chat (the Media Master and its specialists) answers questions and moves
  the graph. Code computes every decision and writes the lines that matter; the model explains.
- **Trust:** a calibrated **trust** answer says how far to trust it: an early signal, not a
  guarantee.

## 2. Where we are: v0.3.0

| Area | State | Evidence |
|---|---|---|
| **GDELT loop** | **Done.** GDELT GKG 2.0 on BigQuery, Nov 1, 2025 to Oct 18, 2026. 1,623,903 AI articles in ring 1 *(measured)*. Every job is dry-run first, capped, and logged: 74 jobs, 389.72 GB billed, 0 USD within the 1 TiB monthly free tier *(measured; USD estimate)*. | [`status/WS1.md`](../../status/WS1.md), [`reports/bq_ledger.csv`](../../reports/bq_ledger.csv) |
| **AI lexicon** (the ranked unit) | **Changed.** v0.2 ranked GDELT-extracted organisations. GDELT does not extract AI-native ones: `org:openai` does not exist in the whole year, only variants such as "openai foundation" *(measured)*, so the W42 top 10 was Marsh McLennan, Kroger, Comcast. The unit is now a curated lexicon: **110 topics in 11 families**, including **opposition and critics** (18 entries with a critic stance), matched on title and URL *(measured)*. | [`contracts/ai_lexicon.yaml`](../../contracts/ai_lexicon.yaml), `bq_sql/s15`, `s16` |
| **Scores and window** | **Done, adapted.** Six scores became five plus the window: Emergence, Stage/Saturation, Audience fit (rule v1, *estimate*), Emotional charge, the framing angle, and the window chip. Outperformance (social engagement) and SHAP "why it worked" were **dropped**: no public social data without scraping. Ranked universe: AI topics with >= 20 articles that week; the gate holds by construction; the syndication guard is kept. **10/10 AI topics in the W41 and W42 top 10** *(measured)*. | `models/`, [`status/WS4.md`](../../status/WS4.md) |
| **Two lists** | **Done (new).** "Lo más grande" for W42: Nvidia 4,718 articles, OpenAI 2,691, Microsoft, Google, Anthropic, agents, ChatGPT. OpenAI ranks 58 in emergence *(measured)*. | `/api/leaders`, `agents.tools.get_leaders` |
| **Backtest** | **Done, honest.** v0.2 (GDELT orgs): primary label (es+pt Wikipedia pageviews) 29.2% [24.4–34.0] vs base 25.4%; beats persistence in the worst case, not raw-count growth. AI run: secondary label (es+pt GDELT growth) **25.6% [22.3–28.8] vs base 25.4%**; beats persistence (+13.3 points), not raw-count growth (−1.6). The primary label covers 27 of the 101 ranked topics and falls below the 90% coverage rule; bounded 27.7% vs 26.5% *(all measured)*. **The list is relevant; it is not yet better than chance on its labels.** | [`reports/backtest.md`](../../reports/backtest.md), [`reports/backtest_ai.md`](../../reports/backtest_ai.md) |
| **Classifier cascade** | **Done; human labels pending.** On 300 gold rows against the 3-model teacher panel: the GDELT ring-1 rule that feeds the radar has precision 0.75, recall 0.97. The trained student/cascade has precision 0.94, recall 0.95 but is **not wired** into the aggregates. Jev sees only doubtful cases (3.12%), 981 calls, 0.044 USD *(measured)*. The 300 human labels are pending. | [`reports/label_quality.md`](../../reports/label_quality.md), [`reports/jev_ledger.csv`](../../reports/jev_ledger.csv) |
| **Agents** | **Done.** Qwen3-30B on Nebius, LangSmith traces, a frozen eval per version (v1, v2, v3). Release eval v0.3 (`release-v0.3.0`, 28 questions x 3): **grounding 0.964 [0.93–1.00]**, usefulness_v2 0.619, routing and decisions 1.000 *(measured)*. | [`status/WS0-agents.md`](../../status/WS0-agents.md), [`agents/README.md`](../../agents/README.md) |
| **Code-written lines and Auditor** | **Done.** Code writes these lines; the model may not change them. The Auditor vetoes any number not returned by a tool, unconditional trust phrases, LatAm growth claims without es/pt coverage, wrong outlet counts, and brief coverage claims that contradict the data. | `agents/runtime.py`, `agents/briefs.py` |
| **Graph** | **Changed.** The plan's Graphistry Hub tier was **dropped**. A frozen cosmos.gl layout (GPU, the 13-week player) and a sigma.js story view cover it. There are 10 lenses: Radar, Historia, Puente, Momento, Novedad, Comunidades, Emoción, Ventana, **Familia** and **Postura** (promoters vs critics). The graph is co-mentions between AI topics, NPMI, Leiden. | [`status/WS3.md`](../../status/WS3.md) |
| **AI community sensor** | **Done (new), unvalidated.** Public feeds and APIs: HF papers and models; practitioner newsletters and podcasts; AI Engineer and YC (videos and Requests for Startups); The Batch; critic organisations. **24 sources registered, 23 with items, 3,636 items**, Jul 8 to Oct 18, 2026 *(measured)*. Kept **out of the backtest**: the feeds' history is short. Person-named sources and titles stay in the lake. | `crosssource/community.py`, `community_topic_weekly` |
| **Deploy** | **Done.** The API (FastAPI over DuckDB) runs on Google Cloud Run with the lake baked into the image, and the UI on Netlify with a static fallback. Revision 00011 is in AI mode, min-instances 1, `make demo-check ARGS=--chat` 8/8 *(reported, 10:30)*. | [`status/WS9.md`](../../status/WS9.md), [`deploy/README.md`](../../deploy/README.md) |
| **Engineering practices** | **Done.** Contracts first (JSON Schema, mocks from the real dev slice). One git worktree per lane, an orchestrator with executor briefs, and Conventional Commits with pre-commit and commitizen. The local gate (`make check && make test`) runs before CI, which is a single job. Data, secrets and person names never enter git. Every number is marked measured or estimate. Releases `v0.1.0` and `v0.2.0` are tagged; v0.3.0 is this delivery. | [`AGENTS.md`](../../AGENTS.md), [`docs/development/`](../development/) |

## 3. The PDF's scope, item by item

| PDF item (§2.3, §3, §10–12) | Status | Why |
|---|---|---|
| GDELT daily topic radar, 2 years | **Changed:** about 1 year (Nov 1, 2025 to Oct 18, 2026) | The backfill covers that span *(measured)*; it gives 43 evaluable backtest weeks |
| Six scores and the weekly top 10 | **Changed:** 4 scores plus angle and window; a second list by volume | Outperformance and SHAP need social data the brief forbids scraping |
| Two-tier graph: Graphistry Hub + sigma story | **Changed:** cosmos.gl + sigma.js | Graphistry was untested (about 3 h estimate) against the 10:00 freeze; the frozen GPU layout was ready |
| Backtest card and filter quality card | **Done** | The Confianza panel opens with a Spanish summary from the same parsers as the chat |
| Community sensor | **Done, broader** | Became the AI community sensor (24 sources) instead of voluntary LinkedIn shares |
| X counts cross-check | **Not built** | Paid per request and needed approval; no lane ran it |
| HN, arXiv, Bluesky in the upstream chain | **Changed:** HF papers and community feeds instead | The community sensor took HF papers and public feeds; HN, arXiv and Bluesky were not built |
| GCAM emotions (2 years) | **Not built** | No lane records a GCAM run; the emotional charge uses GKG tone, polarity and controversy |
| TGNN (gated stretch) | **Reduced** to a baseline table | Persistence and EdgeBank set the bar (MRR 0.0123 / 0.0050); no learned model was trained |
| Memgraph "ask the graph", Kepler.gl geo arcs | **Not built** (stretch) | The agents' graph tools answer graph questions |
| Modal for the API | **Changed:** Cloud Run | Modal's workspace started no container (no payment method) |
| Spanish adaptation brief per top-10 topic | **Done** | Auditor 20/20 on W41–W42, coverage claims checked against the brief's own counts |
| Evidence articles per topic | **Done** | Up to 5 per topic-week, outlet counts, no URLs reach the model |

## 4. Decisions log

| When (UTC-5) | Decision | Reason |
|---|---|---|
| Oct 17, 18:35 | BigQuery-first GDELT loop, every job dry-run and capped | A $0 BigQuery month is the low-cost proof; the ledger is the evidence |
| Oct 17, evening | Jev only for doubtful cases (p between 0.20 and 0.80, 3.12% of articles) | Cheapest place where a stronger model can help. Its gain is not proven: 9/10 vs 7/10, interval touching 0 |
| Oct 17, ~22:30 | The graph serves no persons; persons are dropped before the ring is cut | Privacy rule: persons never leave the lake |
| Oct 18, ~00:00 | API from Modal to Cloud Run | Modal could not start containers without a payment method; BigQuery's GCP project already had billing |
| Oct 18, night | No Graphistry cloud; cosmos.gl with a frozen layout | Graphistry was untested before the freeze; the GPU layout was ready and reproducible |
| Oct 18, 03:40 | Report the primary backtest with bounds below the 90% coverage rule | Honest reporting of a label that does not cover every slot |
| Oct 18, 07:00–07:45 | Code writes the decision, coverage, evidence, graph and trust lines; the Auditor vetoes the rest | The model invented thresholds, costs and trust claims; code-written facts removed them |
| Oct 18, ~09:00 | **The ranked unit moves from GDELT orgs to the AI lexicon** | The v0.2 top 10 was not AI: GDELT does not extract AI-native organisations |
| Oct 18, ~09:25 | A 20-article weekly floor for AI topics | Without it, topics with 3–10 articles reached the top 10 on noisy percentiles |
| Oct 18, ~10:00 | Add "Lo más grande" next to "Despegando" | Emergence hides the giants by design (OpenAI ranks 58) |
| Oct 18, ~09:00 (AI-radar plan) | The community sensor stays out of the backtest | Most feeds keep a short history: no fair label yet |

## 5. Known limits, plainly stated

- **No edge yet on the AI backtest.** It sits at the base rate on the secondary label (25.6% vs
  25.4%) and does not beat raw-count growth. The primary label is bounded below the coverage rule
  *(measured)*.
- **Thin primary label:** only 29 of the 110 lexicon entries have an es/pt Wikipedia title (27 of the
  101 ranked topics) *(measured)*.
- **Thin critics signal:** 45 critic items in 15 weeks; 3 in W42 *(measured)*.
- **Community questions score low** in the agent eval: usefulness_v2 0.500 [0.42–0.58] after two
  fixes *(measured)*. The counts say what builders publish, not what accelerators ask for.
- **Human gold labels pending:** filter quality is measured against a model panel, not people.
- **The trust answer and the Confianza panel** still read v0.2's `reports/backtest.md` under the AI
  source; they should read `reports/backtest_ai.md`.
- **Fixed at delivery (PR #79):** the static fallback image now shows the AI graph with the leaders labelled, and
  the AI graph uses the ring's co-mention floor (W42: 106 nodes, 147 edges, *measured*).
- **No piece-level answer yet:** the 30X social sheet (formats, hooks, authors) has 0 rows.

## 6. Next steps, before Tuesday's 30X demo

1. **Lexicon v0.4,** closing the external review's gaps:
   - AI in agriculture, inclusive finance and banking, logistics, government and SMEs;
   - indigenous and local languages, climate resilience.
   - Then merge or retire the generic entries.
2. **Daily refresh:** `make community-refresh` plus a scheduled Cloud Run job, so the lake and the
   image update without a manual redeploy.
3. **Trust on the AI run:** point the trust answer and panel at `reports/backtest_ai.md`.
4. **The 300 human labels,** to replace the model panel as the filter's reference.
5. **The 30X social sheet:** formats and hooks of 30X's own posts, to answer the brief's piece-level
   question.
6. **After the demo:** min-instances back to 0.

## 7. What it could be

- **GraphRAG** over the community items and the evidence, refreshed daily, so the agents cite fresh
  sources.
- **Lead-lag:** community sensor → news, as a validated early signal; backtest it once enough weeks
  exist.
- **A learned audience-fit model** from 30X's own post analytics.
- **Per-format recommendations** (carrusel, video corto, newsletter) learned from what 30X's
  audience engages with.
- **Spanish and Portuguese native sources,** beyond GDELT's coverage.
- **Alerts** when a topic crosses its window.
- **An editor workflow:** brief → draft → publish.
- **Multi-tenant** for other LatAm media teams.

## References

- [`MASTER_PLAN.pdf`](MASTER_PLAN.pdf): the original plan (Oct 17, 18:35).
- [`graph_viz_tgnn_gcam.pdf`](graph_viz_tgnn_gcam.pdf): the graph, TGNN and GCAM design.
- [`docs/designs/radar-build-plan.md`](../designs/radar-build-plan.md): the build design.
- [`docs/submission/`](../submission/): the v0.3 submission text and demo script.
