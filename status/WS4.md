HANDOFF (orchestrator, 02:25 UTC-5): claude-extend reached its weekly limit; the orchestrator
continues this lane. State: syndication guard and secondary backtest merged (PR #25). Primary backtest
(exact Wikidata matches) coverage at 02:23: published radar 282/440 (64.1%), gate without guard
263/440, no gate 261/440, raw-count growth 191/440 (43.4%), persistence 427/440 (measured); precision
withheld below 90%. WS6 is fetching the 336 missing topics (exact by 03:15, all by 03:45). Next: rerun
`RADAR_PROFILE=full POLARS_MAX_THREADS=4 uv run --extra models python -m models.backtest` after each WS6
write (peak 1.32 GB, 9 s, measured), final run at >= 90%.

# WS4 status

READY FOR REDEPLOY (01:36 UTC-5, Addendum 5): `lake/gold/topic_scores_weekly.parquet` was rebuilt
with the syndication guard in the eligibility gate (16,904 rows, 46 weeks, 4,911 topics, 0 contract
violations, measured). It also uses WS6's larger `topic_wikidata` (01:27: 11,060 rows, 1,916 exact).

## WP2: scores and backtest on the AI lexicon (09:05 UTC-5, branch `feat/ws4-ai-ranking`, claude-cacho; committed locally, the orchestrator pushes)

**Pipeline**
- `--source ai` on `models.build_scores` and `models.backtest` (`models/source.py`). The default
  GDELT run is unchanged: rebuilding `topic_scores_weekly` gives the same 16,904 rows, every column
  equal (*measured*).
- **Outputs:** `topic_ai_scores_weekly`, `reports/backtest_ai.md` and `topic_ai_briefs_weekly`.
  v0.2's tables and report are untouched.
- **Ranked universe:** every `ai:` topic with at least 1 article in the week; no 20-article floor.
- **Eligibility gate:** holds by construction.
- **Syndication guard:** kept. At 09:00 there were no `ai:` rows in `topic_sources_weekly` (S13 not
  yet run on them), so it does not penalise any AI topic yet.
- **Window and fit:** the lexicon family replaces WS1's subtopic mapping. The `business` family is
  the fit share (hand-set, *estimate*).
- **`new_nbr_rate`:** from `edges_ai_weekly` with WS3's rule (4-week look-back, n >= 3, the "all"
  language bucket).
- **Pageview label:** `crosssource/lexicon_pageviews.py` (WS6 fetcher, 6.5 s per request) ->
  `wiki_pageviews_ai_daily`: 18,764 rows, 53 of 58 pages answered (*measured*).
  - Only 29 of 110 lexicon entries have an es or pt title, so the primary label ranks at most 29
    topics a week.
  - The table needs a contract: the existing one requires a QID.

**Scores:** 4,740 rows, 110 topics, 46 scored weeks (51 weeks of data minus the 5 warm-up weeks).

**Top 10:** all 20 entries are AI topics (10/10 each week; the gate needs >= 8/10).
- **W41:** Rondas y valuaciones de IA; IA multimodal; IA en medios, cine y creatividad; Fichajes y
  spin-offs en los laboratorios; Pesos abiertos y open source; Adopción de IA en empresas;
  Deepfakes y desinformación; Modelos del mundo; Nuevos laboratorios; IA en salud y medicina.
- **W42:** Alianzas y adquisiciones en IA; Google DeepMind; Bolsa y acciones de IA; Fichajes y
  spin-offs; Protestas y rechazo social a la IA; Sesgos y discriminación algorítmica; ByteDance
  (Doubao, Seed); Rondas y valuaciones de IA; Tencent Hunyuan; Artistas y creadores contra la IA.
- **Watch:** with no floor, four of the twenty rank on tiny counts. IA multimodal (4 articles that
  week), Modelos del mundo (3), ByteDance (9) and Sesgos (10) rank on noisy percentiles.
- **Floor of 20, tried and not adopted:** it replaces them with ChatGPT, Voz y música, Ajuste fino
  and Robótica. Primary precision is 27.7% against 28.1% without it. It is the orchestrator's call.

**Backtest** (*measured*, 43 evaluable weeks; brackets are 95% bootstrap intervals over weeks):

| Label | AI radar | Raw-count growth | Persistence | Base rate | v0.2 radar (same label) |
|---|---|---|---|---|---|
| Primary: es+pt pageviews, on labelled slots | 28.1% [24.5-31.7]; worst 24.8%, best 36.6%; coverage 88.2% | 25.9% [22.5-29.4] | 21.2% [17.7-24.9] | 26.8% | 29.2% [24.4-34.0] vs 25.4% |
| Secondary: es+pt GDELT growth | 25.6% [22.6-28.6] | 21.2% [17.7-24.4] | 14.2% [10.9-17.7] | 25.0% | 13.3% [9.5-17.2] vs 6.7% |

- **Primary:** below the 90% coverage rule, so the report gives bounds. The worst-case advantage
  holds over neither baseline (raw-count growth -10.9 points [-14.5, -7.5]; persistence +1.8 [-3.2,
  6.8]). The hook may not use it. On 29 mapped topics, a top 10 is a third of the field, so the test
  is weak.
- **Secondary:** it beats both baselines on paired intervals (+4.4 [0.2, 8.4] over raw-count growth,
  +11.4 [7.2, 15.6] over persistence; median lead 2 weeks). But it sits at the base rate (25.6% vs
  25.0%).
- **Against v0.2:** v0.2 was about 2x its base rate on this label, the AI run about 1.0x. The base
  rates differ (6.7% vs 25.0%) because 110 topics have far fewer weeks tied at zero growth than
  4,945 do.
- **Reading:** the AI radar ranks AI topics, but neither label shows it beating chance. It is not
  better evidence than v0.2.

**Briefs:** 20 for the W41-W42 top 10 under `RADAR_SOURCE=ai`. Auditor 20/20, 2 retried, 23,966
tokens, 86 s (*measured*), about $0.01 (*estimate*).
- **Known limit:** some briefs still frame a story the data does not support. Google DeepMind says
  "casi nadie lo cuenta en español" while citing 18 of 68 articles in es/pt; "Modelos del mundo"
  invents a story from 3 articles.

**Eval questions (v1):** none names an old W41/W42 top-10 org. q06-q11 name Nvidia, OpenAI,
Microsoft, Samsung, Google and TSMC, but expect GDELT ids (`org:nvidia`, `org:openai inc`…). Once
the agents resolve to `ai:` topics they need `radar-agents-v2`. Not changed.

## Primary backtest, reported with bounds (orchestrator decision, 03:40 UTC-5)

`models/backtest.py` now reports a label below the 90% coverage rule instead of withholding it:
precision@10 on the labelled slots of each ranker's own top 10, plus a worst case (its unlabelled
slots all misses) and a best case (all hits). The 90% rule's caveat stays in the report, and no
unbounded precision is printed. Slots of weeks with too few labelled topics (2026-W40) count as
unknown. Exact Wikidata matches, 440 slots per ranker (43 evaluable weeks + W40), all measured:

| Ranker | Coverage | Precision on labelled slots [95% interval] | Worst | Best |
|---|---|---|---|---|
| Radar, published (gate + guard) | 92.7% | 119/408 = 29.2% [24.4..34.0] | 27.0% | 34.3% |
| Radar, gate, no guard | 91.6% | 135/403 = 33.5% [29.2..38.0] | 30.7% | 39.1% |
| Radar, no gate | 91.6% | 134/403 = 33.3% [28.8..37.5] | 30.5% | 38.9% |
| Raw-count growth | 85.9% | 120/378 = 31.7% [26.8..37.0] | 27.3% | 41.4% |
| Persistence | 96.8% | 77/426 = 18.1% [14.8..21.3] | 17.5% | 20.7% |
| Base rate | | 1036/4085 = 25.4% | | |

- **Hook: may not use the primary result.** The published radar's worst case minus raw-count
  growth's best case is -14.3 points (95% interval -20.2..-8.6). Even on labelled slots alone the
  published radar (29.2%) is not above raw-count growth (31.7%); the intervals overlap.
- Every radar beats persistence under the worst case (published: +6.4 points, interval 0.7..12.0).
- On labelled slots the syndication guard lowers the radar's precision (29.2% with it, 33.5% without;
  the intervals overlap, measured).
- The alias-included run (separate section) gives the same reading: the published radar's worst
  case 25.7% vs raw-count growth's best case 51.8%.
- The secondary-label backtest (es+pt GDELT growth) is unchanged in the report.

## Primary backtest after WS6's last write (03:20 UTC-5, Claude #4 / claude-cacho, after the handover)

WS6 reports **Done** (03:14 write: 368,394 pageview rows; all 292 missing exact topics fetched, 512 of
512 articles HTTP 200). Final run on that data (`RADAR_PROFILE=full POLARS_MAX_THREADS=4 uv run
--extra models python -m models.backtest`, exit 0), label coverage of each ranker's top 10 over 440
top-10 slots (43 evaluable weeks plus 2026-W40, which has no labels; measured):

| Ranker | Exact matches (primary) | Alias included (separate row) |
|---|---|---|
| Radar, gate + syndication guard (published) | 408/440, 92.7% | 402/440, 91.4% |
| Radar, gate, no guard | 403/440, 91.6% | 400/440, 90.9% |
| Radar, no gate | 403/440, 91.6% | 356/440, 80.9% |
| Baseline: raw-count growth | **378/440, 85.9%** | 318/440, 72.3% |
| Baseline: persistence | 426/440, 96.8% | 427/440, 97.0% |

**Precision@10 on the primary label is not reported:** raw-count growth stays below the 90% rule
(`MIN_COVERAGE`), so its precision could still move by up to 14 points. Why the gap does not close
(measured, read-only check of the same top 10s): the 62 unlabelled raw-count slots (and the 14-37 of
the other rankers) belong to 83 topics that WS6 **did** fetch; their pageview series have fewer than
12 days of data in a 14-day window (new or rarely viewed es/pt articles), so the label is missing by
the protocol and never zero-filled. No further fetch can fill them. The list is in
`lake/labels/backtest_missing_topics.parquet` (topic, QID, articles, reason).

Decision for the orchestrator (not taken here): keep the 90% rule and present the secondary-label
backtest as the result, or accept 85.9% and print the precision with its 14-point bound. The
secondary-label results (es+pt GDELT growth) above are unchanged.

## Addendum 5: the syndication guard (01:36 UTC-5)

- Guard (hand-set from WS1's distributions over 17,154 ranked topic-weeks, estimate): a topic can
  headline only when it has >= 5 sources (p10 is 12), its largest source gives <= 0.5 of the
  articles (p90 is 0.34), and its most common co-mention pattern covers < 0.9 of the articles
  (24.7% of topic-weeks are at or above 0.9). A topic that fails goes to "semillas a vigilar",
  and its `why` names the condition.
- W42: 223 of 426 ranked topics may headline; 57 are held for low source diversity. The 6 WS9
  flags rank 224-241 (measured): `org:euronext` (97% one pattern), `org:adani enterprises`,
  `org:ministry of science`, `org:kioxia holdings`, `org:sterling`, and `org:yahoo` (one source
  gives 60%).

| Rank | Topic | Label | Stage | Decision | Window |
|---|---|---|---|---|---|
| 1 | `org:marsh mclennan` | Marsh & McLennan Companies | semilla | preparar | sin_estimacion |
| 2 | `org:rocket lab` | Rocket Lab | emergente | esperar | dias_restantes (12 d) |
| 3 | `org:national stock exchange` | national stock exchange | emergente | preparar | dias_restantes (5 d) |
| 4 | `org:university college london` | University College de Londres | emergente | preparar | dias_restantes (6 d) |
| 5 | `org:citigroup` | Citigroup | emergente | esperar | dias_restantes (6 d) |
| 6 | `org:sandisk` | SanDisk | emergente | esperar | dias_restantes (14 d) |
| 7 | `org:comcast` | Comcast | emergente | preparar | dias_restantes (8 d) |
| 8 | `org:kroger` | Kroger | emergente | preparar | sin_estimacion |
| 9 | `org:founders fund` | Founders Fund | emergente | esperar | dias_restantes (8 d) |
| 10 | `org:sb energy` | sb energy | emergente | esperar | sin_estimacion |

- W42 decisions: 0 publicar_ahora, 50 preparar, 166 esperar, 210 no_es_tema_caliente. All
  weeks: 40 / 1,936 / 6,319 / 8,609 (measured).
- **Backtest, secondary label** (es+pt GDELT growth, 43 weeks, measured; precision@10):

  | Ranker | Precision@10 | 95% interval |
  |---|---|---|
  | Published radar (gate + guard) | 13.3% | 9.5..17.2 |
  | Gate, no guard | 7.4% | 5.1..10.2 |
  | No gate | 7.2% | 4.9..9.5 |
  | Persistence | 12.8% | 9.1..17.0 |
  | Raw-count growth | 0.2% | 0.0..0.7 |
  | Base rate | 6.7% | |

  - The guard adds +5.8 points (paired interval 2.8..9.1).
  - The published radar beats raw-count growth (+13.0) and ties persistence (+0.5, −3.7..4.9).
  - Lead time: median 3.0 weeks (2.0..4.0) over 47 flagged positives.
  - Caveat in the report: the guard was designed after seeing W42; its thresholds come from
    WS1's distributions, not from the label.
- **Backtest, primary label** (Addendum 4b: exact Wikidata matches only; the alias-included run is
  a separate section). At the 01:50 write, coverage for the published radar is 142/440 (32.3%)
  exact and 139/440 (31.6%) with aliases, so precision is withheld for both (measured).
- **Needed topics, recomputed for exact matches (01:51):** 540 topics are needed, 124 already have
  pageviews, 416 do not. Of those 416, **292 are not on WS6's priority list** (measured), so WS6
  will never fetch them as things stand. Updated lists: `lake/labels/ws4_backtest_needed_topics.parquet`
  and `ws4_backtest_needed_missing.parquet` (the 292).
- Addendum 5b: done as written (the pattern share as a gate on headlining only, and the top
  source share for one-outlet weeks). The guard also needs >= 5 sources, a stricter extra
  condition 5b does not ask for. In W42 it alone holds 6 topics, all below the top-10 cutoff
  (best Priority 0.178 vs 0.291 at rank 10), so it does not change the top 10 (measured).
- Editor sheet regenerated from the guarded top 10: 10 + 10 items, no overlap.
- Memory (measured): build 1.15 GB, backtest 1.31 GB peak.

## Addendum 4 (01:21 UTC-5): secondary backtest done; primary waits on labels

- **Action needed (orchestrator / WS6):** the primary backtest needs 590 topics: each week's
  top 10 among *mapped* topics (those with an es/pt article), for both radars and raw-count growth.
  336 of them are not in WS6's `lake/labels/backtest_priority_topics.parquet`, which takes top 10s
  over all topics (measured). Without them, primary coverage cannot reach the 90% threshold.
  Lists in the lake: `lake/labels/ws4_backtest_needed_topics.parquet` (590) and
  `ws4_backtest_needed_missing.parquet` (336).
- **Secondary-label backtest** (`reports/backtest.md`, es+pt GDELT article growth; 43 weeks,
  4,945 ranked topics, measured):
  - The radar with the gate scores precision@10 7.4% (5.1..10.2) and without it 7.2%. The base
    rate is 6.7%. Persistence reaches 12.8% (8.8..17.0) and raw-count growth 0.2%.
  - **The radar does not beat both baselines.** It beats raw-count growth (+7.2 points,
    4.9..10.0) but loses to persistence (−5.3, −9.1..−1.9). The gate changes nothing (+0.2,
    −2.3..2.8). Lead time with the gate: median 2.5 weeks (2.0..5.0) over 28 flagged positives.
  - The report gives the diagnosis. Most topics have no es/pt article, so the base rate is 6.7%,
    not 25%. Past es/pt growth predicts future es/pt growth better than the emergence-led
    Priority. The label is not independent of the radar's es+pt inputs.
  - Bug found and fixed before reporting: ties in label growth were broken by row order, which
    favoured the radar's own rows (an inflated 87%). Positives are now decided by value only; a
    test shuffles the rows to check it.
- **Primary (pageviews), incremental:** `RADAR_PROFILE=full POLARS_MAX_THREADS=4 uv run python
  -m models.backtest`. It prints the label coverage per ranker first (labelled / needed
  topic-weeks) and refuses to report precision below 90%. Why 90%: at 90% coverage the missing
  slots can move pooled precision@10 by at most 10 points, the size of the differences compared.
  At 01:21: 0/440 (no pageviews in the lake yet). I rerun it at each WS6 write.
- **Memory:** the scores now build in topic chunks. Measured peaks: build 1.08 GB (was 2.4 GB),
  backtest 1.34 GB, with POLARS_MAX_THREADS=4.

Earlier: READY FOR REDEPLOY at 00:52 (Addendum 3, live as Cloud Run revision 00003).

## New W42 top 10 (measured; `rank` 1-10 of 430 ranked topics)

| Rank | Topic | Label | Stage | Decision | Window |
|---|---|---|---|---|---|
| 1 | `org:marsh mclennan` | Marsh & McLennan Companies | semilla | preparar | sin_estimacion |
| 2 | `org:euronext` | Euronext | emergente | preparar | dias_restantes (12 d) |
| 3 | `org:adani enterprises` | adani enterprises | emergente | esperar | dias_restantes (4 d) |
| 4 | `org:rocket lab` | Rocket Lab | emergente | esperar | dias_restantes (12 d) |
| 5 | `org:national stock exchange` | national stock exchange | emergente | preparar | dias_restantes (5 d) |
| 6 | `org:ministry of science` | ministerio de Ciencia | emergente | preparar | dias_restantes (9 d) |
| 7 | `org:kioxia holdings` | kioxia holdings | emergente | esperar | sin_estimacion |
| 8 | `org:sterling` | Sterling | emergente | esperar | dias_restantes (12 d) |
| 9 | `org:citigroup` | Citigroup | emergente | esperar | dias_restantes (6 d) |
| 10 | `org:yahoo` | yahoo | emergente | esperar | dias_restantes (10 d) |

- W42 decisions (430 ranked): 1 publicar_ahora (rank 15), 49 preparar, 166 esperar, 214
  no_es_tema_caliente. All weeks: 33 / 1,962 / 6,418 / 8,741 (measured).
- Gate: 261 of 430 W42 topics may headline; the other 169 are "semillas a vigilar", ranked
  after them with stage `semilla` and the reason in `why`. `org:scam centre`, `org:capital
  markets department`, `org:national anti`, `org:a group` and `org:technological development
  area` are out of the top 10 (measured). The deny list (PR #12) removes `big news network`.
- Alias dedupe: 4 W42 topics absorbed a same-QID variant (for example `org:taiwan
  semiconductor manufacturing company` into `... manufacturing co`). `org:taiwan semiconductor`
  and `... manufacturing` stay separate: WS6 has no QID for them yet.
- **Deviation from Addendum 3, for the orchestrator:** only Wikidata `exact` matches open the
  gate, not `alias`. All 316 alias matches have confidence 0.6, and several are wrong on the W42
  list: `org:national anti` resolves to an anti-doping agency, `org:us department` to Veterans
  Affairs. Aliases still drive the dedupe, but they no longer supply Spanish labels.
- Decision coherence: it was the table's design, not a grain bug (explained in
  `models/README.md`). `publicar_ahora` now needs a priority percentile >= 90, `preparar` >= 75,
  and a priority percentile < 50 is `no_es_tema_caliente`. Kioxia (rank 7) moved from
  `no_es_tema_caliente` to `esperar`. Every row's first `why` line names its decision rule.
- Editor sheet regenerated from the gated top 10: 10 radar + 10 raw-count-growth items, no
  overlap (`reports/editor_test.md`).
- Still weak (estimate weights, not retuned before the backtest): rank 1 Marsh & McLennan rises
  from near zero (share up more than 10x, no z history), and lowercase GKG names show where
  WS6 has no exact Wikidata label.

Owner: claude-cacho · Directories: `models/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 01:36 UTC-5 · branch `feat/ws4-scores` · draft PR #6 (into `develop`); local commits not pushed

## Done

- Unblocked by Addendum 2. Merged `origin/develop` (PR #8: `ranked_universe`,
  `topic_subtopic_weekly`).
- **Topic scores in the lake** (`RADAR_PROFILE=full uv run python -m models.build_scores`):
  - `lake/gold/topic_scores_weekly.parquet`: 17,285 rows over 46 weeks (2025-W49..2026-W42) and
    4,947 topics; every row is valid against the contract.
  - Ranked universe from the taxonomy: org topics minus `org_deny`, plus `thm:TECH_*`, with at
    least 20 ring-1 articles in the ISO week. Median 376 topics a week; 436 in 2026-W42.
  - Primary subtopic from `topic_subtopic_weekly` over weeks t-3..t, ties broken by taxonomy order.
    It is set for 415 of 436 topics in W42. A topic without one gets `primary_subtopic` = ""
    (empty), a `sin_estimacion` chip, and a fit from its own series only.
  - Window chip in W42: 216 of 436 topics have an estimate (138 `dias_restantes`, 68
    `en_cualquier_momento`, 10 `ya_en_espanol`).
  - The 12-subtopic table is kept, same contract, in `lake/gold/subtopic_scores_weekly.parquet`:
    552 rows, 46 weeks.
  - Run time 16 s, 2.4 GB peak.
- **Fix:** the rolling calendar now starts at the input's own first day. `daily_topic` and
  `topic_daily` start 2025-11-01, a year after `daily_totals`. The 21:28 subtopic build had
  counted that year as zero articles. It is replaced.
- **Editor sheet** for 2026-W42 in `reports/editor_test.md`: 9 radar items, 9 raw-count-growth
  items, 1 on both lists. The key is in `lake/editor_test/2026-W42_key.json`; tally with
  `--tally`.
- The backtest runs on topics through the same scoring step. Its report states the coverage
  (mapped / ranked) and that the evidence ids are empty. A smoke test at topic scale with the
  secondary label ran in 10 s; its numbers are not reported.
- Tests: `uv run pytest models -m "not data"`: 79 passed. Lake tests (`-m data`): the topic build
  validates, and the primary subtopic is recounted by hand for `org:nvidia`, 2026-W41.

## In progress

- **Backtest:** waiting for WS6's `wiki_pageviews_daily`. WS6 is fetching pageviews at 22:36 after
  an HTTP 429. Coverage so far: 278 of 4,947 ranked topics have an es or pt article. WS6 is still
  resolving the 8,385 `topic_daily` extras.

## Blocked on

- Nothing.

## For the orchestrator (findings, W42 top 10 and editor sheet)

- **Outlets and retailers still rank.** `org:big news network` (and the artefact
  `org:big new network`), plus `org:king soopers`, `org:ralphs` and `org:fred meyer` (a Kroger
  news cluster), are in the W42 lists. Adding them to `org_deny` is a taxonomy change (yours or
  WS2's).
- **New topics rank high.** A topic that appears from near zero gets a huge `growth_7d_log`:
  `org:marsh mclennan`, rank 1 in W42, shows +25,815% share and has no z history. The Emergence
  weights are hand-set placeholders (estimate). I will not retune them before the backtest
  measures them.
- `evidence_ids` stays empty (no contract tonight), and the backtest report says so.

## Numbers (each marked measured or estimate)

- `topic_scores_weekly`: 17,285 rows, 46 weeks, 4,947 topics, 0 contract violations (measured).
- Ranked topics a week: median 376; 436 in 2026-W42 (measured).
- W42: primary subtopic for 415/436 and a window estimate for 216/436 (measured).
- Wikipedia es/pt coverage so far: 278/4,947 ranked topics (measured, resolution in progress).
- Editor sheet W42: 19 items = 9 radar + 9 baseline + 1 overlap (measured).
- All score weights and thresholds are hand-set (estimate).
