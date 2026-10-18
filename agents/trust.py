"""What the radar's trust rests on, in one place: the backtest headline, the article filter's
quality, and the cost ledgers, with the Spanish sentences that state them.

The chat's trust line (agents/runtime.py) and the UI's trust summary (deploy/evidence.py ->
evidence/trust_summary.json) are both built from these functions, so they say the same thing.
Every number is parsed from reports/ as written; nothing is restated by hand.
"""

import csv
import re
from pathlib import Path
from typing import Any

PUBLISHED = "Radar, with the eligibility gate and the syndication guard (published)"
RAW_GROWTH = "Baseline: raw-count growth"
PERSISTENCE = "Baseline: persistence"
_PCT = r"(\d+(?:\.\d+)?)%"


def backtest_summary(text: str) -> dict[str, Any] | None:
    """The published radar against its baselines, parsed from the primary label's table of
    reports/backtest.md (the first one): precision on labelled slots with its 95% interval, the
    worst and best cases, the base rate, and whether each worst-case advantage holds. None when
    the report has no such table, so no trust line is written from a guess."""
    start = text.find("### Precision@10")
    if start < 0:
        return None
    section = text[start:]
    end = section.find("\n## ")
    section = section if end < 0 else section[:end]

    def row(prefix: str) -> list[str] | None:
        for line in section.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0].startswith(prefix):
                return cells
        return None

    def ranker(prefix: str) -> dict[str, float] | None:
        cells = row(prefix)
        if not cells or len(cells) < 6:
            return None
        prec, ci = re.search(_PCT, cells[2]), re.findall(_PCT, cells[3])
        worst, best = re.search(_PCT, cells[4]), re.search(_PCT, cells[5])
        if not (prec and len(ci) == 2 and worst and best):
            return None
        return {
            "precision_pct": float(prec.group(1)),
            "ic95_pct": [float(ci[0]), float(ci[1])],
            "peor_caso_pct": float(worst.group(1)),
            "mejor_caso_pct": float(best.group(1)),
        }

    def holds(baseline: str) -> bool | None:
        for line in section.splitlines():
            if line.startswith(f"- {PUBLISHED} (worst) minus {baseline}"):
                return "does not hold" not in line
        return None

    published, raw, persistence = ranker(PUBLISHED), ranker(RAW_GROWTH), ranker(PERSISTENCE)
    base = row("Base rate")
    base_pct = re.search(_PCT, base[2]) if base else None
    weeks = re.search(r"Evaluable weeks: (\d+)", text)
    if not (published and raw and persistence and base_pct):
        return None
    return {
        "etiqueta": "el tema sube en páginas vistas de Wikipedia en español y portugués",
        "semanas_evaluadas": int(weeks.group(1)) if weeks else None,
        "radar_publicado": published,
        "tasa_base_pct": float(base_pct.group(1)),
        "crecimiento_de_menciones": raw,
        "persistencia": persistence,
        "supera_crecimiento_en_peor_caso": holds(RAW_GROWTH),
        "supera_persistencia_en_peor_caso": holds(PERSISTENCE),
    }


# BigQuery on-demand compute: first 1 TiB per month free, then USD 6.25 per TiB (checked
# 2026-10-18 at https://cloud.google.com/bigquery/pricing).
BQ_FREE_TIB_PER_MONTH = 1
BQ_USD_PER_TIB = 6.25
BQ_PRICE_SOURCE = "cloud.google.com/bigquery/pricing (on-demand, consultado el 2026-10-18)"
TIB = 2**40


def ledger_costs(reports: Path) -> dict[str, Any]:
    """What the radar has cost: BigQuery bytes billed (measured) with the free tier and the USD it
    implies (estimate), plus Jev's USD from its own ledger (measured)."""
    path = reports / "bq_ledger.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    billed = sum(int(r["billed_bytes"] or 0) for r in rows)
    month = max((r["ts_utc"][:7] for r in rows), default=None)
    month_billed = sum(int(r["billed_bytes"] or 0) for r in rows if r["ts_utc"][:7] == month)
    over_free = max(0.0, month_billed / TIB - BQ_FREE_TIB_PER_MONTH)
    return {
        "bigquery": {
            "medido": "bytes facturados según reports/bq_ledger.csv",
            "jobs": len(rows),
            "billed_gb": round(billed / 1e9, 2),
            "billed_tib": round(billed / TIB, 4),
            "mes": month,
            "billed_tib_mes": round(month_billed / TIB, 4),
            "cuota_gratuita_tib_mes": BQ_FREE_TIB_PER_MONTH,
            "cuota_gratuita_usada": round(month_billed / TIB / BQ_FREE_TIB_PER_MONTH, 4),
            "estimado": "costo en USD calculado con el precio público, no una factura",
            "precio_usd_por_tib": BQ_USD_PER_TIB,
            "fuente_precio": BQ_PRICE_SOURCE,
            "costo_usd_con_cuota_gratuita": round(over_free * BQ_USD_PER_TIB, 2),
            "costo_usd_sin_cuota_gratuita": round(billed / TIB * BQ_USD_PER_TIB, 2),
            "nota": "la cuota gratuita es por cuenta de facturación; si otros proyectos de la cuenta "
            "ya la usaron este mes, el costo real se acerca al de sin cuota",
        },
        "jev": _jev_ledger(reports),
    }


def _jev_ledger(reports: Path) -> dict[str, Any]:
    path = reports / "jev_ledger.csv"
    if not path.exists():
        return {"available": False, "reason": "reports/jev_ledger.csv todavía no existe"}
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {
        "available": True,
        "medido": "suma de cost_usd en reports/jev_ledger.csv",
        "llamadas": len(rows),
        "costo_usd": round(sum(float(r["cost_usd"] or 0) for r in rows), 4),
    }


_GDELT_RULE = "gdelt_ring1_rule"
# The filter that feeds the radar today: the GDELT ring-1 rule in bq_sql/s4_aggregates.sql. The
# trained cascade (pipelines/taxonomy/) is validated but not in the aggregates; a test fails if
# bq_sql starts reading it, so this sentence cannot go stale silently.
FILTER_IN_USE = "regla_gdelt"
_CASCADE = "cascade"
_CELL = r"`(\d\.\d+)` \(`\[(\d\.\d+), (\d\.\d+)\]`"


def filter_summary(text: str) -> dict[str, Any] | None:
    """Precision and recall of the article filter on the 300 gold rows (reports/label_quality.md):
    the GDELT rule and the trained cascade, with their 95% Wilson intervals, against the reference
    named in the table's heading (the teacher panel until human labels land)."""
    heading = re.search(
        r"^### `is_ai` Precision, Recall & F1 on the (\d+) Gold Rows.*$", text, re.M
    )
    if not heading:
        return None

    def row(name: str) -> dict[str, Any] | None:
        line = next((ln for ln in text.splitlines() if ln.startswith(f"| `{name}`")), None)
        cells = re.findall(_CELL, line or "")
        if len(cells) < 2:
            return None
        (p, plo, phi), (r, rlo, rhi) = cells[0], cells[1]
        return {
            "precision": float(p),
            "precision_ic95": [float(plo), float(phi)],
            "exhaustividad": float(r),
            "exhaustividad_ic95": [float(rlo), float(rhi)],
        }

    rule, cascade = row(_GDELT_RULE), row(_CASCADE)
    if not rule:
        return None
    return {
        "n": int(heading.group(1)),
        "regla_gdelt": rule,
        "clasificador": cascade,
        "etiquetas_humanas_pendientes": "Pre-Human-Tally" in heading.group(0),
    }


def _pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def _dec(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def precision_sentence(summary: dict[str, Any], subject: str = "su top 10 publicado") -> str:
    radar = summary["radar_publicado"]
    lo, hi = radar["ic95_pct"]
    return (
        f"{subject} acierta el {_pct(radar['precision_pct'])} de las veces (intervalo "
        f"del 95%: {_pct(lo)} a {_pct(hi)}), frente a un {_pct(summary['tasa_base_pct'])} de un "
        f"tema al azar."
    )


def beats_sentence(summary: dict[str, Any]) -> str:
    raw = summary["crecimiento_de_menciones"]
    beats = {
        "la persistencia (repetir lo que ya subió)": summary["supera_persistencia_en_peor_caso"],
        f"la regla simple de crecimiento de menciones ({_pct(raw['precision_pct'])})": summary[
            "supera_crecimiento_en_peor_caso"
        ],
    }
    yes = [k for k, v in beats.items() if v]
    no = [k for k, v in beats.items() if v is False]
    if yes:
        tail = f"; no supera a {' ni a '.join(no)}." if no else "."
        return f"Supera a {' y a '.join(yes)} incluso en el peor caso{tail}"
    return f"No supera a {' ni a '.join(no)}." if no else ""


HUMAN_LABELS_PENDING = "Las etiquetas humanas del filtro de noticias aún están pendientes."
EARLY_SIGNAL = "Úsalo como señal temprana, no como garantía."


def trust_summary(reports: Path) -> dict[str, Any]:
    """The executive summary of the trust panel: short Spanish points, each marked measured or
    estimate, from the same parsers as the chat's trust line. Missing reports are left out."""
    points: list[dict[str, str]] = []
    sources: list[str] = []
    bt_path, lq_path = reports / "backtest.md", reports / "label_quality.md"
    bt = backtest_summary(bt_path.read_text(encoding="utf-8")) if bt_path.exists() else None
    if bt:
        weeks = f"{bt['semanas_evaluadas']} semanas de " if bt.get("semanas_evaluadas") else ""
        points.append(
            {
                "id": "precision",
                "texto": precision_sentence(bt, "El top 10 publicado del radar")
                + f" Medido en {weeks}backtest; acierto = {bt['etiqueta']}.",
                "kind": "measured",
            }
        )
        points.append({"id": "baselines", "texto": beats_sentence(bt), "kind": "measured"})
        sources.append("reports/backtest.md")
    filt = filter_summary(lq_path.read_text(encoding="utf-8")) if lq_path.exists() else None
    if filt:
        rule, cls = filt["regla_gdelt"], filt["clasificador"]
        ref = "un panel de modelos" if filt["etiquetas_humanas_pendientes"] else "etiquetas humanas"
        text = (
            f"Filtro de noticias de IA, en {filt['n']} noticias revisadas contra {ref}: el radar "
            f"usa hoy la regla de GDELT, con precisión {_dec(rule['precision'])} "
            f"({_dec(rule['precision_ic95'][0])} a {_dec(rule['precision_ic95'][1])}) y "
            f"exhaustividad {_dec(rule['exhaustividad'])} ({_dec(rule['exhaustividad_ic95'][0])} a "
            f"{_dec(rule['exhaustividad_ic95'][1])})"
        )
        if cls:
            # the classifier is validated but not wired into bq_sql's aggregates (FILTER_IN_USE)
            text += (
                f"; el clasificador entrenado (precisión {_dec(cls['precision'])}, exhaustividad "
                f"{_dec(cls['exhaustividad'])}) está validado contra {ref.replace('un ', 'el ', 1)} "
                "pero aún no alimenta el radar"
            )
        points.append({"id": "filtro", "texto": text + ".", "kind": "measured"})
        if filt["etiquetas_humanas_pendientes"]:
            points.append({"id": "etiquetas", "texto": HUMAN_LABELS_PENDING, "kind": "status"})
        sources.append("reports/label_quality.md")
    if (reports / "bq_ledger.csv").exists():
        costs = ledger_costs(reports)
        bq, jev = costs["bigquery"], costs["jev"]
        points.append(
            {
                "id": "bigquery",
                "texto": f"BigQuery: {_dec(bq['billed_gb'])} GB facturados en {bq['jobs']} consultas, "
                f"el {_pct(bq['cuota_gratuita_usada'] * 100)} de la cuota gratuita mensual de "
                f"{bq['cuota_gratuita_tib_mes']} TiB.",
                "kind": "measured",
            }
        )
        points.append(
            {
                "id": "bigquery_usd",
                "texto": f"Costo de BigQuery: {_dec(bq['costo_usd_con_cuota_gratuita'])} USD dentro "
                f"de la cuota gratuita ({_dec(bq['costo_usd_sin_cuota_gratuita'])} USD a precio de "
                f"lista sin ella).",
                "kind": "estimate",
            }
        )
        if jev.get("available"):
            points.append(
                {
                    "id": "jev",
                    "texto": f"Jev: {_dec(jev['costo_usd'], 4)} USD en {jev['llamadas']} llamadas.",
                    "kind": "measured",
                }
            )
        sources += ["reports/bq_ledger.csv", "reports/jev_ledger.csv"]
    if not points:
        return {"available": False, "reason": "no hay informes para resumir"}
    points.append({"id": "senal", "texto": EARLY_SIGNAL, "kind": "rule"})
    return {"available": True, "points": points, "sources": sources}
