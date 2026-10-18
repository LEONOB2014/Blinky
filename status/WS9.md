# WS9 status

Owner: claude-work · Directories: `docs/submission/`, `scripts/showcase_stories.py`, `scripts/demo_check.py`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 01:50 UTC-5 · branch `feat/ws9-demo-hardening` (WS9b) · committed locally, the orchestrator pushes.

Previous: 2026-10-18 01:14 UTC-5 · branch `feat/ws9-submission-kit` · committed locally, the orchestrator pushes.

## WS9b: demo hardening

**Cold start, measured (2026-10-18 06:48 UTC, after 17.7 min idle).** Run with
`deploy/cold_start.py --chat`, from the maintainer's laptop, so times include the network:

| Request | Status | Time |
|---|---|---|
| First request, `/api/freshness` (a container starts) | 200 | **10.00 s** |
| `/api/radar` right after | 200 | 1.53 s |
| `/api/radar`, warm | 200 | 0.18 s |
| One chat turn | 200 | 12.48 s |

- The log shows a new container started after the first request (cold start confirmed). The
  script first counted both of that container's startup lines as two starts; it now counts only
  `Started server process`.
- So a judge arriving after 15 idle minutes waits about 10 s for the first panel. `deploy/README.md`
  has the `--min-instances=1` / `0` commands and the cost from Cloud Run's published pricing
  (us-central1, request-based billing): about **$0.018 per hour** for an idle warm 1 vCPU / 1 GiB
  instance (estimate), about $0.06 for the 09:00-12:30 window today.
- **Not applied:** min-instances is the maintainer's decision. `make redeploy-all` now keeps
  whatever value is set (`deploy-cloudrun` used to force 0).

**Evidence offline.** `deploy/evidence.py`, called by `deploy/export_static.py`, writes
`web/public/data/evidence/`:
- `backtest.json` and `label_quality.json`: every heading's tables and bullets, verbatim;
  `{"available": false}` while a report is missing (`reports/backtest.md` is not on `develop` yet);
- `ledgers.json`: on this branch's ledgers, BigQuery 63 jobs / 376.83 GB billed, Jev 981 calls /
  $0.0443 / median 377 ms (measured);
- `index.json`.

On the dev slice it writes 15.8 KiB. Three unit tests check that tables and bullets are kept
verbatim and that the ledger totals equal the CSVs.

**The final redeploy.** `scripts/redeploy_all.sh` (`make redeploy-all`, `ARGS=--run` to deploy):
1. preconditions (gcloud project, Netlify site id, API URL, current min-instances);
2. `topic_scores_weekly` is stable: same md5 5 s apart and written at least 2 min ago;
3. `make deploy-cloudrun` (Cloud Build), then the shipped scores md5 must equal the lake's;
4. `make deploy-static`;
5. the web build with the API URL;
6. the Netlify production deploy;
7. `make demo-check`.

The dry run at 01:44 passed every precondition and printed each deploy command without running it
(8.5 s, measured).

**Stories after WS4's syndication guard (READY FOR REDEPLOY 01:36).** `stories.md` was regenerated:
- Single-pattern topics in the W42 top 10 fell from 5 to 1 (measured).
- The new top 10 includes University College London, Sandisk, Comcast, Kroger, Founders Fund and
  SB Energy.
- Showcases are unchanged: Marsh McLennan, Rocket Lab, National Stock Exchange.
- The remaining flag is `org:kroger` (#8). My stories rule (the strongest ring neighbour co-occurs
  in 93% of its 201 articles) flags it, but WS1c's `topic_sources_weekly` shows 193 sources and a
  pattern share of 0.59, so WS4's guard passes it rightly.
- The two rules measure different things. Aligning the stories script with the pattern share would
  make the demo text match the gate; it is a small change, left for the orchestrator to decide.

**Rehearsal shots:** waiting for the Drive copy to end (~03:00). At 01:49, 54% of memory was free
and Google Drive was still running.

## Done

- `scripts/showcase_stories.py` writes `docs/submission/stories.md` from the agents' tools
  (`get_top10`, `get_topic_series`, `get_context_1hop`, `labels_es`, `get_freshness`). It refuses
  unless `RADAR_PROFILE=full`.
  - Re-run check: two runs give identical output apart from the timestamp. Peak memory 0.35 GB
    (measured).
  - It writes the latest scored week's top-10 diagnostic, then the three showcase stories. Each
    story has stage and decision, window chip, English and es/pt onsets, the 8-week series by
    language, the 5 strongest ring neighbours, the angle, the why, and a suggested piece (marked as
    an editorial suggestion, not a measurement).
  - Two stated rules decide what is shown:
    - Onset: the first of the last 12 weeks with at least 5 articles and at least 3× the median of
      the earlier weeks. It is a display rule; the chip itself uses WS4's daily z_7d > 2 rule.
    - Concentration: the share of the week's articles that co-mention the strongest neighbour. At
      90% or more, a topic is flagged as a single-pattern week and never chosen.
- `scripts/demo_check.py` + `make demo-check` (`ARGS=--chat` adds one real chat turn). The API URL
  is read from `gcloud` at run time and never written to git.
- `docs/submission/demo_script.md`: the 5-minute demo in Spanish, step by step. Each step has what to
  do, what appears, the sentence to say and a fallback. It has the `[PENDIENTE]` slots for the
  backtest and the human-checked filter P/R. It also warns that the chat limit (10 turns per 10 min
  per IP) can trip during rehearsal.
- `docs/submission/submission_text.md`: draft in Spanish (what it does, how, evidence table, sources
  and ToS, stack, links), with the same slots. Every number cites its file.
- `docs/submission/video_plan.md`: the shot list matching the script (headed Chrome for WebGL) and
  the file names.
  - It has the exact ffmpeg commands: per-block segments sized to each take, `loudnorm`, `concat`.
  - I tested them end to end on synthetic inputs (2 s tones, generated images, a 2 s clip): the
    output was 26.11 s, matching the 26 s of input, H.264 1920x1080, AAC 48 kHz (measured).
  - That test caught a concat-path bug (entries are relative to the list file), now fixed.
- Audit of `docs/submission/`: the only URLs are our site, our repo and a localhost address; no
  `per:` ids, no headlines.

## Numbers (each marked measured or estimate)

`make demo-check ARGS=--chat`, 2026-10-18 01:05 UTC-5: **8/8 PASS** (measured; seconds from the
maintainer's laptop, network included).

| Check | Result | Seconds | Detail |
|---|---|---|---|
| site: page | PASS | 0.58 | HTTP 200 |
| site: static top 10 | PASS | 0.26 | 10 topics |
| api: freshness | PASS | 0.75 | profile full, scores 2026-W42, daily 2026-10-18 |
| api: top 10 | PASS | 1.38 | #1 org:marsh mclennan |
| live top 10 == static top 10 | PASS | 0.00 | same top 10 |
| api: timeline of #1 | PASS | 0.68 | 20 days |
| api: 1-hop ring of #1 | PASS | 1.00 | 20 neighbours, 0 persons |
| api: one chat turn | PASS | 11.98 | 8 trace steps, 3 cards |

Showcase diagnostic for 2026-W42 (measured, `stories.md`):
- 5 of 10 top topics are single-pattern weeks (concentration ≥ 90%): `org:euronext` 97%,
  `org:kioxia holdings` 96%, `org:ministry of science` 93%, `org:sterling` 92%,
  `org:adani enterprises` 90%.
- 2 of 10 show an es/pt onset within 12 weeks.
- Stories: `org:marsh mclennan` (#1), `org:rocket lab` (#4), `org:national stock exchange` (#5).

## For the orchestrator and other lanes

- **The showcase stories are honest but weak.**
  - #1 Marsh McLennan's ring is mostly unemployment-benefit themes (29 of its 44 articles).
  - Rocket Lab's strongest neighbours co-occur only 3 times each.
  - None of the three has an es/pt onset yet.
  - The W42 top 10 leans on finance and wire copy: Euronext's 149 articles share one syndicated
    pattern (145 of them co-mention the same outlet and currency themes).
  - Worth a WS4 look before 06:00, for example a syndication or concentration penalty in the
    eligibility gate. When WS4 rescores, re-run `scripts/showcase_stories.py`.
- `org:big news network` and `org:big new network` (syndication outlets) appear in rings; they are
  candidates for `ranked_universe.org_deny`.
- A correction to the time span I reported earlier tonight: the history is 2025-11-01..2026-10-18,
  about 11.6 months, not 12.5 (that figure was only ever in chat, never in git; the docs here use
  the dates).

## Blocked on

Nothing.
