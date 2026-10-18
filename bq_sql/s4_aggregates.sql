-- S4: aggregates over radar.article_segment (bq_sql/s4a_article_segment.sql, run per month first). Reads no wide
-- gkg_ai column. Rings and domains follow contracts/taxonomy.yaml; ranking, entities and edges use ring 1 only.
-- S4-0: topic rules (regex buckets over lowercased title + URL of ring-1 articles; theme_re, when set, also matches a
-- GKG theme of the article). energy_climate's rules are copied from contracts/taxonomy.yaml (a test checks it).
-- Edit freely and re-run S4 (it reads radar.article_segment, so no rescan of gkg_ai).
CREATE OR REPLACE TABLE `radar.topic_rules` AS
SELECT * FROM UNNEST([
  STRUCT('agents' AS topic, r'agent|agente|agentic' AS re, CAST(NULL AS STRING) AS theme_re),
  ('llms_models', r'\bllms?\b|language model|modelo de lenguaje|gpt-?[0-9]|chatgpt|gemini|claude|llama|deepseek|qwen|mistral', NULL),
  ('chips_infra', r'nvidia|\bgpus?\b|\bchips?\b|semiconduct|data cent|centro de datos|centros de datos|datacenter', NULL),
  ('regulation_policy', r'regulat|regula|\blaw\b|\bley\b|\blei\b|policy|pol[ií]tica|\bact\b', NULL),
  ('education', r'educa|school|escuela|escola|universi|student|estudiant|aluno', NULL),
  ('jobs_work', r'\bjobs?\b|empleo|emprego|trabajo|trabalho|workforce|layoff|despido|demiss', NULL),
  ('business_adoption', r'enterprise|empresa|adoption|adopci|ado[cç][aã]o|productiv|produtiv', NULL),
  ('safety_risk', r'safety|seguridad|seguran|\brisks?\b|riesgo|risco|deepfake|misinformation|desinformaci|fraud|fraude', NULL),
  ('creative_media', r'\bmusic|m[uú]sica|\bfilm|pel[ií]cula|\bart\b|arte|creator|creador|hollywood|copyright|derechos de autor', NULL),
  ('health_science', r'health|salud|sa[uú]de|medic|hospital|cancer|c[aá]ncer|drug discovery|science|ciencia|ci[eê]ncia', NULL),
  ('funding_markets', r'funding|financiaci|investment|inversi[oó]n|investimento|valuation|valoraci|\bipo\b|stock|acciones|a[cç][oõ]es|bubble|burbuja', NULL),
  ('energy_climate', r'climate|clima|carbon|carbono|emission|emisi[oó]n|emiss[aã]o|energy|energ[ií]a|power grid|electricity|electricidad|eletricidade|water use|consumo de agua|consumo de [aá]gua|nuclear|renewable|renovable|renov[aá]vel', r'^(ENV_|ENERGY)')
]);

-- S4a: long entity table from ring-1 articles only (orgs, persons, every GKG theme, location countries).
-- Persons feed the graph context only; they are never ranked (taxonomy.yaml ranked_entity_types).
CREATE OR REPLACE TABLE `radar.article_entities`
PARTITION BY dt
CLUSTER BY etype, entity AS
SELECT DISTINCT gkg_id, dt, source, lang, etype, entity
FROM (
  SELECT gkg_id, dt, source, lang, 'org' AS etype, e AS entity FROM `radar.article_segment`, UNNEST(orgs) AS e WHERE segment = 'ai'
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'per', e FROM `radar.article_segment`, UNNEST(persons) AS e WHERE segment = 'ai'
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'thm', e FROM `radar.article_segment`, UNNEST(themes) AS e WHERE segment = 'ai'
  UNION ALL
  SELECT gkg_id, dt, source, lang, 'loc', e FROM `radar.article_segment`, UNNEST(locs) AS e WHERE segment = 'ai'
)
WHERE entity IS NOT NULL AND entity != '';

-- S4b: weekly co-occurrence edges with NPMI among ring-1 entities (arrives pre-aggregated and small)
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

-- S4c: article -> topic assignment with its ring (regex v1; replace later with the LLM labels loaded back with a free load job)
--   ring 1 (segment 'ai'):        'ai_all' plus the subtopics whose rule matches (multi-label, ring 1 only)
--   ring 2 (segment 'it'):        'it_all'
--   ring 3 (segment 'ai_domain'): 'domain:<id>' once per matched domain (multi-label), domain = <id>
-- Articles in no ring (the control sample) are excluded.
CREATE OR REPLACE TABLE `radar.article_topic`
PARTITION BY dt
CLUSTER BY topic AS
WITH a AS (
  SELECT gkg_id, dt, source, lang, tone, polarity, latam, segment, domains, txt, themes
  FROM `radar.article_segment`
)
SELECT gkg_id, dt, source, lang, tone, polarity, latam, segment, CAST(NULL AS STRING) AS domain, 'ai_all' AS topic
FROM a WHERE segment = 'ai'
UNION ALL
SELECT a.gkg_id, a.dt, a.source, a.lang, a.tone, a.polarity, a.latam, a.segment, NULL, r.topic
FROM a
CROSS JOIN `radar.topic_rules` AS r  -- 12 rules; EXISTS is not allowed in a join predicate
WHERE a.segment = 'ai'
  AND (REGEXP_CONTAINS(a.txt, r.re)
       OR (r.theme_re IS NOT NULL AND EXISTS (SELECT 1 FROM UNNEST(a.themes) AS t WHERE REGEXP_CONTAINS(t, r.theme_re))))
UNION ALL
SELECT gkg_id, dt, source, lang, tone, polarity, latam, segment, NULL, 'it_all'
FROM a WHERE segment = 'it'
UNION ALL
SELECT gkg_id, dt, source, lang, tone, polarity, latam, segment, d, CONCAT('domain:', d)
FROM a, UNNEST(domains) AS d WHERE segment = 'ai_domain';

-- S4d: daily summary keyed by day x topic x segment x domain x lang_bucket x latam, with volume, share and tone statistics.
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
    dt, topic, segment, domain,
    CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
    latam, source, tone, polarity
  FROM `radar.article_topic`
),
agg AS (
  SELECT
    dt, topic, segment, domain, lang_bucket, latam,
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
  GROUP BY dt, topic, segment, domain, lang_bucket, latam
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
