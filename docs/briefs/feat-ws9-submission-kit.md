# BRIEF: WS9, the submission kit (showcase stories, demo script, live checks, video plan)

Account: **Claude #2 (claude-work)** · Branch: `feat/ws9-submission-kit` · Worktree: `../radar-worktrees/feat-ws9-submission-kit`
Written by the orchestrator, 2026-10-18 01:55 UTC-5. Read `AGENTS.md`, then this file.

## Goal

Everything the submission at 11:30 needs that is not code in `web/`: three showcase stories built from
our own measured data, the 5-minute demo script, a live check of the public site, and the plan for the
narrated video. Prepared now so the last hours are rehearsal, not writing.

## Plan reference

MASTER_PLAN §16 ("10:00 feature freeze: Netlify + static fallback + recorded tier-1 video; rehearse
twice"; "10:30-11:30 submission text and screenshots"; must-haves 1-7) and the "three showcase
stories for the pitch, each with onsets, driving edges and the emotional angle";
`docs/designs/radar-build-plan.md` "Demo order (5 minutes)".

## Rules for every word (the maintainer's, not negotiable)

- Only our own measured results and checkable primary sources. Every number marked measured or
  estimate, with its denominator. Where the data shows no signal, say so.
- Never name, cite or compare to other teams, competitors or outside material.
- No headlines, URLs or person names in git (`docs/submission/` is committed: use topic ids,
  counts, dates; titles may appear only in files under `lake/`).

## Outputs

1. `docs/submission/stories.md`: **three showcase stories** from the latest scored week's top 10
   (read them from `topic_scores_weekly`; WS4's eligibility gate is in, the list may still change
   before 06:00, so make the script re-runnable). For each: the topic, its stage and decision, the
   English and es/pt onsets (window chip), the weekly series, its 1-hop ring's strongest neighbours
   (the "driving edges"), the emotional framing angle, and one sentence on what 30X could publish.
   Built by `scripts/showcase_stories.py` from the agents' tools (`agents/tools.py`), never by
   hand-copying numbers.
2. `docs/submission/demo_script.md`: the 5-minute demo in Spanish, step by step, following the demo
   order (hook; top 10 with why and angle; trust: backtest, filter P/R, cost ledger, ToS-clean
   sources; close: GPU temporal graph sweep then the story view of the #1 topic). For each step:
   what to click or ask the chat, what appears, the one sentence to say, and a fallback if it fails
   (static site, screenshot). Leave clearly marked slots for numbers that arrive later (backtest
   05:00, human-checked filter P/R 06:30): `[PENDIENTE: backtest]`.
3. `docs/submission/submission_text.md`: a draft of the submission text (what it does, how, the
   evidence, the stack, the links), with the same `[PENDIENTE]` slots.
4. `scripts/demo_check.py` + `make demo-check`: hits the public Netlify site and the Cloud Run API
   (URL from `gcloud run services describe`, never committed): pages 200, top 10 present, freshness,
   one timeline, one ring, and one chat turn only with `--chat` (it spends Nebius credit). Prints a
   pass/fail table with latencies. Run it once and record the result.
5. `docs/submission/video_plan.md`: the narrated video without an editor, following the maintainer's
   recipe (one audio take per script block; ffmpeg maps each take to frames sized to its duration,
   `loudnorm`, `concat`): the shot list matching the demo script, how each shot is captured (headed
   Chrome window, never headless for WebGL), file names, and the exact ffmpeg commands. Do not record
   the voice: the maintainer does.
6. `status/WS9.md` (new).

## Files you may touch

`docs/submission/**`, `scripts/showcase_stories.py`, `scripts/demo_check.py`, `Makefile` (a
`demo-check` target), `status/WS9.md`.

## Out of scope

`web/` (Antigravity is building the graph views there), agents, models, deploy changes, the backtest
itself. The evidence cards in the UI come after the graph views merge.

## Acceptance

- `make check && make test` pass; `make demo-check` passes against the live site (result in the
  status); `scripts/showcase_stories.py` re-runs cleanly and regenerates `stories.md`.
- No headline, URL (other than our own public site and repo) or person name in `docs/submission/`.

## Paid or outward actions needing approval

Approved: `make demo-check` against our own public site, including one `--chat` turn. Nothing is
published or submitted: the maintainer submits.

## Machine limits

Memory is short until the Google Drive copy ends (~03:00): no full-lake builds; Python under ~1 GB.

## Deadlines (UTC-5)

Stories and demo-check by **03:30**; demo script, submission text and video plan by **05:00**.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS9.md`, then stop.
