# WS0-agents status (answer quality, measured with LangSmith)

Owner: Claude #4 (claude-cacho) · Branch: `feat/ws0-agents-quality` · Directories: `agents/`

## Last update

2026-10-18 01:45 UTC-5 · addendum 2 step 1 done · committed locally; the orchestrator pushes.

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
