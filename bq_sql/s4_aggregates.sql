-- S4a: long entity table from our own small table (orgs, persons, whitelisted themes, location countries)
CREATE OR REPLACE TABLE `radar.article_entities`
PARTITION BY dt
CLUSTER BY etype, entity AS
SELECT DISTINCT gkg_id, dt, source, lang, etype, entity
FROM (
  SELECT gkg_id, dt, source, lang, 'org' AS etype, LOWER(TRIM(SPLIT(o, ',')[SAFE_OFFSET(0)])) AS entity
  FROM `radar.gkg_ai`, UNNEST(SPLIT(IFNULL(orgs, ''), ';')) AS o
  WHERE o != ''
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'per', LOWER(TRIM(SPLIT(p, ',')[SAFE_OFFSET(0)]))
  FROM `radar.gkg_ai`, UNNEST(SPLIT(IFNULL(persons, ''), ';')) AS p
  WHERE p != ''
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'thm', SPLIT(th, ',')[SAFE_OFFSET(0)]
  FROM `radar.gkg_ai`, UNNEST(SPLIT(IFNULL(themes, ''), ';')) AS th
  WHERE REGEXP_CONTAINS(th, r'^(TECH_|WB_133_|WB_2399_|WB_661_|WB_669_|WB_2381_|WB_680_|WB_2457_|WB_2416_|EDUCATION|UNEMPLOYMENT|LEGISLATION)')
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'loc', SPLIT(l, '#')[SAFE_OFFSET(2)]
  FROM `radar.gkg_ai`, UNNEST(SPLIT(IFNULL(locations, ''), ';')) AS l
  WHERE l != '' AND IFNULL(SPLIT(l, '#')[SAFE_OFFSET(2)], '') != ''
)
WHERE entity IS NOT NULL AND entity != '';

-- S4b: weekly co-occurrence edges with NPMI (arrives pre-aggregated and small)
CREATE OR REPLACE TABLE `radar.edges_weekly`
CLUSTER BY x, y AS
WITH e AS (
  SELECT DISTINCT gkg_id, DATE_TRUNC(dt, WEEK(MONDAY)) AS wk, source, CONCAT(etype, ':', entity) AS ent
  FROM `radar.article_entities`
),
pairs AS (
  SELECT a.wk, a.ent AS x, b.ent AS y, COUNT(*) AS n, COUNT(DISTINCT a.source) AS n_src
  FROM e AS a
  JOIN e AS b ON a.gkg_id = b.gkg_id AND a.ent < b.ent
  GROUP BY a.wk, x, y
),
deg AS (
  SELECT wk, ent, COUNT(*) AS nx FROM e GROUP BY wk, ent
),
tot AS (
  SELECT wk, COUNT(DISTINCT gkg_id) AS n_docs FROM e GROUP BY wk
)
SELECT
  p.wk, p.x, p.y, p.n, p.n_src, d1.nx, d2.nx AS ny, t.n_docs,
  SAFE_DIVIDE(LN(SAFE_DIVIDE(p.n * t.n_docs, d1.nx * d2.nx)), -LN(SAFE_DIVIDE(p.n, t.n_docs))) AS npmi
FROM pairs AS p
JOIN tot AS t ON t.wk = p.wk
JOIN deg AS d1 ON d1.wk = p.wk AND d1.ent = p.x
JOIN deg AS d2 ON d2.wk = p.wk AND d2.ent = p.y
WHERE p.n >= 3;

-- S4c: article -> topic assignment (regex v1; replace later with the LLM labels loaded back with a free load job)
-- 'ai_all' = core AI articles; subtopics are assigned only within ai_all. Control-only rows are excluded.
CREATE OR REPLACE TABLE `radar.article_topic`
PARTITION BY dt
CLUSTER BY topic AS
WITH core AS (
  SELECT
    gkg_id, dt, source, lang, tone, pos_score, neg_score, polarity,
    (f_latam_loc OR f_latam_src) AS latam,
    LOWER(CONCAT(IFNULL(title, ''), ' ', IFNULL(url, ''))) AS txt
  FROM `radar.gkg_ai`
  WHERE f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict)
)
SELECT gkg_id, dt, source, lang, tone, pos_score, neg_score, polarity, latam, 'ai_all' AS topic
FROM core
UNION ALL
SELECT c.gkg_id, c.dt, c.source, c.lang, c.tone, c.pos_score, c.neg_score, c.polarity, c.latam, r.topic
FROM core AS c
JOIN `radar.topic_rules` AS r ON REGEXP_CONTAINS(c.txt, r.re);

-- S4d: daily summary keyed by day x topic x lang_bucket x latam, with volume, share and tone statistics.
-- Controversy index (documented in MASTER_PLAN.md section 9):
--   X = 3.0 tone points (~1 SD of article tone on AI rows; measured on the PoC: 14% > +3, 16% < -3)
--   P_REF = 10.5 polarity (~P90 of article polarity on AI rows, PoC)
--   charge     = LEAST(1, mean_polarity / P_REF)
--   neutrality = GREATEST(0, 1 - ABS(mean_tone) / X)
--   two_sided  = 2 * LEAST(positive_share, negative_share)      (1 = half very positive, half very negative)
--   controversy_index = charge * neutrality * two_sided            (0..1; read it relative to its own baseline)
CREATE OR REPLACE TABLE `radar.daily_topic`
PARTITION BY dt
CLUSTER BY topic, lang_bucket AS
WITH a AS (
  SELECT
    dt, topic,
    CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
    latam, source, tone, polarity
  FROM `radar.article_topic`
),
agg AS (
  SELECT
    dt, topic, lang_bucket, latam,
    COUNT(*) AS n_articles,
    COUNT(DISTINCT source) AS n_sources,
    COUNT(tone) AS n_tone,
    SUM(tone) AS sum_tone,
    SUM(tone * tone) AS sum_tone_sq,
    SUM(polarity) AS sum_polarity,
    COUNTIF(tone > 3.0) AS n_pos_x,
    COUNTIF(tone < -3.0) AS n_neg_x,
    AVG(tone) AS mean_tone,
    STDDEV_SAMP(tone) AS sd_tone,
    APPROX_QUANTILES(tone, 10)[SAFE_OFFSET(1)] AS p10_tone,
    APPROX_QUANTILES(tone, 10)[SAFE_OFFSET(9)] AS p90_tone,
    AVG(polarity) AS mean_polarity
  FROM a
  GROUP BY dt, topic, lang_bucket, latam
)
SELECT
  g.*,
  t.n_all AS n_all_stream,
  SAFE_DIVIDE(g.n_articles, t.n_all) AS share_of_day,
  ABS(g.mean_tone) AS extremity,
  SAFE_DIVIDE(g.n_pos_x, g.n_tone) AS positive_share,
  SAFE_DIVIDE(g.n_neg_x, g.n_tone) AS negative_share,
  LEAST(1.0, g.mean_polarity / 10.5)
    * GREATEST(0.0, 1.0 - ABS(g.mean_tone) / 3.0)
    * 2.0 * LEAST(SAFE_DIVIDE(g.n_pos_x, g.n_tone), SAFE_DIVIDE(g.n_neg_x, g.n_tone)) AS controversy_index,
  IFNULL(t.is_missing, TRUE) AS is_missing
FROM agg AS g
LEFT JOIN `radar.daily_totals` AS t
  ON t.dt = g.dt AND t.lang_bucket = g.lang_bucket;
