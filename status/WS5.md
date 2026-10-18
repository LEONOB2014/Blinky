# WS5 status

Owner: Gemini (Antigravity) for WS5; WS5b (full lake) by Claude #4 (claude-cacho) · Directories: `api/, web/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 01:55 UTC-5 · Branch: `feat/ws5-graph-views` (brief `BRIEF.md`, WS5 G) · committed locally; the orchestrator pushes

## G — Graph views in `web/` (`feat/ws5-graph-views`)

### 1. Readable exports (`graph/export_views.py`)

- **Temporal export (`lake/views/temporal.json`)**:
  - Scans `edges_weekly` one week at a time (`min_n=20`, `npmi > 0.1`, `max_nodes=1,000`, `top_k=5` edges by NPMI per node per week) instead of dumping all 296,657 unpruned edges.
  - Precomputes a deterministic frozen 2D layout (`_precompute_layout`, `igraph` Fruchterman-Reingold on the pruned union graph, median-centered with p90 radial compression, scaled to `[448, 3648]` in `spaceSize=4096`), Spanish labels (`label_es`) for `thm:`/`loc:`/`org:` ids, `show_label=true` on the top 30 PageRank nodes plus ranked top-10 topics (`38` labeled nodes total *(measured)*), and `_meta.top_movers_per_week`.
  - **Full-profile measurements (`RADAR_PROFILE=full`, 13 weeks `2026-W30 .. 2026-W42`)**:
    - Nodes: `1,000` (`0` `per:` nodes, `38` with `show_label=true`) *(measured)*
    - Total pruned edges across 13 weeks: `44,610` (`3,290` min .. `3,518` max edges/week; `3,518` in `2026-W42`, down from `36,243` unpruned) *(measured)*
    - File size: `1,671,019` bytes (`1.67 MB`, down from `6.70 MB` unpruned) *(measured)*
    - Export runtime: `2.54 s` *(measured)*
- **Story exports (`lake/views/story*.json`, `lake/views/stories_index.json`)**:
  - Filters out `ranked_universe.org_deny` and `per:` entities, exports `story_<slug>.json` for all `10` ranked Top-10 topics of `2026-W42` (`org:marsh mclennan` #1 .. `org:yahoo` #10) plus `5` reference topics outside the W42 Top 10 (`org:nvidia`, `org:microsoft`, `org:google`, `org:openai group`, `thm:TECH_AUTOMATION`), `story.json` (#1 default), and `stories_index.json` (`15` stories total *(measured)*).
  - File size (`story.json`, `#1 org:marsh mclennan`): `30,345` bytes (`30.3 kB`, `21` nodes, `162` edges) *(measured)*.
  - Export runtime (all 15 stories + index + copy to `web/public/data/views/`): `0.20 s` *(measured)*.
  - Peak RSS across full export (`ru_maxrss`): `1,259,749,376` bytes (`1,201.4 MiB`, below the `1.5 GB` cap) *(measured)*.

### 2. `web/` components (`TemporalGraph.tsx` & `StoryGraph.tsx`)

- **`TemporalGraph.tsx` (`@cosmos.gl/graph` `3.5.1` + pinned `@luma.gl/{constants,core,engine,shadertools,webgl}@9.3.6`)**:
  - Uses precomputed frozen positions (`enableSimulation: false`, `rescalePositions: false`, `fitViewOnInit: false`, `fitView(0, 0.08, false)` after `await graph.ready`) and normalized `[0, 1]` RGBA float buffers.
  - Play/pause (`▶ Reproducir 13 semanas`), week range slider (`2026-W30 .. 2026-W42`), node color by `decision` (`publicar_ahora` green, `preparar` sky blue, `esperar` amber, `deg_growth >= +40%` teal, context slate), greedy bounding-box collision-avoided Spanish labels overlay (`spaceToScreenPosition`, `12` non-overlapping labels on screen in `2026-W42` out of `38` eligible *(measured)*), and side panel of weekly top movers (`_meta.top_movers_per_week[w]`).
- **`StoryGraph.tsx` (`sigma` `3.0.3` + `graphology` `0.26.0`)**:
  - Loads `/data/views/stories_index.json` and the matching `/data/views/story_<slug>.json`.
  - Places the focal topic in the center (`★ label_es`) and its 20 1-hop neighbors on two staggered concentric rings by rank (`1..10` inner, `11..20` outer), spoke edge width proportional to co-mentions `n`, top-10 strongest intra-ring chords, Spanish labels, scores row above the canvas, and ranked 1-hop neighbors sidebar.
  - Displays an explicit notice banner when the requested topic is outside the `2026-W42` Top 10 (e.g., `org:nvidia` at rank `#177`, `decision: no_es_tema_caliente`).
- **Wired into `App.tsx`**:
  - Opens from `view_command` (`view: "temporal" | "story"`, `focus_topic`, `week`, `highlight`, `caption_es`), from clicking any radar card on the left, or from the view switcher buttons (`Tarjetas`, `Grafo temporal (GPU)`, `Historia 1-salto`).

### 3. Headed Chrome measurements (`Apple M1 Pro` Metal GPU, `RADAR_PROFILE=full`)

| View / Action | Metric | Measured value | Notes / Denominator |
|---|---|---|---|
| `TemporalGraph` (`cosmos.gl` 3.5.1) | Renderer | `ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro)` | *(measured)* headed Chrome (`1440×1020`, DPR 2) |
| `TemporalGraph` | `t_fetch_ms` / `t_parse_ms` | `39.8 ms` / `4.5 ms` | *(measured)* `1.67 MB` `temporal.json` |
| `TemporalGraph` | First frame (`t_first_frame_ms`) | `107.2 ms` | *(measured)* `1,000` nodes, `3,518` edges in `2026-W42` |
| `TemporalGraph` | FPS while playing (`fps_playing`) | `120.2 fps` | *(measured)* 13-week animation sweep (`220 ms`/week) |
| `TemporalGraph` | Week switch time (`week_switch_ms`) | median `1.8 ms`, max `3.0 ms` | *(measured)* `n=15` week transitions |
| Chat → `TemporalGraph` | `"Muéstrame el grafo de la semana"` | `22.2 s` LLM turn (`107.2 ms` graph render) | *(measured)* opens `TemporalGraph` + Spanish summary |
| Chat → `StoryGraph` (`org:nvidia`) | `"¿Qué está pasando con Nvidia? Muéstramelo en el grafo"` | `9.9 s` LLM turn, `26.0 ms` Sigma render | *(measured)* `21` nodes; shows banner noting `org:nvidia` is rank `#177` (not in W42 Top 10) |
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

`web/public/data/` is git-ignored (`AGENTS.md` Data rule). Before running `cd web && bun run build` (or deploying `web/dist/` to Netlify), WS8 must ensure `lake/views/*.json` are generated (`RADAR_PROFILE=full uv run --extra graph python -m graph.export_views`) or copied into `web/public/data/views/` (`bun run copy-views` runs automatically in `bun run dev` and `bun run build` when `lake/views/*.json` is present):

- `web/public/data/views/temporal.json` (`1.67 MB`)
- `web/public/data/views/stories_index.json` (`5.3 kB`)
- `web/public/data/views/story.json` (`30.3 kB`, default `#1` story)
- `web/public/data/views/story_org_marsh_mclennan.json`
- `web/public/data/views/story_org_euronext.json`
- `web/public/data/views/story_org_adani_enterprises.json`
- `web/public/data/views/story_org_rocket_lab.json`
- `web/public/data/views/story_org_national_stock_exchange.json`
- `web/public/data/views/story_org_ministry_of_science.json`
- `web/public/data/views/story_org_kioxia_holdings.json`
- `web/public/data/views/story_org_sterling.json`
- `web/public/data/views/story_org_citigroup.json`
- `web/public/data/views/story_org_yahoo.json`
- `web/public/data/views/story_org_nvidia.json`
- `web/public/data/views/story_org_microsoft.json`
- `web/public/data/views/story_org_google.json`
- `web/public/data/views/story_org_openai_group.json`
- `web/public/data/views/story_thm_tech_automation.json`

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

- WS4's W42 top 10 is led by `org:marsh mclennan`, `org:euronext`, `org:big news network` (an
  outlet not on the deny list) and `org:scam centre`: worth a look by WS4 and the lead before the
  demo; the API serves what the table holds.

## Blocked on

- None.
