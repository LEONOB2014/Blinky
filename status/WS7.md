# WS7 status

Owner: claude-extend · Directories: `models/tgnn/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 21:58 UTC-5 · `feat/ws3-graph-metrics` (WS3 brief, output 4) · draft PR #5

## Done

- `models/tgnn/baselines.py`: week t -> t+1 link prediction on `edges_weekly`, persistence and
  unlimited EdgeBank (memory resets at a gap), plus the all-ties random reference. Targets:
  `new` (edges absent in week t) and `all`. Filtered ranking over week t+1's nodes, ties at their
  mean position; MRR with query and week-pair counts; bootstrap interval over week pairs only
  with >= 10 pairs. 7 unit tests on the dev slice.

## In progress

- Nothing. `reports/tgnn.md` written from the full profile.

## Blocked on

Nothing.

## Numbers (each marked measured or estimate)

Full profile, 51 weeks, 50 week pairs (`reports/tgnn.md`, measured; 95% bootstrap over week pairs):

| target | model | queries | MRR | 95% interval |
|---|---|---|---|---|
| new | persistence | 35,733,230 | 0.0002 | 0.0002 .. 0.0002 |
| new | edgebank | 35,733,230 | 0.0050 | 0.0042 .. 0.0059 |
| new | random | 35,733,230 | 0.0002 | 0.0002 .. 0.0003 |
| all | persistence | 75,167,096 | 0.0123 | 0.0115 .. 0.0133 |
| all | edgebank | 75,167,096 | 0.0061 | 0.0051 .. 0.0073 |
| all | random | 75,167,096 | 0.0003 | 0.0002 .. 0.0003 |

Reading: on new edges persistence cannot score (by definition) and EdgeBank's longer memory is the
only signal; on all edges last week beats the whole history, so recency matters more than long
memory. MRRs are low because each query ranks against ~10k nodes with binary scores, ties at the
mean position. The bar for any learned model: beat 0.0050 on new edges and 0.0123 on all edges.
