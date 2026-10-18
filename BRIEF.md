# BRIEF: WS2b, the article classifier cascade (teacher labels -> local student -> Jev when in doubt)

Account: **Gemini (Antigravity)** · Branch: `feat/ws2-distill-cascade` · Worktree: `../radar-worktrees/feat-ws2-distill-cascade`
Written by the orchestrator, 2026-10-17 22:45 UTC-5. Read `AGENTS.md` (or `GEMINI.md`), then this file.

## Goal

The Curator's article decisions (is it AI? which subtopics? brand safe?) made by a **cheap local model**
when it is confident, and by **Jev** (TypeSafe, via OpenRouter) only when it is in doubt. The local
model (the "student") learns from a **teacher's** labels. Every number is checked against the
maintainer's human labels.

**Teacher = Qwen3-30B on Nebius** (`contracts/agents.yaml` model block; key `NEBIUS_API_KEY`), not Jev:
Jev's listing on OpenRouter has no `is_trainable_text` flag and no published TypeSafe terms allow
training on its outputs (checked 2026-10-17). Jev is used **only at inference, for the doubtful cases**;
its answers are logged for evaluation and never used as training labels. Make the teacher a config
value so it can be switched if TypeSafe confirms training is allowed.

## Plan reference

`docs/designs/radar-build-plan.md` ("Evaluation": filter recall via an enriched control sample,
estimator `N_acc·p_acc / (N_acc·p_acc + N_rej·p_rej)`); `contracts/taxonomy.yaml` (rings, 12 subtopics);
MASTER_PLAN §4 (Jev decisions), §6 (labels).

## Inputs (all real)

- BigQuery `radar.gkg_ai` (20.6M rows, 62.3 GB, measured): `gkg_id, dt, source, url, title, lang,
  themes, orgs, f_*` flags, `f_control` (the control sample of rejected rows). `radar.article_segment`
  (4.03M rows): `segment` (ai / it / ai_domain), `domains`, `txt`. Use the `bq` CLI through
  `pipelines/ingest/run_bq.py` (dry run, ledger) exactly as `pipelines/ingest/export_gold.py` does; the
  Python BigQuery client has no credentials on this machine.
- Nebius: `Qwen/Qwen3-30B-A3B-Instruct-2507` (chat) and `Qwen/Qwen3-Embedding-8B` (embeddings), both
  listed on the account (measured). OpenAI-compatible: `https://api.tokenfactory.nebius.com/v1`.
- OpenRouter Decisions API: `POST https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.14`,
  body `{model, state, questions}`, question types `noul` / `choice` / `score` with `instructions` and
  `criteria`. A real call on 2026-10-17 (measured): 699-950 ms, 622 input tokens, cost $0.000026, output
  free. **The account holds $6.50 of credit**: hard cap below.

## Outputs

1. `pipelines/taxonomy/sample.sql` + a sampler: a stratified sample, Aug-Oct 2026, written to
   `lake/labels/sample.parquet` (titles and URLs stay in the lake, never in git): about 1,500 ring 1,
   1,000 ring 2, 500 ring 3, 1,000 rejected (`f_control`), all languages, es/pt over-sampled to at least
   30%. Estimate the bill with a dry run first; cap 30 GiB for this job.
2. `pipelines/taxonomy/teacher.py`: Qwen labels each sampled article from title + URL path + top themes
   + orgs: `is_ai` (bool), `subtopics` (multi-label, the 12 ids), `brand_safe` (bool), `confidence`
   (0-1). JSON output validated; temperature 0; cached by `gkg_id` under `lake/labels/teacher/`.
   Report calls, tokens, failures and Nebius cost (estimate from token counts).
3. `pipelines/taxonomy/student.py`: Qwen3-Embedding-8B embeddings (cached) + the GDELT flags, then
   logistic regression per decision (scikit-learn, the `models` extra), calibrated (isotonic or Platt,
   on a held-out split). Save the model under `lake/models/curator/`.
4. `pipelines/taxonomy/cascade.py`: `classify(article) -> {decision, probability, decided_by:
   student|jev, cost_usd}`. The student decides when its calibrated probability is outside
   `[t_low, t_high]`; otherwise one Jev call (noul for is_ai and brand_safe, choice for the main
   subtopic). Thresholds chosen on the validation split for a target Jev share (report the curve).
   **Jev guard:** the $6.50 of credit must last through tonight's development, Sunday's deliverable
   and the Tuesday demo with 30X executives (nothing after that). So: a per-run cap of **$1.00** and a
   cumulative development cap of **$3.00**, both summed from `usage.cost` in `reports/jev_ledger.csv`
   (time, model, input tokens, cost, latency; no article text), keeping $3.50 for the demos. A cache
   keyed on (model, state, questions). Abort before a call that would cross either cap. Caps are
   config values (`JEV_RUN_CAP_USD`, `JEV_DEV_CAP_USD`).
5. `pipelines/taxonomy/gold_sheet.py`: a 300-row blind sheet for the maintainer (stratified like the
   sample, seeded, the teacher's and student's labels hidden) at `lake/labels/gold_sheet.csv`, with a
   `--tally` that reads the filled sheet. **Ready by 03:30**; the maintainer labels 04:00-05:30.
6. `reports/label_quality.md` (after the gold labels): precision, recall and F1 for is_ai of the
   teacher, the student alone, Jev alone (on the same 300 rows, 300 Jev calls is about $0.01) and the
   cascade, with Wilson or bootstrap intervals; the cascade's Jev share and cost per 1,000 articles;
   filter recall via the design's estimator; subtopic agreement. If the student does not match the
   teacher, say so.

## Files you may touch

`pipelines/taxonomy/**`, `reports/label_quality.md`, `reports/jev_ledger.csv`, `status/WS2.md`,
`.env.example` (no values), and the `labels` extra in `pyproject.toml`/`uv.lock` (add
`scikit-learn` there if you prefer it to the `models` extra).

## Out of scope

Agents (`agents/**`: the orchestrator wires `cascade.classify` into the Curator's tools after your PR),
contracts, scores, graphs, API/UI. No synthetic data; no Jev labels as training data.

## Acceptance

- `make check && make test` pass; unit tests run offline (recorded real responses, no network in CI).
- Real runs: sample written, teacher labels for the whole sample, student trained, cascade run on the
  validation split with its Jev share and spend, gold sheet ready. All numbers in `status/WS2.md`,
  marked measured or estimate.

## Paid or outward actions needing approval

Approved in chat for this brief: the BigQuery sample (one job, cap 30 GiB), Qwen labels for the sample
(about 4,000 calls), embeddings for the sample, Jev calls under the $1.00 per-run and $3.00 cumulative caps. Anything above those:
ask. `git push` and the PR: the orchestrator does them.

## Deadlines (UTC-5)

Sample by **23:30**; teacher labels by **01:00**; student + cascade by **02:30**; gold sheet by
**03:30**; `reports/label_quality.md` by **06:30** (after the maintainer's labels).

## Report

`status/WS2.md` (WS2b section) at each step; commit locally and stop at each deadline's end; the
orchestrator pushes.

## If blocked

`BLOCKED: <reason>` at the top of `status/WS2.md`, then stop.

## Addendum (orchestrator, 23:05 UTC-5): the best student, the best use of the dollars

The maintainer's goal: the best distilled model we can get, and the best use of the $6.50 of Jev
credit. Money is not the binding constraint (the $3.00 dev cap buys about 115,000 Jev calls at the
measured $0.000026 each); label quality is. So, replacing Outputs 2-4 where they differ:

1. **Teacher panel instead of one teacher.** Nebius lists stronger open-weight models (measured, 23:00):
   `Qwen/Qwen3.5-397B-A17B`, `Qwen/Qwen3-235B-A22B-Instruct-2507`, `deepseek-ai/DeepSeek-V4-Pro`,
   `openai/gpt-oss-120b`. **Before using any as a teacher, read its model card's licence and record it
   in `reports/label_quality.md`**; only licences that allow training on outputs (for example
   Apache-2.0, MIT) qualify. Pick two qualifying teachers from different families; each labels the
   whole sample. Where they agree, that is the training label; where they disagree, a third qualifying
   model breaks the tie, and the row is flagged. Report each teacher's agreement rate and, after the
   gold labels, each teacher's precision/recall.
2. **Pilot first (100 articles):** run every candidate on the same 100 sampled articles; record
   latency, tokens and JSON failure rate; drop any teacher with >5% invalid outputs. Nebius cost is an
   estimate from token counts (no Nebius billing API): report it.
3. **Active learning round.** After the first student, sample 2,000 more articles from the lake where
   the student is least certain (probability nearest 0.5, stratified by ring and language), label them
   with the panel, retrain. Report the validation gain of the second round.
4. **Student selection.** On Qwen3-Embedding-8B features + the GDELT flags, compare logistic regression
   and LightGBM per decision; pick on a held-out split of panel labels; calibrate; keep a frozen test
   split never used for selection. Report both, with intervals.
5. **Spending Jev where it pays.** On the validation split, compare per confidence bin of the student:
   the student, Jev and the panel's labels. Route a bin to Jev only where Jev measurably beats the student
   (paired comparison, interval reported). If Jev never beats the student, the cascade sends nothing to
   Jev, and the report says so. Run Jev on the 300 gold rows too (about $0.01).
6. Deadlines unchanged; if the panel would miss the 01:00 labels deadline, label with the pilot's best
   single teacher and say so.

Approved for this addendum: the 100-article pilot on up to five Nebius models, panel labels for about
6,000 articles in total, Jev calls inside the existing caps.
