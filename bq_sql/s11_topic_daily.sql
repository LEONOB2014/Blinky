-- S11: radar.topic_daily, the per-topic series the radar ranks and backtests (contracts/topic_daily.schema.json).
-- A topic is an organization ('org:<name>') or a GKG theme ('thm:<THEME>') inside ring-1 articles; persons are
-- never ranked. Reads radar.article_segment (no wide gkg_ai column). Days with no article for a topic have no row
-- (consumers build the calendar from daily_totals); is_missing days keep their row with share_of_day NULL.
-- Only topics that reach >= 20 articles (all languages) in some trailing 7-day window are kept: a superset of the
-- ranking universe (design "What is ranked"), which keeps the table small enough to export.
CREATE OR REPLACE TABLE `radar.topic_daily`
PARTITION BY dt
CLUSTER BY topic_id, lang_bucket AS
WITH mentions AS (
  SELECT gkg_id, dt, lang_bucket, tone, polarity, CONCAT('org:', e) AS topic_id
  FROM `radar.article_segment`, UNNEST(orgs) AS e
  WHERE segment = 'ai'
  UNION ALL
  SELECT gkg_id, dt, lang_bucket, tone, polarity, CONCAT('thm:', e)
  FROM `radar.article_segment`, UNNEST(themes) AS e
  WHERE segment = 'ai'
),
daily AS (
  SELECT
    topic_id, dt, lang_bucket,
    COUNT(DISTINCT gkg_id) AS n_articles,
    AVG(tone) AS mean_tone,
    AVG(polarity) AS mean_polarity
  FROM mentions
  GROUP BY topic_id, dt, lang_bucket
),
all_lang AS (
  SELECT topic_id, dt, SUM(n_articles) AS n FROM daily GROUP BY topic_id, dt
),
eligible AS (
  SELECT topic_id
  FROM (
    SELECT topic_id, SUM(n) OVER (PARTITION BY topic_id ORDER BY UNIX_DATE(dt) RANGE BETWEEN 6 PRECEDING AND CURRENT ROW) AS n_7d
    FROM all_lang
  )
  GROUP BY topic_id
  HAVING MAX(n_7d) >= 20
)
SELECT
  d.topic_id,
  d.dt,
  d.lang_bucket,
  'ai' AS segment,
  d.n_articles,
  IF(IFNULL(t.is_missing, TRUE), NULL, SAFE_DIVIDE(d.n_articles, t.n_all)) AS share_of_day,
  d.mean_tone,
  d.mean_polarity,
  IFNULL(t.is_missing, TRUE) AS is_missing
FROM daily AS d
JOIN eligible USING (topic_id)
LEFT JOIN `radar.daily_totals` AS t
  ON t.dt = d.dt AND t.lang_bucket = d.lang_bucket;
