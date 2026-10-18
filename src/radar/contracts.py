"""Load the JSON Schema contracts and validate records against them.

A contract is ``contracts/<name>.schema.json``; its mock is ``mocks/<name>.json`` (a list of
records). Workstreams call :func:`validate_records` on their outputs before writing them.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from radar.paths import REPO_ROOT

CONTRACTS_DIR = REPO_ROOT / "contracts"
MOCKS_DIR = REPO_ROOT / "mocks"


def schema_paths() -> list[Path]:
    return sorted(CONTRACTS_DIR.glob("*.schema.json"))


def contract_name(schema_path: Path) -> str:
    return schema_path.name.removesuffix(".schema.json")


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def validate_records(name: str, records: Iterable[dict[str, Any]]) -> list[str]:
    """Return one message per violation (empty when every record matches the contract)."""
    validator = Draft202012Validator(load_schema(name))
    return [
        f"record {i}: {'/'.join(map(str, err.absolute_path)) or '<root>'}: {err.message}"
        for i, record in enumerate(records)
        for err in validator.iter_errors(record)
    ]
