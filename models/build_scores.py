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


def labels_and_mapped() -> tuple[dict[str, str], set[str]]:
    """Spanish labels (taxonomy, then Wikidata) and the topics with an es or pt article."""
    wd = _wikidata()
    labels: dict[str, str] = dict(SUBTOPICS)
    mapped: set[str] = set()
    if wd is not None:
        has = wd.filter(pl.col("article_es").is_not_null() | pl.col("article_pt").is_not_null())
        mapped = set(has["topic_id"].to_list())
        exact = wd.filter(pl.col("label_es").is_not_null(), pl.col("match") == "exact")
        for r in exact.iter_rows(named=True):
            labels.setdefault(r["topic_id"], r["label_es"])
    return labels, mapped


def label(labels: dict[str, str], topic_id: str) -> str:
    return labels.get(topic_id, topic_id.split(":", 1)[-1])


def units() -> str:
    """`topic` when WS1's `topic_daily` is in the active profile, else `subtopic`."""
    return "topic" if gold("topic_daily").exists() else "subtopic"


def _num(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def why(row: dict[str, Any], win: window.Window, dec: str = "", rule: int = 0) -> list[str]:
    """Up to five Spanish reasons, each number marked measured or estimate.

    The decision's reason comes first, then a seed or alias note, then the scores.
    """
    out = []
    if dec:
        out.append(f"Decisión: {dec} (regla {rule}: {decision.REASONS_ES[rule]})")
    if row.get("seed_reason"):
        out.append(f"Semilla a vigilar: {row['seed_reason']}")
    if row.get("alias_of"):
        out.append(f"También aparece como «{row['alias_of']}» (mismo elemento de Wikidata)")
    if row["emergence_pct"] is not None:
        bits = [f"z_7d {row['z_7d']:.1f}"] if row["z_7d"] is not None else []
        if row["growth_7d_log"] is not None:
            g = math.exp(row["growth_7d_log"])
            pct = "más de 10 veces" if g > 10 else f"{g - 1:+.0%}"
            bits.append(f"cuota 7d {pct} vs. semana previa")
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


# What the later steps read from the daily rolling frame (window onsets, gate history, the
# backtest's raw-count growth and GDELT label); the rest is dropped to keep memory low.
SLIM = ("unit_id", "group", "dt", "n", "n_7d", "z_7d_r")
CHUNK_TOPICS = 300  # topics per rolling pass: the full frame peaks at ~3 GB, a chunk well under


def _slim(roll: pl.DataFrame) -> pl.DataFrame:
    return roll.select(SLIM).with_columns(pl.col("n_7d", "z_7d_r").cast(pl.Float32))


def _inputs(unit: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame | None, dt.date]:
    """Weekly panel (with `ai_all`), the unit's slim daily frame, membership and span start.

    Topics are processed in chunks of CHUNK_TOPICS: every rolling feature is per topic, so the
    weekly panel of a chunk does not depend on the other chunks.
    """
    totals = features.load_totals()
    sub = features.subtopic_daily()
    if unit == "subtopic":
        roll = features.rolling(sub, totals)
        panel = scores.weekly_panel(roll)
        weights = {s: {s: 1.0} for s in sub["unit_id"].unique().to_list()}
        weights["ai_all"] = {}
        mem = scores.static_membership(panel, weights).with_columns(
            pl.col("unit_id").alias("primary_subtopic"),
            pl.concat_list(pl.col("unit_id")).alias("subtopics"),
        )
        return panel, _slim(roll), mem, sub["dt"].min()
    daily = features.topic_daily()
    span = (daily["dt"].min(), daily["dt"].max())
    ids = daily["unit_id"].unique().sort().to_list()
    panels, slims = [], []
    for k in range(0, len(ids), CHUNK_TOPICS):
        part = daily.filter(pl.col("unit_id").is_in(ids[k : k + CHUNK_TOPICS]))
        roll = features.rolling(part, totals, span=span)
        panels.append(scores.weekly_panel(roll))
        slims.append(_slim(roll))
        del roll
    # ai_all is the base for the fit's LatAm / es+pt shares; it is never ranked
    base = features.rolling(sub.filter(pl.col("unit_id") == "ai_all"), totals)
    base = base.filter(pl.col("dt").is_between(*span))
    panels.append(scores.weekly_panel(base))
    panel = pl.concat(panels, how="vertical_relaxed")
    own = pl.concat(slims)
    return panel, own, universe.membership(scores.FIT_SUBTOPICS), span[0]


# Eligibility gate for the top 10 (Addendum 3; thresholds hand-set, estimate): a topic can headline
# when it is an established entity (articles in >= GATE_WEEKS of the prior GATE_SPAN ISO weeks and
# >= GATE_ARTICLES articles in them) or it resolves to a Wikidata item with match `exact`.
# Other ranked topics are "semillas a vigilar": stage semilla, ranked after every eligible topic.
# Deviation from Addendum 3 (which allows exact or alias): every `alias` match in WS6's table has
# confidence 0.6 and several are wrong on the W42 list (measured: org:national anti -> an anti-
# doping agency, org:us department -> Veterans Affairs), so an alias alone does not open the gate;
# aliases still merge topics that share a QID, and give no Spanish label.
GATE_SPAN, GATE_WEEKS, GATE_ARTICLES = 8, 6, 200
GATE_MATCH = ("exact",)
WIKIDATA_MATCH = ("exact", "alias")  # for the same-QID dedupe


def history(own: pl.DataFrame) -> pl.DataFrame:
    """Per topic x ISO week: weeks with articles and articles over the prior GATE_SPAN weeks."""
    daily = own.filter(pl.col("group") == "all", pl.col("n").is_not_null())
    wk = daily.group_by("unit_id", pl.col("dt").dt.truncate("1w").alias("monday")).agg(
        pl.col("n").sum().alias("n_week")
    )
    mondays = wk.select("monday").unique()
    grid = wk.select("unit_id").unique().join(mondays, how="cross")
    g = grid.join(wk, on=["unit_id", "monday"], how="left").with_columns(
        pl.col("n_week").fill_null(0)
    )
    g = g.sort("unit_id", "monday").with_columns(
        (pl.col("n_week") > 0)
        .cast(pl.Int32)
        .rolling_sum(GATE_SPAN, min_samples=1)
        .shift(1)
        .over("unit_id")
        .fill_null(0)
        .alias("weeks_active_prior"),
        pl.col("n_week")
        .rolling_sum(GATE_SPAN, min_samples=1)
        .shift(1)
        .over("unit_id")
        .fill_null(0)
        .alias("articles_prior"),
    )
    return g.select(
        "unit_id",
        pl.col("monday").dt.strftime("%G-W%V").alias("week"),
        "weeks_active_prior",
        "articles_prior",
    )


def gate(scored: pl.DataFrame, own: pl.DataFrame) -> pl.DataFrame:
    """Applies the eligibility gate and the Wikidata alias dedupe, and re-ranks each week."""
    s = scored.join(history(own), on=["unit_id", "week"], how="left")
    wd = _wikidata()
    if wd is not None:
        q = wd.filter(pl.col("match").is_in(WIKIDATA_MATCH), pl.col("qid").is_not_null())
        s = s.join(
            q.select(pl.col("topic_id").alias("unit_id"), "qid", "match"), on="unit_id", how="left"
        )
    else:
        s = s.with_columns(
            pl.lit(None, pl.String).alias("qid"), pl.lit(None, pl.String).alias("match")
        )
    established = (pl.col("weeks_active_prior").fill_null(0) >= GATE_WEEKS) & (
        pl.col("articles_prior").fill_null(0) >= GATE_ARTICLES
    )
    s = s.with_columns(
        (established | pl.col("match").is_in(GATE_MATCH).fill_null(False)).alias("headline_ok"),
    )
    # same QID in the same week: keep the topic with more articles, name the others in its why
    s = s.with_columns(
        pl.col("n7raw").rank("ordinal", descending=True).over("week", "qid").alias("qid_rank")
    )
    dup = s.filter(pl.col("qid").is_not_null(), pl.col("qid_rank") > 1)
    names = dup.group_by("week", "qid").agg(
        pl.col("unit_id").str.split(":").list.last().str.join(", ").alias("alias_of")
    )
    s = s.filter(pl.col("qid").is_null() | (pl.col("qid_rank") == 1))
    s = s.join(names, on=["week", "qid"], how="left")
    s = s.with_columns(
        pl.when(pl.col("headline_ok"))
        .then(pl.lit(None, pl.String))
        .otherwise(
            pl.format(
                "{} de {} semanas previas con artículos y {} artículos en ellas; sin Wikidata",
                pl.col("weeks_active_prior").fill_null(0),
                pl.lit(GATE_SPAN),
                pl.col("articles_prior").fill_null(0),
            )
        )
        .alias("seed_reason"),
        pl.when(pl.col("headline_ok"))
        .then(pl.col("stage"))
        .otherwise(pl.lit("semilla"))
        .alias("stage"),
    )
    order = pl.struct(
        (~pl.col("headline_ok")).cast(pl.Int8).alias("seed"), (-pl.col("priority")).alias("p")
    )
    return s.with_columns(order.rank("ordinal").over("week").cast(pl.Int64).alias("rank"))


def scored_units(unit: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame | None]:
    """Scored unit-weeks after the warm-up, the unit's own rolling frame and its membership."""
    panel, own, mem, start = _inputs(unit)
    scored = scores.score(panel, mem, graph=_graph("unit_id"))
    scored = scored.filter(pl.col("asof") >= start + dt.timedelta(days=WARMUP_DAYS))
    return scored, own, mem


def build(unit: str | None = None, min_onsets: int = window.MIN_ONSETS) -> list[dict[str, Any]]:
    """Every record of `topic_scores_weekly` for the active profile and unit.

    Subtopics: all 12 every week. Topics: the ranked universe only (rows with a rank).
    """
    unit = unit or units()
    scored, own, mem = scored_units(unit)
    if unit == "topic":
        scored = gate(scored.filter(pl.col("rank").is_not_null()), own)
    else:
        scored = scored.with_columns(
            pl.lit(None, pl.String).alias("seed_reason"), pl.lit(None, pl.String).alias("alias_of")
        )
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
    labels, mapped = labels_and_mapped()
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
            dec, rule = decision.decide(
                decision.Inputs(
                    eligible=row["eligible"],
                    emergence_pct=row["emergence_pct"],
                    stage=row["stage"],
                    saturation=row["saturation"],
                    window_state=win.state,
                    days_left=win.days_left,
                    priority_pct=_num(row["priority_pct"]),
                )
            )
            records.append(
                {
                    "week": week,
                    "topic_id": u,
                    "label_es": label(labels, u),
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
                    "why": why(row, win, dec, rule),
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
