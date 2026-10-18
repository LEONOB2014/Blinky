# WS7 status

Owner: claude-extend · Directories: `models/tgnn/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 20:58 UTC-5 · `feat/ws3-graph-metrics` (WS3 brief, output 4) · draft PR #5

## Done

- `models/tgnn/baselines.py`: week t -> t+1 link prediction on `edges_weekly`, persistence and
  unlimited EdgeBank (memory resets at a gap), plus the all-ties random reference. Targets:
  `new` (edges absent in week t) and `all`. Filtered ranking over week t+1's nodes, ties at their
  mean position; MRR with query and week-pair counts; bootstrap interval over week pairs only
  with >= 10 pairs. 7 unit tests on the dev slice.

## In progress

- `reports/tgnn.md` is written only on the full profile, after the full graph run.

## Blocked on

Nothing; waiting on WS1's full `edges_weekly` (22:30).

## Numbers (each marked measured or estimate)

- None reported yet (dev-slice numbers are never reported).
