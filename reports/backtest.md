# Backtest: the radar's weekly top 10

Generated 2026-10-18 01:21 UTC-5 by `models/backtest.py` on the `full` profile. Every number below is **measured** on the lake unless marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module docstring. The score weights and thresholds are hand-set (estimate), not fitted to either label. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table maps gkg_id to topics yet); the backtest does not use them.

The primary label (es+pt Wikipedia pageviews) is not reportable yet (coverage). The secondary label (es+pt GDELT article growth) is the fallback card when pageviews are missing.

## Primary label: es+pt Wikipedia pageview growth

- Ranked topics: 4945; with an es or pt Wikipedia article (the backtest ranks those only): 1094 (22.1%, measured). Unmapped topic-weeks: 9649 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate (published) | 0/440 | 0.0% (measured) |
| Radar, without the gate (Priority alone) | 0/440 | 0.0% (measured) |
| Baseline: raw-count growth | 0/440 | 0.0% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 0/0 | n/a (measured) |

**Not reported:** coverage is below 90.0% for at least one ranker, so precision@10 could move by more than 10.0% once the missing labels arrive. Rerun `RADAR_PROFILE=full uv run python -m models.backtest` after the next WS6 write.

## Secondary label: es+pt GDELT article growth

- Ranked topics: 4945, all labelled by their own es+pt GDELT series (no Wikipedia needed). This label is not independent of the radar: saturation and fit read the same es+pt stream (the label is the next 2 weeks; the features read only the past).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate (published) | 430/430 | 100.0% (measured) |
| Radar, without the gate (Priority alone) | 430/430 | 100.0% (measured) |
| Baseline: raw-count growth | 430/430 | 100.0% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 430/430 | 100.0% (measured) |
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: label window not complete.
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.
- Base rate 6.7%, not 25%: many topics have the same label growth (for the GDELT label, most have no es/pt article in either window, growth 0). A tie at the quartile cutoff is left out rather than split by row order, so a positive is real growth (measured).
- Mapped topics with a label per evaluable week: 210..559 (measured).

### Precision@10

| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |
|---|---|---|---|
| Radar, with the eligibility gate (published) | 32/430 | 7.4% (measured) | 5.1% .. 10.2% |
| Radar, without the gate (Priority alone) | 31/430 | 7.2% (measured) | 4.9% .. 10.0% |
| Baseline: raw-count growth | 1/430 | 0.2% (measured) | 0.0% .. 0.7% |
| Baseline: persistence (the label's own last 2 weeks) | 55/430 | 12.8% (measured) | 8.8% .. 17.0% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | 1076/15959 | 6.7% (measured) | n/a |

Differences in precision points (paired bootstrap over weeks):

- Radar, with the eligibility gate (published) minus Baseline: raw-count growth: 7.2%, 95% interval 4.9% .. 10.0% (measured).
- Radar, with the eligibility gate (published) minus Baseline: persistence (the label's own last 2 weeks): -5.3%, 95% interval -9.1% .. -1.9% (measured).
- Radar, without the gate (Priority alone) minus Baseline: raw-count growth: 7.0%, 95% interval 4.4% .. 9.5% (measured).
- Radar, without the gate (Priority alone) minus Baseline: persistence (the label's own last 2 weeks): -5.6%, 95% interval -9.1% .. -2.3% (measured).
- Radar, with the eligibility gate (published) minus Radar, without the gate (Priority alone): 0.2%, 95% interval -2.3% .. 2.8% (measured).

### Lead time

- Radar, with the eligibility gate (published): median 2.5 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 5.0, over 28 flagged positives (measured).
- Radar, without the gate (Priority alone): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 6.0, over 29 flagged positives (measured).

### Verdict

- Radar, with the eligibility gate (published): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, without the gate (Priority alone): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).

Diagnosis:

- Radar hits per week range 0..3 of 10; weeks at or below the base rate: 21 of 43 (measured).
- Overlap between the radar's and persistence's top 10: median 0 units a week (measured).
- The radar's precision (7.4%) is close to the base rate (6.7%); persistence reaches 12.8%: on this label, past es/pt growth predicts future es/pt growth better than the radar's emergence-led Priority (measured).
- The weights and thresholds of the scores are hand-set placeholders (estimate), not fitted to this label.

### Per week

| Week | Labelled | Positives | Radar (gated) | Radar | Raw-count growth | Persistence |
|---|---|---|---|---|---|---|
| 2025-W49 | 343 | 29 | 3/10 | 3/10 | 0/10 | 3/10 |
| 2025-W50 | 380 | 12 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2025-W51 | 275 | 8 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2025-W52 | 221 | 23 | 2/10 | 1/10 | 0/10 | 3/10 |
| 2026-W01 | 210 | 29 | 2/10 | 2/10 | 0/10 | 5/10 |
| 2026-W02 | 384 | 27 | 1/10 | 2/10 | 0/10 | 1/10 |
| 2026-W03 | 385 | 21 | 1/10 | 1/10 | 0/10 | 0/10 |
| 2026-W04 | 352 | 25 | 2/10 | 1/10 | 0/10 | 0/10 |
| 2026-W05 | 334 | 22 | 0/10 | 1/10 | 0/10 | 0/10 |
| 2026-W06 | 343 | 22 | 0/10 | 0/10 | 0/10 | 2/10 |
| 2026-W07 | 335 | 28 | 2/10 | 2/10 | 0/10 | 3/10 |
| 2026-W08 | 386 | 23 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W09 | 452 | 31 | 0/10 | 2/10 | 0/10 | 4/10 |
| 2026-W10 | 378 | 22 | 0/10 | 1/10 | 0/10 | 0/10 |
| 2026-W11 | 315 | 17 | 1/10 | 1/10 | 0/10 | 0/10 |
| 2026-W12 | 348 | 22 | 1/10 | 0/10 | 0/10 | 1/10 |
| 2026-W13 | 322 | 16 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W14 | 264 | 21 | 1/10 | 0/10 | 0/10 | 1/10 |
| 2026-W15 | 259 | 28 | 1/10 | 1/10 | 0/10 | 2/10 |
| 2026-W16 | 339 | 29 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W17 | 371 | 30 | 1/10 | 1/10 | 0/10 | 3/10 |
| 2026-W18 | 376 | 25 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W19 | 315 | 28 | 2/10 | 1/10 | 0/10 | 1/10 |
| 2026-W20 | 460 | 34 | 1/10 | 2/10 | 0/10 | 4/10 |
| 2026-W21 | 482 | 32 | 3/10 | 1/10 | 0/10 | 4/10 |
| 2026-W22 | 417 | 35 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W23 | 443 | 28 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W24 | 428 | 20 | 0/10 | 2/10 | 0/10 | 0/10 |
| 2026-W25 | 300 | 18 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W26 | 453 | 25 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W27 | 328 | 23 | 0/10 | 0/10 | 0/10 | 2/10 |
| 2026-W28 | 388 | 20 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W29 | 433 | 30 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W30 | 365 | 27 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W31 | 410 | 25 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W32 | 345 | 21 | 1/10 | 1/10 | 0/10 | 1/10 |
| 2026-W33 | 344 | 24 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W34 | 373 | 18 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W35 | 421 | 25 | 1/10 | 0/10 | 1/10 | 2/10 |
| 2026-W36 | 381 | 34 | 1/10 | 2/10 | 0/10 | 3/10 |
| 2026-W37 | 414 | 40 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W38 | 528 | 35 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W39 | 559 | 24 | 0/10 | 0/10 | 0/10 | 1/10 |
