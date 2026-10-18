"""Daily rolling features per ranked unit and language group, ported from the S8 view.

`bq_sql/s8_daily_topic_rolling.sql` computes the rolling features per subtopic x language x LatAm
in BigQuery. The scores need the same features at other grains (a subtopic over all languages, the
English bucket against es+pt for the window chip, and WS1's per-topic series), so this module
recomputes them in Python with the same definitions. `tests/test_features.py` checks the port
against the real view on the dev slice.

Missing days (``daily_totals.is_missing``) stay NULL, never 0: every window ignores them.
"""

from __future__ import annotations

import polars as pl

from radar.paths import gold

# Language groups the scores read. A group's day is missing when any member stream is missing.
LANG_GROUPS: dict[str, tuple[str, ...]] = {
    "all": ("eng", "spa", "por", "other"),
    "eng": ("eng",),
    "espt": ("spa", "por"),
}

# Additive daily columns a unit series carries (NULL-able tone columns stay NULL when unknown).
COUNT_COLS = ("n", "n_sources", "n_tone", "sum_tone", "sum_polarity", "n_pos_x", "n_neg_x")

TONE_COLS = ("n_tone", "sum_tone", "sum_polarity", "n_pos_x", "n_neg_x")

EPS = 1e-7  # the S8 view's guard in ln(share_7d / share_7d a week ago)

# Robust z (orchestrator's addendum): the view's z_7d reaches 50 for low-volume subtopics, whose
# 28-day baseline SD is tiny (measured on the dev slice: regulation_policy, spa, 2026-09-17).
# `z_7d_r` and `z_dow_r` floor the SD at SD_FLOOR_REL x the baseline mean (a 10% rise over the
# baseline is at most z = 1; hand-set, estimate), and `z_7d_r` needs MIN_BASE_DAYS baseline days.
# The scores and the window chip read the robust columns; `z_7d`/`z_dow` stay as the view has them.
SD_FLOOR_REL = 0.1
MIN_BASE_DAYS = 14


def _floor(sd: pl.Expr, mean: pl.Expr) -> pl.Expr:
    floor = SD_FLOOR_REL * mean.abs()
    out = pl.max_horizontal(sd, floor)
    return pl.when(out > 0).then(out)


def _as_date(df: pl.DataFrame, col: str = "dt") -> pl.DataFrame:
    if df.schema[col] == pl.Date:
        return df
    return df.with_columns(pl.col(col).str.to_date())


def load_totals() -> pl.DataFrame:
    """`daily_totals` for the active profile, with `dt` as a date."""
    return _as_date(pl.read_parquet(gold("daily_totals")))


def subtopic_daily() -> pl.DataFrame:
    """`daily_topic` (subtopics and ai_all) as unit series: one row per unit x stream x day.

    The LatAm split is summed away; `n_latam` keeps the LatAm part for the audience-fit score.
    """
    d = _as_date(pl.read_parquet(gold("daily_topic")))
    if "segment" in d.columns:
        d = d.filter(pl.col("segment") == "ai")
    return (
        d.group_by("topic", "lang_bucket", "dt")
        .agg(
            pl.col("n_articles").sum().alias("n"),
            # distinct sources are not additive across the LatAm split; the larger part is a floor
            pl.col("n_sources").max(),
            *(pl.col(c).sum() for c in TONE_COLS),
            pl.col("n_articles").filter(pl.col("latam")).sum().alias("n_latam"),
        )
        .rename({"topic": "unit_id"})
    )


def topic_daily() -> pl.DataFrame:
    """WS1's `topic_daily` (entity and theme topics) as unit series.

    The contract carries mean tone and polarity but not the tail counts, so `n_pos_x`/`n_neg_x`
    (and with them controversy) are NULL at topic level; tone sums are rebuilt from the means.
    """
    d = _as_date(pl.read_parquet(gold("topic_daily")))
    if "segment" in d.columns:
        d = d.filter(pl.col("segment") == "ai")
    tone_ok = pl.col("mean_tone").is_not_null()
    return (
        d.group_by("topic_id", "lang_bucket", "dt")
        .agg(
            pl.col("n_articles").sum().alias("n"),
            pl.col("n_articles").filter(tone_ok).sum().alias("n_tone"),
            (pl.col("mean_tone") * pl.col("n_articles")).sum().alias("sum_tone"),
            (pl.col("mean_polarity") * pl.col("n_articles")).sum().alias("sum_polarity"),
        )
        .with_columns(
            pl.lit(None, pl.Int64).alias("n_sources"),
            pl.lit(None, pl.Int64).alias("n_pos_x"),
            pl.lit(None, pl.Int64).alias("n_neg_x"),
            pl.lit(None, pl.Int64).alias("n_latam"),
        )
        .rename({"topic_id": "unit_id"})
    )


def group_totals(totals: pl.DataFrame, groups: dict[str, tuple[str, ...]]) -> pl.DataFrame:
    """Stream totals per language group on a complete calendar (absent days are missing)."""
    out = []
    lo, hi = totals["dt"].min(), totals["dt"].max()
    calendar = pl.DataFrame({"dt": pl.date_range(lo, hi, "1d", eager=True)})
    for name, members in groups.items():
        t = (
            totals.filter(pl.col("lang_bucket").is_in(members))
            .group_by("dt")
            .agg(
                pl.col("n_all").sum(),
                pl.col("is_missing").any(),
                pl.len().alias("n_streams"),
            )
        )
        t = calendar.join(t, on="dt", how="left").with_columns(
            (
                pl.col("is_missing").fill_null(True)
                | (pl.col("n_streams").fill_null(0) < len(members))
            ).alias("is_missing"),
            pl.lit(name).alias("group"),
        )
        out.append(t.select("group", "dt", "n_all", "is_missing"))
    return pl.concat(out)


def rolling(
    daily: pl.DataFrame,
    totals: pl.DataFrame,
    groups: dict[str, tuple[str, ...]] | None = None,
    key: str = "unit_id",
    stream: str = "lang_bucket",
) -> pl.DataFrame:
    """The S8 features per (`key`, language group, day).

    `daily` holds one row per `key` x `stream` x `dt` with the columns in `COUNT_COLS` (and
    optionally `n_latam`); `totals` is `daily_totals`. Pass ``groups={b: (b,) ...}`` to get the
    per-stream view S8 computes.
    """
    groups = groups or LANG_GROUPS
    gt = group_totals(totals, groups)
    extra = [c for c in ("n_latam",) if c in daily.columns]
    parts = []
    for name, members in groups.items():
        g = (
            daily.filter(pl.col(stream).is_in(members))
            .group_by(key, "dt")
            .agg(
                *(pl.col(c).sum() for c in ("n", "n_tone", "sum_tone", "sum_polarity")),
                # tail counts and sources stay NULL when the input never had them
                *(
                    pl.when(pl.col(c).is_not_null().any()).then(pl.col(c).sum())
                    for c in ("n_pos_x", "n_neg_x", "n_sources", *extra)
                ),
            )
            .with_columns(pl.lit(name).alias("group"))
        )
        parts.append(g)
    d = pl.concat(parts, how="diagonal_relaxed")
    keys = d.select(key, "group").unique()
    spine = keys.join(gt, on="group")
    has_tails = d["n_pos_x"].is_not_null().any()
    fill = dict.fromkeys(("n", "n_tone", "sum_tone", "sum_polarity"), 0)
    if has_tails:
        fill |= {"n_pos_x": 0, "n_neg_x": 0}
    f = spine.join(d, on=[key, "group", "dt"], how="left").with_columns(
        *(
            pl.when(pl.col("is_missing")).then(None).otherwise(pl.col(c).fill_null(v)).alias(c)
            for c, v in fill.items()
        ),
        pl.when(pl.col("is_missing")).then(None).otherwise(pl.col("n_all")).alias("n_all"),
        # the view fills absent days with 0 sources; inputs without sources stay NULL
        *(
            pl.when(pl.col("is_missing"))
            .then(None)
            .otherwise(pl.col(c).fill_null(0) if d[c].is_not_null().any() else pl.col(c))
            .alias(c)
            for c in ("n_sources", *extra)
        ),
    )
    by = [key, "group"]
    f = f.sort([*by, "dt"])

    def r7(c: str) -> pl.Expr:
        return pl.col(c).rolling_sum(7, min_samples=1).over(by)

    def lag28(c: str) -> pl.Expr:
        """Sum over the 28 days ending 7 days ago (days 34..7 back)."""
        return pl.col(c).rolling_sum(28, min_samples=1).shift(7).over(by)

    f = f.with_columns(
        (pl.col("n") / pl.col("n_all")).alias("share"),
        pl.col("n")
        .is_not_null()
        .cast(pl.Int32)
        .rolling_sum(7, min_samples=1)
        .over(by)
        .alias("valid7"),
        r7("n").alias("n7raw"),
        r7("n_all").alias("n_all7"),
        r7("n_tone").alias("n_tone7"),
        r7("sum_tone").alias("sum_tone7"),
        r7("sum_polarity").alias("sum_pol7"),
        r7("n_pos_x").alias("n_pos7"),
        r7("n_neg_x").alias("n_neg7"),
        r7("n_latam").alias("n_latam_7d") if extra else pl.lit(None, pl.Int64).alias("n_latam_7d"),
        (lag28("sum_tone") / pl.when(lag28("n_tone") != 0).then(lag28("n_tone"))).alias(
            "tone_prev28"
        ),
    )

    def safe_div(a: str, b: str) -> pl.Expr:
        return pl.col(a) / pl.when(pl.col(b) != 0).then(pl.col(b))

    ok7 = pl.col("valid7") >= 5
    f = f.with_columns(
        pl.when(ok7).then(pl.col("n7raw") * 7 / pl.col("valid7")).alias("n_7d"),
        pl.when(ok7).then(safe_div("n7raw", "n_all7")).alias("share_7d"),
        safe_div("sum_tone7", "n_tone7").alias("mean_tone_7d"),
        safe_div("sum_pol7", "n_tone7").alias("mean_polarity_7d"),
        safe_div("n_pos7", "n_tone7").alias("positive_share_7d"),
        safe_div("n_neg7", "n_tone7").alias("negative_share_7d"),
        *(pl.col("share").shift(k).over(by).alias(f"s_l{k}") for k in (7, 14, 21, 28)),
    )
    lags = [pl.col(f"s_l{k}") for k in (7, 14, 21, 28)]
    dow_n = pl.sum_horizontal(*(c.is_not_null().cast(pl.Int32) for c in lags))
    dow_mean = pl.mean_horizontal(*lags)
    dow_sd = (
        pl.sum_horizontal(*((c - dow_mean) ** 2 for c in lags)) / (dow_n - 1).cast(pl.Float64)
    ).sqrt()
    f = f.with_columns(
        pl.when(dow_n >= 3)
        .then((pl.col("share") - dow_mean) / pl.when(dow_sd != 0).then(dow_sd))
        .alias("z_dow"),
        pl.when(dow_n >= 3)
        .then((pl.col("share") - dow_mean) / _floor(dow_sd, dow_mean))
        .alias("z_dow_r"),
        (((pl.col("share_7d") + EPS) / (pl.col("share_7d").shift(7).over(by) + EPS)).log()).alias(
            "growth_7d_log"
        ),
        pl.col("share_7d").rolling_mean(28, min_samples=1).shift(7).over(by).alias("base_mean"),
        pl.col("share_7d").rolling_std(28, min_samples=2).shift(7).over(by).alias("base_sd"),
        pl.col("share_7d")
        .is_not_null()
        .cast(pl.Int32)
        .rolling_sum(28, min_samples=1)
        .shift(7)
        .over(by)
        .alias("base_n"),
    )
    f = f.with_columns(
        (
            (pl.col("share_7d") - pl.col("base_mean"))
            / pl.when(pl.col("base_sd") != 0).then(pl.col("base_sd"))
        ).alias("z_7d"),
        pl.when(pl.col("base_n") >= MIN_BASE_DAYS)
        .then(
            (pl.col("share_7d") - pl.col("base_mean"))
            / _floor(pl.col("base_sd"), pl.col("base_mean"))
        )
        .alias("z_7d_r"),
        (pl.col("growth_7d_log") - pl.col("growth_7d_log").shift(7).over(by)).alias("accel_7d"),
        pl.col("mean_tone_7d").abs().alias("extremity_7d"),
        (
            pl.min_horizontal(pl.lit(1.0), pl.col("mean_polarity_7d") / 10.5)
            * pl.max_horizontal(pl.lit(0.0), 1.0 - pl.col("mean_tone_7d").abs() / 3.0)
            * 2.0
            * pl.min_horizontal("positive_share_7d", "negative_share_7d")
        ).alias("controversy_7d"),
        (pl.col("mean_tone_7d") - pl.col("tone_prev28")).alias("tone_shift_7d"),
    )
    f = f.sort([*by, "dt"])
    return f.select(
        key, "group", "dt", "is_missing", "n", "n_all", "share", "n_sources", "n_latam_7d",
        "n_7d", "share_7d", "z_dow", "z_7d", "z_dow_r", "z_7d_r", "growth_7d_log", "accel_7d",
        "mean_tone_7d", "extremity_7d", "mean_polarity_7d", "positive_share_7d",
        "negative_share_7d", "controversy_7d", "tone_shift_7d",
    )  # fmt: skip


def self_z(col: str, by: list[str]) -> pl.Expr:
    """`col` against its own distribution over days 34..7 back, as the view computes z_7d.

    The frame must be sorted by `by` and `dt` on a complete calendar (what `rolling` returns).
    """
    base = pl.col(col).rolling_mean(28, min_samples=1).shift(7).over(by)
    sd = pl.col(col).rolling_std(28, min_samples=2).shift(7).over(by)
    return (pl.col(col) - base) / pl.when(sd != 0).then(sd)
