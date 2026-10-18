# AGENTS.md

Instructions for coding agents (Claude Code, Gemini CLI, Grok CLI) and humans working on this
repository: **Radar de Señal Temprana**, the early-signal radar that tells 30X which AI topics are
about to land on LinkedIn, why, and from which emotional angle to tell them to LatAm executives
(Reto 30X "Radar de contenido"). This file is the canonical source of repository standards;
`CLAUDE.md` and `GEMINI.md` import it. The plan is [`docs/plan/MASTER_PLAN.pdf`](docs/plan/MASTER_PLAN.pdf)
(single source of truth); procedures too long for this file live in [`docs/development/`](docs/development/).

## Project map

| Path | Workstream | Owner | What it is |
|---|---|---|---|
| `contracts/`, `mocks/` | WS0 | lead | Data and API contracts (JSON Schema, `api.yaml`, `taxonomy.yaml`) and their mocks |
| `bq_sql/` | WS0 / WS1 | lead | BigQuery scripts Q1–Q4 and S1–S10 |
| `pipelines/ingest/` | WS1 | claude-work | `run_bq.py` (dry run, cap, ledger), exports to Parquet, raw-file poller, DQ |
| `pipelines/taxonomy/` | WS2 | claude-extend | Labeling functions, LLM labels, embeddings routing, gold set |
| `graph/` | WS3 | claude-home | Weekly co-occurrence graphs, metrics, GPU tier-1 layout, story-view JSON |
| `models/` | WS4 | claude-cacho | Six scores, sentiment, LightGBM + SHAP backtest |
| `models/tgnn/` | WS7 | claude-extend | TGNN stretch (gated, never blocks WS4) |
| `api/`, `web/` | WS5 | Gemini CLI | FastAPI over DuckDB (Modal), Lovable UI (Netlify) |
| `entity/`, `crosssource/` | WS6 | Grok CLI | Wikidata resolution, HN / Wikipedia / X / YouTube lead-lag |
| `src/radar/` | all | lead | Shared helpers: lake paths, contract validation |
| `status/` | all | each WS | `WS<N>.md`, updated before every sync |
| `reports/` | all | each WS | Evidence: `bq_ledger.csv`, backtest, label quality, TGNN go/no-go |
| `lake/` | all | — | Parquet outputs, **never in git** |

Work only in your workstream's directory. Anything outside it (the shared core, CI, contracts)
goes through a PR the lead reviews.

## Commands

```bash
make setup                        # uv env + pre-commit and commit-msg hooks + .env from template
uv sync --extra bq                # add your workstream's extra: bq, labels, graph, models, api, crosssource
make test                         # tests that need no network, BigQuery or lake (what CI runs)
make test-ws                      # contracts are valid and every mock matches its contract
make worktree BRANCH=feat/ws1-run-bq   # new worktree from the latest origin/develop
uv run pre-commit run --all-files # the full quality gate, identical to CI
```

Run the relevant tests and the hooks before every commit. A failing hook is a real failure:
fix the cause, never bypass it (`--no-verify` is forbidden).

## Hackathon rules (from the plan, §15.1)

- **Contracts first.** Read `contracts/` before writing code; write outputs exactly as the
  contracts say. Never change a contract without a PR to the lead. Mocks exist from minute one,
  so nobody waits on another workstream.
- **Numbers are evidence.** Every number in code comments, reports, PRs and the UI is marked
  *(measured)* or *(estimate)*. Report denominators and intervals. When the data shows no signal,
  say so; never fabricate a signal or synthetic data to make a result look good.
- **Never zero-fill missing days.** `is_missing` days are `NULL`.
- **BigQuery spend is guarded.** Every job is dry-run first, aborts above 1.5× the ledger
  estimate, and logs its bytes billed to `reports/bq_ledger.csv`. Default cap 50 GiB; raising it
  needs the lead's approval for that one job.
- **Terms of service.** Public content only, no personal data, no scraping or ToS-violating
  techniques, nothing behind third-party logins (plan §3). LinkedIn is never scraped.
- **Status.** Update `status/WS<N>.md` before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Branching model

- `main`: **demo / production**. Changes only through merged release or hotfix pull requests.
- `develop`: **integration**. Every workstream lands here first and is tested here.
- Work branches are short-lived (a few hours), named `<type>/ws<N>-<short-description>` with a
  Conventional Commits type and a kebab-case description: `feat/ws1-run-bq`,
  `feat/ws3-story-view`, `fix/ws5-freshness-badge`, `docs/ws0-contracts`.
- Work branches start from the **latest `develop`** and merge back into `develop` by PR.
- `release/vX.Y.Z` starts from `develop` and merges into `main`; `hotfix/<desc>` starts from
  `main` and merges into `main`, then back into `develop`. See [releasing](docs/development/releasing.md).
- **Never commit on `main` or `develop`, locally or remotely.** The `no-commit-to-branch` hook
  refuses it locally. The repository stays **private until the submission** (Sun Oct 18, 12:00
  UTC-5); on a free plan GitHub cannot enforce branch protection on a private repo, so the hook
  is the guard. Making the repo public is a maintainer action at submission time.

## Worktrees: one per branch

Several agents work at once, so every branch is checked out in its own git worktree.

```bash
git fetch origin
git worktree add -b feat/ws1-run-bq ../radar-worktrees/feat-ws1-run-bq origin/develop
cd ../radar-worktrees/feat-ws1-run-bq
ln -s ../../radar/lake lake          # shared, git-ignored lake (see Data)
```

- The main checkout (`radar/`) stays on `main`, is **read-only**, and is only ever fast-forwarded
  (`git pull --ff-only`). It hosts the shared `lake/` and the local `.env`.
- Remove a worktree after its PR is merged (`git worktree remove <path>`); keep the branch.
- Details: [git workflow](docs/development/git-workflow.md).

## Commits

[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), enforced by
commitizen at the `commit-msg` hook.

```
<type>(<optional scope>)<optional !>: <description>

<optional body: why, wrapped at 72 characters>

<optional footers, e.g. BREAKING CHANGE: ..., Refs: #12>
```

- **Types**: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build` (dependencies,
  packaging), `ci`, `chore`, `style`, `revert`.
- **Scopes** (the area touched): `contracts`, `bq`, `ingest`, `taxonomy`, `labels`, `graph`,
  `viz`, `scores`, `sentiment`, `backtest`, `tgnn`, `entity`, `crosssource`, `api`, `web`,
  `deploy`, `ci`, `deps`, `release`. Omit the scope when a change spans the repository.
- **Description**: imperative, lowercase, no trailing period, at most 72 characters.
- **Breaking changes** (a contract change is one): `!` before the colon and a
  `BREAKING CHANGE:` footer explaining the migration.
- One logical change per commit; never mix a refactor with a behaviour change.
- Pass multi-line messages with `git commit -F <file>`.

```
feat(ingest): log bytes billed per job to the bq ledger
fix(graph): mask gap weeks before computing degree growth
feat(contracts)!: add controversy_7d to daily_topic_rolling

BREAKING CHANGE: consumers of daily_topic_rolling must read the new column.
```

## Pull requests

- Title: a Conventional Commit header (checked by CI). Body: the
  [template](.github/pull_request_template.md).
- Base `develop` for work branches; `main` only for `release/*` and `hotfix/*`.
- CI must be green before merging. The merge captain merges; **squash** for small or
  fix-up-heavy PRs, **merge commit** for a series worth keeping. Never rebase shared branches.
- **Never delete branches** after merging.

## Versioning and releases

[SemVer 2.0.0](https://semver.org/), **0.x until the submission**: each release bumps MINOR,
fixes bump PATCH. Releases are cut with commitizen at sync points (the 09:00 demo freeze is a
release), which updates the version and [`CHANGELOG.md`](CHANGELOG.md), then tagged `vX.Y.Z` on
`main`. Procedure: [releasing](docs/development/releasing.md).

## Data

- Data never enters git: Parquet, DuckDB files, JSONL labels, model caches, graph exports.
- One shared `lake/` lives in the main checkout; worktrees symlink to it.
- Code finds it through `RADAR_LAKE` (default `<repo>/lake`), via `radar.paths`, never through
  hardcoded machine paths.
- Small, reviewed outputs are the exception: `reports/*.md`, `reports/bq_ledger.csv`, mocks,
  and `web/public/data/*.json` for the static fallback. Details: [data and secrets](docs/development/data-and-secrets.md).

## Secrets

- Secrets live only in the git-ignored `.env` (from `.env.example`). Never commit, print, log or
  paste secret values, including in PR bodies, status files and chat.
- New configuration keys go into `.env.example` with an empty value.
- `detect-secrets` runs on every commit. A finding is never silenced on an agent's own authority:
  confirm it is a placeholder, then ask the maintainer before changing `.secrets.baseline`.

## Agent conduct

- Ask before destructive or outward-facing actions: pushes, merges into `main`, deleting data,
  raising BigQuery caps, paid runs (Modal GPU, LLM labeling, X API), editing GitHub settings.
- Prefer the smallest change that fully solves the task; follow existing patterns.
- Report outcomes faithfully: say what was tested, what failed and what was skipped.
- Keep this file current: when a rule changes, change it here in the same PR.
