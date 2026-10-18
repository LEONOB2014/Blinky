"""The committed dev slice: where it lives and which columns it may hold.

The repo goes public at submission, so committed data carries no URLs, titles, person names,
locations, quotations or other free text. A test fails if any fixture or mock holds a column
outside this allow-list.
"""

from radar.paths import REPO_ROOT

DEV_DIR = REPO_ROOT / "fixtures" / "dev"

_TONE = {
    "n_tone", "sum_tone", "sum_tone_sq", "sum_polarity", "n_pos_x", "n_neg_x", "mean_tone",
    "sd_tone", "p10_tone", "p90_tone", "mean_polarity", "extremity", "positive_share",
    "negative_share", "controversy_index",
}  # fmt: skip

ALLOWED_COLUMNS: dict[str, set[str]] = {
    "daily_totals": {"dt", "lang_bucket", "n_all", "n_all_med28", "is_missing"},
    "daily_topic": {
        "dt", "topic", "segment", "domain", "lang_bucket", "latam", "n_articles", "n_sources",
        "n_all_stream", "share_of_day", "is_missing", *_TONE,
    },
    "daily_topic_rolling": {
        "topic", "segment", "lang_bucket", "latam", "dt", "dow", "is_missing", "n", "n_all",
        "share", "n_sources", "n_7d", "share_7d", "z_dow", "z_7d", "growth_7d_log", "accel_7d",
        "mean_tone_7d", "extremity_7d", "mean_polarity_7d", "positive_share_7d",
        "negative_share_7d", "controversy_7d", "tone_shift_7d",
    },
    "edges_weekly": {"wk", "x", "y", "n", "n_src", "nx", "ny", "n_docs", "npmi"},
    "topic_daily": {
        "topic_id", "dt", "lang_bucket", "segment", "n_articles", "share_of_day", "mean_tone",
        "mean_polarity", "is_missing",
    },
    "topic_subtopic_weekly": {"topic_id", "week", "subtopic", "n_articles", "n_topic_articles"},
    "topic_sources_weekly": {
        "topic_id", "week", "n_articles", "n_sources", "top_source_share", "top3_source_share",
        "top_theme_pattern_share",
    },
    "topic_wikidata": {
        "topic_id", "qid", "label_es", "article_es", "article_pt", "article_en", "match",
        "confidence",
    },
    "wiki_pageviews_daily": {"qid", "project", "article", "dt", "views"},
    "node_metrics_weekly": {
        "wk", "entity_id", "deg_w", "deg_growth", "new_nbr_rate", "pagerank", "pr_rank_delta",
        "kcore", "community_id", "community_event", "is_hub",
    },
    "gkg_ai_sample": {
        "gkg_id", "ts", "dt", "source", "lang", "tone", "pos_score", "neg_score", "polarity",
        "activity_density", "self_group_ref_density", "word_count", "orgs", "themes", "f_url",
        "f_url_short", "f_title_strong", "f_title_weak", "f_org", "f_latam_loc", "f_latam_src",
        "f_ict", "f_control", "stratum",
    },
}  # fmt: skip

FORBIDDEN_COLUMNS = {
    "url", "title", "persons", "allnames", "locations", "quotations", "extras",
    "documentidentifier", "headline",
}  # fmt: skip
