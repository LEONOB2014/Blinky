# WS4: scores, window, decision, backtest

Signal analyst and Audience strategist. Code decides; no LLM in this lane.

| Module | What it does |
|---|---|
| `features.py` | The S8 rolling view ported to Python, at any grain (all languages, `eng`, es+pt); `tests/test_features.py` checks it against the real view |
| `scores.py` | Emergence, Stage and Saturation, Audience fit v1 (rules), Emotional charge, framing angle, Priority; every threshold in one table at the top |
| `window.py` | The window chip (onsets, pooled median lag, four states) |
| `decision.py` | `publicar_ahora` / `preparar` / `esperar` / `no_es_tema_caliente`, one documented table |
| `build_scores.py` | Writes `gold/topic_scores_weekly` (validated against the contract) on the full profile |
| `backtest.py` | The design's backtest; writes `reports/backtest.md` on the full profile only |
| `editor_sheet.py` | The blind editor-test sheet (`reports/editor_test.md`); the key stays in the lake |

```bash
uv run pytest models                                   # dev slice
RADAR_PROFILE=full uv run python -m models.build_scores
RADAR_PROFILE=full uv run python -m models.backtest
RADAR_PROFILE=full uv run python -m models.editor_sheet
```

Plan: [design, Evaluation](../docs/designs/radar-build-plan.md), MASTER_PLAN §10, §12, §13.
Status: [status/WS4.md](../status/WS4.md).
