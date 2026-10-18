# Agents

The multi-agent runtime of the radar. Registry and roles: [`contracts/agents.yaml`](../contracts/agents.yaml);
protocol: `decision_card`, `view_command`, `agent_trace` in [`contracts/`](../contracts/).

```bash
make ask Q="¿Qué tema de IA está subiendo esta semana y desde qué ángulo contarlo?"
```

## How a turn works

1. **Route (code).** Keywords pick the specialists the question needs (`runtime.route`).
2. **Gather (code).** Each specialist runs its fixed data plan over the lake (`runtime.gather`): the
   Signal analyst reads the top 10 (or, until WS4's scores exist, the real subtopic trends and the leader
   computed by code); the Cartographer reads the 1-hop ring and emits a `view_command`; and so on.
3. **Interpret (LLM, in parallel).** Each specialist explains only the data it was given.
4. **Integrate (LLM).** The Media Master writes the recommendation, copying the decision code computed.
5. **Audit (code).** Every number in the answer must appear in a tool result; a decision code did not
   compute is replaced by "pendiente". Both are recorded as `veto` steps in the trace.

Questions the router does not recognise fall back to free tool calling by the Media Master.

## Why code plans and the LLM explains

Measured on the first real runs (Qwen3-30B-A3B-Instruct via Nebius, 2026-10-17): with free tool calling
the model skipped the Cartographer when asked for the graph, ignored real fallback data, queried a
column name as if it were an entity, and proposed a decision ("publicar ahora") that no code had
computed. With code-planned gathering the same question took 11.3 s, consulted the three specialists it
needed, emitted a valid view command and passed the Auditor. This follows MASTER_PLAN §4: "Jev decides,
the LLM explains, code ranks".

## Tracing and evals (LangSmith)

With `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` in `.env`, every turn is one LangSmith trace
in project `radar-agents`: `media_master_turn` → `route` → `gather:<agent>` (tools) → `<agent>` (one
Qwen call each) → the Media Master's integration → `auditor`. Each LLM call carries its model and
token usage; each turn carries tags (`agent:<name>`, `auditor:ok` / `auditor:veto`) and metadata
(profile, git sha, week, untraced numbers). Without the key nothing is sent; tests force it off.
Traces hold questions, answers and tool results: public GDELT aggregates, never titles, URLs or
person names.

The frozen question set is [`evals/questions.yaml`](evals/questions.yaml) (25 questions, v1; change
it only with a new version). Run it as an experiment and compare experiments in LangSmith:

```bash
RADAR_PROFILE=full uv run python -m agents.evals.run_evals --prefix <what-changed>
```

Evaluators: `grounding` (the Auditor found no number without a source), `decision_faithful`,
`routing`, `entity_resolved`, `latency_s`, `tokens` (code), and `usefulness` (Qwen3-235B as judge,
1-5 scaled to 0-1).

Measured on the full lake, 2026-10-17 (n = 25 questions, one repetition each):

| Experiment | grounding | decisions | routing | entities (n=6) | usefulness | latency | tokens/turn |
|---|---|---|---|---|---|---|---|
| baseline-qwen3-30b | 0.88 | 1.00 | 0.96 | 0.50 | 0.40 | not recorded | 5,881 |
| entity-routing-v2 | 0.76 | 1.00 | 0.92 | 1.00 | 0.38 (n=24) | 7.7 s | 5,939 |

The entity fix is real (3 → 6 of 6). The grounding drop is 3 questions of 25: two are run-to-run
variance (no entity involved), one is "¿Cuántos likes tendrá mi post en LinkedIn?" now resolving
LinkedIn and answering with unsourced numbers that the Auditor flagged. One repetition is too few to
separate small changes from noise: use `num_repetitions` before trusting a difference of a few
questions. Usefulness around 0.4 is the clearest thing to improve next.

### Answer quality for executives (2026-10-18, 3 repetitions)

`--repetitions 3` runs each of the 25 frozen questions three times; each cell is the mean over 75 runs
and, in brackets, the lowest and highest of the three repetition means (the noise band). All numbers
*(measured)* on the full lake; every experiment read the same `topic_scores_weekly` (written
2026-10-18 05:50 UTC, in each experiment's metadata with its git sha). Each experiment changes one thing
on top of the kept ones; per-question scores and the judge's reasons are in `lake/evals/<experiment>.json`.

| Experiment (sha) | Change | usefulness | grounding | decisions | routing | entities (n=18) | latency | tokens/turn | Kept |
|---|---|---|---|---|---|---|---|---|---|
| baseline-r3 (565d487) | `develop` as is | 0.443 [0.40-0.48] | 0.947 [0.92-0.96] | 1.00 | 0.960 | 1.00 | 6.1 s | 6,395 | - |
| format-plain-r3 (3b57fff) | decision line written by code in plain words, only for what was asked; 2-3 why bullets + one suggestion; no field names | 0.497 [0.45-0.57] | 1.000 | 1.00 | 0.960 | 1.00 | 5.1 s | 6,458 | yes |
| out-of-scope-r3 (01a93dd) | + code route for likes/reach predictions and people's opinions: short honest answer, no numbers, no LLM | **0.520 [0.50-0.53]** | 1.000 | 1.00 | 0.947 [0.92-0.96] (1 of 75 runs lost to a DNS error) | 1.00 | 4.3 s | 5,671 | yes |
| human-numbers-r3 (1d9edba) | + tools add `resumen_es` and human-formatted numbers ("+365%", "65%") | 0.510 [0.49-0.52] | 0.987 [0.96-1.00] | 1.00 | 0.960 | 1.00 | 7.4 s | 6,145 | no (reverted) |
| short-notes-r3 (d5816f5) | + specialists' notes in 1-2 plain sentences | 0.460 [0.43-0.48] | 1.000 | 1.00 | 0.960 | 1.00 | 5.5 s | 5,689 | no (reverted) |
| route-gaps-r3 (05c9ac0) | + tone questions routed to the audience strategist; the cartographer reads the #1 topic's ring when no entity is named | 0.520 [0.48-0.57] | 1.000 | 1.00 | **1.000** | 1.00 | 6.2 s | 5,814 | yes (final) |

Final against the baseline: usefulness 0.443 -> 0.520 (+0.08), grounding 0.947 -> 1.000, decision
faithfulness 1.00 -> 1.00, routing 0.960 -> 1.000, tokens 6,395 -> 5,814 per turn. The usefulness gain
clears the noise band at out-of-scope-r3 (lowest repetition 0.50 vs. the baseline's highest 0.48); with
the route-gaps change the bands touch (0.48), so that last step is kept for routing (q17 tone 0.00 ->
0.42, q14 0.42 -> 0.50), not for usefulness.

What the judge's reasons and the per-question scores say (measured, 3 runs per question):

- The biggest single win is the code-written, plain decision line: answers stopped opening with
  `org:marsh mclennan: preparar, org:euronext: preparar, ...` for every question (q06 Nvidia 0.17 ->
  0.67, q11 Taiwan Semiconductor 0.42 -> 1.00).
- The out-of-scope route takes q24 (likes) from 0.25 to 1.00, but the judge scores q25 ("¿Qué opina Sam
  Altman...?") 0.00 when the radar honestly says it does not track people's opinions ("evade con una
  explicación innecesaria"). The route stays: it is the honest answer the brief asks for, and the radar
  never serves person data.
- Still weak: q12, q15, q16 get the decision line because "tema" routes them to the signal analyst, and
  the judge calls it "una decisión no solicitada". Next experiment (not run, the budget of 6 was used):
  print the decision line only for "what to publish / what is rising" questions.
- The judge cannot see the tools' data, so it calls specific real numbers "no verificables" and 2026
  dates "fechas futuras improbables" (q21 freshness). Grounding is checked by code instead; a judge that
  receives the tool results and today's date would score these fairly, but changing the judge needs the
  baseline re-scored with it.

### Judge v2 and the decision line's scope (2026-10-18, addendum 01:25)

`usefulness_v2` (in `evals/run_evals.py`, v1 kept) gives the judge today's date and the trimmed tool
results the answer was built from, and asks it to score only usefulness to the executive given that
data; grounding stays a code check. `--rescore <experiment>` adds it to an existing experiment
(LangSmith `evaluate_existing`). Same notation as above: mean over 75 runs [lowest-highest repetition
mean], all *(measured)*, same scores file.

| Experiment (sha) | Change | usefulness v1 | usefulness_v2 | grounding | decisions | routing | latency | tokens/turn | Kept |
|---|---|---|---|---|---|---|---|---|---|
| baseline-r3 (565d487), re-scored | `develop` before this lane | 0.443 [0.40-0.48] | 0.383 [0.36-0.41] | 0.947 | 1.00 | 0.960 | 6.1 s | 6,395 | - |
| route-gaps-r3 (05c9ac0), re-scored | final of the first round | 0.520 [0.48-0.57] | 0.567 [0.50-0.60] | 1.000 | 1.00 | 1.000 | 6.2 s | 5,814 | yes |
| decision-scope-r3 (a9dcfa7) | decision line only for decision questions | 0.447 [0.41-0.49] | 0.540 [0.51-0.57] | 1.000 | 1.00 | 1.000 | 10.5 s | 5,783 | no (reverted) |
| entity-words-r3 (55fe2d9) | topic names matched as whole words; "principal", "linkedin" as stop words | 0.497 [0.47-0.53] (n=74, one judge 502) | 0.567 [0.55-0.59] | 1.000 | 0.987 [0.96-1.00] | 1.000 | 15.0 s (API slow, 502s) | 5,866 | yes (correctness) |
| decision-scope2-r3 (edff6ea) | decision line for decision questions and non-graph named topics | 0.483 [0.46-0.50] | 0.560 [0.53-0.60] | 1.000 | 1.00 | 1.000 | 6.0 s | 5,801 | no (reverted) |

**Final against the baseline, both judges:** usefulness v1 0.443 -> 0.497, usefulness_v2 0.383 ->
0.567 (lowest final repetition 0.55 vs. the baseline's highest 0.41: well beyond the spread), grounding
0.947 -> 1.000, routing 0.960 -> 1.000, tokens 6,395 -> 5,866. Decision faithfulness 1.00 -> 0.987:
one run of 75 (q22, "¿Cuánto puedo confiar en el radar?") said "No se recomienda publicar ahora" with
no card. That is not the entity change: the Auditor vetoes decision words only when no tool returned a
decision, and the top 10 (always read) has decisions even when the route shows no card. Closing it is
an Auditor rule change, out of this lane's scope.

What the two judges show (per question, 3 runs each):

- v2 fixes v1's blind spots: freshness (q21) 0.17 -> 0.83 once the judge knows today's date, and the
  honest out-of-scope answer to "¿Qué opina Sam Altman...?" (q25) 0.00 -> 1.00. v2 is stricter where an
  answer misuses the data it was given (q03 top 3 0.08, q05 "what is NOT hot" 0.00).
- **The entity resolver was wrong on 7 of 25 questions** on the full lake: a substring test found
  `org:a co` inside "ha costado" (q03, q14, q20), "el tema principal" became `org:principal group`
  (q15, q19), and "post de LinkedIn" made LinkedIn the topic (q18, q24). With whole-word matching all
  25 resolve as expected; v2 usefulness on those questions rose (q14 0.00 -> 0.58, q15 0.75 -> 1.00,
  q03 0.08 -> 0.17). The `entity_resolved` evaluator only checks expected entities, never false
  positives, which is why this was invisible; a false-positive check is a cheap next evaluator.
- Scoping the decision line did not help in either form: q15 and q16 rose, but q06 (Nvidia) fell
  without the line (0.83 -> 0.42), and with the line kept for named topics the net effect was within
  noise. The line stays as it was.
- Still weak under v2: q03 (top 3), q05 (what is not hot), q13 (communities), q17 (tone in Spanish:
  the data has no Spanish tone field for the leader, so the answer leans on other numbers).

### The Auditor gap (2026-10-18, addendum 2)

The Auditor now keeps a decision phrase ("publicar ahora", "no es tema caliente", "preparar ya") only
when the turn emits a decision card with that decision; otherwise it becomes "decisión pendiente" and
a `veto` step is logged. `entity_resolved` now scores all 25 questions: 1 only when the entity the
code route resolved (recorded on the Media Master's delegate step) equals the expected one, including
none, so false positives count (earlier rows scored only the 6 entity questions, n = 18).

| Experiment (sha) | Change | usefulness v1 | usefulness_v2 | grounding | decisions | routing | entities | latency | tokens/turn |
|---|---|---|---|---|---|---|---|---|---|
| entity-words-r3 (55fe2d9) | before | 0.497 [0.47-0.53] | 0.567 [0.55-0.59] | 1.000 | 0.987 [0.96-1.00] | 1.000 | 1.00 (n=18) | 15.0 s | 5,866 |
| auditor-cards-r3 (7d99229) | decisions only with a card; false-positive entity check | 0.500 [0.47-0.55] | 0.550 [0.50-0.59] | 1.000 | **1.000** | 1.000 | **1.00 (n=75)** | 12.6 s | 5,812 |

Decision faithfulness is back to 1.00 and no question resolves a topic it does not name (75 of 75);
usefulness moves within the repetition spread (all *measured*). Latency was high on both runs tonight
(Nebius returned 502s); token counts are flat, so it is the API, not the turn.
