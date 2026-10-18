"""The backtest: how much to trust the radar's weekly top 10 (design, "Evaluation" / Backtest).

    RADAR_PROFILE=full uv run python -m models.backtest   # writes reports/backtest.md

Protocol, as the design states it:

- Unit: unit x week over the ranked universe (>= 20 articles in the last 7 days). The radar and
  both baselines rank only units with an es or pt Wikipedia article (top 10 among mapped units);
  unmapped units are counted and printed.
- Label: a unit is positive when its es+pt pageview growth over the next 2 weeks is in the top
  quartile of that week's mapped units. Growth = ln((views in the 14 days after the as-of day + 1)
  / (views in the 14 days up to it + 1)); a 14-day window needs >= 12 days with data, and its sum
  is scaled to 14 days.
- Precision@10 per week = positives in the top 10 / 10, next to the base rate (25% by
  construction). Pooled over weeks as positives / total, with a bootstrap interval over weeks.
- Baselines on the same weeks: raw-count growth (ln of the 7-day article count against a week
  earlier, counts not shares) and persistence (the label's own last 2 weeks: the units whose
  pageviews grew most over the 2 weeks up to the as-of day).
- Lead time per flagged positive = weeks from the first flag (a week in the top 10 after a week
  outside it) to the week with most es+pt pageviews within the next 8 weeks; reported as a median
  with a bootstrap interval.
- Evaluable weeks: scored weeks (after the 5 warm-up weeks) whose label window is complete and does
  not overlap the 2025-06-14..07-02 GDELT gap, with more than 10 mapped units. Lead time also
  needs 8 weeks of pageviews after the as-of day.

`label="gdelt_espt"` swaps the label for the design's secondary label, the es+pt GDELT article
count of the same unit (used by the unit tests on the dev slice, which has no pageviews).
Numbers from the dev profile are never reported: the report is written on the full profile only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import random
from dataclasses import dataclass, field
from statistics import median
from typing import Any

import polars as pl

from models import build_scores
from radar.paths import REPO_ROOT, gold, profile

TOP_K = 10
POSITIVE_QUANTILE = 0.75
LABEL_DAYS = 14
MIN_LABEL_DAYS = 12
LEAD_WEEKS = 8
MIN_MAPPED = TOP_K + 1
MIN_WEEKS_FOR_INTERVAL = 10
GAP = (dt.date(2025, 6, 14), dt.date(2025, 7, 2))
HISTORY_DAYS = 41  # what an as-of day's features read: 34 days back plus the 7-day window
BOOTSTRAP_REPS = 2000
SEED = 20261018
REPORT = REPO_ROOT / "reports" / "backtest.md"

RANKERS = {
    "radar": "priority",
    "raw_count_growth": "raw_growth",
    "persistence": "past_growth",
}


def window_sum(daily: pl.DataFrame, start: dt.date, end: dt.date) -> pl.DataFrame:
    """Per unit: the value summed over [start, end], scaled to the window, NULL when too thin."""
    days = (end - start).days + 1
    w = daily.filter(pl.col("dt").is_between(start, end), pl.col("value").is_not_null())
    return w.group_by("unit_id").agg(
        pl.when(pl.len() >= MIN_LABEL_DAYS * days / LABEL_DAYS)
        .then(pl.col("value").sum() * days / pl.len())
        .alias("s")
    )


def growth_table(daily: pl.DataFrame, asofs: list[dt.date]) -> pl.DataFrame:
    """Per unit x as-of day: next-2-week growth (label) and last-2-week growth (persistence)."""
    span = dt.timedelta(days=LABEL_DAYS)
    one = dt.timedelta(days=1)
    rows = []
    for t in asofs:
        nxt = window_sum(daily, t + one, t + span).rename({"s": "nxt"})
        cur = window_sum(daily, t - span + one, t).rename({"s": "cur"})
        prv = window_sum(daily, t - 2 * span + one, t - span).rename({"s": "prv"})
        g = cur.join(nxt, on="unit_id", how="full", coalesce=True).join(
            prv, on="unit_id", how="full", coalesce=True
        )
        rows.append(
            g.select(
                "unit_id",
                pl.lit(t).alias("asof"),
                ((pl.col("nxt") + 1) / (pl.col("cur") + 1)).log().alias("label_growth"),
                ((pl.col("cur") + 1) / (pl.col("prv") + 1)).log().alias("past_growth"),
            )
        )
    return pl.concat(rows) if rows else pl.DataFrame()


def weekly_peak_lead(daily: pl.DataFrame, unit: str, t: dt.date) -> int | None:
    """Weeks (1..8) from `t` to the week with most views in the next 8 weeks; NULL if incomplete."""
    sums = []
    for k in range(LEAD_WEEKS):
        a = t + dt.timedelta(days=7 * k + 1)
        b = t + dt.timedelta(days=7 * k + 7)
        w = daily.filter(pl.col("unit_id") == unit, pl.col("dt").is_between(a, b))
        w = w.filter(pl.col("value").is_not_null())
        if w.height < 6:
            return None
        sums.append(w["value"].sum() * 7 / w.height)
    return 1 + max(range(LEAD_WEEKS), key=lambda k: sums[k])


@dataclass
class Result:
    label: str
    weeks: list[str] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)
    per_week: pl.DataFrame | None = None
    pooled: dict[str, dict[str, Any]] = field(default_factory=dict)
    diffs: dict[str, dict[str, Any]] = field(default_factory=dict)
    leads: list[int] = field(default_factory=list)
    lead_ci: tuple[float, float] | None = None
    n_units: int = 0
    n_mapped_units: int = 0
    n_unmapped_rows: int = 0


def _ci(values: list[float], q: float = 0.025) -> tuple[float, float]:
    v = sorted(values)
    lo = v[int(math.floor(q * (len(v) - 1)))]
    hi = v[int(math.ceil((1 - q) * (len(v) - 1)))]
    return lo, hi


def bootstrap_precision(per_week: pl.DataFrame, col: str, rng: random.Random) -> list[float]:
    hits, tot = per_week[f"hits_{col}"].to_list(), per_week["k"].to_list()
    n = len(hits)
    out = []
    for _ in range(BOOTSTRAP_REPS):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(sum(hits[i] for i in idx) / sum(tot[i] for i in idx))
    return out


def bootstrap_diff(per_week: pl.DataFrame, a: str, b: str, rng: random.Random) -> list[float]:
    ha, hb, k = (per_week[c].to_list() for c in (f"hits_{a}", f"hits_{b}", "k"))
    n = len(k)
    out = []
    for _ in range(BOOTSTRAP_REPS):
        idx = [rng.randrange(n) for _ in range(n)]
        tot = sum(k[i] for i in idx)
        out.append((sum(ha[i] for i in idx) - sum(hb[i] for i in idx)) / tot)
    return out


def evaluate(
    scored: pl.DataFrame,
    raw_growth: pl.DataFrame,
    daily: pl.DataFrame,
    mapped: set[str],
    label: str,
) -> Result:
    """The protocol on scored unit-weeks.

    `scored` has unit_id, week, asof, priority, rank (NULL outside the ranked universe);
    `raw_growth` has unit_id, week, raw_growth; `daily` is the label series (unit_id, dt, value).
    """
    res = Result(label=label)
    eligible = scored.filter(pl.col("rank").is_not_null())
    res.n_units = eligible["unit_id"].n_unique()
    res.n_mapped_units = eligible.filter(pl.col("unit_id").is_in(list(mapped)))[
        "unit_id"
    ].n_unique()
    res.n_unmapped_rows = eligible.filter(~pl.col("unit_id").is_in(list(mapped))).height
    last_day = daily.filter(pl.col("value").is_not_null())["dt"].max()
    asofs = sorted(set(eligible["asof"].to_list()))
    gt = growth_table(daily, asofs)
    u = (
        eligible.filter(pl.col("unit_id").is_in(list(mapped)))
        .select("unit_id", "week", "asof", "priority")
        .join(raw_growth, on=["unit_id", "week"], how="left")
        .join(gt, on=["unit_id", "asof"], how="left")
    )
    rows = []
    for (week,), g in u.group_by("week", maintain_order=True):
        t = g["asof"][0]
        if t + dt.timedelta(days=LABEL_DAYS) > last_day:
            res.excluded[week] = "label window not complete"
            continue
        lo, hi = t - dt.timedelta(days=HISTORY_DAYS), t + dt.timedelta(days=LABEL_DAYS)
        if lo <= GAP[1] and hi >= GAP[0]:
            res.excluded[week] = "overlaps the 2025-06-14..07-02 GDELT gap"
            continue
        g = g.filter(pl.col("label_growth").is_not_null())
        if g.height < MIN_MAPPED:
            res.excluded[week] = f"{g.height} mapped units with a label (needs {MIN_MAPPED})"
            continue
        n_pos = math.ceil(g.height * (1 - POSITIVE_QUANTILE))
        g = g.with_columns(
            (pl.col("label_growth").rank("ordinal", descending=True) <= n_pos).alias("positive")
        )
        rec = {"week": week, "asof": t, "n_mapped": g.height, "n_pos": n_pos, "k": TOP_K}
        for name, col in RANKERS.items():
            top = g.filter(pl.col(col).is_not_null()).sort(col, descending=True).head(TOP_K)
            rec[f"hits_{name}"] = int(top["positive"].sum())
            rec[f"top_{name}"] = top["unit_id"].to_list()
        rec["positives"] = g.filter("positive")["unit_id"].to_list()
        rows.append(rec)
    res.per_week = pl.DataFrame(rows) if rows else None
    res.weeks = [r["week"] for r in rows]
    if not rows:
        return res
    pw = res.per_week
    rng = random.Random(SEED)  # noqa: S311 (a seeded bootstrap, not cryptography)
    for name in RANKERS:
        hits, tot = int(pw[f"hits_{name}"].sum()), int(pw["k"].sum())
        entry: dict[str, Any] = {"hits": hits, "total": tot, "precision": hits / tot}
        if len(rows) >= MIN_WEEKS_FOR_INTERVAL:
            entry["ci"] = _ci(bootstrap_precision(pw, name, rng))
        res.pooled[name] = entry
    base = int(pw["n_pos"].sum()) / int(pw["n_mapped"].sum())
    res.pooled["base_rate"] = {
        "hits": int(pw["n_pos"].sum()),
        "total": int(pw["n_mapped"].sum()),
        "precision": base,
    }
    for b in ("raw_count_growth", "persistence"):
        d = (res.pooled["radar"]["hits"] - res.pooled[b]["hits"]) / res.pooled["radar"]["total"]
        entry = {"diff": d}
        if len(rows) >= MIN_WEEKS_FOR_INTERVAL:
            entry["ci"] = _ci(bootstrap_diff(pw, "radar", b, rng))
        res.diffs[b] = entry
    # lead time: first flags (top 10 after a week outside it) that are positive
    prev: set[str] = set()
    prev_week_idx = None
    order = {w: i for i, w in enumerate(sorted(set(u["week"].to_list())))}
    for r in rows:
        top = set(r["top_radar"])
        contiguous = prev_week_idx is not None and order[r["week"]] == prev_week_idx + 1
        first = top - (prev if contiguous else set())
        for unit in sorted(first & set(r["positives"])):
            lead = weekly_peak_lead(daily, unit, r["asof"])
            if lead is not None:
                res.leads.append(lead)
        prev, prev_week_idx = top, order[r["week"]]
    if len(res.leads) >= 2:
        meds = []
        for _ in range(BOOTSTRAP_REPS):
            meds.append(median(rng.choice(res.leads) for _ in res.leads))
        res.lead_ci = _ci(meds)
    return res


# --- inputs ---------------------------------------------------------------------------------


def scored_units() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Scored unit-weeks, raw-count growth and the rolling frame for the active profile's units."""
    s, roll, _ = build_scores.scored_units(build_scores.units())
    allg = roll.filter(pl.col("group") == "all").sort("unit_id", "dt")
    allg = allg.with_columns(
        ((pl.col("n_7d") + 1) / (pl.col("n_7d").shift(7).over("unit_id") + 1))
        .log()
        .alias("raw_growth")
    )
    raw = s.select("unit_id", "week", "asof").join(
        allg.select("unit_id", pl.col("dt").alias("asof"), "raw_growth"),
        on=["unit_id", "asof"],
        how="left",
    )
    return s, raw.select("unit_id", "week", "raw_growth"), roll


def gdelt_espt_label(roll: pl.DataFrame) -> pl.DataFrame:
    """The secondary label series: es+pt GDELT articles per unit and day (NULL on missing days)."""
    return roll.filter(pl.col("group") == "espt").select(
        "unit_id", "dt", pl.col("n").cast(pl.Float64).alias("value")
    )


def pageview_label() -> tuple[pl.DataFrame, set[str]]:
    """The primary label series (es+pt pageviews per unit and day) and the mapped units."""
    wd = pl.read_parquet(gold("topic_wikidata"))
    pv = pl.read_parquet(gold("wiki_pageviews_daily"))
    if pv.schema["dt"] == pl.String:
        pv = pv.with_columns(pl.col("dt").str.to_date())
    m = wd.filter(
        pl.col("qid").is_not_null()
        & (pl.col("article_es").is_not_null() | pl.col("article_pt").is_not_null())
    ).select(pl.col("topic_id").alias("unit_id"), "qid")
    v = (
        pv.filter(pl.col("project").is_in(["es.wikipedia", "pt.wikipedia"]))
        .group_by("qid", "dt")
        .agg(pl.col("views").sum().cast(pl.Float64).alias("value"))
    )
    return m.join(v, on="qid").select("unit_id", "dt", "value"), set(m["unit_id"].to_list())


def run(label: str = "pageviews") -> Result:
    s, raw, roll = scored_units()
    if label == "pageviews":
        daily, mapped = pageview_label()
    else:
        daily = gdelt_espt_label(roll)
        mapped = set(s["unit_id"].to_list())
    return evaluate(s, raw, daily, mapped, label)


# --- report ---------------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render(res: Result) -> str:
    gen = dt.datetime.now(dt.UTC).astimezone(dt.timezone(dt.timedelta(hours=-5)))
    lines = [
        "# Backtest: the radar's weekly top 10 against es+pt Wikipedia attention",
        "",
        f"Generated {gen:%Y-%m-%d %H:%M} UTC-5 by `models/backtest.py` on the `{profile()}` "
        f"profile; label `{res.label}`. Every number below is **measured** on the lake unless "
        "marked otherwise. Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) "
        "and the module docstring.",
        "",
        "## Coverage",
        "",
        f"- Units in the ranked universe: {res.n_units}; with an es or pt Wikipedia article: "
        f"{res.n_mapped_units} (measured). Unmapped unit-weeks, not ranked by the backtest: "
        f"{res.n_unmapped_rows} (measured).",
        f"- Coverage: {res.n_mapped_units} / {res.n_units} ranked units have an es or pt "
        f"Wikipedia article ({_pct(res.n_mapped_units / max(res.n_units, 1))}, measured); the "
        "backtest ranks those only.",
        f"- Evaluable weeks: {len(res.weeks)} (measured): {', '.join(res.weeks) or 'none'}.",
        "- Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build (no lake table "
        "maps gkg_id to topics yet); the backtest does not use them.",
    ]
    for w, why in sorted(res.excluded.items()):
        lines.append(f"  - {w} excluded: {why}.")
    if not res.weeks:
        lines += [
            "",
            "## Result",
            "",
            "No week is evaluable, so there is no precision@10 or lead time to report.",
        ]
        return "\n".join(lines) + "\n"
    pw = res.per_week
    lines += [
        f"- Mapped units with a label per evaluable week: {int(pw['n_mapped'].min())}.."
        f"{int(pw['n_mapped'].max())} (measured).",
        "",
        "## Precision@10",
        "",
        "| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |",
        "|---|---|---|---|",
    ]
    names = {
        "radar": "Radar (Priority)",
        "raw_count_growth": "Baseline: raw-count growth",
        "persistence": "Baseline: persistence (the label's own last 2 weeks)",
        "base_rate": "Base rate (top quartile by construction)",
    }
    for key in ("radar", "raw_count_growth", "persistence", "base_rate"):
        e = res.pooled[key]
        ci = e.get("ci")
        ci_s = f"{_pct(ci[0])} .. {_pct(ci[1])}" if ci else "n/a"
        if key == "base_rate":
            ci_s = "n/a"
        elif ci is None:
            ci_s = f"n/a (fewer than {MIN_WEEKS_FOR_INTERVAL} weeks)"
        lines.append(
            f"| {names[key]} | {e['hits']}/{e['total']} | {_pct(e['precision'])} (measured) "
            f"| {ci_s} |"
        )
    lines += ["", "Radar minus baseline, in precision points (paired bootstrap over weeks):", ""]
    beats = []
    for b, e in res.diffs.items():
        ci = e.get("ci")
        ci_s = f", 95% interval {_pct(ci[0])} .. {_pct(ci[1])}" if ci else ", no interval"
        lines.append(f"- vs. {names[b]}: {_pct(e['diff'])}{ci_s} (measured).")
        beats.append(ci is not None and ci[0] > 0)
    lines += ["", "## Lead time", ""]
    if res.leads:
        ci_s = (
            f", 95% bootstrap interval {res.lead_ci[0]:.1f} .. {res.lead_ci[1]:.1f}"
            if res.lead_ci
            else ""
        )
        lines.append(
            f"Median weeks from the first flag to the es+pt pageview peak within {LEAD_WEEKS} "
            f"weeks: {median(res.leads):.1f}{ci_s}, over {len(res.leads)} flagged positives "
            "(measured)."
        )
    else:
        lines.append(
            f"No flagged positive has {LEAD_WEEKS} complete weeks of pageviews after it, so "
            "there is no lead time to report."
        )
    lines += ["", "## Verdict", ""]
    if all(beats):
        lines.append(
            "The radar beats both baselines: the lower end of both paired intervals is above "
            "zero (measured)."
        )
    else:
        lines.append(
            "**The radar does not beat both baselines on this backtest**: at least one paired "
            "interval reaches zero or below, or there are too few weeks for an interval "
            "(measured)."
        )
        lines += ["", "Diagnosis:", ""] + diagnosis(res)
    hook = bool(res.lead_ci) and median(res.leads) >= 1 and res.lead_ci[0] > 0
    lines += [
        "",
        "## Hook",
        "",
        (
            f"The lead-time hook is supported: median {median(res.leads):.1f} weeks with an "
            "interval above zero."
            if hook
            else "The lead-time hook is not supported by this backtest; the page uses the "
            "fallback hook."
        ),
        "",
        "## Per week",
        "",
        "| Week | Mapped | Positives | Radar | Raw-count growth | Persistence |",
        "|---|---|---|---|---|---|",
    ]
    for r in pw.iter_rows(named=True):
        lines.append(
            f"| {r['week']} | {r['n_mapped']} | {r['n_pos']} | {r['hits_radar']}/10 "
            f"| {r['hits_raw_count_growth']}/10 | {r['hits_persistence']}/10 |"
        )
    return "\n".join(lines) + "\n"


def diagnosis(res: Result) -> list[str]:
    pw = res.per_week
    out = []
    n = len(res.weeks)
    if n < MIN_WEEKS_FOR_INTERVAL:
        out.append(f"- Only {n} evaluable weeks; below {MIN_WEEKS_FOR_INTERVAL} no interval.")
    radar = pw["hits_radar"].to_list()
    rates = (pw["n_pos"] / pw["n_mapped"]).to_list()
    low = sum(1 for r, p in zip(radar, rates, strict=True) if r / TOP_K <= p)
    out.append(
        f"- Radar hits per week range {min(radar)}..{max(radar)} of {TOP_K}; weeks at or below "
        f"the base rate: {low} of {n} (measured)."
    )
    overlap = [
        len(set(a) & set(b))
        for a, b in zip(pw["top_radar"].to_list(), pw["top_persistence"].to_list(), strict=True)
    ]
    out.append(
        f"- Overlap between the radar's and persistence's top 10: median {median(overlap):.0f} "
        "units a week (measured)."
    )
    out.append(
        "- The weights and thresholds of the scores are hand-set placeholders (estimate), not "
        "fitted to this label."
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", choices=["pageviews", "gdelt_espt"], default="pageviews")
    args = ap.parse_args(argv)
    res = run(args.label)
    text = render(res)
    if profile() == "full":
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT}")  # noqa: T201
    else:
        print("dev profile: numbers are never reported; not writing the report")  # noqa: T201
        print(text)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
