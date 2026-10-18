"""Import the hand-filled 30X social posts sheet into the lake, validated against its contract.

    uv run python -m pipelines.social.importer                    # lake/manual/social_posts.csv
    uv run python -m pipelines.social.importer --csv path/to.csv  # another copy of the sheet
    uv run python -m pipelines.social.importer --init             # put an empty sheet in the lake

Numbers may be typed the way the platforms show them ("1.2K", "1,2 mil", "3.456", "1 234"),
dates as YYYY-MM-DD or DD/MM/YYYY, yes/no as sí/no/yes/true/1/0. Every problem is reported with
its row and column; nothing is written until the whole sheet is valid.
"""

import argparse
import csv
import datetime as dt
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import polars as pl

from radar.contracts import validate_records
from radar.paths import REPO_ROOT, lake

TEMPLATE = REPO_ROOT / "templates" / "social_posts_template.csv"
LOCAL_TZ = dt.timezone(dt.timedelta(hours=-5))  # Bogotá / Lima (UTC-5), where the sheet is filled
INT_FIELDS = ("views", "reactions", "comments", "shares", "saves", "followers_at_observation")
NULLABLE_TEXT = ("topic_hint", "notes")
_SUFFIX = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "mm": 1_000_000, "millones": 1_000_000}


def default_csv() -> Path:
    return lake() / "manual" / "social_posts.csv"


def parse_count(raw: str) -> int | None:
    """'1.2K' -> 1200, '1,2 mil' -> 1200, '3.456' -> 3456, '1 234' -> 1234, '' -> None."""
    text = raw.strip().lower().replace(" ", " ")
    if not text:
        return None
    match = re.fullmatch(r"([\d.,\s]+)\s*(k|mil|mm|m|millones)?", text)
    if not match:
        raise ValueError(f"not a count: {raw!r}")
    number, suffix = match.group(1).replace(" ", ""), match.group(2)
    if suffix:  # a decimal comma or point before a suffix: "1,2 mil", "1.2K"
        value = float(number.replace(",", "."))
        return round(value * _SUFFIX[suffix])
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", number):  # thousands separators: "3.456", "1,234"
        return int(re.sub(r"[.,]", "", number))
    if re.fullmatch(r"\d+", number):
        return int(number)
    raise ValueError(f"ambiguous count: {raw!r} (write it without decimals)")


def parse_date(raw: str) -> dt.date:
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TZ).date()
        except ValueError:
            continue
    raise ValueError(f"not a date (YYYY-MM-DD or DD/MM/YYYY): {raw!r}")


def parse_moment(raw: str) -> dt.datetime:
    """'2026-10-18 09:30' or '18/10/2026 09:30' in UTC-5; a bare date means noon."""
    text = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=LOCAL_TZ)
        except ValueError:
            continue
    return dt.datetime.combine(parse_date(text), dt.time(12), tzinfo=LOCAL_TZ)


def parse_bool(raw: str) -> bool | None:
    text = raw.strip().lower()
    if not text:
        return None
    if text in {"sí", "si", "yes", "y", "true", "1", "x"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    raise ValueError(f"not yes/no: {raw!r}")


def to_record(row: dict[str, str]) -> dict[str, Any]:
    rec: dict[str, Any] = {k: (v or "").strip() for k, v in row.items()}
    rec["platform"] = rec["platform"].lower()
    rec["format"] = rec["format"].lower()
    rec["language"] = rec["language"].lower()
    posted = parse_date(rec["posted_date"])
    observed = parse_moment(rec["observed_at"])
    rec["posted_date"] = posted.isoformat()
    rec["observed_at"] = observed.isoformat()
    for field in INT_FIELDS:
        rec[field] = parse_count(rec[field])
    rec["is_ai_topic"] = parse_bool(rec["is_ai_topic"])
    for field in NULLABLE_TEXT:
        rec[field] = rec[field] or None
    if rec["reactions"] is None or rec["comments"] is None:
        raise ValueError("reactions and comments are required (write 0 when there are none)")
    rec["engagement"] = sum(rec[f] or 0 for f in ("reactions", "comments", "shares", "saves"))
    followers = rec["followers_at_observation"]
    rec["engagement_per_1k_followers"] = (
        round(rec["engagement"] / followers * 1000, 3) if followers else None
    )
    age = (observed.date() - posted).days
    if age < 0:
        raise ValueError("observed_at is before posted_date")
    rec["age_days_at_observation"] = age
    return rec


def read_sheet(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Valid records and every problem found (row numbers as in the spreadsheet, header = 1)."""
    expected = TEMPLATE.read_text(encoding="utf-8").strip().split(",")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != expected:
            return [], [f"header differs from the template: {reader.fieldnames} != {expected}"]
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    records, problems = [], []
    for i, row in enumerate(rows, start=2):
        try:
            rec = to_record(row)
        except (ValueError, KeyError) as exc:
            problems.append(f"row {i}: {exc}")
            continue
        errors = validate_records("social_post_metrics", [rec])
        problems += [f"row {i}: {e}" for e in errors]
        if not errors:
            records.append(rec)
    keys = [r["post_key"] for r in records]
    problems += [f"duplicate post_key {k}" for k in sorted({k for k in keys if keys.count(k) > 1})]
    return records, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--init", action="store_true", help="copy the empty template into the lake")
    args = parser.parse_args()
    path = args.csv or default_csv()
    if args.init:
        if path.exists():
            sys.exit(f"{path} already exists; not overwriting it")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TEMPLATE, path)
        print(f"empty sheet at {path}")
        return
    records, problems = read_sheet(path)
    if problems:
        print("\n".join(problems))
        sys.exit(f"{len(problems)} problem(s); nothing written")
    out = lake() / "gold" / "social_post_metrics.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    # explicit types: an all-empty column (e.g. views) must not become a Null-typed column,
    # which DuckDB 1.5 cannot filter (see agents/tools.py)
    schema = dict.fromkeys((*INT_FIELDS, "engagement", "age_days_at_observation"), pl.Int64) | {
        "engagement_per_1k_followers": pl.Float64,
        "is_ai_topic": pl.Boolean,
        "topic_hint": pl.String,
        "notes": pl.String,
    }
    pl.DataFrame(records, schema_overrides=schema, infer_schema_length=None).write_parquet(out)
    by_platform = pl.DataFrame(records).group_by("platform").len().sort("platform").rows()
    print(f"{len(records)} posts -> {out} ({', '.join(f'{p}: {n}' for p, n in by_platform)})")


if __name__ == "__main__":
    main()
