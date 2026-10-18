"""Pageviews for the AI lexicon's titles: records, checks and the table. No network."""

import polars as pl
import pytest

from crosssource import lexicon_pageviews as lp

pytestmark = pytest.mark.unit

LEXICON = {
    "entries": [
        {"id": "lab:openai", "wikipedia": {"es": "OpenAI", "pt": "OpenAI"}},
        {"id": "tech:agents", "wikipedia": {"es": "Agente inteligente"}},
        {"id": "biz:ai_funding"},  # no page: no request
    ]
}


def test_records_use_the_topic_id_and_skip_entries_without_a_page():
    assert lp.records(LEXICON) == [
        {"qid": "ai:lab:openai", "article_es": "OpenAI", "article_pt": "OpenAI"},
        {"qid": "ai:tech:agents", "article_es": "Agente inteligente", "article_pt": None},
    ]


def test_the_ws6_fetcher_turns_them_into_es_and_pt_requests_only():
    pytest.importorskip("tenacity")  # the crosssource extra
    from crosssource.pageviews import article_keys

    keys = article_keys(lp.records(LEXICON), projects=lp.PROJECTS)
    assert keys == [
        ("ai:lab:openai", "es.wikipedia", "OpenAI"),
        ("ai:lab:openai", "pt.wikipedia", "OpenAI"),
        ("ai:tech:agents", "es.wikipedia", "Agente inteligente"),
    ]


def test_write_keys_the_table_by_topic_and_refuses_bad_rows(tmp_path):
    rows = [
        {"qid": "ai:lab:openai", "project": "es.wikipedia", "article": "OpenAI"}
        | {"dt": "2026-10-12", "views": 120},
        {"qid": "ai:lab:openai", "project": "pt.wikipedia", "article": "OpenAI"}
        | {"dt": "2026-10-12", "views": 0},
    ]
    out = tmp_path / "t.parquet"
    assert lp.write(rows, out) == 2
    frame = pl.read_parquet(out)
    assert frame.columns == ["topic_id", "project", "article", "dt", "views"]
    assert frame.schema["dt"] == pl.Date and frame["views"].to_list() == [120, 0]
    bad = [rows[0] | {"qid": "Q95", "views": -1}]
    with pytest.raises(RuntimeError, match="not an ai: lexicon id"):
        lp.write(bad, out)
