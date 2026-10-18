import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import evidence  # noqa: E402

REPORTS = Path(__file__).resolve().parents[2] / "reports"


@pytest.mark.unit
def test_report_tables_and_bullets_are_kept_verbatim():
    text = (
        "# Backtest\n\n## Precision@10\n\n- Base rate 6.7% (measured)\n\n"
        "| Ranker | Precision@10 |\n|---|---|\n"
        "| Radar | 13.3% (measured) |\n| Persistence | 12.8% |\n"
    )
    parsed = evidence.parse_report(text)
    assert parsed["title"] == "Backtest"
    section = next(s for s in parsed["sections"] if s["heading"] == "Precision@10")
    assert section["bullets"] == ["Base rate 6.7% (measured)"]
    assert section["tables"] == [
        [
            {"Ranker": "Radar", "Precision@10": "13.3% (measured)"},
            {"Ranker": "Persistence", "Precision@10": "12.8%"},
        ]
    ]


@pytest.mark.unit
def test_missing_report_is_marked_unavailable(tmp_path):
    assert evidence.report_json("backtest.md", tmp_path)["available"] is False


@pytest.mark.unit
def test_evidence_files_match_the_committed_reports(tmp_path):
    evidence.write_evidence(tmp_path)
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {
        "backtest.json",
        "label_quality.json",
        "ledgers.json",
        "trust_summary.json",
        "index.json",
    }
    ledgers = json.loads((tmp_path / "ledgers.json").read_text(encoding="utf-8"))
    with (REPORTS / "bq_ledger.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    billed = sum(int(r["billed_bytes"]) for r in rows if r["billed_bytes"].strip().isdigit())
    assert ledgers["bigquery"]["jobs"] == len(rows)
    assert ledgers["bigquery"]["billed_bytes"] == billed
    with (REPORTS / "jev_ledger.csv").open(newline="", encoding="utf-8") as fh:
        jev = list(csv.DictReader(fh))
    assert ledgers["jev"]["calls"] == len(jev)
    quality = json.loads((tmp_path / "label_quality.json").read_text(encoding="utf-8"))
    assert quality["available"] is True and any(s["tables"] for s in quality["sections"])


@pytest.mark.unit
def test_the_trust_summary_comes_from_the_reports_and_matches_the_chat_line(tmp_path):
    from agents import runtime, tools, trust

    evidence.write_evidence(tmp_path)
    summary = json.loads((tmp_path / "trust_summary.json").read_text(encoding="utf-8"))
    points = {p["id"]: p for p in summary["points"]}
    bt = tools.backtest_summary((REPORTS / "backtest.md").read_text(encoding="utf-8"))
    # the panel and the chat say the same precision and baselines, word for word
    assert trust.beats_sentence(bt) == points["baselines"]["texto"]
    turn = runtime.Turn("t")
    turn.tool_results.append({"tool": "get_backtest", "result": tools.get_backtest()})
    assert trust.precision_sentence(bt) in runtime.trust_line(turn)
    assert points["precision"]["texto"].startswith(
        trust.precision_sentence(bt, "El top 10 publicado del radar")
    )
    assert points["bigquery_usd"]["kind"] == "estimate"
    assert all(p["kind"] in {"measured", "estimate", "status", "rule"} for p in summary["points"])
    assert summary["points"][-1]["texto"] == trust.EARLY_SIGNAL
