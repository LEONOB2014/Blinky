# ruff: noqa: E501  (one-off media build script, run by hand from the lake)
"""Critic agent (reasoning): check every sentence of the voiceover against the fact sheet."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nebius import chat

V = Path(__file__).parent
MODEL = "deepseek-ai/DeepSeek-V4-Pro-0813"
script = sys.argv[1] if len(sys.argv) > 1 else "script.json"
s = json.loads((V / "agents" / script).read_text())
facts = (V / "facts.md").read_text()
text = "\n".join(f"{b['id']}: {b['text']}" for b in s)
prompt = f"""Fact-check this Spanish voiceover against the FACT SHEET. List every claim that is not supported by the fact
sheet, overstated, misattributed, or wrong (numbers, names, who pays what, what is built vs planned, comparisons).
Also flag awkward Spanish or terms a LatAm executive would not understand. Be strict and concrete.
Return ONLY JSON: [{{"id": "b02", "quote": "...", "problem": "...", "fix": "Spanish replacement"}}]; [] if none.

VOICEOVER:
{text}

FACT SHEET:
{facts}"""
raw = chat(MODEL, [{"role": "user", "content": prompt}], max_tokens=24000, temperature=0.1)
(V / "agents" / f"check_{script}.txt").write_text(raw)
issues = json.loads(raw[raw.index("[") : raw.rindex("]") + 1])
for i in issues:
    print(f"{i['id']}: «{i['quote']}» -> {i['problem']} | fix: {i['fix']}")
print(len(issues), "issues")
