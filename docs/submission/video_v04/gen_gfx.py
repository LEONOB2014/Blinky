# ruff: noqa: E501  (one-off media build script, run by hand from the lake)
"""Generate every graphic of the v0.4 video as HTML, plus the render job list (render.mjs turns them into PNGs).

Cards are rendered once per reveal step (state k shows the first k items), so the edit can reveal them in time
with the narration. Overlays are transparent PNGs laid over the avatar and the app clips.
"""

import json
from pathlib import Path

V = Path(__file__).parent
H, P = V / "gfx" / "html", V / "gfx" / "png"
AV = Path("/Users/andresbecerra/Documents/30x_Blinky/radar/lake/submission/video/avatar")
H.mkdir(parents=True, exist_ok=True)
P.mkdir(parents=True, exist_ok=True)
jobs = []

BASE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0F152B;--panel:#151D3B;--line:#26305A;--ink:#F1F5F9;--muted:#9AA6C2;--amber:#F59E0B;--violet:#8B5CF6;--cyan:#22D3EE;--green:#34D399;--red:#F87171}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:WIDTHpx;height:HEIGHTpx;overflow:hidden;font-family:'DM Sans',Arial,sans-serif;color:var(--ink);BODYBG}
h1,h2,.h{font-family:'Space Grotesk',Arial,sans-serif}
.kicker{font-size:26px;letter-spacing:4px;color:var(--amber);font-weight:700;text-transform:uppercase}
.glow{position:absolute;border-radius:50%;filter:blur(90px);opacity:.35}
STYLE
</style></head><body>BODY</body></html>"""


def page(name, body, style="", w=1920, h=1080, transparent=False):
    bg = "background:transparent" if transparent else "background:var(--bg)"
    html = (
        BASE.replace("WIDTH", str(w))
        .replace("HEIGHT", str(h))
        .replace("BODYBG", bg)
        .replace("STYLE", style)
        .replace("BODY", body)
    )
    f = H / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    jobs.append(
        {"html": str(f), "png": str(P / f"{name}.png"), "w": w, "h": h, "transparent": transparent}
    )


# ---------- intro overlays (over the avatar, which sits on the left third) ----------
OV = """.ov{position:absolute;right:90px;top:0;bottom:0;width:860px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;gap:22px}
.big{font-size:84px;line-height:1.02;font-weight:700}
.sub{font-size:36px;color:var(--muted);line-height:1.3}
.pill{display:inline-block;padding:10px 22px;border-radius:999px;border:2px solid var(--amber);color:var(--amber);font-weight:700;font-size:28px;letter-spacing:2px}
.lower{position:absolute;left:120px;bottom:84px;display:flex;align-items:center;gap:22px;background:rgba(15,21,43,.82);border:1px solid var(--line);border-left:6px solid var(--amber);padding:20px 30px;border-radius:14px}
.lower .n{font-size:40px;font-weight:700}.lower .r{font-size:28px;color:var(--cyan);font-weight:500}"""
page(
    "intro_0",
    '<div class="lower"><div><div class="n h">Andrés Leonardo Becerra López</div><div class="r">AI Engineer · Equipo Blinky</div></div></div>',
    OV,
    transparent=True,
)
page(
    "intro_1",
    '<div class="ov"><span class="pill">EQUIPO BLINKY</span><div class="big h">Veníamos por la<br><span style="color:var(--amber)">Blinka Task</span>…</div></div>',
    OV,
    transparent=True,
)
page(
    "intro_2",
    '<div class="ov"><span class="pill">RETO 30X</span><div class="big h">…y el reto fue<br><span style="color:var(--cyan)">Radar de Contenido</span></div></div>',
    OV,
    transparent=True,
)
page(
    "intro_3",
    '<div class="ov"><div class="big h">¿No te lo<br><span style="color:var(--violet)">esperabas?</span></div><div class="sub">Nosotros tampoco.</div></div>',
    OV,
    transparent=True,
)
page(
    "intro_4",
    '<div class="ov"><span class="pill">EQUIPO BLINKY · RETO 30X</span><div class="big h">Radar de<br>Señal Temprana</div>'
    '<div class="sub">Qué tema de IA está por llegar a LinkedIn,<br>por qué y desde qué ángulo contarlo.</div></div>'
    '<div class="lower"><div><div class="n h">Andrés Leonardo Becerra López</div><div class="r">AI Engineer</div></div></div>',
    OV,
    transparent=True,
)

# ---------- the upstream chain (b02) ----------
CH = """.wrap{position:absolute;inset:0;padding:90px 110px;display:flex;flex-direction:column;gap:46px}
.title{font-size:58px;font-weight:700;line-height:1.1}
.prob{font-size:32px;color:var(--muted)}
.prob b{color:var(--red)}
.chain{display:flex;align-items:stretch;gap:26px;margin-top:10px}
.st{flex:1;min-height:300px;background:var(--panel);border:2px solid var(--line);border-radius:22px;padding:28px 26px;opacity:.28;transition:none;position:relative}
.st.on{opacity:1;border-color:var(--c);box-shadow:0 0 44px -6px var(--c)}
.st .k{font-size:22px;letter-spacing:3px;color:var(--c);font-weight:700}
.st .t{font-size:40px;font-weight:700;margin-top:12px}
.st .d{font-size:27px;color:var(--muted);margin-top:14px;line-height:1.4}
.arrow{align-self:center;font-size:44px;color:var(--muted)}
.radar{position:absolute;left:110px;right:110px;bottom:90px;display:flex;align-items:center;gap:24px;font-size:34px;opacity:0}
.radar.on{opacity:1}.radar .tag{background:var(--amber);color:#111827;font-weight:700;padding:12px 22px;border-radius:12px}
.brace{position:absolute;left:110px;width:1290px;top:742px;height:22px;border:3px solid var(--amber);border-top:none;border-radius:0 0 14px 14px;opacity:0}
.brace.on{opacity:1}"""
stages = [
    ("1 · ARRIBA", "Papers y código", "arXiv · Hugging Face · GitHub · Hacker News · X", "#8B5CF6"),
    ("2 · NOTICIAS", "GDELT", "noticias globales, 65 idiomas, tono por artículo", "#22D3EE"),
    (
        "3 · ATENCIÓN",
        "Búsqueda y referencia",
        "Google Trends · Wikipedia — inglés primero, español después",
        "#34D399",
    ),
    ("4 · AL FINAL", "LinkedIn e Instagram", "carruseles y reels para ejecutivos", "#F59E0B"),
]
for k in range(0, 6):
    cells = []
    for i, (kk, t, d, c) in enumerate(stages):
        on = " on" if k >= i + 1 else ""
        cells.append(
            f'<div class="st{on}" style="--c:{c}"><div class="k">{kk}</div><div class="t h">{t}</div><div class="d">{d}</div></div>'
        )
        if i < 3:
            cells.append('<div class="arrow">→</div>')
    radar_on = " on" if k >= 5 else ""
    body = (
        '<div class="glow" style="width:700px;height:500px;background:#8B5CF6;left:-200px;top:-180px"></div>'
        '<div class="wrap"><div class="kicker">La idea</div><div class="title h">Los temas de IA no nacen en LinkedIn:<br>viajan por una cadena abierta.</div>'
        '<div class="prob">Hoy: <b>scraping pagado — miles de dólares al año</b>, y responde solo la mitad.</div>'
        f'<div class="chain">{"".join(cells)}</div></div>'
        f'<div class="radar{radar_on}"><span class="tag">EL RADAR MIRA AQUÍ</span>'
        '<span>mide cuánto ha viajado cada tema → <b style="color:var(--amber)">lo que está por llegar</b>, no lo que ya llegó · LinkedIn nunca se scrapea</span></div>'
    )
    page(f"chain_{k}", body, CH)

# ---------- generic card with lines revealed one by one ----------
CARD = """.wrap{position:absolute;inset:0;padding:100px 120px;display:flex;flex-direction:column;gap:34px}
.title{font-size:66px;font-weight:700;line-height:1.08}
.lines{display:flex;flex-direction:column;gap:22px;margin-top:8px}
.ln{display:flex;gap:26px;align-items:baseline;background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--c);border-radius:16px;padding:22px 30px;font-size:34px;opacity:.12}
.ln.on{opacity:1}.ln .n{font-family:'Space Grotesk';font-weight:700;color:var(--c);min-width:260px;font-size:40px}
.src{position:absolute;left:120px;bottom:44px;font-size:20px;color:var(--muted)}"""


def card(name, kicker, title, lines, src, glow="#22D3EE"):
    for k in range(len(lines) + 1):
        items = "".join(
            f'<div class="ln{" on" if i < k else ""}" style="--c:{c}"><span class="n">{n}</span><span>{t}</span></div>'
            for i, (n, t, c) in enumerate(lines)
        )
        body = (
            f'<div class="glow" style="width:760px;height:520px;background:{glow};right:-220px;top:-200px"></div>'
            f'<div class="wrap"><div class="kicker">{kicker}</div><div class="title h">{title}</div><div class="lines">{items}</div></div>'
            f'<div class="src">{src}</div>'
        )
        page(f"{name}_{k}", body, CARD)


card(
    "gdelt",
    "Los datos",
    "GDELT: las noticias del mundo, abiertas",
    [
        (
            "Por artículo",
            "personas, organizaciones, lugares, temas y el <b>tono</b> de la noticia",
            "#8B5CF6",
        ),
        (
            "Cada 15 min",
            "se actualiza; noticias de prensa, radio, TV y web en 65 idiomas",
            "#22D3EE",
        ),
        (
            "4.031.651",
            "artículos de IA clasificados en 51 semanas · 1.623.903 en el anillo de IA",
            "#F59E0B",
        ),
        (
            "0 USD",
            "en BigQuery: 389,7 GB dentro del nivel gratuito (≈ 2,2 USD a precio de lista)",
            "#34D399",
        ),
        (
            "Su valor",
            "tono · qué temas aparecen juntos · cuándo explota en inglés y aún no llega al español",
            "#F87171",
        ),
    ],
    "Fuente: documentación de GDELT 2.0 (actualización y cobertura); cifras del proyecto medidas (status/WS1.md, reports/bq_ledger.csv)",
)
card(
    "eng",
    "Listo para implementarse",
    "Desplegado, probado y medido",
    [
        (
            "Cloud Run",
            "+ Netlify · pruebas (CI) en cada cambio · secretos en Secret Manager",
            "#22D3EE",
        ),
        (
            "130 / 130",
            "verificaciones del navegador: 10 lentes × 13 semanas, sin errores",
            "#34D399",
        ),
        (
            "LangSmith",
            "trazas de cada respuesta · fidelidad del chat 0,964 (28 preguntas × 3)",
            "#8B5CF6",
        ),
        (
            "≈ 13 USD/mes",
            "de servidor (estimado) · 0,001 USD por respuesta · BigQuery: 0 USD",
            "#F59E0B",
        ),
    ],
    "Medido: e2e matrix (status/WS3.md), eval de agentes (status/WS0-agents.md), ledger de BigQuery. Estimados: README, costos de Cloud Run y Nebius.",
    glow="#34D399",
)

# ---------- caption chips over the app clips ----------
CAP = """.cap{position:absolute;left:56px;bottom:56px;display:flex;flex-direction:column;gap:8px;background:rgba(15,21,43,.9);border:1px solid #2B3566;border-left:6px solid var(--c);border-radius:16px;padding:18px 28px;max-width:1100px;box-shadow:0 18px 50px rgba(0,0,0,.45)}
.cap .k{font-size:22px;letter-spacing:3px;font-weight:700;color:var(--c)}
.cap .t{font-size:36px;font-weight:700;line-height:1.15}"""
caps = {
    "cap_despegando": (
        "DESPEGANDO",
        "Top 10: los temas de IA que suben más rápido que su propia historia",
        "#F59E0B",
    ),
    "cap_ring": (
        "UN CLIC · LENTE HISTORIA",
        "La ficha y el anillo de un salto: vecinos más fuertes y artículos que lo respaldan",
        "#8B5CF6",
    ),
    "cap_leaders": (
        "LO MÁS GRANDE · W42",
        "Nvidia 4.718 · OpenAI 2.691 · Microsoft IA 2.153 artículos",
        "#22D3EE",
    ),
    "cap_graph": (
        "EL GRAFO · 13 SEMANAS",
        "105 temas · co-menciones con NPMI · tamaño = PageRank · 7 comunidades (Leiden)",
        "#34D399",
    ),
    "cap_lenses": (
        "DEL TONO AL ÁNGULO",
        "Emoción · Postura · Momento · Puente · Novedad → alerta, oportunidad, debate, giro o explicador",
        "#F87171",
    ),
    "cap_chat": (
        "MAESTRO DE MEDIOS · 8 AGENTES",
        "El código escribe los hechos, el modelo los explica, un auditor revisa cada número",
        "#8B5CF6",
    ),
    "cap_trust": (
        "CONFIANZA",
        "Señal temprana, no garantía: el backtest lo dice con honestidad",
        "#F59E0B",
    ),
}
for name, (k, t, c) in caps.items():
    page(
        name,
        f'<div class="cap" style="--c:{c}"><div class="k">{k}</div><div class="t h">{t}</div></div>',
        CAP,
        transparent=True,
    )

# ---------- closing overlay ----------
CL = """.ov{position:absolute;right:80px;top:0;bottom:0;width:860px;display:flex;flex-direction:column;justify-content:center;gap:26px}
.ask{background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--amber);border-radius:18px;padding:26px 32px;font-size:32px;line-height:1.35}
.ask b{color:var(--amber)}
.name{font-size:62px;font-weight:700;line-height:1.05}.role{font-size:34px;color:var(--cyan);font-weight:500}
.links{display:flex;flex-direction:column;gap:12px;font-size:26px;white-space:nowrap}
.links span{color:var(--muted)}.links b{color:var(--ink);font-weight:500}"""
for k, show in enumerate((("ask",), ("ask", "who"))):
    who = (
        (
            '<div><div class="name h">Andrés Leonardo<br>Becerra López</div><div class="role">AI Engineer · Equipo Blinky</div></div>'
            '<div class="links"><div><span>LinkedIn</span>&nbsp; <b>linkedin.com/in/andres-leonardo-becerra-lopez-01a01995</b></div>'
            "<div><span>App</span>&nbsp; <b>radar-senal-temprana.netlify.app</b></div></div>"
        )
        if "who" in show
        else ""
    )
    page(
        f"closing_{k}",
        '<div class="ov"><div class="kicker">La propuesta</div>'
        '<div class="ask">Un <b>piloto de 4 semanas</b> con el equipo de medios de 30X: ustedes leen el radar cada semana y comparten la analítica de sus publicaciones; el radar aprende qué le funciona a su audiencia.</div>'
        f"{who}</div>",
        CL,
        transparent=True,
    )

# ---------- thumbnail (1280x720) ----------
TH = """.av{position:absolute;left:-150px;top:60px;width:1000px;height:auto;-webkit-mask-image:radial-gradient(ellipse 34% 62% at 33% 50%,#000 55%,transparent 100%);mask-image:radial-gradient(ellipse 34% 62% at 33% 50%,#000 55%,transparent 100%)}
.right{position:absolute;right:56px;top:52px;width:700px;display:flex;flex-direction:column;gap:18px}
.k2{font-size:20px;letter-spacing:4px;color:var(--amber);font-weight:700}
.t1{font-size:78px;font-weight:700;line-height:.98}
.t1 em{font-style:normal;background:linear-gradient(90deg,#F59E0B,#F87171);-webkit-background-clip:text;color:transparent}
.t2{font-size:28px;color:#C9D3EA;line-height:1.25}
.chips{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:6px}
.chip{background:rgba(21,29,59,.92);border:1px solid #2B3566;border-radius:14px;padding:12px 16px}
.chip .v{font-family:'Space Grotesk';font-weight:700;font-size:32px;color:var(--c)}.chip .l{font-size:17px;color:var(--muted)}
.who{position:absolute;left:44px;bottom:36px;display:flex;align-items:center;gap:16px;background:rgba(15,21,43,.88);border:1px solid #2B3566;border-left:6px solid var(--cyan);border-radius:14px;padding:14px 22px}
.who .n{font-size:28px;font-weight:700}.who .r{font-size:19px;color:var(--cyan)}
.badge{position:absolute;right:56px;bottom:40px;font-size:20px;color:var(--muted)}"""
page(
    "thumbnail",
    '<div class="glow" style="width:620px;height:520px;background:#8B5CF6;left:40px;top:60px;opacity:.45"></div>'
    '<div class="glow" style="width:520px;height:420px;background:#F59E0B;right:60px;top:-120px;opacity:.25"></div>'
    f'<img class="av" src="file://{AV}/f4_blinky_radar.png">'
    '<div class="right"><div class="k2">EQUIPO BLINKY · RETO 30X</div>'
    '<div class="t1 h">Radar de<br><em>Señal Temprana</em></div>'
    '<div class="t2">Qué tema de IA está por llegar a LinkedIn, por qué y desde qué ángulo contarlo.</div>'
    '<div class="chips">'
    '<div class="chip" style="--c:#22D3EE"><div class="v">4 M+</div><div class="l">noticias GDELT analizadas</div></div>'
    '<div class="chip" style="--c:#8B5CF6"><div class="v">110</div><div class="l">temas de IA, 11 familias</div></div>'
    '<div class="chip" style="--c:#34D399"><div class="v">0 USD</div><div class="l">BigQuery, nivel gratuito</div></div>'
    '<div class="chip" style="--c:#F59E0B"><div class="v">130/130</div><div class="l">pruebas del grafo en vivo</div></div>'
    "</div></div>"
    '<div class="who"><div><div class="n h">Andrés Leonardo Becerra López</div><div class="r">AI Engineer</div></div></div>',
    TH,
    w=1280,
    h=720,
)

(V / "gfx" / "jobs.json").write_text(json.dumps(jobs, indent=1))
print(len(jobs), "graphics")
