"""Parser mechanics only: the inputs below are typing formats, not observed 30X data."""

import csv
import json

import pytest
from pipelines.social import importer as imp

from radar.paths import REPO_ROOT

HEADER = imp.TEMPLATE.read_text(encoding="utf-8").strip().split(",")


def test_template_matches_the_contract():
    schema = json.loads((REPO_ROOT / "contracts" / "social_post_metrics.schema.json").read_text())
    derived = {"engagement", "engagement_per_1k_followers", "age_days_at_observation"}
    assert [k for k in schema["properties"] if k not in derived] == HEADER


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("1.2K", 1200),
        ("1,2 mil", 1200),
        ("3.456", 3456),
        ("1,234", 1234),
        ("1 234", 1234),
        ("17", 17),
        ("2M", 2_000_000),
        ("", None),
    ],
)
def test_counts_as_platforms_show_them(raw, value):
    assert imp.parse_count(raw) == value


def test_ambiguous_counts_are_refused():
    with pytest.raises(ValueError):
        imp.parse_count("1.5")


def test_dates_and_yes_no():
    assert imp.parse_date("12/10/2026").isoformat() == "2026-10-12"
    assert imp.parse_moment("2026-10-18 09:30").isoformat() == "2026-10-18T09:30:00-05:00"
    assert imp.parse_bool("sí") is True and imp.parse_bool("") is None


def _sheet(tmp_path, rows):
    path = tmp_path / "sheet.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(dict.fromkeys(HEADER, "") | r)
    return path


ROW = {
    "post_key": "li-001",
    "platform": "LinkedIn",
    "account": "page",
    "post_url": "https://example.org/p",
    "posted_date": "12/10/2026",
    "observed_at": "2026-10-18 09:30",
    "format": "carousel",
    "language": "es",
    "post_text": "texto",
    "reactions": "1,2 mil",
    "comments": "3",
    "shares": "",
    "followers_at_observation": "10K",
}


def test_a_valid_row_gets_its_derived_fields(tmp_path):
    records, problems = imp.read_sheet(_sheet(tmp_path, [ROW]))
    assert problems == []
    rec = records[0]
    assert rec["platform"] == "linkedin" and rec["engagement"] == 1203
    assert rec["age_days_at_observation"] == 6 and rec["engagement_per_1k_followers"] == 120.3


def test_problems_name_the_row(tmp_path):
    bad = ROW | {"post_key": "li-002", "platform": "tiktok"}
    late = ROW | {"post_key": "li-003", "observed_at": "2026-10-01 10:00"}
    _, problems = imp.read_sheet(_sheet(tmp_path, [ROW, bad, late, ROW]))
    text = "\n".join(problems)
    assert "row 3" in text and "tiktok" in text
    assert "row 4: observed_at is before posted_date" in text
    assert "duplicate post_key li-001" in text


def test_written_file_keeps_types_when_a_column_is_empty(tmp_path, monkeypatch):
    import duckdb

    monkeypatch.setenv("RADAR_LAKE", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["importer", "--csv", str(_sheet(tmp_path, [ROW]))])
    imp.main()
    out = tmp_path / "gold" / "social_post_metrics.parquet"
    rows = duckdb.sql(f"SELECT post_key FROM '{out}' WHERE views IS NULL").fetchall()
    assert rows == [("li-001",)]


def test_committed_templates_hold_no_data():
    for path in (REPO_ROOT / "templates").glob("*.csv"):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1, f"{path.name} must hold only its header (data stays in the lake)"
