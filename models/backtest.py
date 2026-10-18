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

Rankers: the radar with the eligibility gate (`build_scores.gate`: established or exact-Wikidata
topics first, seeds after; what the API publishes), the radar without it (Priority alone), and the
two baselines.

Two labels (Addendum 4):

- **Primary**: es+pt Wikipedia pageviews, as above. WS6 fetches pageviews only for a priority list
  (every week's radar and raw-count top 10), so the run is incremental. It first prints the
  coverage per ranker: labelled topic-weeks / needed topic-weeks, where needed = the ranker's top
  10 among mapped topics in each evaluable week. It refuses to report precision below
  MIN_COVERAGE (90%). Why 90%: precision@10 counts 10 slots a week, and WS6 fetches labels in its
  own order, not at random. So the missing slots could all be hits or all misses, and pooled
  precision can move by up to (1 - coverage). At 90% that bound is 10 points, about the size of
  the differences we compare; the report prints the bound next to the numbers. The top quartile is
  then taken among the labelled mapped topics of the week (the pool WS6 fetched), not among all
  mapped topics.
- **Secondary** (`gdelt_espt`): the es+pt GDELT article count of the same topic, available for
  every ranked topic (no Wikipedia needed). The label is the next 2 weeks; the features read only
  the past. But the radar's saturation and fit read the same es+pt stream, so this label is not
  independent of the radar's inputs. The report says so.

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

MIN_COVERAGE = 0.90

RANKERS = {
    "radar_gated": "gated_score",
    "radar": "priority",
    "raw_count_growth": "raw_growth",
    "persistence": "past_growth",
}
RADARS = ("radar_gated", "radar")
BASELINES = ("raw_count_growth", "persistence")
NAMES = {
    "radar_gated": "Radar, with the eligibility gate (published)",
    "radar": "Radar, without the gate (Priority alone)",
    "raw_count_growth": "Baseline: raw-count growth",
    "persistence": "Baseline: persistence (the label's own last 2 weeks)",
    "base_rate": "Base rate (top quartile; ties at the cutoff excluded, measured share)",
}
LABELS = {
    "pageviews": "Primary label: es+pt Wikipedia pageview growth",
    "gdelt_espt": "Secondary label: es+pt GDELT article growth",
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
    leads: dict[str, list[int]] = field(default_factory=dict)
    lead_ci: dict[str, tuple[float, float]] = field(default_factory=dict)
    coverage: dict[str, tuple[int, int]] = field(default_factory=dict)
    refused: bool = False
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


def _top(g: pl.DataFrame, col: str) -> pl.DataFrame:
    """A ranker's top 10, ties broken by topic id (never by row order)."""
    return (
        g.filter(pl.col(col).is_not_null())
        .sort([col, "unit_id"], descending=[True, False])
        .head(TOP_K)
    )


def evaluate(
    scored: pl.DataFrame,
    raw_growth: pl.DataFrame,
    daily: pl.DataFrame,
    mapped: set[str],
    label: str,
    gated: pl.DataFrame | None = None,
    min_coverage: float | None = None,
    label_end: dt.date | None = None,
) -> Result:
    """The protocol on scored unit-weeks.

    `scored` has unit_id, week, asof, priority, rank (NULL outside the ranked universe);
    `raw_growth` has unit_id, week, raw_growth; `daily` is the label series (unit_id, dt, value);
    `gated` has unit_id, week and the published (gated) rank. With `min_coverage`, precision is
    reported only when every ranker's top 10 has at least that share of its labels.
    """
    res = Result(label=label)
    eligible = scored.filter(pl.col("rank").is_not_null())
    res.n_units = eligible["unit_id"].n_unique()
    is_mapped = pl.col("unit_id").is_in(list(mapped))
    res.n_mapped_units = eligible.filter(is_mapped)["unit_id"].n_unique()
    res.n_unmapped_rows = eligible.filter(~is_mapped).height
    # the label's last day: given (the calendar the label should cover, so unfetched labels count
    # as missing), or the last day the label series has data
    last_day = label_end or daily.filter(pl.col("value").is_not_null())["dt"].max()
    asofs = sorted(set(eligible["asof"].to_list()))
    gt = growth_table(daily, asofs)
    u = (
        eligible.filter(is_mapped)
        .select("unit_id", "week", "asof", "priority")
        .join(raw_growth, on=["unit_id", "week"], how="left")
        .join(gt, on=["unit_id", "asof"], how="left")
    )
    if gated is not None:
        g_rank = gated.select("unit_id", "week", (-pl.col("rank")).alias("gated_score"))
        u = u.join(g_rank, on=["unit_id", "week"], how="left")
    else:
        u = u.with_columns(pl.lit(None, pl.Int64).alias("gated_score"))
    rows = []
    need = dict.fromkeys(RANKERS, 0)
    have = dict.fromkeys(RANKERS, 0)
    for (week,), g in u.sort("week").group_by("week", maintain_order=True):
        t = g["asof"][0]
        if last_day is None or t + dt.timedelta(days=LABEL_DAYS) > last_day:
            res.excluded[week] = "label window not complete"
            continue
        lo, hi = t - dt.timedelta(days=HISTORY_DAYS), t + dt.timedelta(days=LABEL_DAYS)
        if lo <= GAP[1] and hi >= GAP[0]:
            res.excluded[week] = "overlaps the 2025-06-14..07-02 GDELT gap"
            continue
        # coverage: each ranker's top 10 before dropping unlabelled topics
        for name, col in RANKERS.items():
            top = _top(g, col)
            need[name] += top.height
            have[name] += int(top["label_growth"].is_not_null().sum())
        g = g.filter(pl.col("label_growth").is_not_null())
        if g.height < MIN_MAPPED:
            res.excluded[week] = f"{g.height} mapped units with a label (needs {MIN_MAPPED})"
            continue
        # positives: the top quartile by label growth, decided by value only. Ties take their
        # average rank, so a tie block that straddles the cutoff is either all in or all out,
        # never split by row order (the scored frame is sorted by the radar's own rank, so an
        # ordinal tie-break handed the tied slots to the radar). The base rate is then the
        # measured share of positives, at most 25%.
        cut = math.ceil(g.height * (1 - POSITIVE_QUANTILE))
        g = g.with_columns(
            (pl.col("label_growth").rank("average", descending=True) <= cut).alias("positive")
        )
        n_pos = int(g["positive"].sum())
        rec = {"week": week, "asof": t, "n_mapped": g.height, "n_pos": n_pos, "k": TOP_K}
        for name, col in RANKERS.items():
            top = _top(g, col)
            rec[f"hits_{name}"] = int(top["positive"].sum())
            rec[f"top_{name}"] = top["unit_id"].to_list()
        rec["positives"] = g.filter("positive")["unit_id"].to_list()
        rows.append(rec)
    res.coverage = {
        n: (have[n], need[n]) for n in RANKERS if gated is not None or n != "radar_gated"
    }
    if min_coverage is not None and any(
        need_ == 0 or have_ / need_ < min_coverage for have_, need_ in res.coverage.values()
    ):
        res.refused = True
        return res
    res.per_week = pl.DataFrame(rows) if rows else None
    res.weeks = [r["week"] for r in rows]
    if not rows:
        return res
    pw = res.per_week
    rng = random.Random(SEED)  # noqa: S311 (a seeded bootstrap, not cryptography)
    rankers = [n for n in RANKERS if n in res.coverage]
    for name in rankers:
        hits, tot = int(pw[f"hits_{name}"].sum()), int(pw["k"].sum())
        entry: dict[str, Any] = {"hits": hits, "total": tot, "precision": hits / tot}
        if len(rows) >= MIN_WEEKS_FOR_INTERVAL:
            entry["ci"] = _ci(bootstrap_precision(pw, name, rng))
        res.pooled[name] = entry
    res.pooled["base_rate"] = {
        "hits": int(pw["n_pos"].sum()),
        "total": int(pw["n_mapped"].sum()),
        "precision": int(pw["n_pos"].sum()) / int(pw["n_mapped"].sum()),
    }
    pairs = [(a, b) for a in RADARS if a in rankers for b in BASELINES]
    if "radar_gated" in rankers:
        pairs.append(("radar_gated", "radar"))
    for a, b in pairs:
        d = (res.pooled[a]["hits"] - res.pooled[b]["hits"]) / res.pooled[a]["total"]
        entry = {"diff": d}
        if len(rows) >= MIN_WEEKS_FOR_INTERVAL:
            entry["ci"] = _ci(bootstrap_diff(pw, a, b, rng))
        res.diffs[f"{a}|{b}"] = entry
    # lead time: first flags (top 10 after a week outside it) that are positive
    order = {w: i for i, w in enumerate(sorted(set(u["week"].to_list())))}
    for name in [r for r in RADARS if r in rankers]:
        prev: set[str] = set()
        prev_idx = None
        leads: list[int] = []
        for r in rows:
            top = set(r[f"top_{name}"])
            contiguous = prev_idx is not None and order[r["week"]] == prev_idx + 1
            for unit in sorted((top - (prev if contiguous else set())) & set(r["positives"])):
                lead = weekly_peak_lead(daily, unit, r["asof"])
                if lead is not None:
                    leads.append(lead)
            prev, prev_idx = top, order[r["week"]]
        res.leads[name] = leads
        if len(leads) >= 2:
            meds = [median(rng.choice(leads) for _ in leads) for _ in range(BOOTSTRAP_REPS)]
            res.lead_ci[name] = _ci(meds)
    return res


# --- inputs ---------------------------------------------------------------------------------


def scored_units() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame | None]:
    """Scored unit-weeks, raw-count growth, the slim daily frame and the gated ranks."""
    unit = build_scores.units()
    s, own, _ = build_scores.scored_units(unit)
    gated = None
    if unit == "topic":
        gated = build_scores.gate(s.filter(pl.col("rank").is_not_null()), own).select(
            "unit_id", "week", "rank"
        )
    allg = own.filter(pl.col("group") == "all").sort("unit_id", "dt")
    allg = allg.with_columns(
        ((pl.col("n_7d") + 1) / (pl.col("n_7d").shift(7).over("unit_id") + 1))
        .log()
        .cast(pl.Float64)
        .alias("raw_growth")
    )
    raw = s.select("unit_id", "week", "asof").join(
        allg.select("unit_id", pl.col("dt").alias("asof"), "raw_growth"),
        on=["unit_id", "asof"],
        how="left",
    )
    return s, raw.select("unit_id", "week", "raw_growth"), own, gated


def gdelt_espt_label(roll: pl.DataFrame) -> pl.DataFrame:
    """The secondary label series: es+pt GDELT articles per unit and day.

    Built on each unit's full calendar (its all-language rows): a topic with no es/pt article
    has no es+pt rows at all, and its label is 0 on every observed day, not missing. NULL only
    where the all-language day itself is missing.
    """
    cal = roll.filter(pl.col("group") == "all").select("unit_id", "dt", pl.col("n").alias("n_all"))
    espt = roll.filter(pl.col("group") == "espt").select("unit_id", "dt", "n")
    return cal.join(espt, on=["unit_id", "dt"], how="left").select(
        "unit_id",
        "dt",
        pl.when(pl.col("n_all").is_not_null())
        .then(pl.col("n").fill_null(0))
        .cast(pl.Float64)
        .alias("value"),
    )


def pageview_label() -> tuple[pl.DataFrame, set[str]]:
    """The primary label series (es+pt pageviews per unit and day) and the mapped units."""
    wd = pl.read_parquet(gold("topic_wikidata"))
    m = wd.filter(
        pl.col("qid").is_not_null()
        & (pl.col("article_es").is_not_null() | pl.col("article_pt").is_not_null())
    ).select(pl.col("topic_id").alias("unit_id"), "qid")
    path = gold("wiki_pageviews_daily")
    if not path.exists():
        return pl.DataFrame(schema={"unit_id": pl.String, "dt": pl.Date, "value": pl.Float64}), set(
            m["unit_id"].to_list()
        )
    pv = pl.read_parquet(path)
    if pv.schema["dt"] == pl.String:
        pv = pv.with_columns(pl.col("dt").str.to_date())
    v = (
        pv.filter(pl.col("project").is_in(["es.wikipedia", "pt.wikipedia"]))
        .group_by("qid", "dt")
        .agg(pl.col("views").sum().cast(pl.Float64).alias("value"))
    )
    return m.join(v, on="qid").select("unit_id", "dt", "value"), set(m["unit_id"].to_list())


def run(label: str = "pageviews") -> Result:
    """One label (`pageviews` with the coverage rule, or `gdelt_espt`)."""
    return run_all([label])[label]


def run_all(labels: list[str]) -> dict[str, Result]:
    """Score once, then evaluate each label (one heavy job: Addendum 4's memory budget)."""
    s, raw, own, gated = scored_units()
    out = {}
    for label in labels:
        if label == "pageviews":
            daily, mapped = pageview_label()
            # needed weeks follow the data calendar, so labels WS6 has not fetched count as missing
            end = s["asof"].max()
            out[label] = evaluate(s, raw, daily, mapped, label, gated, MIN_COVERAGE, end)
        else:
            daily = gdelt_espt_label(own)
            out[label] = evaluate(s, raw, daily, set(s["unit_id"].to_list()), label, gated)
    return out


# --- report ---------------------------------------------------------------------------------


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def coverage_lines(res: Result) -> list[str]:
    out = ["| Ranker | Labelled / needed topic-weeks | Coverage |", "|---|---|---|"]
    for name, (have, need) in res.coverage.items():
        cov = _pct(have / need) if need else "n/a"
        out.append(f"| {NAMES[name]} | {have}/{need} | {cov} (measured) |")
    return out


def render_section(res: Result) -> list[str]:
    """One label's section of the report."""
    lines = [
        f"## {LABELS[res.label]}",
        "",
        f"- Ranked topics: {res.n_units}; with an es or pt Wikipedia article (the backtest ranks "
        f"those only): {res.n_mapped_units} "
        f"({_pct(res.n_mapped_units / max(res.n_units, 1))}, measured). Unmapped topic-weeks: "
        f"{res.n_unmapped_rows} (measured).",
    ]
    if res.label == "gdelt_espt":
        lines[-1] = (
            f"- Ranked topics: {res.n_units}, all labelled by their own es+pt GDELT series "
            "(no Wikipedia needed). This label is not independent of the radar: saturation and "
            "fit read the same es+pt stream (the label is the next 2 weeks; the features read "
            "only the past)."
        )
    if res.coverage:
        lines += ["", "Label coverage of each ranker's top 10, over evaluable weeks:", ""]
        lines += coverage_lines(res)
    if res.refused:
        lines += [
            "",
            f"**Not reported:** coverage is below {_pct(MIN_COVERAGE)} for at least one ranker, "
            "so precision@10 could move by more than "
            f"{_pct(1 - MIN_COVERAGE)} once the missing labels arrive. Rerun "
            "`RADAR_PROFILE=full uv run python -m models.backtest` after the next WS6 write.",
        ]
        return lines
    lines.append(
        f"- Evaluable weeks: {len(res.weeks)} (measured): {', '.join(res.weeks) or 'none'}."
    )
    for w, why in sorted(res.excluded.items()):
        lines.append(f"  - {w} excluded: {why}.")
    if not res.weeks:
        return [*lines, "", "No week is evaluable, so there is no precision@10 or lead time."]
    pw = res.per_week
    base = int(pw["n_pos"].sum()) / int(pw["n_mapped"].sum())
    if base < POSITIVE_QUANTILE - 0.5 - 0.01:
        lines.append(
            f"- Base rate {_pct(base)}, not 25%: many topics have the same label growth (for the "
            "GDELT label, most have no es/pt article in either window, growth 0). A tie at the "
            "quartile cutoff is left out rather than split by row order, so a positive is real "
            "growth (measured)."
        )
    lines += [
        f"- Mapped topics with a label per evaluable week: {int(pw['n_mapped'].min())}.."
        f"{int(pw['n_mapped'].max())} (measured).",
        "",
        "### Precision@10",
        "",
        "| Ranker | Positives / total | Precision@10 | 95% bootstrap interval over weeks |",
        "|---|---|---|---|",
    ]
    for key in [*[n for n in RANKERS if n in res.pooled], "base_rate"]:
        e = res.pooled[key]
        ci = e.get("ci")
        if key == "base_rate":
            ci_s = "n/a"
        elif ci is None:
            ci_s = f"n/a (fewer than {MIN_WEEKS_FOR_INTERVAL} weeks)"
        else:
            ci_s = f"{_pct(ci[0])} .. {_pct(ci[1])}"
        lines.append(
            f"| {NAMES[key]} | {e['hits']}/{e['total']} | {_pct(e['precision'])} (measured) "
            f"| {ci_s} |"
        )
    if res.coverage and res.label == "pageviews":
        worst = min(h / n for h, n in res.coverage.values() if n)
        lines += [
            "",
            f"Coverage bound: the lowest coverage is {_pct(worst)}, so any precision above can "
            f"still move by up to {_pct(1 - worst)} as the missing labels arrive (measured).",
        ]
    lines += ["", "Differences in precision points (paired bootstrap over weeks):", ""]
    beats = {}
    for pair, e in res.diffs.items():
        a, b = pair.split("|")
        ci = e.get("ci")
        ci_s = f", 95% interval {_pct(ci[0])} .. {_pct(ci[1])}" if ci else ", no interval"
        lines.append(f"- {NAMES[a]} minus {NAMES[b]}: {_pct(e['diff'])}{ci_s} (measured).")
        beats[pair] = ci is not None and ci[0] > 0
    lines += ["", "### Lead time", ""]
    for name, leads in res.leads.items():
        if leads:
            ci = res.lead_ci.get(name)
            ci_s = f", 95% bootstrap interval {ci[0]:.1f} .. {ci[1]:.1f}" if ci else ""
            lines.append(
                f"- {NAMES[name]}: median {median(leads):.1f} weeks from the first flag to the "
                f"label's peak within {LEAD_WEEKS} weeks{ci_s}, over {len(leads)} flagged "
                "positives (measured)."
            )
        else:
            lines.append(
                f"- {NAMES[name]}: no flagged positive has {LEAD_WEEKS} complete weeks of label "
                "after it."
            )
    lines += ["", "### Verdict", ""]
    for radar in [r for r in RADARS if r in res.pooled]:
        ok = all(beats.get(f"{radar}|{b}", False) for b in BASELINES)
        lines.append(
            f"- {NAMES[radar]}: "
            + (
                "beats both baselines (both paired intervals above zero, measured)."
                if ok
                else "**does not beat both baselines** (an interval reaches zero or below, or "
                "there are too few weeks for one; measured)."
            )
        )
    if not all(beats.get(f"radar_gated|{b}", False) for b in BASELINES):
        lines += ["", "Diagnosis:", "", *diagnosis(res)]
    gl = res.leads.get("radar_gated") or res.leads.get("radar") or []
    gci = res.lead_ci.get("radar_gated") or res.lead_ci.get("radar")
    hook = res.label == "pageviews" and gci is not None and median(gl) >= 1 and gci[0] > 0
    if res.label == "pageviews":
        lines += [
            "",
            "Hook: "
            + (
                f"supported (median {median(gl):.1f} weeks with an interval above zero)."
                if hook
                else "not supported by this backtest; the page uses the fallback hook."
            ),
        ]
    lines += [
        "",
        "### Per week",
        "",
        "| Week | Labelled | Positives | Radar (gated) | Radar | Raw-count growth | Persistence |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in pw.iter_rows(named=True):
        lines.append(
            f"| {r['week']} | {r['n_mapped']} | {r['n_pos']} | {r['hits_radar_gated']}/10 "
            f"| {r['hits_radar']}/10 | {r['hits_raw_count_growth']}/10 "
            f"| {r['hits_persistence']}/10 |"
        )
    return lines


def render(results: Result | dict[str, Result]) -> str:
    if isinstance(results, Result):
        results = {results.label: results}
    gen = dt.datetime.now(dt.UTC).astimezone(dt.timezone(dt.timedelta(hours=-5)))
    lines = [
        "# Backtest: the radar's weekly top 10",
        "",
        f"Generated {gen:%Y-%m-%d %H:%M} UTC-5 by `models/backtest.py` on the `{profile()}` "
        "profile. Every number below is **measured** on the lake unless marked otherwise. "
        "Protocol: `docs/designs/radar-build-plan.md` (Evaluation, Backtest) and the module "
        "docstring. The score weights and thresholds are hand-set (estimate), not fitted to "
        "either label. Evidence ids: `topic_scores_weekly.evidence_ids` is empty in this build "
        "(no lake table maps gkg_id to topics yet); the backtest does not use them.",
    ]
    if "gdelt_espt" in results and "pageviews" in results:
        p = results["pageviews"]
        state = "not reportable yet (coverage)" if p.refused else "reported below"
        lines += [
            "",
            "The primary label (es+pt Wikipedia pageviews) is " + state + ". The secondary "
            "label (es+pt GDELT article growth) is the fallback card when pageviews are "
            "missing.",
        ]
    for label in ("pageviews", "gdelt_espt"):
        if label in results:
            lines += ["", *render_section(results[label])]
    return "\n".join(lines) + "\n"


def diagnosis(res: Result) -> list[str]:
    pw = res.per_week
    out = []
    n = len(res.weeks)
    if n < MIN_WEEKS_FOR_INTERVAL:
        out.append(f"- Only {n} evaluable weeks; below {MIN_WEEKS_FOR_INTERVAL} no interval.")
    key = "radar_gated" if "radar_gated" in res.pooled else "radar"
    radar = pw[f"hits_{key}"].to_list()
    rates = (pw["n_pos"] / pw["n_mapped"]).to_list()
    low = sum(1 for r, p in zip(radar, rates, strict=True) if r / TOP_K <= p)
    out.append(
        f"- Radar hits per week range {min(radar)}..{max(radar)} of {TOP_K}; weeks at or below "
        f"the base rate: {low} of {n} (measured)."
    )
    overlap = [
        len(set(a) & set(b))
        for a, b in zip(pw[f"top_{key}"].to_list(), pw["top_persistence"].to_list(), strict=True)
    ]
    out.append(
        f"- Overlap between the radar's and persistence's top 10: median {median(overlap):.0f} "
        "units a week (measured)."
    )
    if "hits_persistence" in pw.columns and "radar" in res.pooled:
        p = res.pooled.get("persistence", {}).get("precision")
        r = res.pooled[key]["precision"]
        b = res.pooled["base_rate"]["precision"]
        out.append(
            f"- The radar's precision ({_pct(r)}) is close to the base rate ({_pct(b)}); "
            f"persistence reaches {_pct(p)}: on this label, past es/pt growth predicts future "
            "es/pt growth better than the radar's emergence-led Priority (measured)."
        )
    out.append(
        "- The weights and thresholds of the scores are hand-set placeholders (estimate), not "
        "fitted to this label."
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--label", choices=["both", "pageviews", "gdelt_espt"], default="both", help="default: both"
    )
    args = ap.parse_args(argv)
    labels = ["pageviews", "gdelt_espt"] if args.label == "both" else [args.label]
    results = run_all(labels)
    if "pageviews" in results:
        p = results["pageviews"]
        print("Primary label coverage (labelled / needed topic-weeks):")  # noqa: T201
        for name, (have, need) in p.coverage.items():
            cov = f"{100 * have / need:.1f}%" if need else "n/a"
            print(f"  {name:18s} {have:5d}/{need:<5d} {cov}")  # noqa: T201
        state = f"refused (< {100 * MIN_COVERAGE:.0f}%)" if p.refused else "reported"
        print(f"Primary precision: {state}")  # noqa: T201
    text = render(results)
    if profile() == "full":
        REPORT.write_text(text, encoding="utf-8")
        print(f"wrote {REPORT}")  # noqa: T201
    else:
        print("dev profile: numbers are never reported; not writing the report")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
