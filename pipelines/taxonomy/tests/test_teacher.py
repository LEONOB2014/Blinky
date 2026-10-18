"""Unit tests for pipelines/taxonomy/teacher.py (offline, recorded responses via MockTransport)."""

import json

import httpx
import pytest
from pipelines.taxonomy import teacher


@pytest.mark.unit
def test_parse_and_validate_label_cases():
    valid = teacher.parse_and_validate_label(
        '{"is_ai": true, "subtopics": ["agents", "llms_models"], '
        '"brand_safe": true, "confidence": 0.92}'
    )
    assert valid is not None
    assert valid.is_ai is True
    assert valid.subtopics == ["agents", "llms_models"]
    assert valid.brand_safe is True
    assert valid.confidence == 0.92

    # Thinking block + markdown fence should still parse cleanly
    fenced = teacher.parse_and_validate_label(
        "<think>analyzing title</think>\n```json\n"
        '{"is_ai": false, "subtopics": ["agents"], "brand_safe": true, "confidence": 0.88}\n```'
    )
    assert fenced is not None
    assert fenced.is_ai is False
    assert fenced.subtopics == []  # normalized to empty when is_ai is False

    # Unknown subtopic ID must be rejected
    assert (
        teacher.parse_and_validate_label(
            '{"is_ai": true, "subtopics": ["not_a_subtopic"], '
            '"brand_safe": true, "confidence": 0.9}'
        )
        is None
    )
    # Out-of-range confidence must be rejected
    assert (
        teacher.parse_and_validate_label(
            '{"is_ai": true, "subtopics": [], "brand_safe": true, "confidence": 1.5}'
        )
        is None
    )


@pytest.mark.unit
def test_resolve_panel_row_agreement_and_tie_breaker():
    r1 = {
        "valid": True,
        "is_ai": True,
        "subtopics": ["agents", "llms_models"],
        "brand_safe": True,
        "confidence": 0.9,
    }
    r2 = {
        "valid": True,
        "is_ai": True,
        "subtopics": ["agents"],
        "brand_safe": True,
        "confidence": 0.8,
    }
    agreed = teacher.resolve_panel_row("id-1", r1, r2)
    assert agreed["is_ai"] is True
    assert agreed["is_ai_agree"] is True
    assert agreed["tie_broken"] is False
    assert agreed["subtopics"] == ["agents"]

    # Disagreement broken by T3
    r2_disagree = {
        "valid": True,
        "is_ai": False,
        "subtopics": [],
        "brand_safe": True,
        "confidence": 0.7,
    }
    r3_tie = {
        "valid": True,
        "is_ai": True,
        "subtopics": ["agents", "chips_infra"],
        "brand_safe": True,
        "confidence": 0.85,
    }
    broken = teacher.resolve_panel_row("id-2", r1, r2_disagree, r3_tie)
    assert broken["is_ai"] is True
    assert broken["is_ai_agree"] is False
    assert broken["tie_broken"] is True
    assert broken["subtopics"] == ["agents"]


@pytest.mark.unit
def test_call_teacher_one_offline_mock():
    recorded_payload = {
        "id": "chatcmpl-recorded-1",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "is_ai": True,
                            "subtopics": ["chips_infra"],
                            "brand_safe": True,
                            "confidence": 0.95,
                        }
                    ),
                },
            }
        ],
        "usage": {"prompt_tokens": 310, "completion_tokens": 28, "total_tokens": 338},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=recorded_payload)

    client = httpx.Client(
        base_url="https://api.tokenfactory.nebius.com/v1",
        transport=httpx.MockTransport(handler),
    )
    row = {
        "gkg_id": "20260915000000-1",
        "title": "Nvidia expands AI data center GPU supply",
        "url": "https://example.com/tech/nvidia-ai-gpu",
        "top_themes": "WB_133_INFORMATION_AND_COMMUNICATION_TECHNOLOGIES",
        "top_orgs": "nvidia",
        "lang": "eng",
    }
    res = teacher.call_teacher_one(client, "Qwen/Qwen3-235B-A22B-Instruct-2507", row)
    assert res["valid"] is True
    assert res["is_ai"] is True
    assert res["subtopics"] == ["chips_infra"]
    assert res["total_tokens"] == 338
    assert res["cost_usd_est"] > 0
