# AGENTS.md

Instructions for coding agents (Claude Code, Gemini CLI, Grok CLI) and humans working on this
repository: **Radar de Señal Temprana**, the early-signal radar that tells 30X which AI topics are
about to land on LinkedIn, why, and from which emotional angle to tell them to LatAm executives
(Reto 30X "Radar de contenido"). This file is the canonical source of repository standards;
`CLAUDE.md` and `GEMINI.md` import it. The plan is [`docs/plan/MASTER_PLAN.md`](docs/plan/MASTER_PLAN.md)
(living, single source of truth; the original [PDF](docs/plan/MASTER_PLAN.pdf) stays); procedures too long for this file live in [`docs/development/`](docs/development/).

## Project map

| Path | Workstream | Account | Agent it implements | What it is |
|---|---|---|---|---|
| `contracts/`, `mocks/`, `fixtures/dev/` | WS0 | orchestrator (this repo's lead Claude) | — | Contracts, mocks copied from real output, the real dev slice |
| `agents/` | WS0 | orchestrator | Media Master + runtime tools | Multi-agent runtime (Qwen3-30B on Nebius), decision cards, view commands, traces |
| `bq_sql/`, `pipelines/ingest/` | WS1 | Claude #2 | Scout | BigQuery jobs (dry run, cap, ledger), backfill, exports, DQ |
| `pipelines/taxonomy/` | WS2 | Claude #2 | Curator | Segments, subtopics, labels, filter P/R |
| `models/` | WS4 | Claude #3 | Signal analyst, Audience strategist | Six scores, window, decision, backtest, editor-test sheet |
| `graph/` | WS3 | Claude #4 | Cartographer | Graph metrics, 1-hop ring; the graph views last (after the gate) |
| `models/tgnn/` | WS7 | Claude #4 | — | Baseline table only (EdgeBank, persistence) |
| `entity/`, `crosssource/` | WS6 | Grok CLI | Scout (cross-source) | Wikidata, Wikipedia pageviews (the backtest label), HN, YouTube |
| `api/`, `web/` | WS5 | Gemini (Antigravity) | — | FastAPI over DuckDB, a plain contract-driven UI with chat and trace panels; Lovable restyles it later |
| `reports/` | all | each WS | Auditor | Evidence: `bq_ledger.csv`, backtest, label quality |
| `src/radar/` | all | orchestrator | — | Shared helpers: lake paths, profiles, contract validation |
| `status/` | all | each WS | — | `WS<N>.md`, updated before every sync |
| `lake/` | all | — | — | Parquet outputs, **never in git** |

The agents are defined in [`contracts/agents.yaml`](contracts/agents.yaml): each owns part of the
system, its tools and a decision log. Code computes every decision; the LLM explains it.

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

- `main`: **demo / production**. Changes only through the `develop` → `main` pull request,
  which is the release.
- `develop`: **integration**. Every workstream lands here first and is tested here.
- Work branches are short-lived (a few hours), named `<type>/ws<N>-<short-description>` with a
  Conventional Commits type and a kebab-case description: `feat/ws1-run-bq`,
  `feat/ws3-story-view`, `fix/ws5-freshness-badge`, `docs/ws0-contracts`.
- Work branches start from the **latest `develop`** and merge back into `develop` by PR.
- There are no `release/*` or `hotfix/*` branches. A fix for `main` lands on `develop` first and
  reaches `main` with the next release PR. See [releasing](docs/development/releasing.md).
- **Never commit on `main` or `develop`, locally or remotely.** The `no-commit-to-branch` hook
  refuses it locally. The repository stays **private until the submission** (Sun Oct 18, 12:00
  UTC-5); on a free plan GitHub cannot enforce branch protection on a private repo, so the hook
  is the guard. Making the repo public is a maintainer action at submission time.

## Orchestrator and executors

- **One Claude account is the orchestrator.** It creates every worktree and writes its `BRIEF.md`
  (committed as the branch's first commit), owns `contracts/` and this file, reviews each PR against
  its brief, merges into `develop` and cuts releases. It may also execute tasks in its own worktrees.
- **Every other account is an executor.** It reads only `AGENTS.md` and its `BRIEF.md`, touches only
  the files the brief lists, runs the brief's acceptance commands, updates `status/WS<N>.md` and opens
  the PR. When something outside the brief is needed, it writes `BLOCKED: <reason>` in its status file
  and stops; it never improvises.
- `BRIEF.md` sections: Goal · Plan reference · Inputs · Outputs · Files you may touch · Out of scope ·
  Steps · Acceptance · Paid or outward actions needing approval · Report · If blocked.
- The design behind this: [docs/designs/radar-build-plan.md](docs/designs/radar-build-plan.md).

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
- Base `develop` for work branches; `main` only for the `develop` → `main` release PR.
- CI must be green before merging. The orchestrator merges; **squash** for small or
  fix-up-heavy PRs, **merge commit** for a series worth keeping. Never rebase shared branches.
- **Never delete branches** after merging.

## CI and the Actions-minutes budget

GitHub Actions minutes are scarce for this repository (private repos bill every job rounded up to a
whole minute). So:

- CI is **one job**, on **pull requests into `develop` or `main` only**. Pushes, including merges
  into `develop`, do not run CI. Draft PRs and PRs that touch only `*.md`, `docs/`, `status/` or
  `reports/` do not run CI.
- **The gate runs locally first:** `make check && make test` must pass before a PR is opened or
  updated. CI is the last check, not the place to find failures.
- **Open a PR as a draft** while work continues; mark it ready once, when the local gate passes.
  Every push to a ready PR costs a run, so push fixes in one batch.
- Ask the maintainer before opening a PR, marking one ready or re-running a workflow.

## Versioning and releases

[SemVer 2.0.0](https://semver.org/), **0.x until the submission**: each release bumps MINOR,
fixes bump PATCH. Releases are cut with commitizen at sync points (the 10:00 demo freeze is a
release): the bump lands on `develop` through a `chore/release-vX.Y.Z` branch, then one PR
`develop` → `main` (merge commit), tagged `vX.Y.Z` on `main`. Procedure: [releasing](docs/development/releasing.md).

## Data

- Data never enters git: Parquet, DuckDB files, JSONL labels, model caches, graph exports.
- One shared `lake/` lives in the main checkout; worktrees symlink to it.
- Code finds it through `RADAR_LAKE` (default `<repo>/lake`), via `radar.paths`, never through
  hardcoded machine paths.
- Small, reviewed outputs are the exception: `reports/*.md`, `reports/bq_ledger.csv`, and the
  real dev slice in `fixtures/dev/` with mocks copied from it (column allow-list: no URLs, titles,
  person names or free text). Headlines and URLs of news never enter git: `web/public/data/` is
  git-ignored and deployed straight to Netlify. Details: [data and secrets](docs/development/data-and-secrets.md).

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
