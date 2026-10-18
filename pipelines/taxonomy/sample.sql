-- Stratified article sample (Aug-Oct 2026) for WS2b teacher distillation, active-learning pool, and filter P/R evaluation.
-- Built via pipelines/ingest/run_bq.py --workstream WS2 --cap-gib 30.
-- Destination table radar.label_sample is read via free tabledata.list (bq head) into lake/labels/sample.parquet
-- and lake/labels/pool.parquet. Titles and URLs never enter git.
CREATE OR REPLACE TABLE `radar.label_sample` AS
WITH base AS (
  SELECT
    gkg_id,
    dt,
    source,
    url,
    title,
    lang,
    CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
    lang IN ('spa', 'por') AS is_es_pt,
    tone,
    polarity,
    word_count,
    f_url,
    f_url_short,
    f_title_strong,
    f_title_weak,
    f_org,
    f_latam_loc,
    f_latam_src,
    f_ict,
    f_control,
    (f_latam_loc OR f_latam_src) AS latam,
    (f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict)) AS ai,
    f_org
      OR REGEXP_CONTAINS(LOWER(IFNULL(orgs, '')), r'(^|;)(google|alphabet|microsoft|apple|amazon|meta platforms|facebook|ibm|intel|amd|advanced micro devices|qualcomm|tsmc|taiwan semiconductor|samsung|oracle|salesforce|tesla|baidu|alibaba|tencent|huawei|bytedance|tiktok|sap|cisco|dell|mercadolibre|globant|nubank)[,;]')
      AS tech_org,
    ARRAY_LENGTH(ARRAY(
      SELECT DISTINCT t FROM UNNEST(REGEXP_EXTRACT_ALL(IFNULL(themes, ''),
        r'(?:^|;)(WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES|WB_2399_ICT_INNOVATION_AND_TRANSFORMATION|TECH_AUTOMATION|TECH_BIGDATA|WB_661_BIG_DATA|WB_669_SOFTWARE_INFRASTRUCTURE|WB_2381_SOFTWARE_DEVELOPMENT),')) AS t
    )) AS n_ict_themes,
    ARRAY(
      SELECT d.domain FROM UNNEST([
        STRUCT('business' AS domain, r'(?:^|;)(?:ECON_|WB_1235_|WB_2670_)' AS re),
        ('climate', r'(?:^|;)(?:ENV_|ENERGY|NATURAL_DISASTER)'),
        ('labour', r'(?:^|;)(?:UNEMPLOYMENT|LABOR|WB_2689_)'),
        ('health', r'(?:^|;)(?:HEALTH_|MEDICAL|WB_621_)'),
        ('education', r'(?:^|;)(?:EDUCATION|WB_470_)'),
        ('elections_misinformation', r'(?:^|;)(?:ELECTION|MEDIA_CENSORSHIP|TAX_FNCACT_PROPAGANDIST)'),
        ('law_regulation', r'(?:^|;)(?:LEGISLATION|WB_696_|GENERAL_GOVERNMENT)'),
        ('security', r'(?:^|;)(?:CYBER_ATTACK|SECURITY_SERVICES|SURVEILLANCE)')
      ]) AS d
      WHERE REGEXP_CONTAINS(IFNULL(themes, ''), d.re)
      ORDER BY d.domain
    ) AS domain_hits,
    LOWER(CONCAT(IFNULL(title, ''), ' ', IFNULL(url, ''))) AS txt,
    orgs AS raw_orgs,
    themes AS raw_themes
  FROM `radar.gkg_ai`
  WHERE dt >= '2026-08-01' AND dt <= '2026-10-31'
),
segmented AS (
  SELECT
    *,
    (f_ict OR tech_org) AS tech_themed,
    CASE
      WHEN ai THEN 'ai'
      WHEN n_ict_themes >= 1 AND (tech_org OR n_ict_themes >= 2) THEN 'it'
      WHEN ARRAY_LENGTH(domain_hits) > 0 AND tech_org THEN 'ai_domain'
      ELSE 'control'
    END AS raw_segment,
    CASE
      WHEN ai THEN 'ai'
      WHEN f_control THEN 'control'
      WHEN n_ict_themes >= 1 AND (tech_org OR n_ict_themes >= 2) THEN 'it'
      WHEN ARRAY_LENGTH(domain_hits) > 0 AND tech_org THEN 'ai_domain'
      ELSE NULL
    END AS segment,
    CASE
      WHEN ai THEN 'ring1'
      WHEN f_control THEN 'rejected'
      WHEN n_ict_themes >= 1 AND (tech_org OR n_ict_themes >= 2) THEN 'ring2'
      WHEN ARRAY_LENGTH(domain_hits) > 0 AND tech_org THEN 'ring3'
      ELSE NULL
    END AS stratum
  FROM base
),
pop AS (
  SELECT
    COUNTIF(raw_segment = 'ai') AS pop_n_ring1,
    COUNTIF(raw_segment = 'it') AS pop_n_ring2,
    COUNTIF(raw_segment = 'ai_domain') AS pop_n_ring3,
    COUNTIF(f_control AND NOT ai) AS pop_n_control_rej,
    COUNTIF(f_control AND tech_themed AND ai) AS pop_n_acc_tech_ctrl,
    COUNTIF(f_control AND tech_themed AND NOT ai) AS pop_n_rej_tech_ctrl,
    COUNTIF(f_control AND ai) AS pop_n_acc_all_ctrl,
    COUNTIF(f_control AND NOT ai) AS pop_n_rej_all_ctrl
  FROM segmented
),
candidates AS (
  SELECT
    s.*,
    CASE s.stratum
      WHEN 'ring1' THEN 1500
      WHEN 'ring2' THEN 1000
      WHEN 'ring3' THEN 500
      WHEN 'rejected' THEN 1000
    END AS target_sample_n,
    CASE s.stratum
      WHEN 'ring1' THEN 4500
      WHEN 'ring2' THEN 3000
      WHEN 'ring3' THEN 1500
      WHEN 'rejected' THEN 3000
    END AS target_total_n,
    ROW_NUMBER() OVER (
      PARTITION BY s.stratum, s.is_es_pt
      ORDER BY
        -- Ensure tech-themed control rows (accepted in ring1 and rejected in rejected) are well-represented
        CASE
          WHEN s.stratum = 'ring1' AND s.f_control AND s.tech_themed THEN 0
          WHEN s.stratum = 'rejected' AND s.tech_themed AND MOD(ABS(FARM_FINGERPRINT(s.gkg_id)), 2) = 0 THEN 0
          ELSE 1
        END,
        FARM_FINGERPRINT(CONCAT(s.gkg_id, ':ws2b_v1'))
    ) AS rn_lang
  FROM segmented AS s
  WHERE s.stratum IS NOT NULL
    AND s.title IS NOT NULL
    AND LENGTH(TRIM(s.title)) > 5
    AND s.url IS NOT NULL
),
ranked AS (
  SELECT
    c.*,
    ROW_NUMBER() OVER (
      PARTITION BY c.stratum
      ORDER BY
        -- Phase 1: initial sample (36% es/pt, 64% other -> >= 30% es/pt in every stratum)
        CASE
          WHEN c.is_es_pt AND c.rn_lang <= CAST(ROUND(0.36 * c.target_sample_n) AS INT64) THEN 0
          WHEN NOT c.is_es_pt AND c.rn_lang <= (c.target_sample_n - CAST(ROUND(0.36 * c.target_sample_n) AS INT64)) THEN 0
          WHEN c.is_es_pt AND c.rn_lang <= CAST(ROUND(0.36 * c.target_total_n) AS INT64) THEN 1
          WHEN NOT c.is_es_pt AND c.rn_lang <= (c.target_total_n - CAST(ROUND(0.36 * c.target_total_n) AS INT64)) THEN 1
          ELSE 2
        END,
        c.rn_lang,
        FARM_FINGERPRINT(c.gkg_id)
    ) AS rn_stratum
  FROM candidates AS c
)
SELECT
  r.gkg_id,
  r.dt,
  r.source,
  r.url,
  r.title,
  r.lang,
  r.lang_bucket,
  r.is_es_pt,
  r.stratum,
  r.segment,
  r.raw_segment,
  IF(r.raw_segment = 'ai_domain', ARRAY_TO_STRING(r.domain_hits, ';'), '') AS domains,
  ARRAY_TO_STRING(ARRAY(
    SELECT rule.topic FROM UNNEST([
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
      ('energy_climate', r'climate|clima|carbon|carbono|emission|emisi[oó]n|emiss[aã]o|energy|energ[ií]a|power grid|electricity|electricidad|eletricidade|water use|consumo de agua|consumo de [aá]gua|nuclear|renewable|renovable|renov[aá]vel', r'(?:^|;)(?:ENV_|ENERGY)')
    ]) AS rule
    WHERE REGEXP_CONTAINS(r.txt, rule.re)
       OR (rule.theme_re IS NOT NULL AND REGEXP_CONTAINS(IFNULL(r.raw_themes, ''), rule.theme_re))
    ORDER BY rule.topic
  ), ';') AS regex_subtopics,
  ARRAY_TO_STRING(ARRAY(
    SELECT DISTINCT SPLIT(th, ',')[SAFE_OFFSET(0)] AS e
    FROM UNNEST(SPLIT(IFNULL(r.raw_themes, ''), ';')) AS th
    WHERE IFNULL(SPLIT(th, ',')[SAFE_OFFSET(0)], '') != ''
    LIMIT 12
  ), ';') AS top_themes,
  ARRAY_TO_STRING(ARRAY(
    SELECT DISTINCT LOWER(TRIM(SPLIT(o, ',')[SAFE_OFFSET(0)])) AS e
    FROM UNNEST(SPLIT(IFNULL(r.raw_orgs, ''), ';')) AS o
    WHERE TRIM(SPLIT(o, ',')[SAFE_OFFSET(0)]) != ''
    LIMIT 10
  ), ';') AS top_orgs,
  r.tone,
  r.polarity,
  r.word_count,
  r.f_url,
  r.f_url_short,
  r.f_title_strong,
  r.f_title_weak,
  r.f_org,
  r.f_latam_loc,
  r.f_latam_src,
  r.f_ict,
  r.f_control,
  r.tech_org,
  r.n_ict_themes,
  r.tech_themed,
  r.rn_stratum,
  IF(r.rn_stratum <= r.target_sample_n, 'sample', 'pool') AS pool_split,
  p.pop_n_ring1,
  p.pop_n_ring2,
  p.pop_n_ring3,
  p.pop_n_control_rej,
  p.pop_n_acc_tech_ctrl,
  p.pop_n_rej_tech_ctrl,
  p.pop_n_acc_all_ctrl,
  p.pop_n_rej_all_ctrl
FROM ranked AS r
CROSS JOIN pop AS p
WHERE r.rn_stratum <= r.target_total_n;
