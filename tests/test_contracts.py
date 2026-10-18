"""Every contract is valid JSON Schema and every mock matches its contract."""

import json

import pytest
from jsonschema import Draft202012Validator

from radar.contracts import MOCKS_DIR, contract_name, schema_paths, validate_records

SCHEMAS = schema_paths()


@pytest.mark.unit
@pytest.mark.parametrize("schema_path", SCHEMAS, ids=[p.name for p in SCHEMAS])
def test_schema_is_valid_json_schema(schema_path):
    Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))


@pytest.mark.unit
@pytest.mark.parametrize("schema_path", SCHEMAS, ids=[p.name for p in SCHEMAS])
def test_mock_matches_contract(schema_path):
    name = contract_name(schema_path)
    mock = MOCKS_DIR / f"{name}.json"
    assert mock.exists(), f"contract {name} has no mock at mocks/{name}.json"
    records = json.loads(mock.read_text(encoding="utf-8"))
    assert records, f"mocks/{name}.json is empty"
    assert validate_records(name, records) == []


@pytest.mark.unit
def test_every_mock_has_a_contract():
    names = {contract_name(p) for p in SCHEMAS}
    orphans = [m.name for m in MOCKS_DIR.glob("*.json") if m.stem not in names]
    assert orphans == [], f"mocks without a contract: {orphans}"
