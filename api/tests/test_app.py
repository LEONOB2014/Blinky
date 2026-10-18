"""Endpoint tests for `api/app.py` against `contracts/api.yaml` on the dev slice."""

import datetime as dt

import polars as pl
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from agents.llm import Reply
from api.app import _guard_ring, app
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
def test_radar_reads_ai_scores_when_that_source_is_selected(
    client: TestClient, tmp_path, monkeypatch
):
    monkeypatch.setenv("RADAR_SOURCE", "ai")
    ai_path = tmp_path / "topic_ai_scores_weekly.parquet"
    gdelt_path = tmp_path / "topic_scores_weekly.parquet"
    row = {
        "week": "2026-W42",
        "topic_id": "ai:product:chatgpt",
        "label_es": "ChatGPT",
        "subtopics": ["products"],
        "primary_subtopic": "products",
        "emergence_pct": 70.0,
        "stage": "emergente",
        "saturation": 0.1,
        "audience_fit": 0.5,
        "outperformance": None,
        "emotional_charge_pct": 40.0,
        "framing_angle": "explicador neutral",
        "window": {
            "state": "dias_restantes",
            "days_left": 5,
            "typical_lag_days": 6.0,
            "n_onsets": 10,
        },
        "priority": 0.5,
        "rank": 1,
        "decision": "preparar",
        "why": ["Emergencia medida"],
        "evidence_ids": [],
        "has_wikipedia_es_pt": True,
        "profile": "full",
    }
    pl.DataFrame([row]).write_parquet(ai_path)
    pl.DataFrame([{**row, "topic_id": "org:kroger", "label_es": "Kroger"}]).write_parquet(
        gdelt_path
    )

    def fake(name: str):
        if name == "topic_ai_scores_weekly":
            return ai_path
        if name == "topic_scores_weekly":
            return gdelt_path
        return tmp_path / f"{name}.parquet"

    monkeypatch.setattr("api.app.gold", fake)
    rows = client.get("/api/radar?week=2026-W42&limit=5").json()
    assert [r["topic_id"] for r in rows] == ["ai:product:chatgpt"]
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


def _score_row(week, topic_id, rank, label_es):
    return {
        "week": week, "topic_id": topic_id, "label_es": label_es, "subtopics": ["chips_infra"],
        "primary_subtopic": "chips_infra", "emergence_pct": 70.0, "stage": "emergente",
        "saturation": 0.3, "audience_fit": 0.6, "outperformance": None,
        "emotional_charge_pct": 50.0, "framing_angle": "oportunidad ejecutiva",
        "window": {"state": "sin_estimacion", "days_left": None, "typical_lag_days": None,
                   "n_onsets": 0},
        "priority": 1.0 - rank / 10, "rank": rank, "decision": "preparar",
        "why": ["Crecimiento semanal medido en GDELT"], "evidence_ids": [],
        "has_wikipedia_es_pt": True, "profile": "dev",
    }  # fmt: skip


def _gold_at(monkeypatch, tmp_path, tables):
    paths = {}
    for name, df in tables.items():
        paths[name] = tmp_path / f"{name}.parquet"
        df.write_parquet(paths[name])
    monkeypatch.setattr(
        "api.app.gold", lambda name: paths.get(name, tmp_path / f"missing_{name}.parquet")
    )


@pytest.mark.unit
def test_radar_never_returns_a_deny_listed_org(client: TestClient, tmp_path, monkeypatch):
    # org:reuters is on the taxonomy's ranked_universe.org_deny list and ranked first here.
    rows = [
        _score_row("2026-W42", "org:reuters", 1, "Reuters"),
        _score_row("2026-W42", "org:nvidia", 2, "Nvidia"),
        _score_row("2026-W42", "chips_infra", 3, "chips_infra"),
        _score_row("2026-W41", "org:nvidia", 1, "Nvidia"),
    ]
    _gold_at(monkeypatch, tmp_path, {"topic_scores_weekly": pl.DataFrame(rows)})
    body = client.get("/api/radar").json()  # default: the latest scored week
    assert [r["topic_id"] for r in body] == ["org:nvidia", "chips_infra"]
    assert {r["week"] for r in body} == {"2026-W42"}
    assert body[1]["label_es"] == "Chips e infraestructura"  # subtopic label from the taxonomy
    assert validate_records("topic_scores_weekly", body) == []
    assert [r["week"] for r in client.get("/api/radar?week=2026-W41").json()] == ["2026-W41"]


@pytest.mark.unit
def test_context_never_returns_a_person_neighbour(client: TestClient, tmp_path, monkeypatch):
    ring = pl.DataFrame(
        {
            "wk": [dt.date(2026, 10, 12)] * 3,
            "topic_id": ["org:nvidia"] * 3,
            "neighbor": ["per:jensen huang", "org:tsmc", "thm:TECH_AUTOMATION"],
            "rank": [1, 2, 3],
            "n": [40, 30, 20],
            "npmi": [0.6, 0.5, 0.4],
            "neighbor_segment": [None, None, None],
            "neighbor_domain": [None, None, None],
        },
        schema_overrides={"neighbor_segment": pl.Utf8, "neighbor_domain": pl.Utf8},
    )
    _gold_at(monkeypatch, tmp_path, {"topic_context_1hop": ring})
    body = client.get("/api/topic/org:nvidia/context?week=2026-W42").json()
    assert [r["neighbor"] for r in body] == ["org:tsmc", "thm:TECH_AUTOMATION"]
    assert [r["rank"] for r in body] == [1, 2]
    assert validate_records("topic_context_1hop", body) == []
    assert client.get("/api/topic/per:jensen huang/context").json() == []
    assert client.get("/api/topic/per:jensen huang/timeline").json() == []


@pytest.mark.unit
def test_guard_ring_drops_persons_the_sql_missed():
    rows = [
        {"neighbor": "PER:Someone", "rank": 1},
        {"neighbor": "org:tsmc", "rank": 2},
    ]
    assert _guard_ring(rows) == [{"neighbor": "org:tsmc", "rank": 1}]


class _FeedbackSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_feedback(self, **kw) -> None:
        self.calls.append(kw)


_TRACE = "0f8fad5b-d9cb-469f-a165-70867728950e"


def test_chat_returns_a_trace_id_field(client: TestClient, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    app.state.chat_model = ScriptedChat("Respuesta.")
    body = client.post("/api/chat", json={"message": "¿Cuánto ha costado BigQuery?"}).json()
    assert "trace_id" in body and body["trace_id"] is None  # tracing off in tests


def test_feedback_is_503_without_langsmith(client: TestClient, monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    app.state.feedback_client = None
    resp = client.post("/api/feedback", json={"trace_id": _TRACE, "score": 1})
    assert resp.status_code == 503


def test_feedback_records_one_score_on_the_trace(client: TestClient):
    spy = _FeedbackSpy()
    app.state.feedback_client = spy
    try:
        resp = client.post(
            "/api/feedback", json={"trace_id": _TRACE, "score": 0, "comment": "muy largo"}
        )
    finally:
        app.state.feedback_client = None
    assert resp.status_code == 202
    assert spy.calls == [
        {"run_id": _TRACE, "key": "user_thumbs", "score": 0, "comment": "muy largo"}
    ]


@pytest.mark.parametrize(
    "body", [{"trace_id": "not-a-uuid", "score": 1}, {"trace_id": _TRACE, "score": 5}]
)
def test_feedback_rejects_bad_input(client: TestClient, body):
    app.state.feedback_client = _FeedbackSpy()
    try:
        assert client.post("/api/feedback", json=body).status_code == 422
    finally:
        app.state.feedback_client = None
