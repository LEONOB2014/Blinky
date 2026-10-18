-- S1: own dataset (must be in the US multi-region, same as gdelt-bq) and the candidate table
CREATE SCHEMA IF NOT EXISTS `radar`
OPTIONS (location = 'US', description = 'GDELT AI/IT extract for the 30X radar');

CREATE TABLE IF NOT EXISTS `radar.gkg_ai` (
  gkg_id STRING,
  ts TIMESTAMP,
  dt DATE,
  source STRING,
  url STRING,
  title STRING,
  lang STRING,
  -- V2Tone, GKG 2.1 codebook field order: Tone, Positive Score, Negative Score, Polarity,
  -- Activity Reference Density, Self/Group Reference Density, Word Count
  tone FLOAT64,
  pos_score FLOAT64,
  neg_score FLOAT64,
  polarity FLOAT64,
  activity_density FLOAT64,
  self_group_ref_density FLOAT64,
  word_count INT64,
  orgs STRING,
  persons STRING,
  themes STRING,
  locations STRING,
  allnames STRING,
  f_url BOOL,
  f_url_short BOOL,
  f_title_strong BOOL,
  f_title_weak BOOL,
  f_org BOOL,
  f_latam_loc BOOL,
  f_latam_src BOOL,
  f_ict BOOL,
  f_control BOOL,
  ingest_day DATE
)
PARTITION BY dt
CLUSTER BY lang, source
OPTIONS (description = 'GKG rows matching the wide AI/IT net v1, plus a 0.2% random control sample');

-- Migration for a table created from the earlier S1 version (no-op on a fresh table).
-- New columns are appended at the end; all inserts below use explicit column lists, so order does not matter.
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS pos_score FLOAT64;
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS neg_score FLOAT64;
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS polarity FLOAT64;
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS activity_density FLOAT64;
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS self_group_ref_density FLOAT64;
ALTER TABLE `radar.gkg_ai` ADD COLUMN IF NOT EXISTS word_count INT64;

-- Topic rules (regex buckets over lowercased title + URL). Edit freely; rebuild S4 afterwards.
CREATE OR REPLACE TABLE `radar.topic_rules` AS
SELECT * FROM UNNEST([
  STRUCT('agents' AS topic, r'agent|agente|agentic' AS re),
  ('llms_models', r'\bllms?\b|language model|modelo de lenguaje|gpt-?[0-9]|chatgpt|gemini|claude|llama|deepseek|qwen|mistral'),
  ('chips_infra', r'nvidia|\bgpus?\b|\bchips?\b|semiconduct|data cent|centro de datos|centros de datos|datacenter'),
  ('regulation_policy', r'regulat|regula|\blaw\b|\bley\b|\blei\b|policy|pol[ií]tica|\bact\b'),
  ('education', r'educa|school|escuela|escola|universi|student|estudiant|aluno'),
  ('jobs_work', r'\bjobs?\b|empleo|emprego|trabajo|trabalho|workforce|layoff|despido|demiss'),
  ('business_adoption', r'enterprise|empresa|adoption|adopci|ado[cç][aã]o|productiv|produtiv'),
  ('safety_risk', r'safety|seguridad|seguran|\brisks?\b|riesgo|risco|deepfake|misinformation|desinformaci|fraud|fraude'),
  ('creative_media', r'\bmusic|m[uú]sica|\bfilm|pel[ií]cula|\bart\b|arte|creator|creador|hollywood|copyright|derechos de autor'),
  ('health_science', r'health|salud|sa[uú]de|medic|hospital|cancer|c[aá]ncer|drug discovery|science|ciencia|ci[eê]ncia'),
  ('funding_markets', r'funding|financiaci|investment|inversi[oó]n|investimento|valuation|valoraci|\bipo\b|stock|acciones|a[cç][oõ]es|bubble|burbuja')
]);
