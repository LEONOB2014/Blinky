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
