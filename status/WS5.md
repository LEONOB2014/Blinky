# WS5 status

Owner: Gemini (Antigravity) for WS5; WS5b (full lake) by Claude #4 (claude-cacho) · Directories: `api/, web/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 23:00 UTC-5 · Branch: `feat/ws5-full-lake` (brief `BRIEF.md`, WS5b) · committed locally; the orchestrator pushes

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
