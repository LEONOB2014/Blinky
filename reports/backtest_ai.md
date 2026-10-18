# Backtest: the radar's weekly top 10 (AI lexicon topics)

Generated 2026-10-18 14:52 UTC-5 by `models/backtest.py` on the `full` profile. Every number below is **measured** on the lake unless marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module docstring. The score weights and thresholds are hand-set (estimate), not fitted to either label. The syndication guard (Addendum 5) was added after WS9 saw syndicated topics in the 2026-W42 top 10; its thresholds come from WS1's source distributions, not from either label, but its design is not blind to the data. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table maps gkg_id to topics yet); the backtest does not use them.

The primary label (es+pt Wikipedia pageviews) is reported below with bounds (coverage under 90.0%). The secondary label (es+pt GDELT article growth) is the fallback card when pageviews are missing.

## Primary label: es+pt Wikipedia pageview growth (the AI lexicon's page titles)

- Ranked topics: 108; with an es or pt Wikipedia article (the backtest ranks those only): 27 (25.0%, measured). Unmapped topic-weeks: 2550 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 395/440 | 89.8% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 395/440 | 89.8% (measured) |
| Radar, without the gate (Priority alone) | 395/440 | 89.8% (measured) |
| Baseline: raw-count growth | 395/440 | 89.8% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 430/440 | 97.7% (measured) |

**Below the 90.0% coverage rule:** at least one ranker has fewer than 90.0% of its top-10 labels, so an unbounded precision@10 is not reported. Below, each ranker's precision is computed on the labelled slots of its own top 10, with bounds that count its unlabelled slots as all misses (worst case) and all hits (best case). The bounds are hard limits; the labelled precision assumes the unlabelled slots behave like the labelled ones, which nothing guarantees (the missing labels are pageview series with fewer than 12 days of data in a 14-day window, mostly new or rarely viewed articles).
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: 0 mapped units with a label (needs 11).
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.

### Precision@10 on labelled slots, with bounds

| Ranker | Coverage (labelled / slots) | Precision@10 on labelled slots | 95% bootstrap interval over weeks | Worst case (unlabelled = misses) | Best case (unlabelled = hits) |
|---|---|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 395/440 = 89.8% | 110/395 = 27.8% | 24.3% .. 31.4% | 25.0% | 35.2% |
| Radar, with the eligibility gate, without the syndication guard | 395/440 = 89.8% | 110/395 = 27.8% | 24.2% .. 31.3% | 25.0% | 35.2% |
| Radar, without the gate (Priority alone) | 395/440 = 89.8% | 110/395 = 27.8% | 24.4% .. 31.4% | 25.0% | 35.2% |
| Baseline: raw-count growth | 395/440 = 89.8% | 108/395 = 27.3% | 24.0% .. 30.7% | 24.5% | 34.8% |
| Baseline: persistence (the label's own last 2 weeks) | 430/440 = 97.7% | 95/430 = 22.1% | 18.6% .. 25.8% | 21.6% | 23.9% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 254/959 = 26.5% | n/a | n/a | n/a |

All figures measured. Worst-case comparisons (each radar's worst case minus each baseline's best case, paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -9.8%, 95% interval -13.2% .. -6.4%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.1%, 95% interval -4.3% .. 5.9%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: raw-count growth (best): -9.8%, 95% interval -13.2% .. -6.1%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.1%, 95% interval -3.9% .. 6.4%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: raw-count growth (best): -9.8%, 95% interval -13.0% .. -6.4%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 1.1%, 95% interval -3.9% .. 5.9%: the advantage **does not hold** under the worst case.

Hook (primary label): **may not use** this result: the published radar's advantage over raw-count growth does not hold under the worst case (measured). The page uses the secondary label or the fallback hook.

## Secondary label: es+pt GDELT article growth

- Ranked topics: 108, all labelled by their own es+pt GDELT series (no Wikipedia needed). This label is not independent of the radar: saturation and fit read the same es+pt stream (the label is the next 2 weeks; the features read only the past).

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
- Mapped topics with a label per evaluable week: 61..87 (measured).

### Precision@10

| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |
|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 95/430 | 22.1% (measured) | 18.8% .. 25.6% |
| Radar, with the eligibility gate, without the syndication guard | 97/430 | 22.6% (measured) | 19.1% .. 26.0% |
| Radar, without the gate (Priority alone) | 97/430 | 22.6% (measured) | 19.1% .. 25.8% |
| Baseline: raw-count growth | 119/430 | 27.7% (measured) | 23.5% .. 31.6% |
| Baseline: persistence (the label's own last 2 weeks) | 51/430 | 11.9% (measured) | 8.8% .. 14.9% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | 860/3391 | 25.4% (measured) | n/a |

Differences in precision points (paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: raw-count growth: -5.6%, 95% interval -10.0% .. -0.9% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: persistence (the label's own last 2 weeks): 10.2%, 95% interval 6.5% .. 14.2% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: raw-count growth: -5.1%, 95% interval -9.5% .. -0.5% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: persistence (the label's own last 2 weeks): 10.7%, 95% interval 7.0% .. 14.4% (measured).
- Radar, without the gate (Priority alone) minus Baseline: raw-count growth: -5.1%, 95% interval -9.5% .. -0.7% (measured).
- Radar, without the gate (Priority alone) minus Baseline: persistence (the label's own last 2 weeks): 10.7%, 95% interval 7.0% .. 14.4% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, without the gate (Priority alone): -0.5%, 95% interval -1.2% .. 0.0% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, with the eligibility gate, without the syndication guard: -0.5%, 95% interval -1.2% .. 0.0% (measured).

### Lead time

- Radar, with the eligibility gate and the syndication guard (published): median 2.5 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 4.0, over 78 flagged positives (measured).
- Radar, with the eligibility gate, without the syndication guard: median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 4.0, over 79 flagged positives (measured).
- Radar, without the gate (Priority alone): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 4.0, over 79 flagged positives (measured).

### Verdict

- Radar, with the eligibility gate and the syndication guard (published): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, with the eligibility gate, without the syndication guard: **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, without the gate (Priority alone): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).

Diagnosis:

- Radar hits per week range 0..4 of 10; weeks at or below the base rate: 27 of 43 (measured).
- Overlap between the radar's and persistence's top 10: median 1 units a week (measured).
- The radar's precision (22.1%) is close to the base rate (25.4%); persistence reaches 11.9%: on this label, past es/pt growth predicts future es/pt growth better than the radar's emergence-led Priority (measured).
- The weights and thresholds of the scores are hand-set placeholders (estimate), not fitted to this label.

### Per week

| Week | Labelled | Positives | Radar (published) | Radar (gate, no guard) | Radar (no gate) | Raw-count growth | Persistence |
|---|---|---|---|---|---|---|---|
| 2025-W49 | 79 | 20 | 3/10 | 3/10 | 3/10 | 2/10 | 2/10 |
| 2025-W50 | 79 | 19 | 2/10 | 2/10 | 2/10 | 3/10 | 1/10 |
| 2025-W51 | 75 | 19 | 4/10 | 4/10 | 4/10 | 4/10 | 4/10 |
| 2025-W52 | 61 | 16 | 3/10 | 3/10 | 3/10 | 5/10 | 2/10 |
| 2026-W01 | 66 | 16 | 2/10 | 2/10 | 2/10 | 5/10 | 3/10 |
| 2026-W02 | 74 | 19 | 4/10 | 4/10 | 4/10 | 3/10 | 2/10 |
| 2026-W03 | 82 | 21 | 0/10 | 0/10 | 0/10 | 2/10 | 0/10 |
| 2026-W04 | 75 | 19 | 2/10 | 2/10 | 2/10 | 2/10 | 1/10 |
| 2026-W05 | 78 | 20 | 2/10 | 2/10 | 2/10 | 5/10 | 2/10 |
| 2026-W06 | 70 | 18 | 4/10 | 4/10 | 4/10 | 1/10 | 2/10 |
| 2026-W07 | 77 | 20 | 2/10 | 2/10 | 2/10 | 3/10 | 2/10 |
| 2026-W08 | 84 | 19 | 2/10 | 2/10 | 2/10 | 4/10 | 2/10 |
| 2026-W09 | 77 | 20 | 2/10 | 2/10 | 2/10 | 1/10 | 0/10 |
| 2026-W10 | 76 | 19 | 4/10 | 4/10 | 4/10 | 2/10 | 0/10 |
| 2026-W11 | 79 | 20 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W12 | 82 | 21 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W13 | 79 | 20 | 2/10 | 2/10 | 2/10 | 5/10 | 2/10 |
| 2026-W14 | 78 | 20 | 2/10 | 2/10 | 2/10 | 1/10 | 1/10 |
| 2026-W15 | 75 | 19 | 2/10 | 2/10 | 2/10 | 3/10 | 1/10 |
| 2026-W16 | 75 | 18 | 4/10 | 4/10 | 4/10 | 2/10 | 1/10 |
| 2026-W17 | 77 | 20 | 0/10 | 0/10 | 0/10 | 1/10 | 2/10 |
| 2026-W18 | 76 | 19 | 4/10 | 4/10 | 4/10 | 5/10 | 2/10 |
| 2026-W19 | 80 | 20 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W20 | 76 | 19 | 2/10 | 2/10 | 2/10 | 5/10 | 1/10 |
| 2026-W21 | 81 | 21 | 1/10 | 1/10 | 1/10 | 3/10 | 0/10 |
| 2026-W22 | 79 | 20 | 3/10 | 3/10 | 3/10 | 4/10 | 0/10 |
| 2026-W23 | 85 | 22 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 |
| 2026-W24 | 81 | 21 | 1/10 | 1/10 | 1/10 | 3/10 | 0/10 |
| 2026-W25 | 82 | 21 | 1/10 | 1/10 | 1/10 | 2/10 | 3/10 |
| 2026-W26 | 80 | 20 | 2/10 | 2/10 | 2/10 | 4/10 | 2/10 |
| 2026-W27 | 82 | 21 | 2/10 | 2/10 | 2/10 | 4/10 | 0/10 |
| 2026-W28 | 83 | 22 | 2/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W29 | 84 | 21 | 4/10 | 4/10 | 4/10 | 4/10 | 2/10 |
| 2026-W30 | 87 | 22 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W31 | 87 | 22 | 3/10 | 3/10 | 3/10 | 5/10 | 1/10 |
| 2026-W32 | 83 | 21 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W33 | 82 | 21 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 |
| 2026-W34 | 77 | 20 | 3/10 | 3/10 | 3/10 | 3/10 | 0/10 |
| 2026-W35 | 80 | 20 | 1/10 | 1/10 | 1/10 | 2/10 | 1/10 |
| 2026-W36 | 78 | 20 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W37 | 85 | 22 | 2/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W38 | 87 | 22 | 2/10 | 2/10 | 2/10 | 2/10 | 0/10 |
| 2026-W39 | 78 | 20 | 2/10 | 2/10 | 2/10 | 1/10 | 3/10 |
