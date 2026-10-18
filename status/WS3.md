# WS3 status

Owner: claude-home · Directories: `graph/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:58 UTC-5 · `feat/ws3-graph-metrics` · draft PR #5

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

- Nothing. The full-profile run is done (below); the PR stays draft until the maintainer approves the push.

## Blocked on

Nothing outside the brief. Waiting on the scheduled WS1 input above.

## Notes for the lead

- CI installs no extras (`uv sync --locked`), so the graph tests skip there (visibly, via
  `pytest.importorskip`). Running them in CI needs `--extra graph` in `ci.yml` (outside this brief).
- The ring does not drop `per:` neighbours (the brief does not ask for it). The dev slice has
  none; on full ring-1 edges, person neighbours would reach the lake and the API. Say if they
  should be dropped.
- Topic universe: every org/thm node of the week, so the API can filter by `topic_id`. But WS4's
  `topic_scores_weekly` in the lake ranks the 12 subtopic ids (`agents`, `llms_models`, ...), not
  `org:`/`thm:` entities as `topic_daily` and the design do: a ranked topic's ring lookup returns
  nothing until WS4 and the lead settle the ranked unit.
- `per:` neighbours: 724,969 of 4,849,854 ring rows (15.0%) are persons, and 122,889 of 473,275
  node-week rows (measured). They are in the lake only; decide before the API serves the ring.
- Community matching does not hold on full data (see Numbers): changing the rule (for example
  Jaccard over the top-10%-degree core, or over nodes present in both weeks) is the lead's call;
  the code keeps the brief's rule.

## Numbers (each marked measured or estimate)

Full profile, `RADAR_PROFILE=full uv run python -m graph.build`, 2026-10-17 21:47 UTC-5: 51 weeks
(2025-10-27 .. 2026-10-12, contiguous), 37,766,030 edges in; 473,275 `node_metrics_weekly` rows and
4,849,854 `topic_context_1hop` rows written to `lake/gold/`, every row contract-valid. Run time
567 s, peak memory 2.55 GB (measured). The first week (2025-10-27) is partial (2,603 nodes against
6,301-11,365 afterwards), so 2025-11-03's `deg_growth` and rank deltas compare against a partial week.

Per week (measured; `ring_topics` = org/thm topics with at least one ring neighbour):

| wk | nodes | edges | communities | hubs | ring_topics | ring_rows |
|---|---|---|---|---|---|---|
| 2025-10-27 | 2603 | 182482 | 9 | 27 | 2144 | 34511 |
| 2025-11-03 | 9802 | 798741 | 21 | 99 | 6570 | 98959 |
| 2025-11-10 | 9301 | 723598 | 23 | 94 | 6258 | 92849 |
| 2025-11-17 | 10860 | 849909 | 28 | 109 | 7185 | 107076 |
| 2025-11-24 | 8257 | 655890 | 16 | 83 | 5763 | 88147 |
| 2025-12-01 | 8714 | 659506 | 17 | 88 | 5994 | 89936 |
| 2025-12-08 | 9272 | 745845 | 18 | 93 | 6259 | 95396 |
| 2025-12-15 | 8383 | 700955 | 17 | 84 | 5736 | 88643 |
| 2025-12-22 | 6451 | 573536 | 17 | 65 | 4732 | 74856 |
| 2025-12-29 | 6301 | 545081 | 13 | 64 | 4683 | 73001 |
| 2026-01-05 | 8648 | 717306 | 14 | 87 | 5962 | 91475 |
| 2026-01-12 | 8819 | 741257 | 20 | 89 | 6034 | 92312 |
| 2026-01-19 | 8916 | 728918 | 17 | 90 | 5965 | 91138 |
| 2026-01-26 | 9276 | 742416 | 20 | 93 | 6247 | 94279 |
| 2026-02-02 | 8844 | 698014 | 23 | 89 | 5962 | 89484 |
| 2026-02-09 | 9593 | 745200 | 21 | 96 | 6324 | 95086 |
| 2026-02-16 | 9886 | 801902 | 17 | 99 | 6466 | 98069 |
| 2026-02-23 | 10328 | 837759 | 15 | 104 | 6881 | 102826 |
| 2026-03-02 | 9096 | 751511 | 14 | 91 | 6418 | 97025 |
| 2026-03-09 | 9271 | 730309 | 19 | 93 | 6483 | 95963 |
| 2026-03-16 | 9805 | 775509 | 19 | 99 | 6565 | 99466 |
| 2026-03-23 | 9155 | 713106 | 16 | 92 | 6311 | 93793 |
| 2026-03-30 | 7988 | 627373 | 24 | 80 | 5631 | 86140 |
| 2026-04-06 | 8165 | 627417 | 20 | 82 | 5632 | 85709 |
| 2026-04-13 | 9028 | 716451 | 19 | 91 | 6242 | 95111 |
| 2026-04-20 | 9617 | 721893 | 17 | 97 | 6327 | 93923 |
| 2026-04-27 | 9909 | 796885 | 22 | 100 | 6573 | 98172 |
| 2026-05-04 | 9484 | 716758 | 16 | 95 | 6161 | 90131 |
| 2026-05-11 | 10484 | 883393 | 18 | 105 | 6998 | 105450 |
| 2026-05-18 | 10637 | 844559 | 13 | 107 | 7115 | 106117 |
| 2026-05-25 | 10205 | 834821 | 16 | 103 | 6839 | 103917 |
| 2026-06-01 | 10691 | 838932 | 20 | 107 | 7228 | 106192 |
| 2026-06-08 | 9997 | 789336 | 14 | 100 | 6967 | 102590 |
| 2026-06-15 | 8977 | 701425 | 23 | 90 | 6201 | 92619 |
| 2026-06-22 | 9992 | 766247 | 12 | 100 | 6774 | 101213 |
| 2026-06-29 | 8980 | 695386 | 21 | 90 | 6195 | 92572 |
| 2026-07-06 | 9389 | 725132 | 10 | 94 | 6496 | 96450 |
| 2026-07-13 | 9897 | 799004 | 16 | 99 | 6818 | 102848 |
| 2026-07-20 | 9758 | 759401 | 13 | 98 | 6641 | 98108 |
| 2026-07-27 | 9863 | 767030 | 21 | 99 | 6719 | 101440 |
| 2026-08-03 | 9206 | 720385 | 16 | 93 | 6344 | 94750 |
| 2026-08-10 | 8827 | 670624 | 16 | 89 | 6076 | 89990 |
| 2026-08-17 | 8832 | 692544 | 17 | 89 | 6129 | 92551 |
| 2026-08-24 | 9684 | 783057 | 16 | 97 | 6728 | 102423 |
| 2026-08-31 | 9330 | 705039 | 16 | 94 | 6386 | 94507 |
| 2026-09-07 | 10268 | 804099 | 16 | 103 | 6934 | 103562 |
| 2026-09-14 | 11365 | 975857 | 12 | 114 | 7436 | 111986 |
| 2026-09-21 | 10955 | 958995 | 14 | 110 | 7374 | 110507 |
| 2026-09-28 | 10176 | 825854 | 16 | 102 | 6802 | 102420 |
| 2026-10-05 | 9630 | 776470 | 16 | 97 | 6543 | 98890 |
| 2026-10-12 | 10360 | 822913 | 21 | 104 | 7032 | 105276 |

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
