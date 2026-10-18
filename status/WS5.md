# WS5 status

Owner: Gemini (Antigravity) · Directories: `api/, web/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:32 UTC-5 · Branch: `feat/ws5-api-ui` · PR: pending maintainer approval to open draft PR

## Done

- Implemented `api/app.py` (FastAPI + DuckDB over Parquet) covering all 5 paths in `contracts/api.yaml`:
  - `GET /api/radar`: reads `topic_scores_weekly` via `radar.paths.gold`; until WS4 lands the table, returns `[]` with HTTP 200 and headers `X-Radar-Empty-Reason` and `X-Radar-Status: pending-ws4`.
  - `GET /api/topic/{topic_id}/timeline`: reads `topic_daily` when present and falls back to `daily_topic` on the dev slice, preserving `NULL` on `is_missing` days (never zero-filled) and matching `contracts/topic_daily.schema.json`.
  - `GET /api/topic/{topic_id}/context`: reads `topic_context_1hop` when present and falls back to computing the 1-hop context ring from `edges_weekly` (`n >= 3`, `npmi > 0.1`, dropping top 1% weighted-degree hubs, top 20 by NPMI), matching `contracts/topic_context_1hop.schema.json`.
  - `GET /api/freshness`: returns active `profile` (`dev` or `full`) and newest date/week per gold table.
  - `POST /api/chat`: wired to `agents.runtime.run_turn(message, conversation_id, week=week)` per the 21:10 UTC-5 addendum; returns HTTP 503 `{"detail": "agents runtime not deployed yet"}` when `NEBIUS_API_KEY` is missing.
- Added `api/tests/test_app.py`: 7 unit/contract tests on the dev slice validating responses against `topic_scores_weekly`, `topic_daily`, `topic_context_1hop`, `decision_card`, `view_command`, and `agent_trace` JSON Schemas using a scripted model (no network in CI).
- Built `web/` (Vite + React + TypeScript, bun):
  - Visible top banner when `profile === "dev"` (`"datos de desarrollo"`), plus per-table freshness chips from `/api/freshness`.
  - Top-10 cards panel (`GET /api/radar`) with stage, window chip, six score chips, decision badge, and `why` bullets; displays the `X-Radar-Empty-Reason` header and subtopic selector pills while `topic_scores_weekly` is pending from WS4.
  - Topic timeline panel (`GET /api/topic/{topic_id}/timeline`) with per-language (`eng`, `spa`, `por`, `other`) article totals, latest share, mean tone, and multi-language SVG chart leaving `is_missing` days as `NULL` gaps.
  - 1-hop context ring table (`GET /api/topic/{topic_id}/context`) showing rank, neighbor, co-mentions `n`, and `npmi`.
  - Placeholder view area (`view_command`) that updates live when the Cartographer emits `view_commands`.
  - Media Master chat panel (`POST /api/chat`) rendering `answer_es`, `decision_cards` with KPI sources and Auditor status, and applying `view_commands`.
  - Agent trace panel (`agent_trace`) showing step, agent, action, tool, latency (ms), and summary.
- Added `make api-dev` and `make web-dev` targets to `Makefile`.
- Captured screenshot of the live UI running against the dev slice API at `web/screenshot-dev.png`.

## In progress

- Ready to switch `/api/radar` cards view to real `topic_scores_weekly` rows as soon as WS4 lands the dev/full table.

## Blocked on

- None.

## Numbers (each marked measured or estimate)

- API contract endpoints implemented and tested: **5 / 5** *(measured, 5 paths in `contracts/api.yaml`)*
- Test suite (`make test` / `uv run pytest -m "not bq and not data"`): **57 / 57 passed, 9 skipped** *(measured, 50 existing + 7 new API endpoint/contract tests in `api/tests/test_app.py`, runtime 1.33 s)*
- Pre-commit quality gate (`uv run pre-commit run --all-files`): **15 / 15 hooks passed** *(measured)*
- Web production build (`cd web && bun run build`): **30 modules transformed**, bundle **239.97 kB JS / 74.66 kB gzip, 4.68 kB CSS / 1.52 kB gzip** in **595 ms** *(measured)*
- Dev-slice timeline (`GET /api/topic/regulation_policy/timeline`): **220 / 220 rows valid** against `topic_daily.schema.json` across 4 language buckets over 55 days (`2026-08-24` to `2026-10-17`: **6,029** `eng`, **1,097** `spa`, **343** `por`, **572** `other` articles) *(measured)*
- Dev-slice 1-hop context (`GET /api/topic/org:google/context?week=2026-W41`): **20 / 20 rows valid** against `topic_context_1hop.schema.json` (`n >= 3`, `npmi > 0.1`, top 1% degree hubs excluded) *(measured)*
- Dev-slice UI screenshot: `web/screenshot-dev.png` (**263,815 bytes**, `1440x1080`) *(measured)*
