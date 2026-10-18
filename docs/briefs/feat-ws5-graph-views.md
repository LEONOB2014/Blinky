# BRIEF: G phase, the GPU temporal graph and the story view inside the UI, driven by the agents

Account: **Gemini (Antigravity)** · Branch: `feat/ws5-graph-views` · Worktree: `../radar-worktrees/feat-ws5-graph-views`
Written by the orchestrator, 2026-10-18 01:05 UTC-5. Read `AGENTS.md` (or `GEMINI.md`), then this file.

## Goal

The demo's closing moment, in the real UI: a live GPU-rendered temporal graph of about 90 days of AI
news that plays week by week, and a story view of one topic's neighbourhood, both opened by the agents
(the Cartographer's `view_command`) and by clicking a radar card. Business judges should understand
what they see without explanation: few, readable edges, the ranked topics highlighted, Spanish labels.

## Plan reference

`docs/designs/radar-build-plan.md` ("G graph", demo step 5: "the live GPU temporal graph sweep over 90
days, then the story view of the #1 topic"); `contracts/view_command.schema.json` (view `story` /
`temporal` / `cards`, `week`, `focus_topic`, `highlight`, `color_by`, `filter`, `caption_es`);
`status/WS3.md` section "WS3c" (measured sizes, fps, the pitfalls below).

## Inputs (real)

- `graph/export_views.py` writes `lake/views/temporal*.json` and `lake/views/story*.json` from the full
  lake (13 weeks, top nodes, pruned edges, weekly PageRank, decisions; no `per:` nodes).
- `graph/views/temporal.html` (cosmos.gl 3.5.1) and `graph/views/story.html` (sigma 3.0.3 +
  graphology 0.26.0): working reference implementations measured on this Mac (full export plays at
  107 fps; the live layout drops below 30 fps above ~200k unique links).
- `web/` (Vite + React + TS, bun): the agent-controlled view area already receives `view_command`s
  (`web/src/App.tsx`, `activeView`), and the cards panel exists.
- WS4 is rebuilding `topic_scores_weekly` tonight (eligibility gate): never hard-code topics; read the
  top 10 from the data.

## Known pitfalls (measured in WS3c; do not rediscover them)

1. cosmos.gl via jsDelivr `+esm` loads two luma.gl versions and throws. In `web/` install
   `@cosmos.gl/graph@3.5.1` from npm and pin every `@luma.gl/*` package to one `~9.3` version.
2. Blank canvas: use positions in space units, `rescalePositions: false`, call `fitView()` after
   `ready` and after the layout freezes; do not rely on `fitViewOnInit`.
3. sigma 4.0.3 fills the canvas with one node in Chrome on Metal: pin **sigma 3.0.3**.
4. The full graph is a hairball (140k edges a week among 2,000 nodes) and the 10 s live layout does
   not converge on 608k links.
5. Headless Chrome screenshots miss WebGL layers: use a headed window.

## Outputs

1. **Readable exports** (`graph/export_views.py`, extend it):
   - temporal: per week keep the top-k edges by NPMI per node (start at k = 3-5; measure edges/week),
     a **precomputed frozen layout** for the whole span (positions computed once offline, for example
     networkx/igraph force-directed on the union graph, or a GPU layout run once and saved), so the
     sweep never re-lays out; node label for the top ~30 nodes by PageRank and every ranked top-10
     topic; colour by decision.
   - story: one file per ranked top-10 topic of the latest scored week (plus any topic the agents name,
     generated on demand through an API call is out of scope: the 10 files are enough), Spanish labels.
   - written to `lake/views/` and copied by the build into `web/public/data/views/` (git-ignored).
2. **`web/` components:** `TemporalGraph` (cosmos.gl, play/pause, week slider, the week's top movers
   listed beside it) and `StoryGraph` (sigma 3, topic in the centre, ring by rank, edge width by
   co-mentions, the scores row beside it). Both open from:
   - a `view_command` (`view: "temporal" | "story"`, `focus_topic`, `week`, `highlight`, `caption_es`);
   - clicking a radar card (story of that topic).
   Keep the existing panels working; the graph lives in the agent-controlled view area.
3. **Measure** on this Mac, headed Chrome: first frame, fps while playing, week switch time, bundle
   size added. Screenshots under `lake/views/` (not committed). Results in `status/WS5.md` (G section).
4. Tell WS8 in `status/WS5.md` exactly which files the deploy must copy (`web/public/data/views/*`),
   so the next Cloud Run/Netlify redeploy ships them.

## Files you may touch

`web/**`, `graph/export_views.py`, `graph/README.md`, `graph/tests/test_export_views.py`,
`status/WS5.md`, the `graph` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

Agents (`agents/**`: if the Cartographer should emit a field it does not, write it in the status and
the orchestrator adds it), the API, contracts, deploy (WS8 redeploys), visual restyle beyond legibility.

## Acceptance

- `make check && make test` pass; `cd web && bun run build` passes; export tests on the dev slice check
  no `per:` nodes and the top-k pruning.
- A chat question such as "Muéstrame el grafo de la semana" opens the temporal view, and "¿Qué está
  pasando con Nvidia? Muéstramelo en el grafo" opens Nvidia's story view (or says it is not in the 10
  exported stories): screenshots of both.

## Paid or outward actions needing approval

None (local only; no uploads). `git push`, the PR and the deploy: the orchestrator and WS8.

## Deadlines (UTC-5)

Readable exports by **02:30**; both components working locally by **04:30**; measurements and
screenshots by **05:30** (the redeploy follows).

## If blocked

`BLOCKED: <reason>` at the top of `status/WS5.md`, then stop.

## Addendum (orchestrator, 01:15 UTC-5): this Mac is short of memory

The maintainer is copying a large folder to Google Drive: at 01:10 swap was 7.8 of 8 GB used, 7 GB
compressed, about 3.7 GB free (measured), and WS4's score rebuild (2.3 GB) has priority.

1. **One heavy job at a time.** Before any export or layout run, check `memory_pressure` (or
   `vm_stat`) and that no `models.build_scores` or `graph.build` process is running
   (`ps -axo rss,command | grep -E "build_scores|graph.build"`); if one is, work on the components and
   wait.
2. **Stay under ~1.5 GB peak** in Python: start from the "light" export (1,000 nodes, n >= 20), prune
   to top-k edges per node **before** computing the layout, compute the layout on the pruned union
   graph only (target <= 200k unique links), read `edges_weekly` one week at a time with
   `pl.scan_parquet` (never the whole 37.8M rows), and report the measured peak (`/usr/bin/time -l`).
3. In the browser, measure with only the radar tab open; if fps or memory suffer, ship the light export
   and say so.

## Addendum 2 (orchestrator, 02:10 UTC-5): query-driven lenses and a full-screen graph

The G phase is done and measured (120 fps sweep, 26-33 ms story renders). The maintainer wants the
graph to behave like Graphistry: the layout, colours, sizes and edge widths change with each question,
and the graph gets the screen it deserves. Everything below uses the installed `@cosmos.gl/graph@3.5.1`
(its API was checked: `setPointColors`, `setPointSizes`, `setLinkColors` (RGBA: alpha = intensity),
`setLinkWidths`, `setLinkStrength` (per link), `setPointClusters` + `setPointClusterStrength`,
`setPinnedPoints`, `focusedPointIndex`, `zoomToPointByIndex`, `fitViewByPointIndices`,
`linkColorInterpolateFromEndpoints`, `curvedLinks`, `simulationGravity` / `Repulsion` / `LinkSpring`
/ `LinkDistance` / `Friction` / `Decay`, `simulationAlpha`) and sigma 3 reducers.

### Must (in this order)

1. **Re-export first.** The stories were exported before WS4's syndication guard (01:36): re-run
   `RADAR_PROFILE=full uv run --extra graph python -m graph.export_views` so the 10 stories follow the
   current top 10. Keep the reference stories (Nvidia, Microsoft, Google, OpenAI, TECH_AUTOMATION).
2. **Layout: split view + full screen.**
   - Default: cards and chat on the left (~35%), the graph on the right (~65%), draggable divider.
   - Full-screen graph mode: a button and the `F` key; a floating chat box and a collapsible card
     drawer over the graph; `Esc` returns. When the Cartographer emits a `view_command`, the graph
     expands automatically (the user can collapse it).
   - A legend for the active lens and the `caption_es` on top. Spanish throughout.
3. **Lenses driven by `view_command`** (`color_by`, `highlight`, `focus_topic`, `filter`, `week`): one
   function per lens that sets colours, sizes, link colours/widths/strengths and focus, then briefly
   re-runs the simulation from the current positions (reheat with `simulationAlpha`, then freeze), so
   the graph visibly rearranges per question, like Graphistry's play:
   - **Radar** (default, "¿qué sube?"): size = weekly PageRank (or emergence), colour = decision, a
     halo on the top 10; edge width = log(co-mentions), edge alpha = NPMI; the top 10's links get a
     higher `setLinkStrength`, the rest fade.
   - **Story** ("¿qué pasa con X?"): pin X at the centre, its links strong and bright, neighbours
     coloured by ring (IA / IT / IA × dominio), everything else near-transparent; `zoomToPointByIndex`.
     When X is not in the temporal graph, open the sigma story view as today.
   - **Temporal** ("muéstrame la semana / los 90 días"): today's frozen sweep, no re-layout.
4. **Edges that speak:** width from co-mentions, intensity (alpha) from NPMI, gradient from endpoint
   colours, curved links if it stays above 60 fps.
5. Keep the measured limit: live re-layout only on the pruned graph (< 50k links); measure fps during
   a re-layout and the time to settle.

### Nice (only if the must list is done and measured)

- **Emotion** lens: colour = tone (diverging blue-red), size = emotional charge.
- **Window** lens: colour = window chip state, clusters by state with `setPointClusters`.
- Animated transitions between lenses (interpolate colours/sizes over ~400 ms).

### Contract note

If a lens needs a value that `view_command` cannot express, use the existing fields first (`color_by`
values, merged in PR #26: `decision`, `segment` (the ring), `tone`, `window`; merge origin/develop to get them); if that is not enough, write it in the status and the
orchestrator changes the contract. The orchestrator will make the Cartographer emit `color_by` per
question type.

### Acceptance

`make check && make test` and `bun run build` pass; screenshots (headed Chrome) of: split view, full
screen, Radar lens, Story lens for the #1 topic, one chat question that rearranges the graph; fps
during re-layout and time to settle, in `status/WS5.md`.

Deadline: must list by **05:00**; nice items by **06:00** or dropped.

## Addendum 3 (orchestrator, 02:25 UTC-5): graph properties that make the lenses speak

The lenses need properties to encode. `node_metrics_weekly` already gives per node and week:
`deg_w`, `deg_growth`, `new_nbr_rate`, `pagerank`, `pr_rank_delta`, `kcore`, `is_hub`
(`community_id` is unstable across weeks: use communities **within one week only**). But the temporal
export's edges carry only `source`, `target`, `week`: no strength. Compute the rest in
`graph/export_views.py` on the pruned graph (1,000 nodes, ~3.5k edges a week: igraph does all of this
in well under a second per week), ship it in `temporal.json` and the story JSONs, and document every
field in `graph/README.md` with its formula.

### Must

**Edges** (per week):
- `n` (co-mentions) and `npmi` from `edges_weekly`: width = log(n), alpha = NPMI.
- `edge_state`: `new` (absent the week before), `persisting`, `growing` (n up >= 50% vs last week),
  `fading` (down >= 50%). Novelty lens: new edges bright, persisting muted, fading dashed or dim.
- `n_growth` = log((n + 1) / (n_prev + 1)).

**Nodes** (per week):
- `betweenness` (normalised, igraph, on the week's pruned graph, weights as distances = 1 / npmi):
  the "bridge" lens's size.
- `cross_ring_share`: share of the node's edge weight going to neighbours of another ring (AI / IT /
  AI x domain); take the ring from `topic_daily.segment` / `article_segment` aggregates already in the
  lake, or from the node's prefix where that is all there is; say which. The "bridge" lens's colour:
  the product's whole point is AI crossing into other domains.
- `momentum`: `pr_rank_delta` and `deg_growth` already exist; combine into one documented score (for
  example the mean of their within-week percentiles). The "momentum" lens's size and a glow for the
  top decile.
- `community_week`: Leiden on the week's pruned graph (seed fixed, within-week only), for the
  `community` lens; never compare ids across weeks.
- `importance`: one size default for every lens, the within-week percentile of PageRank, so sizes
  stay comparable between lenses.

### Nice

- `kcore` as a depth cue (outer shell more transparent).
- Brokerage (Burt's constraint) as an alternative bridge measure, if betweenness looks noisy.
- Per-node tooltip: label, decision, the 3 strongest neighbours, betweenness and momentum percentiles,
  edge state counts.

### Lenses using them (extends Addendum 2; values merged in PRs #26 and #27, merge origin/develop)

| `color_by` | Node colour | Node size | Edges |
|---|---|---|---|
| `decision` (default) | decision | importance | width log(n), alpha NPMI |
| `segment` (story) | ring | importance | the focus topic's edges strong |
| `bridge` | cross_ring_share (sequential) | betweenness | cross-ring edges highlighted |
| `momentum` | momentum (diverging) | importance, glow top decile | growing edges bright |
| `novelty` | new_nbr_rate | importance | edge_state (new bright, fading dim) |
| `community` | community_week | importance | intra-community edges stronger in the layout |
| `tone` / `window` | as in Addendum 2 | importance | as `decision` |

Keep every measure per week, persons never included, and report their distributions (median, p90) in
`status/WS5.md`. Deadline: edge properties and betweenness / cross-ring / momentum by **04:00**,
together with Addendum 2's must list by **05:00**.

## Addendum 4 (orchestrator, 02:40 UTC-5): the Brief, Evidence and Trust cards (after Addendum 2-3's must list)

The demo's steps 3 and 4 need three cards the UI does not show yet. Start them only after Addendum 2's
must list and Addendum 3's properties are committed and measured (05:00); drop them if time runs out,
and say so.

1. **Brief card** on each top-10 card (expandable): `headline_es`, `what_happened_es`, `why_latam_es`,
   `angle_es`, `hook_es`, `format_es` from `topic_briefs_weekly` (contract merged, PR #28; lake file from
   claude-cacho by 04:30). A small "verificado por el Auditor" badge when `auditor_ok`, otherwise "revisar".
   Read it from the static export (`web/public/data/briefs/<week>.json`; add that file to
   `deploy/export_static.py` if WS1d/WS9 did not) or an API path if one exists; never invent text.
2. **Evidence card**: up to 5 articles per topic (title linked to the URL, outlet, date, language) from
   `web/public/data/evidence/topics/<slug>.json` (claude-work, by 04:30). Titles open in a new tab.
3. **Trust panel** (one view, reachable from the header): the backtest summary, label quality (filter
   precision/recall with intervals), BigQuery and Jev ledger totals, from `web/public/data/evidence/*.json`
   (claude-work's `deploy/evidence.py`, merged later tonight). Every number shows its denominator and
   "medido"/"estimado"; nothing is retyped by hand.

Acceptance: `bun run build` passes; screenshots of the three cards; if a data file is missing, the card
says "pendiente" instead of failing.

## Correction (orchestrator, 02:35 UTC-5): how to reheat the layout in cosmos.gl 3.5.1

Addendum 2 named `simulationAlpha` as a config field: it is not one (the current build fails with
TS2353 at `TemporalGraph.tsx:688`). In the installed `index.d.ts`: reheat with `graph.start(alpha)`
(for example 0.3 for a gentle rearrangement), or apply new colours/sizes/strengths and call
`graph.render(simulationAlpha, transitionDuration)`, which also animates the transition (for example
`render(0.3, 400)`). Stop with `graph.pause()` once settled (`graph.progress` / `isSimulationRunning`).
Keep `bun run build` passing before each commit.

## Addendum 5 (orchestrator, 03:10 UTC-5): fix list after Grok's review — for Grok

Grok's read-only review (`status/WS5-review.md`) found that the lenses do not follow a question and the
layout never rearranges; the orchestrator found two data errors. Fix in this order, `bun run build`
passing before each commit, one commit per item. Measure only what actually happens.

1. **The lens follows the question.** Pass `view_command.color_by` (and `focus_topic`, `highlight`) from
   `App.tsx` into `TemporalGraph` / `StoryGraph`; the chip, the legend and the graph must agree. A pill
   click and a chat answer go through the same path.
2. **Real re-layout.** Set the lens's link strengths (`setLinkStrength`: the focus or highlighted topics'
   links high, the rest low) and pins (`setPinnedPoints` for the focus topic), then `graph.start(0.3)`;
   let it run until `graph.progress` stops changing or a cap (e.g. 2.5 s), then `graph.pause()`. Never
   `render(0, 0)` after a reheat. Measure the real settle time and fps during it, and check that two
   lenses give different positions.
3. **Named topics stay in the GPU graph.** When the focus topic is among the 1,000 nodes, use the
   temporal graph's Story lens (pin, zoom with `zoomToPointByIndex`, neighbours bright, rest dimmed);
   open the sigma story only for topics outside the graph, and say so in the caption.
4. **Movers panel:** show growth as a real ratio or percent (`exp(log) - 1`), not a log printed as a
   percent.
5. **Edge state against the full previous week** (orchestrator's finding): `graph/export_views.py` builds
   the previous week from the top-k-pruned `kept` set, so 2,752 of 3,463 W42 edges are labelled `new`.
   Compare against the previous week's `edges_weekly` with the same `n` / NPMI thresholds but no top-k
   pruning; re-export and report the new state counts and `n_growth` median.
6. **Name the ring honestly** (orchestrator's finding): `node_ring_and_domain` is a name-list rule (every
   node comes from AI articles), so label it in the legend "Sector (regla por nombre): IA / TI / otros
   sectores", document the rule and its lists in `graph/README.md`, and call `cross_ring_share`
   "cruce de sector (regla)".
7. **Correct `status/WS5.md`:** replace the earlier fps / settle numbers and the categorical counts with
   values re-measured from the fixed build and recomputed from the shipped `temporal.json`; mark what was
   wrong before.
8. **Then Addendum 4** (Brief, Evidence, Trust cards) with a "pendiente" state when a data file is
   missing. If it cannot be done by 05:30, record it as dropped in the status.

Deadlines: items 1-4 by **04:30**, 5-7 by **04:45**, item 8 by **05:30** or dropped. Screenshots (headed
Chrome) for 1-3 into `lake/views/`. Commit locally; the orchestrator pushes.
