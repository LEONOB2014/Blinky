"""Write docs/submission/stories.md: three showcase stories from the latest scored week's top 10.

Every number comes from the agents' tools (agents/tools.py) over the full lake, never copied by
hand, so the file can be regenerated whenever WS4 rescores (the top 10 may change until 06:00).

    RADAR_PROFILE=full uv run python scripts/showcase_stories.py

Rules, all stated in the output:
- Onset of a language: the first week of the last 12 where the topic has >= 5 ring-1 articles in
  that language and >= 3x the median of the earlier weeks (weeks without articles count as 0; days
  flagged is_missing are excluded by the tool). No such week = no onset (said, never invented).
- Concentration: articles co-mentioning the strongest 1-hop neighbour / the topic's articles that
  week. >= 0.9 means one co-mention pattern carries the week (typically syndicated wire copy):
  flagged, and not chosen as a showcase.
- Showcases: the three highest-ranked topics of the week that are not flagged.
No titles, URLs or person names are written (the ring already excludes persons).
"""

import datetime as dt
import statistics
import sys
from typing import Any

from agents import tools
from radar.paths import REPO_ROOT, profile

OUT = REPO_ROOT / "docs" / "submission" / "stories.md"
WEEKS = 12
ONSET_MIN = 5
ONSET_RATIO = 3.0
CONCENTRATION_FLAG = 0.9
RING_K = 8
SHOWCASES = 3


def weekly(topic: str, lang: str) -> dict[str, int]:
    rows = tools.get_topic_series(topic, lang, WEEKS)["rows"]
    return {r["week"]: int(r["articles"] or 0) for r in rows}


def week_labels(last: str, n: int = WEEKS) -> list[str]:
    year, wk = last.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(wk), 1)
    days = [monday - dt.timedelta(weeks=i) for i in range(n - 1, -1, -1)]
    return [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in days]


def onset(series: list[int], labels: list[str]) -> str | None:
    for i, n in enumerate(series):
        before = series[:i] or [0]
        if n >= ONSET_MIN and n >= ONSET_RATIO * max(statistics.median(before), 1):
            return labels[i]
    return None


def weeks_between(a: str, b: str) -> int:
    def monday(label: str) -> dt.date:
        year, wk = label.split("-W")
        return dt.date.fromisocalendar(int(year), int(wk), 1)

    return (monday(b) - monday(a)).days // 7


def diagnose(row: dict[str, Any], week: str) -> dict[str, Any]:
    topic = row["topic_id"]
    labels = week_labels(week)
    by_lang = {lang: weekly(topic, lang) for lang in ("all", "eng", "spa", "por")}
    series = {lang: [s.get(w, 0) for w in labels] for lang, s in by_lang.items()}
    series["es_pt"] = [a + b for a, b in zip(series["spa"], series["por"], strict=True)]
    ring = tools.get_context_1hop(topic, week, RING_K)["rows"]
    articles = series["all"][-1]
    top_n = ring[0]["n"] if ring else 0
    concentration = top_n / articles if articles else None
    return {
        "row": row,
        "labels": labels,
        "series": series,
        "ring": ring,
        "articles": articles,
        "concentration": concentration,
        "flagged": concentration is not None and concentration >= CONCENTRATION_FLAG,
        "onset_en": onset(series["eng"], labels),
        "onset_es_pt": onset(series["es_pt"], labels),
    }


def fmt_pct(x: float | None) -> str:
    return "n/d" if x is None else f"{100 * x:.0f}%"


def window_text(window: dict[str, Any] | None) -> str:
    if not window:
        return "sin dato"
    state = window.get("state")
    lag = window.get("typical_lag_days")
    n = window.get("n_onsets")
    days = window.get("days_left")
    base = f"`{state}`"
    if days is not None:
        base += f", ~{days:g} días restantes (estimación)"
    if lag is not None:
        base += (
            f"; desfase típico inglés→español/portugués {lag:g} días (mediana de {n} pares de "
            "onsets de temas con el mismo subtema principal, medido por WS4)"
        )
    return base


def publish_line(d: dict[str, Any], subtopic_labels: dict[str, str]) -> str:
    row = d["row"]
    angle = row.get("framing_angle") or "sin ángulo"
    sub = subtopic_labels.get(
        row.get("primary_subtopic") or "", row.get("primary_subtopic") or "IA"
    )
    neighbours = [r["neighbor"].split(":", 1)[1] for r in d["ring"][:3]]
    with_ = ", ".join(neighbours) if neighbours else "su contexto"
    return (
        f"Pieza con ángulo «{angle}» sobre {row.get('label_es') or row['topic_id']} dentro de "
        f"«{sub}», explicada por su contexto ({with_}), antes de que el tema llegue al español "
        "(sugerencia editorial, no es una medición)."
    )


def story_md(i: int, d: dict[str, Any], subtopic_labels: dict[str, str]) -> list[str]:
    row = d["row"]
    name = row.get("label_es") or row["topic_id"]
    subs = ", ".join(subtopic_labels.get(s, s) for s in row.get("subtopics") or [])
    none = "sin onset en 12 semanas (sin señal)"
    lines = [
        f"## {i}. {name} (`{row['topic_id']}`), puesto #{row['rank']}",
        "",
        f"- **Etapa y decisión:** {row['stage']}, **{row['decision']}** (prioridad "
        f"{row['priority']:.2f}; emergencia percentil {row['emergence_pct']:.0f}, medido).",
        f"- **Subtemas:** {subs}.",
        f"- **Ventana (chip):** {window_text(row.get('window'))}.",
        f"- **Onset en inglés:** {d['onset_en'] or none}; "
        f"**onset en español/portugués:** {d['onset_es_pt'] or none}"
        + (
            f"; desfase medido {weeks_between(d['onset_en'], d['onset_es_pt'])} semanas."
            if d["onset_en"] and d["onset_es_pt"]
            else "."
        ),
        f"- **Ángulo emocional:** {row.get('framing_angle') or 'sin dato'}"
        + (
            f" (carga emocional percentil {row['emotional_charge_pct']:.0f}, medido)."
            if row.get("emotional_charge_pct") is not None
            else " (carga emocional sin dato esta semana)."
        ),
        f"- **Concentración de la semana:** {fmt_pct(d['concentration'])} de sus {d['articles']} "
        "artículos co-mencionan al vecino más fuerte (medido).",
        "",
        "**Serie semanal (artículos del anillo 1, medido):**",
        "",
        "| Semana | " + " | ".join(w.split("-")[1] for w in d["labels"][-8:]) + " |",
        "|---|" + "---|" * 8,
    ]
    for lang, name in (("all", "Total"), ("eng", "Inglés"), ("es_pt", "Español + portugués")):
        lines.append(f"| {name} | " + " | ".join(str(n) for n in d["series"][lang][-8:]) + " |")
    lines += [
        "",
        f"**Aristas que lo impulsan (anillo de 1 salto, semana {d['labels'][-1]}, medido):**",
        "",
        "| # | Vecino | Co-menciones (n) | NPMI |",
        "|---|---|---|---|",
    ]
    for r in d["ring"][:5]:
        lines.append(f"| {r['rank']} | `{r['neighbor']}` | {r['n']} | {r['npmi']:.3f} |")
    if not d["ring"]:
        lines.append("| | sin anillo esta semana | | |")
    lines += [
        "",
        "**Por qué (del Analista de señales, texto generado por código):**",
        "",
        *[f"- {w}" for w in row.get("why") or []],
        "",
        f"**Qué podría publicar 30X:** {publish_line(d, subtopic_labels)}",
        "",
    ]
    return lines


def main() -> int:
    if profile() != "full":
        raise SystemExit("refusing: set RADAR_PROFILE=full (stories come from the full lake only)")
    top = tools.get_top10()
    if not top.get("available"):
        raise SystemExit("topic_scores_weekly is not available")
    week = top["week"]
    labels_es = tools.labels_es()
    diags = [diagnose(r, week) for r in top["rows"]]
    picks = [d for d in diags if not d["flagged"]][:SHOWCASES]
    fresh = tools.get_freshness()["newest"]

    md = [
        "# Historias de muestra (showcase)",
        "",
        f"Generado por `scripts/showcase_stories.py` el "
        f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M} UTC desde el lake completo "
        f"(`topic_scores_weekly` hasta {fresh.get('topic_scores_weekly')}, `daily_topic` hasta "
        f"{fresh.get('daily_topic')}). Semana puntuada: **{week}**. Todas las cifras salen de las "
        "herramientas de los agentes (`agents/tools.py`); se regenera cada vez que WS4 recalcula.",
        "",
        "Reglas (calculadas por código, no a mano):",
        "",
        f"- **Onset de un idioma:** primera semana de las últimas {WEEKS} con >= {ONSET_MIN} "
        f"artículos del anillo 1 en ese idioma y >= {ONSET_RATIO:g}x la mediana de las semanas "
        "anteriores (las semanas sin artículos cuentan 0; los días `is_missing` quedan fuera). "
        "Si no hay, se dice: "
        "sin señal. Es una regla semanal de presentación; el chip de ventana usa la regla diaria "
        "de WS4 (`models/window.py`: onset = primer día con z_7d > 2).",
        "- **Concentración:** artículos que co-mencionan al vecino más fuerte del anillo / "
        f"artículos del tema esa semana. >= {CONCENTRATION_FLAG:.0%} indica que un solo patrón "
        "de co-mención (típicamente copia sindicada de agencia) sostiene la semana: se marca y no "
        "se elige como historia.",
        f"- **Historias:** los {SHOWCASES} temas mejor puestos de la semana sin esa marca.",
        "",
        "## Diagnóstico del top 10",
        "",
        "| Puesto | Tema | Etapa | Decisión | Artículos semana | Concentración | Onset EN "
        "| Onset ES/PT | Historia |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for d in diags:
        r = d["row"]
        md.append(
            f"| {r['rank']} | `{r['topic_id']}` | {r['stage']} | {r['decision']} "
            f"| {d['articles']} | "
            f"{fmt_pct(d['concentration'])}{' ⚠' if d['flagged'] else ''} | "
            f"{d['onset_en'] or '—'} | {d['onset_es_pt'] or '—'} | "
            f"{'sí' if d in picks else ''} |"
        )
    flagged = [d for d in diags if d["flagged"]]
    with_es = sum(1 for d in diags if d["onset_es_pt"])
    md += [
        "",
        f"Lectura honesta (medido): {len(flagged)} de 10 temas tienen una semana sostenida por un "
        f"solo patrón de co-mención (⚠); {with_es} de 10 muestran onset en español/portugués en "
        f"{WEEKS} semanas. Donde no hay onset en español, la ventana del chip es la estimación del "
        "modelo (desfase típico medido sobre otros temas), no una observación de este tema.",
        "",
    ]
    if len(picks) < SHOWCASES:
        md += [
            f"Solo {len(picks)} temas pasan la regla esta semana; no se completan historias con "
            "temas marcados.",
            "",
        ]
    for i, d in enumerate(picks, start=1):
        md += story_md(i, d, labels_es)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    print(f"{week}: {len(picks)} stories, {len(flagged)} flagged -> {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
