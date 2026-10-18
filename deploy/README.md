# Deploy (WS8): the API on Modal, the UI on Netlify, a static fallback

One URL for the judges: the Netlify site. It calls the live API on Modal when one is configured and
reachable, and otherwise reads the static export bundled with the site (`web/public/data/`). The chat
needs the live API; every other panel works from the static files.

| File | What it does |
|---|---|
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

## Commands, in order

```bash
# 1. The Nebius key as a Modal Secret (maintainer; the value never goes into a file in git)
uv run --extra deploy modal secret create radar-nebius NEBIUS_API_KEY=<paste the key>

# 2. The lake tables to the Volume (approved: public GDELT aggregates, no titles, URLs or persons)
make deploy-push-lake                 # RADAR_PROFILE=full; add --dry-run to the script to list only

# 3. Try the API on a temporary URL, then deploy it (deploy = stable public URL: approval)
make deploy-serve                     # prints https://<workspace>--radar-api-web-dev.<region>.modal.run
curl -s <serve-url>/api/freshness     # profile "full", newest week per table
make deploy-api                       # prints https://<workspace>--radar-api-web.<region>.modal.run

# 4. The static fallback, then the web build pointing at the API
make deploy-static                    # web/public/data/, ~5 MiB (measured), git-ignored
make deploy-web API_URL=https://<workspace>--radar-api-web.<region>.modal.run
#    or static only (no API):  make deploy-web API_URL=

# 5. Netlify (maintainer: login, site creation, "Make public")
npx netlify sites:create --name <site-name>        # once; note the site id
npx netlify deploy --dir web/dist --site <site-id> # draft URL to check
npx netlify deploy --dir web/dist --site <site-id> --prod
```

Re-run steps 2 and 4 (and 3 for a code change) whenever the lake is rebuilt. `make deploy-serve`
without the Secret runs with `RADAR_NEBIUS_SECRET=0`, so the read endpoints answer and `/api/chat`
returns 503, as the API does locally without a key.

## Notes

- CORS: `api/app.py` (WS5) allows every origin, so the Netlify origin works. Narrowing it to the
  site's origin is a WS5 change.
- The static export holds the top 10 of every scored week, the timelines of every topic in a top 10
  of the last 4 weeks plus the 12 subtopics and `ai_all`, and the 1-hop rings of those topics for the
  last 4 weeks. A topic outside that set shows an empty timeline or ring in static mode.
- `isStaticMode()` in `web/src/api.ts` tells the UI it is on the static export, so WS5 can show a
  badge.
