"""The window chip: how much time is left before a topic lands in Spanish and Portuguese.

Design (docs/designs/radar-build-plan.md, "Window chip"):

- Each topic uses its primary subtopic (the one with most of its articles over the last 28 days).
- Onset = first day `z_7d` > 2. A new cycle starts when `z_7d` crosses 2 upwards after at least
  `REARM_DAYS` observed days at or below 2, so one burst gives one onset.
- Typical lag L = the median, pooled over the topics with the same primary subtopic in the history,
  of the days between a topic's English-bucket onset and its es/pt-bucket onset (the first es/pt
  onset within `MAX_LAG_DAYS` after it). Only pairs complete by the as-of day count: no lookahead.
- Time left N = L - days since this topic's English onset in the current cycle (an English onset
  within the last `CYCLE_DAYS` days).
- States, checked in this order: no English onset in the current cycle -> `sin_estimacion`;
  an es/pt onset since that English onset -> `ya_en_espanol`; fewer than `MIN_ONSETS` historical
  pairs for the subtopic -> `sin_estimacion`; N > 0 -> `dias_restantes` (an estimate);
  otherwise `en_cualquier_momento`.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median

import polars as pl

ONSET_Z = 2.0
REARM_DAYS = 7  # days at or below the threshold before a new onset counts
MAX_LAG_DAYS = 28  # an es/pt onset later than this is not paired with the English onset
CYCLE_DAYS = 28  # an English onset older than this is not the current cycle
MIN_ONSETS = 3


@dataclass(frozen=True)
class Window:
    state: str
    days_left: int | None
    typical_lag_days: float | None
    n_onsets: int

    def as_record(self) -> dict:
        return {
            "state": self.state,
            "days_left": self.days_left,
            "typical_lag_days": self.typical_lag_days,
            "n_onsets": self.n_onsets,
        }


def onsets(days: Sequence[dt.date], z: Sequence[float | None]) -> list[dt.date]:
    """Onset days of one series (days sorted, complete calendar, NULL z on missing days)."""
    out: list[dt.date] = []
    # Only observed quiet days re-arm: the warm-up (NULL z_7d) and missing days neither count as
    # quiet nor reset the count, so a series that starts above 2 has no onset until it cools.
    quiet = 0
    for day, value in zip(days, z, strict=True):
        if value is None:
            continue
        hot = value > ONSET_Z
        if hot and quiet >= REARM_DAYS:
            out.append(day)
        quiet = 0 if hot else quiet + 1
    return out


def onset_table(roll: pl.DataFrame, key: str = "unit_id", z: str = "z_7d_r") -> pl.DataFrame:
    """One row per unit x language group (`eng`, `espt`) x onset day, from `features.rolling`.

    Onsets read the robust z (`features.SD_FLOOR_REL`) by default.
    """
    rows = []
    for (unit, group), g in roll.filter(pl.col("group").is_in(["eng", "espt"])).group_by(
        key, "group"
    ):
        g = g.sort("dt")
        for day in onsets(g["dt"].to_list(), g[z].to_list()):
            rows.append({key: unit, "group": group, "onset": day})
    schema = {key: pl.String, "group": pl.String, "onset": pl.Date}
    return pl.DataFrame(rows, schema=schema)


def lag_pairs(eng: Iterable[dt.date], espt: Iterable[dt.date], asof: dt.date) -> list[int]:
    """Days from each English onset to the first es/pt onset after it, complete by `asof`."""
    espt = sorted(d for d in espt if d <= asof)
    lags = []
    for e in sorted(d for d in eng if d <= asof):
        nxt = next((s for s in espt if e <= s <= e + dt.timedelta(days=MAX_LAG_DAYS)), None)
        if nxt is not None:
            lags.append((nxt - e).days)
    return lags


def chip(
    eng: Iterable[dt.date],
    espt: Iterable[dt.date],
    pooled_lags: Sequence[int],
    asof: dt.date,
    min_onsets: int = MIN_ONSETS,
) -> Window:
    """The chip for one topic on `asof`, given its onsets and its subtopic's pooled lags."""
    n = len(pooled_lags)
    lag = float(median(pooled_lags)) if n else None
    current = [e for e in eng if asof - dt.timedelta(days=CYCLE_DAYS) <= e <= asof]
    if not current:
        return Window("sin_estimacion", None, lag, n)
    e = max(current)
    if any(e <= s <= asof for s in espt):
        return Window("ya_en_espanol", None, lag, n)
    if n < min_onsets or lag is None:
        return Window("sin_estimacion", None, lag, n)
    left = round(lag - (asof - e).days)
    if left > 0:
        return Window("dias_restantes", left, lag, n)
    return Window("en_cualquier_momento", None, lag, n)


def chips(
    onset_tab: pl.DataFrame,
    primary: dict[str, str],
    asof: dt.date,
    key: str = "unit_id",
    min_onsets: int = MIN_ONSETS,
) -> dict[str, Window]:
    """Chips for every unit in `primary` (unit -> primary subtopic) on `asof`."""
    by_unit: dict[str, dict[str, list[dt.date]]] = {}
    for row in onset_tab.iter_rows(named=True):
        by_unit.setdefault(row[key], {"eng": [], "espt": []})[row["group"]].append(row["onset"])
    pooled: dict[str, list[int]] = {}
    for unit, sub in primary.items():
        o = by_unit.get(unit, {"eng": [], "espt": []})
        pooled.setdefault(sub, []).extend(lag_pairs(o["eng"], o["espt"], asof))
    out = {}
    for unit, sub in primary.items():
        o = by_unit.get(unit, {"eng": [], "espt": []})
        out[unit] = chip(o["eng"], o["espt"], pooled.get(sub, []), asof, min_onsets)
    return out
