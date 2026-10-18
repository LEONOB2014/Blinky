# WS2 status

Owner: claude-extend · Directories: `pipelines/taxonomy/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:40 UTC-5 · branch `feat/ws1-gdelt-loop` (WS1 + WS2 brief) · draft PR #7

## Done

- The three rings as SQL in `bq_sql/s4a_article_segment.sql`. Ring 2 is tightened per the brief:
  an ICT theme AND (a tech organization OR a second ICT theme), minus ring 1. Ring 3 is a domain
  theme group AND a tech organization, minus rings 1–2, with multi-label domains.
- `energy_climate` added to `radar.topic_rules`: the text regex plus the `ENV_`/`ENERGY` theme
  prefix, copied from `taxonomy.yaml`.
- `pipelines/taxonomy/tests/test_taxonomy_sql.py` checks that the SQL rules equal `taxonomy.yaml`
  (subtopic ids, the energy rule, the domain prefixes, the ring-1 rule, the ring order).
- Per-segment and per-subtopic counts: see `status/WS1.md` (measured).

## In progress

## Blocked on

Nothing. For the orchestrator (details in `status/WS1.md`): the ring-2 text in `taxonomy.yaml` is
stale; the ranking universe is about 1,900 topics per week, not 150–400, because of generic GKG
themes; and `energy_climate` is broad (9–11% of ring 1, measured). No LLM labelling in this brief.

## Numbers (each marked measured or estimate)

## WS2b — Article Classifier Cascade (`feat/ws2-distill-cascade`)

### Step 1: Stratified Sample (`pipelines/taxonomy/sample.sql`, `pipelines/taxonomy/sample.py`) — Done (22:55 UTC-5)

- **BigQuery job**: `radar_sample_20261018T035232_c91f93` via `pipelines/ingest/run_bq.py --workstream WS2 --cap-gib 30`.
  - Dry run: `9,334,569,319` bytes (`8.69 GiB`, measured).
  - Billed: `9,335,472,128` bytes (`8.69 GiB`, measured), logged in `reports/bq_ledger.csv`.
  - Exported `12,000` rows from `radar.label_sample` via `bq head` (`0` bytes billed, measured).
- **Initial sample (`lake/labels/sample.parquet`)**: `4,000` rows (Aug–Oct 2026, measured):
  - `ring1` (`segment = 'ai'`): `1,500` rows (`540` `es/pt`, `36.0%`, measured).
  - `ring2` (`segment = 'it'`): `1,000` rows (`360` `es/pt`, `36.0%`, measured).
  - `ring3` (`segment = 'ai_domain'`): `500` rows (`180` `es/pt`, `36.0%`, measured).
  - `rejected` (`f_control = TRUE AND NOT ai`): `1,000` rows (`360` `es/pt`, `36.0%`, measured).
  - Language breakdown across the `4,000` sample rows: `eng = 1,421`, `spa = 980`, `por = 460`, `other = 1,139` (`es/pt` share = `1,440 / 4,000 = 36.0% >= 30%`, measured).
- **Active-learning candidate pool (`lake/labels/pool.parquet`)**: `8,000` additional stratified rows (`3,000` ring 1, `2,000` ring 2, `1,000` ring 3, `2,000` rejected, `36.0%` `es/pt`, measured) in the lake for Round 2 active learning.
- **Aug–Oct 2026 population denominators (`lake/labels/sample_meta.json`)**:
  - `pop_n_ring1 = 398,221` (measured), `pop_n_ring2 = 326,843` (measured), `pop_n_ring3 = 184,784` (measured), `pop_n_control_rej = 40,392` (measured).
  - Enriched tech-themed control stratum (`f_control AND (f_ict OR tech_org)`): `N_acc = 510` accepted by core-AI rule (measured), `N_rej = 7,375` rejected by core-AI rule (measured).
  - All `f_control` stratum: `N_acc_all = 792` accepted (measured), `N_rej_all = 40,392` rejected (measured).
