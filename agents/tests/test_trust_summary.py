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
    text = out["points"][0]["texto"]
    assert "el radar usa hoy la regla de GDELT, con precisión 0,75 (0,66 a 0,82)" in text
    assert "y exhaustividad 0,97 (0,90 a 0,99)" in text and "contra un panel de modelos" in text
    assert (
        "el clasificador entrenado (precisión 0,94, exhaustividad 0,95) está validado contra "
        "el panel de modelos pero aún no alimenta el radar." in text
    )


@pytest.mark.unit
def test_the_radar_aggregates_still_use_the_gdelt_rule_not_the_classifier():
    """Guards the summary's "aún no alimenta el radar": bq_sql must not read the cascade."""
    from pathlib import Path

    sql = Path(__file__).resolve().parents[2] / "bq_sql"
    text = " ".join(p.read_text(encoding="utf-8").lower() for p in sql.glob("*.sql"))
    assert text, "bq_sql has the aggregate jobs"
    assert trust.FILTER_IN_USE == "regla_gdelt"
    assert "cascade" not in text and "is_ai_student" not in text and "classifier" not in text


@pytest.mark.parametrize(
    ("source", "report", "says", "not_says"),
    [
        (None, "backtest.md", "acierta el 29,2%", "bajo la regla del 90%"),
        ("ai", "backtest_ai.md", "acierta el 22,1%", "29,2%"),
    ],
)
def test_the_trust_answer_reads_the_backtest_of_the_active_source(
    monkeypatch, source, report, says, not_says
):
    """v0.2's report by default; the AI lexicon run's under RADAR_SOURCE=ai (its secondary label,
    since its primary is below the coverage rule)."""
    from agents import runtime, tools
    from radar.paths import REPO_ROOT

    if source:
        monkeypatch.setenv("RADAR_SOURCE", source)
    else:
        monkeypatch.delenv("RADAR_SOURCE", raising=False)
    assert trust.backtest_report(REPO_ROOT / "reports").name == report
    turn = runtime.Turn("t")
    for name in ("get_backtest", "get_filter_quality"):
        runtime._run_tool(turn, "auditor", name)
    line = runtime.trust_line(turn)
    assert says in line and not_says not in line
    assert runtime.untraced_numbers(line, turn.tool_results, "") == []
    summary = trust.trust_summary(REPO_ROOT / "reports")
    points = {p["id"]: p["texto"] for p in summary["points"]}
    assert says.replace("acierta el ", "acierta el ") in points["precision"]
    assert f"reports/{report}" in summary["sources"]
    if source == "ai":
        assert "frente a un 25,4% de un tema al azar" in line
        assert "no supera a la regla simple de crecimiento de menciones (27,7%)" in line
        assert "incluso en el peor caso" not in line  # a secondary-label claim, not a bound
        assert trust.PRIMARY_BELOW_COVERAGE in line and points["principal"]
        assert tools.get_backtest()["fuente"] == "reports/backtest_ai.md"
    else:
        assert "principal" not in points


def test_the_secondary_parser_needs_its_section():
    assert trust.secondary_summary("# Backtest\n\nno secondary section") is None
