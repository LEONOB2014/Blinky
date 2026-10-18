# ruff: noqa: PTH123, RET503, S310, SIM115  (one-off media build script, run by hand from the lake)
"""Minimal Nebius Token Factory client (OpenAI-compatible) that logs token usage per call."""

import base64
import json
import re
import time
import urllib.request
from pathlib import Path

ENV = "/Users/andresbecerra/Documents/30x_Blinky/radar/.env"
LOG = Path(__file__).parent / "agents" / "usage.jsonl"


def _key():
    for line in open(ENV, encoding="utf-8-sig"):
        m = re.match(r"\s*NEBIUS_API_KEY\s*=\s*(\S+)", line)
        if m:
            return m.group(1).strip().strip("\"'")


def chat(model, messages, max_tokens=4000, temperature=0.4):
    body = json.dumps(
        {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    ).encode()
    req = urllib.request.Request(
        "https://api.studio.nebius.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=600))
    u = d.get("usage", {})
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(
            json.dumps(
                {
                    "model": model,
                    "prompt": u.get("prompt_tokens"),
                    "completion": u.get("completion_tokens"),
                    "s": round(time.time() - t0, 1),
                }
            )
            + "\n"
        )
    return d["choices"][0]["message"]["content"]


def image_part(path):
    return {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
        },
    }
