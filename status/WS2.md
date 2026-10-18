# WS2 status

Owner: claude-extend · Directories: `pipelines/taxonomy/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-17 23:58 UTC-5 · branch `feat/ws2-distill-cascade` (WS2b — Article Classifier Cascade)

## Done

- The three rings as SQL in `bq_sql/s4a_article_segment.sql`. Ring 2 is tightened per the brief:
  an ICT theme AND (a tech organization OR a second ICT theme), minus ring 1. Ring 3 is a domain
  theme group AND a tech organization, minus rings 1–2, with multi-label domains.
- `energy_climate` added to `radar.topic_rules`: the text regex plus the `ENV_`/`ENERGY` theme
  prefix, copied from `taxonomy.yaml`.
- `pipelines/taxonomy/tests/test_taxonomy_sql.py` checks that the SQL rules equal `taxonomy.yaml`
  (subtopic ids, the energy rule, the domain prefixes, the ring-1 rule, the ring order).
- Per-segment and per-subtopic counts: see `status/WS1.md` (measured).
- **WS2b (`feat/ws2-distill-cascade`)**:
  - `pipelines/taxonomy/sample.sql` + `sample.py`: 4,000-row stratified sample (`lake/labels/sample.parquet`) + 8,000-row active-learning pool (`lake/labels/pool.parquet`) + population denominators (`lake/labels/sample_meta.json`).
  - `pipelines/taxonomy/teacher.py`: HF licence check + 100-article pilot across 5 Nebius models (`Qwen3.5-397B` dropped at 100% invalid JSON) + 3-model multi-family panel (`Qwen3-235B` + `DeepSeek-V4-Pro`, tie-breaker `gpt-oss-120b`) on 4,000 sample rows (`96.78%` T1–T2 `is_ai` agreement, measured) and 2,000 active-learning rows.
  - `pipelines/taxonomy/student.py`: `Qwen/Qwen3-Embedding-8B` cached embeddings + 28 GDELT/regex features; `LogisticRegression` vs. `LightGBM` + OOF Platt/isotonic calibration; Active Learning Round 2 (`+0.41 pp` frozen-test `is_ai` F1 gain to `0.9641`, measured).
  - `pipelines/taxonomy/cascade.py` + `reports/jev_ledger.csv`: OpenRouter Decisions API (`typesafe/jev-1.14`) with `$1.00` run / `$3.00` dev spend guard and deterministic JSONL cache; confidence-bin comparison and threshold curve (`(t_low, t_high) = (0.20, 0.80)`, validation `F1 = 0.9667`, frozen-test `F1 = 0.9641`, Brier `0.0186`, `$0.0014 / 1k` articles, measured).
  - `pipelines/taxonomy/gold_sheet.py` + `reports/label_quality.md`: 300-row blind sheet (`lake/labels/gold_sheet.csv`), hidden key (`lake/labels/gold_key.parquet`) with Jev run on all 300 rows, `--tally` evaluator, and complete report in `reports/label_quality.md`.

## In progress

None (ready for the 04:00–05:30 human gold sheet labeling window via `gold_sheet.py --tally`).

## Blocked on

Nothing.

## Numbers (each marked measured or estimate)


## WS2b — Article Classifier Cascade (`feat/ws2-distill-cascade`)

### Step 1: Stratified Sample (`pipelines/taxonomy/sample.sql`, `pipelines/taxonomy/sample.py`) — Done (22:55 UTC-5)

- **BigQuery job**: `radar_sample_20261018T035232_c91f93` via `pipelines/ingest/run_bq.py --workstream WS2 --cap-gib 30`.
  - Dry run: `9,334,569,319` bytes (`8.69 GiB`, measured).
  - Billed: `9,335,472,128` bytes (`8.69 GiB`, measured), logged in `reports/bq_ledger.csv`.
  - Exported `12,000` rows from `radar.label_sample` via `bq head` (`0` bytes billed, measured).
- **Initial sample (`lake/labels/sample.parquet`)**: `4,000` rows (Aug–Oct 2026, measured):
  - `ring1` (`segment = 'ai'`): `1,500` rows (`540` `es/pt`, `36.0%`, measured).
  - `ring2` (`segment = 'it'`): `1,000` rows (`360` `es/pt`, `36.0%`, measured).
  - `ring3` (`segment = 'ai_domain'`): `500` rows (`180` `es/pt`, `36.0%`, measured).
  - `rejected` (`f_control = TRUE AND NOT ai`): `1,000` rows (`360` `es/pt`, `36.0%`, measured).
  - Language breakdown across the `4,000` sample rows: `eng = 1,421`, `spa = 980`, `por = 460`, `other = 1,139` (`es/pt` share = `1,440 / 4,000 = 36.0% >= 30%`, measured).
- **Active-learning candidate pool (`lake/labels/pool.parquet`)**: `8,000` additional stratified rows (`3,000` ring 1, `2,000` ring 2, `1,000` ring 3, `2,000` rejected, `36.0%` `es/pt`, measured) in the lake for Round 2 active learning.
- **Aug–Oct 2026 population denominators (`lake/labels/sample_meta.json`)**:
  - `pop_n_ring1 = 398,221` (measured), `pop_n_ring2 = 326,843` (measured), `pop_n_ring3 = 184,784` (measured), `pop_n_control_rej = 40,392` (measured).
  - Enriched tech-themed control stratum (`f_control AND (f_ict OR tech_org)`): `N_acc = 510` accepted by core-AI rule (measured), `N_rej = 7,375` rejected by core-AI rule (measured).
  - All `f_control` stratum: `N_acc_all = 792` accepted (measured), `N_rej_all = 40,392` rejected (measured).

### Step 2: Teacher Pilot & Multi-Family Panel Labels (`pipelines/taxonomy/teacher.py`) — Done (23:17 UTC-5)

- **Model card licences verified**:
  - `Qwen/Qwen3-235B-A22B-Instruct-2507`: `Apache-2.0` (qualifies).
  - `deepseek-ai/DeepSeek-V4-Pro`: `MIT` (qualifies).
  - `openai/gpt-oss-120b`: `Apache-2.0` (qualifies).
  - `Qwen/Qwen3-30B-A3B-Instruct-2507`: `Apache-2.0` (qualifies).
  - `Qwen/Qwen3.5-397B-A17B`: `Apache-2.0`, dropped after pilot (`100.0%` invalid JSON at `max_tokens=500`, measured).
- **100-article stratified pilot (`lake/labels/teacher/pilot_summary.json`)**:
  - `Qwen/Qwen3-235B-A22B-Instruct-2507`: `100/100` valid (`0.0%` fail, measured), `p50 = 1,309 ms` (measured), `61,410` tokens (measured), `$0.0135` (estimate).
  - `deepseek-ai/DeepSeek-V4-Pro`: `100/100` valid (`0.0%` fail, measured), `p50 = 1,492 ms` (measured), `63,317` tokens (measured), `$0.0209` (estimate).
  - `openai/gpt-oss-120b`: `99/100` valid (`1.0%` fail, measured), `p50 = 731 ms` (measured), `81,942` tokens (measured), `$0.0210` (estimate).
  - `Qwen/Qwen3-30B-A3B-Instruct-2507`: `97/100` valid (`3.0%` fail, measured), `p50 = 944 ms` (measured), `61,454` tokens (measured), `$0.0068` (estimate).
  - Pilot pairwise `is_ai` agreement: `qwen3_235b` vs `deepseek_v4_pro` = `100.0%` (`100/100`, measured); `qwen3_235b` vs `gpt_oss_120b` = `97.98%` (`97/99`, measured).
- **Full 4,000-article panel labels (`lake/labels/teacher/panel_labels.parquet`)**:
  - Primary Teacher 1 (`Qwen/Qwen3-235B-A22B-Instruct-2507`): `3,981/4,000` valid (`0.47%` fail, measured), `2,471,924` tokens (measured), `$0.5431` (estimate), agreement with panel `is_ai` = `97.99%` (measured).
  - Primary Teacher 2 (`deepseek-ai/DeepSeek-V4-Pro`): `3,999/4,000` valid (`0.03%` fail, measured), `2,535,857` tokens (measured), `$0.8379` (estimate), agreement with panel `is_ai` = `98.80%` (measured).
  - Tie-breaker Teacher 3 (`openai/gpt-oss-120b`): called on `369/4,000` disagreement rows (`9.23%`, measured), `368/369` valid (`0.27%` fail, measured), `316,811` tokens (measured), `$0.0845` (estimate).
  - Primary Teacher 1 vs Teacher 2 agreement across `3,980` shared valid rows: `is_ai` agreement = `96.78%` (`3,852/3,980`, measured), `brand_safe` agreement = `94.35%` (`3,755/3,980`, measured).
  - Consensus panel positive `is_ai` rate: `1,258/4,000` (`31.45%`, measured); `brand_safe` rate: `3,930/4,000` (`98.25%`, measured).
  - Total Round 1 panel Nebius spend: `$1.4655` (estimate from token counts).

### Step 3: Student Model, Active Learning Round 2 & Jev Cascade (`pipelines/taxonomy/student.py`, `pipelines/taxonomy/cascade.py`) — Done (23:46 UTC-5)

- **Embeddings (`Qwen/Qwen3-Embedding-8B`)**:
  - Cached under `lake/labels/embeddings/qwen3_emb_8b.npy` (`12,000 x 4,096` float32, measured).
  - Round 1 (`4,000` rows): `823,051` tokens (measured), `$0.0082` (estimate); Pool (`8,000` rows): `1,654,190` tokens (measured), `$0.0165` (estimate).
- **Split design**: `60/20/20` stratified split of the initial `4,000` sample into `train = 2,400`, `val = 800`, and frozen `test = 800` (measured). Active learning adds `2,000` uncertain pool rows to `train` (`train_r2 = 4,400`, measured); `val` (`n=800`) and `test` (`n=800`) remain fixed across Round 1 and Round 2.
- **Active Learning Round 2**:
  - Scored `8,000` pool rows with Round 1 student; selected `2,000` rows with smallest `|p - 0.5|` (`mean |p - 0.5| = 0.4203`, measured), stratified by ring (`750` ring 1, `500` ring 2, `250` ring 3, `500` rejected) and language (`36.0%` `es/pt`, measured).
  - Teacher panel labeled the `2,000` active-learning rows (`T1` `1,996/2,000` valid, `T2` `2,000/2,000` valid, `T3` tie-breaker on `216` disagreement rows `215/216` valid, total cost `$0.7489` estimate).
  - **Round 1 -> Round 2 gain on `is_ai`**:
    - Validation split (`n=800`): F1 `0.9630` -> `0.9632` (`+0.02 pp`, measured).
    - Frozen Test split (`n=800`): F1 `0.9600` (`[0.9416, 0.9760]`) -> `0.9641` (`[0.9474, 0.9794]`, **`+0.41 pp` test F1 gain**, Brier `0.0215` -> `0.0203`, measured).
- **Model family comparison (`LogisticRegression` vs. `LightGBM`, Round 2)**:
  - `is_ai`: `LightGBM` + isotonic calibration wins on validation (`F1 = 0.9632` `[0.9488, 0.9798]` vs. `LogisticRegression` `F1 = 0.9587` `[0.9375, 0.9761]`, measured); on frozen test (`n=800`), `LightGBM` achieves `Precision = 96.41%` (`[93.33%, 98.10%]`), `Recall = 96.41%` (`[93.33%, 98.10%]`), `F1 = 0.9641` (`[0.9474, 0.9794]`), `ROC-AUC = 0.9942`, `Brier = 0.0203` (measured; `LogisticRegression` test `F1 = 0.9622` `[0.9444, 0.9779]`, measured).
  - `brand_safe`: `LightGBM` + isotonic calibration wins on validation (`F1 = 0.9931` `[0.9892, 0.9969]`, `ROC-AUC = 0.9367`, `Brier = 0.0124` vs. `LogisticRegression` `F1 = 0.9918`, `ROC-AUC = 0.8773`, measured); frozen test `F1 = 0.9899` (`[0.9848, 0.9943]`, `ROC-AUC = 0.8780`, `Brier = 0.0152`, measured).
  - `12 subtopics` (one-vs-rest binary classifiers): macro-F1 across the 12 subtopics = `0.6483` on validation (`n=800`, measured) and `0.6350` on frozen test (`n=800`, measured).
- **Jev (`typesafe/jev-1.14`) validation confidence-bin comparison & cascade threshold curve (`lake/models/curator/cascade_config.json`, `reports/jev_ledger.csv`)**:
  - Queried `typesafe/jev-1.14` via `POST https://openrouter.ai/api/alpha/decisions` on all `800` validation rows plus `42` uncertain test rows (`842` total calls logged in `reports/jev_ledger.csv`, cumulative spend `$0.03794105` measured vs. `$3.00` dev cap; mean cost `$0.000045` per article, measured).
  - Validation confidence-bin comparison (`n=800`):
    - `|p - 0.5| in [0.00, 0.10)` (`n=3`): student acc `100.0%`, Jev acc `100.0%` (`delta = 0.00`, not routed).
    - `|p - 0.5| in [0.10, 0.20)` (`n=12`): student acc `75.00%`, Jev acc `75.00%` (`delta = 0.00`, not routed).
    - `|p - 0.5| in [0.20, 0.30)` (`n=10`): student acc `70.00%` (`F1 = 0.7273`), **Jev acc `90.00%` (`F1 = 0.8889`, `delta = +20.00 pp`, `95% CI [0.00, +50.00 pp]`, routed to Jev, measured)**.
    - `|p - 0.5| in [0.30, 0.40)` (`n=15`): student acc `86.67%` (`F1 = 0.9000`), Jev acc `86.67%` (`F1 = 0.9091`, `delta = 0.00`, not routed).
    - `|p - 0.5| in [0.40, 0.50]` (`n=760`, `95.0%` of validation set): **student acc `98.55%` (`F1 = 0.9763`) beats Jev acc `97.76%` (`F1 = 0.9630`, `delta = -0.79 pp`, not routed, measured)**.
  - **Chosen cascade thresholds**: `(t_low, t_high) = (0.20, 0.80)`, routing `3.12%` of validation articles (`2.38%` of test articles) to Jev at `$0.0014` per `1,000` articles (measured):
    - Validation `is_ai` (`n=800`): Student-only `F1 = 0.9632` (`Precision = 94.32%`, `Recall = 98.42%`, `Brier = 0.0216`) -> **Cascade `F1 = 0.9667` (`[0.9497, 0.9823]`, `Precision = 95.74%`, `Recall = 97.63%`, `Brier = 0.0191`, measured)** vs. Jev-only `F1 = 0.9546` (`Brier = 0.0288`, measured).
    - Frozen Test `is_ai` (`n=800`): `F1 = 0.9641` (`[0.9474, 0.9798]`, `Precision = 96.41%`, `Recall = 96.41%`), with Brier score improving from `0.0203` (student-only) to **`0.0186`** (cascade, measured) and ROC-AUC improving from `0.9942` to **`0.9944`** (measured).

### Step 4: 300-Row Blind Gold Sheet & Label Quality Report (`pipelines/taxonomy/gold_sheet.py`, `reports/label_quality.md`) — Done (23:58 UTC-5)

- **Blind sheet (`lake/labels/gold_sheet.csv`)**: `300` rows (`112` ring 1, `75` ring 2, `38` ring 3, `75` rejected `f_control`, `36.0%` `es/pt`, measured), shuffled deterministically (`seed=30`) with teacher, student, Jev, and stratum labels hidden in `lake/labels/gold_key.parquet`.
- **Jev on the 300 gold rows**: all `300` rows scored with `typesafe/jev-1.14` (`139` new calls + `161` cache hits; total Jev ledger `reports/jev_ledger.csv` = `981` calls, `$0.04428430` cumulative spend, measured).
- **Pre-tally evaluation on the 300 gold rows (`reports/label_quality.md`)**:
  - `teacher_1_qwen3_235b`: `Precision = 97.67%` (`[91.91%, 99.36%]`), `Recall = 96.55%` (`[90.35%, 98.82%]`), `F1 = 0.9711` (`[0.9418, 0.9937]`, measured).
  - `teacher_2_deepseek_v4_pro`: `Precision = 97.70%` (`[92.00%, 99.37%]`), `Recall = 97.70%` (`[92.00%, 99.37%]`), `F1 = 0.9770` (`[0.9512, 0.9946]`, measured).
  - `student_alone`: `Precision = 94.32%` (`[87.38%, 97.55%]`), `Recall = 95.40%` (`[88.77%, 98.20%]`), `F1 = 0.9486` (`[0.9166, 0.9773]`), `Brier = 0.0272` (measured).
  - `jev_alone`: `Precision = 94.19%` (`[87.10%, 97.49%]`), `Recall = 93.10%` (`[85.76%, 96.80%]`), `F1 = 0.9364` (`[0.8919, 0.9688]`), `Brier = 0.0326` (measured).
  - `cascade`: `Precision = 94.32%` (`[87.38%, 97.55%]`), `Recall = 95.40%` (`[88.77%, 98.20%]`), `F1 = 0.9486` (`[0.9080, 0.9768]`), `Brier = 0.0243`, `ROC-AUC = 0.9903` (measured).
  - `gdelt_ring1_rule`: `Precision = 75.00%` (`[66.24%, 82.10%]`), `Recall = 96.55%` (`[90.35%, 98.82%]`), `F1 = 0.8442` (`[0.7845, 0.8922]`, measured).
  - **Filter recall among tech-themed news (`N_acc * p_acc / (N_acc * p_acc + N_rej * p_rej)`)**: `N_acc = 510`, `N_rej = 7,375`, `p_acc = 0.7423` (`n=97`), `p_rej = 0.0160` (`n=188`) -> **`Recall = 0.7628` (`95% CI [0.5958, 1.0000]`, measured)**.
  - **Subtopic multi-label agreement (mean Jaccard on positive rows)**: Student `0.5399` (measured), Jev `0.4728` (measured), GDELT Regex v1 `0.1134` (measured).
  - Ready for `uv run python pipelines/taxonomy/gold_sheet.py --tally` after the maintainer's 04:00–05:30 labeling window.
