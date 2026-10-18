# WS3 status

Owner: claude-home · Directories: `graph/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 20:58 UTC-5 · `feat/ws3-graph-metrics` · PR not opened yet (needs the maintainer's approval)

## Done

- `graph/metrics.py` -> `node_metrics_weekly`: weighted degree (sum of `n`), `deg_growth`
  = ln(deg_w / last week's), new-neighbour rate vs the prior 4 weeks, weighted PageRank and
  `pr_rank_delta` (last week's rank minus this week's: positive = rising), k-core (unweighted
  coreness), Leiden (modularity, weight `n`, seed 42) matched across weeks at Jaccard >= 0.3 with
  birth/merge/split/continue, `is_hub` = top ceil(1%) of nodes by weighted degree (ties included).
- Missing weeks are never filled: `deg_growth`, `pr_rank_delta` and `community_event` are null
  when last week is absent from the data; `new_nbr_rate` is null unless all 4 prior weeks are
  present. The first week (and the week after a gap) has a null community event, not `birth`.
- `graph/context.py` -> `topic_context_1hop`: topics = `ranked_entity_types` of
  `contracts/taxonomy.yaml` (org, thm); n >= 3, NPMI > 0.1, that week's hubs dropped, top 20 by
  NPMI (ties by `n`, then name). `neighbor_segment` / `neighbor_domain` are null: WS1's tables
  do not provide them yet (`context_1hop(..., segments=)` joins them once they do).
- `graph/build.py`: runs both for the active profile, validates every row with
  `radar.contracts.validate_records` (aborts on any violation), writes `lake/gold/` on full,
  only to `--out` on dev.
- 12 unit tests on real dev-slice weeks (hub exclusion, NPMI/n/rank limits, top-20 equals the
  brute-force top NPMI, community matching 2026-10-05 -> 2026-10-12, gap handling, contract
  validation of both outputs). `make check && make test` pass locally.

## In progress

- Full-profile run (`RADAR_PROFILE=full uv run python -m graph.build`) as soon as WS1's ring-1
  `edges_weekly` lands in `lake/gold/` (expected 22:30). At 20:54 `lake/gold/` was empty.

## Blocked on

Nothing outside the brief. Waiting on the scheduled WS1 input above.

## Notes for the lead

- CI installs no extras (`uv sync --locked`), so the graph tests skip there (visibly, via
  `pytest.importorskip`). Running them in CI needs `--extra graph` in `ci.yml` (outside this brief).
- The ring does not drop `per:` neighbours (the brief does not ask for it). The dev slice has
  none; on full ring-1 edges, person neighbours would reach the lake and the API. Say if they
  should be dropped.
- Topic universe: every org/thm node of the week. It is not restricted to WS4's ranked topics,
  so the API can filter by `topic_id`.

## Numbers (each marked measured or estimate)

- Full profile: pending (none reported yet). Dev-slice numbers are never reported.
