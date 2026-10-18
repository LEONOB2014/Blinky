-- S2: one monthly slice. Bytes unchanged vs. the previous version: V2Tone (~97 B/row) was already selected; it is now fully parsed.
-- One monthly slice (example: September 2026). Edit the 4 literals per month (pipelines/ingest/run_bq.py will template them). Dry-run first.
-- Partition window = month +/- 1 day (ingestion-time partitions); DATE filter = exact publication month.
INSERT INTO `radar.gkg_ai` (
  gkg_id, ts, dt, source, url, title, lang, tone, pos_score, neg_score, polarity, activity_density, self_group_ref_density, word_count, orgs, persons, themes, locations, allnames,
  f_url, f_url_short, f_title_strong, f_title_weak, f_org, f_latam_loc, f_latam_src, f_ict, f_control, ingest_day)
WITH base AS (
  SELECT
    GKGRECORDID AS gkg_id,
    SAFE.PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(DATE AS STRING)) AS ts,
    SourceCommonName AS source,
    DocumentIdentifier AS url,
    REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title,
    IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') AS lang,
    -- V2Tone field order (GKG 2.1 codebook): Tone, Positive, Negative, Polarity, ActivityRefDensity, SelfGroupRefDensity, WordCount
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(1)] AS FLOAT64) AS pos_score,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(2)] AS FLOAT64) AS neg_score,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(3)] AS FLOAT64) AS polarity,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(4)] AS FLOAT64) AS activity_density,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(5)] AS FLOAT64) AS self_group_ref_density,
    SAFE_CAST(SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(6)] AS FLOAT64) AS INT64) AS word_count,
    V2Organizations AS orgs,
    V2Persons AS persons,
    V2Themes AS themes,
    V2Locations AS locations,
    AllNames AS allnames,
    _PARTITIONDATE AS ingest_day
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('2026-08-31') AND _PARTITIONTIME < TIMESTAMP('2026-10-02')
    AND DATE >= 20260901000000 AND DATE < 20261001000000
),
flagged AS (
  SELECT
    *,
    DATE(ts) AS dt,
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
SELECT
  gkg_id, ts, dt, source, url, title, lang, tone, pos_score, neg_score, polarity, activity_density, self_group_ref_density, word_count, orgs, persons, themes, locations, allnames,
  f_url, f_url_short, f_title_strong, f_title_weak, f_org, f_latam_loc, f_latam_src, f_ict, f_control, ingest_day
FROM flagged
WHERE dt IS NOT NULL
  -- Wide net (bytes depend on columns, not rows): ring 1 candidates, all ICT news (ring 2), articles naming a
  -- large tech company (rings 2 and 3, contracts/taxonomy.yaml), and the random control sample.
  AND (f_url OR f_url_short OR f_title_strong OR f_title_weak OR f_org
       OR f_ict
       OR REGEXP_CONTAINS(LOWER(IFNULL(orgs, '')), r'(^|;)(google|alphabet|microsoft|apple|amazon|meta platforms|facebook|ibm|intel|amd|advanced micro devices|qualcomm|tsmc|taiwan semiconductor|samsung|oracle|salesforce|tesla|baidu|alibaba|tencent|huawei|bytedance|tiktok|sap|cisco|dell|mercadolibre|globant|nubank)[,;]')
       OR f_control)
QUALIFY ROW_NUMBER() OVER (PARTITION BY gkg_id ORDER BY ingest_day DESC) = 1;
