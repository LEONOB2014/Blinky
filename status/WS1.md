READY FOR WS4 (01:30 UTC-5): `lake/gold/topic_sources_weekly.parquet` exists (270,888 rows, validated). See
the WS1c section below for thresholds.

# WS1 status

Owner: claude-work · Directories: `pipelines/ingest/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 01:30 UTC-5 · branch `feat/ws1-topic-sources` (WS1c) · committed locally, the orchestrator pushes.

Previous: 2026-10-17 22:45 UTC-5 · branch `feat/ws1-gdelt-loop` · Addendum 2 done, push waits for the maintainer

Previous: 2026-10-17 21:40 UTC-5 · branch `feat/ws1-gdelt-loop` · draft PR #7

## Addendum 2 (22:30): topic -> subtopic table and the dev cut

- `bq_sql/s12_topic_subtopic_weekly.sql` -> `radar.topic_subtopic_weekly`, per the contract: ring-1 articles,
  topics = the `topic_daily` ids, Monday weeks, `subtopic` NULL for articles with none. It reads the ring-1
  org/theme arrays of `article_segment` instead of `article_entities` (the same entities: 1.24 GB vs 2.89 GB
  dry run, so the whole job dry-runs at 1.42 GiB instead of 2.95 GiB).
  - Bill: 1,526,726,656 bytes = 1.42 GiB (measured), dry run 1,526,319,470 (measured); check query 0.08 GiB (measured).
  - Rows: 1,265,930; 9,123 topics; 51 weeks; 233,351 NULL-subtopic rows; 0 duplicate keys; 0 rows with
    n_articles > n_topic_articles (measured). Where a topic has articles without a subtopic, those are 55.2%
    of its articles (pooled over such rows, measured): the regex leaves most ring-1 articles unlabelled.
- Lake: `lake/gold/topic_subtopic_weekly.parquet`, 1,265,930 rows, 3.5 MiB, 1,000 sampled rows valid
  (measured). `RADAR_PROFILE=full uv run pytest -m data`: 20 passed.
- Dev cut (`fixtures/dev/`, from the lake, 0 bytes billed): 2026-08-24..2026-10-17, ranked universe of
  `taxonomy.yaml` (orgs minus `org_deny`, `TECH_` themes, >= 20 articles in some week): 1,757 topics
  (1,753 orgs, 4 themes), all kept, no top-N cut needed. `topic_daily.parquet` 42,133 rows, 699 KiB;
  `topic_subtopic_weekly.parquet` 34,101 rows, 82 KiB (measured). 0 deny-listed orgs in either file.
- `x-mock` NOT changed: with `dev-slice`, `make test-ws` fails (`test_mock_matches_contract[topic_daily]`,
  checked) because it needs `mocks/<name>.json`, which this brief does not let me write. For the
  orchestrator: copy records from the two fixtures into `mocks/` and then flip both `x-mock` values.

## WS1c: source diversity per topic-week (the syndication guard)

- `bq_sql/s13_topic_sources_weekly.sql` -> `radar.topic_sources_weekly`, exactly as the contract:
  ring-1 articles, the topic ids of `topic_daily`, Monday weeks.
- `top_theme_pattern_share` is computed, never null:
  - The pattern is the topic-week's 5 most co-mentioned *specific* entities: orgs and themes in at
    most 10% of that week's ring-1 articles, the topic itself excluded.
  - Each article carries the sorted subset of those 5 it mentions. The share is the most common
    subset's articles over the topic-week's articles.
  - The first version, without the 10% cut, picked background themes (2026-W42:
    `EPU_ECONOMY_HISTORIC` in 49% of ring-1 articles, `WB_133` ICT in 48%, `TAX_ECON_PRICE` in 34%;
    measured on `edges_weekly`). It put 31% of ranked topic-weeks at >= 0.9, for example
    `org:national stock exchange` at 1.00.
  - With the cut, the 5 W42 flags match the WS9 diagnostic exactly, and National Stock Exchange
    falls to 0.62.
- Bills (measured): 1,356,857,344 bytes (1.26 GiB) per run, two runs (v1, then v2 with the cut);
  the dry run equals the bill. Both rows are in `reports/bq_ledger.csv`.
- Rows (measured): 270,888 topic-weeks, 9,123 topics, 51 weeks, 0 nulls.
- Lake: `lake/gold/topic_sources_weekly.parquet` (2.2 MiB), 1,000 sampled rows valid.
  `RADAR_PROFILE=full uv run pytest -m data` checks the contract, `n_sources <= n_articles`,
  `top_source_share <= top3_source_share`, Monday weeks, unique keys and topic ids within
  `topic_daily`.
- Dev cut: `fixtures/dev/topic_sources_weekly.parquet`, 9,183 rows, the same 1,757 topics and 8 weeks
  as the `topic_daily` dev cut, 91 KiB, 0 contract violations
  (`scripts/export_dev_slice.py --sources-from-lake`). `x-mock` is still pending: the mock is the
  orchestrator's.

**2026-W42 top 10 (current `topic_scores_weekly`, measured):**

| Rank | Topic | Articles | Sources | Top source share | Top-3 share | Pattern share |
|---|---|---|---|---|---|---|
| 1 | `org:marsh mclennan` | 44 | 39 | 0.05 | 0.14 | 0.66 |
| 2 | `org:euronext` | 149 | 86 | 0.01 | 0.04 | 0.97 |
| 3 | `org:adani enterprises` | 51 | 50 | 0.04 | 0.08 | 0.96 |
| 4 | `org:rocket lab` | 24 | 13 | 0.21 | 0.46 | 0.25 |
| 5 | `org:national stock exchange` | 24 | 17 | 0.08 | 0.25 | 0.62 |
| 6 | `org:ministry of science` | 82 | 82 | 0.01 | 0.04 | 0.91 |
| 7 | `org:kioxia holdings` | 72 | 54 | 0.04 | 0.11 | 0.94 |
| 8 | `org:sterling` | 158 | 91 | 0.03 | 0.06 | 0.92 |
| 9 | `org:citigroup` | 150 | 112 | 0.05 | 0.13 | 0.39 |
| 10 | `org:yahoo` | 177 | 43 | 0.60 | 0.73 | 0.60 |

**Distribution over all ranked topic-weeks** (17,154 rows of `topic_scores_weekly` with a rank, 46
weeks, all matched, measured):

| Column | p10 | median | p90 |
|---|---|---|---|
| `n_articles` | 22 | 41 | 165 |
| `n_sources` | 12 | 28 | 110 |
| `top_source_share` | 0.024 | 0.10 | 0.34 |
| `top3_source_share` | 0.062 | 0.23 | 0.62 |
| `top_theme_pattern_share` | 0.21 | 0.45 | 1.00 |

- Pattern share at or above a threshold, over the 17,154 ranked topic-weeks: >= 0.9 in 4,230 (24.7%),
  >= 0.8 in 5,088, >= 0.7 in 5,831. In past top 10s (460 topic-weeks), >= 0.9 in 75 (16.3%).
- By topic-week size:

  | Articles | Topic-weeks | Share >= 0.9 | Median pattern | Median sources |
  |---|---|---|---|---|
  | < 30 | 5,680 | 21.1% | 0.43 | 18 |
  | 30-59 | 5,501 | 26.3% | 0.44 | 29 |
  | 60-119 | 3,514 | 38.1% | 0.69 | 63 |
  | >= 120 | 2,459 | 10.0% | 0.41 | 145 |

**What this says for WS4's gate (a reading of the data, the thresholds are WS4's):**
- Source counts do not catch these bursts: a syndication network republishes one story under many
  domains. Euronext has 86 sources and a top source share of 0.01, but a pattern share of 0.97.
- The pattern share does catch them, so a penalty on `top_theme_pattern_share` >= 0.9 would have
  removed exactly the 5 single-pattern W42 topics.
- `top_source_share` catches the other failure, one outlet dominating: `org:yahoo` at 0.60.
- The 60-119 article band has the most single-pattern weeks.

## Done

- `pipelines/ingest/run_bq.py`: dry run first; aborts above the cap (50 GiB) or 1.5x the last
  successful bill of the same script. Multi-statement scripts use the last bill, not the dry run
  (`--maximum_bytes_billed` = 1.5x that). A lower-bound dry run with no history needs
  `--expect-gib`, and `--baseline-scale` covers planned growth. One ledger row per job, failed
  jobs included with their partial bill. Unit tests are offline.
- `bq_sql/s4a_article_segment.sql` (new, monthly): the three rings per article in
  `radar.article_segment`, plus ring-1 entity arrays. It is the only step after S2 that scans the
  wide gkg_ai columns (themes is 57% of gkg_ai's bytes, measured). S4 and S11 read this narrow
  table, so a rule change never re-scans gkg_ai.
- `bq_sql/s4_aggregates.sql`: `topic_rules` (moved here from S1, with `energy_climate` from
  `taxonomy.yaml`); `article_entities` and `edges_weekly` built from **ring-1 articles only**;
  `article_topic` and `daily_topic` carry `segment` and `domain`.
- `bq_sql/s8_daily_topic_rolling.sql`: keyed by `segment`. The spine covers only the days the
  extract covers (it used to zero-fill the 2 years of `daily_totals` before the backfill started).
- `bq_sql/s11_topic_daily.sql` (new): `radar.topic_daily`, orgs and GKG themes in ring 1, never
  persons. It keeps only the topics that reach at least 20 articles in some trailing 7-day window
  (a superset of the ranking universe).
- `bq_sql/s2_monthly_insert.sql`: month tokens filled by `run_bq.py --month`.
- Backfill: S2 for 2026-07 back to 2025-11 (newest first, approved in chat), then S4a for every
  month, then S4, S8 and S11 once over 2025-11-01..2026-10-18.
- `pipelines/ingest/export_gold.py`: writes `daily_totals`, `daily_topic`, `daily_topic_rolling`,
  `topic_daily` and `edges_weekly` to `lake/gold/` through the free tabledata.list path, and
  validates 1,000 sampled rows per table against the contract.
- Data tests: `RADAR_PROFILE=full uv run pytest -m data`.

- Lake export done (`lake/gold/`, measured): `daily_totals` 2,860 rows; `daily_topic` 50,155;
  `daily_topic_rolling` 61,952; `topic_daily` 2,012,823 (29 MiB); `edges_weekly` 37,766,030
  (424 MiB, 8:54 over the free tabledata.list path, 0 bytes billed). 1,000 sampled rows per table
  are valid against the contracts.
- `make check && make test` pass (71 passed, 9 skipped). `RADAR_PROFILE=full uv run pytest -m data`:
  17 passed.

## In progress

- Draft PR #7 against `develop` (https://github.com/LEONOB2014/Blinky/pull/7). It will be marked ready only with your approval.

## Blocked on

Nothing. Decisions for the orchestrator are listed below.

## Decisions for the orchestrator

1. **Ring-3 and ring-2 topic ids.** `daily_topic_rolling` has no `domain` column, so the `topic`
   column carries it: ring 2 is `it_all` and ring 3 is `domain:<id>` (one row per matched domain,
   multi-label). `daily_topic` also has `domain` set for ring 3 and NULL elsewhere. Please confirm
   or change this in the contracts.
2. **`taxonomy.yaml` ring 2 text is stale.** It says `(f_ict OR f_tech_org) AND NOT ai`. The brief's
   tightened rule is what runs: an ICT theme AND (a tech organization OR a second, distinct ICT
   theme), minus ring 1. The tech-org list is S2's lab list plus its large-tech list. The contract
   text needs a PR from the orchestrator.
3. **The ranking universe is about 5x the estimate.** See the numbers below: the generic GKG
   themes (`TAX_*`, `WB_*`, `CRISISLEX_*`, …) make up about 1,300 of the roughly 1,900 topics per
   week. Suggestion for WS2/WS4: rank orgs plus a theme allow-list (for example `TECH_*`), or drop
   the generic theme prefixes. That is a `taxonomy.yaml` change (`ranked_entity_types`), so it is
   not made here.
4. **`edges_weekly` now holds every ring-1 GKG theme,** not the old whitelist, so every ranked
   `thm:` topic has a 1-hop ring. Size: 37.8M rows over 51 weeks (measured). By pair type
   (Aug–Oct, measured): thm-thm 54%, org-thm 21%, per-thm 12%. WS3 drops hubs per the design.
5. **`energy_climate` is broad.** 9–11% of ring 1 every month (for example 15,929 of 177,527 in
   2026-09, measured). The themes prefix `ENERGY`/`ENV_` and words such as `clima` and `energy`
   catch general energy news that mentions AI. The Curator should check it against labels.

## Numbers (each marked measured or estimate)

BigQuery billed by WS1 tonight: **287.4 GB (measured)**, all in `reports/bq_ledger.csv`:

| Script | Jobs | Billed |
|---|---|---|
| S2 backfill, 9 months | 9 | 217.85 GB (measured), 22.04–23.92 GiB each |
| S4a segments, 12 months, plus the Aug–Oct iterations | 12 billed (9 more refused by the guard, 0 B) | 55.23 GB (measured) |
| S4 aggregates (2 failed partial runs, Aug–Oct, full span) | 4 | 11.40 GB (measured); full span 7.13 GB |
| S11 topic_daily | 2 | 1.65 GB (measured) |
| S8 view | 2 | 0 B (measured) |
| Checks and the view export | 8 | 1.31 GB (measured) |

The S4a guard worked as designed: the partial October bill (18 days) was the baseline, so all 9
full months were refused at 0 B. They were re-run with `--baseline-scale 2`.

**Per-segment rows per month** (`radar.article_segment`, measured). Ring 2 is far under the
~400k/month target after tightening; it was ~1.4M/month under `f_ict` alone (measured by WS0):

| Month | ai (ring 1) | it (ring 2) | ai_domain (ring 3) | Days |
|---|---|---|---|---|
| 2025-11 | 132,487 | 127,463 | 78,802 | 30 |
| 2025-12 | 114,731 | 133,325 | 80,203 | 31 |
| 2026-01 | 126,501 | 131,042 | 81,958 | 31 |
| 2026-02 | 129,486 | 124,797 | 79,292 | 28 |
| 2026-03 | 134,701 | 138,741 | 80,792 | 31 |
| 2026-04 | 133,134 | 128,472 | 74,184 | 30 |
| 2026-05 | 151,418 | 123,771 | 74,102 | 31 |
| 2026-06 | 153,828 | 133,240 | 79,515 | 30 |
| 2026-07 | 149,396 | 145,478 | 80,944 | 31 |
| 2026-08 | 136,105 | 134,448 | 73,246 | 31 |
| 2026-09 | 177,527 | 125,147 | 70,487 | 30 |
| 2026-10 (to 18th) | 84,589 | 67,248 | 41,051 | 18 |

**`is_missing` in `daily_topic_rolling`** (measured): 2 missing days in the span; 220 missing rows
(ai 130, ai_domain 80, it 10). All 220 have NULL `n`, `n_all`, `share` and `n_sources`; 0 present
days are NULL; 61,952 rows in total.

**Regex subtopic counts per month** (ring-1 articles, multi-label, `radar.article_topic`, measured):

| Month | agents | llms | chips | regul. | educ. | jobs | business | safety | creative | health | funding | energy |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-11 | 2,581 | 12,186 | 14,468 | 2,497 | 2,661 | 2,400 | 2,178 | 2,721 | 3,423 | 4,102 | 12,689 | 10,832 |
| 2025-12 | 2,782 | 9,680 | 9,560 | 2,728 | 2,277 | 1,718 | 2,228 | 2,539 | 2,665 | 3,468 | 9,235 | 9,182 |
| 2026-01 | 2,544 | 10,568 | 9,888 | 2,488 | 2,495 | 2,122 | 1,907 | 4,272 | 2,917 | 4,823 | 8,611 | 9,628 |
| 2026-02 | 3,624 | 8,652 | 9,320 | 2,381 | 2,855 | 2,436 | 2,419 | 3,292 | 2,747 | 3,937 | 11,461 | 10,773 |
| 2026-03 | 4,916 | 9,509 | 10,409 | 2,590 | 2,906 | 2,555 | 2,937 | 4,145 | 3,055 | 4,013 | 9,436 | 13,040 |
| 2026-04 | 4,123 | 10,988 | 6,467 | 2,488 | 3,313 | 2,950 | 2,559 | 2,931 | 3,024 | 3,856 | 11,549 | 10,526 |
| 2026-05 | 4,441 | 9,740 | 11,031 | 3,300 | 3,121 | 3,420 | 2,914 | 3,302 | 4,002 | 4,620 | 14,823 | 15,167 |
| 2026-06 | 4,862 | 10,011 | 12,551 | 3,402 | 2,708 | 2,671 | 3,525 | 3,866 | 3,420 | 3,596 | 15,850 | 14,452 |
| 2026-07 | 4,379 | 10,392 | 11,722 | 3,516 | 3,066 | 2,649 | 3,160 | 3,815 | 4,191 | 3,918 | 13,327 | 14,343 |
| 2026-08 | 4,720 | 10,564 | 12,583 | 2,731 | 3,162 | 2,106 | 2,928 | 3,173 | 3,613 | 3,190 | 13,353 | 13,221 |
| 2026-09 | 8,884 | 11,304 | 11,564 | 5,491 | 4,961 | 2,137 | 3,235 | 10,566 | 3,780 | 5,935 | 12,545 | 15,929 |
| 2026-10 | 3,360 | 5,874 | 6,095 | 1,975 | 1,744 | 1,275 | 1,556 | 4,236 | 2,003 | 4,171 | 5,888 | 7,299 |

**`topic_daily` distinct topics per week with ≥ 20 articles** (50 full Monday weeks, measured):
min 1,499, median 1,936, max 2,318, against the expected 150–400 (estimate). Orgs alone: min 214,
median 380, max 563. Generic-prefix themes: median 1,321.

**Gold tables** (BigQuery rows, measured): `article_segment` 4,031,651; `article_entities`
51,575,758; `edges_weekly` 37,766,030; `article_topic` 5,876,247; `daily_topic` 50,155;
`topic_daily` 2,012,823; `daily_topic_rolling` 61,952.
