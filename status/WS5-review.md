# WS5 review — `feat/ws5-graph-views` (read-only)

Reviewed 2026-10-18 against `BRIEF.md` Addenda 2, 3, 4 and the Correction.
HEAD `5749b98` (`docs(ws5): record Addenda 2 and 3 measurements…`), 13 files ahead of
`origin/develop` (+5,672 / −234). No other file was edited. The graph export was not re-run.
Headed Chrome was not re-driven; the screenshots already in `lake/views/ui_*.png` were read.

## Gates

| Command | Result |
|---|---|
| `make check` | Pass. ruff check, ruff format, trailing whitespace, EOF, yaml, json, toml, large files, merge conflicts, private keys, branch guard, uv-lock, actionlint, detect-secrets, contracts/mocks. |
| `make test` | Pass. **271 passed, 9 skipped, 27 deselected** in 20.04 s (`pytest -m "not bq and not data"`). |
| `cd web && bun run build` | Pass. Vite 6.4.4, 1.73 s. `index-BmV6RG6L.js` 286.04 kB (88.22 kB gzip), CSS 14.08 kB (3.55 kB gzip), `sigma-vendor` 159.49 kB (37.94 kB gzip), `cosmos-vendor` 745.56 kB (195.32 kB gzip). |

`bun run build` from the repo root fails (`Script not found "build"`). The web script is the one that passes.
There is no web unit test. The export tests are `pytest.mark.unit` and ran inside `make test`.

## Met

- Stories were re-exported. `web/public/data/views/stories_index.json` is `full`, week `2026-W42`, 10 top-10 files plus Nvidia, Microsoft, Google, OpenAI group, and `thm:TECH_AUTOMATION` (15 stories). `temporal.json` is 3,740,882 bytes, 1,000 nodes, 44,005 links over 13 weeks, 3,463 links in W42. Zero `per:` nodes. Under the 50k-link re-layout cap.
- Addendum 3 columns are in that file and documented with formulas in `graph/README.md`: `n`, `npmi`, `edge_state`, `n_growth`, `cross_ring`, `betweenness`, `cross_ring_share`, `momentum`, `community_week`, `importance`. Medians in `_meta.property_distributions_latest_week` match the medians quoted in `status/WS5.md`.
- Split pane defaults to 35% and drags between 20% and 60%. Full-screen is a button, `F`, and `Esc`, with a floating chat and a collapsible top-10 drawer. A chat `view_command` of `temporal` or `story` calls `setIsFullscreen(true)`.
- Eight lens functions exist in `TemporalGraph.tsx` (colour, size, width, alpha). `simulationAlpha` is not a config field. The code calls `graph.start(0.35)` and `graph.pause()`, which is the Correction's API.
- Curved links and `linkColorInterpolateFromEndpoints: true` are on. The installed `config.d.ts` says that flag **overrides per-link RGB** from `setLinkColors` (opacity still applies). Width and alpha can still change per lens. The gold / orange / cyan link colours the legend promises do not.

## Bugs

1. **`color_by` never reaches the graph.** `App.tsx` renders `<TemporalGraph>` and `<StoryGraph>` without `colorBy` or `captionEs`. Every local command hardcodes `color_by: "tone"`. The cartographer already emits `decision` / `segment` / `bridge` / `momentum` / `novelty` / `window` / `tone` from `agents/runtime.py` `view_lens` (on this branch via the develop merge). That value is stored on `activeView` and shown in the "Color por" chip, then dropped. `web/src/types/contracts.ts` still types `ViewColorBy` as `"tone" | "arousal" | "community" | "segment"`, so the contract enum (`contracts/view_command.schema.json`) is not what the UI type allows. `arousal` has no lens.
   Both screenshots show the desync: `lake/views/ui_lens_radar.png` is "Lente activo: Radar (Decisión)" with chip "Color por: tone"; `lake/views/ui_chat_rearrange.png` is "Lente activo: Momento" with the same chip, and the chat box still holds "Muéstrame el grafo de la semana" with no answer. The Momento pill was clicked. `view_lens` does not map "¿Qué tema de IA sube esta semana…?" to `momentum` (`_MOMENTUM_Q` is `impulso|acelera|sube más rápido|ganando`). It returns `decision`.

2. **Reheat does not run, and the settle numbers are the timer.** `applyLensToGraph` always ends in `g.render(0, 0)`. Installed `index.d.ts`: `render(0, …)` sets alpha to 0 and the simulation stops after one frame. `handleSelectLens` calls `start(0.35)` and then the effect's `render(0, 0)` cancels it. `reheatSimulation` waits a fixed 380 ms, counts `requestAnimationFrame`, and writes `settle_time_ms` / `fps_relayout`. It never reads `graph.progress` or `isSimulationRunning`. The radar and momentum screenshots share the same frozen positions (Marsh right, Rocket Lab right, UCL left, Comcast lower right). Colours change. The layout does not. `status/WS5.md`'s "120.6 fps re-layout" and "380.7 ms settle" are that timeout, not a measured convergence.

3. **`setLinkStrength` is never called.** The lens code fills a `linkStrength` array and does not pass it. The method exists on `@cosmos.gl/graph@3.5.1`. Top-10 links, the focus topic's links, and intra-community links do not pull the layout. Combined with bug 2, no lens rearranges the graph.

4. **Story lens does not pin, and named topics always leave the temporal graph.** `setPinnedPoints` exists and is never called. `zoomToPointByIndex(focusIdx, 400, 1.8)` omits `enableSimulation`, which defaults to **true**, so a story zoom starts the simulation with nothing pinned. Card clicks, the movers list, and `onOpenStory` set `view: "story"`, which unmounts cosmos and opens sigma. The cartographer does the same whenever the question names an entity (`view="story" if entity else "temporal"`). Nvidia, Microsoft, Google, Marsh McLennan, and `TECH_AUTOMATION` are in the 1,000-node graph, so Addendum 2's rule (sigma only when X is absent) does not run. `org:openai group` is **not** in the temporal graph; sigma is the right fallback for that one, and the reference story file exists.

5. **Highlight repaints the decision lens.** In the `decision` branch, `isFocused` is applied before the decision colour and forces rose. For a question with no named entity, `gather` sets `highlight` to the whole top 10. Wiring `color_by` without changing this will hide publicar / preparar / esperar on exactly the ten nodes the radar is about.

6. **Degree growth is labelled as a percent of a logarithm.** `graph/metrics.py` sets `deg_growth = log(deg / deg_prev)`. The movers panel prints `(deg_growth * 100)%`. The screenshots show Rocket Lab **+200%** (log 2.002 → degree ratio e^2.002 ≈ **7.4×**) and University College London **+512%** (log 5.116 → about **167×**). `pr_rank_delta` is a rank-place delta (`r_prev - rank`) and the +4,673 / +5,844 figures match that definition; the label "ΔPR" does not say they are rank places.

7. **Window clusters are sticky.** `setPointClusters` runs for the `window` lens and no other lens clears it (`setPointClusters` with `undefined`, or `[]`). The next time a simulation actually runs, nodes still carry window-state clusters.

8. **Deny-listed wires stay in the temporal graph.** `_no_persons` drops `per:`. `ranked_universe.org_deny` is applied to score rows and to story selection, not to temporal nodes. Shipped graph contains `org:reuters` and `org:associated press`. `graph/README.md` says deny-listed wire services are dropped.

## Missing must items

| Addendum | Item | State |
|---|---|---|
| 2.3 | Lenses driven by `view_command.color_by` | Not wired (bug 1). Pills work locally. |
| 2.3 | `filter` (`segment`, `lang_bucket`, `hops`) | Not read by either graph component. |
| 2.3 | Radar default from a command | The canvas default is `decision` only because the prop is omitted. The command chip says `tone`. |
| 2.3 | Story: pin X, strong links, neighbours by ring, everyone else faint, `zoomToPointByIndex`; sigma only if X is outside the temporal graph | Sigma is the primary path (bug 4). The cosmos `segment` branch fades non-neighbours and zooms; it does not pin. |
| 2.3 | Reheat from the current positions, then freeze when settled | `start(0.35)` is cancelled by `render(0, 0)` (bug 2). |
| 2.3 | Top-10 links get a higher `setLinkStrength` | Array is discarded (bug 3). |
| 2.4 | Edge RGB follows the lens, gradient from the endpoints | Gradient wins and lens RGB is ignored. Width = log(n) and alpha = NPMI are implemented. |
| 2.5 | Measure fps during re-layout and time to settle | Numbers in `status/WS5.md` are the 380 ms timer and the display refresh. |
| 3 | `community` lens: intra-community edges stronger **in the layout** | Strength is not uploaded (bug 3). |
| 3 | Novelty: persisting edges muted | `new` is bright and `fading` is dim (alpha 0.06). `persisting` keeps the NPMI alpha. Dashed fading is optional; dim qualifies. `setLinkStyles` (solid / dashed / dotted) is unused. |
| 3 | Halo on the radar top 10 | Size floor of 13 px. No second ring. |
| 4 | Brief card on each top-10 card (`headline_es`, `what_happened_es`, `why_latam_es`, `angle_es`, `hook_es`, `format_es`, Auditor badge) | Absent. |
| 4 | Evidence card, up to 5 articles, title opens in a new tab | Absent. |
| 4 | Trust panel from the header, with denominator and medido/estimado | Absent. Header is freshness only. |
| 4 | Missing data file → the card says "pendiente" and does not throw | No card. `web/public/data/briefs/` and `web/public/data/evidence/` do not exist. `deploy/export_static.py` is not in the diff. |
| 4 | Say so in the status if the cards are dropped | `status/WS5.md` (02:55 UTC-5) says Addenda 2 and 3 are complete and does not mention Addendum 4. |

Nice items that did land: tone and window lenses, a label-only tooltip (the canvas has no point hover; the tooltip says "Fading" in English). No 400 ms colour interpolation (`render(0, 0)` snaps). `kcore` is exported and not used as a depth cue.

## Demo risks

Shipped `temporal.json` / `stories_index.json`, week 2026-W42, counted in this review:

- **The top 10 a judge will see** is Marsh McLennan (preparar), Rocket Lab (esperar), National Stock Exchange (preparar), University College London (preparar), Citigroup (esperar), SanDisk (esperar), Comcast (preparar), Kroger (preparar), Founders Fund (esperar), SB Energy (esperar). None is a core AI lab. Nvidia is rank 150, `no_es_tema_caliente`.
- **Radar lens has no "Publicar ahora".** Decisions on the 1,000 nodes: null 911, `no_es_tema_caliente` 43, `esperar` 38, `preparar` 8, `publicar_ahora` 0. The green legend swatch is empty. Most of the graph is the slate "Muted / otro" bin.
- **Bridge lens is sparse.** Rings on the 1,000 nodes: `ai_domain` 942, `ai` 29, `it` 29. `cross_ring_share` median 0, p90 0.207 (n=930). Cross-ring edges in W42: **243 / 3,463 (7.0%)**.
- **Novelty lens is mostly "new".** W42 `edge_state`: `new` 2,228, `persisting` 915, `growing` 218, `fading` 102 (n=3,463). State is compared to the previous week's **top-5 NPMI** edges, so an edge that stayed in the full graph and fell out of the cut is `new`. Across all 13 weeks, 27,360 / 44,005 edges are `new`.
- **Window lens is mostly empty.** W42 `window_state`: null 911, `sin_estimacion` 41, `dias_restantes` 31, `en_cualquier_momento` 15, `ya_en_espanol` 2.
- **Tone lens is mostly grey at the ±1 cut.** Of 944 nodes with a tone: 566 inside [−1, 1], 223 ≤ −1, 155 ≥ 1. Range −5.31 to +5.84, median −0.05.
- **22 Leiden communities, 8 colours** (`cId % COMMUNITY_COLORS.length`). Distinct communities share a colour.
- **`status/WS5.md` categorical counts do not match this file** (medians do). The prose says W42 `edge_state` new 2,752 / growing 422 / persisting 243 / fading 46, cross-ring 468 (13.5%), rings ai 90 / it 43 / ai_domain 867, 20 communities. The file says 2,228 / 218 / 915 / 102, 243 cross-ring edges, 29 / 29 / 942, 22 communities. Quoting the prose in the demo states counts the file does not contain.
- **The WS8 file list in `status/WS5.md` is the previous top 10** (Euronext, Adani, Kioxia, Ministry of Science, Sterling, Yahoo). The index now points at SanDisk, Comcast, Kroger, UCL, Founders Fund, SB Energy. `cp -f` in `bun run copy-views` does not delete the old `story_*.json` files, so `web/public/data/views/` contains both generations (24 json files). Copying the status list misses the current top 10; copying the directory ships stale stories the index no longer names.
- **`ui_lens_radar.png` was taken with the API down** (freshness "…", "Tabla `topic_scores_weekly` pendiente: sin filas", subtopic pills instead of cards). The static graph still draws. A demo that does not have the API up has no top-10 cards and no cartographer command.
- User-visible English on a Spanish screen: "Muted / otro", "Cross-ring", "Glow", "Betweenness", "Fading", "GPU", "NPMI", "sigma", "cosmos.gl".

## Not re-checked

Export peak RSS, headed-Chrome fps of the frozen sweep, and a live `/api/chat` turn. Those figures in `status/WS5.md` were not reproduced in this review. The re-layout fps and settle time should not be used: the code path that records them does not leave the simulation running.
