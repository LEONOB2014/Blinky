-- Q2: true BigQuery logical bytes per row for each column, for one ingestion day (GCAM excluded on purpose)
-- BigQuery STRING logical size = 2 bytes + UTF-8 length; NULL = 0 bytes; INT64 = 8 bytes
SELECT
  COUNT(*) AS n_rows,
  COUNTIF(TranslationInfo IS NOT NULL AND TranslationInfo != '') AS n_translated,
  AVG(IF(DocumentIdentifier IS NULL, 0, BYTE_LENGTH(DocumentIdentifier) + 2)) AS b_DocumentIdentifier,
  AVG(IF(SourceCommonName IS NULL, 0, BYTE_LENGTH(SourceCommonName) + 2)) AS b_SourceCommonName,
  AVG(IF(GKGRECORDID IS NULL, 0, BYTE_LENGTH(GKGRECORDID) + 2)) AS b_GKGRECORDID,
  AVG(IF(V2Organizations IS NULL, 0, BYTE_LENGTH(V2Organizations) + 2)) AS b_V2Organizations,
  AVG(IF(V2Persons IS NULL, 0, BYTE_LENGTH(V2Persons) + 2)) AS b_V2Persons,
  AVG(IF(V2Themes IS NULL, 0, BYTE_LENGTH(V2Themes) + 2)) AS b_V2Themes,
  AVG(IF(V2Locations IS NULL, 0, BYTE_LENGTH(V2Locations) + 2)) AS b_V2Locations,
  AVG(IF(V2Tone IS NULL, 0, BYTE_LENGTH(V2Tone) + 2)) AS b_V2Tone,
  AVG(IF(AllNames IS NULL, 0, BYTE_LENGTH(AllNames) + 2)) AS b_AllNames,
  AVG(IF(Amounts IS NULL, 0, BYTE_LENGTH(Amounts) + 2)) AS b_Amounts,
  AVG(IF(TranslationInfo IS NULL, 0, BYTE_LENGTH(TranslationInfo) + 2)) AS b_TranslationInfo,
  AVG(IF(Extras IS NULL, 0, BYTE_LENGTH(Extras) + 2)) AS b_Extras,
  AVG(IF(Quotations IS NULL, 0, BYTE_LENGTH(Quotations) + 2)) AS b_Quotations,
  AVG(IF(SharingImage IS NULL, 0, BYTE_LENGTH(SharingImage) + 2)) AS b_SharingImage
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME = TIMESTAMP('2026-10-16');
