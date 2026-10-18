# Report: Curator Label Quality, Teacher Distillation & Jev Cascade (WS2b)

Every number below is marked **(measured)** or **(estimate)** with its denominator and
95% Wilson (proportions) or bootstrap (F1, recall estimator, paired differences) confidence interval.

## 1. Candidate Teacher Model Licences & 100-Article Pilot

Before any model was used as a teacher, its Hugging Face model card licence was verified.
Only permissive open-weight licences allowing training on outputs (`Apache-2.0`, `MIT`) qualify.
`typesafe/jev-1.14` (OpenRouter Decisions API) has no trainable-output licence and is used
**strictly at inference for doubtful cases, never as training data**.

| Model | Family | Licence | Trainable | Pilot Valid / N | Fail Rate | p50 Latency | Tokens (100 rows) | Est. Cost (100 rows) | Status |
|---|---|---|---|---|---|---|---|---|---|
| `Qwen/Qwen3-235B-A22B-Instruct-2507` | `qwen` | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507/blob/main/LICENSE) | `True` | `100/100` (measured) | `0.0%` (measured) | `1309 ms` (measured) | `61,410` (measured) | `$0.0135` (estimate) | Selected (Primary) |
| `openai/gpt-oss-120b` | `gpt-oss` | [Apache-2.0](https://huggingface.co/openai/gpt-oss-120b/blob/main/README.md) | `True` | `99/100` (measured) | `1.0%` (measured) | `731 ms` (measured) | `81,942` (measured) | `$0.0210` (estimate) | Selected (Tie-breaker) |
| `deepseek-ai/DeepSeek-V4-Pro` | `deepseek` | [MIT](https://huggingface.co/deepseek-ai) | `True` | `100/100` (measured) | `0.0%` (measured) | `1492 ms` (measured) | `63,317` (measured) | `$0.0209` (estimate) | Selected (Primary) |
| `Qwen/Qwen3.5-397B-A17B` | `qwen` | [Apache-2.0](https://huggingface.co/Qwen/Qwen3.5-397B-A17B/blob/main/LICENSE) | `True` | `0/100` (measured) | `100.0%` (measured) | `0 ms` (measured) | `108,977` (measured) | `$0.0836` (estimate) | Dropped (>5% invalid) |
| `Qwen/Qwen3-30B-A3B-Instruct-2507` | `qwen` | [Apache-2.0](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507/blob/main/LICENSE) | `True` | `97/100` (measured) | `3.0%` (measured) | `944 ms` (measured) | `61,454` (measured) | `$0.0068` (estimate) | Qualified (Backup) |

**Pairwise `is_ai` agreement on the 100 pilot articles (measured):**
- `qwen3_235b__vs__gpt_oss_120b`: `97.98%` (`n = 100`, measured)
- `qwen3_235b__vs__deepseek_v4_pro`: `100.00%` (`n = 100`, measured)
- `qwen3_235b__vs__qwen3_30b`: `96.91%` (`n = 100`, measured)
- `gpt_oss_120b__vs__deepseek_v4_pro`: `97.98%` (`n = 100`, measured)
- `gpt_oss_120b__vs__qwen3_30b`: `96.88%` (`n = 100`, measured)
- `deepseek_v4_pro__vs__qwen3_30b`: `96.91%` (`n = 100`, measured)

## 2. Multi-Family Teacher Panel Agreement & Spend

- **Primary Teacher 1**: `Qwen/Qwen3-235B-A22B-Instruct-2507` (`Apache-2.0`)
- **Primary Teacher 2**: `deepseek-ai/DeepSeek-V4-Pro` (`MIT`)
- **Tie-breaker Teacher 3**: `openai/gpt-oss-120b` (`Apache-2.0`)
- **Round 1 stratified sample (`lake/labels/sample.parquet`)**: `4,000` rows (`1,500` ring 1, `1,000` ring 2, `500` ring 3, `1,000` rejected `f_control`; `es/pt` share = `36.0%`, measured).
  - Teacher 1 vs Teacher 2 exact `is_ai` agreement: `96.78%` (`3,611/3,980` rows, measured).
  - Teacher 1 vs Teacher 2 exact `brand_safe` agreement: `94.35%` (measured).
  - Disagreement rows sent to Teacher 3 tie-breaker: `369/4,000` (`9.22%`, measured).
  - Teacher 1 agreement with final panel `is_ai`: `97.99%` (measured).
  - Teacher 2 agreement with final panel `is_ai`: `98.80%` (measured).
  - Panel positive `is_ai` rate on the 4,000 sample: `1,258/4,000` (`31.45%`, measured).
  - Round 1 Nebius token spend: T1 `2,471,924` tokens (`$0.5431` estimate), T2 `2,535,857` tokens (`$0.8379` estimate), T3 `316,811` tokens (`$0.0845` estimate); total Round 1 panel cost = `$1.4655` (estimate).
- **Round 2 active-learning sample (`lake/labels/active_sample.parquet`)**: `2,000` rows selected from the 8,000-row lake pool where the Round 1 student was least certain (`|p - 0.5|` smallest, stratified by ring and language).
  - Teacher 1 vs Teacher 2 `is_ai` agreement on Round 2 uncertain rows: `91.88%` (`disagreed = 216/2,000`, measured).
  - Round 2 panel cost: `$0.7489` (estimate).

## 3. Student Model Selection (`Qwen3-Embedding-8B` + GDELT Flags) & Active Learning

- **Splits of initial 4,000 sample**: `train = 2,400`, `val = 800` (held-out selection & calibration), `test = 800` (frozen test split, never used for selection or tuning).
- **Round 2 training set size**: `4,400` (`2,400` initial train + `2,000` active-learning rows).

### `is_ai` Model Comparison (Round 2 Student)

| Split | Model | Calibration | Precision (95% CI) | Recall (95% CI) | F1 (95% CI) | ROC-AUC | Brier |
|---|---|---|---|---|---|---|---|
| Validation (`n=800`) | `logreg` | `platt` | `0.9531` (`[0.9199, 0.9730]`, measured) | `0.9644` (`[0.9338, 0.9812]`, measured) | `0.9587` (`[0.9375, 0.9761]`, measured) | `0.9948` (measured) | `0.0201` (measured) |
| Validation (`n=800`) | `lightgbm` | `isotonic` | `0.9432` (`[0.9084, 0.9653]`, measured) | `0.9842` (`[0.9601, 0.9938]`, measured) | `0.9632` (`[0.9488, 0.9798]`, measured) | `0.9913` (measured) | `0.0216` (measured) |
| Frozen Test (`n=800`) | `logreg` | `platt` | `0.9603` (`[0.9285, 0.9783]`, measured) | `0.9641` (`[0.9333, 0.9810]`, measured) | `0.9622` (`[0.9444, 0.9779]`, measured) | `0.9937` (measured) | `0.0217` (measured) |
| Frozen Test (`n=800`) | `lightgbm` | `isotonic` | `0.9641` (`[0.9333, 0.9810]`, measured) | `0.9641` (`[0.9333, 0.9810]`, measured) | `0.9641` (`[0.9474, 0.9794]`, measured) | `0.9942` (measured) | `0.0203` (measured) |

- **Selected `is_ai` student**: `lightgbm` (`isotonic` calibration).
- **Selected `brand_safe` student**: `lightgbm` (Frozen test F1 = `0.9899`, 95% CI `[0.9848, 0.9943]`, measured).
- **12 Subtopics macro-F1**: Validation `0.6483` (measured), Frozen test `0.6350` (measured).

### Active Learning Round 2 Validation & Frozen Test Impact

- Mean `|p - 0.5|` of the 2,000 selected pool articles: `0.4203` (measured).
- Validation `is_ai` F1: Round 1 `0.9630` -> Round 2 `0.9632` (`delta = +0.0002`, measured).
- Validation `is_ai` Brier score: Round 1 `0.0215` -> Round 2 `0.0216` (`Brier reduction = -0.0001`, measured).
- Frozen test `is_ai` F1: Round 1 `0.9600` -> Round 2 `0.9641` (`delta = +0.0041`, measured).

## 4. Spending Jev Where It Pays: Validation Confidence-Bin Comparison

On the held-out validation split (`n = 800`), we ran `typesafe/jev-1.14` via the OpenRouter
Decisions API (`POST /api/alpha/decisions`) and compared the student vs. Jev against the
teacher panel labels within each confidence bin `|p_student - 0.5|`:

| Confidence Bin `|p - 0.5|` | Probability Band | `n` (Share) | Student Acc | Jev Acc | Student F1 | Jev F1 | Paired `Acc(Jev) - Acc(Student)` (95% CI) | Route to Jev? |
|---|---|---|---|---|---|---|---|---|
| `|p-0.5| in [0.00, 0.10)` | `[0.40, 0.50) U (0.50, 0.60]` | `3` (`0.4%`, measured) | `1.0000` (measured) | `1.0000` (measured) | `0.0000` (measured) | `0.0000` (measured) | `+0.0000` (`[+0.0000, +0.0000]`, measured) | `False` |
| `|p-0.5| in [0.10, 0.20)` | `[0.30, 0.40) U (0.60, 0.70]` | `12` (`1.5%`, measured) | `0.7500` (measured) | `0.7500` (measured) | `0.8571` (measured) | `0.8235` (measured) | `+0.0000` (`[-0.3333, +0.2937]`, measured) | `False` |
| `|p-0.5| in [0.20, 0.30)` | `[0.20, 0.30) U (0.70, 0.80]` | `10` (`1.2%`, measured) | `0.7000` (measured) | `0.9000` (measured) | `0.7273` (measured) | `0.8889` (measured) | `+0.2000` (`[+0.0000, +0.5000]`, measured) | `True` |
| `|p-0.5| in [0.30, 0.40)` | `[0.10, 0.20) U (0.80, 0.90]` | `15` (`1.9%`, measured) | `0.8667` (measured) | `0.8667` (measured) | `0.9000` (measured) | `0.9091` (measured) | `+0.0000` (`[-0.2000, +0.2000]`, measured) | `False` |
| `|p-0.5| in [0.40, 0.50)` | `[-0.00, 0.10) U (0.90, 1.00]` | `760` (`95.0%`, measured) | `0.9855` (measured) | `0.9776` (measured) | `0.9763` (measured) | `0.9630` (measured) | `-0.0079` (`[-0.0197, +0.0013]`, measured) | `False` |

- **Selected cascade thresholds**: `[t_low, t_high] = [0.2000, 0.8000]` (routed bins: `['|p-0.5| in [0.20, 0.30)']`), Jev share = `3.12%` (measured), cost per 1,000 articles = `$0.0014` (measured).

### Cascade Threshold Curve on Validation Split (`n = 800`)

| Target Jev Share | Actual Jev Share | `[t_low, t_high]` | Cascade Precision | Cascade Recall | Cascade F1 (95% CI) | Cost / 1,000 Articles |
|---|---|---|---|---|---|---|
| `0%` | `0.00%` (measured) | `[0.5000, 0.5000]` | `0.9432` (measured) | `0.9842` (measured) | `0.9632` (`[0.9488, 0.9798]`, measured) | `$0.0000` (measured) |
| `5%` | `5.00%` (measured) | `[0.1004, 0.8996]` | `0.9538` (measured) | `0.9802` (measured) | `0.9669` (`[0.9489, 0.9806]`, measured) | `$0.0023` (measured) |
| `10%` | `10.62%` (measured) | `[0.0559, 0.9441]` | `0.9569` (measured) | `0.9644` (measured) | `0.9606` (`[0.9412, 0.9747]`, measured) | `$0.0048` (measured) |
| `15%` | `19.25%` (measured) | `[0.0354, 0.9646]` | `0.9526` (measured) | `0.9526` (measured) | `0.9526` (`[0.9326, 0.9697]`, measured) | `$0.0087` (measured) |
| `20%` | `21.00%` (measured) | `[0.0217, 0.9783]` | `0.9526` (measured) | `0.9526` (measured) | `0.9526` (`[0.9326, 0.9697]`, measured) | `$0.0095` (measured) |
| `30%` | `31.00%` (measured) | `[0.0184, 0.9816]` | `0.9600` (measured) | `0.9486` (measured) | `0.9543` (`[0.9365, 0.9714]`, measured) | `$0.0140` (measured) |
| `50%` | `56.75%` (measured) | `[0.0060, 0.9940]` | `0.9526` (measured) | `0.9526` (measured) | `0.9526` (`[0.9342, 0.9697]`, measured) | `$0.0255` (measured) |
| `100%` | `100.00%` (measured) | `[0.0000, 1.0000]` | `0.9528` (measured) | `0.9565` (measured) | `0.9546` (`[0.9363, 0.9711]`, measured) | `$0.0450` (measured) |

- **Jev ledger total (`reports/jev_ledger.csv`)**: `981` calls, `$0.044284` cumulative spend (measured; caps: `JEV_RUN_CAP_USD = $1.00`, `JEV_DEV_CAP_USD = $3.00`).

## 5. 300-Row Gold Evaluation (`lake/labels/gold_sheet.csv`)

> **Note:** `lake/labels/gold_sheet.csv` (`300` blind stratified rows) is ready for the
> maintainer's 04:00–05:30 labeling window. Run
> `uv run python pipelines/taxonomy/gold_sheet.py --tally` after filling `human_is_ai`,
> `human_subtopics`, and `human_brand_safe` to replace the reference column below with
> the human gold labels. Below is the measured evaluation on the exact same 300 gold
> rows against the 3-model teacher panel consensus (`n = 300`, including all 300 Jev calls):

### `is_ai` Precision, Recall & F1 on the 300 Gold Rows (Reference: Teacher Panel Consensus (Pre-Human-Tally))

| Classifier | Precision (95% Wilson CI) | Recall (95% Wilson CI) | F1 (95% Bootstrap CI) | ROC-AUC | Brier |
|---|---|---|---|---|---|
| `teacher_1_qwen3_235b` | `0.9767` (`[0.9191, 0.9936]`, measured) | `0.9655` (`[0.9035, 0.9882]`, measured) | `0.9711` (`[0.9418, 0.9937]`, measured) | `0.9781` (measured) | `0.0167` (measured) |
| `teacher_2_deepseek_v4_pro` | `0.9770` (`[0.9200, 0.9937]`, measured) | `0.9770` (`[0.9200, 0.9937]`, measured) | `0.9770` (`[0.9512, 0.9946]`, measured) | `0.9838` (measured) | `0.0133` (measured) |
| `teacher_panel` | `1.0000` (`[0.9577, 1.0000]`, measured) | `1.0000` (`[0.9577, 1.0000]`, measured) | `1.0000` (`[1.0000, 1.0000]`, measured) | `1.0000` (measured) | `0.0000` (measured) |
| `student_alone` | `0.9432` (`[0.8738, 0.9755]`, measured) | `0.9540` (`[0.8877, 0.9820]`, measured) | `0.9486` (`[0.9166, 0.9773]`, measured) | `0.9898` (measured) | `0.0272` (measured) |
| `jev_alone` | `0.9419` (`[0.8710, 0.9749]`, measured) | `0.9310` (`[0.8576, 0.9680]`, measured) | `0.9364` (`[0.8919, 0.9688]`, measured) | `0.9957` (measured) | `0.0326` (measured) |
| `cascade` | `0.9432` (`[0.8738, 0.9755]`, measured) | `0.9540` (`[0.8877, 0.9820]`, measured) | `0.9486` (`[0.9080, 0.9768]`, measured) | `0.9903` (measured) | `0.0243` (measured) |
| `gdelt_ring1_rule` | `0.7500` (`[0.6624, 0.8210]`, measured) | `0.9655` (`[0.9035, 0.9882]`, measured) | `0.8442` (`[0.7845, 0.8922]`, measured) | `0.9170` (measured) | `0.1033` (measured) |

### Filter Recall Among Tech-Themed News (`N_acc * p_acc / (N_acc * p_acc + N_rej * p_rej)`)

- **Scope**: Tech-themed GDELT news (`f_ict OR tech_org`) in `f_control`, Aug–Oct 2026.
- **Population denominators**: `N_acc = 510` accepted by Ring-1 rule (measured), `N_rej = 7,375` rejected by Ring-1 rule (measured).
- **Labelled shares on the 300-row sheet**: `p_acc = 0.7423` (`n_acc_labeled = 97`, measured), `p_rej = 0.0160` (`n_rej_labeled = 188`, measured).
- **Estimated Filter Recall**: `0.7628` (95% bootstrap CI `[0.5958, 1.0000]`, measured).

### Multi-Label Subtopic Agreement (Mean Jaccard on Positive Rows)

- **Teacher Panel**: `1.0000` (measured)
- **Student Alone**: `0.5399` (measured)
- **Jev Alone**: `0.4728` (measured)
- **GDELT Regex v1**: `0.1134` (measured)
