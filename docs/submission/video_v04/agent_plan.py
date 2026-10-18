# ruff: noqa: E501  (one-off media build script, run by hand from the lake)
"""Planner agent (reasoning): the block structure of the v0.4 video, from the fact sheet and the recorded clips."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nebius import chat

V = Path(__file__).parent
MODEL = "deepseek-ai/DeepSeek-V4-Pro-0813"
facts = (V / "facts.md").read_text()
vision = json.loads((V / "agents" / "vision.json").read_text())
clips = "\n".join(f"- {k} ({v['duration_s']} s): {v['seen']}" for k, v in vision.items())
brief = """Design a 3:30-3:45 demo video in Latin American Spanish for the 30X jury, as a JSON list of blocks.
Requirements from the presenter:
1. Opening (about 15 s): animated avatar (Blinky robot images: calm, shocked, head exploding into AI icons, holding a radar),
   the team name and the presenter "Andrés Leonardo Becerra López, AI Engineer".
2. The problem in 30X's own words, then the key insight: AI topics do not originate on LinkedIn; they travel down an open
   chain (papers/GitHub/HN/X -> news/GDELT -> search and Wikipedia, Spanish later than English -> LinkedIn and Instagram).
   The radar watches the upstream layers and measures how far each topic travelled, so it says what is ABOUT to land.
3. GDELT: what it is, how often it updates, what it gives (tone per article, co-mentions, timing per language), what it
   cost here, and why it is valuable for the project.
4. How the graph with one-hop rings and graph heuristics (NPMI links, PageRank, communities, bridges, novelty, momentum)
   traces the news, the tone and sentiment each topic generates, and turns it into WHAT content 30X should create and from
   WHICH angle (alert, opportunity, debate, twist, explainer) to gain followers.
5. The app in action, using the recorded clips in a sensible order (each clip may be cut or slowed):
"""
rules = """
Rules: use ONLY facts and numbers from the fact sheet; mark nothing as better than it is (the backtest is honest: an early
signal, not a guarantee); no disparaging other teams or products. Explainer blocks without a clip use an animated card
(title + 3-5 short lines that appear one by one, or a chain diagram that lights up step by step).
6. Implementability and cost: deployed, tested (130/130 browser matrix, CI, evals), costs in dollars; then the ask (pilot).
7. Closing (about 15 s): avatar holding the radar, the presenter's name, "AI Engineer", the LinkedIn URL and the app URL.
Return ONLY JSON: [{"id": "b01", "title": "...", "target_s": 15, "visual": {"type": "avatar|card|chain|clip",
"clip": "<clip id or null>", "clip_cut": "how to cut/slow it", "card_lines": ["..."]}, "message": "what the narration must
say, in English, 1-3 sentences", "facts_used": ["exact fact sheet phrases"]}]. 10 to 13 blocks; target_s must sum to 210-225."""
prompt = brief + clips + rules + "\n\nFACT SHEET:\n" + facts
raw = V / "agents" / "plan_raw.txt"
if raw.exists() and "--reuse" in sys.argv:
    txt = raw.read_text()
else:
    txt = chat(MODEL, [{"role": "user", "content": prompt}], max_tokens=24000, temperature=0.3)
    raw.write_text(txt)
s = txt[txt.index("[") : txt.rindex("]") + 1]
plan = json.loads(s)
(V / "agents" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
print(sum(b["target_s"] for b in plan), "s total,", len(plan), "blocks")
for b in plan:
    print(
        f"{b['id']} {b['target_s']:>3}s {b['visual']['type']:<6} {b['visual'].get('clip') or '':<14} {b['title']}"
    )
