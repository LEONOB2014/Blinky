"""Contracts are valid, mocks match their contracts, and the contracts agree with each other."""

import json

import pytest
import yaml
from jsonschema import Draft202012Validator

from radar.contracts import (
    CONTRACTS_DIR,
    MOCKS_DIR,
    contract_name,
    load_schema,
    schema_paths,
    validate_records,
)

SCHEMAS = schema_paths()
PENDING = {"pending-dev-slice", "pending-first-agent-run", "private"}  # private: never mocked


def _yaml(name):
    return yaml.safe_load((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.unit
@pytest.mark.parametrize("schema_path", SCHEMAS, ids=[p.name for p in SCHEMAS])
def test_schema_is_valid_json_schema(schema_path):
    Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))


@pytest.mark.unit
@pytest.mark.parametrize("schema_path", SCHEMAS, ids=[p.name for p in SCHEMAS])
def test_mock_matches_contract(schema_path):
    name = contract_name(schema_path)
    mock = MOCKS_DIR / f"{name}.json"
    pending = load_schema(name).get("x-mock")
    if not mock.exists() and pending in PENDING:
        pytest.skip(f"{name}: mock {pending} (copied from real output once it exists)")
    assert mock.exists(), f"contract {name} has no mock at mocks/{name}.json"
    records = json.loads(mock.read_text(encoding="utf-8"))
    assert records, f"mocks/{name}.json is empty"
    assert validate_records(name, records) == []


@pytest.mark.unit
def test_every_mock_has_a_contract():
    names = {contract_name(p) for p in SCHEMAS}
    orphans = [m.name for m in MOCKS_DIR.glob("*.json") if m.stem not in names]
    assert orphans == [], f"mocks without a contract: {orphans}"


@pytest.mark.unit
def test_decision_values_agree():
    scores = load_schema("topic_scores_weekly")["properties"]["decision"]["enum"]
    card = load_schema("decision_card")["properties"]["decision"]["enum"]
    assert scores == card


@pytest.mark.unit
def test_agents_in_registry_match_the_trace_contract():
    registry = set(_yaml("agents.yaml")["agents"])
    traced = set(load_schema("agent_trace")["properties"]["agent"]["enum"])
    assert registry == traced


@pytest.mark.unit
def test_taxonomy_has_twelve_subtopics_and_known_domain_targets():
    tax = _yaml("taxonomy.yaml")
    subtopics = set(tax["subtopics"])
    assert len(subtopics) == 12
    for domain, spec in tax["domains"].items():
        assert set(spec["explains"]) <= subtopics, domain
    assert "per" not in tax["ranked_entity_types"]


@pytest.mark.unit
def test_api_references_existing_schemas():
    text = (CONTRACTS_DIR / "api.yaml").read_text(encoding="utf-8")
    yaml.safe_load(text)
    names = {contract_name(p) for p in SCHEMAS}
    refs = {part.split('"')[0] for part in text.split('$ref: "')[1:]}
    assert {r.removesuffix(".schema.json") for r in refs} <= names
