"""OpenAI-compatible chat client for the model named in contracts/agents.yaml (Nebius Token Factory)."""

import os
import time
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Protocol

import httpx
import yaml
from dotenv import load_dotenv

from radar.paths import REPO_ROOT


@cache
def model_config() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "contracts" / "agents.yaml").read_text(encoding="utf-8"))[
        "model"
    ]


@dataclass
class Reply:
    """One assistant message: text and/or tool calls, with what it cost."""

    content: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    tokens: int = 0
    model: str = ""


class ChatModel(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply: ...


class NebiusChat:
    """Calls `<base_url>/chat/completions` with tool definitions; the key comes from `.env`."""

    def __init__(self, temperature: float = 0.2, timeout_s: float = 60.0) -> None:
        load_dotenv(REPO_ROOT / ".env")
        cfg = model_config()
        key = os.environ.get(cfg["auth_env"])
        if not key:
            raise RuntimeError(f"{cfg['auth_env']} is not set (see .env.example)")
        self.model = cfg["name"]
        self.temperature = temperature
        self.client = httpx.Client(
            base_url=cfg["base_url"],
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout_s,
        )

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": 900,
        }
        if tools:
            body["tools"] = tools
        t0 = time.perf_counter()
        resp = self.client.post("/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        return Reply(
            content=msg.get("content"),
            tool_calls=msg.get("tool_calls") or [],
            latency_ms=int((time.perf_counter() - t0) * 1000),
            tokens=int((data.get("usage") or {}).get("total_tokens") or 0),
            model=self.model,
        )
