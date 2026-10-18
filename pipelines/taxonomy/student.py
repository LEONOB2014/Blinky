"""Student classifier training, embedding cache, model selection, and active learning (WS2b).

Implements:
1. Batched ``Qwen/Qwen3-Embedding-8B`` embeddings via Nebius Token Factory, cached by ``gkg_id``
   under ``lake/labels/embeddings/``.
2. Comparison of ``LogisticRegression`` and ``LightGBM`` per decision (``is_ai``, ``brand_safe``,
   and the 12 ``subtopics``) on ``Qwen3-Embedding-8B`` + 28 GDELT/regex features.
3. Out-of-fold Platt (sigmoid) and isotonic calibration, selected on the held-out validation split,
   with a frozen test split never used for selection or threshold tuning.
4. Active learning Round 2: scores the 8,000-row lake pool with Round 1 student, picks the 2,000
   least certain articles (``|p - 0.5|`` smallest, stratified by ring and language), labels them
   with the teacher panel, retrains Round 2, and reports the validation and test gain with 95%
   confidence intervals.
"""

import argparse
import concurrent.futures
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import joblib
import numpy as np
import polars as pl
from lightgbm import LGBMClassifier
from pipelines.taxonomy import teacher
from sklearn.decomposition import TruncatedSVD
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler, normalize

from radar.paths import lake

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-8B"
EMBEDDING_USD_PER_1M = 0.01  # Nebius Token Factory embedding price (estimate)

FLAG_COLS = [
    "f_url",
    "f_url_short",
    "f_title_strong",
    "f_title_weak",
    "f_org",
    "f_latam_loc",
    "f_latam_src",
    "f_ict",
    "f_control",
    "tech_org",
    "tech_themed",
    "is_es_pt",
]
SUBTOPIC_LIST = sorted(teacher.SUBTOPICS)


def format_embedding_text(row: dict[str, Any]) -> str:
    """Build text representation of an article for Qwen3-Embedding-8B."""
    title = (row.get("title") or "").strip()[:300]
    url_path = teacher.clean_url_path(row.get("url") or "")
    themes = (row.get("top_themes") or "").strip()[:280]
    orgs = (row.get("top_orgs") or "").strip()[:180]
    lang = (row.get("lang") or "eng").strip()
    return f"[{lang}] {title} | {url_path} | themes: {themes} | orgs: {orgs}"


def load_embedding_cache(emb_dir: Path) -> tuple[dict[str, int], np.ndarray]:
    """Load cached gkg_id -> row index and float32 embedding matrix."""
    idx_path = emb_dir / "qwen3_emb_8b_index.json"
    mat_path = emb_dir / "qwen3_emb_8b.npy"
    if not idx_path.exists() or not mat_path.exists():
        return {}, np.empty((0, 0), dtype=np.float32)
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    matrix = np.load(mat_path)
    return index, matrix


def save_embedding_cache(emb_dir: Path, index: dict[str, int], matrix: np.ndarray) -> None:
    emb_dir.mkdir(parents=True, exist_ok=True)
    idx_tmp = emb_dir / "qwen3_emb_8b_index.json.tmp"
    mat_tmp = emb_dir / "qwen3_emb_8b.tmp.npy"
    idx_tmp.write_text(json.dumps(index), encoding="utf-8")
    np.save(mat_tmp, matrix.astype(np.float32))
    idx_tmp.replace(emb_dir / "qwen3_emb_8b_index.json")
    mat_tmp.replace(emb_dir / "qwen3_emb_8b.npy")


def _embed_batch(
    client: httpx.Client, batch: list[dict[str, Any]], model: str = EMBEDDING_MODEL
) -> tuple[list[str], np.ndarray, int, int]:
    texts = [format_embedding_text(r) for r in batch]
    gids = [r["gkg_id"] for r in batch]
    t0 = time.perf_counter()
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            resp = client.post("/embeddings", json={"model": model, "input": texts})
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(0.8 * (2**attempt))
                continue
            resp.raise_for_status()
            latency_ms = int((time.perf_counter() - t0) * 1000)
            data = resp.json()
            items = sorted(data["data"], key=lambda x: x["index"])
            vecs = np.array([it["embedding"] for it in items], dtype=np.float32)
            tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
            return gids, vecs, tokens, latency_ms
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"Embedding batch failed after retries: {last_exc}")


def embed_rows(
    rows: list[dict[str, Any]],
    emb_dir: Path | None = None,
    batch_size: int = 64,
    workers: int = 8,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Return (N, D) float32 embeddings for rows, fetching missing gkg_ids from Nebius."""
    e_dir = emb_dir or (lake() / "labels" / "embeddings")
    index, matrix = load_embedding_cache(e_dir)
    todo = [r for r in rows if r["gkg_id"] not in index]

    total_tokens = 0
    batches_called = 0
    if todo:
        key = teacher.nebius_api_key()
        batches = [todo[i : i + batch_size] for i in range(0, len(todo), batch_size)]
        batches_called = len(batches)
        new_gids: list[str] = []
        new_vecs: list[np.ndarray] = []
        with (
            httpx.Client(
                base_url=teacher.NEBIUS_BASE_URL,
                headers={"Authorization": f"Bearer {key}"},
                timeout=60.0,
            ) as client,
            concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool,
        ):
            futs = [pool.submit(_embed_batch, client, b) for b in batches]
            for fut in concurrent.futures.as_completed(futs):
                gids, vecs, toks, _ = fut.result()
                new_gids.extend(gids)
                new_vecs.append(vecs)
                total_tokens += toks

        stacked = np.vstack(new_vecs)
        if matrix.size == 0:
            matrix = stacked
            index = {gid: i for i, gid in enumerate(new_gids)}
        else:
            offset = matrix.shape[0]
            matrix = np.vstack([matrix, stacked])
            for i, gid in enumerate(new_gids):
                index[gid] = offset + i
        save_embedding_cache(e_dir, index, matrix)

    out_idx = [index[r["gkg_id"]] for r in rows]
    out_mat = matrix[out_idx]
    stats = {
        "model": EMBEDDING_MODEL,
        "requested_rows": len(rows),
        "new_embedded_rows": len(todo),
        "batches_called": batches_called,
        "embedding_dim": int(out_mat.shape[1]) if out_mat.ndim == 2 and out_mat.size else 0,
        "total_tokens": total_tokens,
        "cost_usd_est": round(total_tokens * EMBEDDING_USD_PER_1M / 1_000_000.0, 6),
    }
    return out_mat, stats


def extract_structured_features(rows: list[dict[str, Any]]) -> np.ndarray:
    """Extract 28 GDELT flag, tone, word_count, and regex subtopic features per row."""
    feats = np.zeros((len(rows), len(FLAG_COLS) + 4 + len(SUBTOPIC_LIST)), dtype=np.float32)
    for i, r in enumerate(rows):
        for j, col in enumerate(FLAG_COLS):
            feats[i, j] = 1.0 if r.get(col) else 0.0
        base = len(FLAG_COLS)
        feats[i, base + 0] = float(r.get("n_ict_themes") or 0.0)
        feats[i, base + 1] = float(r.get("tone") or 0.0)
        feats[i, base + 2] = float(r.get("polarity") or 0.0)
        wc = max(0.0, float(r.get("word_count") or 0.0))
        feats[i, base + 3] = math.log1p(wc)
        matched = set((r.get("regex_subtopics") or "").split(";")) - {""}
        for k, st in enumerate(SUBTOPIC_LIST):
            feats[i, base + 4 + k] = 1.0 if st in matched else 0.0
    return feats


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n."""
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)) / denom
    return round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)


def bootstrap_f1_interval(
    y_true: np.ndarray, y_pred: np.ndarray, n_boot: int = 400, seed: int = 42
) -> tuple[float, float]:
    """95% bootstrap confidence interval for binary F1."""
    if len(y_true) == 0:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    n = len(y_true)
    scores = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        scores.append(f1_score(y_true[idx], y_pred[idx], zero_division=0))
    return round(float(np.percentile(scores, 2.5)), 4), round(float(np.percentile(scores, 97.5)), 4)


def binary_metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    """Compute precision, recall, F1, ROC-AUC, Brier score, and 95% intervals."""
    y_true = y_true.astype(int)
    y_pred = (prob >= threshold).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    pred_pos = int((y_pred == 1).sum())
    true_pos = int((y_true == 1).sum())

    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    auc = float(roc_auc_score(y_true, prob)) if len(np.unique(y_true)) > 1 else 0.5
    brier = float(brier_score_loss(y_true, np.clip(prob, 0.0, 1.0)))
    return {
        "n": int(len(y_true)),
        "positives": true_pos,
        "predicted_positives": pred_pos,
        "tp": tp,
        "precision": round(prec, 4),
        "precision_ci95": list(wilson_interval(tp, pred_pos)),
        "recall": round(rec, 4),
        "recall_ci95": list(wilson_interval(tp, true_pos)),
        "f1": round(f1, 4),
        "f1_ci95": list(bootstrap_f1_interval(y_true, y_pred)),
        "roc_auc": round(auc, 4),
        "brier": round(brier, 4),
    }


def _logit(p: np.ndarray) -> np.ndarray:
    clipped = np.clip(p, 1e-6, 1.0 - 1e-6)
    return np.log(clipped / (1.0 - clipped))


class CalibratedTaskModel:
    """Wraps a base binary classifier (logreg or lightgbm) and a post-hoc probability calibrator."""

    __module__ = "pipelines.taxonomy.student"

    def __init__(
        self,
        model_type: str,
        base_model: Any,
        cal_method: str,
        calibrator: Any,
    ) -> None:
        self.model_type = model_type
        self.base_model = base_model
        self.cal_method = cal_method
        self.calibrator = calibrator

    def predict_proba_1d(self, x_lr: np.ndarray, x_lgb: np.ndarray) -> np.ndarray:
        x = x_lr if self.model_type == "logreg" else x_lgb
        raw_p = self.base_model.predict_proba(x)[:, 1]
        if self.cal_method == "isotonic" and self.calibrator is not None:
            return np.clip(self.calibrator.predict(raw_p), 0.001, 0.999)
        if self.cal_method == "platt" and self.calibrator is not None:
            logits = _logit(raw_p).reshape(-1, 1)
            return np.clip(self.calibrator.predict_proba(logits)[:, 1], 0.001, 0.999)
        return np.clip(raw_p, 0.001, 0.999)


def load_student_bundle(bundle_path: Path | None = None) -> dict[str, Any]:
    """Load the pickled student bundle safely regardless of caller __main__."""
    if "__main__" in sys.modules:
        sys.modules["__main__"].CalibratedTaskModel = CalibratedTaskModel  # type: ignore[attr-defined]
    path = bundle_path or (lake() / "models" / "curator" / "student_bundle.joblib")
    return joblib.load(path)


def fit_and_compare_binary(
    x_lr_train: np.ndarray,
    x_lgb_train: np.ndarray,
    y_train: np.ndarray,
    x_lr_val: np.ndarray,
    x_lgb_val: np.ndarray,
    y_val: np.ndarray,
    x_lr_test: np.ndarray,
    x_lgb_test: np.ndarray,
    y_test: np.ndarray,
) -> tuple[CalibratedTaskModel, dict[str, Any]]:
    """Train LogisticRegression and LightGBM, calibrate via OOF, and evaluate on val and test."""
    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    if pos_count < 5 or neg_count < 5:
        const_p = pos_count / max(1, len(y_train))

        class _Const:
            def predict_proba(self, x: np.ndarray) -> np.ndarray:
                p1 = np.full(len(x), const_p)
                return np.column_stack([1.0 - p1, p1])

        cm = CalibratedTaskModel("logreg", _Const(), "none", None)
        v_m = binary_metrics(y_val, np.full(len(y_val), const_p))
        t_m = binary_metrics(y_test, np.full(len(y_test), const_p))
        return cm, {
            "selected": "logreg",
            "calibration": "none",
            "note": "constant_fallback",
            "logreg_val": v_m,
            "lightgbm_val": v_m,
            "logreg_test": t_m,
            "lightgbm_test": t_m,
            "winner_val": v_m,
            "winner_test": t_m,
        }

    # 1. Fit LogisticRegression and LightGBM on train, plus 5-fold OOF raw probs for calibration
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    oof_lr = np.zeros(len(y_train), dtype=np.float64)
    oof_lgb = np.zeros(len(y_train), dtype=np.float64)

    for tr_idx, va_idx in skf.split(x_lr_train, y_train):
        lr_f = LogisticRegression(C=1.0, solver="newton-cholesky", max_iter=500, random_state=42)
        lr_f.fit(x_lr_train[tr_idx], y_train[tr_idx])
        oof_lr[va_idx] = lr_f.predict_proba(x_lr_train[va_idx])[:, 1]

        lgb_f = LGBMClassifier(
            n_estimators=120,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=20,
            random_state=42,
            n_jobs=1,
            verbose=-1,
        )
        lgb_f.fit(x_lgb_train[tr_idx], y_train[tr_idx])
        oof_lgb[va_idx] = lgb_f.predict_proba(x_lgb_train[va_idx])[:, 1]

    lr_full = LogisticRegression(C=1.0, solver="newton-cholesky", max_iter=500, random_state=42)
    lr_full.fit(x_lr_train, y_train)

    lgb_full = LGBMClassifier(
        n_estimators=120,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=20,
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )
    lgb_full.fit(x_lgb_train, y_train)

    candidates: dict[str, tuple[CalibratedTaskModel, dict[str, Any], dict[str, Any]]] = {}
    for m_type, base_mod, oof_p, x_v, x_t in [
        ("logreg", lr_full, oof_lr, x_lr_val, x_lr_test),
        ("lightgbm", lgb_full, oof_lgb, x_lgb_val, x_lgb_test),
    ]:
        platt = LogisticRegression(solver="newton-cholesky", random_state=42)
        platt.fit(_logit(oof_p).reshape(-1, 1), y_train)
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(oof_p, y_train)

        m_platt = CalibratedTaskModel(m_type, base_mod, "platt", platt)
        m_iso = CalibratedTaskModel(m_type, base_mod, "isotonic", iso)

        p_val_platt = m_platt.predict_proba_1d(x_v, x_v)
        p_val_iso = m_iso.predict_proba_1d(x_v, x_v)

        b_platt = brier_score_loss(y_val, p_val_platt)
        b_iso = brier_score_loss(y_val, p_val_iso)
        chosen_mod = m_platt if b_platt <= b_iso else m_iso

        p_val = chosen_mod.predict_proba_1d(x_v, x_v)
        p_test = chosen_mod.predict_proba_1d(x_t, x_t)
        val_m = binary_metrics(y_val, p_val)
        test_m = binary_metrics(y_test, p_test)
        val_m["calibration"] = chosen_mod.cal_method
        test_m["calibration"] = chosen_mod.cal_method
        candidates[m_type] = (chosen_mod, val_m, test_m)

    # Pick on validation split (by F1, breaking ties with lower Brier loss)
    lr_mod, lr_val, lr_test = candidates["logreg"]
    lgb_mod, lgb_val, lgb_test = candidates["lightgbm"]
    if (lgb_val["f1"], -lgb_val["brier"]) > (lr_val["f1"], -lr_val["brier"]):
        winner_name, winner_mod = "lightgbm", lgb_mod
    else:
        winner_name, winner_mod = "logreg", lr_mod

    report = {
        "selected": winner_name,
        "calibration": winner_mod.cal_method,
        "logreg_val": lr_val,
        "lightgbm_val": lgb_val,
        "logreg_test": lr_test,
        "lightgbm_test": lgb_test,
        "winner_val": candidates[winner_name][1],
        "winner_test": candidates[winner_name][2],
    }
    return winner_mod, report


def prepare_feature_matrices(
    train_rows: list[dict[str, Any]],
    emb_train: np.ndarray,
    other_splits: list[tuple[list[dict[str, Any]], np.ndarray]],
    n_svd: int = 64,
) -> tuple[
    StandardScaler,
    TruncatedSVD,
    np.ndarray,
    np.ndarray,
    list[tuple[np.ndarray, np.ndarray]],
]:
    """Build (X_lr, X_lgb) for train and each evaluation split."""
    s_train = np.nan_to_num(extract_structured_features(train_rows).astype(np.float64), nan=0.0)
    emb_train_clean = np.nan_to_num(emb_train.astype(np.float64), nan=0.0)
    emb_train_norm = normalize(emb_train_clean)
    n_comp = min(n_svd, emb_train_norm.shape[1] - 1, emb_train_norm.shape[0] - 1)
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    emb_train_svd = svd.fit_transform(emb_train_norm)

    raw_comb_train = np.hstack([emb_train_svd, s_train]).astype(np.float64)
    scaler = StandardScaler()
    x_lr_train = np.clip(scaler.fit_transform(raw_comb_train), -10.0, 10.0).astype(np.float64)
    x_lgb_train = raw_comb_train.astype(np.float32)

    transformed_others: list[tuple[np.ndarray, np.ndarray]] = []
    for rows, emb in other_splits:
        s_raw = np.nan_to_num(extract_structured_features(rows).astype(np.float64), nan=0.0)
        e_norm = normalize(np.nan_to_num(emb.astype(np.float64), nan=0.0))
        e_svd = svd.transform(e_norm)
        raw_comb = np.hstack([e_svd, s_raw]).astype(np.float64)
        x_lr = np.clip(scaler.transform(raw_comb), -10.0, 10.0).astype(np.float64)
        x_lgb = raw_comb.astype(np.float32)
        transformed_others.append((x_lr, x_lgb))

    return scaler, svd, x_lr_train, x_lgb_train, transformed_others


def train_student_suite(
    train_rows: list[dict[str, Any]],
    emb_train: np.ndarray,
    val_rows: list[dict[str, Any]],
    emb_val: np.ndarray,
    test_rows: list[dict[str, Any]],
    emb_test: np.ndarray,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fit and compare LogisticRegression vs LightGBM across is_ai, brand_safe, and 12 subtopics."""
    scaler, svd, x_lr_tr, x_lgb_tr, [(x_lr_va, x_lgb_va), (x_lr_te, x_lgb_te)] = (
        prepare_feature_matrices(
            train_rows, emb_train, [(val_rows, emb_val), (test_rows, emb_test)]
        )
    )

    y_ai_tr = np.array([1 if r["is_ai"] else 0 for r in train_rows])
    y_ai_va = np.array([1 if r["is_ai"] else 0 for r in val_rows])
    y_ai_te = np.array([1 if r["is_ai"] else 0 for r in test_rows])

    is_ai_model, is_ai_rep = fit_and_compare_binary(
        x_lr_tr, x_lgb_tr, y_ai_tr, x_lr_va, x_lgb_va, y_ai_va, x_lr_te, x_lgb_te, y_ai_te
    )

    y_bs_tr = np.array([1 if r["brand_safe"] else 0 for r in train_rows])
    y_bs_va = np.array([1 if r["brand_safe"] else 0 for r in val_rows])
    y_bs_te = np.array([1 if r["brand_safe"] else 0 for r in test_rows])

    bs_model, bs_rep = fit_and_compare_binary(
        x_lr_tr, x_lgb_tr, y_bs_tr, x_lr_va, x_lgb_va, y_bs_va, x_lr_te, x_lgb_te, y_bs_te
    )

    subtopic_models: dict[str, CalibratedTaskModel] = {}
    subtopic_reports: dict[str, Any] = {}
    for st in SUBTOPIC_LIST:
        y_st_tr = np.array([1 if st in (r.get("subtopics") or []) else 0 for r in train_rows])
        y_st_va = np.array([1 if st in (r.get("subtopics") or []) else 0 for r in val_rows])
        y_st_te = np.array([1 if st in (r.get("subtopics") or []) else 0 for r in test_rows])
        st_mod, st_rep = fit_and_compare_binary(
            x_lr_tr, x_lgb_tr, y_st_tr, x_lr_va, x_lgb_va, y_st_va, x_lr_te, x_lgb_te, y_st_te
        )
        subtopic_models[st] = st_mod
        subtopic_reports[st] = st_rep

    macro_f1_val = round(
        float(np.mean([subtopic_reports[st]["winner_val"]["f1"] for st in SUBTOPIC_LIST])), 4
    )
    macro_f1_test = round(
        float(np.mean([subtopic_reports[st]["winner_test"]["f1"] for st in SUBTOPIC_LIST])), 4
    )

    bundle = {
        "scaler": scaler,
        "svd": svd,
        "is_ai_model": is_ai_model,
        "brand_safe_model": bs_model,
        "subtopic_models": subtopic_models,
        "subtopic_list": SUBTOPIC_LIST,
    }
    metrics = {
        "train_n": len(train_rows),
        "val_n": len(val_rows),
        "test_n": len(test_rows),
        "is_ai": is_ai_rep,
        "brand_safe": bs_rep,
        "subtopics_macro_f1_val": macro_f1_val,
        "subtopics_macro_f1_test": macro_f1_test,
        "subtopics": subtopic_reports,
    }
    return bundle, metrics


def predict_with_bundle(
    bundle: dict[str, Any], rows: list[dict[str, Any]], emb: np.ndarray
) -> list[dict[str, Any]]:
    """Run all student classifiers on rows + embeddings and return calibrated predictions."""
    s_raw = np.nan_to_num(extract_structured_features(rows).astype(np.float64), nan=0.0)
    e_norm = normalize(np.nan_to_num(emb.astype(np.float64), nan=0.0))
    e_svd = bundle["svd"].transform(e_norm)
    raw_comb = np.hstack([e_svd, s_raw]).astype(np.float64)
    x_lr = np.clip(bundle["scaler"].transform(raw_comb), -10.0, 10.0).astype(np.float64)
    x_lgb = raw_comb.astype(np.float32)

    p_ai = bundle["is_ai_model"].predict_proba_1d(x_lr, x_lgb)
    p_bs = bundle["brand_safe_model"].predict_proba_1d(x_lr, x_lgb)
    st_probs = {
        st: bundle["subtopic_models"][st].predict_proba_1d(x_lr, x_lgb)
        for st in bundle["subtopic_list"]
    }

    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        prob_ai = float(p_ai[i])
        is_ai = prob_ai >= 0.5
        prob_bs = float(p_bs[i])
        brand_safe = prob_bs >= 0.5
        row_st_probs = {st: round(float(st_probs[st][i]), 4) for st in bundle["subtopic_list"]}
        if is_ai:
            chosen = [st for st, p in row_st_probs.items() if p >= 0.35]
            if not chosen:
                top_st = max(row_st_probs.items(), key=lambda kv: kv[1])[0]
                chosen = [top_st]
            chosen = sorted(chosen, key=lambda s: row_st_probs[s], reverse=True)[:3]
        else:
            chosen = []
        out.append(
            {
                "gkg_id": r["gkg_id"],
                "student_is_ai_prob": round(prob_ai, 4),
                "student_is_ai": is_ai,
                "student_brand_safe_prob": round(prob_bs, 4),
                "student_brand_safe": brand_safe,
                "student_subtopics": sorted(chosen),
                "student_subtopics_str": ";".join(sorted(chosen)),
                "student_main_subtopic": chosen[0] if chosen else "none",
            }
        )
    return out


def select_active_learning_sample(
    pool_df: pl.DataFrame,
    probs_is_ai: np.ndarray,
    total_n: int = 2000,
) -> pl.DataFrame:
    """Select 2,000 pool articles nearest p=0.5, stratified by ring and language."""
    scored = pool_df.with_columns(
        pl.Series("student_r1_prob", probs_is_ai),
        pl.Series("dist_to_05", np.abs(probs_is_ai - 0.5)),
    )
    q1 = int(round(0.375 * total_n))
    q2 = int(round(0.25 * total_n))
    q3 = int(round(0.125 * total_n))
    q4 = total_n - q1 - q2 - q3
    quotas = {"ring1": q1, "ring2": q2, "ring3": q3, "rejected": q4}
    parts: list[pl.DataFrame] = []
    for stratum, q in quotas.items():
        es_q = int(round(0.36 * q))
        other_q = q - es_q
        sub_es = (
            scored.filter((pl.col("stratum") == stratum) & pl.col("is_es_pt"))
            .sort("dist_to_05")
            .head(es_q)
        )
        sub_other = (
            scored.filter((pl.col("stratum") == stratum) & (~pl.col("is_es_pt")))
            .sort("dist_to_05")
            .head(other_q)
        )
        parts.append(pl.concat([sub_es, sub_other]))
    return pl.concat(parts).head(total_n)


def split_initial_sample(
    panel_df: pl.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministic 60/20/20 stratified train/val/test split of the 4,000 initial sample."""
    from collections import Counter

    rows = panel_df.sort("gkg_id").to_dicts()
    raw_strata = [
        f"{r['stratum']}_{int(bool(r['is_ai']))}_{int(bool(r['is_es_pt']))}" for r in rows
    ]
    counts = Counter(raw_strata)
    strata = [
        s if counts[s] >= 5 else str(r["stratum"]) for r, s in zip(rows, raw_strata, strict=True)
    ]
    s_counts = Counter(strata)
    strata = [s if s_counts[s] >= 5 else "other" for s in strata]
    train_rows, temp_rows, _, temp_strata = train_test_split(
        rows, strata, test_size=0.40, random_state=42, stratify=strata
    )
    t_counts = Counter(temp_strata)
    temp_strata_clean = [s if t_counts[s] >= 2 else "other" for s in temp_strata]
    tc2 = Counter(temp_strata_clean)
    if min(tc2.values()) < 2:
        val_rows, test_rows = train_test_split(temp_rows, test_size=0.50, random_state=42)
    else:
        val_rows, test_rows = train_test_split(
            temp_rows, test_size=0.50, random_state=42, stratify=temp_strata_clean
        )
    return train_rows, val_rows, test_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-active-learning", action="store_true")
    ap.add_argument("--workers", type=int, default=32)
    args = ap.parse_args(argv)

    t_dir = lake() / "labels" / "teacher"
    panel_path = t_dir / "panel_labels.parquet"
    if not panel_path.exists():
        raise SystemExit(f"Missing {panel_path}; run pipelines/taxonomy/teacher.py first")

    panel_df = pl.read_parquet(panel_path)
    train_rows, val_rows, test_rows = split_initial_sample(panel_df)

    all_initial_rows = train_rows + val_rows + test_rows
    emb_all, emb_stats_r1 = embed_rows(all_initial_rows)
    n_tr, n_va = len(train_rows), len(val_rows)
    emb_tr = emb_all[:n_tr]
    emb_va = emb_all[n_tr : n_tr + n_va]
    emb_te = emb_all[n_tr + n_va :]

    bundle_r1, metrics_r1 = train_student_suite(
        train_rows, emb_tr, val_rows, emb_va, test_rows, emb_te
    )
    print(
        f"[student R1] val is_ai F1={metrics_r1['is_ai']['winner_val']['f1']:.4f} "
        f"(winner={metrics_r1['is_ai']['selected']}), "
        f"test is_ai F1={metrics_r1['is_ai']['winner_test']['f1']:.4f}"
    )

    final_bundle = bundle_r1
    final_metrics: dict[str, Any] = {
        "embedding_round1": emb_stats_r1,
        "round1": metrics_r1,
    }

    pool_path = lake() / "labels" / "pool.parquet"
    if not args.skip_active_learning and pool_path.exists():
        pool_df = pl.read_parquet(pool_path)
        pool_rows = pool_df.to_dicts()
        emb_pool, emb_stats_pool = embed_rows(pool_rows)
        pool_preds = predict_with_bundle(bundle_r1, pool_rows, emb_pool)
        probs_pool = np.array([p["student_is_ai_prob"] for p in pool_preds])

        active_sample_path = lake() / "labels" / "active_sample.parquet"
        if active_sample_path.exists():
            active_df = pl.read_parquet(active_sample_path)
        else:
            active_df = select_active_learning_sample(pool_df, probs_pool, total_n=2000)
            active_df.write_parquet(active_sample_path, compression="zstd")

        pilot_summary = json.loads((t_dir / "pilot_summary.json").read_text(encoding="utf-8"))
        active_labeled_df, active_panel_summary = teacher.label_dataset_with_panel(
            active_df.drop(["student_r1_prob", "dist_to_05"]),
            panel=pilot_summary["selected_panel"],
            workers=args.workers,
            output_name="active_panel_labels.parquet",
        )

        active_rows = active_labeled_df.to_dicts()
        emb_active, _ = embed_rows(active_rows)

        train_r2_rows = train_rows + active_rows
        emb_tr_r2 = np.vstack([emb_tr, emb_active])

        bundle_r2, metrics_r2 = train_student_suite(
            train_r2_rows, emb_tr_r2, val_rows, emb_va, test_rows, emb_te
        )
        final_bundle = bundle_r2
        val_f1_gain = round(
            metrics_r2["is_ai"]["winner_val"]["f1"] - metrics_r1["is_ai"]["winner_val"]["f1"], 4
        )
        val_brier_gain = round(
            metrics_r1["is_ai"]["winner_val"]["brier"] - metrics_r2["is_ai"]["winner_val"]["brier"],
            4,
        )
        test_f1_gain = round(
            metrics_r2["is_ai"]["winner_test"]["f1"] - metrics_r1["is_ai"]["winner_test"]["f1"], 4
        )
        final_metrics["embedding_pool"] = emb_stats_pool
        final_metrics["active_learning_panel"] = active_panel_summary
        final_metrics["round2"] = metrics_r2
        final_metrics["active_learning_gain"] = {
            "added_rows": len(active_rows),
            "mean_selected_dist_to_05": round(float(active_df["dist_to_05"].mean()), 4),
            "val_is_ai_f1_r1": metrics_r1["is_ai"]["winner_val"]["f1"],
            "val_is_ai_f1_r2": metrics_r2["is_ai"]["winner_val"]["f1"],
            "val_is_ai_f1_delta": val_f1_gain,
            "val_is_ai_brier_r1": metrics_r1["is_ai"]["winner_val"]["brier"],
            "val_is_ai_brier_r2": metrics_r2["is_ai"]["winner_val"]["brier"],
            "val_is_ai_brier_reduction": val_brier_gain,
            "test_is_ai_f1_r1": metrics_r1["is_ai"]["winner_test"]["f1"],
            "test_is_ai_f1_r2": metrics_r2["is_ai"]["winner_test"]["f1"],
            "test_is_ai_f1_delta": test_f1_gain,
        }
        print(
            f"[student R2] val is_ai F1={metrics_r2['is_ai']['winner_val']['f1']:.4f} "
            f"(delta={val_f1_gain:+.4f}), test F1={metrics_r2['is_ai']['winner_test']['f1']:.4f}"
        )

    out_dir = lake() / "models" / "curator"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_bundle, out_dir / "student_bundle.joblib")
    (out_dir / "metrics.json").write_text(
        json.dumps(final_metrics, indent=2) + "\n", encoding="utf-8"
    )

    # Save val and test split predictions for cascade threshold and bin evaluation
    val_preds = predict_with_bundle(final_bundle, val_rows, emb_va)
    test_preds = predict_with_bundle(final_bundle, test_rows, emb_te)
    pl.DataFrame(val_rows).join(pl.DataFrame(val_preds), on="gkg_id", how="left").write_parquet(
        out_dir / "val_predictions.parquet", compression="zstd"
    )
    pl.DataFrame(test_rows).join(pl.DataFrame(test_preds), on="gkg_id", how="left").write_parquet(
        out_dir / "test_predictions.parquet", compression="zstd"
    )
    print(
        json.dumps(
            final_metrics.get("active_learning_gain", final_metrics["round1"]["is_ai"]), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
