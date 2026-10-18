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
