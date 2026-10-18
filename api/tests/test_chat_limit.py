"""The public chat is rate limited: per client (sliding window) and per UTC day (all clients)."""

import datetime as dt

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from agents.llm import Reply
from api.app import ChatLimits, ChatQuota, app, chat_limits, chat_quota

T0 = dt.datetime(2026, 10, 18, 5, 0, tzinfo=dt.UTC).timestamp()
LIMITS = ChatLimits(per_client=10, window_s=600, daily_cap=500)


class ScriptedChat:
    def chat(self, messages, tools):
        return Reply(content="Decisión: PENDIENTE.", model="scripted", latency_ms=5, tokens=10)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setenv("RADAR_PROFILE", "dev")
    for key in ("RADAR_CHAT_PER_CLIENT", "RADAR_CHAT_WINDOW_S", "RADAR_CHAT_DAILY_CAP"):
        monkeypatch.delenv(key, raising=False)
    chat_quota.reset()
    app.state.chat_model = ScriptedChat()
    yield
    app.state.chat_model = None
    chat_quota.reset()


@pytest.mark.unit
def test_defaults_are_ten_per_ten_minutes_and_500_a_day():
    assert chat_limits() == LIMITS


@pytest.mark.unit
def test_client_window_refuses_the_eleventh_turn_then_recovers():
    q = ChatQuota()
    for i in range(10):
        assert q.admit("a", LIMITS, T0 + i) is None
    refusal = q.admit("a", LIMITS, T0 + 30)
    assert refusal is not None and "10 cada 10 minutos" in refusal
    assert (
        q.retry_after_s("a", LIMITS, T0 + 30) == 570
    )  # the first turn leaves the window at T0+600
    assert q.admit("b", LIMITS, T0 + 30) is None  # another client is not affected
    assert q.admit("a", LIMITS, T0 + 601) is None  # the oldest turn left the window


@pytest.mark.unit
def test_refused_turns_are_not_counted():
    q = ChatQuota()
    limits = ChatLimits(per_client=1, window_s=600, daily_cap=2)
    assert q.admit("a", limits, T0) is None
    for _ in range(5):
        assert q.admit("a", limits, T0 + 1) is not None
    assert q.admit("b", limits, T0 + 2) is None  # the daily count is still 2, not 7


@pytest.mark.unit
def test_daily_cap_spans_clients_and_resets_at_utc_midnight():
    q = ChatQuota()
    limits = ChatLimits(per_client=10, window_s=600, daily_cap=3)
    for client in ("a", "b", "c"):
        assert q.admit(client, limits, T0) is None
    refusal = q.admit("d", limits, T0 + 1)
    assert refusal is not None and "límite diario de 3" in refusal
    midnight = dt.datetime(2026, 10, 19, tzinfo=dt.UTC).timestamp()
    assert q.retry_after_s("d", limits, T0 + 1) == midnight - (T0 + 1)  # 18 h 59 min 59 s
    assert q.admit("d", limits, midnight + 1) is None


@pytest.mark.unit
def test_endpoint_answers_429_in_spanish_with_retry_after(monkeypatch):
    monkeypatch.setenv("RADAR_CHAT_PER_CLIENT", "2")
    client = TestClient(app)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    for _ in range(2):
        assert (
            client.post("/api/chat", json={"message": "hola"}, headers=headers).status_code == 200
        )
    resp = client.post("/api/chat", json={"message": "hola"}, headers=headers)
    assert resp.status_code == 429
    assert resp.json()["detail"].startswith("Límite de preguntas alcanzado")
    assert int(resp.headers["Retry-After"]) > 0
    other = {"X-Forwarded-For": "198.51.100.9"}
    assert client.post("/api/chat", json={"message": "hola"}, headers=other).status_code == 200


@pytest.mark.unit
def test_a_spoofed_forwarded_header_does_not_reset_the_limit(monkeypatch):
    monkeypatch.setenv("RADAR_CHAT_PER_CLIENT", "1")
    client = TestClient(app)
    # Cloud Run appends the real client last; whatever the caller sends goes before it.
    first = {"X-Forwarded-For": "1.1.1.1, 203.0.113.7"}
    second = {"X-Forwarded-For": "8.8.8.8, 203.0.113.7"}
    assert client.post("/api/chat", json={"message": "hola"}, headers=first).status_code == 200
    assert client.post("/api/chat", json={"message": "hola"}, headers=second).status_code == 429


@pytest.mark.unit
def test_missing_key_answers_503_without_spending_quota(monkeypatch):
    monkeypatch.setenv("RADAR_CHAT_PER_CLIENT", "1")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    app.state.chat_model = None
    client = TestClient(app)
    for _ in range(3):
        assert client.post("/api/chat", json={"message": "hola"}).status_code == 503
    app.state.chat_model = ScriptedChat()
    assert client.post("/api/chat", json={"message": "hola"}).status_code == 200


@pytest.mark.unit
def test_a_ten_question_demo_with_the_default_limits_is_never_blocked():
    client = TestClient(app)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    codes = [
        client.post("/api/chat", json={"message": f"pregunta {i}"}, headers=headers).status_code
        for i in range(10)
    ]
    assert codes == [200] * 10
