-- S9: topic-level emotion table and rolling view from radar.gcam_ai (own tables only; < 2 GB per rebuild, estimate).
-- Densities per 1,000 words. "Arousal" (ANEW, 1-9 scale) is the best single proxy for the "both extremes" thesis:
-- high arousal can come with high OR low valence. All "_rel" columns are relative to the same-day all-news baseline
-- of the same language stream (radar.gcam_daily_baseline), so news-wide mood swings are removed.
CREATE OR REPLACE TABLE `radar.gcam_daily_topic`
PARTITION BY dt
CLUSTER BY topic, lang_bucket AS
WITH a AS (
  SELECT
    t.dt, t.topic, g.lang_bucket, t.latam,
    g.anew_valence, g.anew_arousal, g.es_anew_arousal, g.wc,
    SAFE_DIVIDE(g.liwc_anxiety + g.wna_anxiety, g.wc) * 1000 AS anxiety_pk,
    SAFE_DIVIDE(g.roget_fear + g.wna_negative_fear + g.wna_alarm, g.wc) * 1000 AS fear_pk,
    SAFE_DIVIDE(g.roget_hope + g.wna_hopefulness + g.wna_positive_hope + g.wna_enthusiasm, g.wc) * 1000 AS hope_pk,
    SAFE_DIVIDE(g.wna_awe + g.wna_surprise, g.wc) * 1000 AS awe_surprise_pk,
    SAFE_DIVIDE(g.wna_anticipation, g.wc) * 1000 AS anticipation_pk,
    SAFE_DIVIDE(g.wna_confidence + g.wna_security, g.wc) * 1000 AS trust_proxy_pk,
    SAFE_DIVIDE(g.lm_uncertainty, g.wc) * 1000 AS uncertainty_pk,
    SAFE_DIVIDE(g.liwc_anger, g.wc) * 1000 AS anger_pk,
    SAFE_DIVIDE(g.mfd_harm_vice + g.mfd_fairness_vice, g.wc) * 1000 AS moral_outrage_pk
  FROM `radar.article_topic` AS t
  JOIN `radar.gcam_ai` AS g ON g.gkg_id = t.gkg_id AND g.dt = t.dt
)
SELECT
  a.dt, a.topic, a.lang_bucket, a.latam,
  COUNT(*) AS n_gcam,
  AVG(a.anew_valence) AS mean_valence,
  AVG(a.anew_arousal) AS mean_arousal,
  COUNTIF(a.anew_arousal >= 5.6) / COUNT(*) AS high_arousal_share,  -- 5.6 is a placeholder: set to the P75 of AI rows
  AVG(a.es_anew_arousal) AS mean_es_arousal,
  AVG(a.anxiety_pk) AS anxiety_pk,
  AVG(a.fear_pk) AS fear_pk,
  AVG(a.hope_pk) AS hope_pk,
  AVG(a.awe_surprise_pk) AS awe_surprise_pk,
  AVG(a.anticipation_pk) AS anticipation_pk,
  AVG(a.trust_proxy_pk) AS trust_proxy_pk,
  AVG(a.uncertainty_pk) AS uncertainty_pk,
  AVG(a.anger_pk) AS anger_pk,
  AVG(a.moral_outrage_pk) AS moral_outrage_pk,
  AVG(a.anew_arousal) - ANY_VALUE(b.mean_anew_arousal) AS arousal_rel,
  SAFE_DIVIDE(AVG(a.fear_pk), ANY_VALUE(b.mean_fear_pk)) AS fear_rel,
  SAFE_DIVIDE(AVG(a.hope_pk), ANY_VALUE(b.mean_hope_pk)) AS hope_rel,
  SAFE_DIVIDE(AVG(a.uncertainty_pk), ANY_VALUE(b.mean_uncertainty_pk)) AS uncertainty_rel
FROM a
LEFT JOIN `radar.gcam_daily_baseline` AS b ON b.dt = a.dt AND b.lang_bucket = a.lang_bucket
GROUP BY a.dt, a.topic, a.lang_bucket, a.latam;

-- Rolling 7-day emotion view with z-scores vs. days 34..7 back (same convention as S8; missing days stay NULL).
CREATE OR REPLACE VIEW `radar.gcam_topic_rolling` AS
WITH r AS (
  SELECT
    *,
    SUM(n_gcam) OVER w7 AS n_gcam_7d,
    SAFE_DIVIDE(SUM(mean_arousal * n_gcam) OVER w7, SUM(n_gcam) OVER w7) AS arousal_7d,
    SAFE_DIVIDE(SUM(fear_pk * n_gcam) OVER w7, SUM(n_gcam) OVER w7) AS fear_7d,
    SAFE_DIVIDE(SUM(hope_pk * n_gcam) OVER w7, SUM(n_gcam) OVER w7) AS hope_7d,
    SAFE_DIVIDE(SUM(uncertainty_pk * n_gcam) OVER w7, SUM(n_gcam) OVER w7) AS uncertainty_7d,
    SAFE_DIVIDE(SUM(arousal_rel * n_gcam) OVER w7, SUM(n_gcam) OVER w7) AS arousal_rel_7d
  FROM `radar.gcam_daily_topic`
  WINDOW w7 AS (PARTITION BY topic, lang_bucket, latam ORDER BY UNIX_DATE(dt) RANGE BETWEEN 6 PRECEDING AND CURRENT ROW)
)
SELECT
  *,
  SAFE_DIVIDE(arousal_rel_7d - AVG(arousal_rel_7d) OVER wb, NULLIF(STDDEV_SAMP(arousal_rel_7d) OVER wb, 0)) AS z_arousal_rel_7d,
  SAFE_DIVIDE(fear_7d - AVG(fear_7d) OVER wb, NULLIF(STDDEV_SAMP(fear_7d) OVER wb, 0)) AS z_fear_7d,
  SAFE_DIVIDE(hope_7d - AVG(hope_7d) OVER wb, NULLIF(STDDEV_SAMP(hope_7d) OVER wb, 0)) AS z_hope_7d,
  -- "both extremes" signal: fear and hope rising together (divisive / high-stakes framing)
  LEAST(
    SAFE_DIVIDE(fear_7d - AVG(fear_7d) OVER wb, NULLIF(STDDEV_SAMP(fear_7d) OVER wb, 0)),
    SAFE_DIVIDE(hope_7d - AVG(hope_7d) OVER wb, NULLIF(STDDEV_SAMP(hope_7d) OVER wb, 0))) AS z_fear_and_hope_7d
FROM r
WINDOW wb AS (PARTITION BY topic, lang_bucket, latam ORDER BY UNIX_DATE(dt) RANGE BETWEEN 34 PRECEDING AND 7 PRECEDING);
