# Backtest: the radar's weekly top 10 (AI lexicon topics)

Generated 2026-10-18 09:00 UTC-5 by `models/backtest.py` on the `full` profile. Every number below is **measured** on the lake unless marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module docstring. The score weights and thresholds are hand-set (estimate), not fitted to either label. The syndication guard (Addendum 5) was added after WS9 saw syndicated topics in the 2026-W42 top 10; its thresholds come from WS1's source distributions, not from either label, but its design is not blind to the data. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table maps gkg_id to topics yet); the backtest does not use them.

The primary label (es+pt Wikipedia pageviews) is reported below with bounds (coverage under 90.0%). The secondary label (es+pt GDELT article growth) is the fallback card when pageviews are missing.

## Primary label: es+pt Wikipedia pageview growth (the AI lexicon's page titles)

- Ranked topics: 110; with an es or pt Wikipedia article (the backtest ranks those only): 29 (26.4%, measured). Unmapped topic-weeks: 3446 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 388/440 | 88.2% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 388/440 | 88.2% (measured) |
| Radar, without the gate (Priority alone) | 388/440 | 88.2% (measured) |
| Baseline: raw-count growth | 382/440 | 86.8% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 430/440 | 97.7% (measured) |

**Below the 90.0% coverage rule:** at least one ranker has fewer than 90.0% of its top-10 labels, so an unbounded precision@10 is not reported. Below, each ranker's precision is computed on the labelled slots of its own top 10, with bounds that count its unlabelled slots as all misses (worst case) and all hits (best case). The bounds are hard limits; the labelled precision assumes the unlabelled slots behave like the labelled ones, which nothing guarantees (the missing labels are pageview series with fewer than 12 days of data in a 14-day window, mostly new or rarely viewed articles).
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: 0 mapped units with a label (needs 11).
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.

### Precision@10 on labelled slots, with bounds

| Ranker | Coverage (labelled / slots) | Precision@10 on labelled slots | 95% bootstrap interval over weeks | Worst case (unlabelled = misses) | Best case (unlabelled = hits) |
|---|---|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 388/440 = 88.2% | 109/388 = 28.1% | 24.5% .. 31.7% | 24.8% | 36.6% |
| Radar, with the eligibility gate, without the syndication guard | 388/440 = 88.2% | 109/388 = 28.1% | 24.6% .. 31.6% | 24.8% | 36.6% |
| Radar, without the gate (Priority alone) | 388/440 = 88.2% | 109/388 = 28.1% | 24.5% .. 31.7% | 24.8% | 36.6% |
| Baseline: raw-count growth | 382/440 = 86.8% | 99/382 = 25.9% | 22.5% .. 29.4% | 22.5% | 35.7% |
| Baseline: persistence (the label's own last 2 weeks) | 430/440 = 97.7% | 91/430 = 21.2% | 17.7% .. 24.9% | 20.7% | 23.0% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 295/1102 = 26.8% | n/a | n/a | n/a |

All figures measured. Worst-case comparisons (each radar's worst case minus each baseline's best case, paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -10.9%, 95% interval -14.5% .. -7.5%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.8%, 95% interval -3.2% .. 6.8%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: raw-count growth (best): -10.9%, 95% interval -14.3% .. -7.3%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.8%, 95% interval -3.2% .. 6.8%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: raw-count growth (best): -10.9%, 95% interval -14.5% .. -7.5%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.8%, 95% interval -3.2% .. 6.8%: the advantage **does not hold** under the worst case.

Hook (primary label): **may not use** this result: the published radar's advantage over raw-count growth does not hold under the worst case (measured). The page uses the secondary label or the fallback hook.

## Secondary label: es+pt GDELT article growth

- Ranked topics: 110, all labelled by their own es+pt GDELT series (no Wikipedia needed). This label is not independent of the radar: saturation and fit read the same es+pt stream (the label is the next 2 weeks; the features read only the past).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 430/430 | 100.0% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 430/430 | 100.0% (measured) |
| Radar, without the gate (Priority alone) | 430/430 | 100.0% (measured) |
| Baseline: raw-count growth | 430/430 | 100.0% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 430/430 | 100.0% (measured) |
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: label window not complete.
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.
- Mapped topics with a label per evaluable week: 99..106 (measured).

### Precision@10

| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |
|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 110/430 | 25.6% (measured) | 22.6% .. 28.6% |
| Radar, with the eligibility gate, without the syndication guard | 110/430 | 25.6% (measured) | 22.3% .. 28.6% |
| Radar, without the gate (Priority alone) | 110/430 | 25.6% (measured) | 22.3% .. 28.6% |
| Baseline: raw-count growth | 91/430 | 21.2% (measured) | 17.7% .. 24.4% |
| Baseline: persistence (the label's own last 2 weeks) | 61/430 | 14.2% (measured) | 10.9% .. 17.7% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | 1109/4428 | 25.0% (measured) | n/a |

Differences in precision points (paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: raw-count growth: 4.4%, 95% interval 0.2% .. 8.4% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: persistence (the label's own last 2 weeks): 11.4%, 95% interval 7.2% .. 15.6% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: raw-count growth: 4.4%, 95% interval 0.5% .. 8.6% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: persistence (the label's own last 2 weeks): 11.4%, 95% interval 7.2% .. 15.6% (measured).
- Radar, without the gate (Priority alone) minus Baseline: raw-count growth: 4.4%, 95% interval 0.2% .. 8.4% (measured).
- Radar, without the gate (Priority alone) minus Baseline: persistence (the label's own last 2 weeks): 11.4%, 95% interval 7.2% .. 15.6% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, without the gate (Priority alone): 0.0%, 95% interval 0.0% .. 0.0% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, with the eligibility gate, without the syndication guard: 0.0%, 95% interval 0.0% .. 0.0% (measured).

### Lead time

- Radar, with the eligibility gate and the syndication guard (published): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 86 flagged positives (measured).
- Radar, with the eligibility gate, without the syndication guard: median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 86 flagged positives (measured).
- Radar, without the gate (Priority alone): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 86 flagged positives (measured).

### Verdict

- Radar, with the eligibility gate and the syndication guard (published): beats both baselines (both paired intervals above zero, measured).
- Radar, with the eligibility gate, without the syndication guard: beats both baselines (both paired intervals above zero, measured).
- Radar, without the gate (Priority alone): beats both baselines (both paired intervals above zero, measured).

### Per week

| Week | Labelled | Positives | Radar (published) | Radar (gate, no guard) | Radar (no gate) | Raw-count growth | Persistence |
|---|---|---|---|---|---|---|---|
| 2025-W49 | 102 | 24 | 3/10 | 3/10 | 3/10 | 1/10 | 2/10 |
| 2025-W50 | 106 | 23 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2025-W51 | 104 | 16 | 2/10 | 2/10 | 2/10 | 2/10 | 3/10 |
| 2025-W52 | 100 | 25 | 4/10 | 4/10 | 4/10 | 3/10 | 4/10 |
| 2026-W01 | 99 | 25 | 3/10 | 3/10 | 3/10 | 2/10 | 3/10 |
| 2026-W02 | 104 | 25 | 4/10 | 4/10 | 4/10 | 3/10 | 2/10 |
| 2026-W03 | 104 | 26 | 2/10 | 2/10 | 2/10 | 1/10 | 0/10 |
| 2026-W04 | 105 | 27 | 2/10 | 2/10 | 2/10 | 2/10 | 1/10 |
| 2026-W05 | 105 | 27 | 2/10 | 2/10 | 2/10 | 4/10 | 2/10 |
| 2026-W06 | 100 | 25 | 3/10 | 3/10 | 3/10 | 2/10 | 3/10 |
| 2026-W07 | 104 | 26 | 2/10 | 2/10 | 2/10 | 2/10 | 3/10 |
| 2026-W08 | 104 | 29 | 3/10 | 3/10 | 3/10 | 4/10 | 2/10 |
| 2026-W09 | 103 | 26 | 2/10 | 2/10 | 2/10 | 1/10 | 0/10 |
| 2026-W10 | 100 | 25 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W11 | 102 | 26 | 1/10 | 1/10 | 1/10 | 2/10 | 0/10 |
| 2026-W12 | 102 | 26 | 2/10 | 2/10 | 2/10 | 1/10 | 1/10 |
| 2026-W13 | 100 | 25 | 2/10 | 2/10 | 2/10 | 3/10 | 4/10 |
| 2026-W14 | 102 | 26 | 2/10 | 2/10 | 2/10 | 0/10 | 1/10 |
| 2026-W15 | 103 | 26 | 4/10 | 4/10 | 4/10 | 4/10 | 1/10 |
| 2026-W16 | 100 | 26 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W17 | 101 | 26 | 0/10 | 0/10 | 0/10 | 0/10 | 2/10 |
| 2026-W18 | 101 | 26 | 4/10 | 4/10 | 4/10 | 4/10 | 2/10 |
| 2026-W19 | 102 | 26 | 4/10 | 4/10 | 4/10 | 0/10 | 1/10 |
| 2026-W20 | 103 | 26 | 4/10 | 4/10 | 4/10 | 3/10 | 2/10 |
| 2026-W21 | 106 | 27 | 1/10 | 1/10 | 1/10 | 3/10 | 0/10 |
| 2026-W22 | 104 | 26 | 3/10 | 3/10 | 3/10 | 2/10 | 0/10 |
| 2026-W23 | 106 | 27 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W24 | 104 | 26 | 1/10 | 1/10 | 1/10 | 4/10 | 2/10 |
| 2026-W25 | 106 | 27 | 1/10 | 1/10 | 1/10 | 2/10 | 3/10 |
| 2026-W26 | 105 | 27 | 2/10 | 2/10 | 2/10 | 3/10 | 2/10 |
| 2026-W27 | 103 | 27 | 3/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W28 | 101 | 25 | 2/10 | 2/10 | 2/10 | 3/10 | 1/10 |
| 2026-W29 | 105 | 27 | 4/10 | 4/10 | 4/10 | 3/10 | 2/10 |
| 2026-W30 | 102 | 26 | 4/10 | 4/10 | 4/10 | 2/10 | 1/10 |
| 2026-W31 | 104 | 26 | 3/10 | 3/10 | 3/10 | 1/10 | 1/10 |
| 2026-W32 | 102 | 26 | 3/10 | 3/10 | 3/10 | 0/10 | 2/10 |
| 2026-W33 | 103 | 26 | 2/10 | 2/10 | 2/10 | 2/10 | 0/10 |
| 2026-W34 | 105 | 27 | 4/10 | 4/10 | 4/10 | 1/10 | 0/10 |
| 2026-W35 | 103 | 26 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W36 | 104 | 26 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W37 | 103 | 26 | 3/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W38 | 101 | 26 | 2/10 | 2/10 | 2/10 | 2/10 | 0/10 |
| 2026-W39 | 105 | 27 | 3/10 | 3/10 | 3/10 | 3/10 | 2/10 |
