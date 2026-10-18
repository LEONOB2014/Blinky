"""The decision per topic and week, computed from the scores (never by the LLM).

One table, checked top to bottom; the first row whose rule holds decides. The thresholds are set
by hand (estimate), to be tuned on the backtest and the editor test.

1. `no_es_tema_caliente`: not in the ranked universe, no Emergence, Emergence_pct < 50, or stage
   `en_declive`.
2. `esperar`: stage `saturado` or saturation >= 0.6.
3. `publicar_ahora`: Emergence_pct >= 75, stage `emergente` or `en_pico`, and the window is
   closing (`en_cualquier_momento`, `ya_en_espanol`, or `dias_restantes` with <= 3 days left).
4. `preparar`: Emergence_pct >= 75 (the window is still open, the topic is a seed, or there is
   no estimate).
5. `esperar`: otherwise (Emergence_pct 50..75).
"""

from __future__ import annotations

from dataclasses import dataclass

HOT_PCT = 50.0
STRONG_PCT = 75.0
SATURATED = 0.6
CLOSING_DAYS = 3
RISING = {"emergente", "en_pico"}
CLOSING = {"en_cualquier_momento", "ya_en_espanol"}


@dataclass(frozen=True)
class Inputs:
    eligible: bool
    emergence_pct: float | None
    stage: str
    saturation: float | None
    window_state: str
    days_left: int | None


def decide(x: Inputs) -> tuple[str, int]:
    """The decision and the number of the table row that made it."""
    if not x.eligible or x.emergence_pct is None or x.emergence_pct < HOT_PCT:
        return "no_es_tema_caliente", 1
    if x.stage == "en_declive":
        return "no_es_tema_caliente", 1
    if x.stage == "saturado" or (x.saturation is not None and x.saturation >= SATURATED):
        return "esperar", 2
    if x.emergence_pct >= STRONG_PCT:
        closing = x.window_state in CLOSING or (
            x.window_state == "dias_restantes"
            and x.days_left is not None
            and x.days_left <= CLOSING_DAYS
        )
        if x.stage in RISING and closing:
            return "publicar_ahora", 3
        return "preparar", 4
    return "esperar", 5
