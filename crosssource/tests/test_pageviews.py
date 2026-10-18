"""Parse one real Wikimedia pageviews response. No network."""

import json
from pathlib import Path

import pytest

pytest.importorskip("tenacity")  # the crosssource extra; CI installs no extras

from entity.wikidata import parse_entity_payload  # noqa: E402

from crosssource.pageviews import (  # noqa: E402
    article_keys,
    merge_pageview_rows,
    parse_pageviews,
    timestamp_to_date,
)
from radar.contracts import validate_records

DATA = Path(__file__).parent / "data"
ENTITY = Path(__file__).parents[2] / "entity" / "tests" / "data" / "wbgetentities.json"
pytestmark = pytest.mark.unit


def _payload():
    return json.loads((DATA / "pageviews.json").read_text(encoding="utf-8"))


def test_priority_article_keys_skip_english():
    keys = article_keys(
        [
            {
                "qid": "Q1",
                "article_es": "Tema",
                "article_pt": "Tópico",
                "article_en": "Topic",
            }
        ],
        projects={"es.wikipedia", "pt.wikipedia"},
    )
    assert [project for _qid, project, _title in keys] == ["es.wikipedia", "pt.wikipedia"]


def test_merge_keeps_existing_days_and_adds_a_new_article():
    existing = [
        {
            "qid": "Q1",
            "project": "es.wikipedia",
            "article": "Uno",
            "dt": "2025-10-01",
            "views": 3,
        }
    ]
    incoming = [
        {
            "qid": "Q1",
            "project": "es.wikipedia",
            "article": "Uno",
            "dt": "2025-10-01",
            "views": 9,
        },
        {
            "qid": "Q2",
            "project": "pt.wikipedia",
            "article": "Dois",
            "dt": "2025-10-02",
            "views": 4,
        },
    ]
    merged = merge_pageview_rows(existing, incoming)
    assert [(row["qid"], row["views"]) for row in merged] == [("Q1", 3), ("Q2", 4)]


def test_pageviews_fixture_is_daily_user_views():
    payload = _payload()
    items = payload["items"]
    assert items
    assert {item["agent"] for item in items} == {"user"}
    assert {item["granularity"] for item in items} == {"daily"}
    assert {item["project"] for item in items} == {"en.wikipedia"}


def test_pageviews_rows_match_the_contract_and_do_not_fill_gaps():
    payload = _payload()
    entity = parse_entity_payload(json.loads(ENTITY.read_text(encoding="utf-8")))
    assert entity is not None
    rows = parse_pageviews(payload, qid=entity.qid)
    assert len(rows) == len(payload["items"])
    assert [row["dt"] for row in rows] == [
        timestamp_to_date(item["timestamp"]) for item in payload["items"]
    ]
    assert [row["views"] for row in rows] == [item["views"] for item in payload["items"]]
    assert validate_records("wiki_pageviews_daily", rows) == []

    gapped = dict(payload)
    gapped["items"] = [payload["items"][0], payload["items"][2]]
    gap_rows = parse_pageviews(gapped, qid=entity.qid)
    assert [row["dt"] for row in gap_rows] == [
        timestamp_to_date(payload["items"][0]["timestamp"]),
        timestamp_to_date(payload["items"][2]["timestamp"]),
    ]
    assert validate_records("wiki_pageviews_daily", gap_rows) == []
