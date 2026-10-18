# ruff: noqa: B905, E501  (one-off media build script, run by hand from the lake)
"""Writer agent (content creator): the Spanish voiceover per block, to a word budget, facts only."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nebius import chat

V = Path(__file__).parent
MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
plan = json.loads((V / "agents" / "plan_final.json").read_text())
facts = (V / "facts.md").read_text()
blocks = "\n".join(
    f"{b['id']} ({b['s']} s, about {round(b['s'] * 2.3)} words; on screen: {b['visual']}): {b['message']}"
    for b in plan
)
prompt = f"""You are a senior content creator writing the voiceover of a hackathon demo video for executives at 30X, a LatAm
AI-education company. Voice: a warm, confident Latin American Spanish narrator (ElevenLabs). Write natural spoken Spanish
(Latinoamérica, tuteo neutral), short sentences, concrete, energetic but never hype; no English except proper names
(GDELT, LinkedIn, Instagram, PageRank, NPMI, Leiden, Cloud Run, Netlify, LangSmith, BigQuery, Hugging Face, GitHub,
Hacker News). Write numbers the way they should be SPOKEN (e.g. "cuatro millones de artículos", "quince minutos",
"cero coma noventa y seis" or "noventa y seis por ciento"). Keep every block within its word budget (±10%).
Use ONLY facts from the fact sheet; never invent numbers, names, clients or returns. The presenter is
"Andrés Leonardo Becerra López, ingeniero de IA" (say it in b01 and b11). In b11, say the LinkedIn and the app are on screen
(do not read URLs aloud).
Return ONLY JSON: [{{"id": "b01", "text": "..."}}, ...] for all blocks in order.

BLOCKS:
{blocks}

FACT SHEET:
{facts}"""
raw = chat(MODEL, [{"role": "user", "content": prompt}], max_tokens=6000, temperature=0.6)
(V / "agents" / "script_raw.txt").write_text(raw)
s = raw[raw.index("[") : raw.rindex("]") + 1]
script = json.loads(s)
(V / "agents" / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
for b, p in zip(script, plan):
    n = len(b["text"].split())
    print(f"{b['id']} {n:>3} words (budget {round(p['s'] * 2.3)}): {b['text']}\n")
