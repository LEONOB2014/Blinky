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
