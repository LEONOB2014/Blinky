# BRIEF: WS5, the read API and a plain contract-driven UI

Account: **Gemini (Antigravity)** · Branch: `feat/ws5-api-ui` · Worktree: `../radar-worktrees/feat-ws5-api-ui`
Written by the orchestrator, 2026-10-17 20:45 UTC-5. Read `AGENTS.md` (or `GEMINI.md`), then this file.

## Goal

Serve the radar's data through the API in `contracts/api.yaml` and show it in a plain, working web UI
with a chat panel and an agent-trace panel. Visual design comes later from Lovable: keep the UI simple,
typed from the contracts, and easy to restyle.

## Plan reference

`docs/designs/radar-build-plan.md`: "Demo order", "Mocks, dev slices and the release check",
"Distribution Plan"; `contracts/api.yaml`, `contracts/decision_card.schema.json`,
`contracts/view_command.schema.json`, `contracts/agent_trace.schema.json`.

## Inputs

- `radar.paths.gold(name)` (dev profile reads `fixtures/dev/`, full reads the lake). Today's real tables:
  `daily_totals`, `daily_topic`, `daily_topic_rolling`, `edges_weekly`. `topic_scores_weekly` arrives from
  WS4 (dev ~23:30, full ~03:00); until then `/api/radar` returns an empty list and says why in a header.
- `POST /api/chat` calls the orchestrator's agent runtime (`agents/`, arriving ~01:00). Until it exists,
  return HTTP 503 with `{"detail": "agents runtime not deployed yet"}`. Never return invented answers.

## Outputs

1. `api/app.py` (FastAPI + DuckDB over Parquet): every path in `contracts/api.yaml`; responses validated
   against the JSON Schemas in tests; `/api/freshness` returns the newest `dt` per table and the profile.
2. `api/tests/`: endpoint tests on the dev slice.
3. `web/` (Vite + React + TypeScript, bun): top-10 cards (chips, decision, window), a topic timeline, a
   chat panel (calls `/api/chat`, renders decision cards and applies `view_command`s to a placeholder view
   area), and a trace panel (agent, action, tool, latency). Types generated or hand-written from the
   contracts. A visible banner when the API reports `profile = dev`: "datos de desarrollo".
4. `make api-dev` and `make web-dev` targets (add them to the Makefile section for WS5).

## Files you may touch

`api/**`, `web/**`, `status/WS5.md`, the `api` extra in `pyproject.toml`/`uv.lock`, and new WS5 targets in
`Makefile`.

## Out of scope

Agents, scores, graphs (the graph views are a later brief), deployment to Modal/Netlify (later brief),
visual polish (Lovable).

## Acceptance

- `make check && make test` pass; API tests on the dev slice validate responses against the contracts.
- `cd web && bun run build` passes.
- Screenshot of the UI on the dev slice in `status/WS5.md` (path to the file under `web/`, not committed if large).

## Paid or outward actions needing approval

`git push`, opening the PR, any deployment.

## Deadlines (UTC-5)

API on the dev slice by **23:00**; UI with cards, chat and trace panels by **01:30**.

## Report

`status/WS5.md` at each sync; PR as a **draft** against `develop`, ready only after the local gate passes.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS5.md`, then stop. If your account cannot run (auth), the
orchestrator reassigns this brief to Claude #4.

## Addendum (orchestrator, 21:10 UTC-5)

- The agent runtime is merged into this branch: `from agents.runtime import run_turn`; `run_turn(message,
  conversation_id, week=week)` returns exactly the `/api/chat` response of `contracts/api.yaml`. It needs
  `NEBIUS_API_KEY` in `.env` (already there). Replace the 503 stub with it; keep the 503 when the key is
  missing. In tests, pass a scripted model as `agents/tests/test_runtime.py` does (no network in CI).
- Open this worktree in **Antigravity** (Gemini AI Pro account).
