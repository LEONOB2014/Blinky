"""The Spanish adaptation brief of each top-10 topic, written ahead of time by the Editor agent.

Code gathers the data with the agents' tools and turns it into plain Spanish values (no internal ids);
the Editor (the agents' model) writes six text fields as JSON; the deterministic Auditor then checks
that every number in the text is one of the numbers passed and that no decision other than the
code's appears. A failing brief is retried once with the Auditor's complaint; the second result is
kept even if it still fails (flagged with auditor_ok = false). Output:
`lake/gold/topic_briefs_weekly.parquet`, validated against contracts/topic_briefs_weekly.schema.json.

    RADAR_PROFILE=full uv run python -m agents.briefs --weeks 2
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from agents import tools
from agents.llm import ChatModel, NebiusChat
from agents.runtime import DECISION_ES, NO_NARRATIVE, PLAIN, topic_name, untraced_numbers
from agents.tools import gold
from radar.contracts import validate_records
from radar.paths import profile

FIELDS = ("headline_es", "what_happened_es", "why_latam_es", "angle_es", "hook_es", "format_es")
MAX_LEN = {"headline_es": 110, "hook_es": 220}
WINDOW_ES = {
    "dias_restantes": "faltan unos {days} días para que llegue al español (estimación)",
    "en_cualquier_momento": "puede llegar al español en cualquier momento (estimación)",
    "ya_en_espanol": "ya se está contando en español o portugués",
    "sin_estimacion": "todavía no hay estimación de cuándo llega al español",
}
SYSTEM = (
    "Eres el Editor del radar de 30X. Escribes un brief de adaptación en español para un editor que "
    "publica para ejecutivos de LatAm en LinkedIn. "
    + PLAIN
    + " Reglas: usa SOLO los datos que te doy; copia cada número tal cual aparece (no calcules "
    "números nuevos, no conviertas, no inventes); no prometas que algo 'se hará viral' ni exageres; "
    "no nombres personas; la decisión del radar es la que te doy y no propongas otra. "
    "No predigas alcance ni impacto ('estará en todos los medios', 'impactará', 'llegará pronto'): "
    "di solo lo que los datos muestran. La ventana es una estimación del radar: escríbela como tal "
    "('según la estimación del radar, faltan unos N días'), nunca como un hecho. "
    + NO_NARRATIVE
    + " "
    "Responde SOLO con un objeto JSON con estas claves, todas en español: "
    '"headline_es" (título de trabajo, máximo 100 caracteres), '
    '"what_happened_es" (2-3 frases: qué muestran los datos esta semana), '
    '"why_latam_es" (por qué importa a ejecutivos de LatAm, sin inventar datos de LatAm), '
    '"angle_es" (cómo contarlo, desde el ángulo dado), '
    '"hook_es" (frase de apertura para LinkedIn, máximo 200 caracteres), '
    '"format_es" (formato sugerido: carrusel, video corto, post de texto o newsletter, y por qué).'
)
_THEME_PREFIX = re.compile(r"^(?:[A-Z]+_)?(?:\d+_)?")
_RAW_IDS = re.compile(r"\b(?:org|thm|per):|\b[A-Z]{2,}_[A-Z_0-9]{3,}\b")
_VIRAL = re.compile(r"viral", re.I)
# claims beyond the data (measured on the first run: "En 12 días ... estará en todos los medios")
_OVERCLAIM = re.compile(
    r"todos los medios|en todas partes|impactar[áa]|llegar[áa] pronto|est[áa] conectad[oa]|"
    r"explot|boom|revolucion",
    re.I,
)
_DECISIONS_TEXT = {v.lower(): k for k, v in DECISION_ES.items()}

# Coverage claims checked against the brief's own es+pt count (claude-work's review, 2026-10-18:
# DeepMind "aún no llega al español" next to 18 es/pt articles; ChatGPT "casi nadie lo cuenta en
# español" with 152). A claim is a phrase within one sentence that names Spanish, Portuguese or
# LatAm. Hand-set thresholds (estimate): an absolute claim needs 0 es+pt articles that week; a
# "casi nadie" claim needs es+pt under NEAR_NONE_SHARE of the English + es+pt articles.
_LANG_WORDS = re.compile(r"español|espanol|portugu[eé]s|latam|latinoam[eé]rica|hispan", re.I)
_ABSENT = re.compile(
    r"(?<!casi )\bnadie\b|no llega|"
    r"a[uú]n no (?:llega|ha llegado|(?:se cuenta|se habla|hay|aparece)(?! mucho))|"
    r"no hay (?:cobertura|art[ií]culos|notas)|sin cobertura|ninguna cobertura|cero art[ií]culos",
    re.I,
)
_NEAR_ABSENT = re.compile(
    r"casi nadie|casi no|muy poca cobertura|poca cobertura|apenas (?:se cuenta|se habla|aparece)|"
    r"no se (?:cuenta|habla) mucho|"
    r"escasa cobertura",
    re.I,
)
NEAR_NONE_SHARE = 0.10
_SENTENCES = re.compile(r"(?<=[.!?])\s+")


def coverage_line(data: "TopicData") -> str:
    """The code-written coverage sentence that replaces a contradicted claim."""
    es, en = (
        data.facts["articulos_en_espanol_y_portugues_por_semana"][-1],
        data.facts["articulos_en_ingles_por_semana"][-1],
    )
    return f"Esta semana hubo {es} artículos en español y portugués, frente a {en} en inglés."


def _headline_coverage(data: "TopicData") -> str:
    """A headline keeps the topic's name: "ChatGPT: 152 artículos en español y portugués"."""
    es = data.facts["articulos_en_espanol_y_portugues_por_semana"][-1]
    name = topic_name(data.row) if getattr(data, "row", None) else "El tema"
    return f"{name}: {es} artículos en español y portugués esta semana"


def coverage_contradictions(fields: dict[str, str], data: "TopicData") -> list[str]:
    """Sentences whose Spanish/Portuguese coverage claim disagrees with the brief's own count
    (none when the brief's data has no weekly language counts)."""
    es_weeks = data.facts.get("articulos_en_espanol_y_portugues_por_semana")
    en_weeks = data.facts.get("articulos_en_ingles_por_semana")
    if not es_weeks or not en_weeks:
        return []
    es, en = es_weeks[-1], en_weeks[-1]
    share = es / (es + en) if (es + en) else 0.0
    bad = []
    for text in fields.values():
        for sentence in _SENTENCES.split(text):
            if not _LANG_WORDS.search(sentence):
                continue
            if (_ABSENT.search(sentence) and es > 0) or (
                _NEAR_ABSENT.search(sentence) and share >= NEAR_NONE_SHARE
            ):
                bad.append(sentence.strip())
    return bad


def fix_coverage(fields: dict[str, str], data: "TopicData") -> dict[str, str]:
    """Replace each contradicted sentence with the code-written coverage line (once per field)."""
    bad = set(coverage_contradictions(fields, data))
    out = {}
    for name, text in fields.items():
        parts, used = [], False
        for sentence in _SENTENCES.split(text):
            if sentence.strip() in bad:
                if not used:
                    parts.append(
                        _headline_coverage(data) if name == "headline_es" else coverage_line(data)
                    )
                    used = True
                continue
            parts.append(sentence)
        out[name] = " ".join(parts)
    return out


def humanize(entity: str) -> str:
    """'thm:WB_1649_UNEMPLOYMENT_BENEFITS' -> 'unemployment benefits'; 'org:kroger' -> 'kroger'."""
    kind, _, name = entity.partition(":")
    if kind == "thm":
        name = _THEME_PREFIX.sub("", name).replace("_", " ").lower()
    return name


@dataclass
class Cited:
    name: str
    value: float
    kind: str
    source: str


@dataclass
class TopicData:
    row: dict[str, Any]
    week: str
    facts: dict[str, Any]  # plain Spanish keys -> values, what the model sees
    numbers: list[Cited] = field(default_factory=list)


def _calendar_weeks(week: str, n: int = 4) -> list[str]:
    """The n ISO weeks ending at `week`, oldest first."""
    year, wk = week.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(wk), 1)
    days = [monday - dt.timedelta(weeks=k) for k in range(n - 1, -1, -1)]
    return [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in days]


def _weekly(topic: str, langs: tuple[str, ...], week: str, n: int = 4) -> list[int]:
    """Articles per calendar week up to `week` (a week with no article row is a real 0)."""
    totals: dict[str, int] = {}
    for lang in langs:
        for r in tools.get_topic_series(topic, lang, 12)["rows"]:
            totals[r["week"]] = totals.get(r["week"], 0) + int(r["articles"] or 0)
    return [totals.get(w, 0) for w in _calendar_weeks(week, n)]


def _sources(topic: str, week: str) -> tuple[int, int] | None:
    path = gold("topic_sources_weekly")
    if not path.exists():
        return None
    year, wk = week.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(wk), 1)
    row = (
        pl.scan_parquet(path)
        .filter((pl.col("topic_id") == topic) & (pl.col("week") == monday))
        .select("n_articles", "n_sources")
        .collect()
    )
    return (int(row["n_articles"][0]), int(row["n_sources"][0])) if row.height else None


def gather(row: dict[str, Any], week: str) -> TopicData:
    """Every value the Editor may use, in plain Spanish, plus the numbers it may cite."""
    topic = row["topic_id"]
    labels = tools.labels_es()
    window = row.get("window") or {}
    days = window.get("days_left")
    facts: dict[str, Any] = {
        "tema": topic_name(row),
        "semana": week,
        "decision_del_radar": DECISION_ES[row["decision"]],
        "etapa": row.get("stage"),
        "angulo": row.get("framing_angle"),
        "subtemas": [labels.get(s, s) for s in row.get("subtopics") or []],
        "ventana": WINDOW_ES.get(window.get("state"), "sin dato").format(
            days=int(days) if days is not None else "?"
        ),
    }
    data = TopicData(row, week, facts)

    def cite(key: str, value: float | None, kind: str, source: str) -> None:
        if value is None:
            return
        value = round(float(value))
        facts[key] = value
        data.numbers.append(Cited(key, value, kind, source))

    cite("emergencia_percentil", row.get("emergence_pct"), "measured", "topic_scores_weekly")
    if row.get("saturation") is not None:
        cite("saturacion_pct", 100 * row["saturation"], "measured", "topic_scores_weekly")
    if row.get("audience_fit") is not None:
        cite("encaje_latam_pct", 100 * row["audience_fit"], "estimate", "topic_scores_weekly")
    cite("carga_emocional_percentil", row.get("emotional_charge_pct"), "measured",
         "topic_scores_weekly")  # fmt: skip
    if days is not None:
        cite("dias_restantes_ventana", days, "estimate", "topic_scores_weekly.window")
    cite("desfase_tipico_dias", window.get("typical_lag_days"), "measured",
         "topic_scores_weekly.window")  # fmt: skip
    counts = _sources(topic, week)
    if counts:
        cite("articulos_semana", counts[0], "measured", "topic_sources_weekly")
        cite("medios_semana", counts[1], "measured", "topic_sources_weekly")
    eng = _weekly(topic, ("eng",), week)
    es_pt = _weekly(topic, ("spa", "por"), week)
    facts["semanas"] = _calendar_weeks(week)
    facts["articulos_en_ingles_por_semana"] = eng
    facts["articulos_en_espanol_y_portugues_por_semana"] = es_pt
    for i, n in enumerate(eng):
        data.numbers.append(Cited(f"articulos_ingles_semana_{i + 1}", n, "measured",
                                  "get_topic_series"))  # fmt: skip
    for i, n in enumerate(es_pt):
        data.numbers.append(Cited(f"articulos_es_pt_semana_{i + 1}", n, "measured",
                                  "get_topic_series"))  # fmt: skip
    ring = tools.get_context_1hop(topic, week, 5).get("rows") or []
    facts["contexto_vecinos"] = [humanize(r["neighbor"]) for r in ring]
    return data


def parse_reply(text: str | None) -> dict[str, str]:
    """The six fields from the model's reply (tolerates code fences and text around the JSON)."""
    if not text:
        raise ValueError("respuesta vacía")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("la respuesta no contiene un objeto JSON")
    obj = json.loads(match.group(0))
    missing = [f for f in FIELDS if not isinstance(obj.get(f), str) or not obj[f].strip()]
    if missing:
        raise ValueError(f"faltan campos: {', '.join(missing)}")
    return {f: obj[f].strip() for f in FIELDS}


def audit(fields: dict[str, str], data: TopicData) -> tuple[list[str], list[str], list[str]]:
    """(untraced numbers, decision contradictions, style problems) of one brief."""
    text = " ".join(fields.values())
    sources = [{"result": data.facts}]
    untraced = untraced_numbers(text, sources, "")
    wrong = sorted(
        {
            phrase
            for phrase, code in _DECISIONS_TEXT.items()
            if code != data.row["decision"] and re.search(rf"\b{re.escape(phrase)}\b", text, re.I)
        }
    )
    style = []
    if _RAW_IDS.search(text):
        style.append("usa identificadores internos (org:, thm: o códigos en mayúsculas)")
    if _VIRAL.search(text):
        style.append("promete viralidad")
    claims = sorted({m.group(0).lower() for m in _OVERCLAIM.finditer(text)})
    if claims:
        style.append("afirma más de lo que muestran los datos (" + ", ".join(claims) + ")")
    if contradicted := coverage_contradictions(fields, data):
        es = data.facts["articulos_en_espanol_y_portugues_por_semana"][-1]  # present: it flagged
        style.append(
            f"la cobertura en español no coincide con los datos ({es} artículos en español y "
            f"portugués esta semana): «{contradicted[0]}»"
        )
    for f, limit in MAX_LEN.items():
        if len(fields[f]) > limit:
            style.append(f"{f} supera {limit} caracteres")
    return untraced, wrong, style


def cited_used(fields: dict[str, str], data: TopicData) -> list[dict[str, Any]]:
    """The passed numbers that appear in the text (each with its kind and source)."""
    text = " ".join(fields.values())
    tokens = {
        float(t.rstrip("%").replace(",", ".")) for t in re.findall(r"-?\d+(?:[.,]\d+)?%?", text)
    }
    return [
        {"name": c.name, "value": c.value, "kind": c.kind, "source": c.source}
        for c in data.numbers
        if c.value in tokens
    ]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class Result:
    record: dict[str, Any]
    retried: bool
    tokens: int
    seconds: float
    coverage_fixed: bool = False


def write_brief(model: ChatModel, data: TopicData) -> Result:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": "Datos del tema:\n" + json.dumps(data.facts, ensure_ascii=False),
        },
    ]
    tokens, t0, retried, coverage_fixed = 0, time.perf_counter(), False, False
    fields: dict[str, str] | None = None
    untraced: list[str] = []
    wrong: list[str] = []
    for attempt in range(2):
        reply = model.chat(messages, [])
        tokens += reply.tokens
        try:
            fields = parse_reply(reply.content)
        except (ValueError, json.JSONDecodeError) as err:
            complaint = (
                f"Tu respuesta no se pudo leer ({err}). Devuelve SOLO el objeto JSON pedido."
            )
        else:
            untraced, wrong, style = audit(fields, data)
            if not (untraced or wrong or style):
                break
            problems = []
            if untraced:
                problems.append("estos números no están en los datos: " + ", ".join(untraced))
            if wrong:
                problems.append(
                    "mencionas una decisión distinta a la del radar: " + ", ".join(wrong)
                )
            problems += style
            complaint = "El Auditor rechazó el brief: " + "; ".join(problems) + ". Corrígelo."
        if attempt == 0:
            retried = True
            messages += [
                {"role": "assistant", "content": reply.content or ""},
                {"role": "user", "content": complaint},
            ]
    if fields is None:  # two unreadable replies: an honest placeholder, flagged
        fields = dict.fromkeys(FIELDS, "Brief no disponible: el modelo no devolvió un JSON válido.")
        untraced, wrong = [], ["sin respuesta válida"]
    elif coverage_contradictions(fields, data):  # still wrong after the retry: code writes it
        fields = fix_coverage(fields, data)
        coverage_fixed = True
        untraced, wrong, _ = audit(fields, data)
    fields = {f: _clip(v, MAX_LEN[f]) if f in MAX_LEN else v for f, v in fields.items()}
    record = {
        "week": data.week,
        "topic_id": data.row["topic_id"],
        "rank": int(data.row["rank"]),
        "label_es": topic_name(data.row),
        "decision": data.row["decision"],
        **fields,
        "numbers_cited": cited_used(fields, data),
        "auditor_ok": not untraced and not wrong,
        "untraced_numbers": untraced + [f"decisión: {w}" for w in wrong],
        "model": getattr(model, "model", "scripted"),
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return Result(record, retried, tokens, time.perf_counter() - t0, coverage_fixed)


def latest_weeks(n: int) -> list[str]:
    scores = pl.scan_parquet(gold("topic_scores_weekly")).filter(pl.col("rank").is_not_null())
    return scores.select(pl.col("week").unique()).collect()["week"].sort().to_list()[-n:]


def run(model: ChatModel, weeks: list[str], limit: int = 10) -> list[Result]:
    results = []
    for week in weeks:
        for row in tools.get_top10(week)["rows"][:limit]:
            result = write_brief(model, gather(row, week))
            results.append(result)
            r = result.record
            print(
                f"{week} #{r['rank']:>2} {r['topic_id'][:40]:40} auditor_ok={r['auditor_ok']} "
                f"retried={result.retried} coverage_fixed={result.coverage_fixed} "
                f"tokens={result.tokens} {result.seconds:.1f}s",
                flush=True,
            )
    return results


SCHEMA = {
    "week": pl.String, "topic_id": pl.String, "rank": pl.Int64, "label_es": pl.String,
    "decision": pl.String, **dict.fromkeys(FIELDS, pl.String),
    "numbers_cited": pl.List(pl.Struct({"name": pl.String, "value": pl.Float64,
                                        "kind": pl.String, "source": pl.String})),
    "auditor_ok": pl.Boolean, "untraced_numbers": pl.List(pl.String), "model": pl.String,
    "generated_at": pl.String,
}  # fmt: skip


def save(records: list[dict[str, Any]]) -> None:
    errors = validate_records("topic_briefs_weekly", records)
    if errors:
        raise SystemExit(f"{len(errors)} contract violations, e.g. {errors[:3]}")
    path = gold("topic_briefs_weekly", write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(records, schema=SCHEMA).write_parquet(path, compression="zstd")
    print(f"{len(records)} briefs -> {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", type=int, default=2)
    ap.add_argument("--limit", type=int, default=10, help="topics per week (top N)")
    args = ap.parse_args(argv)
    if profile() != "full":
        raise SystemExit("refusing: set RADAR_PROFILE=full (briefs are written from the full lake)")
    t0 = time.perf_counter()
    results = run(NebiusChat(), latest_weeks(args.weeks), args.limit)
    save([r.record for r in results])
    ok = sum(r.record["auditor_ok"] for r in results)
    print(
        f"auditor_ok {ok}/{len(results)}, retried {sum(r.retried for r in results)}, "
        f"coverage fixed by code {sum(r.coverage_fixed for r in results)}, "
        f"tokens {sum(r.tokens for r in results)}, {time.perf_counter() - t0:.0f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
