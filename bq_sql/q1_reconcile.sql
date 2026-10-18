-- Q1: reconcile BigQuery row counts against the raw files (expect ~110k eng + ~221k translated per publication day)
SELECT
  _PARTITIONDATE AS partition_day,
  DIV(DATE, 1000000) AS pub_day,
  IF(TranslationInfo IS NULL OR TranslationInfo = '', 'eng', 'trans') AS stream,
  COUNT(*) AS n_rows,
  COUNT(DISTINCT GKGRECORDID) AS n_ids,
  MIN(DATE) AS min_ts,
  MAX(DATE) AS max_ts
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP('2026-10-13')
GROUP BY partition_day, pub_day, stream
ORDER BY partition_day, pub_day, stream;
