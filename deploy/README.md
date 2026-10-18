# Deploy (WS8): the API on Cloud Run, the UI on Netlify, a static fallback

**Platform (2026-10-18, approved by the maintainer):** the API runs on **Google Cloud
Run** in the GCP project that already runs BigQuery (billing enabled, measured). Modal stays as an
alternative (`modal_app.py`), but the Modal workspace starts no container until its billing is fixed.

One URL for the judges: the Netlify site. It calls the live API on Cloud Run when one is configured and
reachable, and otherwise reads the static export bundled with the site (`web/public/data/`). The chat
needs the live API; every other panel works from the static files.

| File | What it does |
|---|---|
| `cloudrun/Dockerfile`, `cloudrun_stage.py` | The API image for Cloud Run: `cloudrun_stage.py` stages `build/cloudrun/` (the code the API imports, `contracts/`, `reports/` and the 7 lake tables; never `.env` or `edges_weekly`) |
| `modal_app.py` | `api/app.py` on Modal: CPU, `@modal.asgi_app`, Volume `radar-lake` at `/lake`, `RADAR_PROFILE=full`, Secret `radar-nebius` |
| `push_lake.py` | Uploads the 7 tables the API reads (81.8 MiB, measured) to the Volume; never `edges_weekly` |
| `export_static.py` | Writes `web/public/data/` from the full lake through the real API handlers; refuses unless `RADAR_PROFILE=full` |
| `web/src/api.ts` | Live API first; on a network error or 5xx (or with no API URL in a production build) it reads the static files |

## Before you start

- Modal: `modal profile current` shows the workspace. **The workspace needs a working payment
  method**: without one (or while billing is paused) Modal builds images but starts no container,
  even on CPU, while existing deployments keep serving. That is what happened on 2026-10-18 (see
  `status/WS8.md`).
- Netlify: `npx netlify login` (maintainer). A new site answers 401 until "Make public" is clicked in
  the site settings; always deploy with `--site <id>`.
- The full lake is in `lake/gold/` (`RADAR_PROFILE=full uv run pytest -m data` passes).

## Commands, in order (Cloud Run)

```bash
P=$(grep '^GCP_PROJECT_ID=' .env | cut -d= -f2)   # the radar GCP project, never written in git
gcloud config set project $P

# 1. The Nebius key in Secret Manager (maintainer; read from .env without printing it)
grep '^NEBIUS_API_KEY=' .env | cut -d= -f2- | tr -d '\n' | \
  gcloud secrets create radar-nebius-key --data-file=- --replication-policy=automatic
gcloud secrets add-iam-policy-binding radar-nebius-key \
  --member="serviceAccount:$(gcloud projects describe $P --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor

# 2. Test the image locally (Docker), then deploy (public URL: approval)
make deploy-cloudrun-local            # http://127.0.0.1:18080/api/freshness
make deploy-cloudrun                  # prints https://radar-api-<hash>-uc.a.run.app

# 3. The static fallback, then the web build pointing at the API
make deploy-static                    # web/public/data/, ~5 MiB (measured), git-ignored
make deploy-web API_URL=https://radar-api-<hash>-uc.a.run.app
#    or static only (no API):  make deploy-web API_URL=

# 4. Netlify (maintainer: login, site creation, "Make public")
npx netlify sites:create --name <site-name>        # once; note the site id
npx netlify deploy --dir web/dist --site <site-id> # draft URL to check
npx netlify deploy --dir web/dist --site <site-id> --prod
```

Re-run `make deploy-cloudrun` (it re-stages the lake tables) and step 3 whenever the lake is rebuilt,
and only after the lake writer has finished: a table rewritten mid-stage ships an old copy
(compare `md5 lake/gold/topic_scores_weekly.parquet build/cloudrun/lake/gold/topic_scores_weekly.parquet`).

### Modal (alternative, blocked by the workspace's billing on 2026-10-18)

```bash
uv run --extra deploy modal secret create radar-nebius NEBIUS_API_KEY=<paste the key>
make deploy-push-lake                 # the 7 tables to the Volume radar-lake
make deploy-serve                     # temporary URL; make deploy-api for a stable one
```

`make deploy-serve` (Modal) runs without the Secret (`RADAR_NEBIUS_SECRET=0`): the read endpoints
answer and `/api/chat` returns 503, as the API does locally without a key.

## Cold starts and a warm instance for the demo (maintainer's decision)

Cloud Run scales `radar-api` to zero after about 15 minutes without requests, so the first visitor
afterwards waits for a container to start. Measured cold start: see `status/WS9.md`
(`uv run python deploy/cold_start.py --chat` waits for idle and repeats the measurement).

To keep one instance warm, and to stop it again afterwards:

```bash
P=$(grep '^GCP_PROJECT_ID=' .env | cut -d= -f2)
gcloud run services update radar-api --region us-central1 --project "$P" --min-instances=1   # on
gcloud run services update radar-api --region us-central1 --project "$P" --min-instances=0   # off
gcloud run services describe radar-api --region us-central1 --project "$P" \
  --format='value(spec.template.metadata.annotations."autoscaling.knative.dev/minScale")'     # check
```

Each update creates a new revision of the same image; it does not rebuild anything.
`make redeploy-all` (and `make deploy-cloudrun MIN_INSTANCES=…`) keeps the current setting, so a
redeploy does not switch the warm instance off.

**Cost (estimate)** comes from Cloud Run's published pricing (https://cloud.google.com/run/pricing,
"Services (Requests-based billing)", Tier 1 / us-central1, default USD, read 2026-10-18).

| Rate | Price |
|---|---|
| CPU, idle minimum instance | $0.0000025 per vCPU-second |
| Memory, idle minimum instance | $0.0000025 per GiB-second |
| CPU, active | $0.000024 per vCPU-second |
| Memory, active | $0.0000025 per GiB-second |

With this service's 1 vCPU and 1 GiB:

| Instance state | Cost per hour (estimate) |
|---|---|
| Idle warm instance | (0.0000025 + 0.0000025) × 3,600 ≈ **$0.018** |
| Serving requests | (0.000024 + 0.0000025) × 3,600 ≈ $0.095 |

The monthly free tier (180,000 vCPU-seconds and 360,000 GiB-seconds of request-based billing,
per billing account) may cover these hours entirely (estimate: it depends on other usage on the
account).

**When to use it:**

| Window | Turn on | Turn off | Cost (estimate, idle) |
|---|---|---|---|
| Rehearsal and submission, Sun 2026-10-18 | 09:00 UTC-5 | 12:30 UTC-5 | ≈ $0.06 |
| The 30X demo, Tue 2026-10-20 | 30 min before | right after | ≈ $0.02-0.04 |

Outside those windows leave it at 0. The static fallback still serves every panel except the chat
if the API is slow to wake.

## Notes

- Chat rate limit (`api/app.py`): 10 turns per 10 minutes per client IP and 500 turns per UTC day in
  total. Over the limit the API answers HTTP 429 with a Spanish message (shown in the chat panel) and
  `Retry-After`. Configure with `RADAR_CHAT_PER_CLIENT`, `RADAR_CHAT_WINDOW_S` and
  `RADAR_CHAT_DAILY_CAP` (for example `gcloud run services update radar-api --update-env-vars
  RADAR_CHAT_DAILY_CAP=300`). The counters live in memory, one set per instance; with Cloud Run's
  3 instances at most, the effective limits are up to 3x the configured ones. The client IP is the
  last `X-Forwarded-For` entry (the one Cloud Run appends), so a client cannot reset its limit by
  sending its own header.
- The image's Python packages come from `pyproject.toml` (core + `api` extra) at stage time, so a new
  dependency of `agents/` (for example `langsmith`) reaches the image without editing `deploy/`.

- CORS: `api/app.py` (WS5) allows every origin, so the Netlify origin works. Narrowing it to the
  site's origin is a WS5 change.
- The static export holds the top 10 of every scored week, the timelines of every topic in a top 10
  of the last 4 weeks plus the 12 subtopics and `ai_all`, and the 1-hop rings of those topics for the
  last 4 weeks. A topic outside that set shows an empty timeline or ring in static mode.
- `isStaticMode()` in `web/src/api.ts` tells the UI it is on the static export, so WS5 can show a
  badge.
