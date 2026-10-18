-- S5: export small tables to GCS as Parquet (EXPORT DATA bills the query bytes of OUR small table only)
EXPORT DATA OPTIONS (
  uri = 'gs://YOUR_BUCKET/radar/edges_weekly/part-*.parquet',
  format = 'PARQUET',
  compression = 'SNAPPY',
  overwrite = true
) AS
SELECT * FROM `radar.edges_weekly`;
