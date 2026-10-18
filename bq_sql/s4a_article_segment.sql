-- S4a: one month of radar.article_segment, the three rings of contracts/taxonomy.yaml (v1, ring 2 tightened).
-- run_bq.py --month YYYY-MM fills the tokens. This is the only step after S2 that scans the wide gkg_ai columns
-- (themes is ~57% of its bytes, measured), once per month; S4 and S11 read this narrow table instead.
-- Rings never overlap:
--   ai        (ring 1)  f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict)
--   it        (ring 2)  an ICT theme AND (a tech organization OR a second, distinct ICT theme), minus ring 1
--   ai_domain (ring 3)  a domain theme group AND a tech organization, minus rings 1-2; domains is multi-label
-- Entity arrays, the lowercased title + URL (txt) and the theme list are kept for ring 1 only (ranking, edges,
-- subtopics); nothing here is exported to git.
CREATE TABLE IF NOT EXISTS `radar.article_segment` (
  gkg_id STRING,
  dt DATE,
  source STRING,
  lang STRING,
  lang_bucket STRING,
  latam BOOL,
  tone FLOAT64,
  polarity FLOAT64,
  segment STRING,
  domains ARRAY<STRING>,
  tech_org BOOL,
  n_ict_themes INT64,
  txt STRING,
  orgs ARRAY<STRING>,
  persons ARRAY<STRING>,
  themes ARRAY<STRING>,
  locs ARRAY<STRING>
)
PARTITION BY dt
CLUSTER BY segment, lang_bucket
OPTIONS (description = 'Rings (segment, domains) per gkg_ai article; ring-1 entity arrays. Built by bq_sql/s4a_article_segment.sql');

DELETE FROM `radar.article_segment` WHERE dt >= '${MONTH_START}' AND dt < '${MONTH_END}';

INSERT INTO `radar.article_segment`
  (gkg_id, dt, source, lang, lang_bucket, latam, tone, polarity, segment, domains, tech_org, n_ict_themes,
   txt, orgs, persons, themes, locs)
WITH src AS (
  SELECT
    gkg_id, dt, source, lang, tone, polarity,
    (f_latam_loc OR f_latam_src) AS latam,
    (f_url OR f_url_short OR f_title_strong OR f_org OR (f_title_weak AND f_ict)) AS ai,
    f_org
      OR REGEXP_CONTAINS(LOWER(IFNULL(orgs, '')), r'(^|;)(google|alphabet|microsoft|apple|amazon|meta platforms|facebook|ibm|intel|amd|advanced micro devices|qualcomm|tsmc|taiwan semiconductor|samsung|oracle|salesforce|tesla|baidu|alibaba|tencent|huawei|bytedance|tiktok|sap|cisco|dell|mercadolibre|globant|nubank)[,;]')
      AS tech_org,
    ARRAY_LENGTH(ARRAY(
      SELECT DISTINCT t FROM UNNEST(REGEXP_EXTRACT_ALL(IFNULL(themes, ''),
        r'(?:^|;)(WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES|WB_2399_ICT_INNOVATION_AND_TRANSFORMATION|TECH_AUTOMATION|TECH_BIGDATA|WB_661_BIG_DATA|WB_669_SOFTWARE_INFRASTRUCTURE|WB_2381_SOFTWARE_DEVELOPMENT),')) AS t
    )) AS n_ict_themes,
    -- Ring-3 domain theme groups: prefixes copied from contracts/taxonomy.yaml `domains` (a test checks them).
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
    title, url, orgs, persons, themes, locations
  FROM `radar.gkg_ai`
  WHERE dt >= '${MONTH_START}' AND dt < '${MONTH_END}'
),
seg AS (
  SELECT
    *,
    CASE
      WHEN ai THEN 'ai'
      WHEN n_ict_themes >= 1 AND (tech_org OR n_ict_themes >= 2) THEN 'it'
      WHEN ARRAY_LENGTH(domain_hits) > 0 AND tech_org THEN 'ai_domain'
    END AS segment
  FROM src
)
SELECT
  gkg_id, dt, source, lang,
  CASE WHEN lang IN ('eng', 'spa', 'por') THEN lang ELSE 'other' END AS lang_bucket,
  latam, tone, polarity, segment,
  IF(segment = 'ai_domain', domain_hits, []) AS domains,
  tech_org, n_ict_themes,
  IF(segment = 'ai', LOWER(CONCAT(IFNULL(title, ''), ' ', IFNULL(url, ''))), NULL) AS txt,
  IF(segment = 'ai', ARRAY(
    SELECT DISTINCT LOWER(TRIM(SPLIT(o, ',')[SAFE_OFFSET(0)])) AS e
    FROM UNNEST(SPLIT(IFNULL(orgs, ''), ';')) AS o
    WHERE TRIM(SPLIT(o, ',')[SAFE_OFFSET(0)]) != ''), []) AS orgs,
  IF(segment = 'ai', ARRAY(
    SELECT DISTINCT LOWER(TRIM(SPLIT(p, ',')[SAFE_OFFSET(0)])) AS e
    FROM UNNEST(SPLIT(IFNULL(persons, ''), ';')) AS p
    WHERE TRIM(SPLIT(p, ',')[SAFE_OFFSET(0)]) != ''), []) AS persons,
  IF(segment = 'ai', ARRAY(
    SELECT DISTINCT SPLIT(th, ',')[SAFE_OFFSET(0)] AS e
    FROM UNNEST(SPLIT(IFNULL(themes, ''), ';')) AS th
    WHERE IFNULL(SPLIT(th, ',')[SAFE_OFFSET(0)], '') != ''), []) AS themes,
  IF(segment = 'ai', ARRAY(
    SELECT DISTINCT SPLIT(l, '#')[SAFE_OFFSET(2)] AS e
    FROM UNNEST(SPLIT(IFNULL(locations, ''), ';')) AS l
    WHERE IFNULL(SPLIT(l, '#')[SAFE_OFFSET(2)], '') != ''), []) AS locs
FROM seg
WHERE segment IS NOT NULL;
