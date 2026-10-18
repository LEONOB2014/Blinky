-- S10: pruned, emotion-annotated weekly graph for the demo visual (last ~90 days; own tables only, a few GB at most, estimate).
-- Output: radar.viz_nodes_weekly + radar.viz_edges_weekly -> export to Parquet/CSV for Graphistry (primary) or cosmos.gl/sigma.js (backup).
-- Pruning budget per week (tunable): edges n >= 5 AND npmi >= 0.2, nodes = top 400 by weighted degree among those edges,
-- edges kept only between kept nodes, max 2,500 edges per week. Evidence = up to 3 public article URLs + titles per node-week.
CREATE OR REPLACE TABLE `radar.viz_edges_weekly` AS
WITH ew AS (
  SELECT *
  FROM `radar.edges_weekly`
  WHERE wk >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 91 DAY), WEEK(MONDAY))
    AND n >= 5 AND npmi >= 0.2
),
deg AS (
  SELECT wk, ent, SUM(n) AS wdeg
  FROM (SELECT wk, x AS ent, n FROM ew UNION ALL SELECT wk, y, n FROM ew)
  GROUP BY wk, ent
),
top_nodes AS (
  SELECT wk, ent FROM deg
  QUALIFY ROW_NUMBER() OVER (PARTITION BY wk ORDER BY wdeg DESC) <= 400
),
kept AS (
  SELECT ew.*
  FROM ew
  JOIN top_nodes AS a ON a.wk = ew.wk AND a.ent = ew.x
  JOIN top_nodes AS b ON b.wk = ew.wk AND b.ent = ew.y
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ew.wk ORDER BY ew.npmi * LN(1 + ew.n) DESC) <= 2500
),
first_seen AS (
  SELECT x, y, MIN(wk) AS first_wk FROM `radar.edges_weekly` WHERE n >= 3 GROUP BY x, y
),
edge_tone AS (
  -- mean article tone of the co-mentioning articles (for coloring edges)
  SELECT DATE_TRUNC(e1.dt, WEEK(MONDAY)) AS wk, CONCAT(e1.etype, ':', e1.entity) AS x, CONCAT(e2.etype, ':', e2.entity) AS y,
         AVG(g.tone) AS mean_tone
  FROM `radar.article_entities` AS e1
  JOIN `radar.article_entities` AS e2 ON e1.gkg_id = e2.gkg_id AND CONCAT(e1.etype, ':', e1.entity) < CONCAT(e2.etype, ':', e2.entity)
  JOIN `radar.gkg_ai` AS g ON g.gkg_id = e1.gkg_id
  WHERE e1.dt >= DATE_SUB(CURRENT_DATE(), INTERVAL 98 DAY)
  GROUP BY wk, x, y
)
SELECT
  k.wk, k.x AS src, k.y AS dst, k.n, k.n_src, k.npmi,
  f.first_wk, (f.first_wk = k.wk) AS is_new_edge,
  t.mean_tone
FROM kept AS k
LEFT JOIN first_seen AS f USING (x, y)
LEFT JOIN edge_tone AS t ON t.wk = k.wk AND t.x = k.x AND t.y = k.y;

CREATE OR REPLACE TABLE `radar.viz_nodes_weekly` AS
WITH nodes AS (
  SELECT DISTINCT wk, src AS ent FROM `radar.viz_edges_weekly`
  UNION DISTINCT
  SELECT DISTINCT wk, dst FROM `radar.viz_edges_weekly`
),
art AS (
  SELECT DATE_TRUNC(e.dt, WEEK(MONDAY)) AS wk, CONCAT(e.etype, ':', e.entity) AS ent, e.gkg_id,
         g.tone, g.polarity, g.url, g.title, g.lang,
         c.anew_arousal,
         SAFE_DIVIDE(c.roget_fear + c.wna_negative_fear + c.wna_alarm, c.wc) * 1000 AS fear_pk,
         SAFE_DIVIDE(c.roget_hope + c.wna_hopefulness + c.wna_positive_hope + c.wna_enthusiasm, c.wc) * 1000 AS hope_pk
  FROM `radar.article_entities` AS e
  JOIN `radar.gkg_ai` AS g ON g.gkg_id = e.gkg_id
  LEFT JOIN `radar.gcam_ai` AS c ON c.gkg_id = e.gkg_id
  WHERE e.dt >= DATE_SUB(CURRENT_DATE(), INTERVAL 98 DAY)
)
SELECT
  n.wk, n.ent,
  SPLIT(n.ent, ':')[SAFE_OFFSET(0)] AS etype,
  COUNT(DISTINCT a.gkg_id) AS n_docs,
  AVG(a.tone) AS mean_tone,
  AVG(a.polarity) AS mean_polarity,
  AVG(a.anew_arousal) AS mean_arousal,
  AVG(a.fear_pk) AS fear_pk,
  AVG(a.hope_pk) AS hope_pk,
  COUNTIF(a.lang IN ('spa', 'por')) / COUNT(*) AS es_pt_share,
  ARRAY_AGG(STRUCT(a.title, a.url, a.tone) ORDER BY ABS(a.tone) DESC LIMIT 3) AS evidence
FROM nodes AS n
JOIN art AS a ON a.wk = n.wk AND a.ent = n.ent
GROUP BY n.wk, n.ent;
