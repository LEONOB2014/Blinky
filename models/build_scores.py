"""Build `topic_scores_weekly`: every ranked unit x ISO week, its scores, window chip and decision.

    uv run python -m models.build_scores                     # dev slice, subtopics, no write
    RADAR_PROFILE=full uv run python -m models.build_scores  # topics -> topic_scores_weekly,
                                                             # subtopics -> subtopic_scores_weekly

Every record is validated against `contracts/topic_scores_weekly.schema.json` before writing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from models import decision, features, scores, universe, window
from radar.contracts import validate_records
from radar.paths import REPO_ROOT, gold, profile

TAXONOMY = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
SUBTOPICS: dict[str, str] = {k: v["label_es"] for k, v in TAXONOMY["subtopics"].items()}

# The first 5 weeks of the span have no z_7d history (34 days back plus the 7-day window), so
# they are not scored (design: evaluable weeks = span - 5 warm-up weeks).
WARMUP_DAYS = 35

STAGE_ES = {
    "semilla": "semilla",
    "emergente": "emergente",
    "en_pico": "en pico",
    "saturado": "saturado",
    "en_declive": "en declive",
}


NULLABLE = ("emergence_pct", "saturation", "emotional_charge_pct", "z_7d", "growth_7d_log")


def _wikidata() -> pl.DataFrame | None:
    path = gold("topic_wikidata")
    return pl.read_parquet(path) if path.exists() else None


def _graph(key: str) -> pl.DataFrame | None:
    path = gold("node_metrics_weekly")
    if not path.exists():
        return None
    g = pl.read_parquet(path)
    wk = pl.col("wk").cast(pl.Date) if g.schema["wk"] != pl.String else pl.col("wk").str.to_date()
    return g.select(
        pl.col("entity_id").alias(key), wk.dt.strftime("%G-W%V").alias("week"), "new_nbr_rate"
    )


def units() -> str:
    """`topic` when WS1's `topic_daily` is in the active profile, else `subtopic`."""
    return "topic" if gold("topic_daily").exists() else "subtopic"


def _num(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def why(row: dict[str, Any], win: window.Window) -> list[str]:
    """Up to five Spanish reasons, each number marked measured or estimate."""
    out = []
    if row["emergence_pct"] is not None:
        bits = [f"z_7d {row['z_7d']:.1f}"] if row["z_7d"] is not None else []
        if row["growth_7d_log"] is not None:
            bits.append(f"cuota 7d {math.exp(row['growth_7d_log']) - 1:+.0%} vs. semana previa")
        detail = f" ({', '.join(bits)})" if bits else ""
        pct = row["emergence_pct"]
        out.append(f"Emergencia: percentil {pct:.0f} de la semana{detail} (medido)")
    sat = f", saturación {row['saturation']:.2f}" if row["saturation"] is not None else ""
    out.append(f"Etapa: {STAGE_ES[row['stage']]}{sat} (medido, reglas v1)")
    if row["emotional_charge_pct"] is not None:
        out.append(
            f"Carga emocional: percentil {row['emotional_charge_pct']:.0f}; "
            f"ángulo «{row['framing_angle']}» (medido)"
        )
    out.append(f"Encaje con la audiencia: {row['audience_fit']:.2f} (regla v1, estimación)")
    if win.state == "dias_restantes":
        out.append(
            f"Ventana: ~{win.days_left} días antes de llegar al español "
            f"(estimación, mediana de {win.n_onsets} desfases)"
        )
    elif win.state == "en_cualquier_momento":
        out.append("Ventana: puede llegar al español en cualquier momento (estimación)")
    elif win.state == "ya_en_espanol":
        out.append("Ventana: la cobertura en español y portugués ya despegó (medido)")
    return out[:5]


def _inputs(unit: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame | None, dt.date]:
    """Rolling frame (with `ai_all`), the unit's own rolling frame, membership and span start."""
    totals = features.load_totals()
    sub = features.subtopic_daily()
    if unit == "subtopic":
        roll = features.rolling(sub, totals)
        weights = {s: {s: 1.0} for s in sub["unit_id"].unique().to_list()}
        weights["ai_all"] = {}
        mem = scores.static_membership(scores.weekly_panel(roll), weights).with_columns(
            pl.col("unit_id").alias("primary_subtopic"),
            pl.concat_list(pl.col("unit_id")).alias("subtopics"),
        )
        return roll, roll, mem, sub["dt"].min()
    daily = features.topic_daily()
    own = features.rolling(daily, totals)
    # ai_all is the base for the fit's LatAm / es+pt shares; it is never ranked
    base = features.rolling(sub.filter(pl.col("unit_id") == "ai_all"), totals)
    base = base.filter(pl.col("dt").is_between(own["dt"].min(), own["dt"].max()))
    roll = pl.concat([own, base], how="vertical_relaxed")
    return roll, own, universe.membership(scores.FIT_SUBTOPICS), daily["dt"].min()


def build(unit: str | None = None, min_onsets: int = window.MIN_ONSETS) -> list[dict[str, Any]]:
    """Every record of `topic_scores_weekly` for the active profile and unit.

    Subtopics: all 12 every week. Topics: the ranked universe only (rows with a rank).
    """
    unit = unit or units()
    roll, own, mem, start = _inputs(unit)
    panel = scores.weekly_panel(roll)
    scored = scores.score(panel, mem, graph=_graph("unit_id"))
    scored = scored.filter(pl.col("asof") >= start + dt.timedelta(days=WARMUP_DAYS))
    if unit == "topic":
        scored = scored.filter(pl.col("rank").is_not_null())
    if mem is not None:
        scored = scored.join(
            mem.select("unit_id", "week", "primary_subtopic", "subtopics"),
            on=["unit_id", "week"],
            how="left",
        )
    else:
        scored = scored.with_columns(
            pl.lit(None, pl.String).alias("primary_subtopic"),
            pl.lit(None, pl.List(pl.String)).alias("subtopics"),
        )
    onset_tab = window.onset_table(own)
    wd = _wikidata()
    mapped: set[str] = set()
    labels: dict[str, str] = dict(SUBTOPICS)
    if wd is not None:
        has = wd.filter(pl.col("article_es").is_not_null() | pl.col("article_pt").is_not_null())
        mapped = set(has["topic_id"].to_list())
        for r in wd.filter(pl.col("label_es").is_not_null()).iter_rows(named=True):
            labels.setdefault(r["topic_id"], r["label_es"])
    records = []
    for (week,), wk in scored.group_by("week", maintain_order=True):
        asof = wk["asof"][0]
        # the lag pool is every topic with the same primary subtopic this week, ranked or not
        pool = {}
        if mem is not None:
            m = mem.filter(pl.col("week") == week, pl.col("primary_subtopic").is_not_null())
            pool = dict(zip(m["unit_id"], m["primary_subtopic"], strict=True))
        chips = window.chips(onset_tab, pool, asof, min_onsets=min_onsets) if pool else {}
        for row in wk.iter_rows(named=True):
            u = row["unit_id"]
            for c in NULLABLE:
                row[c] = _num(row[c])
            win = chips.get(u, window.Window("sin_estimacion", None, None, 0))
            dec, _ = decision.decide(
                decision.Inputs(
                    eligible=row["eligible"],
                    emergence_pct=row["emergence_pct"],
                    stage=row["stage"],
                    saturation=row["saturation"],
                    window_state=win.state,
                    days_left=win.days_left,
                )
            )
            records.append(
                {
                    "week": week,
                    "topic_id": u,
                    "label_es": labels.get(u, u.split(":", 1)[-1]),
                    "subtopics": list(row["subtopics"] or []),
                    "primary_subtopic": row["primary_subtopic"] or universe.NO_SUBTOPIC,
                    "emergence_pct": row["emergence_pct"],
                    "stage": row["stage"],
                    "saturation": row["saturation"],
                    "audience_fit": _num(row["audience_fit"]),
                    "outperformance": None,
                    "emotional_charge_pct": row["emotional_charge_pct"],
                    "framing_angle": row["framing_angle"],
                    "window": win.as_record(),
                    "priority": float(row["priority"]),
                    "rank": row["rank"],
                    "decision": dec,
                    "why": why(row, win),
                    "evidence_ids": [],
                    "has_wikipedia_es_pt": u in mapped,
                    "profile": profile(),
                }
            )
    return records


def to_frame(records: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(records, infer_schema_length=None)


def out_path(unit: str) -> Path:
    """Topics are `topic_scores_weekly` (what the API and the agents rank). Once topics exist, the
    12-subtopic table keeps the same contract in `subtopic_scores_weekly` (the agents' overview)."""
    if unit == "subtopic" and units() == "topic":
        return gold("subtopic_scores_weekly")
    return gold("topic_scores_weekly")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--unit", choices=["subtopic", "topic"], default=None, help="default: both")
    ap.add_argument("--out", type=Path, default=None, help="default: the lake on the full profile")
    args = ap.parse_args(argv)
    todo = (
        [args.unit]
        if args.unit
        else (["topic", "subtopic"] if units() == "topic" else ["subtopic"])
    )
    for unit in todo:
        records = build(unit)
        errors = validate_records("topic_scores_weekly", records)
        if errors:
            print("\n".join(errors[:20]), file=sys.stderr)  # noqa: T201
            return 1
        df = to_frame(records)
        out = args.out or (out_path(unit) if profile() == "full" else None)
        n_units = df["topic_id"].n_unique()
        print(f"{unit}: {len(records)} rows, {df['week'].n_unique()} weeks, {n_units} units, valid")  # noqa: T201
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(out)
            print(f"wrote {out}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
