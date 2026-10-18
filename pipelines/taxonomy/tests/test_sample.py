"""Unit and data tests for pipelines/taxonomy/sample.sql and pipelines/taxonomy/sample.py."""

import pytest
import yaml
from pipelines.taxonomy import sample

from radar.paths import REPO_ROOT, lake

TAXONOMY = yaml.safe_load((REPO_ROOT / "contracts" / "taxonomy.yaml").read_text(encoding="utf-8"))
SAMPLE_SQL = (REPO_ROOT / "pipelines" / "taxonomy" / "sample.sql").read_text(encoding="utf-8")


@pytest.mark.unit
def test_sample_sql_is_single_statement_and_respects_ring_one():
    rule = TAXONOMY["rings"]["ai"]["rule"]
    assert f"({rule}) AS ai" in SAMPLE_SQL
    assert "WHERE dt >= '2026-08-01' AND dt <= '2026-10-31'" in SAMPLE_SQL
    assert sample.run_bq.count_statements(SAMPLE_SQL) == 1


@pytest.mark.unit
def test_cast_rows_and_summarize_sample():
    raw_rows = [
        {
            "gkg_id": "row-1",
            "dt": "2026-09-15",
            "source": "example.com",
            "url": "https://example.com/ai-news",
            "title": "OpenAI launches new agent platform",
            "lang": "spa",
            "lang_bucket": "spa",
            "is_es_pt": "true",
            "stratum": "ring1",
            "segment": "ai",
            "raw_segment": "ai",
            "domains": "",
            "regex_subtopics": "agents;llms_models",
            "top_themes": "WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES",
            "top_orgs": "openai",
            "tone": "1.5",
            "polarity": "3.2",
            "word_count": "450.0",
            "f_url": "true",
            "f_url_short": "false",
            "f_title_strong": "true",
            "f_title_weak": "false",
            "f_org": "true",
            "f_latam_loc": "false",
            "f_latam_src": "false",
            "f_ict": "true",
            "f_control": "false",
            "tech_org": "true",
            "n_ict_themes": "1",
            "tech_themed": "true",
            "rn_stratum": "1",
            "pool_split": "sample",
            "pop_n_ring1": "398221",
            "pop_n_ring2": "326843",
            "pop_n_ring3": "184784",
            "pop_n_control_rej": "40392",
            "pop_n_acc_tech_ctrl": "510",
            "pop_n_rej_tech_ctrl": "7375",
            "pop_n_acc_all_ctrl": "792",
            "pop_n_rej_all_ctrl": "40392",
        },
        {
            "gkg_id": "row-2",
            "dt": "2026-09-16",
            "source": "example.org",
            "url": "https://example.org/sports",
            "title": "Local football league update",
            "lang": "eng",
            "lang_bucket": "eng",
            "is_es_pt": "false",
            "stratum": "rejected",
            "segment": "control",
            "raw_segment": "control",
            "domains": "",
            "regex_subtopics": "",
            "top_themes": "SPORTS",
            "top_orgs": "",
            "tone": "0.5",
            "polarity": "1.2",
            "word_count": "300",
            "f_url": "false",
            "f_url_short": "false",
            "f_title_strong": "false",
            "f_title_weak": "false",
            "f_org": "false",
            "f_latam_loc": "false",
            "f_latam_src": "false",
            "f_ict": "false",
            "f_control": "true",
            "tech_org": "false",
            "n_ict_themes": "0",
            "tech_themed": "false",
            "rn_stratum": "1",
            "pool_split": "sample",
            "pop_n_ring1": "398221",
            "pop_n_ring2": "326843",
            "pop_n_ring3": "184784",
            "pop_n_control_rej": "40392",
            "pop_n_acc_tech_ctrl": "510",
            "pop_n_rej_tech_ctrl": "7375",
            "pop_n_acc_all_ctrl": "792",
            "pop_n_rej_all_ctrl": "40392",
        },
    ]
    df = sample.cast_rows(raw_rows)
    assert df.height == 2
    assert df["word_count"].to_list() == [450, 300]
    summary = sample.summarize_sample(df)
    assert summary["sample_rows"] == 2
    assert summary["es_pt_share"] == 0.5
    assert summary["population_aug_oct_2026"]["pop_n_acc_tech_ctrl"] == 510


@pytest.mark.data
def test_lake_sample_parquet_stratification():
    path = lake() / "labels" / "sample.parquet"
    if not path.exists():
        pytest.skip("lake/labels/sample.parquet not present")
    import polars as pl

    df = pl.read_parquet(path)
    assert df.height == 4000
    counts = dict(df.group_by("stratum").len().iter_rows())
    assert counts == {"ring1": 1500, "ring2": 1000, "ring3": 500, "rejected": 1000}
    es_pt_share = float(df["is_es_pt"].mean())
    assert es_pt_share >= 0.30
