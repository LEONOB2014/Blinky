"""Run one bq_sql/ script through the spend guard and log its bytes to reports/bq_ledger.csv.

Every job is dry-run first. The run aborts when the dry run exceeds the cap (default 50 GiB, from
``BQ_MAX_BYTES_BILLED_GIB``) or 1.5x the last measured bill of the same script. Multi-statement
scripts are not trusted to their dry run (S4 billed 14.2 GB against a 10.6 GB dry run, measured):
their expected bill is the larger of the dry run and the last measured bill, and the guard and the
hard ``--maximum_bytes_billed`` limit both use 1.5x that. Uses the ``bq`` CLI (gcloud login).

    uv run python pipelines/ingest/run_bq.py bq_sql/s2_monthly_insert.sql --month 2026-07
    uv run python pipelines/ingest/run_bq.py bq_sql/s4_aggregates.sql --note "ring-1 edges"
    uv run python pipelines/ingest/run_bq.py bq_sql/s4_aggregates.sql --dry-run-only

Month scripts carry the tokens ``${PART_START}``, ``${PART_END}`` (ingestion partitions, the month
+/- 1 day), ``${DATE_START}`` and ``${DATE_END}`` (GKG ``DATE`` integers for the exact month),
``${MONTH_START}`` and ``${MONTH_END}`` (ISO dates, end exclusive).
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = REPO_ROOT / "reports" / "bq_ledger.csv"
LEDGER_COLUMNS = [
    "ts_utc",
    "job_id",
    "script",
    "workstream",
    "dry_run_bytes",
    "billed_bytes",
    "cap_gib",
    "note",
]
GIB = 2**30
GROWTH_LIMIT = 1.5
DRY_RUN_RE = re.compile(r"process (upper|lower) bound of (\d+) bytes")


class GuardError(RuntimeError):
    """The job would exceed the cap or the ledger history; nothing was run."""


@dataclass(frozen=True)
class Plan:
    dry_run_bytes: int
    expected_bytes: int
    max_bytes_billed: int
    previous_billed: int | None
    multi_statement: bool


def parse_dry_run(output: str) -> tuple[int, bool]:
    """(bytes, is_lower_bound) from the bq CLI dry-run line ('... upper bound of N bytes of data.').

    A script that creates a table and then reads it gets a *lower* bound (often 0): unusable.
    """
    match = DRY_RUN_RE.search(output)
    if not match:
        raise ValueError(f"no byte estimate in dry-run output: {output.strip()[:200]!r}")
    return int(match.group(2)), match.group(1) == "lower"


def strip_comments(sql: str) -> str:
    """Remove -- comments and string literals so statement counting sees only code."""
    # One left-to-right pass, so an apostrophe inside a comment never opens a string.
    pattern = r"--[^\n]*|'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\""
    return re.sub(pattern, lambda m: "" if m.group().startswith("--") else "''", sql)


def count_statements(sql: str) -> int:
    return sum(1 for part in strip_comments(sql).split(";") if part.strip())


def month_params(month: str) -> dict[str, str]:
    """Token values for a 'YYYY-MM' month; the partition window is the month +/- 1 day."""
    first = dt.date.fromisoformat(f"{month}-01")
    nxt = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return {
        "PART_START": (first - dt.timedelta(days=1)).isoformat(),
        "PART_END": (nxt + dt.timedelta(days=1)).isoformat(),
        "DATE_START": f"{first:%Y%m%d}000000",
        "DATE_END": f"{nxt:%Y%m%d}000000",
        "MONTH_START": first.isoformat(),
        "MONTH_END": nxt.isoformat(),
    }


def render(sql: str, params: dict[str, str]) -> str:
    """Substitute ${TOKEN}s; every token in the script must have a value and vice versa."""
    found = set(re.findall(r"\$\{([A-Z_]+)\}", sql))
    missing = found - params.keys()
    if missing:
        raise ValueError(f"script needs {sorted(missing)}; pass --month")
    if params and not found:
        raise ValueError("--month given but the script has no ${...} tokens")
    for key, value in params.items():
        sql = sql.replace("${" + key + "}", value)
    return sql


def ledger_label(script: Path, month: str | None) -> str:
    return f"{script.name} ({month})" if month else script.name


def previous_billed(rows: list[dict[str, str]], script_name: str) -> int | None:
    """Last measured bill (> 0) of a successful run of the same script, whatever its month."""
    for row in reversed(rows):
        if (row.get("note") or "").startswith("FAILED"):
            continue
        label = row.get("script", "")
        billed = (row.get("billed_bytes") or "").strip()
        same = label == script_name or label.startswith(script_name + " (")
        if same and billed.isdigit() and int(billed) > 0:
            return int(billed)
    return None


def plan(
    dry_run_bytes: int,
    multi_statement: bool,
    previous: int | None,
    cap_bytes: int,
    baseline_scale: float = 1.0,
    lower_bound: bool = False,
    expect_bytes: int | None = None,
) -> Plan:
    """Decide the expected bill and the hard limit, or raise GuardError.

    ``expect_bytes`` is the operator's estimate for a script with no ledger history; it replaces
    the previous bill and is the only basis when the dry run is a lower bound.
    """
    scaled_prev = int(previous * baseline_scale) if previous else None
    if scaled_prev is None and expect_bytes:
        scaled_prev = expect_bytes
    if lower_bound and scaled_prev is None:
        raise GuardError("dry run is only a lower bound and there is no history; pass --expect-gib")
    if multi_statement:
        expected = max(dry_run_bytes, scaled_prev or 0)
        limit = int(GROWTH_LIMIT * expected)
        if limit > cap_bytes:
            raise GuardError(
                f"multi-statement script: 1.5x expected bill {limit / GIB:.1f} GiB "
                f"exceeds the cap {cap_bytes / GIB:.0f} GiB"
            )
        if scaled_prev and dry_run_bytes > GROWTH_LIMIT * scaled_prev:
            raise GuardError(
                f"dry run {dry_run_bytes / GIB:.1f} GiB exceeds 1.5x the last bill "
                f"{scaled_prev / GIB:.1f} GiB"
            )
        return Plan(dry_run_bytes, expected, limit, previous, True)
    if dry_run_bytes > cap_bytes:
        raise GuardError(
            f"dry run {dry_run_bytes / GIB:.1f} GiB exceeds the cap {cap_bytes / GIB:.0f} GiB"
        )
    if scaled_prev and dry_run_bytes > GROWTH_LIMIT * scaled_prev:
        raise GuardError(
            f"dry run {dry_run_bytes / GIB:.1f} GiB exceeds 1.5x the last bill "
            f"{scaled_prev / GIB:.1f} GiB"
        )
    # A single statement bills at most its dry run (plus 10 MB minimum); the cap is the hard stop.
    return Plan(dry_run_bytes, dry_run_bytes, cap_bytes, previous, False)


def ledger_row(
    job_id: str,
    script: str,
    workstream: str,
    dry_run_bytes: int,
    billed_bytes: int | None,
    cap_gib: float,
    note: str,
    now: dt.datetime | None = None,
) -> dict[str, str]:
    now = now or dt.datetime.now(dt.UTC)
    return {
        "ts_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "job_id": job_id,
        "script": script,
        "workstream": workstream,
        "dry_run_bytes": str(dry_run_bytes),
        "billed_bytes": "" if billed_bytes is None else str(billed_bytes),
        "cap_gib": f"{cap_gib:g}",
        "note": note,
    }


def read_ledger(path: Path = LEDGER) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_ledger(row: dict[str, str], path: Path = LEDGER) -> None:
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow(row)


def project_id() -> str:
    value = os.environ.get("GCP_PROJECT_ID")
    if not value:
        from dotenv import dotenv_values

        value = dotenv_values(REPO_ROOT / ".env").get("GCP_PROJECT_ID")
    if not value:
        raise SystemExit("GCP_PROJECT_ID is not set (.env)")
    return value


def default_cap_gib() -> float:
    value = os.environ.get("BQ_MAX_BYTES_BILLED_GIB")
    if not value:
        from dotenv import dotenv_values

        value = dotenv_values(REPO_ROOT / ".env").get("BQ_MAX_BYTES_BILLED_GIB")
    return float(value or 50)


def bq(project: str, *args: str, stdin: str | None = None) -> str:
    cmd = ["bq", f"--project_id={project}", "--location=US", *args]
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=False)  # noqa: S603
    if proc.returncode != 0:
        lines = [
            x for x in (proc.stdout + proc.stderr).splitlines() if not x.startswith("Waiting on")
        ]
        raise RuntimeError(f"bq {args[0]} failed: {' '.join(lines)[-2000:]}")
    return proc.stdout


def dry_run(project: str, sql: str) -> tuple[int, bool]:
    return parse_dry_run(bq(project, "query", "--use_legacy_sql=false", "--dry_run", stdin=sql))


def execute(project: str, sql: str, job_id: str, max_bytes: int, show: bool = False) -> int:
    """Run the job synchronously and return its billed bytes (scripts: summed over children)."""
    out = bq(
        project,
        "--format=pretty" if show else "--format=none",
        "query",
        "--max_rows=200",
        "--use_legacy_sql=false",
        f"--job_id={job_id}",
        f"--maximum_bytes_billed={max_bytes}",
        stdin=sql,
    )
    if show:
        print(out)
    return billed_bytes(project, job_id)


def billed_bytes(project: str, job_id: str) -> int:
    job = json.loads(bq(project, "--format=json", "show", "-j", job_id))
    return int(job["statistics"].get("query", {}).get("totalBytesBilled") or 0)


def new_job_id(script: Path, month: str | None) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_]", "_", script.stem)
    suffix = f"_{month.replace('-', '')}" if month else ""
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S")
    return f"radar_{stem}{suffix}_{stamp}_{secrets.token_hex(3)}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("script", type=Path)
    ap.add_argument("--month", help="YYYY-MM, fills the ${...} tokens")
    ap.add_argument("--cap-gib", type=float, default=None, help="hard cap (default 50)")
    ap.add_argument(
        "--baseline-scale",
        type=float,
        default=1.0,
        help="scale the last bill when the input table grew on purpose (e.g. after a backfill); "
        "recorded in the ledger note",
    )
    ap.add_argument(
        "--expect-gib",
        type=float,
        default=None,
        help="expected bill for a script with no ledger history (estimate from column dry runs)",
    )
    ap.add_argument("--workstream", default="WS1")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run-only", action="store_true")
    ap.add_argument("--show", action="store_true", help="print the result rows (checks)")
    args = ap.parse_args(argv)

    script = args.script.resolve()
    cap_gib = args.cap_gib if args.cap_gib is not None else default_cap_gib()
    sql = render(script.read_text(encoding="utf-8"), month_params(args.month) if args.month else {})
    project = project_id()
    multi = count_statements(sql) > 1
    previous = previous_billed(read_ledger(), script.name)
    dry, lower = dry_run(project, sql)
    label = ledger_label(script, args.month)
    print(
        f"{label}: dry run {'lower bound ' if lower else ''}{dry:,} bytes ({dry / GIB:.2f} GiB); "
        f"{'multi-statement; ' if multi else ''}"
        f"last bill {f'{previous:,}' if previous else 'none'}; cap {cap_gib:g} GiB"
    )
    try:
        decision = plan(
            dry,
            multi,
            previous,
            int(cap_gib * GIB),
            args.baseline_scale,
            lower,
            int(args.expect_gib * GIB) if args.expect_gib else None,
        )
    except GuardError as err:
        print(f"ABORT: {err}", file=sys.stderr)
        return 2
    print(
        f"expected {decision.expected_bytes / GIB:.2f} GiB; "
        f"maximum_bytes_billed {decision.max_bytes_billed / GIB:.2f} GiB"
    )
    if args.dry_run_only:
        return 0
    job_id = new_job_id(script, args.month)
    note = args.note
    if args.baseline_scale != 1.0:
        note = f"{note}; baseline_scale={args.baseline_scale:g}".lstrip("; ")
    try:
        billed = execute(project, sql, job_id, decision.max_bytes_billed, args.show)
    except RuntimeError as err:
        # A failed script still bills the statements that ran before the error.
        try:
            partial = billed_bytes(project, job_id)
        except (RuntimeError, KeyError, ValueError):
            partial = None
        append_ledger(
            ledger_row(
                job_id, label, args.workstream, dry, partial, cap_gib, f"FAILED; {note} (measured)"
            )
        )
        print(f"job {job_id} failed: {err}", file=sys.stderr)
        return 1
    append_ledger(
        ledger_row(job_id, label, args.workstream, dry, billed, cap_gib, f"{note} (measured)")
    )
    print(f"job {job_id}: billed {billed:,} bytes ({billed / GIB:.2f} GiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
