-- S7: GCAM emotion extraction (NOW IN SCOPE with the ~$250 Google Cloud credit). One month per run, newest first.
-- !!! DRY-RUN FIRST. GCAM averages 9,172 B/row (measured) and is billed IN FULL for every row of every scanned partition,
-- !!! whatever the WHERE / IN filter. One month ~ 92 GB (~0.084 TiB, ~$0.52 at $6.25/TiB) at ~331k rows/day (estimate).
-- !!! Before running: Query settings -> Maximum bytes billed = 161061273600 (150 GiB) for THIS job only; restore 50 GiB afterwards.
-- !!! Two years = 24 runs ~ 1.5-2.2 TiB ~ $9-15 (estimate). The 0.7 TiB/day quota allows ~7 runs/day; raise it temporarily if needed.
-- Heavy column read ONCE (statement 1) into a narrow temp table; statements 2-3 read only the temp table (~3-4 GB each).
-- Keys verified in GCAM-MASTER-CODEBOOK.TXT (Oct 17, 2026). Coverage measured on 6,184 GKG rows (Oct 17, 22:00-23:30 UTC):
-- v19.* / v21.1 / v10.* ~100%; LIWC posemo/negemo >90%; Spanish ANEW v22.* on 99% of Spanish-source rows; Portuguese c27.* on 98% of
-- Portuguese-source rows. Native-language dictionaries run on the native text; 'nwc' = native word count (GKG 2.1 codebook).
-- 'c' keys are word counts (absent = 0); 'v' keys are average scores (absent = NULL). Densities are computed downstream.
-- Licensing: GCAM scores are GDELT open data (cite GDELT). Each dictionary has its own citation and licence (see codebook column
-- DictionaryCitation); LIWC is a proprietary dictionary, so we use only GDELT's published scores. Redistribution of derived scores: unverified.

CREATE TABLE IF NOT EXISTS `radar.gcam_ai` (
  gkg_id STRING,
  dt DATE,
  lang_bucket STRING,
  wc FLOAT64,
  nwc FLOAT64,
  lsd_neg FLOAT64,
  lsd_pos FLOAT64,
  liwc_sad FLOAT64,
  liwc_anger FLOAT64,
  liwc_anxiety FLOAT64,
  liwc_negemo FLOAT64,
  liwc_posemo FLOAT64,
  lm_litigious FLOAT64,
  lm_uncertainty FLOAT64,
  wna_alarm FLOAT64,
  wna_anticipation FLOAT64,
  wna_anxiety FLOAT64,
  wna_awe FLOAT64,
  wna_confidence FLOAT64,
  wna_enthusiasm FLOAT64,
  wna_hopefulness FLOAT64,
  wna_insecurity FLOAT64,
  wna_joy FLOAT64,
  wna_negative_fear FLOAT64,
  wna_positive_hope FLOAT64,
  wna_security FLOAT64,
  wna_surprise FLOAT64,
  roget_hope FLOAT64,
  roget_fear FLOAT64,
  gi_arousal FLOAT64,
  gi_emot FLOAT64,
  mfd_harm_vice FLOAT64,
  mfd_fairness_vice FLOAT64,
  mfd_morality_general FLOAT64,
  anew_valence FLOAT64,
  anew_arousal FLOAT64,
  anew_dominance FLOAT64,
  hedonometer FLOAT64,
  vader_valence FLOAT64,
  swn_pos FLOAT64,
  swn_neg FLOAT64,
  es_anew_valence FLOAT64,
  es_anew_arousal FLOAT64,
  es_senticon_l1_pos FLOAT64,
  es_senticon_l1_neg FLOAT64,
  es_hedonometer FLOAT64,
  pt_hedonometer FLOAT64,
  pt_emotion FLOAT64,
  pt_prosocial FLOAT64
)
PARTITION BY dt
CLUSTER BY lang_bucket;

CREATE TABLE IF NOT EXISTS `radar.gcam_daily_baseline` (
  dt DATE,
  lang_bucket STRING,
  n_rows INT64,
  mean_anew_valence FLOAT64,
  mean_anew_arousal FLOAT64,
  mean_es_anew_arousal FLOAT64,
  mean_negemo_pk FLOAT64,
  mean_posemo_pk FLOAT64,
  mean_anxiety_pk FLOAT64,
  mean_fear_pk FLOAT64,
  mean_hope_pk FLOAT64,
  mean_uncertainty_pk FLOAT64
)
PARTITION BY dt;

-- 1) THE ONLY EXPENSIVE STATEMENT: parse GCAM for all rows of the month (example: September 2026; edit the 4 literals).
CREATE TEMP TABLE gcam_month AS
SELECT r.gkg_id, r.dt, r.lang_bucket, r.g.*
FROM (
  SELECT
    GKGRECORDID AS gkg_id,
    DATE(SAFE.PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING))) AS dt,
    CASE WHEN IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') IN ('eng', 'spa', 'por')
         THEN IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') ELSE 'other' END AS lang_bucket,
    (
    SELECT AS STRUCT
      MAX(IF(k = 'wc', v, NULL)) AS wc,
      MAX(IF(k = 'nwc', v, NULL)) AS nwc,
      IFNULL(MAX(IF(k = 'c3.1', v, NULL)), 0) AS lsd_neg,
      IFNULL(MAX(IF(k = 'c3.2', v, NULL)), 0) AS lsd_pos,
      IFNULL(MAX(IF(k = 'c5.31', v, NULL)), 0) AS liwc_sad,
      IFNULL(MAX(IF(k = 'c5.32', v, NULL)), 0) AS liwc_anger,
      IFNULL(MAX(IF(k = 'c5.33', v, NULL)), 0) AS liwc_anxiety,
      IFNULL(MAX(IF(k = 'c5.34', v, NULL)), 0) AS liwc_negemo,
      IFNULL(MAX(IF(k = 'c5.35', v, NULL)), 0) AS liwc_posemo,
      IFNULL(MAX(IF(k = 'c6.1', v, NULL)), 0) AS lm_litigious,
      IFNULL(MAX(IF(k = 'c6.6', v, NULL)), 0) AS lm_uncertainty,
      IFNULL(MAX(IF(k = 'c15.7', v, NULL)), 0) AS wna_alarm,
      IFNULL(MAX(IF(k = 'c15.20', v, NULL)), 0) AS wna_anticipation,
      IFNULL(MAX(IF(k = 'c15.22', v, NULL)), 0) AS wna_anxiety,
      IFNULL(MAX(IF(k = 'c15.30', v, NULL)), 0) AS wna_awe,
      IFNULL(MAX(IF(k = 'c15.57', v, NULL)), 0) AS wna_confidence,
      IFNULL(MAX(IF(k = 'c15.103', v, NULL)), 0) AS wna_enthusiasm,
      IFNULL(MAX(IF(k = 'c15.147', v, NULL)), 0) AS wna_hopefulness,
      IFNULL(MAX(IF(k = 'c15.160', v, NULL)), 0) AS wna_insecurity,
      IFNULL(MAX(IF(k = 'c15.167', v, NULL)), 0) AS wna_joy,
      IFNULL(MAX(IF(k = 'c15.198', v, NULL)), 0) AS wna_negative_fear,
      IFNULL(MAX(IF(k = 'c15.212', v, NULL)), 0) AS wna_positive_hope,
      IFNULL(MAX(IF(k = 'c15.233', v, NULL)), 0) AS wna_security,
      IFNULL(MAX(IF(k = 'c15.254', v, NULL)), 0) AS wna_surprise,
      IFNULL(MAX(IF(k = 'c9.896', v, NULL)), 0) AS roget_hope,
      IFNULL(MAX(IF(k = 'c9.898', v, NULL)), 0) AS roget_fear,
      IFNULL(MAX(IF(k = 'c2.17', v, NULL)), 0) AS gi_arousal,
      IFNULL(MAX(IF(k = 'c2.47', v, NULL)), 0) AS gi_emot,
      IFNULL(MAX(IF(k = 'c25.2', v, NULL)), 0) AS mfd_harm_vice,
      IFNULL(MAX(IF(k = 'c25.4', v, NULL)), 0) AS mfd_fairness_vice,
      IFNULL(MAX(IF(k = 'c25.11', v, NULL)), 0) AS mfd_morality_general,
      MAX(IF(k = 'v19.1', v, NULL)) AS anew_valence,
      MAX(IF(k = 'v19.2', v, NULL)) AS anew_arousal,
      MAX(IF(k = 'v19.3', v, NULL)) AS anew_dominance,
      MAX(IF(k = 'v21.1', v, NULL)) AS hedonometer,
      MAX(IF(k = 'v26.1', v, NULL)) AS vader_valence,
      MAX(IF(k = 'v10.1', v, NULL)) AS swn_pos,
      MAX(IF(k = 'v10.2', v, NULL)) AS swn_neg,
      MAX(IF(k = 'v22.1', v, NULL)) AS es_anew_valence,
      MAX(IF(k = 'v22.2', v, NULL)) AS es_anew_arousal,
      MAX(IF(k = 'v23.17', v, NULL)) AS es_senticon_l1_pos,
      MAX(IF(k = 'v23.18', v, NULL)) AS es_senticon_l1_neg,
      MAX(IF(k = 'v24.9', v, NULL)) AS es_hedonometer,
      MAX(IF(k = 'v24.7', v, NULL)) AS pt_hedonometer,
      IFNULL(MAX(IF(k = 'c27.1', v, NULL)), 0) AS pt_emotion,
      IFNULL(MAX(IF(k = 'c27.2', v, NULL)), 0) AS pt_prosocial
    FROM (
      SELECT SPLIT(p, ':')[SAFE_OFFSET(0)] AS k, SAFE_CAST(SPLIT(p, ':')[SAFE_OFFSET(1)] AS FLOAT64) AS v
      FROM UNNEST(SPLIT(GCAM, ',')) AS p
    )
    WHERE k IN ('wc', 'nwc', 'c3.1', 'c3.2', 'c5.31', 'c5.32', 'c5.33', 'c5.34', 'c5.35', 'c6.1', 'c6.6', 'c15.7', 'c15.20', 'c15.22', 'c15.30', 'c15.57', 'c15.103', 'c15.147', 'c15.160', 'c15.167', 'c15.198', 'c15.212', 'c15.233', 'c15.254', 'c9.896', 'c9.898', 'c2.17', 'c2.47', 'c25.2', 'c25.4', 'c25.11', 'v19.1', 'v19.2', 'v19.3', 'v21.1', 'v26.1', 'v10.1', 'v10.2', 'v22.1', 'v22.2', 'v23.17', 'v23.18', 'v24.9', 'v24.7', 'c27.1', 'c27.2')
    ) AS g
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('2026-08-31') AND _PARTITIONTIME < TIMESTAMP('2026-10-02')
    AND DATE >= 20260901000000 AND DATE < 20261001000000
) AS r
WHERE r.dt IS NOT NULL;

-- 2) Narrow per-article emotion table for AI candidates + control sample (rows that exist in radar.gkg_ai)
DELETE FROM `radar.gcam_ai` WHERE dt >= DATE '2026-09-01' AND dt < DATE '2026-10-01';
INSERT INTO `radar.gcam_ai` (gkg_id, dt, lang_bucket, wc, nwc, lsd_neg, lsd_pos, liwc_sad, liwc_anger, liwc_anxiety, liwc_negemo, liwc_posemo, lm_litigious, lm_uncertainty, wna_alarm, wna_anticipation, wna_anxiety, wna_awe, wna_confidence, wna_enthusiasm, wna_hopefulness, wna_insecurity, wna_joy, wna_negative_fear, wna_positive_hope, wna_security, wna_surprise, roget_hope, roget_fear, gi_arousal, gi_emot, mfd_harm_vice, mfd_fairness_vice, mfd_morality_general, anew_valence, anew_arousal, anew_dominance, hedonometer, vader_valence, swn_pos, swn_neg, es_anew_valence, es_anew_arousal, es_senticon_l1_pos, es_senticon_l1_neg, es_hedonometer, pt_hedonometer, pt_emotion, pt_prosocial)
SELECT m.gkg_id, m.dt, m.lang_bucket, m.wc, m.nwc, m.lsd_neg, m.lsd_pos, m.liwc_sad, m.liwc_anger, m.liwc_anxiety, m.liwc_negemo, m.liwc_posemo, m.lm_litigious, m.lm_uncertainty, m.wna_alarm, m.wna_anticipation, m.wna_anxiety, m.wna_awe, m.wna_confidence, m.wna_enthusiasm, m.wna_hopefulness, m.wna_insecurity, m.wna_joy, m.wna_negative_fear, m.wna_positive_hope, m.wna_security, m.wna_surprise, m.roget_hope, m.roget_fear, m.gi_arousal, m.gi_emot, m.mfd_harm_vice, m.mfd_fairness_vice, m.mfd_morality_general, m.anew_valence, m.anew_arousal, m.anew_dominance, m.hedonometer, m.vader_valence, m.swn_pos, m.swn_neg, m.es_anew_valence, m.es_anew_arousal, m.es_senticon_l1_pos, m.es_senticon_l1_neg, m.es_hedonometer, m.pt_hedonometer, m.pt_emotion, m.pt_prosocial
FROM gcam_month AS m
JOIN (
  SELECT DISTINCT gkg_id FROM `radar.gkg_ai` WHERE dt >= DATE '2026-09-01' AND dt < DATE '2026-10-01'
) AS a USING (gkg_id)
QUALIFY ROW_NUMBER() OVER (PARTITION BY m.gkg_id ORDER BY m.dt) = 1;

-- 3) Daily emotional baseline of ALL news per language stream (free ride on the bytes already paid in statement 1).
--    Densities per 1,000 words; English-dictionary densities use wc (MT English text), so they apply to every stream.
DELETE FROM `radar.gcam_daily_baseline` WHERE dt >= DATE '2026-09-01' AND dt < DATE '2026-10-01';
INSERT INTO `radar.gcam_daily_baseline`
SELECT
  dt,
  lang_bucket,
  COUNT(*) AS n_rows,
  AVG(anew_valence),
  AVG(anew_arousal),
  AVG(es_anew_arousal),
  AVG(SAFE_DIVIDE(liwc_negemo, wc) * 1000),
  AVG(SAFE_DIVIDE(liwc_posemo, wc) * 1000),
  AVG(SAFE_DIVIDE(liwc_anxiety + wna_anxiety, wc) * 1000),
  AVG(SAFE_DIVIDE(roget_fear + wna_negative_fear + wna_alarm, wc) * 1000),
  AVG(SAFE_DIVIDE(roget_hope + wna_hopefulness + wna_positive_hope + wna_enthusiasm, wc) * 1000),
  AVG(SAFE_DIVIDE(lm_uncertainty, wc) * 1000)
FROM gcam_month
GROUP BY dt, lang_bucket;
