# Backtest: the radar's weekly top 10 (AI lexicon topics)

Generated 2026-10-18 09:20 UTC-5 by `models/backtest.py` on the `full` profile. Every number below is **measured** on the lake unless marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module docstring. The score weights and thresholds are hand-set (estimate), not fitted to either label. The syndication guard (Addendum 5) was added after WS9 saw syndicated topics in the 2026-W42 top 10; its thresholds come from WS1's source distributions, not from either label, but its design is not blind to the data. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table maps gkg_id to topics yet); the backtest does not use them.

The primary label (es+pt Wikipedia pageviews) is reported below with bounds (coverage under 90.0%). The secondary label (es+pt GDELT article growth) is the fallback card when pageviews are missing.

## Primary label: es+pt Wikipedia pageview growth (the AI lexicon's page titles)

- Ranked topics: 101; with an es or pt Wikipedia article (the backtest ranks those only): 27 (26.7%, measured). Unmapped topic-weeks: 2293 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 394/440 | 89.5% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 394/440 | 89.5% (measured) |
| Radar, without the gate (Priority alone) | 394/440 | 89.5% (measured) |
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
| Radar, with the eligibility gate and the syndication guard (published) | 394/440 = 89.5% | 109/394 = 27.7% | 24.0% .. 31.2% | 24.8% | 35.2% |
| Radar, with the eligibility gate, without the syndication guard | 394/440 = 89.5% | 109/394 = 27.7% | 24.0% .. 31.1% | 24.8% | 35.2% |
| Radar, without the gate (Priority alone) | 394/440 = 89.5% | 109/394 = 27.7% | 24.2% .. 31.1% | 24.8% | 35.2% |
| Baseline: raw-count growth | 395/440 = 89.8% | 108/395 = 27.3% | 24.0% .. 30.7% | 24.5% | 34.8% |
| Baseline: persistence (the label's own last 2 weeks) | 430/440 = 97.7% | 95/430 = 22.1% | 18.6% .. 25.8% | 21.6% | 23.9% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 254/959 = 26.5% | n/a | n/a | n/a |

All figures measured. Worst-case comparisons (each radar's worst case minus each baseline's best case, paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -10.0%, 95% interval -13.6% .. -6.6%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 0.9%, 95% interval -4.5% .. 5.7%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: raw-count growth (best): -10.0%, 95% interval -13.4% .. -6.4%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 0.9%, 95% interval -4.1% .. 5.9%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: raw-count growth (best): -10.0%, 95% interval -13.4% .. -6.6%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 0.9%, 95% interval -4.1% .. 5.7%: the advantage **does not hold** under the worst case.

Hook (primary label): **may not use** this result: the published radar's advantage over raw-count growth does not hold under the worst case (measured). The page uses the secondary label or the fallback hook.

## Secondary label: es+pt GDELT article growth

- Ranked topics: 101, all labelled by their own es+pt GDELT series (no Wikipedia needed). This label is not independent of the radar: saturation and fit read the same es+pt stream (the label is the next 2 weeks; the features read only the past).

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
- Mapped topics with a label per evaluable week: 58..82 (measured).

### Precision@10

| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |
|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 110/430 | 25.6% (measured) | 22.3% .. 28.8% |
| Radar, with the eligibility gate, without the syndication guard | 110/430 | 25.6% (measured) | 22.1% .. 28.8% |
| Radar, without the gate (Priority alone) | 110/430 | 25.6% (measured) | 22.3% .. 28.8% |
| Baseline: raw-count growth | 117/430 | 27.2% (measured) | 23.3% .. 31.2% |
| Baseline: persistence (the label's own last 2 weeks) | 53/430 | 12.3% (measured) | 9.3% .. 15.6% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | 802/3152 | 25.4% (measured) | n/a |

Differences in precision points (paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: raw-count growth: -1.6%, 95% interval -5.6% .. 2.3% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: persistence (the label's own last 2 weeks): 13.3%, 95% interval 9.1% .. 17.2% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: raw-count growth: -1.6%, 95% interval -5.6% .. 2.6% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: persistence (the label's own last 2 weeks): 13.3%, 95% interval 9.1% .. 17.0% (measured).
- Radar, without the gate (Priority alone) minus Baseline: raw-count growth: -1.6%, 95% interval -5.6% .. 2.1% (measured).
- Radar, without the gate (Priority alone) minus Baseline: persistence (the label's own last 2 weeks): 13.3%, 95% interval 9.1% .. 17.0% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, without the gate (Priority alone): 0.0%, 95% interval -0.7% .. 0.7% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, with the eligibility gate, without the syndication guard: 0.0%, 95% interval -0.7% .. 0.7% (measured).

### Lead time

- Radar, with the eligibility gate and the syndication guard (published): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 91 flagged positives (measured).
- Radar, with the eligibility gate, without the syndication guard: median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 90 flagged positives (measured).
- Radar, without the gate (Priority alone): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 3.0, over 90 flagged positives (measured).

### Verdict

- Radar, with the eligibility gate and the syndication guard (published): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, with the eligibility gate, without the syndication guard: **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, without the gate (Priority alone): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).

Diagnosis:

- Radar hits per week range 0..5 of 10; weeks at or below the base rate: 20 of 43 (measured).
- Overlap between the radar's and persistence's top 10: median 1 units a week (measured).
- The radar's precision (25.6%) is close to the base rate (25.4%); persistence reaches 12.3%: on this label, past es/pt growth predicts future es/pt growth better than the radar's emergence-led Priority (measured).
- The weights and thresholds of the scores are hand-set placeholders (estimate), not fitted to this label.

### Per week

| Week | Labelled | Positives | Radar (published) | Radar (gate, no guard) | Radar (no gate) | Raw-count growth | Persistence |
|---|---|---|---|---|---|---|---|
| 2025-W49 | 73 | 19 | 3/10 | 3/10 | 3/10 | 2/10 | 2/10 |
| 2025-W50 | 73 | 19 | 3/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2025-W51 | 69 | 18 | 4/10 | 4/10 | 4/10 | 4/10 | 4/10 |
| 2025-W52 | 58 | 15 | 4/10 | 4/10 | 4/10 | 5/10 | 2/10 |
| 2026-W01 | 62 | 16 | 5/10 | 5/10 | 5/10 | 5/10 | 3/10 |
| 2026-W02 | 68 | 17 | 4/10 | 4/10 | 4/10 | 3/10 | 2/10 |
| 2026-W03 | 77 | 20 | 0/10 | 0/10 | 0/10 | 2/10 | 0/10 |
| 2026-W04 | 70 | 19 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W05 | 72 | 18 | 3/10 | 3/10 | 3/10 | 5/10 | 2/10 |
| 2026-W06 | 66 | 17 | 3/10 | 3/10 | 3/10 | 2/10 | 3/10 |
| 2026-W07 | 71 | 18 | 2/10 | 2/10 | 2/10 | 3/10 | 2/10 |
| 2026-W08 | 78 | 19 | 2/10 | 2/10 | 2/10 | 4/10 | 2/10 |
| 2026-W09 | 71 | 18 | 2/10 | 2/10 | 2/10 | 1/10 | 0/10 |
| 2026-W10 | 71 | 17 | 3/10 | 3/10 | 3/10 | 2/10 | 0/10 |
| 2026-W11 | 74 | 19 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W12 | 76 | 19 | 3/10 | 3/10 | 3/10 | 1/10 | 1/10 |
| 2026-W13 | 73 | 19 | 2/10 | 2/10 | 2/10 | 5/10 | 2/10 |
| 2026-W14 | 72 | 18 | 2/10 | 2/10 | 2/10 | 1/10 | 1/10 |
| 2026-W15 | 70 | 18 | 3/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W16 | 70 | 18 | 4/10 | 4/10 | 4/10 | 2/10 | 2/10 |
| 2026-W17 | 72 | 18 | 0/10 | 0/10 | 0/10 | 1/10 | 3/10 |
| 2026-W18 | 71 | 18 | 4/10 | 4/10 | 4/10 | 4/10 | 1/10 |
| 2026-W19 | 74 | 19 | 3/10 | 3/10 | 3/10 | 1/10 | 1/10 |
| 2026-W20 | 70 | 18 | 1/10 | 1/10 | 1/10 | 4/10 | 1/10 |
| 2026-W21 | 76 | 19 | 2/10 | 2/10 | 2/10 | 3/10 | 0/10 |
| 2026-W22 | 75 | 19 | 4/10 | 4/10 | 4/10 | 4/10 | 0/10 |
| 2026-W23 | 79 | 20 | 1/10 | 1/10 | 1/10 | 1/10 | 0/10 |
| 2026-W24 | 75 | 19 | 1/10 | 1/10 | 1/10 | 3/10 | 0/10 |
| 2026-W25 | 76 | 19 | 1/10 | 1/10 | 1/10 | 2/10 | 3/10 |
| 2026-W26 | 74 | 19 | 3/10 | 3/10 | 3/10 | 4/10 | 2/10 |
| 2026-W27 | 76 | 19 | 2/10 | 2/10 | 2/10 | 3/10 | 0/10 |
| 2026-W28 | 77 | 19 | 2/10 | 2/10 | 2/10 | 4/10 | 1/10 |
| 2026-W29 | 78 | 20 | 4/10 | 4/10 | 4/10 | 4/10 | 2/10 |
| 2026-W30 | 81 | 21 | 4/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W31 | 81 | 21 | 3/10 | 3/10 | 3/10 | 5/10 | 1/10 |
| 2026-W32 | 77 | 20 | 3/10 | 3/10 | 3/10 | 2/10 | 1/10 |
| 2026-W33 | 76 | 19 | 2/10 | 2/10 | 2/10 | 1/10 | 0/10 |
| 2026-W34 | 71 | 18 | 3/10 | 3/10 | 3/10 | 3/10 | 0/10 |
| 2026-W35 | 74 | 20 | 2/10 | 2/10 | 2/10 | 2/10 | 1/10 |
| 2026-W36 | 72 | 18 | 3/10 | 3/10 | 3/10 | 1/10 | 0/10 |
| 2026-W37 | 79 | 20 | 2/10 | 3/10 | 3/10 | 3/10 | 1/10 |
| 2026-W38 | 82 | 20 | 2/10 | 2/10 | 2/10 | 2/10 | 0/10 |
| 2026-W39 | 72 | 18 | 2/10 | 2/10 | 2/10 | 2/10 | 3/10 |
