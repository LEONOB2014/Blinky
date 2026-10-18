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
