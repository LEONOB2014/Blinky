# WS6 status

Owner: Grok CLI · Directories: `entity/, crosssource/`

Updated before each sync (20:00, 22:00, 00:00, 07:00, 09:00, 10:30, UTC-5).

## Last update

2026-10-18 03:15 UTC-5, branch `feat/ws6-wikipedia-pageviews`, PR not opened (needs approval)

## Done

- `entity/wikidata.py` resolves topics with wbsearchentities (es/en/pt) and a P31 check.
- Persons are never resolved.
- `crosssource/pageviews.py` fetches daily `agent=user` pageviews from 2025-10-01.
- Gold and the 8-week dev cut (2026-08-24 .. 2026-10-17) land in the lake.
- Unit tests parse one real cached response per endpoint.

## In progress

- WS4 missing es/pt pageviews are written. Exact matches were fetched first.
- Full `topic_daily` is included when the lake file exists. It was present.

## Blocked on

## Numbers (each marked measured or estimate)

Phase: Done.

- topics attempted: 11060 (measured)
- resolved exact: 1916 (measured)
- resolved alias: 997 (measured)
- resolved none: 8147 (measured)
- articles found, es / pt / en: 1306 / 1138 / 2289 (measured)
- pageview rows in gold: 368394 (measured)
- pageview rows in the 8-week dev cut: 16997 (measured)
- pageview end date returned by the API: 2026-10-18 (measured)
- failed requests (final non-200): 0 (measured)
- ws4 missing topics: 292 (measured)
- ws4 missing exact / alias / none: 292 / 0 / 0 (measured)
- ws4 missing articles found, es / pt / en: 270 / 242 / 291 (measured)
- ws4 missing pageview articles attempted / HTTP 200: 512 / 512 (measured)
- ws4 missing pageviews: exact matches first, then aliases; es and pt only
- ws4 missing window: 2025-10-01 .. 2026-10-18
- HTTP 429: 0 (measured)
- write times:
  - 2026-10-18 02:19 UTC-5 topic_wikidata rows 11060 (measured)
  - 2026-10-18 02:24 UTC-5 wiki_pageviews_daily rows 206831 (dev cut 15302, end 2026-10-18) (measured)
  - 2026-10-18 02:30 UTC-5 wiki_pageviews_daily rows 224192 (dev cut 15563, end 2026-10-18) (measured)
  - 2026-10-18 02:35 UTC-5 wiki_pageviews_daily rows 241265 (dev cut 15652, end 2026-10-18) (measured)
  - 2026-10-18 02:41 UTC-5 wiki_pageviews_daily rows 258878 (dev cut 15863, end 2026-10-18) (measured)
  - 2026-10-18 02:46 UTC-5 wiki_pageviews_daily rows 276129 (dev cut 15969, end 2026-10-18) (measured)
  - 2026-10-18 02:51 UTC-5 wiki_pageviews_daily rows 292715 (dev cut 16214, end 2026-10-18) (measured)
  - 2026-10-18 02:57 UTC-5 wiki_pageviews_daily rows 310405 (dev cut 16426, end 2026-10-18) (measured)
  - 2026-10-18 03:02 UTC-5 wiki_pageviews_daily rows 328525 (dev cut 16635, end 2026-10-18) (measured)
  - 2026-10-18 03:08 UTC-5 wiki_pageviews_daily rows 345831 (dev cut 16945, end 2026-10-18) (measured)
  - 2026-10-18 03:13 UTC-5 wiki_pageviews_daily rows 363924 (dev cut 16945, end 2026-10-18) (measured)
  - 2026-10-18 03:14 UTC-5 wiki_pageviews_daily rows 368394 (dev cut 16997, end 2026-10-18) (measured)
- confidence rule: 0.9 exact, 0.6 alias, +0.05 per extra language, cap 1 (estimate, not calibrated)
