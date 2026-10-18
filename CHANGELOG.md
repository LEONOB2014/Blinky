# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (0.x until the hackathon submission).
Entries are generated from Conventional Commits by commitizen; see
[docs/development/releasing.md](docs/development/releasing.md).

## v0.1.0 (2026-10-17)

### Highlights

- Repository scaffold: one directory per workstream (WS0–WS7), the shared `radar` core
  (lake paths, contract validation), the BigQuery scripts Q1–Q4 and S1–S10, and the master plan.
- Engineering practices: Conventional Commits enforced by commitizen, pre-commit hooks run
  identically in CI, a conventional PR title check, worktree-per-branch workflow and agent rules
  (`AGENTS.md`, imported by `CLAUDE.md` and `GEMINI.md`).
