"""Trust answers: a calibrated line written by code from the backtest; unconditional trust audited."""

import pytest

from agents import runtime, tools
from agents.llm import Reply


@pytest.fixture(autouse=True)
def _dev(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")


REPORT = """# Backtest

## Primary label: es+pt Wikipedia pageview growth (exact Wikidata matches only)

- Evaluable weeks: 43 (measured): 2025-W49, 2025-W50.

### Precision@10 on labelled slots, with bounds

| Ranker | Coverage | Precision@10 on labelled slots | 95% bootstrap interval over weeks | Worst case | Best case |
|---|---|---|---|---|---|
| Radar, with the eligibility gate and the syndication guard (published) | 408/440 = 92.7% | 119/408 = 29.2% | 24.4% .. 34.0% | 27.0% | 34.3% |
| Baseline: raw-count growth | 378/440 = 85.9% | 120/378 = 31.7% | 26.8% .. 37.0% | 27.3% | 41.4% |
| Baseline: persistence (the label's own last 2 weeks) | 426/440 = 96.8% | 77/426 = 18.1% | 14.8% .. 21.3% | 17.5% | 20.7% |
| Base rate (top quartile; ties at the cutoff excluded, measured share) | n/a | 1036/4085 = 25.4% | n/a | n/a | n/a |

- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: raw-count growth (best): -14.3%: the advantage **does not hold** under the worst case.
- Radar, with the eligibility gate and the syndication guard (published) (worst) minus Baseline: persistence (the label's own last 2 weeks) (best): 6.4%: the advantage **holds** under the worst case.

## Primary label, alias matches included

### Precision@10 on labelled slots, with bounds

| Radar, with the eligibility gate and the syndication guard (published) | 402/440 | 113/402 = 28.1% | 23.3% .. 33.1% | 25.7% | 34.3% |
"""


@pytest.mark.unit
def test_the_backtest_headline_is_parsed_from_the_primary_table_only():
    s = tools.backtest_summary(REPORT)
    assert s["radar_publicado"] == {
        "precision_pct": 29.2,
        "ic95_pct": [24.4, 34.0],
        "peor_caso_pct": 27.0,
        "mejor_caso_pct": 34.3,
    }  # not the alias table's 28.1%
    assert s["tasa_base_pct"] == 25.4 and s["semanas_evaluadas"] == 43
    assert s["crecimiento_de_menciones"]["precision_pct"] == 31.7
    assert s["supera_persistencia_en_peor_caso"] is True
    assert s["supera_crecimiento_en_peor_caso"] is False
    assert tools.backtest_summary("# no table") is None


@pytest.mark.unit
def test_the_real_report_parses():
    s = tools.get_backtest()["resumen"]
    assert s is not None and 0 < s["radar_publicado"]["precision_pct"] < 100


def _trust_turn(pending=True):
    turn = runtime.Turn("t")
    turn.tool_results += [
        {
            "tool": "get_backtest",
            "result": {
                "available": True,
                "resumen": tools.backtest_summary(REPORT),
                "report": REPORT,
            },
        },
        {
            "tool": "get_filter_quality",
            "result": {"available": True, "etiquetas_humanas_pendientes": pending},
        },
    ]
    return turn


@pytest.mark.unit
def test_the_trust_line_is_calibrated_and_every_number_is_traced():
    turn = _trust_turn()
    line = runtime.trust_line(turn)
    assert "acierta el 29,2% de las veces (intervalo del 95%: 24,4% a 34,0%)" in line
    assert "frente a un 25,4% de un tema al azar" in line
    assert "Supera a la persistencia" in line and "no supera a la regla simple" in line
    assert "(31,7%)" in line and "etiquetas humanas" in line and "no como garantía" in line
    assert runtime.untraced_numbers(line, turn.tool_results, "") == []
    assert runtime.trust_claims(line, turn) == []  # the line never trips its own check
    assert "etiquetas humanas" not in runtime.trust_line(_trust_turn(pending=False))


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Puedes confiar en el radar.", ["Puedes confiar"]),
        ("El radar es muy confiable.", ["es muy confiable"]),
        ("Tiene alta precisión.", ["alta precisión"]),
        ("El radar no es confiable como garantía.", []),
        ("Puedes confiar con cautela: es una señal temprana.", []),
        ("Es confiable solo como señal temprana.", []),
    ],
)
def test_unconditional_trust_is_flagged_on_the_trust_route(text, flagged):
    assert runtime.trust_claims(text, _trust_turn()) == flagged
    assert runtime.trust_claims(text, runtime.Turn("t")) == []  # other routes: no check


class Overclaim:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools_):
        self.calls.append(messages)
        return Reply(content="Puedes confiar en el radar: tiene backtest.", model="scripted")


@pytest.mark.unit
def test_a_trust_question_gets_the_line_and_an_overclaim_is_vetoed():
    model = Overclaim()
    response = runtime.run_turn("¿Cuánto puedo confiar en el radar? ¿Hay backtest?", model=model)
    answer = response["answer_es"]
    assert answer.startswith("Qué tan confiable es el radar")
    assert "⚠️ El Auditor: el backtest no respalda una confianza sin condiciones" in answer
    assert any(
        s["action"] == "veto" and "confianza" in s["result_summary"] for s in response["trace"]
    )
    master = [m for m in model.calls if m[0]["content"].startswith("Eres el Maestro de Medios")]
    assert "No digas que se puede confiar sin condiciones" in master[-1][1]["content"]
