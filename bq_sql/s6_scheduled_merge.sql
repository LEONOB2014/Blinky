-- S6: daily scheduled query (multi-statement script; Scheduled queries supply @run_date).
-- Cost (estimate): gkg_ai MERGE ~1.7 GB/day (2 ingestion partitions x graph-ready columns; V2Tone was already included)
--                + daily_totals refresh ~0.05 GB/day + own-table rebuilds of the last 5 days (< 0.1 GB) => ~0.055 TiB/month.

-- 1) New candidate rows (late arrivals covered by the 2-partition window; dedup on gkg_id)
MERGE `radar.gkg_ai` AS T
USING (
  WITH base AS (
    SELECT
      GKGRECORDID AS gkg_id,
      SAFE.PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)) AS ts,
      SourceCommonName AS source,
      DocumentIdentifier AS url,
      REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title,
      IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') AS lang,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(1)] AS FLOAT64) AS pos_score,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(2)] AS FLOAT64) AS neg_score,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(3)] AS FLOAT64) AS polarity,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(4)] AS FLOAT64) AS activity_density,
      SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(5)] AS FLOAT64) AS self_group_ref_density,
      SAFE_CAST(SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(6)] AS FLOAT64) AS INT64) AS word_count,
      V2Organizations AS orgs, V2Persons AS persons, V2Themes AS themes, V2Locations AS locations, AllNames AS allnames,
      _PARTITIONDATE AS ingest_day
    FROM `gdelt-bq.gdeltv2.gkg_partitioned`
    WHERE _PARTITIONTIME >= TIMESTAMP(DATE_SUB(@run_date, INTERVAL 2 DAY))
      AND _PARTITIONTIME < TIMESTAMP(@run_date)
  ),
  flagged AS (
    SELECT *, DATE(ts) AS dt,
      REGEXP_CONTAINS(LOWER(url), r'artificial-intelligence|inteligencia-artificial|intelig[a-z0-9%]{1,8}ncia-artificial|intelligence-artificielle|intelligenza-artificiale|kunstliche-intelligenz|chatgpt|openai|anthropic|deepmind|deepseek|generative-ai|genai|ia-generativa|machine-learning|aprendizaje-automatico|large-language|llm|agentic|ai-agent|agentes-de-ia|agentes-ia|copilot|nvidia|hugging-?face') AS f_url,
      (lang = 'eng' AND REGEXP_CONTAINS(LOWER(url), r'[/_-]ai[/_.-]')) OR (lang IN ('spa', 'por') AND REGEXP_CONTAINS(LOWER(url), r'[/_-]ia[/_.-]')) AS f_url_short,
      REGEXP_CONTAINS(LOWER(IFNULL(title, '')), r'artificial intelligence|intelig\S{1,8}ncia artificial|intelligence artificielle|intelligenza artificiale|k\S{1,8}nstliche intelligenz|chatgpt|openai|anthropic|deepmind|deepseek|\bllms?\b|machine learning|aprendizaje autom|aprendizado de m|deep learning|generative ai|\bgen ?ai\b|ia generativa|agentic|agentes? de ia|chatbot|copilot|hugging ?face') AS f_title_strong,
      REGEXP_CONTAINS(LOWER(IFNULL(title, '')), r'\bai\b|\bia\b|\bki\b|\bgemini\b|\bclaude\b|\bgrok\b|\bmistral\b|nvidia') AS f_title_weak,
      REGEXP_CONTAINS(LOWER(IFNULL(orgs, '')), r'(^|;)(openai|anthropic|google deepmind|deepmind|nvidia|nvidia corporation|mistral ai|deepseek|hugging face|perplexity|xai|cohere|stability ai|midjourney|scale ai|databricks|cerebras|groq|safe superintelligence|meta ai)[,;]') AS f_org,
      REGEXP_CONTAINS(IFNULL(locations, ''), r'#(CO|MX|BR|AR|CI|PE|VE|EC|UY|PA|BL|CS|GT|HO|ES|NU|PM|DR|CU|RQ)#') AS f_latam_loc,
      REGEXP_CONTAINS(LOWER(IFNULL(source, '')), r'\.(com\.)?(co|mx|br|ar|cl|pe|ve|ec|uy|py|bo|cr|gt|hn|sv|ni|pa|do|cu)$') AS f_latam_src,
      REGEXP_CONTAINS(IFNULL(themes, ''), r'(^|;)(WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES|WB_2399_ICT_INNOVATION_AND_TRANSFORMATION|TECH_AUTOMATION|TECH_BIGDATA|WB_661_BIG_DATA|WB_669_SOFTWARE_INFRASTRUCTURE|WB_2381_SOFTWARE_DEVELOPMENT)[,;]') AS f_ict,
      MOD(ABS(FARM_FINGERPRINT(gkg_id)), 500) = 0 AS f_control
    FROM base
  )
  SELECT *
  FROM flagged
  WHERE dt IS NOT NULL
    AND (f_url OR f_url_short OR f_title_strong OR f_title_weak OR f_org OR (f_ict AND (f_latam_loc OR f_latam_src)) OR f_control)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY gkg_id ORDER BY ingest_day DESC) = 1
) AS S
ON T.gkg_id = S.gkg_id AND T.dt >= DATE_SUB(@run_date, INTERVAL 5 DAY)
WHEN NOT MATCHED THEN INSERT (
  gkg_id, ts, dt, source, url, title, lang, tone, pos_score, neg_score, polarity, activity_density, self_group_ref_density,
  word_count, orgs, persons, themes, locations, allnames, f_url, f_url_short, f_title_strong, f_title_weak, f_org,
  f_latam_loc, f_latam_src, f_ict, f_control, ingest_day)
VALUES (
  S.gkg_id, S.ts, S.dt, S.source, S.url, S.title, S.lang, S.tone, S.pos_score, S.neg_score, S.polarity, S.activity_density,
  S.self_group_ref_density, S.word_count, S.orgs, S.persons, S.themes, S.locations, S.allnames, S.f_url, S.f_url_short,
  S.f_title_strong, S.f_title_weak, S.f_org, S.f_latam_loc, S.f_latam_src, S.f_ict, S.f_control, S.ingest_day);

-- 2) Refresh denominators for the last 5 publication days (6 cheap ingestion partitions)
DELETE FROM `radar.daily_totals` WHERE dt >= DATE_SUB(@run_date, INTERVAL 5 DAY);
INSERT INTO `radar.daily_totals` (dt, lang_bucket, n_all, n_all_med28, is_missing)
WITH fresh AS (
  SELECT
    DATE(SAFE.PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING))) AS dt,
    CASE WHEN IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') IN ('eng', 'spa', 'por')
         THEN IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') ELSE 'other' END AS lang_bucket,
    COUNT(*) AS n_all
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP(DATE_SUB(@run_date, INTERVAL 6 DAY))
    AND _PARTITIONTIME < TIMESTAMP(@run_date)
    AND DATE >= CAST(FORMAT_DATE('%Y%m%d000000', DATE_SUB(@run_date, INTERVAL 5 DAY)) AS INT64)
  GROUP BY dt, lang_bucket
),
base28 AS (
  SELECT lang_bucket, AVG(n_all) AS mean28
  FROM `radar.daily_totals`
  WHERE dt >= DATE_SUB(@run_date, INTERVAL 33 DAY) AND dt < DATE_SUB(@run_date, INTERVAL 5 DAY) AND NOT is_missing
  GROUP BY lang_bucket
)
SELECT f.dt, f.lang_bucket, f.n_all, b.mean28,
       (b.mean28 IS NOT NULL AND f.n_all < 0.5 * b.mean28) AS is_missing
FROM fresh AS f
LEFT JOIN base28 AS b USING (lang_bucket)
WHERE f.dt IS NOT NULL AND f.dt < @run_date;

-- 3) Rebuild topic assignments and the daily summary for the last 5 days (own tables only; tiny)
DELETE FROM `radar.article_topic` WHERE dt >= DATE_SUB(@run_date, INTERVAL 5 DAY);
INSERT INTO `radar.article_topic` (gkg_id, dt, source, lang, tone, pos_score, neg_score, polarity, latam, topic)
WITH core AS (
  SELECT gkg_id, dt, source, lang, tone, pos_score, neg_score, polarity,
         (f_latam_loc OR f_latam_src) AS latam,
         LOWER(CONCAT(IFNULL(title, ''), ' ', IFNULL(url, ''))) AS txt
  FROM `radar.gkg_ai`
  WHERE dt >= DATE_SUB(@run_date, INTERVAL 5 DAY)
    AND (f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict))
)
SELECT gkg_id, dt, source, lang, tone, pos_score, neg_score, polarity, latam, 'ai_all' FROM core
UNION ALL
SELECT c.gkg_id, c.dt, c.source, c.lang, c.tone, c.pos_score, c.neg_score, c.polarity, c.latam, r.topic
FROM core AS c JOIN `radar.topic_rules` AS r ON REGEXP_CONTAINS(c.txt, r.re);

DELETE FROM `radar.daily_topic` WHERE dt >= DATE_SUB(@run_date, INTERVAL 5 DAY);
INSERT INTO `radar.daily_topic` (
  dt, topic, lang_bucket, latam, n_articles, n_sources, n_tone, sum_tone, sum_tone_sq, sum_polarity, n_pos_x, n_neg_x,
  mean_tone, sd_tone, p10_tone, p90_tone, mean_polarity, n_all_stream, share_of_day, extremity, positive_share,
  negative_share, controversy_index, is_missing)
WITH a AS (
  SELECT dt, topic, CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
         latam, source, tone, polarity
  FROM `radar.article_topic`
  WHERE dt >= DATE_SUB(@run_date, INTERVAL 5 DAY)
),
agg AS (
  SELECT dt, topic, lang_bucket, latam,
    COUNT(*) AS n_articles, COUNT(DISTINCT source) AS n_sources, COUNT(tone) AS n_tone,
    SUM(tone) AS sum_tone, SUM(tone * tone) AS sum_tone_sq, SUM(polarity) AS sum_polarity,
    COUNTIF(tone > 3.0) AS n_pos_x, COUNTIF(tone < -3.0) AS n_neg_x,
    AVG(tone) AS mean_tone, STDDEV_SAMP(tone) AS sd_tone,
    APPROX_QUANTILES(tone, 10)[SAFE_OFFSET(1)] AS p10_tone, APPROX_QUANTILES(tone, 10)[SAFE_OFFSET(9)] AS p90_tone,
    AVG(polarity) AS mean_polarity
  FROM a GROUP BY dt, topic, lang_bucket, latam
)
SELECT
  g.dt, g.topic, g.lang_bucket, g.latam, g.n_articles, g.n_sources, g.n_tone, g.sum_tone, g.sum_tone_sq, g.sum_polarity,
  g.n_pos_x, g.n_neg_x, g.mean_tone, g.sd_tone, g.p10_tone, g.p90_tone, g.mean_polarity,
  t.n_all, SAFE_DIVIDE(g.n_articles, t.n_all), ABS(g.mean_tone),
  SAFE_DIVIDE(g.n_pos_x, g.n_tone), SAFE_DIVIDE(g.n_neg_x, g.n_tone),
  LEAST(1.0, g.mean_polarity / 10.5) * GREATEST(0.0, 1.0 - ABS(g.mean_tone) / 3.0)
    * 2.0 * LEAST(SAFE_DIVIDE(g.n_pos_x, g.n_tone), SAFE_DIVIDE(g.n_neg_x, g.n_tone)),
  IFNULL(t.is_missing, TRUE)
FROM agg AS g
LEFT JOIN `radar.daily_totals` AS t ON t.dt = g.dt AND t.lang_bucket = g.lang_bucket;
