# WS5 status

Owner: Gemini (Antigravity) for WS5; WS5b (full lake) by Claude #4 (claude-cacho) · Directories: `api/, web/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 03:51 UTC-5 · Branch: `feat/ws5-graph-views` · Addendum 5 items 1–8 committed locally. The orchestrator pushes. Graph counts below were recomputed from `lake/views/temporal.json` (3,794,275 bytes). The 02:55 figures marked **wrong** are not in that file.

## Addendum 4 — Brief, Evidence, Trust (2026-10-18 03:51 UTC-5)

The three cards read static JSON. A missing file, a non-JSON body (the preview server returns `index.html` with HTTP 200), or `"available": false` shows **pendiente** and does not throw. No brief text is written in the UI.

`RADAR_PROFILE=full uv run --extra api python deploy/export_static.py --cards` writes the files under git-ignored `web/public/data/` and does not delete `views/`. This run *(measured)*: briefs 32,008 bytes (`2026-W41.json` and `2026-W42.json`, 10 rows each, `auditor_ok` true on 20/20), evidence topics 627,291 bytes (212 files), trust 26,323 bytes. `org:marsh mclennan` in W42 has 5 articles. `org:nvidia` is not in the W42 brief rows and has no `evidence/topics/org_nvidia.json`.

Headed Chrome against `bun run preview` (`http://127.0.0.1:4173`, build `index-nBFIs8--.js` 301.68 kB): the Marsh brief headline matched the JSON file, the badge said “verificado por el Auditor”, and the view stayed on cards. Its evidence list had 5 links, each `target=_blank` and `http`. Nvidia’s brief said “Brief pendiente briefs/2026-W42.json” and its evidence said “Evidencia pendiente evidence/topics/org_nvidia.json”. The header button opened Confianza: BigQuery 379.54 GB over 65 jobs (379,543,617,536 bytes, medido, `reports/bq_ledger.csv`); Jev 0.044284 USD over 981 calls, median latency 377 ms (medido, `reports/jev_ledger.csv`). The backtest block cites `reports/backtest.md` and was not pendiente. Screenshot: `lake/views/ui_trust_cards.png` (not committed).

## Addendum 5 — corrected measurements (2026-10-18 03:40 UTC-5)

Source file: `lake/views/temporal.json`, 3,794,275 bytes, 1,000 nodes (0 `per:`), 40 with `show_label`, 44,005 edges, 13 weeks `2026-W30`..`2026-W42`. Edges per week: 3,337, 3,415, 3,398, 3,357, 3,395, 3,433, 3,339, 3,238, 3,409, 3,392, 3,373, 3,456, 3,463. Last week `2026-W42` has 3,463 edges. Node types: 793 `thm`, 158 `org`, 49 `loc` *(measured)*.

Re-export (`RADAR_PROFILE=full`, `/usr/bin/time -l`, one job): temporal export 4.75 s, wall 5.50 s, peak RSS 1,559,805,952 bytes (1.45 GiB), 0 swaps *(measured)*. The 02:55 line “3.74 MB, 4.90 s, peak 1,201.26 MiB” was the previous export **(wrong for this file)**.

### Reheat on the fixed build (headed Chrome, 1,000 nodes, 3,463 W42 links)

`graph.start(0.3)` runs with `enableSimulation` on. The loop stops when `graph.progress` is unchanged for 3 ticks of 100 ms, the simulation stops, or 2,500 ms, then `graph.pause()`. It does not call `render(0, 0)` after the reheat.

| Lens | settle_time_ms | fps_relayout | sim_progress | layout_moved |
|---|---|---|---|---|
| bridge | 2,508.1 | 106.5 | 0.069 | 468.3 |
| momentum | 2,501.4 | 120.3 | 0.071 | 31.5 |

*(measured)*, n=1 run each. Both hit the 2,500 ms cap because progress was still about 0.07. `layout_moved` is the mean absolute move of 6 sampled points. `layout_delta` between the bridge sample and the momentum sample was 31.5, so the two lenses did not land on the same positions. Moving the week slider from W42 to W41 did not increment `reheat_count`.

**Wrong before:** the 02:55 status said `fps_relayout` 120.6–120.8 and `settle_time_ms` 380.7–381.3. That settle was a 380 ms timer. `render(0, 0)` had set the simulation alpha to 0, so the layout did not run. `fps_playing` 120.2 and the week-switch times in the tables below were not re-measured on this build; do not quote them as the reheat.

Screenshots (git-ignored `lake/views/`, headed Chrome, 03:27 UTC-5): `ui_lens_momentum.png` (527 kB), `ui_story_nvidia_gpu.png` (1.3 MB), `ui_story_openai_sigma.png` (497 kB).

### Categorical counts, `2026-W42`, recomputed from the shipped file

`edge_state` compares each pruned edge with the previous week’s edges at the same `n` / NPMI thresholds **before** top-k pruning *(measured, n=3,463)*:

| state | count | share |
|---|---|---|
| new | 1,523 | 1,523/3,463 |
| persisting | 1,298 | 1,298/3,463 |
| growing | 485 | 485/3,463 |
| fading | 157 | 157/3,463 |

**Wrong before:** the 02:55 status said new 2,752 / growing 422 / persisting 243 / fading 46. The file before this re-export (same pruned edge list, previous week also pruned) was new 2,228 / persisting 915 / growing 218 / fading 102. Neither pair is the current file.

`n_growth` = ln((n+1)/(n_prev+1)), n=3,463: median 0.885038, p90 4.70048, min −3.064725, max 6.818924 *(measured)*. **Wrong before:** median 3.4657, p90 5.1059. That median matched the pre-fix file; it is not this file.

`cross_ring` (cruce de sector, regla por nombre): 243/3,463 edges (7.0%) *(measured)*. **Wrong before:** 468 edges, 13.5%.

Sectors are the name-list rule in `graph/README.md`, not `topic_daily.segment` *(measured, n=1,000)*: `ai` 29, `it` 29, `ai_domain` 942. **Wrong before:** `ai` 90, `it` 43, `ai_domain` 867, described as taxonomy segments.

`community_week` in W42: 22 distinct ids among 930 nodes that have one *(measured)*. **Wrong before:** 20 communities.

Decisions in W42 (n=1,000): null 911, `no_es_tema_caliente` 43, `esperar` 38, `preparar` 8, `publicar_ahora` 0 *(measured)*. Window state: null 911, `sin_estimacion` 41, `dias_restantes` 31, `en_cualquier_momento` 15, `ya_en_espanol` 2 *(measured)*. Tone (n=944 non-null): min −5.309661, p50 −0.052378, max 5.838564; bins at ±1: neu 566, neg 223, pos 155 *(measured)*.

Distributions in `_meta.property_distributions_latest_week`, checked against the arrays *(measured)*:

| property | n | median | p90 | max in the arrays |
|---|---|---|---|---|
| edge_n | 3,463 | 80 | 761 | 15,331 |
| edge_npmi | 3,463 | 0.485244 | 0.83239 | 1.0 |
| node_betweenness | 930 | 0.001823 | 0.01004 | 0.111055 |
| node_cross_ring_share | 930 | 0 | 0.207229 | 1.0 |
| node_momentum | 968 | 0.497415 | 0.896587 | 0.998966 |
| node_new_nbr_rate | 979 | 0.207865 | 0.322399 | 1.0 |
| node_importance | 979 | 0.5 | 0.900818 | 1.0 |

The 02:55 medians for `edge_n`, `edge_npmi`, betweenness, cross_ring_share, momentum, and new_nbr_rate match this file. The 02:55 maxima (edge_n 7,133, npmi 0.9982, betweenness 0.05432, cross_ring_share 0.7778) do **not**. All-weeks `edge_state` (n=44,005): persisting 17,567, new 18,183, growing 5,850, fading 2,405 *(measured)*.

### Stories the current index names (WS8)

`stories_index.json` (5,264 bytes): `n_top10` 10, `n_total_stories` 15, default `org:marsh mclennan`, week `2026-W42`. `story.json` is that default (45,805 bytes, 21 nodes, 162 edges = 20 ring spokes + 142 among). **Wrong before:** the WS8 list still named the previous top 10 (`euronext`, `adani enterprises`, `ministry of science`, `kioxia holdings`, `sterling`, `yahoo`) and called `story.json` 30.3 kB.

Current top 10:

| rank | topic_id | decision | file |
|---|---|---|---|
| 1 | `org:marsh mclennan` | preparar | `story_org_marsh_mclennan.json` (45,805 B) |
| 2 | `org:rocket lab` | esperar | `story_org_rocket_lab.json` (34,520 B) |
| 3 | `org:national stock exchange` | preparar | `story_org_national_stock_exchange.json` (48,115 B) |
| 4 | `org:university college london` | preparar | `story_org_university_college_london.json` (44,226 B) |
| 5 | `org:citigroup` | esperar | `story_org_citigroup.json` (27,651 B) |
| 6 | `org:sandisk` | esperar | `story_org_sandisk.json` (28,471 B) |
| 7 | `org:comcast` | preparar | `story_org_comcast.json` (26,467 B) |
| 8 | `org:kroger` | preparar | `story_org_kroger.json` (44,166 B) |
| 9 | `org:founders fund` | esperar | `story_org_founders_fund.json` (53,021 B) |
| 10 | `org:sb energy` | esperar | `story_org_sb_energy.json` (33,824 B) |

References in the same index, not in the top 10: `org:nvidia` rank 150, `no_es_tema_caliente`, 21 nodes / 149 edges; `org:microsoft` rank 133, `no_es_tema_caliente`; `org:google` rank 203, `no_es_tema_caliente`; `org:openai group` rank null, decision null, 6 nodes / 15 edges (not one of the 1,000 temporal nodes); `thm:TECH_AUTOMATION` rank 73, `esperar`. **Wrong before:** Nvidia was quoted as rank 177.

`web/package.json` `copy-views` copies `lake/views/*.json` into `web/public/data/views` and does not delete. These six files are still in `lake/views/` and `web/public/data/views/` and are **not** in `stories_index.json`: `story_org_euronext.json`, `story_org_adani_enterprises.json`, `story_org_ministry_of_science.json`, `story_org_kioxia_holdings.json`, `story_org_sterling.json`, `story_org_yahoo.json`. WS8 should not ship them as the current top 10.

Latest `cd web && bun run build` (item 6, vite 6.4.4, 1.57 s): `index-DtEE30iC.js` 291.50 kB (90.16 kB gzip), `index-rt_7rvKX.css` 14.08 kB (3.55 kB gzip). The 02:55 bundle line (`index` 286.04 kB) was an earlier build **(wrong for the current `web/dist`)**.

## Addenda 2 & 3 — Query-driven Lenses, Graph Properties, Split View & Fullscreen (2026-10-18 02:55 UTC-5)

Property counts, the reheat settle, and the WS8 file list in this older write-up were replaced by the correction above. Where a number below disagrees with that section, the correction is the one to quote.

### 1. Graph properties that make the lenses speak (`graph/export_views.py`, `lake/views/temporal.json`)

All Addendum 3 node and edge properties are on the pruned graph. The export size, runtime, and the W42 counts that used to sit in this paragraph were wrong for the current file; use the Addendum 5 correction (3,794,275 bytes, peak RSS 1,559,805,952 bytes, W42 `edge_state` 1,523 / 1,298 / 485 / 157).

- **Edge properties (computed per week, `edges_weekly` scanned week-by-week)**:
  - `n` (co-mentions) and `npmi`: width = `0.5 + 2.5 * log(n)`, intensity = NPMI alpha.
  - `edge_state`: `new` (absent previous week), `growing` (n up >= 50%), `persisting`, `fading` (down >= 50%).
  - `n_growth`: `log((n + 1) / (n_prev + 1))`.
  - `cross_ring`: boolean indicating if endpoints belong to different rings.
  - **Distribution in `2026-W42`:** the figures that were printed here (n_growth median 3.4657, edge_state 2,752/422/243/46, cross_ring 468 = 13.5%, maxima 7,133 / 0.9982) were **wrong**. Recomputed values are in the Addendum 5 correction. `edge_n` median 80 and p90 761, and `edge_npmi` median 0.485244 and p90 0.83239, still match the current file (n=3,463).

- **Node properties (computed per week)**:
  - `ring` and `domain`: name-list sector, not `topic_daily.segment`. The count printed here (`ai` 90, `it` 43, `ai_domain` 867) was **wrong**. The current file has `ai` 29, `it` 29, `ai_domain` 942 (n=1,000).
  - `importance`: within-week percentile of PageRank (`[0, 1]`), default node size across lenses.
  - `betweenness`: igraph Freeman normalized $B(v) / ((V-1)(V-2)/2)$ with edge distance weights $1 / \text{npmi}$:
    - median `0.001823`, p90 `0.01004` still match the current file (n=930). The max `0.05432` printed here was **wrong**; the current arrays max at 0.111055.
  - `cross_ring_share` (cruce de sector, regla por nombre):
    - median `0`, p90 `0.207229` still match (n=930). The max `0.7778` printed here was **wrong**; the current arrays max at 1.0.
  - `momentum`: mean of within-week percentiles of `pr_rank_delta` and `deg_growth`:
    - median `0.4974`, p90 `0.8966`, top decile >= `0.8966` glowing halo *(measured)*.
  - `community_week`: within-week Leiden clustering (seed 42). The “20 communities” figure was **wrong**; W42 has 22 ids among 930 nodes.
  - `new_nbr_rate`: median `0.2079`, p90 `0.3224` *(measured)*.

### 2. Split view & Full-screen graph mode (`App.tsx`, `App.css`)

- **Draggable split layout**:
  - Cards and Maestro de Medios chat on the left (`~35%` default, draggable between `20%` and `60%`).
  - Graph on the right (`~65%` default). Draggable divider with mouse/touch support.
- **Full-screen graph mode (`view-panel-fullscreen`)**:
  - Toggled with dedicated button or keyboard shortcut `F` / `f`; `Esc` returns.
  - Auto-expands to full screen whenever the Cartographer / chat emits a `view_command` for `temporal` or `story`.
  - **Floating chat box** over the graph with question input, quick pills, and response stream.
  - **Collapsible Top 10 card drawer** sliding out over the graph to inspect decision cards without leaving fullscreen.
  - Active lens legend and `caption_es` displayed on top in Spanish.

### 3. Query-driven lenses (`TemporalGraph.tsx` & `StoryGraph.tsx`)

- **8 reactive lenses**:
  - `decision` (Radar default): node color by decision, halo on top 10, size by importance, edge width log(n), alpha NPMI.
  - `segment` (Story): node color by ring (`ai` fuchsia, `it` sky blue, `ai_domain` orange), focus topic pinned and centered, links highlighted.
  - `bridge`: node color by `cross_ring_share`, size by betweenness centrality, gold cross-ring links highlighted.
  - `momentum`: node color by momentum, glowing halo on top decile, growing edges highlighted.
  - `novelty`: node color by `new_nbr_rate`, new edges bright green, fading edges muted.
  - `community`: node color by within-week Leiden community.
  - `tone`: diverging blue-red by tone.
  - `window`: node color by window state, GPU clustering with `setPointClusters` + `setPointClusterStrength`.
- **Reheat re-layout (Addendum 5 item 2)**:
  - `setLinkStrength`, `setPinnedPoints` for the focus, `enableSimulation`, then `graph.start(0.3)`. The ~380 ms settle printed here was **wrong** (a timer; `render(0, 0)` had stopped the simulation). Measured settle on the fixed build is 2,508.1 ms (bridge) and 2,501.4 ms (momentum), both at the 2,500 ms cap. See the correction.

### 4. Headed Chrome measurements (Apple M1 Pro Metal GPU, full profile)

| View / Action | Metric | Measured value | Notes / Denominator |
|---|---|---|---|
| `TemporalGraph` (GPU) | Renderer | `ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro)` | *(measured)* headed Chrome (`1440×1020`, DPR 2) |
| `TemporalGraph` | `t_fetch_ms` / `t_parse_ms` | `12.9 ms` / `25.3 ms` | earlier file, not re-measured; current file is 3,794,275 bytes |
| `TemporalGraph` | First frame (`t_first_frame_ms`) | `177.1 ms` | *(measured)* 1,000 nodes, 3,463 edges in W42 |
| `TemporalGraph` | Re-layout FPS (`fps_relayout`) | 106.5 (bridge), 120.3 (momentum) | *(measured)* fixed build; the 120.6–120.8 row was **wrong** |
| `TemporalGraph` | Settle time (`settle_time_ms`) | 2,508.1 (bridge), 2,501.4 (momentum) | *(measured)* cap 2,500 ms hit; 380.7–381.3 ms was **wrong** |
| `TemporalGraph` | Playing FPS (`fps_playing`) | `120.2 fps` | *(measured)* 13-week playback sweep |
| `TemporalGraph` | Week switch time (`week_switch_ms`) | median `2.6 ms` (2.2 .. 4.3 ms) | *(measured)* week slider steps |
| Story View #1 | Load time (`org:marsh mclennan`) | `31.2 ms` Sigma render | *(measured)* 21 nodes, 162 edges, ring colors |
| Fullscreen toggle | Switch time | `< 16 ms` (immediate layout reflow) | *(measured)* WebGL context preserved |

- **Screenshots (saved in git-ignored `lake/views/`)**:
  - `lake/views/ui_split_view.png` (`1.03 MB`): Split view with cards/chat on left (~35%) and GPU graph on right (~65%), draggable divider.
  - `lake/views/ui_lens_radar.png` (`1.03 MB`): Radar lens with decision colors, importance sizing, dynamic legend, reheat settle.
  - `lake/views/ui_fullscreen.png` (`821 kB`): Full-screen graph mode with top bar controls, legend, and floating chat overlay.
  - `lake/views/ui_fullscreen_drawer.png` (`728 kB`): Collapsible Top 10 card drawer open over full-screen graph.
  - `lake/views/ui_story_top1.png` (`1.03 MB`): Story ring for Top #1 `org:marsh mclennan`, rings colored by AI/IT/domain with gold cross-ring chords.
  - `lake/views/ui_chat_rearrange.png` (`902 kB`): Chat question *"¿Qué tema de IA sube esta semana y por qué? Muéstramelo en el grafo"* rearranging graph into Momentum lens.

- **Build size (`bun run build`, Vite 6.4.4)**:
  - `dist/assets/index-*.js`: `286.04 kB` (`88.22 kB` gzip) *(measured)*
  - `dist/assets/index-*.css`: `14.08 kB` (`3.55 kB` gzip) *(measured)*
  - `dist/assets/sigma-vendor-CxsImN5y.js`: `159.49 kB` (`37.94 kB` gzip) *(measured)*
  - `dist/assets/cosmos-vendor-DOVCUqqA.js`: `745.56 kB` (`195.32 kB` gzip) *(measured)*
  - Build time: `1.83 s` *(measured)*.

---

## G — Graph views in `web/` (`feat/ws5-graph-views`)

### 1. Readable exports (`graph/export_views.py`)

- **Temporal export (`lake/views/temporal.json`)**:
  - Scans `edges_weekly` one week at a time (`min_n=20`, `npmi > 0.1`, `max_nodes=1,000`, `top_k=5` edges by NPMI per node per week) instead of dumping all 296,657 unpruned edges.
  - Precomputes a deterministic frozen 2D layout (`_precompute_layout`, `igraph` Fruchterman-Reingold on the pruned union graph, median-centered with p90 radial compression, scaled to `[448, 3648]` in `spaceSize=4096`), Spanish labels (`label_es`) for `thm:`/`loc:`/`org:` ids, `show_label=true` on the top 30 PageRank nodes plus ranked top-10 topics. The “38 labeled” count was **wrong**; `_meta.n_labeled_nodes` and a count of `show_label` are both 40 in the current file. `_meta.top_movers_per_week` is still written.
  - **Full-profile measurements:** the numbers that used to be in this list (38 labels, 44,610 edges, 3,518 in W42, 1,671,019 bytes, 2.54 s) were an earlier export and are **wrong** for the current file. Current file: 1,000 nodes, 40 labels, 44,005 edges, 3,463 in W42, 3,794,275 bytes. See the Addendum 5 correction.
- **Story exports (`lake/views/story*.json`, `lake/views/stories_index.json`)**:
  - The top-10 names and the 30,345-byte `story.json` size printed here were **wrong** (that list ended at `org:yahoo`). The current index’s top 10 ends at `org:sb energy`. `story.json` is 45,805 bytes, still 21 nodes and 162 edges. Peak RSS of the re-export is 1,559,805,952 bytes. See the correction for the file list. The 0.20 s story-only runtime was not re-measured on this run (the whole export wall time was 5.50 s).

### 2. `web/` components (`TemporalGraph.tsx` & `StoryGraph.tsx`)

- **`TemporalGraph.tsx` (`@cosmos.gl/graph` `3.5.1` + pinned `@luma.gl/{constants,core,engine,shadertools,webgl}@9.3.6`)**:
  - Uses precomputed frozen positions (`enableSimulation: false`, `rescalePositions: false`, `fitViewOnInit: false`, `fitView(0, 0.08, false)` after `await graph.ready`) and normalized `[0, 1]` RGBA float buffers.
  - Play/pause (`▶ Reproducir 13 semanas`), week range slider (`2026-W30 .. 2026-W42`), node color by `decision` (`publicar_ahora` green, `preparar` sky blue, `esperar` amber, `deg_growth >= +40%` teal, context slate), greedy bounding-box collision-avoided Spanish labels overlay (`spaceToScreenPosition`). The “12 labels out of 38 eligible” count used the old label total and was **not** re-measured; the current file has 40 `show_label` nodes. The movers panel reads `_meta.top_movers_per_week[w]` and shows `deg_growth` as `exp(log) − 1`.
- **`StoryGraph.tsx` (`sigma` `3.0.3` + `graphology` `0.26.0`)**:
  - Loads `/data/views/stories_index.json` and the matching `/data/views/story_<slug>.json`.
  - Places the focal topic in the center (`★ label_es`) and its 20 1-hop neighbors on two staggered concentric rings by rank (`1..10` inner, `11..20` outer), spoke edge width proportional to co-mentions `n`, top-10 strongest intra-ring chords, Spanish labels, scores row above the canvas, and ranked 1-hop neighbors sidebar.
  - A named topic that is one of the 1,000 temporal nodes stays on the GPU story lens. `org:nvidia` is in that set (rank 150, `no_es_tema_caliente`). The “rank #177, open sigma” sentence was **wrong** for the current file. `org:openai group` is not among the 1,000, so it still opens the sigma story.
- **Wired into `App.tsx`**:
  - Opens from `view_command` (`view: "temporal" | "story"`, `focus_topic`, `week`, `highlight`, `caption_es`), from clicking any radar card on the left, or from the view switcher buttons (`Tarjetas`, `Grafo temporal (GPU)`, `Historia 1-salto`).

### 3. Headed Chrome measurements (`Apple M1 Pro` Metal GPU, `RADAR_PROFILE=full`)

| View / Action | Metric | Measured value | Notes / Denominator |
|---|---|---|---|
| `TemporalGraph` (`cosmos.gl` 3.5.1) | Renderer | `ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro)` | *(measured)* headed Chrome (`1440×1020`, DPR 2) |
| `TemporalGraph` | `t_fetch_ms` / `t_parse_ms` | `39.8 ms` / `4.5 ms` | earlier 1.67 MB file; **wrong** size for the current 3,794,275-byte file. Not re-measured. |
| `TemporalGraph` | First frame (`t_first_frame_ms`) | `107.2 ms` | earlier session. The `3,518` W42 edge count was **wrong**; the current file has 3,463. |
| `TemporalGraph` | FPS while playing (`fps_playing`) | `120.2 fps` | *(measured)* 13-week animation sweep (`220 ms`/week) |
| `TemporalGraph` | Week switch time (`week_switch_ms`) | median `1.8 ms`, max `3.0 ms` | *(measured)* `n=15` week transitions |
| Chat → `TemporalGraph` | `"Muéstrame el grafo de la semana"` | `22.2 s` LLM turn (`107.2 ms` graph render) | *(measured)* opens `TemporalGraph` + Spanish summary |
| Chat → `StoryGraph` (`org:nvidia`) | `"¿Qué está pasando con Nvidia? Muéstramelo en el grafo"` | `9.9 s` LLM turn, `26.0 ms` Sigma render | earlier session. Rank `#177` and “opens sigma” were **wrong**: current rank is 150, and Nvidia is one of the 1,000 GPU nodes. |
| Card click → `StoryGraph` (`#1`) | Click card `#1 org:marsh mclennan` | `33.0 ms` Sigma render | *(measured)* `21` nodes + scores row + 20 Spanish neighbors |

- **Bundle size added (`cd web && bun run build`, Vite 6.4.4)**:
  - `dist/assets/index-_zBrtXyz.js`: `267.67 kB` (`83.08 kB` gzip) *(measured)*
  - `dist/assets/sigma-vendor-CxsImN5y.js` (`sigma` 3.0.3 + `graphology` 0.26.0): `159.49 kB` (`37.94 kB` gzip) *(measured)*
  - `dist/assets/cosmos-vendor-DOVCUqqA.js` (`@cosmos.gl/graph` 3.5.1 + `@luma.gl/*` 9.3.6): `745.56 kB` (`195.32 kB` gzip) *(measured)*
  - Total JS added by the two graph libraries: `905.05 kB` raw / `233.26 kB` gzipped *(measured)*.
- **Screenshots (saved in git-ignored `lake/views/`)**:
  - `lake/views/ui_temporal_chat.png` (and `lake/views/temporal.png`): `TemporalGraph` opened from chat `"Muéstrame el grafo de la semana"`.
  - `lake/views/ui_story_nvidia_chat.png`: `StoryGraph` for `org:nvidia` opened from chat `"¿Qué está pasando con Nvidia? Muéstramelo en el grafo"`, with outside-Top-10 notice banner.
  - `lake/views/ui_story_top1_card.png` (and `lake/views/story.png`): `StoryGraph` for `#1 org:marsh mclennan` opened by clicking radar card #1.

### 4. Exact files WS8 must copy for deploy (`web/public/data/views/*`)

`web/public/data/` is git-ignored (`AGENTS.md` Data rule). The list that used to be here (1.67 MB temporal, 30.3 kB story, and `euronext` / `adani` / `ministry of science` / `kioxia` / `sterling` / `yahoo` as current top-10 files) was **wrong**. `copy-views` copies `lake/views/*.json` and does not delete those six stale files; they are still on disk and are not in `stories_index.json`. Copy the current index, not those leftovers:

- `web/public/data/views/temporal.json` (3,794,275 bytes)
- `web/public/data/views/stories_index.json` (5,264 bytes)
- `web/public/data/views/story.json` (45,805 bytes, default `#1` `org:marsh mclennan`)
- `web/public/data/views/story_org_marsh_mclennan.json`
- `web/public/data/views/story_org_rocket_lab.json`
- `web/public/data/views/story_org_national_stock_exchange.json`
- `web/public/data/views/story_org_university_college_london.json`
- `web/public/data/views/story_org_citigroup.json`
- `web/public/data/views/story_org_sandisk.json`
- `web/public/data/views/story_org_comcast.json`
- `web/public/data/views/story_org_kroger.json`
- `web/public/data/views/story_org_founders_fund.json`
- `web/public/data/views/story_org_sb_energy.json`
- `web/public/data/views/story_org_nvidia.json` (reference, rank 150)
- `web/public/data/views/story_org_microsoft.json` (reference, rank 133)
- `web/public/data/views/story_org_google.json` (reference, rank 203)
- `web/public/data/views/story_org_openai_group.json` (reference, rank null, outside the 1,000)
- `web/public/data/views/story_thm_tech_automation.json` (reference, rank 73)

Do not treat as current: `story_org_euronext.json`, `story_org_adani_enterprises.json`, `story_org_ministry_of_science.json`, `story_org_kioxia_holdings.json`, `story_org_sterling.json`, `story_org_yahoo.json`.

---

## Done (WS5b, full lake)

- **`/api/radar` was broken on the full lake (HTTP 500).** DuckDB 1.5.6 cannot filter WS4's
  Polars-2.0-written `topic_scores_weekly.parquet`: `NotImplementedException: PlainSkip not
  implemented` on the all-null `outperformance` column whenever a WHERE clause applies (plain
  `SELECT *` works). The endpoint now scans the file with Polars (week filter pushed down); the
  table is 1.1 MB. Handles both subtopic ids and `org:`/`thm:` ids; the lake currently holds 17,285
  rows (17,101 org, 184 thm) over 46 weeks, 2025-W49 .. 2026-W42 (measured).
- **Privacy guard.** `/context` drops `per:` neighbours in SQL and again in Python, renumbers ranks
  1..n, and returns `[]` when the topic itself is a person (`/timeline` too). `/api/radar` drops
  `ranked_universe.org_deny` orgs read from `contracts/taxonomy.yaml` (and any `per:` id).
  Tests bind on real-shaped rows: `org:reuters` ranked #1 is removed; a `per:` neighbour ranked #1
  is removed and the next one becomes rank 1.
- **No request reads `edges_weekly`** when `topic_context_1hop` exists; `/api/freshness` now reads
  Parquet footer statistics (edges_weekly: 13 ms instead of a 461 ms scan, measured).
- **UI**: ISO-week selector (`<input type="week">`, default = latest scored week from
  `/api/freshness`); cards titled with the taxonomy `label_es` for subtopics and the name for
  `org:`/`thm:` rows (id shown next to it); clicking a card loads its timeline and its 1-hop ring
  for the selected week; chat turns send the selected week; dev-only wording removed.
- Tests: `uv run --extra api pytest api` 10 passed (3 new); `make check && make test` pass;
  `cd web && bun run build` passes.

## Latency on the full lake (measured, 2026-10-17 22:56 UTC-5)

`RADAR_PROFILE=full`, uvicorn on localhost, 20 calls per endpoint after one warm-up call; topics
`org:nvidia`, `org:openai group`, `thm:TECH_AUTOMATION`, `org:microsoft` (`org:openai` does not
exist in GDELT's names); radar: 10 latest-week calls + 10 for 2026-W40. Target p95 < 300 ms
(estimate): met.

| endpoint | calls | p50 ms | p95 ms | max ms | rows (first call) |
|---|---|---|---|---|---|
| /api/radar | 20 | 11 | 17 | 18 | 10 |
| /api/topic/{id}/timeline | 20 | 27 | 32 | 36 | 704 |
| /api/topic/{id}/context | 20 | 21 | 22 | 22 | 20 |

Before the change `/api/radar` failed with HTTP 500 on every call (measured).

## Chat on the full profile (measured, 3 turns, Nebius, week 2026-W42)

The Chrome extension was not connected, so the turns were sent through the UI's own path (the Vite
dev server's `/api` proxy, the same `POST /api/chat` payload the UI sends), not by clicking. Full
responses with traces: `lake/agent_traces/ws5-full-<conversation_id>.json` (the runtime itself does
not persist traces).

| question | HTTP | latency | trace steps | Auditor |
|---|---|---|---|---|
| ¿Qué tema de IA sube esta semana y por qué? | 200 | 21,828 ms | 8 | **veto**: numbers without source 37.550, 46.991, 100% (answer cites W38, not W42) |
| ¿Qué está pasando con Nvidia? | 200 | 40,474 ms | 14 | ok (all numbers sourced) |
| ¿Cuánto ha costado en BigQuery? | 200 | 4,043 ms | 6 | ok: 365.89 GB billed over 60 jobs (from the ledger) |

## Agent problems for the orchestrator (`agents/**` is out of this brief)

1. `get_top10` fails on the full lake with the same DuckDB `PlainSkip` error, so the agents never see
   the radar and fall back to subtopic trends (turns 1 and 2). Fix in `agents/tools.py` (read with
   Polars) or have WS4 write `topic_scores_weekly` so DuckDB can filter it (e.g. via pyarrow, or
   without the all-null Int32 column).
2. The Cartographer called `get_context_1hop` with "Nvidia" instead of `org:nvidia` and got no rows;
   `/api/topic/org:nvidia/context?week=2026-W42` returns 20 neighbours. The tool needs name -> id
   resolution (GDELT names: `org:openai group`, not `org:openai`).
3. Answers say "Datos en desarrollo" on the full profile.
4. `run_turn` does not write traces to `lake/agent_traces/`.

## Screenshot (full profile, not committed)

`/Users/andresbecerra/Documents/30x_Blinky/radar/lake/ws5/screenshot-full.png` (1440x2200, headless Chrome against the Vite dev server proxied to the full-profile API).

## Notes

- An earlier note said WS4's W42 top 10 was led by `org:marsh mclennan`, `org:euronext`,
  `org:big news network`, and `org:scam centre`. That list does **not** match the current
  `stories_index.json` top 10 (marsh, rocket lab, national stock exchange, university college
  london, citigroup, sandisk, comcast, kroger, founders fund, sb energy). This pass did not
  re-read `topic_scores_weekly`, so it does not say whether the scores table still differs.

## Blocked on

- None.
