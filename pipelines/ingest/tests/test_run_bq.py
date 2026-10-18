import csv
import datetime as dt

import pytest
import run_bq

GIB = 2**30
CAP = 50 * GIB


@pytest.mark.unit
def test_parse_real_dry_run_line():
    out = (
        "Query successfully validated. Assuming the tables are not modified, running this query "
        "will process upper bound of 12499550274 bytes of data."
    )
    assert run_bq.parse_dry_run(out) == (12499550274, False)
    low = "running this query will process lower bound of 0 bytes of data."
    assert run_bq.parse_dry_run(low) == (0, True)


@pytest.mark.unit
def test_parse_dry_run_without_estimate_fails():
    with pytest.raises(ValueError, match="no byte estimate"):
        run_bq.parse_dry_run("Error in query string")


@pytest.mark.unit
def test_count_statements_ignores_comments_and_strings():
    sql = "-- a; b\nSELECT ';' AS x;\n-- trailing; comment\nSELECT 2;\n"
    assert run_bq.count_statements(sql) == 2
    assert run_bq.count_statements("SELECT 1 -- only one;\n") == 1
    assert run_bq.count_statements("-- don't\nSELECT 1;\n-- it's\nSELECT 2;") == 2


@pytest.mark.unit
def test_month_params_pad_partitions_by_a_day():
    p = run_bq.month_params("2026-07")
    assert p == {
        "PART_START": "2026-06-30",
        "PART_END": "2026-08-02",
        "DATE_START": "20260701000000",
        "DATE_END": "20260801000000",
        "MONTH_START": "2026-07-01",
        "MONTH_END": "2026-08-01",
    }
    assert run_bq.month_params("2025-12")["DATE_END"] == "20260101000000"


@pytest.mark.unit
def test_render_requires_tokens_to_match():
    sql = "WHERE a >= '${PART_START}' AND b < ${DATE_END}"
    out = run_bq.render(sql, run_bq.month_params("2026-02"))
    assert out == "WHERE a >= '2026-01-31' AND b < 20260301000000"
    with pytest.raises(ValueError, match="pass --month"):
        run_bq.render(sql, {})
    with pytest.raises(ValueError, match="no \\$"):
        run_bq.render("SELECT 1", run_bq.month_params("2026-02"))


@pytest.mark.unit
def test_single_statement_guard():
    ok = run_bq.plan(22 * GIB, False, None, CAP)
    assert ok.expected_bytes == 22 * GIB and ok.max_bytes_billed == CAP
    with pytest.raises(run_bq.GuardError, match="cap"):
        run_bq.plan(51 * GIB, False, None, CAP)
    with pytest.raises(run_bq.GuardError, match="1.5x"):
        run_bq.plan(34 * GIB, False, 22 * GIB, CAP)
    assert run_bq.plan(33 * GIB, False, 22 * GIB, CAP).expected_bytes == 33 * GIB


@pytest.mark.unit
def test_multi_statement_uses_the_last_bill_not_the_dry_run():
    # S4: 10.6 GB dry run, 14.2 GB billed (measured) -> expect 14.2, hard limit 1.5x.
    p = run_bq.plan(10_587_059_621, True, 14_247_002_112, CAP)
    assert p.expected_bytes == 14_247_002_112
    assert p.max_bytes_billed == int(1.5 * 14_247_002_112)
    with pytest.raises(run_bq.GuardError, match="cap"):
        run_bq.plan(10 * GIB, True, 40 * GIB, CAP)
    with pytest.raises(run_bq.GuardError, match="1.5x"):
        run_bq.plan(30 * GIB, True, 14 * GIB, CAP)


@pytest.mark.unit
def test_baseline_scale_allows_planned_growth():
    with pytest.raises(run_bq.GuardError):
        run_bq.plan(25 * GIB, True, 10 * GIB, CAP)
    assert run_bq.plan(25 * GIB, True, 10 * GIB, CAP, baseline_scale=2.5).expected_bytes == (
        25 * GIB
    )


@pytest.mark.unit
def test_previous_billed_matches_the_script_across_months():
    rows = [
        {"script": "s2_monthly_insert.sql (2026-09)", "billed_bytes": "22407020544"},
        {"script": "s2_monthly_insert.sql (2026-08)", "billed_bytes": "22677553152"},
        {"script": "s2_monthly_insert.sql (2026-07)", "billed_bytes": ""},
        {"script": "s4_aggregates.sql", "billed_bytes": "0"},
        {"script": "scripts/export_dev_slice.py ()", "billed_bytes": ""},
        {"script": "s2_monthly_insert.sql (2026-06)", "billed_bytes": "5", "note": "FAILED; x"},
    ]
    assert run_bq.previous_billed(rows, "s2_monthly_insert.sql") == 22677553152
    assert run_bq.previous_billed(rows, "s4_aggregates.sql") is None
    assert run_bq.previous_billed(rows, "s11_topic_daily.sql") is None


@pytest.mark.unit
def test_ledger_row_keeps_the_existing_columns(tmp_path):
    path = tmp_path / "ledger.csv"
    path.write_text(",".join(run_bq.LEDGER_COLUMNS) + "\n", encoding="utf-8")
    now = dt.datetime(2026, 10, 18, 3, 0, 5, tzinfo=dt.UTC)
    row = run_bq.ledger_row(
        "radar_s2_x", "s2_monthly_insert.sql (2026-07)", "WS1", 123, 456, 50, "n (measured)", now
    )
    run_bq.append_ledger(row, path)
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows == [
        {
            "ts_utc": "2026-10-18T03:00:05Z",
            "job_id": "radar_s2_x",
            "script": "s2_monthly_insert.sql (2026-07)",
            "workstream": "WS1",
            "dry_run_bytes": "123",
            "billed_bytes": "456",
            "cap_gib": "50",
            "note": "n (measured)",
        }
    ]


@pytest.mark.unit
def test_real_ledger_header_matches():
    with run_bq.LEDGER.open(newline="", encoding="utf-8") as fh:
        assert next(csv.reader(fh)) == run_bq.LEDGER_COLUMNS


@pytest.mark.unit
def test_lower_bound_needs_history_or_an_expectation():
    with pytest.raises(run_bq.GuardError, match="lower bound"):
        run_bq.plan(0, True, None, CAP, lower_bound=True)
    p = run_bq.plan(0, True, None, CAP, lower_bound=True, expect_bytes=5 * GIB)
    assert p.expected_bytes == 5 * GIB and p.max_bytes_billed == int(7.5 * GIB)
    # History wins over the operator's expectation.
    assert run_bq.plan(
        0, True, 4 * GIB, CAP, lower_bound=True, expect_bytes=9 * GIB
    ).expected_bytes == (4 * GIB)
