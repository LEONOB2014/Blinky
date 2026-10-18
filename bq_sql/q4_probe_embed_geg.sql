-- Q4a (DRY RUN ONLY: read the green "This query will process ..." estimate, then do NOT run): is gsg_docembed pruned by date?
SELECT url, title, lang
FROM `gdelt-bq.gdeltv2.gsg_docembed`
WHERE date >= TIMESTAMP('2026-10-16') AND date < TIMESTAMP('2026-10-17');

-- Q4b (DRY RUN ONLY): bytes for the 512-d embedding column for the same day
SELECT docembed
FROM `gdelt-bq.gdeltv2.gsg_docembed`
WHERE date >= TIMESTAMP('2026-10-16') AND date < TIMESTAMP('2026-10-17');

-- Q4c (DRY RUN ONLY): GEG Cloud NL entities, selected leaf fields only, one day
SELECT url, lang, e.name, e.type, e.mid, e.avgSalience
FROM `gdelt-bq.gdeltv2.geg_gcnlapi`, UNNEST(entities) AS e
WHERE date >= TIMESTAMP('2026-10-16') AND date < TIMESTAMP('2026-10-17');
