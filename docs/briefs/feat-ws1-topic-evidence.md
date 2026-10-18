# BRIEF: WS1d, evidence articles per ranked topic-week

Account: **Claude #2 (claude-work)**, after the interim redeploy · Branch: `feat/ws1-topic-evidence` · Worktree: `../radar-worktrees/feat-ws1-topic-evidence`
Written by the orchestrator, 2026-10-18 02:35 UTC-5. Read `AGENTS.md`, then this file.

## Goal

The demo's step 3 shows the real articles behind each top topic. `topic_scores_weekly.evidence_ids` is
empty; this lane produces up to 5 representative ring-1 articles per ranked topic and week.

## Inputs

- Contract `contracts/topic_evidence_weekly.schema.json` (merged, PR #28; `x-mock: private`: titles and
  URLs never enter git).
- BigQuery `radar.gkg_ai` (`gkg_id`, `dt`, `source`, `url`, `title`, `lang`, `tone`) and
  `radar.article_segment` (ring-1 entity arrays). The topics: the top 30 of each of the last 8 scored weeks
  of `lake/gold/topic_scores_weekly.parquet` (upload that small id list as a temp table or inline).
  Your WS1c pattern logic (the week's specific co-mentioned entities) is the natural relevance signal.

## Outputs

1. `bq_sql/s14_topic_evidence_weekly.sql` -> `radar.topic_evidence_weekly`, per the contract. Selection
   rule (state it in `why_selected` and the SQL comment): among the topic-week's ring-1 articles, rank by
   (number of the week's top specific co-mentioned entities the article carries, then es/pt first, then
   earliest), keep at most one article per source, take 5. Prefer es/pt articles when they tie.
   Through `run_bq.py` with a dry run; cap 15 GiB (title and url are wide columns: estimate first; if the
   dry run is higher, restrict to the last 8 weeks' partitions and ask before going above 15 GiB).
2. Export to `lake/gold/topic_evidence_weekly.parquet`, contract-checked; no dev cut, no mock (private).
3. `deploy/export_static.py`: write `web/public/data/evidence/topics/<slug>.json` (git-ignored) for the
   top 10 of the last 4 weeks, so the UI's Evidence card works offline too.
4. A tool `get_topic_evidence(topic_id, week)` is the orchestrator's (agents); just say in the status
   when the lake file exists (`READY FOR EVIDENCE` at the top of `status/WS1.md`).
5. In `status/WS1.md`: bill, rows, how many topic-weeks got 5 / fewer, share es/pt, and the 2026-W42
   top 10's article counts (no titles in the status file).

## Files you may touch

`bq_sql/s14_topic_evidence_weekly.sql`, `pipelines/ingest/**`, `deploy/export_static.py`,
`deploy/tests/**`, `reports/bq_ledger.csv`, `status/WS1.md`.

## Acceptance

`make check && make test` pass; data test: the lake file validates, at most 5 per topic-week, one per
source, every URL starts with http.

## Paid or outward actions needing approval

Approved: the S14 job up to 15 GiB and its checks. `git push`: the orchestrator.

## Deadline (UTC-5)

Lake file by **04:00**; static evidence JSON by **04:30** (the final redeploy ships it).

## If blocked

`BLOCKED: <reason>` at the top of `status/WS1.md`, then stop.
