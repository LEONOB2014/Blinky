"""The committed dev slice and mocks hold no personal data or free text (the repo goes public)."""

import json

import polars as pl
import pytest

from radar.contracts import MOCKS_DIR
from radar.fixtures import ALLOWED_COLUMNS, DEV_DIR, FORBIDDEN_COLUMNS

FILES = sorted(DEV_DIR.glob("*.parquet"))


@pytest.mark.unit
def test_dev_slice_exists():
    # Every committed file is allow-listed; the orchestrator's GDELT files are always present.
    assert {p.stem for p in FILES} <= set(ALLOWED_COLUMNS)
    assert {"daily_totals", "daily_topic", "edges_weekly", "gkg_ai_sample"} <= {
        p.stem for p in FILES
    }


@pytest.mark.unit
@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_dev_slice_columns_are_allow_listed(path):
    columns = set(pl.read_parquet_schema(path))
    assert columns <= ALLOWED_COLUMNS[path.stem], sorted(columns - ALLOWED_COLUMNS[path.stem])
    assert not {c.lower() for c in columns} & FORBIDDEN_COLUMNS


@pytest.mark.unit
@pytest.mark.parametrize("path", FILES, ids=[p.name for p in FILES])
def test_dev_slice_files_stay_small(path):
    assert path.stat().st_size < 1_000_000


@pytest.mark.unit
def test_edges_carry_no_person_nodes():
    edges = pl.read_parquet(DEV_DIR / "edges_weekly.parquet")
    assert not edges.filter(
        pl.col("x").str.starts_with("per:") | pl.col("y").str.starts_with("per:")
    ).height


@pytest.mark.unit
def test_mocks_hold_no_forbidden_fields():
    for mock in MOCKS_DIR.glob("*.json"):
        for record in json.loads(mock.read_text(encoding="utf-8")):
            assert not {k.lower() for k in record} & FORBIDDEN_COLUMNS, mock.name
