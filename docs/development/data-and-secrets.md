# Data and secrets

## Data

Nothing under `lake/` is ever committed. Everything in it is reproducible from `bq_sql/` and the
workstream scripts.

**Where it lives.** One shared `lake/` in the main checkout (`radar/lake`). Worktrees symlink to it
(`make worktree` does it), so every branch reads the same files without copying them. The root
`.gitignore` ignores `/lake` (no trailing slash, so the symlink is ignored too).

**How code finds it.** Through `radar.paths.lake()` and `radar.paths.gold(name)`, which read
`RADAR_LAKE` and default to `<repo>/lake`. Never hardcode a machine path.

**Layout.** `lake/raw/` (poller files), `lake/silver/`, `lake/gold/<table>.parquet` (the tables in
`contracts/`), `lake/labels/` (JSONL), `lake/viz/` (graph exports).

**Committed exceptions.** Small, reviewed outputs only: `reports/*.md`, `reports/*.csv`, `mocks/`,
and `web/public/data/*.json` for the static fallback. Anything over 1 MB is refused by the
`check-added-large-files` hook.

## BigQuery spend

- Guardrails: maximum bytes billed 50 GiB per job, daily quota 0.7 TiB, budget alerts at $1, $25
  and $50 (plan §20).
- Every job is dry-run first and aborts above 1.5× the ledger estimate; its bytes go to
  `reports/bq_ledger.csv`.
- Raising the cap (GCAM S7: 150 GiB) is approved by the lead for that one job, then restored.

## Secrets

| File | Holds | Created from |
|---|---|---|
| `.env` (root, main checkout) | GCP project, LLM, X, YouTube, Graphistry keys | `.env.example` |

- `.env*` files are git-ignored (except `.env.example`) and kept with mode `600`. Worktrees copy
  it with `cp -p ../../radar/.env .env`.
- BigQuery authenticates with `gcloud auth application-default login`; service-account JSON files
  are git-ignored and never needed.
- Never print, log, paste or commit a secret value. Refer to secrets by variable name.
- Every new key is added to `.env.example` with an empty value.
- `detect-secrets` scans every commit against `.secrets.baseline`. When it flags something,
  confirm it is a placeholder, then ask the maintainer before updating the baseline.
- A real secret that reaches a commit is rotated first, then removed from history with the maintainer.
