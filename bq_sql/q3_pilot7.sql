-- Q3: 7-day pilot of the wide AI net: candidate rates by rule, language and LatAm flag (returns aggregates only)
WITH base AS (
  SELECT
    LOWER(DocumentIdentifier) AS url,
    LOWER(IFNULL(REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>'), '')) AS title,
    LOWER(IFNULL(V2Organizations, '')) AS orgs,
    IFNULL(REGEXP_EXTRACT(TranslationInfo, r'srclc:([a-z]{3})'), 'eng') AS lang,
    REGEXP_CONTAINS(IFNULL(V2Locations, ''), r'#(CO|MX|BR|AR|CI|PE|VE|EC|UY|PA|BL|CS|GT|HO|ES|NU|PM|DR|CU|RQ)#') AS latam_loc
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP('2026-10-09') AND _PARTITIONTIME < TIMESTAMP('2026-10-16')
),
flagged AS (
  SELECT
    lang,
    latam_loc,
    REGEXP_CONTAINS(url, r'artificial-intelligence|inteligencia-artificial|intelig[a-z0-9%]{1,8}ncia-artificial|intelligence-artificielle|intelligenza-artificiale|kunstliche-intelligenz|chatgpt|openai|anthropic|deepmind|deepseek|generative-ai|genai|ia-generativa|machine-learning|aprendizaje-automatico|large-language|llm|agentic|ai-agent|agentes-de-ia|agentes-ia|copilot|nvidia|hugging-?face') AS f_url,
    (lang = 'eng' AND REGEXP_CONTAINS(url, r'[/_-]ai[/_.-]')) OR (lang IN ('spa', 'por') AND REGEXP_CONTAINS(url, r'[/_-]ia[/_.-]')) AS f_url_short,
    REGEXP_CONTAINS(title, r'artificial intelligence|intelig\S{1,8}ncia artificial|intelligence artificielle|intelligenza artificiale|k\S{1,8}nstliche intelligenz|chatgpt|openai|anthropic|deepmind|deepseek|\bllms?\b|machine learning|aprendizaje autom|aprendizado de m|deep learning|generative ai|\bgen ?ai\b|ia generativa|agentic|agentes? de ia|chatbot|copilot|hugging ?face') AS f_title_strong,
    REGEXP_CONTAINS(title, r'\bai\b|\bia\b|\bki\b|\bgemini\b|\bclaude\b|\bgrok\b|\bmistral\b|nvidia') AS f_title_weak,
    REGEXP_CONTAINS(orgs, r'(^|;)(openai|anthropic|google deepmind|deepmind|nvidia|nvidia corporation|mistral ai|deepseek|hugging face|perplexity|xai|cohere|stability ai|midjourney|scale ai|databricks|cerebras|groq|safe superintelligence|meta ai)[,;]') AS f_org
  FROM base
)
SELECT
  lang,
  latam_loc,
  COUNT(*) AS n_rows,
  COUNTIF(f_url) AS n_url,
  COUNTIF(f_url_short) AS n_url_short,
  COUNTIF(f_title_strong) AS n_title_strong,
  COUNTIF(f_title_weak) AS n_title_weak,
  COUNTIF(f_org) AS n_org,
  COUNTIF(f_url OR f_url_short OR f_title_strong OR f_org) AS n_cand_core,
  COUNTIF(f_url OR f_url_short OR f_title_strong OR f_title_weak OR f_org) AS n_cand_wide,
  ROUND(100 * COUNTIF(f_url OR f_url_short OR f_title_strong OR f_title_weak OR f_org) / COUNT(*), 2) AS pct_wide
FROM flagged
GROUP BY lang, latam_loc
HAVING n_rows >= 500
ORDER BY n_rows DESC;
