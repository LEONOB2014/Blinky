"""Offline unit tests for pipelines/taxonomy/cascade.py (recorded Jev responses & spend guard)."""

from pathlib import Path

import httpx
import polars as pl
import pytest

pytest.importorskip("numpy")  # the models extra; CI installs no extras

from pipelines.taxonomy import cascade  # noqa: E402


@pytest.mark.unit
def test_call_jev_offline_and_cache_and_cap_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JEV_MODEL", "typesafe/jev-1.14")
    monkeypatch.setenv("JEV_RUN_CAP_USD", "1.00")
    monkeypatch.setenv("JEV_DEV_CAP_USD", "3.00")
    cascade._RUN_SPEND_USD = 0.0

    recorded_jev_response = {
        "model": "typesafe/jev-1.14-20261017",
        "answers": {
            "is_ai": {"type": "noul", "noul": 0.94},
            "brand_safe": {"type": "noul", "noul": 0.99},
            "main_subtopic": {
                "type": "choice",
                "choice": "agents",
                "probabilities": {"agents": 0.82, "llms_models": 0.30, "chips_infra": 0.02},
            },
        },
        "usage": {"input_tokens": 622, "output_tokens": 0, "cost": 0.000026},
    }

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=recorded_jev_response)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cache_file = tmp_path / "jev_cache.jsonl"
    ledger_file = tmp_path / "jev_ledger.csv"

    article = {
        "gkg_id": "row-101",
        "title": "Enterprise AI agents automate customer support",
        "url": "https://example.com/ai-agents",
        "top_themes": "WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES",
        "top_orgs": "openai",
        "lang": "eng",
    }

    res1 = cascade.call_jev(article, client=client, cache_path=cache_file, ledger_path=ledger_file)
    assert res1["is_ai"] is True
    assert res1["is_ai_prob"] == 0.94
    assert res1["main_subtopic"] == "agents"
    assert "agents" in res1["subtopics"]
    assert res1["cached"] is False
    assert calls["n"] == 1
    assert cascade.cumulative_jev_spend_usd(ledger_file) == pytest.approx(0.000026)

    # Second call with identical (model, state, questions) must hit cache (0 new HTTP calls)
    res2 = cascade.call_jev(article, client=client, cache_path=cache_file, ledger_path=ledger_file)
    assert res2["cached"] is True
    assert res2["cost_usd"] == 0.0
    assert calls["n"] == 1

    # Lowering JEV_RUN_CAP_USD below current run spend must abort before calling
    monkeypatch.setenv("JEV_RUN_CAP_USD", "0.00001")
    article2 = dict(article, gkg_id="row-102", title="Another distinct article title")
    with pytest.raises(cascade.JevCapExceededError):
        cascade.call_jev(article2, client=client, cache_path=cache_file, ledger_path=ledger_file)
    assert calls["n"] == 1


@pytest.mark.unit
def test_evaluate_bins_and_classify_routing():
    val_df = pl.DataFrame(
        [
            {
                "gkg_id": f"v-{i}",
                "is_ai": i % 2 == 0,
                "student_is_ai_prob": 0.92 if i % 2 == 0 else 0.08,
            }
            for i in range(40)
        ]
    )
    jev_map = {
        f"v-{i}": {
            "is_ai_prob": 0.90 if i % 2 == 0 else 0.10,
            "is_ai": i % 2 == 0,
            "cost_usd": 0.000026,
        }
        for i in range(40)
    }
    summary = cascade.evaluate_bins_and_thresholds(val_df, jev_map)
    assert summary["val_n"] == 40
    # Student is 100% accurate and Jev does not beat it -> routed_bins is empty ([0.5, 0.5])
    assert summary["routed_bins"] == []
    assert summary["selected_thresholds"]["t_low"] == 0.5
    assert summary["selected_thresholds"]["t_high"] == 0.5
