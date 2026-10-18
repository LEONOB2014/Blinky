"""The demo's trust step as plain JSON, for the static fallback (web/public/data/evidence/).

The reports are read as they are in git; nothing is recomputed or summarised by hand:
- `backtest.json`, `label_quality.json`: every heading of `reports/backtest.md` and
  `reports/label_quality.md` with its markdown tables (as rows of strings, verbatim) and bullets.
  A report that does not exist yet is written as `{"available": false}`.
- `ledgers.json`: totals of `reports/bq_ledger.csv` (jobs, bytes billed, by workstream) and
  `reports/jev_ledger.csv` (calls, input tokens, cost, median latency), computed from the rows.
- `trust_summary.json`: the executive summary at the top of the trust panel, short Spanish points
  marked measured or estimate, from agents/trust.py (the same parsers as the chat's trust line).
- `index.json`: which files exist and when they were generated.

    uv run python deploy/evidence.py [OUT_DIR]     # default web/public/data/evidence/
"""

import csv
import datetime as dt
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from agents.trust import backtest_report, trust_summary

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports"
OUT = REPO / "web" / "public" / "data" / "evidence"
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_report(text: str) -> dict[str, Any]:
    """Headings with their tables (rows as dicts of verbatim cell strings) and bullet lines."""
    title, sections = None, []
    current: dict[str, Any] = {"heading": None, "level": 0, "tables": [], "bullets": []}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = HEADING.match(line)
        if m:
            if current["heading"] is not None or current["tables"] or current["bullets"]:
                sections.append(current)
            if title is None and len(m.group(1)) == 1:
                title = m.group(2)
            current = {"heading": m.group(2), "level": len(m.group(1)), "tables": [], "bullets": []}
        elif (
            line.lstrip().startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])
        ):
            header = _cells(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = _cells(lines[i])
                rows.append(dict(zip(header, cells, strict=False)))
                i += 1
            current["tables"].append(rows)
            continue
        elif re.match(r"^\s*[-*]\s+", line):
            current["bullets"].append(re.sub(r"^\s*[-*]\s+", "", line).strip())
        i += 1
    sections.append(current)
    return {"available": True, "title": title, "sections": sections}


def report_json(name: str, reports: Path = REPORTS) -> dict[str, Any]:
    path = reports / name
    if not path.exists():
        return {"available": False, "source": f"reports/{name}", "reason": "not written yet"}
    return {"source": f"reports/{name}", **parse_report(path.read_text(encoding="utf-8"))}


def ledgers(reports: Path = REPORTS) -> dict[str, Any]:
    out: dict[str, Any] = {}
    bq = reports / "bq_ledger.csv"
    if bq.exists():
        with bq.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        by_ws: dict[str, int] = defaultdict(int)
        for r in rows:
            billed = (r.get("billed_bytes") or "").strip()
            by_ws[r.get("workstream") or "?"] += int(billed) if billed.isdigit() else 0
        total = sum(by_ws.values())
        out["bigquery"] = {
            "source": "reports/bq_ledger.csv",
            "jobs": len(rows),
            "billed_bytes": total,
            "billed_gb": round(total / 1e9, 2),
            "billed_gb_by_workstream": {k: round(v / 1e9, 2) for k, v in sorted(by_ws.items())},
            "note": "measured: bytes billed as logged per job",
        }
    jev = reports / "jev_ledger.csv"
    if jev.exists():
        with jev.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        latencies = [float(r["latency_ms"]) for r in rows if r.get("latency_ms")]
        out["jev"] = {
            "source": "reports/jev_ledger.csv",
            "calls": len(rows),
            "input_tokens": sum(int(r["input_tokens"] or 0) for r in rows),
            "cost_usd": round(sum(float(r["cost_usd"] or 0) for r in rows), 4),
            "median_latency_ms": statistics.median(latencies) if latencies else None,
            "note": "measured: one row per call as logged",
        }
    return out


def write_evidence(out: Path = OUT, reports: Path = REPORTS) -> int:
    """Write the evidence JSON files; return the bytes written."""
    out.mkdir(parents=True, exist_ok=True)
    files = {
        # the AI lexicon run's report under RADAR_SOURCE=ai, as the trust summary reads it
        "backtest.json": report_json(backtest_report(reports).name, reports),
        "label_quality.json": report_json("label_quality.md", reports),
        "ledgers.json": ledgers(reports),
        "trust_summary.json": trust_summary(reports),
    }
    files["index.json"] = {
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {name: body.get("available", True) for name, body in files.items()},
    }
    total = 0
    for name, body in files.items():
        text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        (out / name).write_text(text, encoding="utf-8")
        total += len(text.encode("utf-8"))
    return total


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    print(f"evidence: {write_evidence(out) / 1024:.1f} KiB -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
