# Contracts

Owned by the orchestrator (WS0). Every workstream writes its outputs exactly as these files say.
Changing a contract is a breaking change: open a PR with `feat(contracts)!:` and a
`BREAKING CHANGE:` footer naming the consumers. Design: [docs/designs/radar-build-plan.md](../docs/designs/radar-build-plan.md).

## Data tables (`lake/gold/<name>.parquet`)

| Contract | Producer | One record is |
|---|---|---|
| `daily_totals` | WS1 Scout | one day of one language stream (the denominator) |
| `daily_topic` | WS1 Scout | day × subtopic × language × LatAm |
| `daily_topic_rolling` | WS1 Scout | the same, with 7-day signals and baselines |
| `topic_daily` | WS1 Scout | day × ranked topic (entity or theme in ring 1) × language |
| `topic_subtopic_weekly` | WS1 Scout | week × ranked topic × AI subtopic (the topic's primary subtopic for WS4) |
| `edges_weekly` | WS1 Scout | one weekly co-occurrence edge with NPMI |
| `topic_context_1hop` | WS3 Cartographer | one neighbour in a topic's 1-hop ring |
| `topic_scores_weekly` | WS4 Signal analyst | one ranked topic in one week, with its decision |
| `topic_wikidata` | WS6 Scout (cross-source) | a ranked topic resolved to Wikidata and its es/pt/en articles |
| `wiki_pageviews_daily` | WS6 Scout (cross-source) | one day of pageviews of one article (the backtest label's raw series) |
| `node_metrics_weekly` | WS3 Cartographer | one graph node in one week: degree growth, new neighbours, community |

## Agent protocol (`agents/` → API → web)

| Contract | One record is |
|---|---|
| `decision_card` | the Media Master's answer on one topic: decision, KPIs (each measured or estimate, each citing its tool call), justification |
| `view_command` | a structured command the web view applies (week, focus, highlight, colour, filter) |
| `agent_trace` | one step of a conversation, for the trace panel and the evaluation |

## Other contracts

| File | What it is |
|---|---|
| `taxonomy.yaml` | the three rings, the 12 AI subtopics and the ring-3 domains |
| `agents.yaml` | the agent registry: who owns what, which tools, the model |
| `api.yaml` | OpenAPI of the read API and `/api/chat` |

## Mocks

Every `<name>.schema.json` gets a mock at `mocks/<name>.json`: a non-empty list of records **copied
from real output**, never invented. Until that output exists, the schema says so with `x-mock`:
`pending-dev-slice` (data tables, filled from `fixtures/dev/`) or `pending-first-agent-run` (agent
protocol, filled from a recorded real conversation). `make test-ws` skips pending schemas and prints
why; it fails when a mock is missing for a schema that is not pending, or when a mock does not match.
