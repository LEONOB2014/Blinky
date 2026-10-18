"""Brief coverage claims must agree with the brief's own es+pt count (agents/briefs.py)."""

import pytest

from agents import briefs

pytestmark = pytest.mark.unit


def _data(es: int, en: int) -> briefs.TopicData:
    data = briefs.TopicData.__new__(briefs.TopicData)
    data.facts = {
        "articulos_en_espanol_y_portugues_por_semana": [0, 0, 0, es],
        "articulos_en_ingles_por_semana": [0, 0, 0, en],
    }
    return data


def _fields(text: str) -> dict[str, str]:
    return dict.fromkeys(briefs.FIELDS, "Sin datos de cobertura.") | {"what_happened_es": text}


@pytest.mark.parametrize(
    ("text", "es", "en", "flagged"),
    [  # the review's cases and the first AI briefs (2026-10-18)
        ("Google DeepMind: crece rápido, pero aún no llega al español.", 18, 28, True),
        ("ChatGPT crece muy rápido, pero casi nadie lo cuenta en español.", 152, 785, True),
        ("El debate aún no ha llegado al español.", 10, 142, True),
        ("Casi nadie lo cuenta en español.", 3, 63, False),  # 4.5% < 10%: a fair claim
        ("Aún no se cuenta mucho en español.", 3, 63, False),
        ("Aún no se cuenta mucho en español.", 18, 28, True),  # 39%: not "not much"
        ("Aún no llega al español.", 0, 40, False),  # true: 0 articles
        ("Crece en inglés; aún no hay datos de su tono.", 18, 28, False),  # no language named
    ],
)
def test_a_coverage_claim_must_agree_with_the_count(text, es, en, flagged):
    bad = briefs.coverage_contradictions(_fields(text), _data(es, en))
    assert bool(bad) is flagged


def test_a_contradicted_sentence_is_replaced_by_the_code_written_line():
    fields = _fields("Crece rápido. Pero aún no llega al español. Es un tema de laboratorios.")
    fixed = briefs.fix_coverage(fields, _data(18, 28))
    assert fixed["what_happened_es"] == (
        "Crece rápido. Esta semana hubo 18 artículos en español y portugués, frente a 28 en "
        "inglés. Es un tema de laboratorios."
    )
    assert briefs.coverage_contradictions(fixed, _data(18, 28)) == []
    assert fixed["headline_es"] == fields["headline_es"]  # other fields untouched
