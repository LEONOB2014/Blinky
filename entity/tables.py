"""Write a validated table to the lake."""

from __future__ import annotations

from pathlib import Path

import polars as pl


def write_parquet(path: Path, records: list[dict], schema: dict[str, pl.DataType]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(records, schema=schema)
    if "dt" in frame.columns:
        frame = frame.with_columns(pl.col("dt").str.to_date())
    temporary = path.with_suffix(".parquet.tmp")
    frame.write_parquet(temporary)
    temporary.replace(path)
