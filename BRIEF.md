# BRIEF: WS8, deploy the API, the agents and the UI (prepared tonight, switched on with approval)

Account: **Claude #2 (claude-work)** · Branch: `feat/ws8-deploy` · Worktree: `../radar-worktrees/feat-ws8-deploy`
Written by the orchestrator, 2026-10-17 23:20 UTC-5. Read `AGENTS.md`, then this file.
(The design gave this to Gemini; Gemini now runs the classifier cascade, so it moves to you.)

## Goal

A judge opens one URL and sees the radar on the full lake: the cards, the timeline, the 1-hop ring and
the Media Master chat. If the live API cannot run, the same UI serves a static export.

## Plan reference

`docs/designs/radar-build-plan.md`: "Distribution Plan" (API on Modal, UI on Netlify, static fallback),
the `export_static.py` rules (refuses unless `RADAR_PROFILE=full`; `web/public/data/` is git-ignored;
deployed with `netlify deploy --dir`).

## Inputs

- `api/app.py` (FastAPI; `/api/chat` calls `agents.runtime.run_turn`), `web/` (Vite + React, bun).
  WS5b's full-lake fixes are on `feat/ws5-full-lake` (not merged yet): merge `origin/develop` when the
  orchestrator says it landed.
- The lake tables the API reads (measured sizes): `topic_scores_weekly` ~1 MB, `topic_daily` 29 MB,
  `topic_context_1hop` 33 MB, `daily_topic` 4 MB, `daily_topic_rolling` 5 MB, `daily_totals`,
  `node_metrics_weekly` 10 MB. **Not** `edges_weekly` (432 MB): the API reads the ring instead.
- Modal CLI is installed and logged in on this machine (profile measured). Netlify CLI is not
  installed (`npx netlify` works once logged in by the maintainer).
- Known pitfalls: Modal starts no functions without a payment method on the account (a CPU-only app
  may still need it; test early); a new Netlify site returns 401 until "Make public" is clicked;
  deploy with `--site <id>`.

## Outputs

1. `deploy/modal_app.py`: the FastAPI app on Modal (CPU, `@modal.asgi_app`), a Modal Volume holding only
   the tables above (an upload script, `deploy/push_lake.py`), `RADAR_PROFILE=full`, the Nebius key as a
   Modal Secret (created by the maintainer, never from a file in git), CORS for the Netlify origin.
   Test with `modal serve` first; report cold-start and warm latency of `/api/radar` and one `/api/chat`
   turn (measured).
2. `deploy/export_static.py`: writes `web/public/data/` (top 10 per week, timelines and rings of the
   ranked topics of the last 4 weeks, freshness) from the full lake; refuses unless
   `RADAR_PROFILE=full`; a unit test checks the refusal. The UI reads the static JSON when the API is
   unreachable (a small switch in `web/src/api.ts`; coordinate in the status, WS5 owns `web/`, you may
   touch `web/src/api.ts` only).
3. `deploy/README.md`: the exact commands, in order, for the maintainer: create the Modal secret, push
   the lake, deploy, build the web with the API URL, `npx netlify deploy --dir web/dist --site <id>`.
4. `status/WS8.md` (new): what ran, latency, sizes, what waits for approval.

## Files you may touch

`deploy/**`, `web/src/api.ts`, `status/WS8.md`, `Makefile` (deploy targets), `.env.example` (no
values), a `deploy` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

Agents, models, graph, contracts, visual design, the graph views.

## Acceptance

- `make check && make test` pass; the refusal test passes.
- `modal serve` answers `/api/radar` and `/api/freshness` from the Volume (measured latency in the status).

## Paid or outward actions needing approval

Approved: `modal serve` (temporary URL) and uploading the listed lake tables to a Modal Volume (public
GDELT aggregates, no persons, no titles or URLs). **Ask first:** `modal deploy`, creating the Modal
secret, any Netlify login, site creation or deploy, and anything that makes a URL public. `git push`:
the orchestrator.

## Deadlines (UTC-5)

`modal serve` working by **01:30**; static export and README by **03:00**; deploys at the maintainer's
approval, at the latest by **06:00**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS8.md`, then stop.

## Addendum (orchestrator, 00:50 UTC-5): Cloud Run approved; protect the chat; redeploy on WS4

Recorded: the maintainer approved Cloud Run (API) + Netlify (UI) in place of Modal (Modal starts no
containers on this account). Both are live and public.

1. **Protect `POST /api/chat`.** It is public and each turn spends Nebius credit (about 5,900 tokens,
   measured in the LangSmith baseline). Add, in `api/app.py` (you may touch it for this):
   a per-client limit (for example 10 turns per 10 minutes per IP, from `X-Forwarded-For` on Cloud
   Run) and a global daily cap (for example 500 turns), both config values, returning HTTP 429 with a
   Spanish message the UI shows. In-memory is enough (max 3 instances: say so in the runbook). Tests
   offline. Measure that a normal demo flow (5-10 questions) is never blocked.
2. **Redeploy on WS4's signal.** When `status/WS4.md` says `READY FOR REDEPLOY`, rebuild the image
   from the refreshed lake and redeploy Cloud Run, then re-run `make deploy-static` and the Netlify
   deploy so the static fallback matches. Verify the public W42 top 10 no longer shows
   `org:scam centre` / `org:capital markets department`. The redeploy itself is approved.
3. Keep committing locally; the orchestrator pushes. No service URL or project number in git.

Deadline: rate limit by **01:30**; redeploy within 30 minutes of WS4's signal.
