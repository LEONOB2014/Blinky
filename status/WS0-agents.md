# WS0-agents status (answer quality, measured with LangSmith)

Owner: Claude #4 (claude-cacho) · Branch: `feat/ws0-agents-quality` · Directories: `agents/`

## Last update

2026-10-18 06:25 UTC-5 · graph facts written by code (fix/agents-graph-facts): graph questions 15/15 grounded · committed locally; the orchestrator lands it.

## Graph facts written by code (06:25 UTC-5, branch `fix/agents-graph-facts`, committed locally; the orchestrator lands it)

The last grounding gap: on the graph route the model invented thresholds ("más de 50 co-menciones",
"nPMI > 0.85"; q10 and q12 in predeploy-fixes).

- **Fix:** code now writes a "Cómo se arma el grafo" line from real values, as it writes the
  decision line.
  - **Weekly graph** (no topic named): the new `get_graph_facts` reads the metadata
    `graph/export_views.py` writes to `lake/views/temporal.json`. That gives the top-k per node (5),
    the minimum co-mentions (20) and the NPMI cut (> 0.1). It also counts the nodes and edges the
    view draws that week: 930 and 3,463 in W42 (*measured*). The node count is nodes with an edge
    that week, not `importance` rows (979), so it matches what is on screen.
  - **Named topic:** `get_context_1hop`'s own criteria: top 20, n >= 3, NPMI > 0.1, hubs and persons
    dropped, how many are shown.
  - The model is told the line is written and must not state other thresholds.
  - Nothing is hard-coded in the prompt. `get_graph_facts` is in the Cartographer's plan and in
    `contracts/agents.yaml`.
- **Auditor:** every number in both lines is traced. A test checks this, and that an invented
  "0.85" beside the line is still caught.
- **Tests:** 4 new. `make test` 264 passed, `make check` clean, contract tests pass.
- **Deploy gap closed** (06:30):
  - `deploy/cloudrun_stage.py` now also stages `lake/views/temporal.json`, and only that view file.
  - The image reads it at `$RADAR_LAKE/views/temporal.json` = `/app/lake/views/temporal.json`, the
    staged path. Checked by running `get_graph_facts` against a real staged context: 930 nodes and
    3463 edges for W42.
  - The stage refuses if the file is missing or has a `per:` node; the current file has none and no
    URLs.
  - Staged size, *measured*: temporal.json 3.6 MiB; the whole context 91.6 MiB.
  - 2 tests in `deploy/tests/test_cloudrun_stage.py`.
  - Not deployed; the orchestrator redeploys after landing.

**Results** against PR #47's full eval (predeploy-fixes, fea4dd2), all *measured*. Brackets are the
min-max of the three repetition means.

| Experiment | Questions | grounding | usefulness_v2 | tokens/turn |
|---|---|---|---|---|
| predeploy-fixes (fea4dd2), graph questions only | q07, q10, q12, q13, q14 x 3 | 0.867 (13/15) | 0.467 | - |
| graph-facts-graphq (d6fa0ff) | same x 3 | **1.000** [1.00-1.00] (15/15) | 0.633 [0.60-0.70] | 5,677 |
| predeploy-fixes (fea4dd2) | 25 x 3 | 0.947 [0.88-1.00] | 0.547 [0.51-0.58] | 6,148 [6,141-6,154] |
| graph-facts (d6fa0ff) | 25 x 3 | 0.933 [0.88-0.96] | 0.647 [0.61-0.67] | 6,205 [6,186-6,219] |

- **Graph questions:** 28 of 30 runs grounded across both experiments (was 13 of 15).
  - No answer states an NPMI value any more.
  - Left: one q10 run (of 6) still writes "todos con más de 50 co-menciones" about the listed
    neighbours, and one q13 run cites a "video de 35 segundos" (below).
- **Full-run grounding** is within the old range (5 of 75 missed vs 4 of 75). The other misses are
  not graph thresholds:
  - q21 x2: "actualizados a menos de 24 horas", an inference from the date.
  - q02 and q13: "video de 35 segundos", taken from the Editor's "30-45 s" role text, which is not
    tool data.
  - Both are prompt-sourced numbers. A fix would be to give the Editor's format lengths as data, or
    to drop the number from its role.
- **usefulness_v2** rose beyond the old range (0.547 -> 0.647). Only part of it is this change:
  - q12 rose 0.33 -> 0.83, the line opens its answer;
  - q21 rose 0.50 -> 0.83 from PR #47's date fix, which landed after predeploy-fixes was run;
  - q11 (0.25 -> 1.00) and q23 (0.25 -> 0.67) use routes this change does not touch, so read them as
    noise.
- **Tokens:** +57 per turn.
- **Nebius spend,** *estimate*:
  - agent tokens 550,557 (*measured*: 85,153 subset + 465,404 full, Qwen3-30B);
  - judge tokens not recorded, roughly 90 runs x 2 judges x ~4k on Qwen3-235B;
  - about $0.25 at assumed list rates, under the $0.40 cap.

## Pre-deploy defects D1-D3 fixed (06:10 UTC-5, branch `fix/agents-trust-cost`, committed locally; the orchestrator lands it)

From claude-work's pre-deploy check of `develop` e830a28 (`status/WS9.md`, PR #45):

- **D1, outlet count.**
  - New `get_topic_sources(topic_id, week)` over `topic_sources_weekly`: `n_articulos`, `n_medios`
    (distinct outlets) and the top source shares. It is in the Signal analyst's plan for named
    topics and in `contracts/agents.yaml`.
  - `get_topic_evidence`'s counts are renamed `articulos_mostrados` / `medios_entre_mostrados`, so
    the 5 articles shown are no longer a second `n_medios`.
- **D2, evidence written by code.** A question about artículos / evidencia / fuentes / medios of a
  named topic gets a block after the decision line: "N artículos de M medios esa semana", then
  outlet, date, language and title of each `get_topic_evidence` row. Never the URL.
- **D3, no stories.** The Media Master's prompt forbids causes, stories or intentions beyond the
  data, and says subtopics are categories, not the company's business. It shares the briefs'
  wording (`NO_NARRATIVE`, used by both).
- **Tests:** 5 new (tool, plan, block present and absent, prompt rule). `make test` 259 passed;
  `make check` clean.

**Eval:** predeploy-fixes, 25 x 3 at fea4dd2, all *measured*. Brackets are the min-max of the three
repetition means.

| Experiment | grounding | usefulness_v2 | usefulness v1 | decisions / routing / entities | tokens/turn |
|---|---|---|---|---|---|
| final-develop (7634781) | 0.973 [0.92-1.00] | 0.567 [0.51-0.60] | 0.457 [0.43-0.48] | 0.987 each (1 DNS-lost run) | 5,824 [5,531-5,980] |
| predeploy-fixes (fea4dd2) | 0.947 [0.88-1.00] | 0.547 [0.51-0.58] | 0.480 [0.45-0.52] | 1.000 each | 6,148 [6,141-6,154] |

- **Grounding** overlaps the baseline's range: 4 of 75 runs failed, against 2 of 75. None comes
  from D1-D3.
  - **q21 x2** ("¿qué tan frescos?"): "18 de octubre de 2026" is a correct date, but the Auditor's
    `_numbers` reads "2026-10-18" as only "2026", so the day is flagged. Before PR #42 it passed by
    matching 0.18 through the /100 rule. This is an Auditor false positive; the fix is to split ISO
    dates in `_numbers`.
  - **q10 and q12**: invented co-mention and nPMI thresholds ("más de 50", "0.85") on the graph
    route, which this change does not touch. The ring thresholds from PR #42 reduce this but do not
    stop it.
- **usefulness_v2** overlaps the baseline's range. q20 rose (0.67 -> 1.00, the cost fix of PR #42);
  q21 fell (1.00 -> 0.50, the two flagged runs).
- **Tokens** rose by 324 per turn (beyond the range): the sources tool's output and the longer
  Media Master prompt.

**Auditor date fix** (06:12, 17cf402):
- **Change:** `_numbers` no longer splits dates into loose numbers. A date in the answer (ISO, or
  "18 de octubre", year optional) is traced when the same day appears in the tool data; a
  different date is flagged, and numbers beside a date are still checked. A unit test covers
  "2026-10-18" next to an untraced 9999.
- **Result,** iso-dates-q21 (q21 x 3, *measured*):
  - grounding 3/3 = 1.000 [1.00-1.00], was 1/3 in predeploy-fixes;
  - usefulness_v2 0.583 [0.50-0.75], was 0.50;
  - every run says "18 de octubre de 2026" and passes.
- **Left as is:** q21 still volunteers the cost, because the Scout reads the ledger for freshness
  by design. One run calls Jev's $0.0443 "costo total de procesamiento".
- **Spend:** 5,620 agent tokens (*measured*); under $0.01 (*estimate*).

**claude-work's 4 questions, run by hand** (full lake, tracing off, read against the tool results):

| # | Question | Before (claude-work) | After |
|---|---|---|---|
| 1 | ¿Qué contenido preparo esta semana sobre Marsh McLennan? | pass | pass on data (Preparar, 92, carrusel from the brief); D3 not fully: "su enfoque en inversión y tecnología" still reads the subtopics as the business |
| 2 | ¿Qué artículos respaldan a Marsh McLennan, el tema número 1 de esta semana? | fail: no article named | **pass**: block with 44 articles / 39 outlets and 5 outlet-date-language-title rows. The model repeats the decision line once below it (seen before this change) |
| 3 | ¿Cuántos medios distintos cubren a Marsh McLennan esta semana? | fail: "44 medios" | **pass on the fact**: "39 medios distintos". D3 fails: "No es por IA, sino por su rol en inversiones estratégicas en infraestructura de chips" is invented |
| 4 | ¿En qué subtemas de IA cae Marsh McLennan esta semana? | pass | **partial**: "temas de financiamiento y tecnología de chips" (the right subtopics, loosely named). D3 fails: "cómo el sector asegurador está invirtiendo en tecnología de chips" is invented, and "crecimiento muy rápido en Latinoamérica" is wrong |

- Auditor 4/4 with no veto; tokens 31,065 for the 4 turns (*measured*).
- **D1 and D2 are fixed. D3 is not:** the prompt rule alone does not stop Qwen3-30B from writing a
  story in "Qué hacer".
- **Next for D3:** a code check like the briefs' overclaim list ("está redefiniendo", "invierte
  en", "su rol en", subtopic names next to the company), or a "Qué hacer" written from the brief's
  angle field.
- **Data note:** the five evidence articles for Marsh McLennan are generic Wall Street / AI-stock
  pieces. That is how WS1d's evidence selection matched the topic, not an agent fault.

**Nebius spend** for this follow-up, *estimate*:
- agent tokens 492,173 (*measured*: 461,108 eval + 31,065 by hand, Qwen3-30B);
- judge tokens not recorded, roughly 75 runs x 2 judges x ~4k on Qwen3-235B;
- about $0.21 at assumed list rates, about $0.27 with the 06:00 trust runs; under the $0.60 cap.

## Trust route reads the cost ledger only for cost questions (05:35 UTC-5, branch `fix/agents-trust-cost`, committed locally; the orchestrator lands it)

- `agents/runtime.py`: the Auditor's plan calls `get_cost_ledger` only when the question matches
  `_COST_Q`, the cost words of the Scout route, now a shared regex.
- Runtime test for both cases: a trust question reads only the backtest and the filter quality; a
  cost question also reads the ledger.
- `run_evals.py --questions q20,q22,q23` runs a subset of the frozen dataset.
- Before = `develop` e830a28 (includes the % fix of PR #42); after = e5eb9d5. Same questions, 3 runs
  each, all *measured*; brackets are the min-max of the three repetition means.

  | Experiment | grounding | usefulness v1 | usefulness_v2 | decisions / routing / entities | tokens/turn |
  |---|---|---|---|---|---|
  | trust-cost-before (n=9) | 0.778 [0.67-1.00] | 0.306 [0.17-0.50] | 0.528 [0.50-0.58] | 1.00 / 1.00 / 1.00 | 4,414 |
  | trust-cost-after (n=9) | **1.000** [1.00-1.00] | 0.250 [0.08-0.50] | 0.528 [0.50-0.58] | 1.00 / 1.00 / 1.00 | 4,294 |

- Per question (grounding, before -> after):
  - q22 (trust): 1/3 -> 3/3. Before, two runs invented a total cost ("$2.21"), and the Auditor now
    catches it after PR #42. After, no q22 run cites the BigQuery or Jev cost.
  - q20 (cost): 3/3 -> 3/3. It still gets the ledger and cites the real figures.
  - q23 (filter): 3/3 -> 3/3.
- **Usefulness:** v2 is unchanged and v1 moves within its range; n = 9 is too small to read more
  into it.
- **Left as is:** "$1.47", the labelling round's cost from `reports/label_quality.md`, still appears
  in q22 and q23 answers. The number is real and grounded, but one q22 run calls it "el costo del
  backtest". That is a wrong label on a real number, not an invented one.
- **Nebius spend** for both runs, *estimate*:
  - agent tokens 78,373 (*measured*, Qwen3-30B);
  - judge tokens not recorded, roughly 18 runs x 2 judges x ~4k on Qwen3-235B;
  - about $0.06 at Nebius list prices, under the $0.30 cap.

## Grounding gaps closed (05:05 UTC-5, branch `fix/ws0-grounding-gaps`, committed locally; the orchestrator pushes)

- `get_cost_ledger` now returns:
  - BigQuery bytes billed (*measured*) and the month's share of the 1 TiB free tier;
  - the USD it implies at USD 6.25/TiB, with and without the free tier (*estimate*, source stated);
  - Jev's USD total (*measured*): $0.0443 over 981 calls.
- The old share divided by 1 TB instead of 1 TiB: 0.38 -> 0.346.
- `get_context_1hop` now states the ring's thresholds: n >= 3, NPMI > 0.1, hubs and persons dropped,
  top 20. A test checks them against `graph/`.
- grounding-gaps (3 x 25, *measured*) vs final-develop:
  - grounding 1.000 [1.00-1.00] vs 0.973 [0.92-1.00]; the ranges touch at 1.00;
  - usefulness_v2 0.593 [0.54-0.63] vs 0.567; v1 0.460 vs 0.457;
  - decisions, routing and entities 1.000 (no lost runs);
  - tokens 6,035 vs 5,824 (beyond the spread: larger tool outputs).
- q20 cites the real cost in 3 of 3 runs. q12 no longer invents a threshold, but no graph answer
  cites one either.
- **Open:** two q22 runs say "$2.20 por semana", an invented weekly cost the Auditor missed.
  - Cause: `untraced_numbers` divides every number by 100, not only percentages.
  - Proposed fix: divide only "%" tokens, and keep the cost ledger out of the trust route.
  - Not done here: outside this brief.

## Final regression check (04:55 UTC-5, branch `chore/final-eval`, committed locally; the orchestrator pushes)

- `final-develop` on `develop` 7634781 (briefs, evidence tools and graph lenses merged).
  25 questions x 3 repetitions, concurrency 4, all *measured*.
- Results against auditor-cards-r3 (spread in brackets):

  | Metric | auditor-cards-r3 | final-develop |
  |---|---|---|
  | usefulness v1 | 0.500 [0.47-0.55] | 0.457 [0.43-0.48] |
  | usefulness_v2 | 0.550 | 0.567 [0.51-0.60] |
  | grounding | 1.000 | 0.973 [0.92-1.00] |
  | decisions, routing, entities | 1.000 | 0.987 each |
  | latency | 12.6 s | 7.8 s |
  | tokens per turn | 5,812 | 5,824 |

- **Decisions, routing and entities:** each lost the same single run, a q11 run that hit a DNS error
  before any agent ran. Over the 74 completed runs, all three are 1.00.
- **Grounding** is the only metric outside the old spread: 2 of 75 runs.
  - The model made up an "nPMI > 0.85" threshold (q12) and a "$114.23" cost (q20).
  - The Auditor caught and labelled both.
  - Neither tool path changed in the diff, so this is sampling, not a regression from the merge.
- **Usefulness v1:** dips, but the spreads overlap.
- Verdict: no regression attributable to the merged changes. Detail in `agents/README.md`.

## Done

- `run_evals.py --repetitions N --change "..."`: LangSmith `num_repetitions`, git sha and the scores
  file's timestamp in the metadata, per-question scores and judge reasons in `lake/evals/`.
- 6 experiments of 25 questions x 3 repetitions (the brief's maximum), one change each, table and
  diagnosis in `agents/README.md`. Kept: plain decision line written by code, out-of-scope route,
  routing gaps closed. Reverted (no win, measured): human-formatted tool fields, shorter notes.
- Final vs. 3-repetition baseline (measured, n = 75 runs each): usefulness 0.443 [0.40-0.48] -> 0.520
  [0.48-0.57]; grounding 0.947 -> 1.000; decision faithfulness 1.00 -> 1.00; routing 0.960 -> 1.000;
  tokens per turn 6,395 -> 5,814.

## Addendum 01:25 (done)

- Judge v2 (`usefulness_v2`, tool data + today's date; v1 kept) and `--rescore`. Baseline and the first
  round's final re-scored with it (measured, n = 75 each): baseline 0.383 [0.36-0.41], route-gaps
  0.567 [0.50-0.60].
- 3 experiments (the addendum's maximum): decision line scoped to decision questions (no win,
  reverted), whole-word entity matching (kept: 7 of 25 questions were answered about a topic nobody
  named; v2 0.567 [0.55-0.59]), decision line for decision questions and named topics (no win,
  reverted).
- Final vs. baseline: usefulness_v2 0.383 -> 0.567 and v1 0.443 -> 0.497; grounding 0.947 -> 1.000;
  routing 0.960 -> 1.000; decision faithfulness 1.00 -> 0.987 (one q22 run; Auditor gap below).

## Addendum 2, step 1 (done)

- The Auditor keeps a decision phrase only when the turn emits a card with that decision;
  `entity_resolved` counts false positives over all 25 questions.
- auditor-cards-r3 (measured, n = 75): decision faithfulness 1.000 (was 0.987), entities 1.00 over 75
  runs, grounding 1.000, routing 1.000, usefulness_v2 0.550 [0.50-0.59] (was 0.567 [0.55-0.59]:
  within the spread), v1 0.500.

## Spanish briefs per top-10 topic (claude-work, 03:32 UTC-5, branch `feat/ws0-spanish-briefs`)

- `agents/briefs.py` (`RADAR_PROFILE=full uv run python -m agents.briefs --weeks 2`):
  - Code gathers each topic's data with the agents' tools: scores, the window, calendar-week series
    in English vs es/pt, the 1-hop ring with theme codes turned into words, and articles/outlets from
    WS1c's `topic_sources_weekly`.
  - The Editor (`Qwen/Qwen3-30B-A3B-Instruct-2507`, Nebius) writes the six fields as JSON.
  - The deterministic Auditor checks the text:
    - `untraced_numbers` uses `runtime.untraced_numbers` over the data passed;
    - a decision word other than the code's decision is a contradiction;
    - style: internal ids, "viral", over-length fields, and overclaims ("todos los medios",
      "impactará", "llegará pronto", "está conectado").
  - One retry with the Auditor's complaint; the second result is kept even if it fails (flagged).
  - `numbers_cited` lists every passed number that appears in the text, with its kind and source.
- `lake/gold/topic_briefs_weekly.parquet`: **20 briefs** (top 10 of 2026-W41 and 2026-W42),
  validated against the contract.
- **Final run, measured:** `auditor_ok` 20/20, 3 retried (all for overclaims), 27,076 tokens, 98 s
  (4-8 s per brief).
- **First run:** 20/20 `auditor_ok` with 0 retries, 20,411 tokens, 172 s. Reading the texts showed
  claims the number check cannot see:
  - a hook said a topic "podría estar en todos los medios en español" in 12 days, turning the
    window's estimate into a prediction;
  - a brief said a company "está conectada con inversiones en chips", reading the radar's subtopic
    categories as the company's business.
  - Fix: the prompt now says the window is an estimate and subtopics are categories, and forbids
    reach and impact predictions; the overclaim check above triggers a retry.
  - Total Nebius calls for the lane: 43 (20 + 23), slightly above the brief's "about 20-40".
- **Still imperfect (read, not measured):** some briefs keep mild speculation ("podría aparecer
  pronto en los medios locales"). The audience fit (an estimate) is quoted as a plain percentage,
  although `numbers_cited` marks it `estimate`.
- Tool `get_topic_brief(topic_id, week)` in `agents/tools.py`. The Editor specialist calls it first
  whenever the briefs file exists, so "¿qué contenido preparo?" answers from the brief.
- `mocks/topic_briefs_weekly.json`: the 2026-W42 #1-#3 briefs. The contract's `x-mock` is now
  `first-agent-run`; `make test-ws` passes.
- Tests (offline, scripted model): fenced and bad JSON, the Auditor catching an invented "380%",
  a wrong decision, ids/viral and overclaims, retry-then-pass, fail-twice-kept-and-flagged, contract
  validation, humanized theme codes.
- Addendum 03:35, done: `get_topic_evidence(topic_id, week)` in `agents/tools.py` reads WS1d's
  `topic_evidence_weekly`.
  - It returns up to 5 articles (outlet, date, language, title) and their article and outlet
    counts; the URL never reaches the model.
  - The Signal analyst and the Editor call it when a named topic is asked about.
  - Two offline tests: the tool never returns a URL and caps at 5; a named-topic turn reads it and
    no URL is in any message sent to the model.
  - Checked on the full lake: `org:marsh mclennan`, 2026-W42, 5 articles from 5 outlets, all
    English (measured).
  - The briefs keep citing the week's real article and outlet counts from `topic_sources_weekly`
    (for example 44 artículos de 39 medios). The evidence's 5 of 5 is a selection, not the
    volume. They never cite titles.
- Regenerate at 06:00 if the final scores change (`--weeks 2`, about 20-25 calls).

**Two examples** (as written; no titles, URLs or person names):

**2026-W42 #1 Marsh & McLennan Companies** (decisión del código: preparar; auditor_ok true)

> **Titular:** Marsh & McLennan Companies: un tema que crece muy rápido
> **Qué pasó:** Esta semana, 44 artículos en inglés hablaron de Marsh & McLennan Companies, sin ningún contenido en español ni portugués. El tema está en etapa de semilla, con una emergencia del 92 por ciento y cero saturación. Aún no hay noticias en español, pero su crecimiento es notable.
> **Por qué importa en LatAm:** Aunque no hay datos específicos de LatAm, el tema tiene un encaje del 65 por ciento con intereses regionales, especialmente en inversiones y tecnología. Su relevancia creciente en mercados globales puede afectar decisiones de negocio en la región.
> **Ángulo:** Explicar de forma neutral el surgimiento de Marsh & McLennan Companies como un tema de crecimiento acelerado, sin conexión directa con los subtemas, y destacar que aún no hay cobertura en español.
> **Gancho:** Marsh & McLennan Companies está apareciendo en medios internacionales con fuerza, pero aún no se habla de ello en español. ¿Qué está pasando y por qué importa?
> **Formato:** carrusel, porque permite mostrar el crecimiento semanal, la ausencia de contenido en español y el contexto global de forma clara y visual

Números citados: emergencia_percentil=92 (measured), encaje_latam_pct=65 (estimate), articulos_semana=44 (measured), articulos_ingles_semana_4=44 (measured).

**2026-W41 #1 PepsiCo** (decisión del código: preparar; auditor_ok true)

> **Titular:** PepsiCo: crece rápido en inglés, aún no en español
> **Qué pasó:** Esta semana, el número de artículos sobre PepsiCo en inglés llegó a 159, un aumento significativo respecto a semanas anteriores. En cambio, no se publicaron artículos en español ni portugués esta semana.
> **Por qué importa en LatAm:** El tema está ganando atención en mercados globales, lo que podría tener relevancia para decisiones empresariales y de inversión en América Latina en los próximos días.
> **Ángulo:** PepsiCo está en una fase emergente con crecimiento acelerado en inglés, pero aún no se ha traducido a contenido en español.
> **Gancho:** PepsiCo está en aumento en inglés. En español, aún no hay nada. Según la estimación del radar, faltan unos 8 días para que llegue.
> **Formato:** carrusel, porque permite mostrar el crecimiento en inglés, la ausencia en español y el tiempo estimado de llegada sin exagerar

Números citados: dias_restantes_ventana=8 (estimate), articulos_ingles_semana_4=159 (measured).

## Blocked on

- None.

## Notes for the orchestrator


- One of 75 runs in out-of-scope-r3 failed on a DNS error (empty answer, counted as is).
