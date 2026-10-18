import datetime as dt

import export_gold
import polars as pl
import pytest

from radar.contracts import validate_records


@pytest.mark.unit
def test_schema_comes_from_the_contract():
    schema = export_gold.polars_schema("topic_daily")
    assert schema["dt"] == pl.Date
    assert schema["n_articles"] == pl.Int64
    assert schema["share_of_day"] == pl.Float64
    assert schema["is_missing"] == pl.Boolean
    assert schema["segment"] == pl.String  # a const
    assert export_gold.polars_schema("daily_topic")["domain"] == pl.String


@pytest.mark.unit
def test_bq_json_strings_are_typed_and_validate():
    # Shape of `bq --format=json head` output: every value a string, NULL columns absent.
    rows = [
        {
            "topic_id": "org:openai",
            "dt": "2026-09-01",
            "lang_bucket": "eng",
            "segment": "ai",
            "n_articles": "41",
            "share_of_day": "0.00031",
            "mean_tone": "-0.5",
            "is_missing": "false",
        },
        {
            "topic_id": "thm:TECH_AUTOMATION",
            "dt": "2025-11-02",
            "lang_bucket": "spa",
            "segment": "ai",
            "n_articles": "3.0",
            "is_missing": "true",
        },
    ]
    frame = export_gold.typed(rows, export_gold.polars_schema("topic_daily"))
    assert frame["dt"].to_list() == [dt.date(2026, 9, 1), dt.date(2025, 11, 2)]
    assert frame["n_articles"].to_list() == [41, 3]
    assert frame["is_missing"].to_list() == [False, True]
    assert frame["share_of_day"].to_list() == [0.00031, None]
    recs = export_gold.records_for_validation(frame)
    assert recs[0]["dt"] == "2026-09-01"
    # share_of_day is required: a NULL is kept as None (allowed by the contract), not dropped.
    assert validate_records("topic_daily", recs) == []


@pytest.mark.unit
def test_validation_catches_a_bad_record():
    rows = [{"topic_id": "org:x", "dt": "2026-09-01", "lang_bucket": "deu", "segment": "it"}]
    frame = export_gold.typed(rows, export_gold.polars_schema("topic_daily"))
    errors = validate_records("topic_daily", export_gold.records_for_validation(frame))
    assert any("lang_bucket" in e for e in errors)
    assert any("segment" in e for e in errors)


@pytest.mark.unit
def test_sample_is_capped():
    frame = pl.DataFrame({"a": range(5000)})
    assert export_gold.sample_for_validation(frame).height == 1000
    assert export_gold.sample_for_validation(frame.head(10)).height == 10
