-- S8: rolling 7-day view with weekday-adjusted baselines, growth and acceleration.
-- A complete calendar spine is built per (topic, lang_bucket, latam): days with real source data but no articles get n = 0;
-- days flagged is_missing in daily_totals (2025-06-14..2025-07-02 outage, partial days) get NULL, never 0.
-- Querying this view bills only the bytes of our small tables.
CREATE OR REPLACE VIEW `radar.daily_topic_rolling` AS
WITH keys AS (
  SELECT DISTINCT topic, lang_bucket, latam FROM `radar.daily_topic`
),
spine AS (
  SELECT k.topic, k.lang_bucket, k.latam, t.dt, t.n_all, t.is_missing
  FROM keys AS k
  JOIN `radar.daily_totals` AS t ON t.lang_bucket = k.lang_bucket
),
filled AS (
  SELECT
    s.topic, s.lang_bucket, s.latam, s.dt,
    EXTRACT(DAYOFWEEK FROM s.dt) AS dow,
    s.is_missing,
    IF(s.is_missing, NULL, s.n_all) AS n_all,
    IF(s.is_missing, NULL, IFNULL(d.n_articles, 0)) AS n,
    IF(s.is_missing, NULL, IFNULL(d.n_sources, 0)) AS n_sources,
    IF(s.is_missing, NULL, IFNULL(d.n_tone, 0)) AS n_tone,
    IF(s.is_missing, NULL, IFNULL(d.sum_tone, 0)) AS sum_tone,
    IF(s.is_missing, NULL, IFNULL(d.sum_polarity, 0)) AS sum_polarity,
    IF(s.is_missing, NULL, IFNULL(d.n_pos_x, 0)) AS n_pos_x,
    IF(s.is_missing, NULL, IFNULL(d.n_neg_x, 0)) AS n_neg_x
  FROM spine AS s
  LEFT JOIN `radar.daily_topic` AS d
    ON d.topic = s.topic AND d.lang_bucket = s.lang_bucket AND d.latam = s.latam AND d.dt = s.dt
),
roll AS (
  SELECT
    *,
    SAFE_DIVIDE(n, n_all) AS share,
    COUNT(n) OVER w7 AS valid_days_7,
    SUM(n) OVER w7 AS n_7d_raw,
    SUM(n_all) OVER w7 AS n_all_7d,
    SUM(n_tone) OVER w7 AS n_tone_7d,
    SUM(sum_tone) OVER w7 AS sum_tone_7d,
    SUM(sum_polarity) OVER w7 AS sum_polarity_7d,
    SUM(n_pos_x) OVER w7 AS n_pos_7d,
    SUM(n_neg_x) OVER w7 AS n_neg_7d,
    -- trailing 28 days ending 7 days ago (the comparison window for tone shift)
    SAFE_DIVIDE(SUM(sum_tone) OVER w28lag, SUM(n_tone) OVER w28lag) AS mean_tone_prev28
  FROM filled
  WINDOW
    w7 AS (PARTITION BY topic, lang_bucket, latam ORDER BY UNIX_DATE(dt) RANGE BETWEEN 6 PRECEDING AND CURRENT ROW),
    w28lag AS (PARTITION BY topic, lang_bucket, latam ORDER BY UNIX_DATE(dt) RANGE BETWEEN 34 PRECEDING AND 7 PRECEDING)
),
metrics AS (
  SELECT
    *,
    -- 7-day sums are only trusted with >= 5 valid days; scaled to 7 days
    IF(valid_days_7 >= 5, n_7d_raw * 7 / valid_days_7, NULL) AS n_7d,
    IF(valid_days_7 >= 5, SAFE_DIVIDE(n_7d_raw, n_all_7d), NULL) AS share_7d,
    SAFE_DIVIDE(sum_tone_7d, n_tone_7d) AS mean_tone_7d,
    SAFE_DIVIDE(sum_polarity_7d, n_tone_7d) AS mean_polarity_7d,
    SAFE_DIVIDE(n_pos_7d, n_tone_7d) AS positive_share_7d,
    SAFE_DIVIDE(n_neg_7d, n_tone_7d) AS negative_share_7d,
    -- same-weekday baseline: the previous 4 same weekdays (lags 7, 14, 21, 28) of the daily share
    LAG(SAFE_DIVIDE(n, n_all), 7) OVER wd AS s_l7,
    LAG(SAFE_DIVIDE(n, n_all), 14) OVER wd AS s_l14,
    LAG(SAFE_DIVIDE(n, n_all), 21) OVER wd AS s_l21,
    LAG(SAFE_DIVIDE(n, n_all), 28) OVER wd AS s_l28
  FROM roll
  WINDOW wd AS (PARTITION BY topic, lang_bucket, latam ORDER BY dt)
),
z AS (
  SELECT
    *,
    (SELECT AVG(x) FROM UNNEST([s_l7, s_l14, s_l21, s_l28]) AS x) AS dow_base_mean,
    (SELECT STDDEV_SAMP(x) FROM UNNEST([s_l7, s_l14, s_l21, s_l28]) AS x) AS dow_base_sd,
    (SELECT COUNT(x) FROM UNNEST([s_l7, s_l14, s_l21, s_l28]) AS x) AS dow_base_n,
    LN(SAFE_DIVIDE(share_7d + 1e-7, LAG(share_7d, 7) OVER wz + 1e-7)) AS growth_7d_log,
    AVG(share_7d) OVER w28z AS share_7d_base_mean,
    STDDEV_SAMP(share_7d) OVER w28z AS share_7d_base_sd
  FROM metrics
  WINDOW
    wz AS (PARTITION BY topic, lang_bucket, latam ORDER BY dt),
    w28z AS (PARTITION BY topic, lang_bucket, latam ORDER BY UNIX_DATE(dt) RANGE BETWEEN 34 PRECEDING AND 7 PRECEDING)
)
SELECT
  topic, lang_bucket, latam, dt, dow, is_missing,
  n, n_all, share, n_sources,
  n_7d, share_7d,
  IF(dow_base_n >= 3, SAFE_DIVIDE(share - dow_base_mean, NULLIF(dow_base_sd, 0)), NULL) AS z_dow,
  SAFE_DIVIDE(share_7d - share_7d_base_mean, NULLIF(share_7d_base_sd, 0)) AS z_7d,
  growth_7d_log,
  growth_7d_log - LAG(growth_7d_log, 7) OVER (PARTITION BY topic, lang_bucket, latam ORDER BY dt) AS accel_7d,
  mean_tone_7d,
  ABS(mean_tone_7d) AS extremity_7d,
  mean_polarity_7d,
  positive_share_7d,
  negative_share_7d,
  LEAST(1.0, mean_polarity_7d / 10.5)
    * GREATEST(0.0, 1.0 - ABS(mean_tone_7d) / 3.0)
    * 2.0 * LEAST(positive_share_7d, negative_share_7d) AS controversy_7d,
  mean_tone_7d - mean_tone_prev28 AS tone_shift_7d
FROM z;
