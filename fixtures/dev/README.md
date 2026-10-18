# Dev slice (real data, committed)

Real BigQuery output, exported once by the orchestrator with
`uv run python scripts/export_dev_slice.py --project <gcp-project-id>` on 2026-10-18 (UTC).
Source data: GDELT 2.0 GKG (open data, attribution: The GDELT Project, https://www.gdeltproject.org/).

| File | Content | Rows |
|---|---|---|
| `daily_totals.parquet` | 8 weeks (2026-08-24 .. 2026-10-17), 4 language streams | 220 |
| `daily_topic.parquet` | 8 weeks, ai_all + 11 subtopics (regex v1), ring 1 only | 4,497 |
| `daily_topic_rolling.parquet` | the S8 view over the same 8 weeks | 5,280 |
| `edges_weekly.parquet` | top 1,500 edges per week by co-mentions, no person nodes | 12,000 |
| `gkg_ai_sample.parquet` | 2026-10-11 .. 10-17: 900 ring-1, 300 ICT-only, 300 control rows | 1,500 |

Column allow-list (`src/radar/fixtures.py`, enforced by `tests/test_fixtures.py`): no URLs, titles,
person names, locations, quotations or free text. Export cost: 1.68 GB billed (measured, in
`reports/bq_ledger.csv`).

Known gaps, by design of the current SQL (fixed in the GDELT loop, WS1/WS2):
- `daily_topic` has no `segment`/`domain` yet: S4 builds ring 1 only, so its mock stays pending.
- `edges_weekly` is built over every row of `gkg_ai` (ring 1, ICT and control); the design ranks and
  explains from ring-1 articles only.
- Numbers from this slice are never reported (`RADAR_PROFILE=dev`).
