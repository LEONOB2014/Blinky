# 30X social posts, observed by hand

A person (not a script, not an agent) opens 30X's public posts and writes down what the platform
shows. No automation touches LinkedIn, X or Instagram: their terms forbid automated access, and this
project never scrapes. The sheet is 30X's private business data: it lives only in the git-ignored
lake, never in git, and only aggregates leave it, with 30X's consent.

## Fill it

```bash
uv run python -m pipelines.social.importer --init     # empty sheet at lake/manual/social_posts.csv
# open it in Excel, Numbers or Google Sheets (export back to CSV, UTF-8), one row per post
uv run python -m pipelines.social.importer            # check it and write lake/gold/social_post_metrics.parquet
```

The importer lists every problem with its row and column and writes nothing until the sheet is
clean. Run it as often as you like.

## The columns

| Column | Required | What to write |
|---|---|---|
| `post_key` | yes | Your own id: `li-001`, `x-001`, `ig-001` (platform prefix, 3+ digits) |
| `platform` | yes | `linkedin`, `x` or `instagram` |
| `account` | yes | Which 30X account, e.g. `30x company page` |
| `post_url` | yes | The post's link (starts with `https://`) |
| `posted_date` | yes | `2026-10-12` or `12/10/2026` |
| `observed_at` | yes | When you read the counts: `2026-10-18 09:30` (UTC-5). Counts keep growing, so this matters |
| `format` | yes | `text`, `image`, `carousel`, `video`, `reel`, `article`, `poll`, `thread`, `link`, `document` |
| `language` | yes | `es`, `pt`, `en`, `other` |
| `post_text` | yes | The text, or at least its first lines (the Curator labels the topic from it) |
| `topic_hint` | no | What it is about, in your words |
| `is_ai_topic` | no | Your own `sí`/`no`: is it about AI? (a human label we can check the classifier against) |
| `views` | no | Views or impressions **only when the platform shows them publicly**; leave empty otherwise |
| `reactions` | yes | Likes or reactions (write `0` if none) |
| `comments` | yes | Comments (write `0` if none) |
| `shares` | no | Reposts or shares, when shown |
| `saves` | no | Bookmarks or saves, when shown |
| `followers_at_observation` | no | The account's followers when you looked |
| `notes` | no | Anything odd: boosted post, pinned, edited, a giveaway |

Counts can be typed as the platform shows them: `1.2K`, `1,2 mil`, `3.456`, `1 234`. Yes/no as
`sí`, `no`, `yes`, `true`, `1`, `0`.

What each platform shows publicly changes over time and by account type. Write what you see and
leave the rest empty: an empty cell is honest, a guessed one is not. If 30X later gives you their
own analytics exports (impressions, clicks), we add those as a second source rather than mixing
them into this sheet.

## What the radar does with it

The importer adds `engagement` (reactions + comments + shares + saves), `engagement_per_1k_followers`
and `age_days_at_observation`. Next steps (not built yet): the Curator labels each post's topic and
subtopic, and each post is joined with what the radar said about its topic that week (decision,
stage, window), to measure whether posts on `publicar_ahora` topics did better.
