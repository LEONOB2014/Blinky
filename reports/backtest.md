# Backtest: the radar's weekly top 10

Generated 2026-10-18 03:26 UTC-5 by `models/backtest.py` on the `full` profile. Every number below is **measured** on the lake unless marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module docstring. The score weights and thresholds are hand-set (estimate), not fitted to either label. The syndication guard (Addendum 5) was added after WS9 saw syndicated topics in the 2026-W42 top 10; its thresholds come from WS1's source distributions, not from either label, but its design is not blind to the data. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table maps gkg_id to topics yet); the backtest does not use them.

The primary label (es+pt Wikipedia pageviews) is reported below with bounds (coverage under 90.0%). The secondary label (es+pt GDELT article growth) is the fallback card when pageviews are missing.

## Primary label: es+pt Wikipedia pageview growth (exact Wikidata matches only)

- Ranked topics: 4945; with an es or pt Wikipedia article (the backtest ranks those only): 816 (16.5%, measured). Unmapped topic-weeks: 11137 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 408/440 | 92.7% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 403/440 | 91.6% (measured) |
| Radar, without the gate (Priority alone) | 403/440 | 91.6% (measured) |
| Baseline: raw-count growth | 378/440 | 85.9% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 426/440 | 96.8% (measured) |

**Below the 90.0% coverage rule:** at least one ranker has fewer than 90.0% of its top-10 labels, so an unbounded precision@10 is not reported. Below, each ranker's precision is computed on the labelled slots of its own top 10, with bounds that count its unlabelled slots as all misses (worst case) and all hits (best case). The bounds are hard limits; the labelled precision assumes the unlabelled slots behave like the labelled ones, which nothing guarantees (the missing labels are pageview series with fewer than 12 days of data in a 14-day window, mostly new or rarely viewed articles).
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: 0 mapped units with a label (needs 11).
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.

### Precision@10 on labelled slots, with bounds

| Ranker | Coverage (labelled / slots) | Precision@10 on labelled slots | 95% bootstrap interval over weeks | Worst case (unlabelled = misses) | Best case (unlabelled = hits) |
|---|---|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 408/440 = 92.7% | 119/408 = 29.2% | 24.4% .. 34.0% | 27.0% | 34.3% |
| Radar, with the eligibility gate, without the syndication guard | 403/440 = 91.6% | 135/403 = 33.5% | 29.2% .. 38.0% | 30.7% | 39.1% |
| Radar, without the gate (Priority alone) | 403/440 = 91.6% | 134/403 = 33.3% | 28.8% .. 37.5% | 30.5% | 38.9% |
| Baseline: raw-count growth | 378/440 = 85.9% | 120/378 = 31.7% | 26.8% .. 37.0% | 27.3% | 41.4% |
| Baseline: persistence (the label's own last 2 weeks) | 426/440 = 96.8% | 77/426 = 18.1% | 14.8% .. 21.3% | 17.5% | 20.7% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 1036/4085 = 25.4% | n/a | n/a | n/a |

All figures measured. Worst-case comparisons (each radar's worst case minus each baseline's best case, paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -14.3%, 95% interval -20.2% .. -8.6%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 6.4%, 95% interval 0.7% .. 12.0%: the advantage **holds** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: raw-count growth (best): -10.7%, 95% interval -14.8% .. -6.6%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 10.0%, 95% interval 5.0% .. 15.2%: the advantage **holds** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: raw-count growth (best): -10.9%, 95% interval -15.0% .. -7.0%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 9.8%, 95% interval 4.8% .. 14.8%: the advantage **holds** under the worst case.

Hook (primary label): **may not use** this result: the published radar's advantage over raw-count growth does not hold under the worst case (measured). The page uses the secondary label or the fallback hook.

## Primary label, alias matches included (separate row; aliases are confidence 0.6 and several are wrong)

- Ranked topics: 4945; with an es or pt Wikipedia article (the backtest ranks those only): 1094 (22.1%, measured). Unmapped topic-weeks: 9649 (measured).

Label coverage of each ranker's top 10, over evaluable weeks:

| Ranker | Labelled / needed topic-weeks | Coverage |
|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 402/440 | 91.4% (measured) |
| Radar, with the eligibility gate, without the syndication guard | 400/440 | 90.9% (measured) |
| Radar, without the gate (Priority alone) | 356/440 | 80.9% (measured) |
| Baseline: raw-count growth | 318/440 | 72.3% (measured) |
| Baseline: persistence (the label's own last 2 weeks) | 427/440 | 97.0% (measured) |

**Below the 90.0% coverage rule:** at least one ranker has fewer than 90.0% of its top-10 labels, so an unbounded precision@10 is not reported. Below, each ranker's precision is computed on the labelled slots of its own top 10, with bounds that count its unlabelled slots as all misses (worst case) and all hits (best case). The bounds are hard limits; the labelled precision assumes the unlabelled slots behave like the labelled ones, which nothing guarantees (the missing labels are pageview series with fewer than 12 days of data in a 14-day window, mostly new or rarely viewed articles).
- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50, 2025-W51, 2025-W52, 2026-W01, 2026-W02, 2026-W03, 2026-W04, 2026-W05, 2026-W06, 2026-W07, 2026-W08, 2026-W09, 2026-W10, 2026-W11, 2026-W12, 2026-W13, 2026-W14, 2026-W15, 2026-W16, 2026-W17, 2026-W18, 2026-W19, 2026-W20, 2026-W21, 2026-W22, 2026-W23, 2026-W24, 2026-W25, 2026-W26, 2026-W27, 2026-W28, 2026-W29, 2026-W30, 2026-W31, 2026-W32, 2026-W33, 2026-W34, 2026-W35, 2026-W36, 2026-W37, 2026-W38, 2026-W39.
  - 2026-W40 excluded: 0 mapped units with a label (needs 11).
  - 2026-W41 excluded: label window not complete.
  - 2026-W42 excluded: label window not complete.

### Precision@10 on labelled slots, with bounds

| Ranker | Coverage (labelled / slots) | Precision@10 on labelled slots | 95% bootstrap interval over weeks | Worst case (unlabelled = misses) | Best case (unlabelled = hits) |
|---|---|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 402/440 = 91.4% | 113/402 = 28.1% | 23.3% .. 33.1% | 25.7% | 34.3% |
| Radar, with the eligibility gate, without the syndication guard | 400/440 = 90.9% | 134/400 = 33.5% | 29.2% .. 38.2% | 30.5% | 39.5% |
| Radar, without the gate (Priority alone) | 356/440 = 80.9% | 118/356 = 33.1% | 29.1% .. 37.3% | 26.8% | 45.9% |
| Baseline: raw-count growth | 318/440 = 72.3% | 106/318 = 33.3% | 27.9% .. 39.1% | 24.1% | 51.8% |
| Baseline: persistence (the label's own last 2 weeks) | 427/440 = 97.0% | 72/427 = 16.9% | 13.6% .. 20.1% | 16.4% | 19.3% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 1181/4668 = 25.3% | n/a | n/a | n/a |

All figures measured. Worst-case comparisons (each radar's worst case minus each baseline's best case, paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -26.1%, 95% interval -32.0% .. -20.0%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 6.4%, 95% interval 0.9% .. 12.3%: the advantage **holds** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: raw-count growth (best): -21.4%, 95% interval -26.1% .. -16.6%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate, without the syndication guard (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 11.1%, 95% interval 5.9% .. 16.8%: the advantage **holds** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: raw-count growth (best): -25.0%, 95% interval -30.0% .. -19.5%: the advantage **does not hold** under the worst case.
- Radar, without the gate (Priority alone) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 7.5%, 95% interval 2.5% .. 12.0%: the advantage **holds** under the worst case.

## Secondary label: es+pt GDELT article growth

- Ranked topics: 4945, all labelled by their own es+pt GDELT series (no Wikipedia needed). This label is not independent of the radar: saturation and fit read the same es+pt stream (the label is the next 2 weeks; the features read only the past).

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
- Base rate 6.7%, not 25%: many topics have the same label growth (for the GDELT label, most have no es/pt article in either window, growth 0). A tie at the quartile cutoff is left out rather than split by row order, so a positive is real growth (measured).
- Mapped topics with a label per evaluable week: 210..559 (measured).

### Precision@10

| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |
|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 57/430 | 13.3% (measured) | 9.5% .. 17.2% |
| Radar, with the eligibility gate, without the syndication guard | 32/430 | 7.4% (measured) | 5.1% .. 10.2% |
| Radar, without the gate (Priority alone) | 31/430 | 7.2% (measured) | 4.9% .. 9.5% |
| Baseline: raw-count growth | 1/430 | 0.2% (measured) | 0.0% .. 0.7% |
| Baseline: persistence (the label's own last 2 weeks) | 55/430 | 12.8% (measured) | 9.1% .. 17.0% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | 1076/15959 | 6.7% (measured) | n/a |

Differences in precision points (paired bootstrap over weeks):

- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: raw-count growth: 13.0%, 95% interval 9.3% .. 17.2% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Baseline: persistence (the label's own last 2 weeks): 0.5%, 95% interval -3.7% .. 4.9% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: raw-count growth: 7.2%, 95% interval 4.7% .. 9.8% (measured).
- Radar, with the eligibility gate, without the syndication guard minus Baseline: persistence (the label's own last 2 weeks): -5.3%, 95% interval -9.3% .. -1.6% (measured).
- Radar, without the gate (Priority alone) minus Baseline: raw-count growth: 7.0%, 95% interval 4.4% .. 9.5% (measured).
- Radar, without the gate (Priority alone) minus Baseline: persistence (the label's own last 2 weeks): -5.6%, 95% interval -9.1% .. -2.3% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, without the gate (Priority alone): 6.0%, 95% interval 2.3% .. 9.5% (measured).
- Radar, with the eligibility gate and the syndication guard (published) minus Radar, with the eligibility gate, without the syndication guard: 5.8%, 95% interval 2.8% .. 9.1% (measured).

### Lead time

- Radar, with the eligibility gate and the syndication guard (published): median 3.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 4.0, over 47 flagged positives (measured).
- Radar, with the eligibility gate, without the syndication guard: median 2.5 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 5.0, over 28 flagged positives (measured).
- Radar, without the gate (Priority alone): median 2.0 weeks from the first flag to the label's peak within 8 weeks, 95% bootstrap interval 2.0 .. 6.0, over 29 flagged positives (measured).

### Verdict

- Radar, with the eligibility gate and the syndication guard (published): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, with the eligibility gate, without the syndication guard: **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).
- Radar, without the gate (Priority alone): **does not beat both baselines** (an interval reaches zero or below, or there are too few weeks for one; measured).

Diagnosis:

- Radar hits per week range 0..5 of 10; weeks at or below the base rate: 12 of 43 (measured).
- Overlap between the radar's and persistence's top 10: median 0 units a week (measured).
- The radar's precision (13.3%) is close to the base rate (6.7%); persistence reaches 12.8%: on this label, past es/pt growth predicts future es/pt growth better than the radar's emergence-led Priority (measured).
- The weights and thresholds of the scores are hand-set placeholders (estimate), not fitted to this label.

### Per week

| Week | Labelled | Positives | Radar (published) | Radar (gate, no guard) | Radar (no gate) | Raw-count growth | Persistence |
|---|---|---|---|---|---|---|---|
| 2025-W49 | 343 | 29 | 5/10 | 3/10 | 3/10 | 0/10 | 3/10 |
| 2025-W50 | 380 | 12 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2025-W51 | 275 | 8 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2025-W52 | 221 | 23 | 2/10 | 2/10 | 1/10 | 0/10 | 3/10 |
| 2026-W01 | 210 | 29 | 2/10 | 2/10 | 2/10 | 0/10 | 5/10 |
| 2026-W02 | 384 | 27 | 1/10 | 1/10 | 2/10 | 0/10 | 1/10 |
| 2026-W03 | 385 | 21 | 1/10 | 1/10 | 1/10 | 0/10 | 0/10 |
| 2026-W04 | 352 | 25 | 2/10 | 2/10 | 1/10 | 0/10 | 0/10 |
| 2026-W05 | 334 | 22 | 0/10 | 0/10 | 1/10 | 0/10 | 0/10 |
| 2026-W06 | 343 | 22 | 0/10 | 0/10 | 0/10 | 0/10 | 2/10 |
| 2026-W07 | 335 | 28 | 3/10 | 2/10 | 2/10 | 0/10 | 3/10 |
| 2026-W08 | 386 | 23 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W09 | 452 | 31 | 0/10 | 0/10 | 2/10 | 0/10 | 4/10 |
| 2026-W10 | 378 | 22 | 1/10 | 0/10 | 1/10 | 0/10 | 0/10 |
| 2026-W11 | 315 | 17 | 1/10 | 1/10 | 1/10 | 0/10 | 0/10 |
| 2026-W12 | 348 | 22 | 1/10 | 1/10 | 0/10 | 0/10 | 1/10 |
| 2026-W13 | 322 | 16 | 1/10 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W14 | 264 | 21 | 3/10 | 1/10 | 0/10 | 0/10 | 1/10 |
| 2026-W15 | 259 | 28 | 1/10 | 1/10 | 1/10 | 0/10 | 2/10 |
| 2026-W16 | 339 | 29 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W17 | 371 | 30 | 3/10 | 1/10 | 1/10 | 0/10 | 3/10 |
| 2026-W18 | 376 | 25 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W19 | 315 | 28 | 1/10 | 2/10 | 1/10 | 0/10 | 1/10 |
| 2026-W20 | 460 | 34 | 1/10 | 1/10 | 2/10 | 0/10 | 4/10 |
| 2026-W21 | 482 | 32 | 2/10 | 3/10 | 1/10 | 0/10 | 4/10 |
| 2026-W22 | 417 | 35 | 1/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W23 | 443 | 28 | 3/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W24 | 428 | 20 | 0/10 | 0/10 | 2/10 | 0/10 | 0/10 |
| 2026-W25 | 300 | 18 | 1/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W26 | 453 | 25 | 0/10 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W27 | 328 | 23 | 3/10 | 0/10 | 0/10 | 0/10 | 2/10 |
| 2026-W28 | 388 | 20 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W29 | 433 | 30 | 2/10 | 0/10 | 0/10 | 0/10 | 0/10 |
| 2026-W30 | 365 | 27 | 1/10 | 0/10 | 1/10 | 0/10 | 1/10 |
| 2026-W31 | 410 | 25 | 1/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W32 | 345 | 21 | 2/10 | 1/10 | 1/10 | 0/10 | 1/10 |
| 2026-W33 | 344 | 24 | 1/10 | 0/10 | 0/10 | 0/10 | 1/10 |
| 2026-W34 | 373 | 18 | 1/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W35 | 421 | 25 | 1/10 | 1/10 | 0/10 | 1/10 | 2/10 |
| 2026-W36 | 381 | 34 | 5/10 | 1/10 | 2/10 | 0/10 | 3/10 |
| 2026-W37 | 414 | 40 | 2/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W38 | 528 | 35 | 1/10 | 1/10 | 0/10 | 0/10 | 0/10 |
| 2026-W39 | 559 | 24 | 1/10 | 0/10 | 0/10 | 0/10 | 1/10 |
