# Contracts

Owned by the lead (WS0). Changing a contract is a breaking change: open a PR with
`feat(contracts)!:` and a `BREAKING CHANGE:` footer naming the consumers.

| File | Shape |
|---|---|
| `<name>.schema.json` | JSON Schema (draft 2020-12) of one record of table `<name>` |
| `api.yaml` | OpenAPI of `GET /api/radar`, `/api/topic/{id}/graph`, `/timeline`, `/sentiment`, `/api/freshness` |
| `taxonomy.yaml` | AI topic taxonomy |

Every `<name>.schema.json` needs a mock at `mocks/<name>.json` (a non-empty list of records);
`make test-ws` and the `contracts` pre-commit hook check that they agree. Planned contracts (plan §15):
`gkg_ai`, `daily_topic`, `daily_topic_rolling`, `node_metrics_weekly`, `topic_scores_weekly`.
