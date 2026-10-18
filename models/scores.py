"""The weekly scores per ranked unit: Emergence, Stage and Saturation, Audience fit, Emotional
charge, the framing angle and Priority (MASTER_PLAN §10 and §12). Code computes every score.

A unit is scored once per ISO week, on its as-of day: the last day of the week present in the
data (Sunday, or the latest day for the current week). All 7-day features end on that day.

Every threshold and weight lives in the tables below. Weights and thresholds are placeholders set
by hand (estimate), to be tuned on the backtest; none of them is a measured number.
"""

from __future__ import annotations

import polars as pl

from models import universe
from models.features import self_z

# The scores read the robust z (features.SD_FLOOR_REL); below, `z_7d` and `z_dow_7d` mean it.
Z, ZDOW = "z_7d_r", "z_dow_r"

# Ranked universe: >= `min_articles_week` (taxonomy, 20) ring-1 articles in the ISO week, counted
# on the as-of day's 7-day window (design, "What is ranked"; Addendum 2).
MIN_ARTICLES_7D = universe.MIN_ARTICLES_WEEK
NOT_RANKED = {"ai_all"}  # the whole AI stream is the baseline, never a topic

# Emergence components (MASTER_PLAN §12, score 1); each becomes a within-week percentile and the
# mean of the available percentiles is ranked again. `new_nbr_rate` joins when WS3's table exists.
EMERGENCE_TERMS = ("z_7d", "z_dow_7d", "growth_7d_log", "accel_7d", "new_nbr_rate")

# Emotional charge (MASTER_PLAN §10.4) without the two GCAM terms, which are not in the lake:
# mean(z(extremity_7d), z(mean_polarity_7d), z(controversy_7d), |z(tone_shift_7d)|), each z
# against the unit's own days 34..7 back. Controversy is NULL for WS1 topics (no tail counts).
CHARGE_TERMS = ("z_extremity", "z_polarity", "z_controversy", "abs_z_tone_shift")

# Saturation, 0..1 = mean of: the share of the last 28 days the unit was hot (z_7d > 1), and the
# share of the last 7 days its es/pt coverage was in onset (es/pt z_7d > 2, already in Spanish).
HOT_Z = 1.0
ESPT_HOT_Z = 2.0

# Stage: first matching row wins (the `stage` enum of topic_scores_weekly).
STAGE_RULES = (
    ("semilla", "no z_7d history yet (a new unit)"),
    ("en_declive", "growth_7d_log <= -0.15 and share_7d < 0.85 x its 56-day max"),
    ("saturado", "saturation >= 0.6"),
    ("en_pico", "z_7d >= 2 and accel_7d <= 0"),
    ("emergente", "z_7d >= 1, or growth_7d_log >= 0.15 with accel_7d > 0"),
    ("semilla", "growth_7d_log >= 0 (otherwise en_declive)"),
)
DECLINE_GROWTH = -0.15
DECLINE_LEVEL = 0.85
SATURATED = 0.6
PEAK_Z = 2.0
EMERGING_Z = 1.0
EMERGING_GROWTH = 0.15

# Audience fit v1, rule-based (MASTER_PLAN §12, score 3; Jev is optional and approval-gated):
# fit = FIT_BASE + FIT_W_SUBTOPIC x [business/education share of the unit's subtopics]
#                + FIT_W_LATAM x clip(LatAm share / ai_all LatAm share / 2, 0, 1)
# LatAm share = LatAm-source articles / all articles over 7 days; where the unit has no LatAm
# split (WS1 topics), the es/pt share of its articles replaces it, against ai_all's es/pt share.
FIT_SUBTOPICS = {"business_adoption", "funding_markets", "education"}
FIT_BASE, FIT_W_SUBTOPIC, FIT_W_LATAM = 0.4, 0.3, 0.3

# Priority = Emergence_pct x (1 - Saturation) x Fit x (1 + CHARGE_WEIGHT x EmotionalCharge_pct),
# percentiles as fractions (MASTER_PLAN §12).
CHARGE_WEIGHT = 0.25

# Framing angle (MASTER_PLAN §10.5), first matching row wins.
ANGLE_TONE = 1.5
ANGLE_Z = 1.5
ANGLES = (
    ("Alerta / riesgo", "negative tail dominant and mean_tone_7d < -1.5"),
    ("Oportunidad / cómo aprovecharlo", "positive tail dominant and mean_tone_7d > +1.5"),
    ("Debate", "z(controversy_7d) > 1.5"),
    ("Giro", "|z(tone_shift_7d)| > 1.5"),
    ("Explicador neutral", "otherwise"),
)


def iso_week(col: str = "dt") -> pl.Expr:
    return pl.col(col).dt.strftime("%G-W%V")


def with_unit_z(roll: pl.DataFrame, key: str = "unit_id") -> pl.DataFrame:
    """Adds the self-z of the tone terms, the 7-day mean of z_dow and the saturation inputs."""
    by = [key, "group"]
    r = roll.sort([*by, "dt"])
    hot = (pl.col(Z) > HOT_Z).cast(pl.Float64)
    hot = pl.when(pl.col(Z).is_not_null()).then(hot)
    return r.with_columns(
        self_z("extremity_7d", by).alias("z_extremity"),
        self_z("mean_polarity_7d", by).alias("z_polarity"),
        self_z("controversy_7d", by).alias("z_controversy"),
        self_z("tone_shift_7d", by).alias("z_tone_shift"),
        pl.col(ZDOW).rolling_mean(7, min_samples=1).over(by).alias("z_dow_7d"),
        hot.rolling_mean(28, min_samples=1).over(by).alias("hot_days_28"),
        (pl.col(Z) > ESPT_HOT_Z)
        .cast(pl.Float64)
        .rolling_mean(7, min_samples=1)
        .over(by)
        .alias("onset_days_7"),
        pl.col("share_7d").rolling_max(56, min_samples=1).over(by).alias("share_7d_max56"),
    ).with_columns(pl.col("z_tone_shift").abs().alias("abs_z_tone_shift"))


def asof_days(roll: pl.DataFrame) -> pl.DataFrame:
    """The as-of day of each ISO week: its last day present in the data."""
    return (
        roll.select("dt")
        .unique()
        .with_columns(iso_week().alias("week"))
        .group_by("week")
        .agg(pl.col("dt").max().alias("asof"))
        .sort("week")
    )


def weekly_panel(roll: pl.DataFrame, key: str = "unit_id") -> pl.DataFrame:
    """One row per unit x week with the features the scores read (from `features.rolling`)."""
    r = with_unit_z(roll, key)
    days = asof_days(r)
    at = r.join(days, left_on="dt", right_on="asof")
    allg = at.filter(pl.col("group") == "all").select(
        key, "week", pl.col("dt").alias("asof"), "n7raw", "n_7d", "share_7d",
        pl.col(Z).alias("z_7d"), "z_dow_7d", "growth_7d_log", "accel_7d", "mean_tone_7d",
        "positive_share_7d", "negative_share_7d", "n_latam_7d", "hot_days_28", "share_7d_max56",
        *CHARGE_TERMS, "z_tone_shift",
    )  # fmt: skip
    espt = at.filter(pl.col("group") == "espt").select(
        key, "week", pl.col("n_7d").alias("n_7d_espt"), pl.col("onset_days_7").alias("espt_onset_7")
    )
    return allg.join(espt, on=[key, "week"], how="left")


def _pct(col: str) -> pl.Expr:
    """Within-week percentile, 0..1 (average rank / count of non-null values)."""
    return (pl.col(col).rank("average") / pl.col(col).count()).over("week")


def static_membership(
    panel: pl.DataFrame, subtopics: dict[str, dict[str, float]], key: str = "unit_id"
) -> pl.DataFrame:
    """A membership frame from fixed subtopic weights (a subtopic maps to itself)."""
    rows = [
        {key: u, "fit_subtopic": float(sum(w for s, w in ws.items() if s in FIT_SUBTOPICS))}
        for u, ws in subtopics.items()
    ]
    fit = pl.DataFrame(rows, schema={key: pl.String, "fit_subtopic": pl.Float64})
    return panel.select(key, "week").unique().join(fit, on=key, how="left")


def score(
    panel: pl.DataFrame,
    subtopics: dict[str, dict[str, float]] | pl.DataFrame | None,
    key: str = "unit_id",
    graph: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """The scores per unit x week.

    `subtopics` is either fixed subtopic weights per unit (shares of its articles; a subtopic maps
    to itself), or a membership frame with `key`, `week` and `fit_subtopic` (the business and
    education share of the unit's articles that week, `universe.membership`), or None (no
    subtopics known: the fit uses the unit's own series only). `graph` is WS3's
    `node_metrics_weekly` keyed by `key` and `week` (optional).
    """
    p = panel
    if isinstance(subtopics, dict):
        subtopics = static_membership(panel, subtopics, key)
    if subtopics is not None:
        p = p.join(subtopics.select(key, "week", "fit_subtopic"), on=[key, "week"], how="left")
    else:
        p = p.with_columns(pl.lit(None, pl.Float64).alias("fit_subtopic"))
    if graph is not None:
        p = p.join(graph.select(key, "week", "new_nbr_rate"), on=[key, "week"], how="left")
    else:
        p = p.with_columns(pl.lit(None, pl.Float64).alias("new_nbr_rate"))
    base = p.filter(pl.col(key) == "ai_all").select(
        "week",
        (pl.col("n_latam_7d") / pl.col("n_7d")).alias("ai_latam_share"),
        (pl.col("n_7d_espt") / pl.col("n_7d")).alias("ai_espt_share"),
    )
    p = p.filter(~pl.col(key).is_in(list(NOT_RANKED))).join(base, on="week", how="left")
    p = p.with_columns(
        (pl.col("n7raw").fill_null(0) >= universe.min_articles_week()).alias("eligible"),
    )
    # percentiles are taken over the ranked universe of the week only
    ranked = p.filter("eligible")
    ranked = ranked.with_columns(*(_pct(t).alias(f"pct_{t}") for t in EMERGENCE_TERMS))
    ranked = ranked.with_columns(
        pl.mean_horizontal(*(f"pct_{t}" for t in EMERGENCE_TERMS)).alias("emergence_raw"),
        pl.mean_horizontal(*CHARGE_TERMS).alias("charge_raw"),
    ).with_columns(
        (100 * _pct("emergence_raw")).alias("emergence_pct"),
        (100 * _pct("charge_raw")).alias("emotional_charge_pct"),
    )
    p = p.join(
        ranked.select(key, "week", "emergence_pct", "emotional_charge_pct"),
        on=[key, "week"],
        how="left",
    )
    latam_ratio = pl.coalesce(
        (pl.col("n_latam_7d") / pl.col("n_7d")) / pl.col("ai_latam_share"),
        (pl.col("n_7d_espt") / pl.col("n_7d")) / pl.col("ai_espt_share"),
    )
    p = p.with_columns(
        pl.min_horizontal(
            pl.lit(1.0),
            pl.mean_horizontal(pl.col("hot_days_28"), pl.col("espt_onset_7")),
        ).alias("saturation"),
        (
            FIT_BASE
            + FIT_W_SUBTOPIC * pl.col("fit_subtopic").fill_null(0)
            + FIT_W_LATAM * (latam_ratio / 2).clip(0, 1).fill_null(0)
        ).alias("audience_fit"),
    )
    p = p.with_columns(_stage().alias("stage"), _angle().alias("framing_angle"))
    p = p.with_columns(
        (
            (pl.col("emergence_pct") / 100)
            * (1 - pl.col("saturation").fill_null(0))
            * pl.col("audience_fit")
            * (1 + CHARGE_WEIGHT * pl.col("emotional_charge_pct").fill_null(0) / 100)
        )
        .fill_null(0.0)
        .alias("priority")
    )
    rank = pl.col("priority").rank("ordinal", descending=True).over("week")
    ranked_rank = p.filter("eligible").select(
        key,
        "week",
        rank.cast(pl.Int64).alias("rank"),
        (100 * _pct("priority")).alias("priority_pct"),
    )
    return p.join(ranked_rank, on=[key, "week"], how="left").sort("week", "rank", key)


def _stage() -> pl.Expr:
    z, g, a = pl.col("z_7d"), pl.col("growth_7d_log"), pl.col("accel_7d")
    level = pl.col("share_7d") / pl.col("share_7d_max56")
    return (
        pl.when(z.is_null())
        .then(pl.lit("semilla"))
        .when((g <= DECLINE_GROWTH) & (level < DECLINE_LEVEL))
        .then(pl.lit("en_declive"))
        .when(pl.col("saturation") >= SATURATED)
        .then(pl.lit("saturado"))
        .when((z >= PEAK_Z) & (a <= 0))
        .then(pl.lit("en_pico"))
        .when((z >= EMERGING_Z) | ((g >= EMERGING_GROWTH) & (a > 0)))
        .then(pl.lit("emergente"))
        .when(g.fill_null(0) >= 0)
        .then(pl.lit("semilla"))
        .otherwise(pl.lit("en_declive"))
    )


def _angle() -> pl.Expr:
    tone = pl.col("mean_tone_7d")
    pos, neg = pl.col("positive_share_7d"), pl.col("negative_share_7d")
    # without tail counts (WS1 topics) the tone sign alone decides the tail
    neg_dom = pl.coalesce(neg > pos, pl.lit(True))
    pos_dom = pl.coalesce(pos > neg, pl.lit(True))
    return (
        pl.when(neg_dom & (tone < -ANGLE_TONE))
        .then(pl.lit(ANGLES[0][0]))
        .when(pos_dom & (tone > ANGLE_TONE))
        .then(pl.lit(ANGLES[1][0]))
        .when(pl.col("z_controversy") > ANGLE_Z)
        .then(pl.lit(ANGLES[2][0]))
        .when(pl.col("z_tone_shift").abs() > ANGLE_Z)
        .then(pl.lit(ANGLES[3][0]))
        .otherwise(pl.lit(ANGLES[4][0]))
    )
