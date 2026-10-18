-- S3: denominators for normalization and gap detection (2 cheap columns over 2 years, ~6 GB estimate)
-- lang_bucket: eng / spa / por / other. is_missing marks the known outage and partial days (treated as NULL downstream).
CREATE OR REPLACE TABLE `radar.daily_totals`
PARTITION BY dt AS
WITH raw AS (
  SELECT
    DATE(SAFE.PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING))) AS dt,
    IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') AS lang,
    COUNT(*) AS n_all
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('2024-10-16')
    AND DATE >= 20241017000000
  GROUP BY dt, lang
),
bucketed AS (
  SELECT
    dt,
    CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
    SUM(n_all) AS n_all
  FROM raw
  WHERE dt IS NOT NULL
  GROUP BY dt, lang_bucket
),
with_baseline AS (
  SELECT
    *,
    -- trailing 28-day mean of the same stream, used to flag partial days (< 50% of normal volume)
    -- (PERCENTILE_CONT does not accept a window frame in BigQuery, so a mean is used)
    AVG(n_all) OVER (
      PARTITION BY lang_bucket ORDER BY UNIX_DATE(dt) RANGE BETWEEN 28 PRECEDING AND 1 PRECEDING) AS n_all_med28
  FROM bucketed
)
SELECT
  dt,
  lang_bucket,
  n_all,
  n_all_med28,
  (dt BETWEEN DATE '2025-06-14' AND DATE '2025-07-02')
    OR (n_all_med28 IS NOT NULL AND n_all < 0.5 * n_all_med28) AS is_missing
FROM with_baseline;
