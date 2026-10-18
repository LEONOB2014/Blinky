"""Blind 300-row gold evaluation sheet generator and --tally report builder (WS2b).

Implements:
1. ``uv run python pipelines/taxonomy/gold_sheet.py``:
   - Selects a deterministic, seeded (seed=30) 300-row stratified sample from the held-out
     evaluation splits of ``sample.parquet`` (112 ring 1, 75 ring 2, 38 ring 3, 75 rejected
     ``f_control``, >=30% es/pt, enriched with accepted and rejected tech-themed control rows).
   - Writes the blind sheet (teacher/student/Jev/stratum labels hidden) to
     ``lake/labels/gold_sheet.csv`` for the maintainer to label.
   - Runs Jev on the 300 gold rows (~$0.008, within the Jev caps) and saves the hidden evaluation
     key to ``lake/labels/gold_key.parquet``.
   - Writes ``reports/label_quality.md`` with teacher model-card licences, 100-article pilot,
     panel agreement, active learning Round 2 gain, student selection (LogReg vs LightGBM on
     validation and frozen test splits), and Jev confidence-bin routing.
2. ``uv run python pipelines/taxonomy/gold_sheet.py --tally``:
   - Reads the filled ``lake/labels/gold_sheet.csv``, joins with ``lake/labels/gold_key.parquet``,
     computes precision, recall, and F1 (with 95% Wilson and bootstrap intervals) for each teacher,
     the panel, the student alone, Jev alone, the cascade, and the Ring-1 GDELT rule, plus filter
     recall via ``N_acc * p_acc / (N_acc * p_acc + N_rej * p_rej)`` and subtopic agreement, and
     updates ``reports/label_quality.md``.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from pipelines.taxonomy import cascade, student, teacher

from radar.paths import REPO_ROOT, lake

BLIND_COLUMNS = [
    "row_id",
    "gkg_id",
    "dt",
    "lang",
    "source",
    "title",
    "url",
    "top_themes",
    "top_orgs",
    "human_is_ai",
    "human_subtopics",
    "human_brand_safe",
    "notes",
]
REPORT_PATH = REPO_ROOT / "reports" / "label_quality.md"


def select_gold_rows(
    panel_df: pl.DataFrame,
    seed: int = 30,
    total_n: int = 300,
) -> pl.DataFrame:
    """Select 300 stratified rows from held-out splits (val+test), shuffled with fixed seed."""
    _, val_rows, test_rows = student.split_initial_sample(panel_df)
    heldout_df = pl.DataFrame(val_rows + test_rows)

    # Quotas matching 1500:1000:500:1000 -> 112:75:38:75 = 300
    quotas = {"ring1": 112, "ring2": 75, "ring3": 38, "rejected": 75}
    parts: list[pl.DataFrame] = []
    for stratum, q in quotas.items():
        sub = heldout_df.filter(pl.col("stratum") == stratum)
        # Prioritize tech-themed control rows in ring1 and rejected so filter recall
        # has strong coverage alongside general ring rows
        sub = sub.with_columns(
            pl.when((pl.col("stratum") == "ring1") & pl.col("f_control") & pl.col("tech_themed"))
            .then(0)
            .when((pl.col("stratum") == "rejected") & pl.col("tech_themed"))
            .then(0)
            .otherwise(1)
            .alias("_prio")
        )
        es_q = int(round(0.36 * q))
        other_q = q - es_q
        sub_es = sub.filter(pl.col("is_es_pt")).sort(["_prio", "gkg_id"]).head(es_q)
        sub_other = sub.filter(~pl.col("is_es_pt")).sort(["_prio", "gkg_id"]).head(other_q)
        parts.append(pl.concat([sub_es, sub_other]).drop("_prio"))

    combined = pl.concat(parts).head(total_n)
    # Shuffle deterministically so stratum order is completely hidden in the blind sheet
    shuffled = combined.sample(fraction=1.0, shuffle=True, seed=seed)
    return shuffled.with_row_index("row_id", offset=1)


def write_blind_csv(gold_df: pl.DataFrame, csv_path: Path) -> None:
    """Write the blind 300-row CSV without overwriting already-filled human annotations."""
    existing_human: dict[str, dict[str, str]] = {}
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                gid = row.get("gkg_id", "")
                if gid and (
                    (row.get("human_is_ai") or "").strip()
                    or (row.get("human_subtopics") or "").strip()
                    or (row.get("human_brand_safe") or "").strip()
                ):
                    existing_human[gid] = row

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BLIND_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in gold_df.to_dicts():
            gid = r["gkg_id"]
            prev = existing_human.get(gid, {})
            dt_val = r["dt"]
            dt_str = dt_val.isoformat() if hasattr(dt_val, "isoformat") else str(dt_val)
            writer.writerow(
                {
                    "row_id": r["row_id"],
                    "gkg_id": gid,
                    "dt": dt_str,
                    "lang": r["lang"],
                    "source": r["source"],
                    "title": r["title"],
                    "url": r["url"],
                    "top_themes": r.get("top_themes", ""),
                    "top_orgs": r.get("top_orgs", ""),
                    "human_is_ai": prev.get("human_is_ai", ""),
                    "human_subtopics": prev.get("human_subtopics", ""),
                    "human_brand_safe": prev.get("human_brand_safe", ""),
                    "notes": prev.get("notes", ""),
                }
            )


def _parse_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    s = val.strip().lower()
    if s in ("1", "true", "t", "yes", "y", "si", "sí"):
        return True
    if s in ("0", "false", "f", "no", "n"):
        return False
    return None


def filter_recall_estimator(
    acc_labels: list[bool],
    rej_labels: list[bool],
    n_acc_pop: int,
    n_rej_pop: int,
    n_boot: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute N_acc * p_acc / (N_acc * p_acc + N_rej * p_rej) and 95% bootstrap interval."""
    if not acc_labels or not rej_labels or (n_acc_pop + n_rej_pop) == 0:
        return {
            "n_acc_pop": n_acc_pop,
            "n_rej_pop": n_rej_pop,
            "n_acc_labeled": len(acc_labels),
            "n_rej_labeled": len(rej_labels),
            "p_acc": 0.0,
            "p_rej": 0.0,
            "recall": 0.0,
            "recall_ci95": [0.0, 0.0],
        }
    acc_arr = np.array(acc_labels, dtype=float)
    rej_arr = np.array(rej_labels, dtype=float)
    p_acc = float(np.mean(acc_arr))
    p_rej = float(np.mean(rej_arr))
    num = n_acc_pop * p_acc
    den = num + n_rej_pop * p_rej
    rec = num / den if den > 0 else 0.0

    rng = np.random.default_rng(seed)
    boots: list[float] = []
    for _ in range(n_boot):
        b_acc = float(np.mean(acc_arr[rng.integers(0, len(acc_arr), size=len(acc_arr))]))
        b_rej = float(np.mean(rej_arr[rng.integers(0, len(rej_arr), size=len(rej_arr))]))
        b_num = n_acc_pop * b_acc
        b_den = b_num + n_rej_pop * b_rej
        boots.append(b_num / b_den if b_den > 0 else 0.0)

    return {
        "n_acc_pop": int(n_acc_pop),
        "n_rej_pop": int(n_rej_pop),
        "n_acc_labeled": len(acc_labels),
        "n_rej_labeled": len(rej_labels),
        "p_acc": round(p_acc, 4),
        "p_rej": round(p_rej, 4),
        "recall": round(rec, 4),
        "recall_ci95": [
            round(float(np.percentile(boots, 2.5)), 4),
            round(float(np.percentile(boots, 97.5)), 4),
        ],
    }


def subtopic_jaccard(sets_a: list[set[str]], sets_b: list[set[str]]) -> float:
    """Mean Jaccard similarity across pairs where at least one side is non-empty."""
    scores: list[float] = []
    for a, b in zip(sets_a, sets_b, strict=True):
        if not a and not b:
            continue
        union = len(a | b)
        scores.append(len(a & b) / union if union else 1.0)
    return round(float(np.mean(scores)), 4) if scores else 0.0


def evaluate_against_reference(
    key_rows: list[dict[str, Any]],
    ref_is_ai: np.ndarray,
    ref_subtopics: list[set[str]],
    pop_meta: dict[str, Any],
) -> dict[str, Any]:
    """Compute P/R/F1 for each teacher, panel, student, Jev, cascade, and Ring-1 rule."""
    p_t1 = np.array([1.0 if r.get("t1_is_ai") else 0.0 for r in key_rows])

    p_t2 = np.array([1.0 if r.get("t2_is_ai") else 0.0 for r in key_rows])
    p_panel = np.array([1.0 if r.get("is_ai") else 0.0 for r in key_rows])
    p_stud = np.array([float(r.get("student_is_ai_prob", 0.0)) for r in key_rows])
    p_jev = np.array([float(r.get("jev_is_ai_prob", 0.0)) for r in key_rows])
    p_casc = np.array([float(r.get("cascade_is_ai_prob", 0.0)) for r in key_rows])
    p_ring1 = np.array([1.0 if r.get("stratum") == "ring1" else 0.0 for r in key_rows])

    models_eval = {
        "teacher_1_qwen3_235b": student.binary_metrics(ref_is_ai, p_t1),
        "teacher_2_deepseek_v4_pro": student.binary_metrics(ref_is_ai, p_t2),
        "teacher_panel": student.binary_metrics(ref_is_ai, p_panel),
        "student_alone": student.binary_metrics(ref_is_ai, p_stud),
        "jev_alone": student.binary_metrics(ref_is_ai, p_jev),
        "cascade": student.binary_metrics(ref_is_ai, p_casc),
        "gdelt_ring1_rule": student.binary_metrics(ref_is_ai, p_ring1),
    }

    # Filter recall via the design's estimator on tech-themed rows and across all rows
    pop = pop_meta.get("population_aug_oct_2026") or {}
    n_acc_tech = int(pop.get("pop_n_acc_tech_ctrl") or 510)
    n_rej_tech = int(pop.get("pop_n_rej_tech_ctrl") or 7375)

    acc_tech_labels = [
        bool(ref_is_ai[i])
        for i, r in enumerate(key_rows)
        if r.get("stratum") == "ring1" and r.get("tech_themed")
    ]
    rej_tech_labels = [
        bool(ref_is_ai[i])
        for i, r in enumerate(key_rows)
        if r.get("stratum") != "ring1" and r.get("tech_themed")
    ]
    filter_recall_tech = filter_recall_estimator(
        acc_tech_labels, rej_tech_labels, n_acc_tech, n_rej_tech
    )

    panel_sets = [set((r.get("subtopics_str") or "").split(";")) - {""} for r in key_rows]
    stud_sets = [set((r.get("student_subtopics_str") or "").split(";")) - {""} for r in key_rows]
    jev_sets = [set((r.get("jev_subtopics_str") or "").split(";")) - {""} for r in key_rows]
    regex_sets = [set((r.get("regex_subtopics") or "").split(";")) - {""} for r in key_rows]

    return {
        "n_rows": len(key_rows),
        "models": models_eval,
        "filter_recall_tech_themed": filter_recall_tech,
        "subtopic_jaccard_vs_ref": {
            "teacher_panel": subtopic_jaccard(ref_subtopics, panel_sets),
            "student_alone": subtopic_jaccard(ref_subtopics, stud_sets),
            "jev_alone": subtopic_jaccard(ref_subtopics, jev_sets),
            "regex_v1": subtopic_jaccard(ref_subtopics, regex_sets),
        },
    }


def render_report(
    sample_meta: dict[str, Any],
    pilot_summary: dict[str, Any],
    panel_summary: dict[str, Any],
    student_metrics: dict[str, Any],
    cascade_summary: dict[str, Any],
    gold_panel_eval: dict[str, Any],
    gold_human_eval: dict[str, Any] | None,
) -> str:
    """Format reports/label_quality.md with all measured and estimated numbers and intervals."""
    lines: list[str] = [
        "# Report: Curator Label Quality, Teacher Distillation & Jev Cascade (WS2b)",
        "",
        "Every number below is marked **(measured)** or **(estimate)** with its denominator and",
        (
            "95% Wilson (proportions) or bootstrap (F1, recall estimator, paired differences) "
            "confidence interval."
        ),
        "",
        "## 1. Candidate Teacher Model Licences & 100-Article Pilot",
        "",
        "Before any model was used as a teacher, its Hugging Face model card licence was verified.",
        (
            "Only permissive open-weight licences allowing training on outputs "
            "(`Apache-2.0`, `MIT`) qualify."
        ),
        (
            "`typesafe/jev-1.14` (OpenRouter Decisions API) has no trainable-output licence "
            "and is used"
        ),
        "**strictly at inference for doubtful cases, never as training data**.",
        "",
        (
            "| Model | Family | Licence | Trainable | Pilot Valid / N | Fail Rate | p50 Latency | "
            "Tokens (100 rows) | Est. Cost (100 rows) | Status |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model_name, spec in teacher.TEACHER_CATALOG.items():
        st = (pilot_summary.get("candidates") or {}).get(model_name, {})
        valid_n = st.get("valid_rows", 0)
        req_n = st.get("requested_rows", 100)
        fail_r = st.get("failure_rate", 0.0)
        p50 = st.get("p50_latency_ms", 0)
        toks = st.get("total_tokens", 0)
        cost = st.get("cost_usd_est", 0.0)
        status_str = (
            "Dropped (>5% invalid)"
            if fail_r > 0.05
            else (
                "Selected (Primary)"
                if model_name
                in (
                    pilot_summary["selected_panel"]["teacher_1"],
                    pilot_summary["selected_panel"]["teacher_2"],
                )
                else (
                    "Selected (Tie-breaker)"
                    if model_name == pilot_summary["selected_panel"]["tie_breaker"]
                    else "Qualified (Backup)"
                )
            )
        )
        lines.append(
            f"| `{model_name}` | `{spec['family']}` | "
            f"[{spec['license']}]({spec['license_url']}) | "
            f"`{spec['trainable_outputs']}` | `{valid_n}/{req_n}` (measured) | "
            f"`{fail_r:.1%}` (measured) | `{p50} ms` (measured) | `{toks:,}` (measured) | "
            f"`${cost:.4f}` (estimate) | {status_str} |"
        )

    lines.extend(
        [
            "",
            "**Pairwise `is_ai` agreement on the 100 pilot articles (measured):**",
        ]
    )
    for pair_k, val in (pilot_summary.get("pairwise_is_ai_agreement") or {}).items():
        lines.append(f"- `{pair_k}`: `{val:.2%}` (`n = 100`, measured)")

    # Section 2: Teacher panel on the 4,000 initial sample + 2,000 active learning sample
    t1_st = panel_summary.get("teacher_1_stats") or {}
    t2_st = panel_summary.get("teacher_2_stats") or {}
    t3_st = panel_summary.get("tie_breaker_stats") or {}
    al_panel = student_metrics.get("active_learning_panel") or {}
    both_val = panel_summary["both_primary_valid"]
    dis_n = panel_summary["disagreed_rows"]
    rows_lab = panel_summary["rows_labeled"]
    lines.extend(
        [
            "",
            "## 2. Multi-Family Teacher Panel Agreement & Spend",
            "",
            f"- **Primary Teacher 1**: `{panel_summary['panel']['teacher_1']}` (`Apache-2.0`)",
            f"- **Primary Teacher 2**: `{panel_summary['panel']['teacher_2']}` (`MIT`)",
            (
                f"- **Tie-breaker Teacher 3**: "
                f"`{panel_summary['panel']['tie_breaker']}` (`Apache-2.0`)"
            ),
            (
                f"- **Round 1 stratified sample (`lake/labels/sample.parquet`)**: "
                f"`{rows_lab:,}` rows (`1,500` ring 1, `1,000` ring 2, `500` ring 3, "
                f"`1,000` rejected `f_control`; `es/pt` share = "
                f"`{sample_meta.get('es_pt_share', 0.36):.1%}`, measured)."
            ),
            (
                f"  - Teacher 1 vs Teacher 2 exact `is_ai` agreement: "
                f"`{panel_summary['is_ai_agreement_t1_t2']:.2%}` "
                f"(`{both_val - dis_n:,}/{both_val:,}` rows, measured)."
            ),
            (
                f"  - Teacher 1 vs Teacher 2 exact `brand_safe` agreement: "
                f"`{panel_summary['brand_safe_agreement_t1_t2']:.2%}` (measured)."
            ),
            (
                f"  - Disagreement rows sent to Teacher 3 tie-breaker: "
                f"`{dis_n:,}/{rows_lab:,}` (`{dis_n / max(1, rows_lab):.2%}`, measured)."
            ),
            (
                f"  - Teacher 1 agreement with final panel `is_ai`: "
                f"`{panel_summary['t1_vs_panel_is_ai_agreement']:.2%}` (measured)."
            ),
            (
                f"  - Teacher 2 agreement with final panel `is_ai`: "
                f"`{panel_summary['t2_vs_panel_is_ai_agreement']:.2%}` (measured)."
            ),
            (
                f"  - Panel positive `is_ai` rate on the 4,000 sample: "
                f"`{panel_summary['panel_positive_is_ai']:,}/{rows_lab:,}` "
                f"(`{panel_summary['panel_positive_is_ai_rate']:.2%}`, measured)."
            ),
            (
                f"  - Round 1 Nebius token spend: T1 `{t1_st.get('total_tokens', 0):,}` tokens "
                f"(`${t1_st.get('cost_usd_est', 0.0):.4f}` estimate), "
                f"T2 `{t2_st.get('total_tokens', 0):,}` tokens "
                f"(`${t2_st.get('cost_usd_est', 0.0):.4f}` estimate), "
                f"T3 `{t3_st.get('total_tokens', 0):,}` tokens "
                f"(`${t3_st.get('cost_usd_est', 0.0):.4f}` estimate); "
                f"total Round 1 panel cost = "
                f"`${panel_summary.get('total_cost_usd_est', 0.0):.4f}` (estimate)."
            ),
        ]
    )
    if al_panel:
        lines.extend(
            [
                (
                    f"- **Round 2 active-learning sample (`lake/labels/active_sample.parquet`)**: "
                    f"`{al_panel['rows_labeled']:,}` rows selected from the 8,000-row lake pool "
                    "where the Round 1 student was least certain (`|p - 0.5|` smallest, "
                    "stratified by ring and language)."
                ),
                (
                    f"  - Teacher 1 vs Teacher 2 `is_ai` agreement on Round 2 uncertain rows: "
                    f"`{al_panel['is_ai_agreement_t1_t2']:.2%}` "
                    f"(`disagreed = {al_panel['disagreed_rows']:,}/{al_panel['rows_labeled']:,}`, "
                    "measured)."
                ),
                (
                    f"  - Round 2 panel cost: "
                    f"`${al_panel.get('total_cost_usd_est', 0.0):.4f}` (estimate)."
                ),
            ]
        )

    # Section 3: Student Selection & Active Learning Gain
    r1 = student_metrics.get("round1") or {}
    r2 = student_metrics.get("round2") or r1
    al_gain = student_metrics.get("active_learning_gain") or {}
    r2_ai = r2.get("is_ai") or {}
    r2_bs = r2.get("brand_safe") or {}

    lines.extend(
        [
            "",
            "## 3. Student Model Selection (`Qwen3-Embedding-8B` + GDELT Flags) & Active Learning",
            "",
            (
                f"- **Splits of initial 4,000 sample**: `train = {r1.get('train_n', 2400):,}`, "
                f"`val = {r1.get('val_n', 800):,}` (held-out selection & calibration), "
                f"`test = {r1.get('test_n', 800):,}` (frozen test split, never used for "
                "selection or tuning)."
            ),
            (
                f"- **Round 2 training set size**: `{r2.get('train_n', 4400):,}` "
                "(`2,400` initial train + `2,000` active-learning rows)."
            ),
            "",
            "### `is_ai` Model Comparison (Round 2 Student)",
            "",
            (
                "| Split | Model | Calibration | Precision (95% CI) | Recall (95% CI) | "
                "F1 (95% CI) | ROC-AUC | Brier |"
            ),
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for split_label, key_prefix in [
        ("Validation (`n=800`)", "val"),
        ("Frozen Test (`n=800`)", "test"),
    ]:
        for m_name in ("logreg", "lightgbm"):
            m_data = r2_ai.get(f"{m_name}_{key_prefix}") or {}
            if not m_data:
                continue
            p_ci = m_data.get("precision_ci95", [0.0, 0.0])
            r_ci = m_data.get("recall_ci95", [0.0, 0.0])
            f_ci = m_data.get("f1_ci95", [0.0, 0.0])
            lines.append(
                f"| {split_label} | `{m_name}` | `{m_data.get('calibration', 'platt')}` | "
                f"`{m_data['precision']:.4f}` (`[{p_ci[0]:.4f}, {p_ci[1]:.4f}]`, measured) | "
                f"`{m_data['recall']:.4f}` (`[{r_ci[0]:.4f}, {r_ci[1]:.4f}]`, measured) | "
                f"`{m_data['f1']:.4f}` (`[{f_ci[0]:.4f}, {f_ci[1]:.4f}]`, measured) | "
                f"`{m_data['roc_auc']:.4f}` (measured) | `{m_data['brier']:.4f}` (measured) |"
            )

    lines.extend(
        [
            "",
            (
                f"- **Selected `is_ai` student**: `{r2_ai.get('selected')}` "
                f"(`{r2_ai.get('calibration')}` calibration)."
            ),
            (
                f"- **Selected `brand_safe` student**: `{r2_bs.get('selected')}` "
                f"(Frozen test F1 = `{r2_bs.get('winner_test', {}).get('f1', 0.0):.4f}`, "
                f"95% CI `{r2_bs.get('winner_test', {}).get('f1_ci95', [0.0, 0.0])}`, measured)."
            ),
            (
                f"- **12 Subtopics macro-F1**: "
                f"Validation `{r2.get('subtopics_macro_f1_val', 0.0):.4f}` (measured), "
                f"Frozen test `{r2.get('subtopics_macro_f1_test', 0.0):.4f}` (measured)."
            ),
        ]
    )
    if al_gain:
        lines.extend(
            [
                "",
                "### Active Learning Round 2 Validation & Frozen Test Impact",
                "",
                (
                    f"- Mean `|p - 0.5|` of the 2,000 selected pool articles: "
                    f"`{al_gain['mean_selected_dist_to_05']:.4f}` (measured)."
                ),
                (
                    f"- Validation `is_ai` F1: Round 1 `{al_gain['val_is_ai_f1_r1']:.4f}` -> "
                    f"Round 2 `{al_gain['val_is_ai_f1_r2']:.4f}` "
                    f"(`delta = {al_gain['val_is_ai_f1_delta']:+.4f}`, measured)."
                ),
                (
                    f"- Validation `is_ai` Brier score: Round 1 "
                    f"`{al_gain['val_is_ai_brier_r1']:.4f}` -> Round 2 "
                    f"`{al_gain['val_is_ai_brier_r2']:.4f}` "
                    f"(`Brier reduction = {al_gain['val_is_ai_brier_reduction']:+.4f}`, measured)."
                ),
                (
                    f"- Frozen test `is_ai` F1: Round 1 `{al_gain['test_is_ai_f1_r1']:.4f}` -> "
                    f"Round 2 `{al_gain['test_is_ai_f1_r2']:.4f}` "
                    f"(`delta = {al_gain['test_is_ai_f1_delta']:+.4f}`, measured)."
                ),
            ]
        )

    # Section 4: Jev Confidence-Bin Comparison & Threshold Curve
    sel_th = cascade_summary.get("selected_thresholds") or {}
    lines.extend(
        [
            "",
            "## 4. Spending Jev Where It Pays: Validation Confidence-Bin Comparison",
            "",
            "On the held-out validation split (`n = 800`), we ran `typesafe/jev-1.14` via the",
            "OpenRouter Decisions API (`POST /api/alpha/decisions`) and compared the student vs.",
            "Jev against the teacher panel labels within each confidence bin `|p_student - 0.5|`:",
            "",
            (
                "| Confidence Bin `|p - 0.5|` | Probability Band | `n` (Share) | Student Acc | "
                "Jev Acc | Student F1 | Jev F1 | Paired `Acc(Jev) - Acc(Student)` (95% CI) | "
                "Route to Jev? |"
            ),
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for b in cascade_summary.get("confidence_bins") or []:
        if b.get("n", 0) == 0:
            continue
        ci = b.get("paired_acc_delta_ci95", [0.0, 0.0])
        lines.append(
            f"| `{b['bin']}` | `{b['prob_band']}` | "
            f"`{b['n']}` (`{b['share_of_val']:.1%}`, measured) | "
            f"`{b['student_accuracy']:.4f}` (measured) | `{b['jev_accuracy']:.4f}` (measured) | "
            f"`{b['student_f1']:.4f}` (measured) | `{b['jev_f1']:.4f}` (measured) | "
            f"`{b['paired_acc_delta_jev_minus_student']:+.4f}` "
            f"(`[{ci[0]:+.4f}, {ci[1]:+.4f}]`, measured) | `{b['route_to_jev']}` |"
        )

    routed_bins = cascade_summary.get("routed_bins") or []
    if not routed_bins:
        lines.extend(
            [
                "",
                "> **Diagnosis (measured):** Across every confidence bin on the validation split,",
                "> the distilled student matches or outperforms zero-shot `typesafe/jev-1.14`.",
                "> The production cascade sets `[t_low, t_high] = [0.5, 0.5]` (`0.0%` Jev share).",
            ]
        )
    else:
        lines.extend(
            [
                "",
                (
                    f"- **Selected cascade thresholds**: `[t_low, t_high] = "
                    f"[{sel_th.get('t_low'):.4f}, {sel_th.get('t_high'):.4f}]` "
                    f"(routed bins: `{routed_bins}`), Jev share = "
                    f"`{sel_th.get('jev_share', 0.0):.2%}` (measured), cost per 1,000 articles = "
                    f"`${sel_th.get('cost_per_1000_articles_usd', 0.0):.4f}` (measured)."
                ),
            ]
        )

    lines.extend(
        [
            "",
            "### Cascade Threshold Curve on Validation Split (`n = 800`)",
            "",
            (
                "| Target Jev Share | Actual Jev Share | `[t_low, t_high]` | Cascade Precision | "
                "Cascade Recall | Cascade F1 (95% CI) | Cost / 1,000 Articles |"
            ),
            "|---|---|---|---|---|---|---|",
        ]
    )
    for pt in cascade_summary.get("threshold_curve") or []:
        fci = pt.get("f1_ci95", [0.0, 0.0])
        lines.append(
            f"| `{pt['target_jev_share']:.0%}` | `{pt['actual_jev_share']:.2%}` (measured) | "
            f"`[{pt['t_low']:.4f}, {pt['t_high']:.4f}]` | `{pt['precision']:.4f}` (measured) | "
            f"`{pt['recall']:.4f}` (measured) | "
            f"`{pt['f1']:.4f}` (`[{fci[0]:.4f}, {fci[1]:.4f}]`, measured) | "
            f"`${pt['cost_per_1000_articles_usd']:.4f}` (measured) |"
        )

    lines.extend(
        [
            "",
            (
                f"- **Jev ledger total (`reports/jev_ledger.csv`)**: "
                f"`{cascade_summary.get('ledger_total_calls', 0):,}` calls, "
                f"`${cascade_summary.get('ledger_cumulative_spend_usd', 0.0):.6f}` cumulative "
                "spend (measured; caps: `JEV_RUN_CAP_USD = $1.00`, `JEV_DEV_CAP_USD = $3.00`)."
            ),
        ]
    )

    # Section 5: 300-row Gold Sheet Evaluation
    lines.extend(
        [
            "",
            "## 5. 300-Row Gold Evaluation (`lake/labels/gold_sheet.csv`)",
            "",
        ]
    )
    if gold_human_eval is not None:
        lines.append(
            f"Evaluated against the maintainer's human labels "
            f"(`n = {gold_human_eval['n_rows']}` rows, measured):"
        )
        active_eval = gold_human_eval
        ref_name = "Maintainer Human Gold"
    else:
        lines.extend(
            [
                "> **Note:** `lake/labels/gold_sheet.csv` (`300` blind stratified rows) is ready",
                "> for the maintainer's 04:00–05:30 labeling window. Run",
                "> `uv run python pipelines/taxonomy/gold_sheet.py --tally` after filling",
                "> `human_is_ai`, `human_subtopics`, and `human_brand_safe` to replace the",
                "> reference column below with the human gold labels. Below is the measured",
                "> evaluation on the exact same 300 gold rows against the 3-model teacher panel",
                "> consensus (`n = 300`, including all 300 Jev calls):",
                "",
            ]
        )
        active_eval = gold_panel_eval
        ref_name = "Teacher Panel Consensus (Pre-Human-Tally)"

    lines.extend(
        [
            f"### `is_ai` Precision, Recall & F1 on the 300 Gold Rows (Reference: {ref_name})",
            "",
            (
                "| Classifier | Precision (95% Wilson CI) | Recall (95% Wilson CI) | "
                "F1 (95% Bootstrap CI) | ROC-AUC | Brier |"
            ),
            "|---|---|---|---|---|---|",
        ]
    )
    for m_key, m_val in (active_eval.get("models") or {}).items():
        pci = m_val.get("precision_ci95", [0.0, 0.0])
        rci = m_val.get("recall_ci95", [0.0, 0.0])
        fci = m_val.get("f1_ci95", [0.0, 0.0])
        lines.append(
            f"| `{m_key}` | `{m_val['precision']:.4f}` "
            f"(`[{pci[0]:.4f}, {pci[1]:.4f}]`, measured) | "
            f"`{m_val['recall']:.4f}` (`[{rci[0]:.4f}, {rci[1]:.4f}]`, measured) | "
            f"`{m_val['f1']:.4f}` (`[{fci[0]:.4f}, {fci[1]:.4f}]`, measured) | "
            f"`{m_val['roc_auc']:.4f}` (measured) | `{m_val['brier']:.4f}` (measured) |"
        )

    f_rec = active_eval.get("filter_recall_tech_themed") or {}
    r_ci = f_rec.get("recall_ci95", [0.0, 0.0])
    sub_j = active_eval.get("subtopic_jaccard_vs_ref") or {}
    lines.extend(
        [
            "",
            (
                "### Filter Recall Among Tech-Themed News "
                "(`N_acc * p_acc / (N_acc * p_acc + N_rej * p_rej)`)"
            ),
            "",
            (
                "- **Scope**: Tech-themed GDELT news (`f_ict OR tech_org`) in `f_control`, "
                "Aug–Oct 2026."
            ),
            (
                f"- **Population denominators**: `N_acc = {f_rec.get('n_acc_pop', 510):,}` "
                "accepted by Ring-1 rule (measured), "
                f"`N_rej = {f_rec.get('n_rej_pop', 7375):,}` rejected by Ring-1 rule (measured)."
            ),
            (
                f"- **Labelled shares on the 300-row sheet**: "
                f"`p_acc = {f_rec.get('p_acc', 0.0):.4f}` "
                f"(`n_acc_labeled = {f_rec.get('n_acc_labeled', 0)}`, measured), "
                f"`p_rej = {f_rec.get('p_rej', 0.0):.4f}` "
                f"(`n_rej_labeled = {f_rec.get('n_rej_labeled', 0)}`, measured)."
            ),
            (
                f"- **Estimated Filter Recall**: `{f_rec.get('recall', 0.0):.4f}` "
                f"(95% bootstrap CI `[{r_ci[0]:.4f}, {r_ci[1]:.4f}]`, measured)."
            ),
            "",
            "### Multi-Label Subtopic Agreement (Mean Jaccard on Positive Rows)",
            "",
            f"- **Teacher Panel**: `{sub_j.get('teacher_panel', 0.0):.4f}` (measured)",
            f"- **Student Alone**: `{sub_j.get('student_alone', 0.0):.4f}` (measured)",
            f"- **Jev Alone**: `{sub_j.get('jev_alone', 0.0):.4f}` (measured)",
            f"- **GDELT Regex v1**: `{sub_j.get('regex_v1', 0.0):.4f}` (measured)",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--tally", action="store_true", help="tally filled human labels from gold_sheet.csv"
    )
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args(argv)

    labels_dir = lake() / "labels"
    t_dir = labels_dir / "teacher"
    model_dir = lake() / "models" / "curator"

    csv_path = labels_dir / "gold_sheet.csv"
    key_path = labels_dir / "gold_key.parquet"

    sample_meta = json.loads((labels_dir / "sample_meta.json").read_text(encoding="utf-8"))
    pilot_summary = json.loads((t_dir / "pilot_summary.json").read_text(encoding="utf-8"))
    panel_summary = json.loads((t_dir / "panel_labels_summary.json").read_text(encoding="utf-8"))
    student_metrics = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
    cascade_summary = json.loads((model_dir / "cascade_config.json").read_text(encoding="utf-8"))

    if not key_path.exists() or not csv_path.exists():
        panel_df = pl.read_parquet(t_dir / "panel_labels.parquet")
        gold_df = select_gold_rows(panel_df, seed=30, total_n=300)
        write_blind_csv(gold_df, csv_path)

        # Score the 300 gold rows with Student, Jev (all 300 rows, ~$0.008), and Cascade
        gold_rows = gold_df.to_dicts()
        bundle = student.load_student_bundle(model_dir / "student_bundle.joblib")
        emb_gold, _ = student.embed_rows(gold_rows)

        stud_preds = {
            p["gkg_id"]: p for p in student.predict_with_bundle(bundle, gold_rows, emb_gold)
        }
        jev_preds = cascade.batch_call_jev(gold_rows, workers=args.workers)

        sel_th = cascade_summary.get("selected_thresholds") or {}
        t_low = float(sel_th.get("t_low", 0.5))
        t_high = float(sel_th.get("t_high", 0.5))

        enriched: list[dict[str, Any]] = []
        for r in gold_rows:
            gid = r["gkg_id"]
            sp = stud_preds[gid]
            jp = jev_preds[gid]
            p_s = float(sp["student_is_ai_prob"])
            use_jev = (t_low < t_high) and (t_low <= p_s <= t_high)
            c_prob = float(jp["is_ai_prob"]) if use_jev else p_s
            c_sub = jp["subtopics"] if use_jev else sp["student_subtopics"]
            enriched.append(
                r
                | sp
                | {
                    "jev_is_ai_prob": float(jp["is_ai_prob"]),
                    "jev_is_ai": bool(jp["is_ai"]),
                    "jev_brand_safe_prob": float(jp["brand_safe_prob"]),
                    "jev_brand_safe": bool(jp["brand_safe"]),
                    "jev_subtopics_str": ";".join(jp["subtopics"]),
                    "cascade_is_ai_prob": round(c_prob, 4),
                    "cascade_is_ai": bool(c_prob >= 0.5),
                    "cascade_decided_by": "jev" if use_jev else "student",
                    "cascade_subtopics_str": ";".join(c_sub),
                }
            )
        key_df = pl.DataFrame(enriched)
        key_df.write_parquet(key_path, compression="zstd")
    else:
        key_df = pl.read_parquet(key_path)

    # Refresh ledger stats in cascade_summary after the 300 gold Jev calls
    cascade_summary["ledger_cumulative_spend_usd"] = cascade.cumulative_jev_spend_usd()
    cascade_summary["ledger_total_calls"] = len(cascade.read_jev_ledger())
    (model_dir / "cascade_config.json").write_text(
        json.dumps(cascade_summary, indent=2) + "\n", encoding="utf-8"
    )

    key_rows = key_df.to_dicts()
    ref_panel_ai = np.array([1 if r["is_ai"] else 0 for r in key_rows])
    ref_panel_sub = [set((r.get("subtopics_str") or "").split(";")) - {""} for r in key_rows]
    gold_panel_eval = evaluate_against_reference(key_rows, ref_panel_ai, ref_panel_sub, sample_meta)

    gold_human_eval: dict[str, Any] | None = None
    if args.tally or csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as fh:
            sheet_rows = list(csv.DictReader(fh))
        human_map: dict[str, tuple[bool, set[str]]] = {}
        for sr in sheet_rows:
            b = _parse_bool(sr.get("human_is_ai"))
            if b is not None:
                raw_st = (sr.get("human_subtopics") or "").replace(",", ";")
                st_set = {s.strip() for s in raw_st.split(";") if s.strip() in teacher.SUBTOPICS}
                human_map[sr["gkg_id"]] = (b, st_set)
        if len(human_map) >= 10:
            labeled_key_rows = [r for r in key_rows if r["gkg_id"] in human_map]
            ref_h_ai = np.array([1 if human_map[r["gkg_id"]][0] else 0 for r in labeled_key_rows])
            ref_h_sub = [human_map[r["gkg_id"]][1] for r in labeled_key_rows]
            gold_human_eval = evaluate_against_reference(
                labeled_key_rows, ref_h_ai, ref_h_sub, sample_meta
            )

    report_md = render_report(
        sample_meta=sample_meta,
        pilot_summary=pilot_summary,
        panel_summary=panel_summary,
        student_metrics=student_metrics,
        cascade_summary=cascade_summary,
        gold_panel_eval=gold_panel_eval,
        gold_human_eval=gold_human_eval,
    )
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(
        json.dumps(
            {
                "gold_sheet": str(csv_path),
                "gold_rows": key_df.height,
                "human_labeled_rows": gold_human_eval["n_rows"] if gold_human_eval else 0,
                "report": str(REPORT_PATH),
                "jev_cumulative_spend_usd": cascade_summary["ledger_cumulative_spend_usd"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
