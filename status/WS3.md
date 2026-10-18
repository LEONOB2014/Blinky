# WS3 status

Owner: claude-home · Directories: `graph/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 22:45 UTC-5 · `feat/ws3-graph-metrics` (addendum 22:30; PR #5 merged) · push waits for the maintainer

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

## Addendum 22:30 (done)

1. `per:` neighbours are dropped from `topic_context_1hop` before the top-20 selection, so each topic
   still gets up to 20 non-person neighbours. `per:` nodes stay in `node_metrics_weekly` as graph
   structure only. Full rerun: ring 4,773,204 rows (was 4,849,854), 0 person neighbours; metrics
   473,275 rows, unchanged; 518 s, 2.44 GB peak (measured).
2. Ranked topics: no change; the ring keeps covering every org/thm node (`ranked_entity_types`) and
   the API filters by `ranked_universe`.
3. Community continuity, tried once (measured, 876 community-weeks with a previous week, 51 weeks):
   - full membership, Jaccard >= 0.3: 842 birth, 34 continue: 3.9% non-birth;
   - nodes in the top 10% by weighted degree in both weeks, Jaccard >= 0.3: 697 birth, 174 continue,
     4 split, 1 merge: 20.4% non-birth.
   Continuity stays under 50%, so `community_event` and `community_id` stay as computed (full
   membership) and **agents must not use them**. No further iteration tonight.
4. `ci.yml` untouched; the graph tests skip in CI and run locally with `uv sync --extra graph`.

## In progress

- Nothing. The addendum is done; the push waits for the maintainer.

## Blocked on

Nothing outside the brief. Waiting on the scheduled WS1 input above.

## Notes for the lead

- The `develop` merge changed `uv.lock`; plain `uv run` then drops the `graph` extra and the graph
  tests skip silently. Use `uv sync --extra graph` (or `uv run --extra graph`) in this worktree.

## Numbers (each marked measured or estimate)

Full profile, `RADAR_PROFILE=full uv run --extra graph python -m graph.build`, 2026-10-17 22:45 UTC-5
(persons out of the ring): 51 weeks (2025-10-27 .. 2026-10-12, contiguous), 37,766,030 edges in;
473,275 `node_metrics_weekly` rows and 4,773,204 `topic_context_1hop` rows written to `lake/gold/`,
every row contract-valid; 321,586 topic-weeks, 184,681 of them at the 20-neighbour cap. Run time
518 s, peak memory 2.44 GB (measured). The first week (2025-10-27) is partial (2,603 nodes against
6,301-11,365 afterwards), so 2025-11-03's `deg_growth` and rank deltas compare against a partial week.

Per week (measured; `ring_topics` = org/thm topics with at least one ring neighbour):

| wk | nodes | edges | communities | hubs | ring_topics | ring_rows |
|---|---|---|---|---|---|---|
| 2025-10-27 | 2603 | 182482 | 9 | 27 | 2143 | 34324 |
| 2025-11-03 | 9802 | 798741 | 21 | 99 | 6556 | 97145 |
| 2025-11-10 | 9301 | 723598 | 23 | 94 | 6237 | 91228 |
| 2025-11-17 | 10860 | 849909 | 28 | 109 | 7165 | 104860 |
| 2025-11-24 | 8257 | 655890 | 16 | 83 | 5744 | 86794 |
| 2025-12-01 | 8714 | 659506 | 17 | 88 | 5978 | 88369 |
| 2025-12-08 | 9272 | 745845 | 18 | 93 | 6237 | 93752 |
| 2025-12-15 | 8383 | 700955 | 17 | 84 | 5728 | 87309 |
| 2025-12-22 | 6451 | 573536 | 17 | 65 | 4720 | 74112 |
| 2025-12-29 | 6301 | 545081 | 13 | 64 | 4676 | 72290 |
| 2026-01-05 | 8648 | 717306 | 14 | 87 | 5945 | 89990 |
| 2026-01-12 | 8819 | 741257 | 20 | 89 | 6022 | 90859 |
| 2026-01-19 | 8916 | 728918 | 17 | 90 | 5953 | 89631 |
| 2026-01-26 | 9276 | 742416 | 20 | 93 | 6236 | 92590 |
| 2026-02-02 | 8844 | 698014 | 23 | 89 | 5953 | 87923 |
| 2026-02-09 | 9593 | 745200 | 21 | 96 | 6310 | 93474 |
| 2026-02-16 | 9886 | 801902 | 17 | 99 | 6446 | 95901 |
| 2026-02-23 | 10328 | 837759 | 15 | 104 | 6861 | 101036 |
| 2026-03-02 | 9096 | 751511 | 14 | 91 | 6405 | 95730 |
| 2026-03-09 | 9271 | 730309 | 19 | 93 | 6465 | 94704 |
| 2026-03-16 | 9805 | 775509 | 19 | 99 | 6543 | 97833 |
| 2026-03-23 | 9155 | 713106 | 16 | 92 | 6299 | 92353 |
| 2026-03-30 | 7988 | 627373 | 24 | 80 | 5622 | 84870 |
| 2026-04-06 | 8165 | 627417 | 20 | 82 | 5626 | 84316 |
| 2026-04-13 | 9028 | 716451 | 19 | 91 | 6234 | 93894 |
| 2026-04-20 | 9617 | 721893 | 17 | 97 | 6314 | 92454 |
| 2026-04-27 | 9909 | 796885 | 22 | 100 | 6555 | 96367 |
| 2026-05-04 | 9484 | 716758 | 16 | 95 | 6145 | 88850 |
| 2026-05-11 | 10484 | 883393 | 18 | 105 | 6982 | 103777 |
| 2026-05-18 | 10637 | 844559 | 13 | 107 | 7105 | 104266 |
| 2026-05-25 | 10205 | 834821 | 16 | 103 | 6828 | 102131 |
| 2026-06-01 | 10691 | 838932 | 20 | 107 | 7208 | 104449 |
| 2026-06-08 | 9997 | 789336 | 14 | 100 | 6951 | 101100 |
| 2026-06-15 | 8977 | 701425 | 23 | 90 | 6190 | 91181 |
| 2026-06-22 | 9992 | 766247 | 12 | 100 | 6762 | 99571 |
| 2026-06-29 | 8980 | 695386 | 21 | 90 | 6183 | 91196 |
| 2026-07-06 | 9389 | 725132 | 10 | 94 | 6486 | 94895 |
| 2026-07-13 | 9897 | 799004 | 16 | 99 | 6805 | 101178 |
| 2026-07-20 | 9758 | 759401 | 13 | 98 | 6630 | 96532 |
| 2026-07-27 | 9863 | 767030 | 21 | 99 | 6710 | 99805 |
| 2026-08-03 | 9206 | 720385 | 16 | 93 | 6331 | 93518 |
| 2026-08-10 | 8827 | 670624 | 16 | 89 | 6067 | 88890 |
| 2026-08-17 | 8832 | 692544 | 17 | 89 | 6113 | 91337 |
| 2026-08-24 | 9684 | 783057 | 16 | 97 | 6717 | 101065 |
| 2026-08-31 | 9330 | 705039 | 16 | 94 | 6370 | 92881 |
| 2026-09-07 | 10268 | 804099 | 16 | 103 | 6922 | 101960 |
| 2026-09-14 | 11365 | 975857 | 12 | 114 | 7410 | 110040 |
| 2026-09-21 | 10955 | 958995 | 14 | 110 | 7362 | 108632 |
| 2026-09-28 | 10176 | 825854 | 16 | 102 | 6783 | 101086 |
| 2026-10-05 | 9630 | 776470 | 16 | 97 | 6530 | 97159 |
| 2026-10-12 | 10360 | 822913 | 21 | 104 | 7023 | 103597 |

Community matching across weeks (measured): of 876 community-weeks with a previous week, 842 are
`birth` and 34 `continue` (no merge or split); 9 first-week communities have a null event. So at
Jaccard >= 0.3 `community_id` has almost no continuity on full data. Diagnosis on 2026-09-28 ->
10-05 and 10-05 -> 10-12 (measured):
- Leiden is stable within a week: seed 42 vs seed 7 reproduce 12/14 and 18/24 communities at
  Jaccard >= 0.3.
- The node set churns: consecutive weeks share 32% of nodes (node Jaccard 0.321, 0.318); 33% of
  `org:` and 22% of `per:` nodes recur against 83% of `thm:`; 95% of the p90-99 and 100% of the top
  1% by weighted degree recur, but only 32% of the bottom half.
- Partitions also reshuffle: restricted to nodes present in both weeks, only 5/16 and 6/21 match.
  Communities are large (largest 2,997 and 3,217 nodes) on a dense graph (~800k edges, ~10k nodes).

Distributions over node-weeks (measured): median `new_nbr_rate` 0.606, median `deg_growth` -0.008.
