"""Endpoint tests for `api/app.py` against `contracts/api.yaml` on the dev slice."""

import polars as pl
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from agents.llm import Reply
from api.app import app
from radar.contracts import validate_records


class ScriptedChat:
    """Scripted stand-in for the HTTP LLM client (no network in CI)."""

    def __init__(self, master_text: str) -> None:
        self.master_text = master_text

    def chat(self, messages, tools):
        if messages[0]["content"].startswith("Eres el Maestro de Medios"):
            return Reply(content=self.master_text, model="scripted", latency_ms=12, tokens=42)
        return Reply(content="Informe del especialista.", model="scripted", latency_ms=8, tokens=20)


@pytest.fixture(autouse=True)
def _dev_profile(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")
    app.state.chat_model = None
    yield
    app.state.chat_model = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.unit
def test_freshness_returns_newest_dates_and_dev_profile(client: TestClient):
    resp = client.get("/api/freshness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["profile"] == "dev"
    assert body["tables"]["daily_totals"] == "2026-10-17"
    assert body["tables"]["daily_topic"] == "2026-10-17"
    assert body["tables"]["daily_topic_rolling"] == "2026-10-17"
    assert body["tables"]["edges_weekly"] == "2026-10-12"
    assert body["newest"] == body["tables"]


@pytest.mark.unit
def test_radar_returns_empty_list_and_reason_header_before_ws4_table_exists(client: TestClient):
    resp = client.get("/api/radar")
    assert resp.status_code == 200
    assert resp.json() == []
    assert "topic_scores_weekly" in resp.headers.get("X-Radar-Empty-Reason", "")
    assert resp.headers.get("X-Radar-Status") == "pending-ws4"


@pytest.mark.unit
def test_radar_returns_validated_scores_when_table_exists(
    client: TestClient, tmp_path, monkeypatch
):
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir(parents=True)
    scores_path = gold_dir / "topic_scores_weekly.parquet"
    df = pl.DataFrame(
        [
            {
                "week": "2026-W41",
                "topic_id": "org:google",
                "label_es": "Google",
                "subtopics": ["llms_models", "agents"],
                "primary_subtopic": "llms_models",
                "emergence_pct": 88.5,
                "stage": "emergente",
                "saturation": 0.24,
                "audience_fit": 0.85,
                "outperformance": None,
                "emotional_charge_pct": 72.0,
                "framing_angle": "oportunidad ejecutiva",
                "window": {
                    "state": "dias_restantes",
                    "days_left": 5,
                    "typical_lag_days": 7.0,
                    "n_onsets": 4,
                },
                "priority": 0.84,
                "rank": 1,
                "decision": "publicar_ahora",
                "why": ["Crecimiento semanal medido en GDELT", "Baja saturación en español"],
                "evidence_ids": ["20261012000000-1"],
                "has_wikipedia_es_pt": True,
                "profile": "dev",
            }
        ]
    )
    df.write_parquet(scores_path)
    monkeypatch.setattr(
        "api.app.gold",
        lambda name: scores_path if name == "topic_scores_weekly" else tmp_path / f"{name}.parquet",
    )

    resp = client.get("/api/radar?week=2026-W41&limit=5")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert validate_records("topic_scores_weekly", rows) == []


@pytest.mark.unit
def test_topic_timeline_matches_topic_daily_contract_on_dev_slice(client: TestClient):
    resp = client.get("/api/topic/regulation_policy/timeline")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert validate_records("topic_daily", rows) == []
    assert {r["lang_bucket"] for r in rows} <= {"eng", "spa", "por", "other"}
    assert all(r["topic_id"] == "regulation_policy" and r["segment"] == "ai" for r in rows)


@pytest.mark.unit
def test_topic_context_matches_1hop_contract_on_dev_slice(client: TestClient):
    resp = client.get("/api/topic/org:google/context?week=2026-W41")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    assert validate_records("topic_context_1hop", rows) == []
    assert all(r["n"] >= 3 and r["npmi"] > 0.1 for r in rows)
    assert "org:united states" not in {r["neighbor"] for r in rows}


@pytest.mark.unit
def test_chat_returns_503_when_nebius_key_is_missing(client: TestClient, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    resp = client.post("/api/chat", json={"message": "¿Qué tema sube esta semana?"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "agents runtime not deployed yet"}


@pytest.mark.unit
def test_chat_returns_contract_validated_turn_with_scripted_model(client: TestClient):
    app.state.chat_model = ScriptedChat("Decisión: PENDIENTE. Muéstramelo en el grafo.")
    resp = client.post(
        "/api/chat",
        json={
            "conversation_id": "conv12345678",
            "message": "¿Qué tema sube esta semana? muéstramelo en el grafo",
            "week": "2026-W41",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == "conv12345678"
    assert isinstance(body["answer_es"], str) and body["answer_es"]
    assert validate_records("decision_card", body["decision_cards"]) == []
    assert len(body["view_commands"]) >= 1
    assert validate_records("view_command", body["view_commands"]) == []
    assert len(body["trace"]) >= 1
    assert validate_records("agent_trace", body["trace"]) == []
