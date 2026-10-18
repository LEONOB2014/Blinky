import pytest
import yaml
from gen_ai_sql import LEXICON, lexicon_array, load_entries, s15, s16

STUB = {
    "version": 1,
    "entries": [
        {"id": "lab:openai", "patterns": [r"\bopenai\b", r"\bchatgpt\b"], "gdelt_orgs": ["openai"]},
        {"id": "tech:agents", "patterns": [r"\bagentic\b"]},
        {"id": "infra:nvidia", "gdelt_orgs": ["nvidia"]},
    ],
}


def _write(tmp_path, doc):
    path = tmp_path / "lexicon.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


@pytest.mark.unit
def test_entries_become_one_typed_struct_each(tmp_path):
    arr = lexicon_array(load_entries(_write(tmp_path, STUB)))
    assert arr.startswith("ARRAY<STRUCT<id STRING, re STRING, orgs ARRAY<STRING>>>[")
    openai = r'("lab:openai", r"""(?:\bopenai\b)|(?:\bchatgpt\b)""", ARRAY<STRING>["openai"])'
    assert openai in arr
    # no aliases: an empty array still typed STRING (a bare [] is ARRAY<INT64> in BigQuery)
    assert '("tech:agents", r"""(?:\\bagentic\\b)""", ARRAY<STRING>[])' in arr
    # aliases only: no regex
    assert '("infra:nvidia", NULL, ARRAY<STRING>["nvidia"])' in arr


@pytest.mark.unit
def test_scripts_write_the_contract_tables(tmp_path):
    path = _write(tmp_path, STUB)
    entries = load_entries(path)
    one = s15(entries, path)
    assert "CREATE OR REPLACE TABLE `radar.article_topic_ai`" in one
    assert "CREATE OR REPLACE TABLE `radar.topic_ai_daily`" in one
    assert "CONCAT('ai:', l.id)" in one
    assert ">= 20" not in one  # no article floor: the lexicon is curated
    two = s16(entries, path)
    assert "CREATE OR REPLACE TABLE `radar.edges_ai_weekly`" in two
    assert "'all'" in two and "AS npmi" in two


@pytest.mark.unit
@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        ({"id": "person:someone", "patterns": ["x"]}, "bad id"),
        ({"id": "lab:x", "patterns": []}, "no patterns and no gdelt_orgs"),
        ({"id": "lab:x", "patterns": ["(unclosed"]}, "does not compile"),
        ({"id": "lab:x", "gdelt_orgs": ["OpenAI"]}, "lowercase"),
        ({"id": "lab:x", "patterns": ['a"""b']}, "triple quote"),
    ],
)
def test_bad_entries_are_refused(tmp_path, entry, problem):
    with pytest.raises(ValueError, match=problem):
        load_entries(_write(tmp_path, {"version": 1, "entries": [entry]}))


@pytest.mark.unit
def test_duplicate_ids_are_refused(tmp_path):
    twice = [{"id": "lab:x", "patterns": ["x"]}, {"id": "lab:x", "patterns": ["y"]}]
    doc = {"version": 1, "entries": twice}
    with pytest.raises(ValueError, match="duplicate"):
        load_entries(_write(tmp_path, doc))


@pytest.mark.unit
@pytest.mark.skipif(not LEXICON.exists(), reason="contracts/ai_lexicon.yaml not landed yet")
def test_the_real_lexicon_generates():
    entries = load_entries(LEXICON)
    assert len(entries) == len({e["id"] for e in entries})
    assert s15(entries, LEXICON) and s16(entries, LEXICON)
