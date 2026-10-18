"""Offline unit tests for pipelines/taxonomy/gold_sheet.py."""

from pathlib import Path

import polars as pl
import pytest
from pipelines.taxonomy import gold_sheet


@pytest.mark.unit
def test_filter_recall_estimator_and_subtopic_jaccard():
    acc = [True] * 40 + [False] * 10  # p_acc = 0.80
    rej = [True] * 5 + [False] * 45  # p_rej = 0.10
    res = gold_sheet.filter_recall_estimator(acc, rej, n_acc_pop=500, n_rej_pop=5000)
    # 500*0.8 / (500*0.8 + 5000*0.1) = 400 / 900 = 0.4444
    assert res["recall"] == pytest.approx(0.4444, abs=1e-3)
    assert res["recall_ci95"][0] <= res["recall"] <= res["recall_ci95"][1]

    j = gold_sheet.subtopic_jaccard(
        [{"agents", "llms_models"}, set()],
        [{"agents"}, set()],
    )
    assert j == 0.5


@pytest.mark.unit
def test_write_blind_csv_hides_labels(tmp_path: Path):
    df = pl.DataFrame(
        [
            {
                "row_id": 1,
                "gkg_id": "g-1",
                "dt": "2026-09-20",
                "lang": "spa",
                "source": "example.com",
                "title": "Avances en agentes de IA",
                "url": "https://example.com/ia",
                "top_themes": "TECH_AUTOMATION",
                "top_orgs": "openai",
                "is_ai": True,
                "student_is_ai": True,
            }
        ]
    )
    csv_path = tmp_path / "gold_sheet.csv"
    gold_sheet.write_blind_csv(df, csv_path)
    text = csv_path.read_text(encoding="utf-8")
    assert "human_is_ai" in text
    assert "student_is_ai" not in text
    assert "Avances en agentes de IA" in text
