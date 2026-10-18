# WS9 status

Owner: claude-work · Directories: `docs/submission/`, `scripts/showcase_stories.py`, `scripts/demo_check.py`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 06:25 UTC-5 · branch `docs/ws9-final-redeploy` (the final redeploy of `develop` 0a006f8) · committed locally, not pushed.

Previous: 2026-10-18 05:34 UTC-5 · branch `docs/ws9-predeploy-check` (pre-deploy check of `develop` e830a28, no deploy) · committed locally, not pushed.

Previous: 2026-10-18 05:30 UTC-5 · branch `feat/ws9-final-data` · committed locally, the orchestrator pushes.

Previous: 2026-10-18 04:54 UTC-5 · branch `docs/ws9-redeploy-0500` (the 05:00 redeploy of `develop` e4518d2) · committed locally, the orchestrator pushes.

Previous: 2026-10-18 02:26 UTC-5 · branch `feat/ws9-demo-hardening` (WS9b) · committed locally, the orchestrator pushes.

Previous: 2026-10-18 01:14 UTC-5 · branch `feat/ws9-submission-kit` · committed locally, the orchestrator pushes.

## Final redeploy of `develop` 0a006f8 (orchestrator's order, 06:15, approved)

Run from `../radar-worktrees/deploy-develop`, moved to `origin/develop` 0a006f8: design redesign (PR #46),
agent fixes (PR #47), pre-deploy check (PR #45).

**Result: every check passed. 0 steps failed; nothing was fixed on the live service.**

- **Dry run** (`make redeploy-all`): passed, 9.3 s, every step listed. Steps 0-6 include the new
  3b (graph views after the static wipe). Current min-instances is 0, and it was kept.
- **`make redeploy-all ARGS=--run`: 3 min 27 s** (measured):
  - Cloud Run revision **`radar-api-00006-vw5`**, built with Cloud Build;
  - static export, 7.53 MiB;
  - 3b graph views: temporal 1,000 nodes / 44,005 edges / 13 weeks, plus 15 stories;
  - web build;
  - Netlify production deploy (579 files);
  - closing `make demo-check`: **7/7**.
- **Live checks** (measured):

  | Check | Result |
  |---|---|
  | `make demo-check` | 7/7 (inside the run) |
  | `make demo-check ARGS=--chat` | **8/8** (chat turn 10.2 s, 8 trace steps, 3 cards) |
  | `/fallback/temporal.png` | **200** (312 KB) |
  | `/data/views/temporal.json` | **200** (3.79 MB) |
  | First API request after the deploy (`/api/freshness` in the closing check) | 2.48 s |

- **The 4 questions on the live chat** (W42 #1 Marsh McLennan): **4/4 pass** (the right tools ran
  with data; the Auditor found no unsourced number).

  | # | Question | Tools (data available) | Answer |
  |---|---|---|---|
  | 1 | ¿Qué contenido preparo…? | `get_topic_brief`, `get_topic_evidence`, `get_topic_sources`, scores | The brief's format, angle, 92 and 65 |
  | 2 | ¿Qué artículos respaldan…? | `get_topic_evidence`, `get_topic_sources` | A code-written evidence block: "44 artículos de 39 medios" and 5 outlets with date, language and title |
  | 3 | ¿Cuántos medios distintos…? | `get_topic_sources` | **39** (expected 39), plus the evidence block |
  | 4 | ¿En qué subtemas…? | scores, sources, evidence | Inversión y mercados, chips e infraestructura |

  - Latency 13.6 / 12.1 / 8.9 / 8.5 s; 31,054 tokens for the 4 turns (estimate: under $0.01).
  - Defects D1 and D2 of the pre-deploy check are **fixed live**: the outlet count is 39, and the
    evidence is shown.
- **Rehearsal screenshots**, headed Chrome with WebGL at 1440x900, in `lake/submission/shots/`
  (git-ignored; the 04:52 shots of the old UI moved to `old-ui-0452/`):

  | File | What it shows |
  |---|---|
  | `01_default.png` | Default view: top 10 and the temporal graph. First frame 0.74 s, ANGLE Metal on the M1 Pro (measured). |
  | `02_fullscreen.png` | The in-app full screen ("Salir (Esc)") |
  | `03_lens_momento.png` | Momento lens |
  | `04_lens_puente.png` | Puente lens |
  | `05_card_detail.png` | #1 card detail |
  | `06_trust.png` | Trust panel |
  | `07_chat_evidence.png` | A chat answer with the evidence block and "Auditor: verificado" |

  The page threw no exceptions during the walk.

**Remaining defects** (seen live; for the design and agents lanes; nothing changed):
- R1: the evidence answer prints the decision line twice.
- R2: the title dedupe misses copies that differ only by a site suffix.
  - Example: two of the 5 Marsh McLennan W42 articles are the same story ("Wall Street muscles
    higher…"), one with " - Boston News, Weather, Sports" appended.
  - Fix in S14: drop a trailing " - <site>" before normalizing (about 1.1 GiB).
- R3: D3 of the pre-deploy check is still there.
  - The subtopics answer says "crecimiento muy rápido en Latinoamérica" (there is no es/pt
    coverage) and adds a made-up sector story.
  - The other three are clean of it in this run.
- R4 (design): the chat panel overlaps the graph's right edge, clipping labels. Inside the chat
  panel's decision card the topic name renders dark on dark. The trust panel does not close with
  Escape (only "Ocultar confianza").
- Fixed by the design lane, seen live: audience fit is now marked as an estimate on the card
  ("Encaje LatAm: 65% ○").

**Cold start**, `deploy/cold_start.py` on `radar-api-00006-vw5`, measured at 11:42 UTC (06:42 UTC-5)
after **18.0 min** idle, from the maintainer's laptop:

| Request | Status | Time |
|---|---|---|
| First request, `/api/freshness` | 200 | **5.37 s** |
| `/api/radar` right after | 200 | 0.40 s |
| `/api/radar`, warm | 200 | 0.18 s |

- One container start was logged after the first request (cold start confirmed).
- That is about half the 10.0 s measured on revision 00002 (01:48). The image is larger now
  (11 lake tables, 87.6 MiB), so the difference is probably container start-up variance, not an
  improvement (not tested).
- min-instances stays 0. The warm-instance commands and cost are in `deploy/README.md`: about $0.018
  per hour idle (estimate). Your decision.

## Pre-deploy check of `develop` e830a28 (orchestrator's order, 05:38; no deploy)

The `deploy-develop` checkout was moved to `origin/develop` e830a28. Its API ran locally on
**port 8011** (`RADAR_PROFILE=full`, LangSmith tracing off so the test questions stay out of the
traces) over the shared lake, and was stopped afterwards (checked: 8011 free).

**Result: 3 checks; 2 pass outright. The chat check passes the Auditor 4/4 but fails on content
2 of 4.**

1. `RADAR_API_URL=http://127.0.0.1:8011 scripts/demo_check.py`: **7/7 PASS** (measured). The site
   checks still read the live Netlify site; local `/api/radar` equals Netlify's static top 10.
2. **Chat, 4 questions that need the new tables** (Marsh McLennan, the W42 #1):

   | # | Question | Tools that ran (data available) | Auditor | Answers from the tool data? |
   |---|---|---|---|---|
   | 1 | ¿Qué contenido preparo esta semana sobre Marsh McLennan? | `get_topic_brief`, `get_topic_evidence`, scores, series | pass | **pass**: the brief's format, angle, 92 and 65 |
   | 2 | ¿Qué artículos respaldan a Marsh McLennan…? | `get_topic_evidence` (5 articles, 5 outlets), scores | pass | **fail**: names no article and no outlet; answers about growth instead |
   | 3 | ¿Cuántos medios distintos cubren a Marsh McLennan…? | scores, series, evidence; **no tool reads `topic_sources_weekly`** | pass | **fail, wrong fact**: "44 medios distintos". 44 is the article count; the measured outlet count is 39. |
   | 4 | ¿En qué subtemas de IA cae Marsh McLennan…? | scores (`subtopics`), series, evidence; **no tool reads `topic_subtopic_weekly`** | pass | **pass**: inversión y mercados, chips e infraestructura, from the scores row |

   - Auditor 4/4 (no veto: "todos los números de la respuesta tienen fuente"); content 2/4 (judged
     by reading each answer against its tool results).
   - "más del 900%" in answer 3 traces to the scores' "cuota 7d más de 10 veces", so it is not
     invented.
   - Latency 12.5 / 8.0 / 6.5 / 6.5 s.
   - **Spend:** 29,946 tokens in total for the 4 turns. At Qwen3-30B rates this is well under the
     $0.10 limit (estimate: under $0.01).
3. `deploy/export_static.py` into a scratch folder: **PASS**. 212 evidence files, 240 topic-weeks,
   1,191 articles, **0 topic-weeks with duplicate titles** (measured).

**Defects (for the orchestrator; nothing changed here):**

- **D1, no tool for two of the four new tables.** `topic_sources_weekly` and `topic_subtopic_weekly`
  are now staged in the image (PR #44), but no agent tool reads them.
  - "¿cuántos medios?" gets a wrong number: the article count presented as the outlet count. The
    Auditor cannot catch it, because 44 is a real number in the data.
  - Fix: a `get_topic_sources(topic_id, week)` tool returning `n_articles`, `n_sources` and the top
    source shares, added to the Signal analyst's plan for named topics. Subtopics already come from
    the scores row, so `topic_subtopic_weekly` (per-subtopic article shares) is optional.
- **D2, evidence is fetched but not shown.** For an evidence question the Media Master does not list
  the outlets, dates or titles that `get_topic_evidence` returned. Fix: route "artículos /
  evidencia / fuentes / medios" questions to a code-written evidence block (outlet, date, language,
  title), as the decision line is written by code.
- **D3, the same invented framing in every answer.** All four end with a made-up story ("cómo la
  firma está redefiniendo la gestión de riesgos en América Latina", "cómo las aseguradoras usan IA
  en riesgos financieros"). No tool data supports it, and the number-only Auditor cannot see it.
  Answer 1 also reads the subtopic categories as the company's business ("su expansión en mercados
  de financiamiento e infraestructura de chips"), the overclaim the briefs' prompt now forbids. Fix:
  the same rules in the Media Master's prompt (no causes or narratives beyond the data; subtopics
  are categories).

## Final data fixes (orchestrator's decisions on the 05:00 findings), branch `feat/ws9-final-data`

The findings themselves and the 05:00 redeploy record are on `docs/ws9-redeploy-0500` (the orchestrator
lands it).

1. **The image stages all 11 lake tables.** `deploy/push_lake.py` `TABLES`, which
   `deploy/cloudrun_stage.py` reuses, adds `topic_briefs_weekly`, `topic_evidence_weekly`,
   `topic_sources_weekly` and `topic_subtopic_weekly`.
   - Dry run: 87.6 MiB in total (was 81.8), measured.
   - **Not deployed:** the final redeploy comes after the design work merges. Until then the live
     chat's `get_topic_brief` and `get_topic_evidence` still answer "not available".
2. **Evidence deduplicated by normalized title** (`bq_sql/s14_topic_evidence_weekly.sql`).
   - The normalized title is lowercase with every run of non-letters and non-digits collapsed. An
     empty or missing title counts as its own title.
   - Order: keep the earliest copy of each title, then one article per outlet, then the relevance
     order, refilled to 5 from other titles. The rule is in `why_selected`.
   - Re-run on the same 240 topic-weeks (top 30 of the 8 weeks 2026-08-24..2026-10-12, checked
     identical): billed **1.12 GiB** (measured).
   - **Before:** **177 of 240** topic-weeks (74%) had duplicate titles, and **463 of the 1,200**
     article slots (39%) were repeat copies. In the worst cases, `org:ai safety institute` (W38),
     `org:australian recording industry association` (W35) and `org:marsh mclennan` (W42), all 5
     slots were one title.
   - **After:** 0 duplicates; 1,191 rows. 235 topic-weeks have 5 articles; 5 have fewer because
     they lack 5 distinct titles (1 has 2, 2 have 3, 2 have 4). `org:marsh mclennan` W42 now shows 5
     distinct titles from 5 outlets.
   - The lake file was re-exported (1,000 sampled rows valid).
   - A new data test fails on any duplicated normalized title per topic-week; the evidence data
     tests pass.
   - The static JSON was regenerated (`web/public/data/evidence/topics/`, 212 files, git-ignored);
     the final redeploy ships it.
   - What the duplicates say: in three topic-weeks of four, the evidence used to be partly one
     syndicated story. The radar's volume counts (`topic_sources_weekly.n_articles`) still count
     each copy. WS4's guard limits that with the pattern share and the top-source share, not with
     titles.
3. Items 3 (the "medido" label on audience fit) and 4 (the raw markdown in the trust panel) went to
   Grok's design lane.

## Redeploy of `develop` e4518d2 (orchestrator's order, ~04:50 UTC-5)

Run from `../radar-worktrees/deploy-develop`, a detached checkout of `origin/develop` at e4518d2: graph
lenses and full screen, cards, briefs, evidence, feedback endpoint, LangSmith on Cloud Run.

- `uv sync --extra api --extra graph`, then
  `RADAR_PROFILE=full uv run --extra graph python -m graph.export_views` (12 s, measured):
  - temporal: 1,000 nodes and 44,005 edges over 13 weeks (2026-07-20..2026-10-12), 3.79 MB;
  - story of `org:marsh mclennan` 2026-W42, plus 14 other stories.
- `.env` here lacked `NETLIFY_SITE_ID` (the script's precondition); added from the WS8 `.env`
  (git-ignored). The LangSmith secret `radar-langsmith-key` exists and the Cloud Run service
  account can read it (checked).
- `make redeploy-all ARGS=--run`, **3 min 17 s** (measured):
  - scores stable;
  - Cloud Run revision **`radar-api-00005-8sm`** (09:49 UTC), built with Cloud Build;
  - static export, web build;
  - Netlify production deploy (575 files);
  - `make demo-check`: **7/7 passed**.
- `make demo-check ARGS=--chat`: **8/8 passed** (chat turn 8.95 s, 8 trace steps, 3 cards; measured).
- **Feedback:** a chat turn returned `trace_id` `01a14e6c-1306-71c0-99db-b85e9400ced6` (10.8 s).
  `POST /api/feedback` on it answered **202**, `{"recorded": true}`, in 0.54 s (measured). Its
  comment says "deploy check 2026-10-18 (not a user rating)", so it can be filtered out of the real
  usefulness scores.
- **Public site** (https://radar-senal-temprana.netlify.app), walked in a **headed** Chrome window
  over the DevTools protocol, the same approach as `graph/views/measure.mjs`. Screenshots are in
  `lake/submission/shots/` (not in git).
  - `00_site_full.png`, `01_cards.png`: the cards with the "Confianza" button, view tabs and the
    Brief and Evidencia expanders.
  - `02_brief.png`: the #1 brief with "verificado por el Auditor" and its cited numbers.
  - `03_evidence.png`: 5 evidence articles.
  - `04_trust.png`: the trust panel (BigQuery 380.75 GB in 66 jobs, Jev 981 calls, the
    label-quality report verbatim).
  - `05_temporal.png`: the GPU temporal graph; `window.__metrics`: ANGLE Metal on the M1 Pro, first
    frame 1.24 s, 1,000 nodes, 3,463 edges in W42, week switch 3.5 ms (measured).
  - `06_story.png`: "Historia 1-salto" switches the temporal graph to the Historia lens focused on
    the #1 topic.
- All the static data files answer 200 (views, briefs, per-topic evidence, `evidence/backtest.json`,
  `label_quality.json`, `ledgers.json`). The page logs 404s only for evidence of the UI's default
  context entities (nvidia, google, microsoft, openai group, TECH_AUTOMATION), which are not in a
  top 10 and so have no evidence file. Harmless, but console noise.

**Found in the checks (for the orchestrator; nothing changed here):**

1. **The Cloud Run image does not ship the briefs or the evidence.**
   - `deploy/push_lake.py` `TABLES` (used by `cloudrun_stage.py`) still lists the original 7.
     `topic_briefs_weekly`, `topic_evidence_weekly`, `topic_sources_weekly` and
     `topic_subtopic_weekly` exist in the lake but not in the image.
   - The live chat's `get_topic_brief` and `get_topic_evidence` return "not available". A chat
     about Marsh & McLennan called only `get_top10` and `get_topic_series`.
   - The cards are fine: they read the static files.
   - Fix: add the four tables to `TABLES` and rerun `make deploy-cloudrun` (~2.5 min). One line in
     `deploy/`; I can do it on your word.
2. **The #1 topic's evidence is one wire story five times.** `org:marsh mclennan` W42's 5 evidence
   articles are the same syndicated title from five outlets.
   - It passed WS4's guard (pattern share 0.66 < 0.9, 39 sources) because the copies carry varied
     co-mentions.
   - The evidence rule (one per outlet) does not dedupe identical titles.
   - Two candidate fixes: S14 keeps one article per title, and WS4 adds a title-duplication signal
     to the guard. Both are cheap (S14 about 1.1 GiB).
3. **The card labels audience fit as measured.** "Encaje LatAm: 65% (medido)" on the card, while its
   own bullet and the contract call it an estimate (regla v1). WS5, one word.
4. The trust panel shows `label_quality.md` as raw markdown (tables as pipes). Readable, but it
   looks unfinished in the video.

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

**Interim redeploy (orchestrator's order, ~02:25 UTC-5), `make redeploy-all ARGS=--run`, measured:**
- The `topic_scores_weekly` checksum was stable before the run, and the shipped copy equals the lake's
  (md5 `8876536416ad47422b1ae3e2fc05483f`).
- Cloud Run revision `radar-api-00004` (07:25 UTC), built with Cloud Build.
- The static export and web build ran, then the Netlify production deploy (7 s, 334 files).
- The whole run took 2 min 40 s.
- The script's last step crashed: `make` passed the caller's `ARGS=--run` down into the nested
  `make demo-check`, and `demo_check.py` does not accept `--run`.
  - Every deploy before it had succeeded (the script stops on any earlier failure).
  - Fixed in `scripts/redeploy_all.sh` (the nested call now clears `ARGS`).
  - Re-run by hand: `make demo-check` **7/7 passed**.
- The public 2026-W42 top 10, identical on the live API (`/api/radar?week=2026-W42`) and on Netlify's
  static `/data/radar/2026-W42.json` (and `latest.json` equals the live list):
  marsh mclennan, rocket lab, national stock exchange, university college london, citigroup, sandisk,
  comcast, kroger, founders fund, sb energy.
- **`org:euronext`, `org:adani enterprises`, `org:kioxia holdings`, `org:sterling` and `org:yahoo`
  are absent from both (checked, measured).**

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
