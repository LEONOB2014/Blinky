-- S14: radar.topic_evidence_weekly (contracts/topic_evidence_weekly.schema.json): up to 5 representative ring-1
-- articles per ranked topic and week, for the demo's evidence card. Topics: radar.evidence_topics (the top 30 of each of
-- the last 8 scored weeks, loaded by pipelines/ingest/evidence_topics.py). Titles and URLs stay in the lake; never git.
-- Selection rule (also written per row in why_selected):
--   1. relevance = how many of the topic-week's 5 top *specific* co-mentioned entities the article carries (as WS1c:
--      orgs and themes in at most 10% of that week's ring-1 articles, the topic itself excluded, ties by name);
--   2. at most one article per normalized title (the earliest copy), so one syndicated story repeated by several
--      outlets fills one slot, not five (measured on 2026-W42: the #1 topic's 5 articles were one wire title);
--      titles are normalized by decoding HTML dash and no-break-space entities, dropping a trailing site suffix (the
--      last " - X", " | X" or " :: X" segment, also with an en/em dash, when X is at most 40 characters without
--      another separator and at least 25 characters
--      remain), then lowercasing and collapsing everything that is not a letter or digit; an article without a
--      title counts as its own title. The suffix rule only builds the grouping key: the title shown is untouched
--      (measured before this rule: 16 topic-week groups were one story with and without a site name appended);
--   2b. then at most one article per source (the best one by the order below), so one outlet cannot fill the card;
--   3. order: relevance desc, then es/pt first, then earliest, then gkg_id; keep 5. Articles without an http(s) URL
--      are skipped.
-- The scan is limited to the topics' weeks (script variables prune the dt partitions of the wide url/title columns).
DECLARE lo DATE DEFAULT (SELECT MIN(week) FROM `radar.evidence_topics`);
DECLARE hi DATE DEFAULT (SELECT DATE_ADD(MAX(week), INTERVAL 7 DAY) FROM `radar.evidence_topics`);

CREATE OR REPLACE TABLE `radar.topic_evidence_weekly`
PARTITION BY week
CLUSTER BY topic_id AS
WITH art_ents AS (
  SELECT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)) AS week, CONCAT('org:', e) AS ent
  FROM `radar.article_segment`, UNNEST(orgs) AS e
  WHERE segment = 'ai' AND dt >= lo AND dt < hi
  UNION DISTINCT
  SELECT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)), CONCAT('thm:', e)
  FROM `radar.article_segment`, UNNEST(themes) AS e
  WHERE segment = 'ai' AND dt >= lo AND dt < hi
),
mentions AS (
  SELECT a.gkg_id, a.week, a.ent AS topic_id
  FROM art_ents AS a
  JOIN `radar.evidence_topics` AS t ON t.topic_id = a.ent AND t.week = a.week
),
week_docs AS (
  SELECT week, COUNT(DISTINCT gkg_id) AS n_week FROM art_ents GROUP BY week
),
specific AS (
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
relevance AS (
  SELECT m.topic_id, m.week, m.gkg_id, COUNT(t.ent) AS n_top
  FROM mentions AS m
  LEFT JOIN art_ents AS a ON a.gkg_id = m.gkg_id
  LEFT JOIN top5 AS t ON t.topic_id = m.topic_id AND t.week = m.week AND t.ent = a.ent
  GROUP BY m.topic_id, m.week, m.gkg_id
),
articles AS (
  SELECT
    r.topic_id, r.week, r.n_top, g.gkg_id, g.dt, g.ts, g.source, g.title, g.url, g.tone,
    CASE WHEN g.lang IN ('eng', 'spa', 'por') THEN g.lang ELSE 'other' END AS lang_bucket
  FROM relevance AS r
  JOIN `radar.gkg_ai` AS g ON g.gkg_id = r.gkg_id
  WHERE g.dt >= lo AND g.dt < hi
    AND REGEXP_CONTAINS(IFNULL(g.url, ''), r'^https?://')
    AND IFNULL(g.source, '') != ''
),
keyed AS (
  -- the grouping key of a title: HTML dash and no-break-space entities decoded (GDELT titles are escaped:
  -- "&#x2013;" is the most common entity, often before a site name), then the trailing site suffix dropped,
  -- then lowercased with every run of non-letters and non-digits collapsed
  SELECT
    *,
    IFNULL(NULLIF(TRIM(REGEXP_REPLACE(LOWER(
      IF(LENGTH(TRIM(REGEXP_REPLACE(decoded, r'\s+(?:-|–|—|\||::)\s+[^-–—|:]{1,40}$', ''))) >= 25,
         REGEXP_REPLACE(decoded, r'\s+(?:-|–|—|\||::)\s+[^-–—|:]{1,40}$', ''), decoded)
    ), r'[^\p{L}\p{N}]+', ' ')), ''), gkg_id) AS title_key
  FROM (
    SELECT
      *,
      REGEXP_REPLACE(
        REGEXP_REPLACE(title, r'(?i)&#x(?:2012|2013|2014|2015);', ' - '),
        r'(?i)&#x(?:a0|202f);|&nbsp;', ' ') AS decoded
    FROM articles
  )
),
one_per_title AS (
  SELECT * EXCEPT (decoded, title_key)
  FROM keyed
  QUALIFY ROW_NUMBER() OVER (PARTITION BY topic_id, week, title_key ORDER BY ts, gkg_id) = 1
),
one_per_source AS (
  SELECT *
  FROM one_per_title
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY topic_id, week, source
    ORDER BY n_top DESC, IF(lang_bucket IN ('spa', 'por'), 0, 1), ts, gkg_id
  ) = 1
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY topic_id, week
      ORDER BY n_top DESC, IF(lang_bucket IN ('spa', 'por'), 0, 1), ts, gkg_id
    ) AS evidence_rank
  FROM one_per_source
)
SELECT
  week, topic_id, evidence_rank, gkg_id, dt, source, lang_bucket, title, url, tone,
  CONCAT(
    'carries ', CAST(n_top AS STRING), ' of the 5 top specific co-mentions of the topic that week; ',
    'one article per title (earliest copy) and per source; ties: es/pt first, then earliest'
  ) AS why_selected
FROM ranked
WHERE evidence_rank <= 5;
