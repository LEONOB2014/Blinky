"""No repeated decision line; Spanish/Portuguese coverage written by code; LatAm claims audited."""

import pytest

from agents import runtime, tools
from agents.llm import Reply


@pytest.fixture(autouse=True)
def _dev(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")


def _turn(coverage):
    turn = runtime.Turn("t")
    turn.tool_results.append(
        {"source": 0, "tool": "get_language_coverage", "args": {}, "result": coverage}
    )
    return turn


ZERO = {
    "available": True,
    "topic": "org:marsh mclennan",
    "week": "2026-W42",
    "articulos_es": 0,
    "articulos_pt": 0,
    "articulos_total": 44,
    "dias_con_datos": 6,
}


@pytest.mark.unit
def test_strip_echo_drops_a_repeated_decision_line_and_code_lines_only():
    code = "Decisión del radar para Marsh: Preparar.\n\nCobertura en español y portugués: 0."
    body = (
        "**Decisión del radar para Marsh: Preparar.**\n\nPor qué:\n- crece rápido.\n"
        "Cobertura en español y portugués: 0.\nQué hacer: un carrusel."
    )
    out = runtime.strip_echo(body, code)
    assert "Decisión del radar" not in out and "Cobertura" not in out
    assert out.startswith("Por qué:") and out.endswith("Qué hacer: un carrusel.")
    assert runtime.strip_echo("Decisión del radar: otra.", "") == "Decisión del radar: otra."


class EchoChat:
    """The Media Master repeats the code's decision line, as the live model did."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools_):
        self.calls.append(messages)
        user = messages[-1]["content"]
        if "«Decisión del radar" in user:
            line = user.split("«", 1)[1].split("»", 1)[0].splitlines()[0]
            return Reply(content=f"{line}\n\nPor qué:\n- dato.", model="scripted")
        return Reply(content="Nota.", model="scripted")


@pytest.mark.unit
def test_the_decision_line_appears_once_even_when_the_model_echoes_it():
    answer = runtime.run_turn("¿Qué debería publicar 30X esta semana?", model=EchoChat())[
        "answer_es"
    ]
    assert answer.count("Decisión del radar") == 1
    assert "Por qué:" in answer


@pytest.mark.unit
def test_coverage_counts_spanish_and_portuguese_and_says_zero(monkeypatch):
    series = {
        "all": [{"week": "2026-W41", "articles": 3}, {"week": "2026-W42", "articles": 44}],
        "spa": [{"week": "2026-W41", "articles": 2}],  # none in W42: 0, not missing
        "por": [],
    }
    monkeypatch.setattr(
        tools,
        "get_topic_series",
        lambda topic, lang, weeks=8: {
            "available": bool(series[lang]),
            "topic": topic,
            "rows": series[lang],
        },
    )
    monkeypatch.setattr(tools, "_days_with_data", lambda monday, sunday: 6)
    out = tools.get_language_coverage("org:marsh mclennan")
    assert out["week"] == "2026-W42" and out["articulos_total"] == 44
    assert out["articulos_es"] == 0 and out["articulos_pt"] == 0 and out["dias_con_datos"] == 6
    assert tools.get_language_coverage("org:marsh mclennan", "2026-W41")["articulos_es"] == 2
    line = runtime.coverage_line(_turn(out))
    assert "0 artículos en español y 0 en portugués, de 44 en total (6 días con datos)" in line
    assert runtime.untraced_numbers(line, [{"result": out}], "") == []


@pytest.mark.unit
def test_latam_growth_claims_are_flagged_only_without_es_or_pt_articles():
    text = (
        "Marsh crece muy rápido en Latinoamérica. Encaja con ejecutivos de LatAm. "
        "Aún no hay cobertura en la región. Tiene alta participación en América Latina."
    )
    assert runtime.latam_claims(text, _turn(ZERO)) == [
        "crece muy rápido en Latinoamérica",
        "participación en América Latina",
    ]
    assert runtime.latam_claims(text, _turn(ZERO | {"articulos_es": 3})) == []
    assert runtime.latam_claims(text, runtime.Turn("t")) == []  # no coverage data: no check


@pytest.mark.parametrize(
    "sentence",
    [  # from the answer-polish eval: true statements or other claims, never flagged
        "Un video sobre la brecha de cobertura en LatAm.",
        "Datos de crecimiento global y vacío de cobertura en LatAm.",
        "Su impacto en LatAm es casi nulo.",
        "Es relevante para ejecutivos de LatAm por su presencia en seguros.",
        "Crecimiento rápido (emergencia 92%) y alto potencial de impacto en LatAm.",
        "Sin presencia en la región todavía.",
    ],
)
def test_latam_check_ignores_gaps_and_other_claims(sentence):
    assert runtime.latam_claims(sentence, _turn(ZERO)) == []


@pytest.mark.unit
def test_thousands_separators_are_traced():
    results = [{"result": {"articulos_total": 4117}}]
    assert runtime.untraced_numbers("4.117 artículos o 4,117.", results, "") == []
    assert runtime.untraced_numbers("4.118 artículos.", results, "") == ["4.118"]


@pytest.mark.unit
def test_the_auditor_warns_and_logs_a_veto_on_an_unbacked_latam_claim():
    turn = _turn(ZERO)
    answer, bad, _ = runtime._audit(turn, "El tema crece en LatAm.", "q", [])
    assert "no muestran artículos de este tema en español ni en portugués" in answer
    assert bad == []  # a claim, not an untraced number
    assert any(s["action"] == "veto" and "LatAm" in s["result_summary"] for s in turn.trace)
