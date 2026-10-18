<div align="center">

# Radar de Señal Temprana

### The early-signal radar of AI topics for 30X

**We tell you which AI topics are about to land on LinkedIn, why, and from which emotional angle to tell them to
LatAm executives.**

[![CI](https://github.com/LEONOB2014/Blinky/actions/workflows/ci.yml/badge.svg)](https://github.com/LEONOB2014/Blinky/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.1.0-2563eb)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-fe5196?logo=conventionalcommits&logoColor=white)](https://www.conventionalcommits.org/en/v1.0.0/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-FAB040?logo=pre-commit&logoColor=white)](.pre-commit-config.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/uv-managed-DE5FE9)](https://docs.astral.sh/uv/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![BigQuery](https://img.shields.io/badge/BigQuery-GDELT-4285F4?logo=googlecloud&logoColor=white)](bq_sql/)

<sub>Reto 30X "Radar de contenido" · built by Andrés Becerra</sub>

</div>

---

## What it does

LinkedIn bans automated collection, so the radar measures the open upstream chain instead: papers, models and repos
(arXiv, Hugging Face, GitHub), tech-social (Hacker News, X counts, Bluesky), global news (GDELT, 65 languages, with
tone and GCAM emotions), and reference attention (Wikipedia es/pt/en). LinkedIn itself is observed only through 30X's
own analytics and a consented community sensor.

Six scores combine into a weekly top 10, each with its reasons, lifecycle stage, emotional framing angle and a Spanish
adaptation brief. The evidence is a backtest (lead time, precision@10) and measured filter recall.

The full plan: [docs/plan/MASTER_PLAN.pdf](docs/plan/MASTER_PLAN.pdf).

## Repository

| Path | Workstream |
|---|---|
| [`contracts/`](contracts/), [`mocks/`](mocks/) | WS0: data and API contracts |
| [`bq_sql/`](bq_sql/) | BigQuery scripts |
| [`pipelines/ingest/`](pipelines/ingest/) | WS1: BigQuery and ingestion |
| [`pipelines/taxonomy/`](pipelines/taxonomy/) | WS2: taxonomy, labels, quality |
| [`graph/`](graph/) | WS3: co-occurrence graphs and GPU visualization |
| [`models/`](models/) | WS4: scores, sentiment, backtest (WS7: [`models/tgnn/`](models/tgnn/)) |
| [`api/`](api/), [`web/`](web/) | WS5: API and UI |
| [`entity/`](entity/), [`crosssource/`](crosssource/) | WS6: entities, cross-source lead-lag |
| [`reports/`](reports/) | Evidence: cost ledger, backtest, label quality |

## Quick start

```bash
make setup          # uv env, git hooks, .env from the template
make test           # what CI runs
make help           # every target
```

## Engineering practices

- [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) enforced at commit time; PR titles checked in CI.
- The same pinned pre-commit hooks locally and in CI: Ruff, file hygiene, actionlint, detect-secrets, the lockfile,
  and contracts-versus-mocks validation.
- `develop` → `main` with release branches, [SemVer](https://semver.org/) 0.x and a generated
  [changelog](CHANGELOG.md).
- One git worktree per branch, so parallel coding agents never collide.
- Every number is marked measured or estimate; BigQuery bytes billed are logged per job.

Rules for contributors and coding agents: [AGENTS.md](AGENTS.md). Procedures: [docs/development/](docs/development/).

## License

[MIT](LICENSE).
