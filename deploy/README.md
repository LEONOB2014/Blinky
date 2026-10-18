# Deploy (WS8): the API on Cloud Run, the UI on Netlify, a static fallback

**Platform (2026-10-18 00:40 UTC-5, approved by the maintainer):** the API runs on **Google Cloud
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

Re-run `make deploy-cloudrun` (it re-stages the lake tables) and step 3 whenever the lake is rebuilt.

### Modal (alternative, blocked by the workspace's billing on 2026-10-18)

```bash
uv run --extra deploy modal secret create radar-nebius NEBIUS_API_KEY=<paste the key>
make deploy-push-lake                 # the 7 tables to the Volume radar-lake
make deploy-serve                     # temporary URL; make deploy-api for a stable one
```

`make deploy-serve` (Modal) runs without the Secret (`RADAR_NEBIUS_SECRET=0`): the read endpoints
answer and `/api/chat` returns 503, as the API does locally without a key.

## Notes

- CORS: `api/app.py` (WS5) allows every origin, so the Netlify origin works. Narrowing it to the
  site's origin is a WS5 change.
- The static export holds the top 10 of every scored week, the timelines of every topic in a top 10
  of the last 4 weeks plus the 12 subtopics and `ai_all`, and the 1-hop rings of those topics for the
  last 4 weeks. A topic outside that set shows an empty timeline or ring in static mode.
- `isStaticMode()` in `web/src/api.ts` tells the UI it is on the static export, so WS5 can show a
  badge.
