"""Every row of the decision table, in order."""

import pytest

from models.decision import Inputs, decide


def x(**kw) -> Inputs:
    base = {
        "eligible": True,
        "emergence_pct": 90.0,
        "stage": "emergente",
        "saturation": 0.1,
        "window_state": "en_cualquier_momento",
        "days_left": None,
    }
    return Inputs(**(base | kw))


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (x(eligible=False), ("no_es_tema_caliente", 1)),
        (x(emergence_pct=None), ("no_es_tema_caliente", 1)),
        (x(emergence_pct=49.9), ("no_es_tema_caliente", 1)),
        (x(stage="en_declive"), ("no_es_tema_caliente", 1)),
        (x(stage="saturado"), ("esperar", 2)),
        (x(saturation=0.6), ("esperar", 2)),
        (x(), ("publicar_ahora", 3)),
        (x(stage="en_pico", window_state="ya_en_espanol"), ("publicar_ahora", 3)),
        (x(window_state="dias_restantes", days_left=3), ("publicar_ahora", 3)),
        (x(window_state="dias_restantes", days_left=4), ("preparar", 4)),
        (x(window_state="sin_estimacion"), ("preparar", 4)),
        (x(stage="semilla"), ("preparar", 4)),
        (x(emergence_pct=75.0, stage="semilla"), ("preparar", 4)),
        (x(emergence_pct=74.9), ("esperar", 5)),
        (x(emergence_pct=50.0), ("esperar", 5)),
    ],
)
def test_decision_table(inputs, expected):
    assert decide(inputs) == expected
