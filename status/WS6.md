# WS6 status

Owner: Grok CLI · Directories: `entity/, crosssource/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 02:19 UTC-5, branch `feat/ws6-wikipedia-pageviews`, PR not opened (needs approval)

## Done

- `entity/wikidata.py` resolves topics with wbsearchentities (es/en/pt) and a P31 check.
- Persons are never resolved.
- `crosssource/pageviews.py` fetches daily `agent=user` pageviews from 2025-10-01.
- Gold and the 8-week dev cut (2026-08-24 .. 2026-10-17) land in the lake.
- Unit tests parse one real cached response per endpoint.

## In progress

- Priority es/pt pageviews are written. Extras pageviews were not started.
- Full `topic_daily` is included when the lake file exists. It was present.

## Blocked on

## Numbers (each marked measured or estimate)

Phase: Done.

- topics attempted: 11060 (measured)
- resolved exact: 1916 (measured)
- resolved alias: 997 (measured)
- resolved none: 8147 (measured)
- articles found, es / pt / en: 1306 / 1138 / 2289 (measured)
- pageview rows in gold: 189167 (measured)
- pageview rows in the 8-week dev cut: 14772 (measured)
- pageview end date returned by the API: 2026-10-18 (measured)
- failed requests (final non-200): 0 (measured)
- priority topics: 679 (measured)
- priority exact / alias / none: 373 / 105 / 201 (measured)
- priority topics sent to Wikidata this run: 201 (measured)
- priority articles found, es / pt / en: 273 / 255 / 406 (measured)
- priority pageview articles attempted / HTTP 200: 521 / 521 (measured)
- priority pageviews: es.wikipedia and pt.wikipedia, 2025-10-01 .. 2026-10-18
- HTTP 429: 0 (measured)
- write times:
  - 2026-10-18 01:22 UTC-5 topic_wikidata rows 11060 (measured)
  - 2026-10-18 01:27 UTC-5 wiki_pageviews_daily rows 17764 (dev cut 1339, end 2026-10-18) (measured)
  - 2026-10-18 01:33 UTC-5 wiki_pageviews_daily rows 35462 (dev cut 2563, end 2026-10-18) (measured)
  - 2026-10-18 01:38 UTC-5 wiki_pageviews_daily rows 53532 (dev cut 4143, end 2026-10-18) (measured)
  - 2026-10-18 01:44 UTC-5 wiki_pageviews_daily rows 71427 (dev cut 5572, end 2026-10-18) (measured)
  - 2026-10-18 01:49 UTC-5 wiki_pageviews_daily rows 89396 (dev cut 7101, end 2026-10-18) (measured)
  - 2026-10-18 01:55 UTC-5 wiki_pageviews_daily rows 106850 (dev cut 8460, end 2026-10-18) (measured)
  - 2026-10-18 02:00 UTC-5 wiki_pageviews_daily rows 125644 (dev cut 10089, end 2026-10-18) (measured)
  - 2026-10-18 02:05 UTC-5 wiki_pageviews_daily rows 144083 (dev cut 11658, end 2026-10-18) (measured)
  - 2026-10-18 02:11 UTC-5 wiki_pageviews_daily rows 162814 (dev cut 12978, end 2026-10-18) (measured)
  - 2026-10-18 02:16 UTC-5 wiki_pageviews_daily rows 181652 (dev cut 14038, end 2026-10-18) (measured)
  - 2026-10-18 02:19 UTC-5 wiki_pageviews_daily rows 189167 (dev cut 14772, end 2026-10-18) (measured)
- confidence rule: 0.9 exact, 0.6 alias, +0.05 per extra language, cap 1 (estimate, not calibrated)
