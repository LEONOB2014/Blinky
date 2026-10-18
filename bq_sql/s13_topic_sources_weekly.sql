-- S13: radar.topic_sources_weekly (contracts/topic_sources_weekly.schema.json): per ranked topic and Monday week, how
-- many distinct outlets carry it and how concentrated it is, so WS4 can keep wire-syndication bursts out of the top 10.
-- Reads radar.article_segment (ring 1: segment 'ai', its org/theme arrays and source) and the topic ids of topic_daily;
-- bills only the bytes of those columns.
-- top_theme_pattern_share: the topic-week's 5 most co-mentioned *specific* entities (orgs and themes in at most 10% of
-- that week's ring-1 articles, the topic itself excluded, ties by name) define a pattern; each article's pattern is the
-- sorted subset of those 5 it carries (possibly empty). Background themes are excluded because they sit in most
-- articles of a topic whatever their source (measured on 2026-W42: EPU_ECONOMY_HISTORIC in 49% of ring-1 articles,
-- WB_133 ICT in 48%), which made unrelated articles look alike (31% of ranked topic-weeks at >= 0.9 without the cut).
-- The share is the most common pattern's articles / the topic-week's articles. Syndicated copies of one story carry the
-- same subset, so a share near 1 marks a single feed even when it is spread over many domains.
CREATE OR REPLACE TABLE `radar.topic_sources_weekly`
PARTITION BY week
CLUSTER BY topic_id AS
WITH topics AS (
  SELECT DISTINCT topic_id FROM `radar.topic_daily`
),
art_ents AS (
  SELECT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)) AS week, source, CONCAT('org:', e) AS ent
  FROM `radar.article_segment`, UNNEST(orgs) AS e
  WHERE segment = 'ai'
  UNION DISTINCT
  SELECT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)), source, CONCAT('thm:', e)
  FROM `radar.article_segment`, UNNEST(themes) AS e
  WHERE segment = 'ai'
),
mentions AS (
  SELECT a.gkg_id, a.week, a.source, a.ent AS topic_id
  FROM art_ents AS a
  JOIN topics AS t ON t.topic_id = a.ent
),
sources AS (
  SELECT
    topic_id, week, source, COUNT(DISTINCT gkg_id) AS n,
    ROW_NUMBER() OVER (PARTITION BY topic_id, week ORDER BY COUNT(DISTINCT gkg_id) DESC, source) AS rk
  FROM mentions
  GROUP BY topic_id, week, source
),
by_topic AS (
  SELECT
    topic_id, week,
    SUM(n) AS n_articles,
    COUNT(*) AS n_sources,
    SAFE_DIVIDE(MAX(n), SUM(n)) AS top_source_share,
    SAFE_DIVIDE(SUM(IF(rk <= 3, n, 0)), SUM(n)) AS top3_source_share
  FROM sources
  GROUP BY topic_id, week
),
week_docs AS (
  SELECT week, COUNT(DISTINCT gkg_id) AS n_week FROM art_ents GROUP BY week
),
specific AS (
  -- entities in at most 10% of the week's ring-1 articles
  SELECT a.week, a.ent
  FROM art_ents AS a
  JOIN week_docs AS w USING (week)
  GROUP BY a.week, a.ent, w.n_week
  HAVING COUNT(DISTINCT a.gkg_id) <= 0.10 * w.n_week
),
co AS (
  SELECT m.topic_id, m.week, a.ent, COUNT(*) AS cnt
  FROM mentions AS m
  JOIN art_ents AS a ON a.gkg_id = m.gkg_id AND a.ent != m.topic_id
  JOIN specific AS sp ON sp.week = a.week AND sp.ent = a.ent
  GROUP BY m.topic_id, m.week, a.ent
),
top5 AS (
  SELECT topic_id, week, ent
  FROM co
  QUALIFY ROW_NUMBER() OVER (PARTITION BY topic_id, week ORDER BY cnt DESC, ent) <= 5
),
article_pattern AS (
  SELECT
    m.topic_id, m.week, m.gkg_id,
    ARRAY_TO_STRING(ARRAY_AGG(DISTINCT t.ent IGNORE NULLS ORDER BY t.ent), '|') AS pattern
  FROM (SELECT DISTINCT topic_id, week, gkg_id FROM mentions) AS m
  LEFT JOIN art_ents AS a ON a.gkg_id = m.gkg_id
  LEFT JOIN top5 AS t ON t.topic_id = m.topic_id AND t.week = m.week AND t.ent = a.ent
  GROUP BY m.topic_id, m.week, m.gkg_id
),
pattern_share AS (
  SELECT topic_id, week, SAFE_DIVIDE(MAX(n), SUM(n)) AS top_theme_pattern_share
  FROM (
    SELECT topic_id, week, pattern, COUNT(*) AS n
    FROM article_pattern
    GROUP BY topic_id, week, pattern
  )
  GROUP BY topic_id, week
)
SELECT
  b.topic_id,
  b.week,
  b.n_articles,
  b.n_sources,
  b.top_source_share,
  b.top3_source_share,
  p.top_theme_pattern_share
FROM by_topic AS b
LEFT JOIN pattern_share AS p USING (topic_id, week);
