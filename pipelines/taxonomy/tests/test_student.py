"""Offline unit tests for pipelines/taxonomy/student.py."""

import polars as pl
import pytest

pytest.importorskip("numpy")  # the models extra; CI installs no extras
pytest.importorskip("sklearn")
pytest.importorskip("lightgbm")
import numpy as np  # noqa: E402
from pipelines.taxonomy import student  # noqa: E402


def _synthetic_labeled_rows(n: int = 80) -> list[dict]:
    rng = np.random.default_rng(7)
    rows = []
    for i in range(n):
        is_ai = bool(i % 2 == 0)
        rows.append(
            {
                "gkg_id": f"id-{i:04d}",
                "title": "OpenAI LLM agent benchmark" if is_ai else "Sports match report",
                "url": "https://example.com/ai" if is_ai else "https://example.com/sports",
                "top_themes": "WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES" if is_ai else "",
                "top_orgs": "openai" if is_ai else "",
                "lang": "spa" if i % 3 == 0 else "eng",
                "is_es_pt": bool(i % 3 == 0),
                "stratum": "ring1" if is_ai else "rejected",
                "f_url": is_ai,
                "f_url_short": False,
                "f_title_strong": is_ai,
                "f_title_weak": is_ai,
                "f_org": is_ai,
                "f_latam_loc": False,
                "f_latam_src": False,
                "f_ict": is_ai,
                "f_control": not is_ai,
                "tech_org": is_ai,
                "tech_themed": is_ai,
                "n_ict_themes": 1 if is_ai else 0,
                "tone": float(rng.normal(0.5, 1.0)),
                "polarity": float(rng.uniform(1.0, 4.0)),
                "word_count": 400,
                "regex_subtopics": "agents;llms_models" if is_ai else "",
                "is_ai": is_ai,
                "brand_safe": True,
                "subtopics": ["agents", "llms_models"] if is_ai else [],
            }
        )
    return rows


@pytest.mark.unit
def test_extract_structured_features_and_wilson():
    rows = _synthetic_labeled_rows(10)
    feats = student.extract_structured_features(rows)
    assert feats.shape == (10, 28)
    lo, hi = student.wilson_interval(80, 100)
    assert 0.70 < lo < 0.80 < hi < 0.88


@pytest.mark.unit
def test_train_student_suite_and_predict():
    rows = _synthetic_labeled_rows(90)
    rng = np.random.default_rng(11)
    emb = rng.normal(0, 1, size=(90, 32)).astype(np.float32)
    for i, r in enumerate(rows):
        if r["is_ai"]:
            emb[i, :8] += 2.5

    tr_r, va_r, te_r = rows[:50], rows[50:70], rows[70:]
    emb_tr, emb_va, emb_te = emb[:50], emb[50:70], emb[70:]

    bundle, metrics = student.train_student_suite(tr_r, emb_tr, va_r, emb_va, te_r, emb_te)
    assert metrics["is_ai"]["selected"] in ("logreg", "lightgbm")
    assert metrics["is_ai"]["winner_test"]["f1"] >= 0.8

    preds = student.predict_with_bundle(bundle, te_r, emb_te)
    assert len(preds) == len(te_r)
    assert all(0.0 <= p["student_is_ai_prob"] <= 1.0 for p in preds)


@pytest.mark.unit
def test_select_active_learning_sample_stratified():
    rows = []
    for stratum in ["ring1", "ring2", "ring3", "rejected"]:
        for i in range(40):
            rows.append(
                {
                    "gkg_id": f"{stratum}-{i}",
                    "stratum": stratum,
                    "is_es_pt": bool(i % 2 == 0),
                }
            )
    pool_df = pl.DataFrame(rows)
    probs = np.tile(np.linspace(0.05, 0.95, 40), 4)
    sel = student.select_active_learning_sample(pool_df, probs, total_n=40)
    assert sel.height == 40
    assert float(sel["dist_to_05"].mean()) < float(np.mean(np.abs(probs - 0.5)))
