"""Parsers and the P31 check against real wbsearchentities and wbgetentities responses."""

import json
from pathlib import Path

import pytest

from entity.claims import claim_ids
from entity.client import RateLimiter
from entity.wikidata import (
    ALLOWED_ROOTS,
    classify,
    load_dev_topics,
    match_kind,
    none_record,
    order_hits,
    parse_entity_payload,
    parse_search,
    to_record,
    topic_from_id,
)
from radar.contracts import validate_records

DATA = Path(__file__).parent / "data"
pytestmark = pytest.mark.unit


def _search():
    return json.loads((DATA / "wbsearchentities.json").read_text(encoding="utf-8"))


def _entity():
    return json.loads((DATA / "wbgetentities.json").read_text(encoding="utf-8"))


def test_search_fixture_is_a_real_wbsearchentities_payload():
    payload = _search()
    assert payload["success"] == 1
    assert payload["searchinfo"]["search"] == "nvidia"
    hits = parse_search(payload)
    assert hits
    assert all(hit.qid.startswith("Q") and hit.qid[1:].isdigit() for hit in hits)
    exact = [hit for hit in hits if match_kind(hit) == "exact"]
    aliases = [hit for hit in hits if match_kind(hit) == "alias"]
    assert exact and aliases
    assert norm_label(exact[0]) == "nvidia"


def norm_label(hit) -> str:
    return hit.label.casefold()


def test_exact_hit_is_ordered_before_a_partial_label():
    ordered = order_hits(parse_search(_search()))
    assert match_kind(ordered[0]) == "exact"
    assert ordered[0].label.casefold() == "nvidia"


def test_entity_fixture_has_p31_and_three_wikipedia_sitelinks():
    payload = _entity()
    entity = parse_entity_payload(payload)
    assert entity is not None
    assert entity.qid == next(iter(payload["entities"]))
    assert entity.p31
    assert set(entity.p31) & ALLOWED_ROOTS
    assert "Q5" not in entity.p31
    assert entity.article_es and entity.article_pt and entity.article_en
    assert entity.label_es
    raw = next(iter(payload["entities"].values()))
    assert claim_ids(raw, "P31") == entity.p31


def test_nvidia_record_matches_the_contract():
    hits = parse_search(_search())
    entity = parse_entity_payload(_entity())
    assert entity is not None
    assert classify(entity.p31, entity.p279, lambda _qid: ()) == "ok"
    exact = next(hit for hit in hits if match_kind(hit) == "exact")
    record = to_record("org:nvidia", entity, "exact", 0.9)
    assert record["qid"] == exact.qid
    assert record["article_en"] == entity.article_en
    assert validate_records("topic_wikidata", [record]) == []


def test_subclass_of_artificial_intelligence_is_allowed():
    assert "Q11660" in ALLOWED_ROOTS
    assert classify((), ("Q11660",), lambda _qid: ("Q5",)) == "ok"


def test_priority_topic_skips_persons_and_keeps_organizations():
    org = topic_from_id("org:nvidia", {})
    assert org is not None
    assert org.topic_id == "org:nvidia"
    assert org.queries == (("en", "nvidia"),)
    assert topic_from_id("per:someone", {}) is None


def test_human_and_country_are_not_resolved():
    assert classify(("Q5",), (), lambda _qid: ()) == "person"
    assert classify(("Q6256", "Q3624078"), (), lambda _qid: ()) == "reject"


def test_classify_does_not_walk_through_metaclasses():
    calls: list[str] = []

    def parents(qid: str) -> tuple[str, ...]:
        calls.append(qid)
        if qid == "Q1":
            return ("Q21146257", "Q7397")
        return ("Q999999",)

    assert classify(("Q1",), (), parents) == "ok"
    assert "Q21146257" not in calls


def test_classify_stops_when_the_superclass_walk_fans_out():
    def parents(qid: str) -> tuple[str, ...]:
        number = int(qid[1:])
        return (f"Q{number * 2 + 1}", f"Q{number * 2 + 2}")

    assert classify(("Q1",), (), parents) == "reject"


def test_none_record_matches_the_contract():
    record = none_record("org:not-a-real-organization")
    assert record["match"] == "none"
    assert record["qid"] is None
    assert record["confidence"] == 0.0
    assert validate_records("topic_wikidata", [record]) == []


def test_dev_topics_are_subtopics_and_organizations_only():
    topics = load_dev_topics()
    ids = {topic.topic_id for topic in topics}
    subtopics = [topic for topic in topics if topic.kind == "subtopic"]
    assert len(subtopics) == 12
    assert "agents" in ids
    assert "org:nvidia" in ids
    assert "org:microsoft" in ids
    assert all(not topic_id.startswith("per:") for topic_id in ids)
    assert all(not topic_id.startswith("loc:") for topic_id in ids)
    agents = next(topic for topic in subtopics if topic.topic_id == "agents")
    languages = {lang for lang, _text in agents.queries}
    assert languages == {"es", "en", "pt"}


def test_limiter_spaces_calls_and_stays_under_twenty_per_second():
    clock = {"t": 0.0}

    def now() -> float:
        return clock["t"]

    def sleep(seconds: float) -> None:
        clock["t"] += seconds

    limiter = RateLimiter(start_interval=6.5, floor=0.4, now=now, sleep=sleep)
    limiter.wait()
    limiter.wait()
    assert clock["t"] == pytest.approx(6.5)
    for _ in range(12):
        limiter.reward()
    assert limiter.interval == 1.0
    for _ in range(40):
        limiter.reward()
    assert limiter.interval == 0.4
    assert limiter.interval > 1 / 20


def test_limiter_doubles_the_gap_after_a_429():
    limiter = RateLimiter(start_interval=0.4, floor=0.4, now=lambda: 0.0, sleep=lambda _s: None)
    limiter.penalize(60)
    assert limiter.interval == pytest.approx(0.8)
    for _ in range(20):
        limiter.reward()
    assert limiter.interval == pytest.approx(0.8)


def test_pageview_pace_does_not_drop_below_its_floor():
    limiter = RateLimiter(start_interval=6.5, floor=6.5, now=lambda: 0.0, sleep=lambda _s: None)
    for _ in range(60):
        limiter.reward()
    assert limiter.interval == pytest.approx(6.5)


def test_limiter_rejects_a_twenty_per_second_floor():
    with pytest.raises(ValueError):
        RateLimiter(floor=0.01)
