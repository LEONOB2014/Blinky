"""The trust panel's executive summary (agents/trust.py), from the reports alone."""

import pytest

from agents import trust

LQ = """### `is_ai` Precision, Recall & F1 on the 300 Gold Rows (Reference: Teacher Panel Consensus (Pre-Human-Tally))

| Classifier | Precision (95% Wilson CI) | Recall (95% Wilson CI) | F1 |
|---|---|---|---|
| `cascade` | `0.9432` (`[0.8738, 0.9755]`, measured) | `0.9540` (`[0.8877, 0.9820]`, measured) | x |
| `gdelt_ring1_rule` | `0.7500` (`[0.6624, 0.8210]`, measured) | `0.9655` (`[0.9035, 0.9882]`, measured) | x |
"""


@pytest.mark.unit
def test_the_filter_rows_and_the_pending_flag_are_parsed():
    f = trust.filter_summary(LQ)
    assert f["n"] == 300 and f["etiquetas_humanas_pendientes"] is True
    assert f["regla_gdelt"]["precision"] == 0.75 and f["regla_gdelt"]["exhaustividad_ic95"] == [
        0.9035,
        0.9882,
    ]
    assert f["clasificador"]["precision"] == 0.9432
    assert (
        trust.filter_summary(LQ.replace(" (Pre-Human-Tally)", ""))["etiquetas_humanas_pendientes"]
        is False
    )
    assert trust.filter_summary("no table") is None


@pytest.mark.unit
def test_missing_reports_leave_their_points_out(tmp_path):
    assert trust.trust_summary(tmp_path)["available"] is False
    (tmp_path / "label_quality.md").write_text(LQ, encoding="utf-8")
    out = trust.trust_summary(tmp_path)
    ids = [p["id"] for p in out["points"]]
    assert ids == ["filtro", "etiquetas", "senal"]  # no backtest, no ledgers: nothing invented
    assert (
        "precisión 0,75 (0,66 a 0,82) y exhaustividad 0,97 (0,90 a 0,99)"
        in out["points"][0]["texto"]
    )
    assert "contra un panel de modelos" in out["points"][0]["texto"]
