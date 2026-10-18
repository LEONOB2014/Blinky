"""The decision per topic and week, computed from the scores (never by the LLM).

One table, checked top to bottom; the first row whose rule holds decides. The thresholds are set
by hand (estimate), to be tuned on the backtest and the editor test.

1. `no_es_tema_caliente`: not in the ranked universe, no Emergence, stage `en_declive`, or
   Priority_pct < 50 (when Priority_pct is known; otherwise Emergence_pct < 50).
2. `esperar`: stage `saturado` or saturation >= 0.6.
3. `publicar_ahora`: Priority_pct >= 90, Emergence_pct >= 75, stage `emergente` or `en_pico`, and
   the window is closing (`en_cualquier_momento`, `ya_en_espanol`, or `dias_restantes` with <= 3
   days left).
4. `preparar`: Priority_pct >= 75 and Emergence_pct >= 75 (the window is still open, the topic is
   a seed, or there is no estimate).
5. `esperar`: otherwise (hot, but not high enough in the week's priority).

Priority_pct is the topic's percentile of Priority among the week's ranked topics. Rows 3 and 4
require it (Addendum 3) so the actions follow the rank: before, a topic could be `publicar_ahora`
at rank 150 because Emergence and the window alone decided, while Priority also multiplies
saturation, fit and charge. Row 1 can still put a high-priority topic below the action rows when
its stage is `en_declive`; its `why` says so. Row 1 reads Priority_pct for the same reason: Kioxia
was rank 8 in W42 yet `no_es_tema_caliente` because its Emergence alone was below 50 (measured).
"""

from __future__ import annotations

from dataclasses import dataclass

HOT_PCT = 50.0
STRONG_PCT = 75.0
PUBLISH_PRIORITY_PCT = 90.0
PREPARE_PRIORITY_PCT = 75.0
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
    priority_pct: float | None = None


def decide(x: Inputs) -> tuple[str, int]:
    """The decision and the number of the table row that made it."""
    if not x.eligible or x.emergence_pct is None:
        return "no_es_tema_caliente", 1
    low = x.priority_pct < HOT_PCT if x.priority_pct is not None else x.emergence_pct < HOT_PCT
    if low:
        return "no_es_tema_caliente", 1
    if x.stage == "en_declive":
        return "no_es_tema_caliente", 1
    if x.stage == "saturado" or (x.saturation is not None and x.saturation >= SATURATED):
        return "esperar", 2
    pp = x.priority_pct if x.priority_pct is not None else 0.0
    if x.emergence_pct >= STRONG_PCT and pp >= PREPARE_PRIORITY_PCT:
        closing = x.window_state in CLOSING or (
            x.window_state == "dias_restantes"
            and x.days_left is not None
            and x.days_left <= CLOSING_DAYS
        )
        if x.stage in RISING and closing and pp >= PUBLISH_PRIORITY_PCT:
            return "publicar_ahora", 3
        return "preparar", 4
    return "esperar", 5


REASONS_ES = {
    1: "no está en el universo, su prioridad es baja o va en declive",
    2: "ya está saturado",
    3: "emergencia y prioridad altas y la ventana se cierra",
    4: "emergencia y prioridad altas; la ventana sigue abierta o no hay estimación",
    5: "señal presente, sin la emergencia o la prioridad que piden publicar o preparar",
}
