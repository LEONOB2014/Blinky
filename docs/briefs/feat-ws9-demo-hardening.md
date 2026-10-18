# BRIEF: WS9b, harden the live demo (cold starts, evidence offline, the final redeploy, rehearsal shots)

Account: **Claude #2 (claude-work)** · Branch: `feat/ws9-demo-hardening` · Worktree: `../radar-worktrees/feat-ws9-demo-hardening`
Written by the orchestrator, 2026-10-18 01:45 UTC-5. Read `AGENTS.md`, `deploy/README.md`,
`docs/submission/demo_script.md`, then this file.

## Goal

The demo works on the first click at 10:00-12:00 today and on Tuesday with 30X: no cold-start pause,
the trust step works even if the API is down, and the last redeploy ships everything merged tonight.

## Outputs

1. **Cold start, measured.** Measure a true cold start of `radar-api` (wait for scale to zero, about
   15 minutes idle, then time `/api/freshness`, `/api/radar` and one chat turn). Then write in
   `deploy/README.md` the exact `gcloud run services update radar-api --min-instances=1` and back to 0
   commands, the cost of one always-on instance per hour (from Cloud Run's published pricing for
   1 CPU / 1 GiB, cited, marked estimate), and the windows to use it (rehearsal and submission today,
   the Tuesday demo). **Do not apply min-instances yourself: the maintainer decides.**
2. **Evidence offline.** Extend `deploy/export_static.py` so the static fallback carries what the
   demo's trust step shows: the backtest summary (`reports/backtest.md` numbers as JSON, whichever
   rows exist), the label-quality summary (`reports/label_quality.md`), the BigQuery and Jev ledgers'
   totals. Plain JSON under `web/public/data/evidence/` (git-ignored); the UI reads it later (WS5).
   A unit test on the dev slice.
3. **The final redeploy, rehearsed.** Write `scripts/redeploy_all.sh` (or a Make target) that runs, in
   order: the checksum check of `topic_scores_weekly` against the lake, `make deploy-cloudrun` (Cloud
   Build), `make deploy-static`, the web build with the API URL, the Netlify deploy, `make
   demo-check`. Dry-run it (no deploy) now. The real run happens when the orchestrator says so,
   after WS4's syndication guard, the agents' quality work and the graph views are merged (about
   05:30-06:00); that run is approved in advance.
4. **Rehearsal shots.** After the Google Drive copy ends (~03:00, check memory first), capture the shot
   list of `docs/submission/video_plan.md` from the live site in a headed Chrome window: screenshots
   under `lake/submission/shots/` (never in git), and note in `status/WS9.md` any step of the demo
   script that does not match what the site shows.
5. When WS4 writes `READY FOR REDEPLOY` with the syndication guard: re-run
   `scripts/showcase_stories.py` and update `docs/submission/stories.md`.

## Files you may touch

`deploy/**`, `scripts/redeploy_all.sh`, `scripts/showcase_stories.py`, `docs/submission/**`,
`Makefile` (deploy/demo targets), `status/WS9.md`.

## Out of scope

`web/` (Antigravity), agents, models, the min-instances change itself.

## Acceptance

`make check && make test` pass; the redeploy script's dry run lists every step and stops before any
deploy; the cold-start numbers are in the status.

## Paid or outward actions needing approval

Approved: the cold-start measurement (a few requests and one chat turn), the final redeploy when the
orchestrator signals it. Ask first: min-instances, anything else that changes the live service.

## Deadlines (UTC-5)

Cold start and evidence export by **03:30**; redeploy script dry-run by **04:00**; shots by **05:00**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS9.md`, then stop.
