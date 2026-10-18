PLATFORM CHANGE (2026-10-18, shortly after 00:00 UTC-5, approved by the maintainer in chat): the API moves from
Modal to **Google Cloud Run**, in the GCP project that already runs BigQuery (billing enabled,
measured; Cloud Run, Cloud Build and Artifact Registry APIs enabled). Modal stays as an alternative:
its workspace starts no container (no payment method or billing paused), and that blocker is now
moot for the demo. Orchestrator: please confirm, and update the brief's "API on Modal" if you agree.

# WS8 status

Owner: claude-work · Directories: `deploy/`, `web/src/api.ts`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 00:57 UTC-5 (clock checked; earlier versions of this line were mis-stamped) · branch `feat/ws8-deploy` (origin/develop merged, PR #14 included) ·
committed locally, the orchestrator pushes.

## Done

- `deploy/modal_app.py`: `api/app.py` on Modal (CPU, `@modal.asgi_app`, `@modal.concurrent(20)`).
  - The image holds only `api/`, `agents/`, `src/radar/`, `contracts/` and `reports/`; never `.env`.
  - Volume `radar-lake` is mounted at `/lake`, with `RADAR_PROFILE=full` and `RADAR_LAKE=/lake`.
  - The Nebius key comes from the Modal Secret `radar-nebius`. `RADAR_NEBIUS_SECRET=0` runs without
    it, and then `/api/chat` answers 503.
- `deploy/push_lake.py`: uploaded the 7 tables to the Volume (approved), never `edges_weekly`.
  81.8 MiB in about 20 s (measured):
  - `topic_scores_weekly` 1.1 MiB
  - `topic_daily` 28.9 MiB
  - `topic_context_1hop` 32.8 MiB
  - `daily_topic` 3.7 MiB
  - `daily_topic_rolling` 4.8 MiB
  - `daily_totals` 0.0 MiB
  - `node_metrics_weekly` 10.4 MiB
- `modal serve` (approved, without the Secret): the image built in 4.7 s, but no container ever started.
  - Two requests answered 303 after 150.5 s each (Modal's long-request redirect).
  - A third request timed out at 100 s while `modal container list` showed no `radar-api` container.
  - The app was stopped afterwards (ephemeral, 0 tasks).
- The same configuration was run locally as a stand-in, labelled **local, not Modal**: uvicorn with
  `RADAR_PROFILE=full` over a lake holding only the 7 uploaded tables. Latency (measured, local):

  | Endpoint | Status | Time |
  |---|---|---|
  | `/api/radar` first request | 200 | 113 ms |
  | `/api/radar` warm | 200 | 11–12 ms |
  | `/api/freshness` | 200 | 13 ms |
  | `/api/topic/org:nvidia/timeline` | 200 | 43 ms, 131 KB |
  | `/api/topic/org:nvidia/context` | 200 | 24 ms |
  | `/api/chat` without a key | 503 | — |

- `deploy/export_static.py` writes `web/public/data/` (git-ignored) through the real API handlers, so
  the static files are the API's bodies. It refuses unless `RADAR_PROFILE=full`; the unit test for
  the refusal passes.
  - Run on the full lake (measured, 6.4 s, 5.09 MiB): 46 weekly top 10s (0.41 MiB); 58 timelines
    (4.38 MiB: the topics in a top 10 of the last 4 weeks, the 12 subtopics, `ai_all` and the UI's
    default entities); 45 rings × 5 weeks (0.30 MiB).
- `web/src/api.ts`: the read panels call the live API first. They switch to the static files for the
  rest of the session on a network error or a 5xx, always with `VITE_DATA_MODE=static`, and in a
  production build without `VITE_API_BASE_URL`.
  - Chat never flips the session (its 503 only means "no key"); in static mode it says the chat
    needs the live API.
  - Checked: `bun run build` passes. `vite preview` with no API running (the proxy answers 500)
    renders the full-lake top 10 (2026-W42) and the freshness chips from the static files, seen in
    a headless Chrome screenshot.
- `deploy/README.md`: the maintainer's commands in order (Secret, lake, serve/deploy, static, web
  build, Netlify).
- `Makefile`: `deploy-push-lake`, `deploy-serve`, `deploy-api`, `deploy-static`, `deploy-web`.
  `.env.example`: `NETLIFY_SITE_ID=` (empty).
- `pyproject.toml`: a `deploy` extra (`modal>=1.0`, in `uv.lock`), and `deploy` added to pytest
  `testpaths` so the refusal test runs in `make test`. That last line is outside the "deploy extra"
  wording of the brief, but the acceptance needs it.

- Cloud Run: `deploy/cloudrun/Dockerfile` and `deploy/cloudrun_stage.py`, which stages
  `build/cloudrun/`: the code the API imports, `contracts/`, `reports/` and the 7 tables
  (81.9 MiB). It refuses to stage `.env` or `edges_weekly`. Make targets: `deploy-cloudrun-stage`,
  `deploy-cloudrun-local`, `deploy-cloudrun`.
  - Local Docker test of the image (measured): built in 39 s, 761 MB. Every request returned 200:
    `/api/freshness` 20 ms, `/api/radar` 72 ms then 21 ms warm, `/api/radar?week=2026-W41` 20 ms,
    nvidia timeline 51 ms, ring 26 ms, `regulation_policy` timeline 36 ms. `/api/chat` without a
    key: 503. No `.env` in the image (checked).

- **Deployed on Cloud Run** (approved by the maintainer in chat). Service `radar-api`, us-central1,
  1 CPU, 1 GiB, 0–3 instances, public (`--allow-unauthenticated`). `NEBIUS_API_KEY` comes from the
  Secret Manager secret `radar-nebius-key`, created from `.env` without being printed; only the
  compute service account can read it.
  - The URL stays out of git (it holds the project number). Get it with
    `gcloud run services describe radar-api --region us-central1 --format='value(status.url)'`.
  - Deploy (source upload, Cloud Build, revision): 2 min 20 s (measured).
  - Latency measured from the maintainer's laptop (UTC-5), so it includes the network round trip:

    | Request | Status | Time |
    |---|---|---|
    | First `/api/radar` after the deploy (cold start) | 200 | 1.74 s |
    | Warm `/api/radar` | 200 | 0.32–0.35 s |
    | `/api/freshness` | 200 | 0.43 s |
    | `/api/radar?week=2026-W41` | 200 | 0.32 s |
    | nvidia timeline | 200 | 0.94 s, 131 KB |
    | nvidia ring | 200 | 0.68 s |
    | One `/api/chat` turn ("¿Qué tema de IA sube esta semana y por qué?") | 200 | 10.3 s |

  - The chat turn returned `answer_es`, decision cards, view commands and an 8-step trace.
  - CORS: GET answers with `access-control-allow-origin: *`.
  - A true cold start after a scale-to-zero (about 15 min idle) has not been measured yet.

- **Netlify, live and public:** site `radar-senal-temprana` (team `aleonardobecerra`, free plan),
  https://radar-senal-temprana.netlify.app, with "Make public" clicked by the maintainer.
  - Built with `make deploy-static` (5.09 MiB) and `VITE_API_BASE_URL=<Cloud Run URL>`, giving a
    6.4 MB `web/dist`.
  - Deploys (measured): draft 16 s, production 7 s. Both answered 401 until "Make public".
  - The site id is in the git-ignored `.env` (`NETLIFY_SITE_ID`). The CLI's `.netlify/` folder was
    removed; nothing was linked or committed.
  - Checks (measured): `/`, `/data/radar/latest.json`, `/data/freshness.json` and
    `/data/timeline/org_nvidia.json` all return 200 (0.32–0.71 s), and the bundle calls the Cloud
    Run API.
  - A headless-Chrome screenshot of the public URL shows the 2026-W42 cards. Its freshness strip
    reads `edges_weekly: pendiente`, which only the live Cloud Run API returns (the static copy has
    a date), so the page reads live data.
  - Redeploy after a lake rebuild: `make deploy-cloudrun`, `make deploy-static`,
    `make deploy-web API_URL=<Cloud Run URL>`, then
    `npx netlify-cli deploy --dir web/dist --site $NETLIFY_SITE_ID --prod`.

- **Chat rate limit (addendum 00:50), live in revision `radar-api-00002`.** In `api/app.py`: 10 turns
  per 10 minutes per client IP and 500 turns per UTC day in total, set with `RADAR_CHAT_PER_CLIENT`,
  `RADAR_CHAT_WINDOW_S` and `RADAR_CHAT_DAILY_CAP`.
  - Over the limit the API answers HTTP 429 with a Spanish message (the chat panel shows it) and
    `Retry-After`.
  - The client IP is the last `X-Forwarded-For` hop, so a client cannot reset its limit by sending
    its own header. Refused turns do not count. A missing key answers 503 without spending quota.
  - The counters are in memory, one set per instance: up to 3x the limits with 3 instances (in the
    runbook).
  - 8 offline tests, all passing. One sends 10 demo questions with the default limits: all 10
    answer 200, none blocked (measured with a scripted model).
  - Before the 01:20 addendum, a local container with a limit of 2 answered the 3rd call with 429,
    the Spanish detail and `Retry-After: 599` (measured).
  - Live after the redeploy (measured): `/api/radar` 200 (1.98 s cold, 0.31 s warm),
    `/api/freshness` 200, one chat turn 200 in 13.6 s with an 8-step trace. A live 429 was not
    triggered: it would spend 10 real Nebius turns.
- Merged `origin/develop` (LangSmith agents, labels cascade): `uv.lock` was regenerated and
  `.env.example` keeps both blocks.
  - The agents now import `langsmith`. The image's packages are now read from `pyproject.toml`
    (core + `api` extra), so the redeploy carries it.
- Addendum 01:20 (memory): the redeploy built with Cloud Build (`gcloud run deploy --source`, 2 min
  29 s) and Docker Desktop was quit. The two local container tests ran before I read the addendum.

- **Redeploy on WS4's signal (READY FOR REDEPLOY, 00:52).** Built with Cloud Build, no local Docker.
  - Revision `radar-api-00002` (00:51) was staged one minute before WS4 wrote its final
    `topic_scores_weekly` (00:50:27), so it carried an intermediate file (checksums differed).
  - Revision `radar-api-00003` (00:55, 1 min 52 s) was built from the final file (checksum checked).
  - The static export (7.10 MiB) and Netlify production deploy (16 s) ran on the final file too.
  - Checked at 00:56 (measured): the public W42 top 10 is identical on Cloud Run `/api/radar` and in
    Netlify's `/data/radar/latest.json`: marsh mclennan, euronext, adani enterprises, rocket lab,
    national stock exchange, ministry of science, kioxia holdings, sterling, citigroup, yahoo.
    `org:scam centre` and `org:capital markets department` are gone from both. The site answers 200.
  - Lesson: stage the image only after WS4's signal and check the scores checksum against the lake.

## Waits for approval or for the maintainer

1. Done (Cloud Run secret and deploy).
2. (Alternative only) Fix Modal billing, create the Modal Secret `radar-nebius`, then `modal deploy`.
3. Done (Netlify site, production deploy, "Make public").

## For other lanes

- WS5: `isStaticMode()` in `web/src/api.ts` can drive a "datos estáticos" badge; CORS in
  `api/app.py` allows every origin (narrow it to the Netlify origin if wanted).
- WS4: the live chat's first decision card names `org:big news network` (a news outlet) as a
  topic. It is worth adding to `ranked_universe.org_deny`, like the other outlets.
- WS4: the 2026-W42 top 10 holds `org:scam centre`, `org:national anti`,
  `org:capital markets department` and `org:technological development area`. They look like GKG
  extraction artefacts, worth a deny-list check.

## Numbers (each marked measured or estimate)

All in "Done" above, each marked measured. Modal cost: image builds only, no container ran
(measured: 0 tasks).
