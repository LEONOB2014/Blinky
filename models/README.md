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

## Top 10 eligibility and decisions (Addendum 3)

- **Eligibility gate** (`build_scores.gate`): a topic can headline the weekly list when it is an
  established entity (articles in >= 6 of the prior 8 ISO weeks and >= 200 articles in them) or it
  resolves to Wikidata with match `exact`. Thresholds are hand-set (estimate). Every other ranked
  topic is a "semilla a vigilar": stage `semilla`, ranked after all eligible topics, with the
  reason in `why`. `alias` matches (confidence 0.6, several wrong on W42) do not open the gate,
  but topics sharing a QID are merged: the one with more articles stays and names the others.
- **Why decisions did not follow the rank.** It was the table's design, not a grain bug. Priority
  multiplies Emergence by saturation, fit and charge, while the old table decided on Emergence,
  stage and the window alone. So a topic could be `publicar_ahora` at rank 150 (high Emergence, a
  closing window, low fit). And Kioxia was rank 8 in W42 but `no_es_tema_caliente`: its Emergence
  was below 50, but its fit and charge lifted its Priority. The table now reads the week's
  Priority percentile: `publicar_ahora` needs >= 90, `preparar` >= 75, and Priority_pct < 50 is
  `no_es_tema_caliente`. A high-priority topic can still sit below the action rows when its stage
  is `en_declive`. The first `why` line of every row names its decision rule.

```bash
uv run pytest models                                   # dev slice
RADAR_PROFILE=full uv run python -m models.build_scores
RADAR_PROFILE=full uv run python -m models.backtest
RADAR_PROFILE=full uv run python -m models.editor_sheet
```

Plan: [design, Evaluation](../docs/designs/radar-build-plan.md), MASTER_PLAN §10, §12, §13.
Status: [status/WS4.md](../status/WS4.md).
