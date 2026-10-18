<!-- Title: a Conventional Commit header, e.g. feat(ingest): add the 15-minute raw-file poller
     Base: develop (work branches) · main (release/* and hotfix/* only) -->

## What and why

<!-- The change and the reason for it. Name the workstream (WS0–WS7) and the plan section (MASTER_PLAN §…). -->

## How it was tested

- [ ] `uv run pre-commit run --all-files`
- [ ] Tests for the touched area (list the commands and results)
- [ ] Outputs validated against `contracts/` (`make test-ws`)
- [ ] CI green

## Numbers and cost

<!-- Every number in this PR is marked (measured) or (estimate). BigQuery bytes billed per job,
     as logged in reports/bq_ledger.csv. "None" if none. -->

## Data, contracts and secrets

<!-- New or changed contracts (lead approval), datasets, generated artefacts, .env.example keys,
     detect-secrets baseline changes (each approved by the maintainer). "None" if none. -->

## Follow-ups

<!-- Anything deliberately left out, with the reason. -->
