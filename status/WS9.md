# WS9 status

Owner: claude-work · Directories: `docs/submission/`, `scripts/showcase_stories.py`, `scripts/demo_check.py`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 01:14 UTC-5 · branch `feat/ws9-submission-kit` · committed locally, the orchestrator pushes.

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
