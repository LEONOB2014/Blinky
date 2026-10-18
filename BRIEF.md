# BRIEF: WS6, Wikidata and Wikipedia pageviews (Scout, cross-source)

Account: **Grok CLI** · Branch: `feat/ws6-wikipedia-pageviews` · Worktree: `../radar-worktrees/feat-ws6-wikipedia-pageviews`
Written by the orchestrator, 2026-10-17 20:45 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Produce the backtest's label: resolve every ranked topic to Wikidata and its es/pt/en Wikipedia articles,
and fetch their daily pageviews for 12 months. This is on the critical path.

## Plan reference

`docs/designs/radar-build-plan.md`: "Backtest", premise P1; MASTER_PLAN §3 (Wikipedia: clean, send a
descriptive User-Agent).

## Inputs

- Now: the 12 subtopics in `contracts/taxonomy.yaml`, and the organizations in
  `fixtures/dev/gkg_ai_sample.parquet` (`orgs` column) and in `fixtures/dev/edges_weekly.parquet` (`org:`
  nodes).
- From **22:30**: WS1's `topic_daily` in the lake (`RADAR_PROFILE=full`) for the full topic list.
- `.env`: `WIKIMEDIA_USER_AGENT` (already set). No other key is needed.

## Outputs

1. `entity/wikidata.py`: `topic_wikidata` per `contracts/topic_wikidata.schema.json`, using the Wikidata
   `wbsearchentities` API (es, en, pt) plus a P31 check (organization, company, software, concept);
   persons are never resolved. Cache responses under `lake/raw/wikidata/`.
2. `crosssource/pageviews.py`: `wiki_pageviews_daily` per contract, from the Wikimedia REST pageviews API
   (`per-article`, `agent=user`, daily), es/pt/en, 2025-10-01 to today. At most 100 requests per second
   is allowed by Wikimedia; stay under 20 with retries (tenacity) and caching under `lake/raw/pageviews/`.
3. A real dev slice for the orchestrator: write `lake/gold/topic_wikidata.parquet` and
   `lake/gold/wiki_pageviews_daily.parquet`, plus 8-week cuts (2026-08-24 .. 2026-10-17) as
   `lake/devcut/<name>.parquet`; the orchestrator copies them into `fixtures/dev/`.
4. Validation of every row with `radar.contracts.validate_records`.

## Files you may touch

`entity/**`, `crosssource/**`, `status/WS6.md`, the `crosssource` extra in `pyproject.toml`/`uv.lock`.

## Out of scope

HN, X and YouTube (a later brief), contracts, scores, anything that is not a public API. No scraping.

## Acceptance

- `make check && make test` pass; unit tests parse real cached API responses (save one real response per
  endpoint under `entity/tests/data/` and `crosssource/tests/data/`; no invented responses).
- `status/WS6.md` reports, measured: topics attempted, resolved (exact/alias/none), articles found per
  language, pageview rows, failed requests.

## Paid or outward actions needing approval

None paid. `git push` and opening the PR need the maintainer's approval.

## Deadlines (UTC-5)

Subtopics + dev-slice organizations resolved and their pageviews fetched by **22:00** (dev cut ready);
full topic list from `topic_daily` by **01:30**.

## Report

`status/WS6.md` at each sync; PR as a **draft** against `develop`, ready only after the local gate passes.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS6.md`, then stop.

## Addendum (orchestrator, 22:30 UTC-5): resolve the ranked universe first

The ranked unit is now `ranked_universe` in `contracts/taxonomy.yaml` (PR #8): every `org:` topic
except `org_deny`, plus `thm:TECH_*`, with at least 20 ring-1 articles in some week of `topic_daily`.
Generic GKG themes (`TAX_*`, `WB_*`, ...) are no longer ranked, so do not spend requests on them.

1. Reorder the queue: the ranked-universe topics first, by total ring-1 articles descending; then the
   dev-slice topics; skip non-ranked `thm:` topics. Keep the cache; do not restart from scratch.
2. Write `topic_wikidata` and `wiki_pageviews_daily` to `lake/gold/` as soon as the first 1,000 ranked
   topics are done (WS4's backtest waits on it), then again at the end.
3. Report: ranked topics attempted, exact / alias / none, pageview rows, failed requests (measured).

Deadline: first write by **00:30**.

## Addendum 2 (orchestrator, 01:45 UTC-5): fetch what the backtest needs, now

At 01:40 `topic_wikidata` (22:42) had 2,675 rows and no `wiki_pageviews_daily` existed; the run is
still resolving `topic_daily` extras, and pageviews at the safe 6.5 s pace would not reach the
backtest (WS4, 05:00). The backtest only needs the topics in each method's weekly top 10:
`lake/labels/backtest_priority_topics.parquet` (679 topics: the radar's top 10 over 46 weeks, 253,
and the raw-count-growth baseline's, 467; measured). 189 exact + 30 alias are resolved, 152 with an
es or pt article; 425 are not resolved yet.

1. **Stop the extras.** Finish the current batch, write `topic_wikidata`, then resolve the 425
   unresolved priority topics (same rules: no persons, no countries).
2. **Pageviews for the priority topics only, es and pt only** (the label is es+pt growth; skip en
   tonight), one request per article covering 2025-10-01..2026-10-18, at the pace that worked
   (6.5 s). Write `wiki_pageviews_daily` (and `topic_wikidata`) every 50 articles so WS4 can start.
3. Then, if time remains, the extras as before.
4. Report in `status/WS6.md`: priority topics resolved (exact / alias / none), articles fetched,
   rows, 429s, and the time of each write.

Deadlines: priority resolution by **02:30**; pageviews for the priority topics by **04:00**.
