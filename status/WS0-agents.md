# WS0-agents status (answer quality, measured with LangSmith)

Owner: Claude #4 (claude-cacho) · Branch: `feat/ws0-agents-quality` · Directories: `agents/`

## Last update

2026-10-18 05:35 UTC-5 · trust route reads the cost ledger only for cost questions (fix/agents-trust-cost) · committed locally; the orchestrator lands it.

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
