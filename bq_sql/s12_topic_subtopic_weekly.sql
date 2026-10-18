-- S12: radar.topic_subtopic_weekly (contracts/topic_subtopic_weekly.schema.json): per week and ranked topic, how many
-- of the topic's ring-1 articles carry each AI subtopic. WS4 reads it for a topic's primary subtopic.
-- Topics are the org/thm ids of radar.topic_daily (S11); weeks start on Monday, the edges_weekly key. Multi-label: a
-- topic's rows in one week can sum to more than n_topic_articles; articles with no subtopic count under subtopic NULL.
-- Reads the ring-1 org/theme arrays of radar.article_segment (the same entities S4 puts in article_entities, at less
-- than half the bytes: 1.24 GB vs 2.89 GB, dry runs) and article_topic segment 'ai'.
CREATE OR REPLACE TABLE `radar.topic_subtopic_weekly`
PARTITION BY week
CLUSTER BY topic_id AS
WITH topics AS (
  SELECT DISTINCT topic_id FROM `radar.topic_daily`
),
mentions AS (
  SELECT DISTINCT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)) AS week, CONCAT('org:', e) AS topic_id
  FROM `radar.article_segment`, UNNEST(orgs) AS e
  WHERE segment = 'ai'
  UNION DISTINCT
  SELECT DISTINCT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)), CONCAT('thm:', e)
  FROM `radar.article_segment`, UNNEST(themes) AS e
  WHERE segment = 'ai'
),
ranked AS (
  SELECT m.* FROM mentions AS m JOIN topics USING (topic_id)
),
subtopics AS (
  SELECT DISTINCT gkg_id, topic AS subtopic
  FROM `radar.article_topic`
  WHERE segment = 'ai' AND topic != 'ai_all'
),
labelled AS (
  SELECT r.gkg_id, r.week, r.topic_id, s.subtopic
  FROM ranked AS r
  LEFT JOIN subtopics AS s USING (gkg_id)
),
denom AS (
  SELECT topic_id, week, COUNT(DISTINCT gkg_id) AS n_topic_articles FROM ranked GROUP BY topic_id, week
)
SELECT
  l.topic_id,
  l.week,
  l.subtopic,
  COUNT(DISTINCT l.gkg_id) AS n_articles,
  ANY_VALUE(d.n_topic_articles) AS n_topic_articles
FROM labelled AS l
JOIN denom AS d USING (topic_id, week)
GROUP BY l.topic_id, l.week, l.subtopic;
