"""The Media Master and its specialists (contracts/agents.yaml).

One turn: the Media Master reads the question and delegates to specialists through `ask_<agent>`
tools; each specialist answers with its own tools over the lake. Code assembles the decision cards and
view commands from tool results; the Auditor checks that every number in the answer came from a tool.
Every step is recorded as an `agent_trace` row.
"""

import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from langsmith.utils import ContextThreadPoolExecutor

from agents import tools
from agents.llm import ChatModel, NebiusChat
from radar.paths import lake

MAX_ROUNDS = 3

SPECIALISTS: dict[str, dict[str, Any]] = {
    "signal_analyst": {
        "name_es": "Analista de señales",
        "tools": [
            "list_subtopic_trends",
            "get_topic_series",
            "get_top10",
            "get_topic_scores",
            "get_language_coverage",
            "get_topic_sources",
            "get_topic_evidence",
        ],
        "role": "Mides qué temas de IA crecen, en qué etapa están y su carga emocional, con las "
        "señales normalizadas de GDELT (participación del día, z_7d, crecimiento, tono, controversia). "
        "Empieza por get_top10; si dice que no está disponible, usa list_subtopic_trends y "
        "get_topic_series, y aclara que la decisión formal aún no está calculada.",
    },
    "cartographer": {
        "name_es": "Cartógrafo",
        "tools": ["get_context_1hop", "get_graph_facts", "update_view"],
        "role": "Explicas un tema por sus vecinos en el grafo de co-menciones y cambias la vista del "
        "grafo con update_view cuando el usuario quiere ver algo.",
    },
    "audience_strategist": {
        "name_es": "Estratega de audiencia",
        "tools": ["get_topic_series", "get_topic_scores"],
        "role": "Juzgas el encaje con ejecutivos de LatAm (participación LatAm, subtemas de negocio y "
        "educación) y el ángulo emocional para contarlo.",
    },
    "editor": {
        "name_es": "Editor",
        "tools": ["get_topic_brief", "get_topic_evidence", "get_topic_series", "get_context_1hop"],
        "role": "Propones formato, dos ganchos y un guion de 30-45 s en español, apoyado solo en los "
        "datos que consultas. Si existe el brief ya escrito del tema, parte de él.",
    },
    "scout": {
        "name_es": "Explorador",
        "tools": ["get_freshness", "get_cost_ledger"],
        "role": "Dices qué tan frescos están los datos y cuánto ha costado traerlos.",
    },
    "curator": {
        "name_es": "Curador",
        "tools": ["get_segment_mix", "get_filter_quality"],
        "role": "Explicas qué cuenta como noticia de IA, cómo se reparte por subtema e idioma, y la "
        "calidad del filtro.",
    },
    "auditor": {
        "name_es": "Auditor",
        "tools": ["get_backtest", "get_filter_quality", "get_cost_ledger"],
        "role": "Dices cuánto confiar en el radar: backtest, calidad del filtro, costo. Nunca afirmas "
        "algo que no esté en un informe.",
    },
}

# no story beyond the data: the same rule the Editor's briefs follow (agents/briefs.py)
NO_NARRATIVE = (
    "Los subtemas son categorías del radar, no el negocio de la empresa: no afirmes que el tema "
    "'está conectado' con ellos ni inventes por qué crece; si no sabes la causa, dilo."
)
MASTER_NO_NARRATIVE = (
    "No agregues causas, historias ni intenciones que los datos no muestren (por ejemplo, que una "
    "empresa 'está redefiniendo' algo o 'se expande' a un mercado): di solo lo que muestran. "
    + NO_NARRATIVE
    + " En 'Qué hacer', el enfoque sale de los datos (decisión, ángulo, cifras), no de una historia "
    "sobre la empresa."
)

RULES = (
    "Reglas: responde en español claro para ejecutivos de medios. Usa SOLO números que devuelvan las "
    "herramientas, sin inventar ni redondear de forma engañosa; si una herramienta dice que algo no "
    "está disponible, dilo tal cual. Las decisiones (publicar ahora, preparar, esperar, no es tema "
    "caliente) las calcula el código del Analista de señales: nunca las inventes. Sé breve: máximo "
    "8 líneas."
)


def rules() -> str:
    """RULES plus what the data is, so answers never call the full lake 'development data'."""
    if tools.profile() == "dev":
        return RULES + " Los datos son un corte de desarrollo (8 semanas reales): menciónalo."
    return RULES + " Los datos son el conjunto completo y real; no digas que son de desarrollo."


MASTER_PROMPT = (
    "Eres el Maestro de Medios de la Radar de Señal Temprana de 30X: un estratega de contenido de "
    "clase mundial que interpreta datos, grafos y decisiones de modelos para ejecutivos de LatAm. "
    "No consultas datos tú mismo: delegas en tu equipo con las herramientas ask_<agente> (puedes "
    "llamar a varios a la vez) y luego integras sus respuestas en una recomendación con KPIs "
    "concretos. A quién preguntar: qué publicar o qué sube -> signal_analyst y audience_strategist; "
    "por qué o con qué se conecta, o si piden VER el grafo -> cartographer (que usa update_view); "
    "qué contenido hacer -> editor; frescura o costo -> scout; qué cuenta como IA -> curator; "
    "cuánto confiar -> auditor. Pregunta solo a quien haga falta. Tu equipo: "
    + "; ".join(f"{k} ({v['name_es']}): {v['role']}" for k, v in SPECIALISTS.items())
    + ". "
)


def master_prompt() -> str:
    return MASTER_PROMPT + rules() + " " + MASTER_NO_NARRATIVE


@dataclass
class Turn:
    conversation_id: str
    answer_es: str = ""
    decision_cards: list[dict[str, Any]] = field(default_factory=list)
    view_commands: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    def log(self, agent: str, action: str, **kw: Any) -> str:
        step = len(self.trace)
        self.trace.append(
            {
                "conversation_id": self.conversation_id,
                "step": step,
                "agent": agent,
                "action": action,
                "tool": None,
                "arguments": None,
                "result_summary": None,
                "latency_ms": None,
                "tokens": None,
                "model": None,
            }
            | kw
        )
        return f"{self.conversation_id}:{step}"

    def as_response(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "answer_es": self.answer_es,
            "decision_cards": self.decision_cards,
            "view_commands": self.view_commands,
            "trace": self.trace,
        }


def _summary(result: dict[str, Any]) -> str:
    text = json.dumps(result, ensure_ascii=False, default=str)
    return text[:497] + "..." if len(text) > 500 else text


def _delegate_spec(agent: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": f"ask_{agent}",
            "description": f"Pregunta al {SPECIALISTS[agent]['name_es']}: {SPECIALISTS[agent]['role']}",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    }


def _loop(
    model: ChatModel, turn: Turn, agent: str, system: str, user: str, specs: list[dict[str, Any]]
) -> str:
    """Generic tool loop for one agent; returns its final text."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _ in range(MAX_ROUNDS):
        reply = model.chat(messages, specs)
        if not reply.tool_calls:
            turn.log(
                agent,
                "answer",
                result_summary=(reply.content or "")[:500],
                latency_ms=reply.latency_ms,
                tokens=reply.tokens,
                model=reply.model,
            )
            return reply.content or ""
        messages.append(
            {"role": "assistant", "content": reply.content or "", "tool_calls": reply.tool_calls}
        )
        for i, tc in enumerate(reply.tool_calls):
            name, raw = tc["function"]["name"], tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {}
            meta = {
                "latency_ms": reply.latency_ms if i == 0 else None,
                "tokens": reply.tokens if i == 0 else None,
                "model": reply.model,
            }
            if name.startswith("ask_") and name[4:] in SPECIALISTS:
                sub = name[4:]
                turn.log(agent, "delegate", tool=name, arguments=args, **meta)
                result: dict[str, Any] = {
                    "answer": run_specialist(model, turn, sub, args.get("question", user))
                }
            else:
                turn.log(agent, "tool_call", tool=name, arguments=args, **meta)
                result = tools.call(name, args)
                source = turn.log(agent, "tool_result", tool=name, result_summary=_summary(result))
                turn.tool_results.append(
                    {"source": source, "tool": name, "args": args, "result": result}
                )
                if name == "update_view" and result.get("available"):
                    turn.view_commands.append(result["view_command"])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
    # Out of rounds: one last call without tools, so the agent answers with what it already has.
    messages.append(
        {"role": "user", "content": "Responde ya con lo que tienes, sin más herramientas."}
    )
    reply = model.chat(messages, [])
    turn.log(
        agent,
        "answer",
        result_summary=(reply.content or "")[:500],
        latency_ms=reply.latency_ms,
        tokens=reply.tokens,
        model=reply.model,
    )
    return reply.content or ""


@traceable(
    run_type="chain", process_inputs=lambda i: {"agent": i["agent"], "question": i["question"]}
)
def run_specialist(model: ChatModel, turn: Turn, agent: str, question: str) -> str:
    spec = SPECIALISTS[agent]
    system = f"Eres el {spec['name_es']} de la Radar de Señal Temprana. {spec['role']} {rules()}"
    return _loop(
        model, turn, agent, system, question, [tools.TOOLS[t].spec() for t in spec["tools"]]
    )


# --- Auditor (deterministic) ------------------------------------------------------------------

_NUM = re.compile(r"(?<![\w-])-?\d+(?:[.,]\d+)?%?")


_MONTHS_ES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
_DATE = re.compile(
    r"\b(\d{4})-(\d{2})-(\d{2})\b"
    rf"|\b(\d{{1,2}}) de ({'|'.join(_MONTHS_ES)})(?: de(?:l)? (\d{{4}}))?\b",
    re.I,
)


def _dates(text: str) -> list[tuple[str, tuple[int | None, int, int]]]:
    """Dates in a text, ISO ("2026-10-18") or Spanish ("18 de octubre de 2026", year optional)."""
    out = []
    for m in _DATE.finditer(text):
        if m.group(1):
            out.append((m.group(0), (int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        else:
            month = _MONTHS_ES.index(m.group(5).lower()) + 1
            year = int(m.group(6)) if m.group(6) else None
            out.append((m.group(0), (year, month, int(m.group(4)))))
    return out


def _numbers(text: str) -> list[str]:
    """Numbers outside dates: a date is read whole (see _dates), never as loose parts."""
    return [m.group(0) for m in _NUM.finditer(_DATE.sub(" ", text))]


def _as_float(token: str) -> float:
    return float(token.rstrip("%").replace(",", "."))


def _source_numbers(results: list[dict[str, Any]], extra: str) -> list[float]:
    found = [_as_float(t) for t in _numbers(extra)]
    for r in results:
        text = json.dumps(r["result"], default=str)
        found += [_as_float(t) for t in _numbers(text)]
        found += [float(d[0]) for _, d in _dates(text) if d[0]]  # a source date's year ("en 2026")
    return found


def _source_dates(results: list[dict[str, Any]], extra: str) -> set[tuple[int | None, int, int]]:
    texts = [extra] + [json.dumps(r["result"], default=str) for r in results]
    return {d for t in texts for _, d in _dates(t)}


_THOUSANDS = re.compile(r"^[1-9]\d{0,2}(?:[.,]\d{3})+$")


def untraced_numbers(answer: str, results: list[dict[str, Any]], question: str) -> list[str]:
    """Numbers in the answer that match no tool result (allowing rounding and % of a share)."""
    sources = _source_numbers(results, question)
    dates = _source_dates(results, question)
    # a date is traced when the same day appears in the data (a date without a year matches any year)
    bad = [
        text
        for text, (y, m, d) in _dates(answer)
        if not any(sm == m and sd == d and (y is None or sy in (y, None)) for sy, sm, sd in dates)
    ]
    for token in _numbers(answer):
        value = _as_float(token)
        if abs(value) <= 12 and value == int(value):
            continue  # small counts such as "top 10" or "2 ganchos"
        # only a percentage may match a share (34,6% <- 0.346); a plain number must match itself
        candidates = [value, value / 100] if token.endswith("%") else [value]
        decimals = len(token.rstrip("%").replace(",", ".").partition(".")[2])
        tol = 0.5 * 10**-decimals
        if any(abs(s - c) <= max(tol, abs(c) * 0.005) for s in sources for c in candidates):
            continue
        # "4.117" or "4,117" written for 4117: an exact integer, no rounding allowance
        if _THOUSANDS.match(token) and float(re.sub(r"[.,]", "", token)) in sources:
            continue
        bad.append(token)
    return bad


# --- Decision cards (code, never the LLM) -----------------------------------------------------


def cards_from_scores(turn: Turn) -> list[dict[str, Any]]:
    cards = []
    for r in turn.tool_results:
        if r["tool"] not in {"get_top10", "get_topic_scores"} or not r["result"].get("available"):
            continue
        for row in r["result"]["rows"][:3]:
            kpis = [
                {
                    "name": n,
                    "value": row.get(k),
                    "unit": u,
                    "kind": "measured",
                    "source": r["source"],
                }
                for n, k, u in [
                    ("Emergencia (percentil)", "emergence_pct", "pct"),
                    ("Saturación", "saturation", None),
                    ("Encaje audiencia", "audience_fit", None),
                    ("Carga emocional (percentil)", "emotional_charge_pct", "pct"),
                ]
                if row.get(k) is not None
            ]
            window = row.get("window") or {}
            if window.get("days_left") is not None:
                kpis.append(
                    {
                        "name": "Ventana (días restantes)",
                        "value": window["days_left"],
                        "unit": "días",
                        "kind": "estimate",
                        "source": r["source"],
                    }
                )
            cards.append(
                {
                    "topic_id": row["topic_id"],
                    "week": row["week"],
                    "decision": row["decision"],
                    "kpis": kpis
                    or [
                        {
                            "name": "prioridad",
                            "value": row.get("priority"),
                            "unit": None,
                            "kind": "measured",
                            "source": r["source"],
                        }
                    ],
                    "justification_es": " · ".join(row.get("why") or []),
                    "context_1hop": [],
                    "evidence_ids": (row.get("evidence_ids") or [])[:5],
                    "suggested_content": None,
                    "auditor_ok": True,
                }
            )
    return cards


# a question about money: the Scout answers it, and only then does the Auditor read the cost ledger
_COST_Q = re.compile(r"cost[oóa]|costad|cuesta|gast|factur", re.I)

ROUTES = [
    (
        re.compile(r"grafo|graf|red |muestr|mu[eé]stra|visual|vista|conect|vecin|comunidad", re.I),
        "cartographer",
    ),
    (
        re.compile(r"public|sube|subiendo|crece|caliente|tendenc|top|semana|tema", re.I),
        "signal_analyst",
    ),
    (
        re.compile(r"[aá]ngulo|ejecutiv|latam|audiencia|encaj|\btono\b|sentimiento|emoci", re.I),
        "audience_strategist",
    ),
    (re.compile(r"contenido|guion|gancho|post|formato|escrib|brief", re.I), "editor"),
    (re.compile(rf"{_COST_Q.pattern}|fresc|actualiz|fuente", re.I), "scout"),
    (re.compile(r"conf[ií]a|backtest|precisi|evidencia|calidad", re.I), "auditor"),
]


@traceable(run_type="chain")
def route(question: str) -> list[str]:
    """Specialists the question needs, by keyword (Qwen3-30B routes poorly on its own)."""
    return [agent for pattern, agent in ROUTES if pattern.search(question)]


# Questions no tool can answer, recognised by code (the LLM answered them with unrelated numbers).
OUT_OF_SCOPE = [
    (
        re.compile(
            # social-network metrics only: "predice", "pronóstico" or "cuántos días tendrá" are
            # questions the radar answers, so they must not land here
            r"\blikes?\b|me gusta|seguidores|followers|engagement|impresiones|viraliz|"
            r"alcance (?:de|tendr[aá]|en) (?:mi|un|el|nuestro) (?:post|publicaci[oó]n)",
            re.I,
        ),
        "no predice likes, alcance ni resultados de una publicación: no lee LinkedIn ni redes "
        "sociales",
    ),
    (
        re.compile(r"\bopina\b|opini[oó]n|qu[eé] piensa|qu[eé] dijo|declaraci", re.I),
        "no sigue lo que opinan o dicen personas concretas: no guarda nombres de personas",
    ),
]
CAN_DO = (
    "Lo que sí puedo decirte: qué temas de IA están subiendo esta semana y por qué, desde qué "
    "ángulo contarlos a ejecutivos de LatAm, qué contenido preparar y qué tan frescos y confiables "
    "son los datos. Prueba con «¿Qué debería publicar esta semana?»."
)


def out_of_scope(question: str) -> str | None:
    """A short honest answer for questions no tool covers (code, no LLM, no numbers), else None."""
    for pattern, why in OUT_OF_SCOPE:
        if pattern.search(question):
            return f"Eso no lo puede responder el radar: {why}. {CAN_DO}"
    return None


_DECISION_WORDS = re.compile(r"publicar ahora|no es tema caliente|\bpreparar\b(?= ya| ahora)", re.I)


def _decisions_by_code(turn: Turn) -> dict[str, str]:
    """Decisions present in WS4's scores that a tool returned this turn (topic -> decision)."""
    out = {}
    for r in turn.tool_results:
        if r["tool"] in {"get_top10", "get_topic_scores"} and r["result"].get("available"):
            out |= {row["topic_id"]: row["decision"] for row in r["result"]["rows"]}
    return out


_WEEK_IN_TEXT = re.compile(r"\b(\d{4}-W\d{2})\b")

DECISION_ES = {
    "publicar_ahora": "Publicar ahora",
    "preparar": "Preparar",
    "esperar": "Esperar",
    "no_es_tema_caliente": "No es tema caliente",
}
_PLURAL = re.compile(r"\btop\b|\btemas\b|\d", re.I)

# How the Media Master writes for an executive (measured: the judge penalised raw ids, field names,
# long data dumps and decisions about topics nobody asked about).
PLAIN = (
    "Escribe para un ejecutivo de medios, en español llano. Nunca uses nombres de campos ni "
    "identificadores internos (z_7d, emergence_pct, saturation, npmi, growth_7d_log, 'org:…', "
    "'thm:…', 'funding_markets'): di el nombre del tema y lo que significa ('crece muy rápido', "
    "'casi nadie lo cuenta en español'). Redondea: porcentajes sin decimales y como mucho tres "
    "cifras. Responde primero exactamente lo que se pregunta."
)


def topic_name(row: dict[str, Any]) -> str:
    """How an executive reads a topic: its Spanish label, else the name without the 'org:' prefix."""
    tid = row.get("topic_id") or ""
    label = row.get("label_es")
    if label and label != tid:
        return label
    return tools.labels_es().get(tid) or (tid.split(":", 1)[1] if ":" in tid else tid)


def decision_line(turn: Turn, entity: str | None, question: str) -> str:
    """The first line of the answer, written by code from WS4's decisions, in plain words.

    An entity question gets that entity's decision only (or says it has none); otherwise the #1
    topic, or the top 3 when the question asks for several.
    """
    rows: list[dict[str, Any]] = []
    for r in turn.tool_results:
        if r["tool"] in {"get_top10", "get_topic_scores"} and r["result"].get("available"):
            rows += r["result"]["rows"]
    if entity:
        mine = [r for r in rows if r.get("topic_id") == entity]
        name = entity.split(":", 1)[1] if ":" in entity else entity
        if not mine:
            return f"Decisión del radar: {name} no está entre los temas puntuados esta semana."
        return f"Decisión del radar para {topic_name(mine[0])}: {DECISION_ES[mine[0]['decision']]}."
    top = [r for r in rows if r.get("rank") is not None]
    top = sorted({r["topic_id"]: r for r in top}.values(), key=lambda r: r["rank"])
    if not top:
        return "Decisión del radar: pendiente (las puntuaciones de esta semana aún no están)."
    n = 3 if _PLURAL.search(question) else 1
    parts = [f"{DECISION_ES[r['decision']]} — {topic_name(r)}" for r in top[:n]]
    return "Decisión del radar: " + "; ".join(parts) + "."


_EVIDENCE_Q = re.compile(r"\bart[ií]culos?\b|\bevidencias?\b|\bfuentes?\b|\bmedios\b", re.I)
LANG_ES = {"spa": "español", "eng": "inglés", "por": "portugués"}


def _num(x: float) -> str:
    """A threshold as the answer writes it: 0.1 -> "0,1", 20 -> "20"."""
    return f"{x:g}".replace(".", ",")


def graph_facts_line(turn: Turn, entity: str | None) -> str:
    """How the graph shown was built, written by code from the graph tools' own output: a named
    topic's ring (get_context_1hop's criterios) or the weekly view (get_graph_facts)."""
    found = {r["tool"]: r["result"] for r in turn.tool_results if r["result"].get("available")}
    ring, view = found.get("get_context_1hop"), found.get("get_graph_facts")
    if view and not entity:
        return (
            f"Cómo se arma el grafo ({view['week']}): cada tema muestra hasta sus "
            f"{view['conexiones_por_tema']} conexiones más fuertes, con al menos "
            f"{view['min_coapariciones']} co-menciones y NPMI mayor que {_num(view['npmi_mayor_que'])}; "
            f"esta semana son {view['temas_semana']} temas y {view['conexiones_semana']} conexiones."
        )
    if ring and ring.get("criterios"):
        c = ring["criterios"]
        top = (
            f"sus {c['top_por_tema']} vecinos más fuertes"
            if c.get("top_por_tema")
            else "sus vecinos"
        )
        return (
            f"Cómo se arma el grafo ({ring['week']}): {top}, con al menos "
            f"{c['n_minimo_coapariciones']} co-menciones y NPMI mayor que "
            f"{_num(c['npmi_mayor_que'])}, sin los nodos más conectados ni personas; "
            f"se muestran {len(ring.get('rows') or [])}."
        )
    return ""


def _display_name(turn: Turn, topic_id: str) -> str:
    """A topic's name as the scores give it ("Marsh & McLennan Companies"), else topic_name."""
    scored = [
        row
        for r in turn.tool_results
        if r["tool"] in {"get_top10", "get_topic_scores"} and r["result"].get("available")
        for row in r["result"].get("rows") or []
        if row.get("topic_id") == topic_id
    ]
    return topic_name(scored[0] if scored else {"topic_id": topic_id})


_OUTLET_COUNT_Q = re.compile(r"cu[aá]ntos\s+(?:\w+\s+){0,2}medios", re.I)
_OUTLETS_SAID = re.compile(r"(?<![\d.,])(\d[\d.,]*)\s+medios\b", re.I)


def _sources_result(turn: Turn) -> dict[str, Any] | None:
    return next(
        (
            r["result"]
            for r in turn.tool_results
            if r["tool"] == "get_topic_sources" and r["result"].get("available")
        ),
        None,
    )


def outlet_count_line(turn: Turn) -> str:
    """The answer to "¿cuántos medios?", written by code from get_topic_sources."""
    src = _sources_result(turn)
    if not src:
        return ""
    name = _display_name(turn, src["topic_id"])
    return (
        f"Medios distintos que cubrieron a {name} en {src['week']}: {src['n_medios']} "
        f"(en {src['n_articulos']} artículos)."
    )


def wrong_outlet_counts(answer: str, turn: Turn) -> list[str]:
    """'N medios' in the answer where N is not the measured outlet count (44 articles != 39)."""
    src = _sources_result(turn)
    if not src:
        return []
    bad = []
    for m in _OUTLETS_SAID.finditer(answer):
        if answer[max(0, m.start() - 15) : m.start()].rstrip().endswith("artículos de"):
            continue  # "44 artículos de 39 medios": the block's own phrasing
        if int(re.sub(r"[.,]", "", m.group(1))) != src["n_medios"]:
            bad.append(m.group(0))
    return bad


_TRUST_Q = re.compile(r"conf[ií]a|confiable|fiable|backtest|precisi|acierta|creer", re.I)
# unconditional trust: "puedes confiar", "es confiable", "alta precisión"; a hedge right after
# ("con cautela", "solo para", "pero") or a "no" right before makes it a calibrated statement
_TRUST_CLAIM = re.compile(
    r"(?:puedes|puede|se puede|pueden) confiar|conf[ií]a(?:r)? (?:plenamente|totalmente|en el radar)|"
    r"(?:es|son|resulta) (?:muy |altamente |totalmente |bastante )?(?:confiable|fiable|precis[oa]|"
    r"exact[oa]|sólid[oa]|robust[oa])|alta (?:precisi[oó]n|confiabilidad|fiabilidad)|"
    r"(?:muy|altamente|totalmente) (?:confiable|fiable|precis[oa])",
    re.I,
)
_TRUST_HEDGE = re.compile(
    r"con (?:cautela|moderaci[oó]n|reservas|cuidado)|solo|s[oó]lo|parcialmente|siempre que|"
    r"pero|aunque|como se[nñ]al|no (?:supera|es mejor)",
    re.I,
)


def _pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "%"


def trust_line(turn: Turn) -> str:
    """How far to trust the radar, written by code from get_backtest's parsed headline."""
    found = {r["tool"]: r["result"] for r in turn.tool_results if r["result"].get("available")}
    summary = (found.get("get_backtest") or {}).get("resumen")
    if not summary:
        return ""
    radar, raw = summary["radar_publicado"], summary["crecimiento_de_menciones"]
    lo, hi = radar["ic95_pct"]
    weeks = (
        f" de {summary['semanas_evaluadas']} semanas" if summary.get("semanas_evaluadas") else ""
    )
    beats = {
        "la persistencia (repetir lo que ya subió)": summary["supera_persistencia_en_peor_caso"],
        f"la regla simple de crecimiento de menciones ({_pct(raw['precision_pct'])})": summary[
            "supera_crecimiento_en_peor_caso"
        ],
    }
    yes = [k for k, v in beats.items() if v]
    no = [k for k, v in beats.items() if v is False]
    text = (
        f"Qué tan confiable es el radar (backtest{weeks}; acierto = {summary['etiqueta']}): su "
        f"top 10 publicado acierta el {_pct(radar['precision_pct'])} de las veces (intervalo del "
        f"95%: {_pct(lo)} a {_pct(hi)}), frente a un {_pct(summary['tasa_base_pct'])} de un tema "
        f"al azar."
    )
    if yes:
        text += f" Supera a {' y a '.join(yes)} incluso en el peor caso"
        text += f"; no supera a {' ni a '.join(no)}." if no else "."
    elif no:
        text += f" No supera a {' ni a '.join(no)}."
    if (found.get("get_filter_quality") or {}).get("etiquetas_humanas_pendientes"):
        text += " Las etiquetas humanas del filtro de noticias aún están pendientes."
    return text + " Úsalo como señal temprana, no como garantía."


def trust_claims(answer: str, turn: Turn) -> list[str]:
    """Unconditional trust phrases on the trust route (where get_backtest ran)."""
    if not any(r["tool"] == "get_backtest" for r in turn.tool_results):
        return []
    claims = []
    for m in _TRUST_CLAIM.finditer(answer):
        before = answer[max(0, m.start() - 12) : m.start()].lower()
        after = answer[m.end() : m.end() + 40]
        if re.search(r"\bno\b|\bni\b", before) or _TRUST_HEDGE.search(after):
            continue
        claims.append(m.group(0))
    return claims


def coverage_line(turn: Turn) -> str:
    """Spanish and Portuguese coverage of the topic, written by code from get_language_coverage."""
    cov = next(
        (
            r["result"]
            for r in turn.tool_results
            if r["tool"] == "get_language_coverage" and r["result"].get("available")
        ),
        None,
    )
    if not cov:
        return ""
    name = _display_name(turn, cov["topic"])
    days = f" ({cov['dias_con_datos']} días con datos)" if cov.get("dias_con_datos") else ""
    return (
        f"Cobertura en español y portugués de {name} ({cov['week']}): {cov['articulos_es']} "
        f"artículos en español y {cov['articulos_pt']} en portugués, de {cov['articulos_total']} "
        f"en total{days}."
    )


# a growth or presence word followed within three words by "en <LatAm>", e.g. "crecimiento muy
# rápido en Latinoamérica", "alta participación en América Latina"; a gap word just before it
# ("brecha de cobertura en LatAm", "sin presencia en la región") makes it the opposite claim
_LATAM_CLAIM = re.compile(
    r"\b(?:crec\w*|sub\w*|aument\w*|gan\w*|tracci[oó]n|expan\w*|particip\w*|presencia|"
    r"cobertura|conversaci[oó]n|se habla|repunt\w*)(?:\s+\S+){0,3}?\s+en\s+"
    r"(?:latinoam[eé]rica|am[eé]rica latina|latam|la regi[oó]n)\b",
    re.I,
)
_GAP = re.compile(
    r"\b(?:no|sin|nul[oa]|cero|brecha|vac[ií]o|ausencia|falta|baj[oa]|poc[oa]|escas[oa]|nadie)\b",
    re.I,
)


def latam_claims(answer: str, turn: Turn) -> list[str]:
    """Phrases claiming growth or presence in LatAm while the topic has 0 es and 0 pt articles."""
    cov = next(
        (
            r["result"]
            for r in turn.tool_results
            if r["tool"] == "get_language_coverage" and r["result"].get("available")
        ),
        None,
    )
    if not cov or cov["articulos_es"] + cov["articulos_pt"] > 0:
        return []
    claims = []
    for m in _LATAM_CLAIM.finditer(answer):
        before = answer[max(0, m.start() - 30) : m.start()]
        if not _GAP.search(before) and not _GAP.search(m.group(0)):
            claims.append(m.group(0))
    return claims


def strip_echo(body: str, code_text: str) -> str:
    """Drop the model's lines that repeat a line code already wrote (the decision line above all)."""
    if not code_text:
        return body

    def norm(text: str) -> str:
        return re.sub(r"[*_`]+", "", text).strip().rstrip(".").lower()

    written = {norm(t) for t in code_text.splitlines() if norm(t)}
    decision = any(t.startswith("decisión del radar") for t in written)
    kept = [
        ln
        for ln in body.splitlines()
        if not (norm(ln) in written or (decision and norm(ln).startswith("decisión del radar")))
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def evidence_block(turn: Turn) -> str:
    """The articles behind a named topic, written by code from get_topic_evidence (and the week's
    outlet count from get_topic_sources), so an evidence question lists them verbatim."""
    found = {r["tool"]: r["result"] for r in turn.tool_results if r["result"].get("available")}
    evidence, sources = found.get("get_topic_evidence"), found.get("get_topic_sources")
    if not evidence:
        return ""
    name = _display_name(turn, evidence["topic_id"])
    head = f"Artículos que respaldan a {name} ({evidence['week']})"
    if sources:
        head += f": {sources['n_articulos']} artículos de {sources['n_medios']} medios esa semana"
    lines = [
        f"- {a['source']}, {a['dt']}, {LANG_ES.get(a['lang_bucket'], 'otro idioma')}: «{a['title']}»"
        for a in evidence["articles"]
    ]
    return head + "; estos son los más representativos:\n" + "\n".join(lines)


_WORD = re.compile(r"[\wáéíóúñü&.-]+", re.I)
_NON_NAME = re.compile(r"[^\w&.-]+")


def _entity_in_question(question: str, week: str | None) -> str | None:
    """The graph topic a question names: a full node name in the text ('google' -> 'org:google'),
    else the longest 1-3 word phrase that resolves to one ('OpenAI' -> GDELT's 'org:openai inc')."""
    # whole words only: a plain substring test found 'org:a co' inside "ha costado"
    padded = f" {_NON_NAME.sub(' ', question.lower())} "
    names = tools.graph_nodes(week)
    hits = [
        n
        for n in names
        if len(n.split(":", 1)[1].replace(" ", "")) > 3
        and n.split(":", 1)[1] not in labels_stop()
        and f" {n.split(':', 1)[1]} " in padded
    ]
    if hits:
        return max(hits, key=len)
    words = _WORD.findall(question)
    for size in (3, 2, 1):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i : i + size]).strip(".-")
            if len(phrase) <= 3 or phrase.lower() in labels_stop():
                continue
            resolved = tools.resolve_topic(phrase)
            if resolved != phrase and resolved in names:
                return resolved
    return None


@cache
def labels_stop() -> frozenset[str]:
    """Spanish words that would resolve to an unrelated org by prefix ('esta' -> 'org:esta ...')."""
    return frozenset(
        [
            "esta",
            "este",
            "semana",
            "tema",
            "temas",
            "qué",
            "que",
            "para",
            "sobre",
            "como",
            "cómo",
            "cuál",
            "cual",
            "está",
            "pasando",
            "con",
            "noticias",
            "grafo",
            "vecinos",
            "conviene",
            "escribir",
            "aparece",
            "muéstrame",
            "muestrame",
            "ahora",
            # 'el tema principal' is not 'org:principal group'; LinkedIn is where 30X publishes,
            # not the topic of the question
            "principal",
            "linkedin",
        ]
    )


_traced_tool = traceable(run_type="tool")(tools.call)


def _run_tool(turn: Turn, agent: str, name: str, **args: Any) -> dict[str, Any]:
    turn.log(agent, "tool_call", tool=name, arguments=args)
    result = _traced_tool(name, args, langsmith_extra={"name": name, "metadata": {"agent": agent}})
    source = turn.log(agent, "tool_result", tool=name, result_summary=_summary(result))
    turn.tool_results.append({"source": source, "tool": name, "args": args, "result": result})
    if name == "update_view" and result.get("available"):
        turn.view_commands.append(result["view_command"])
    return result


def _leader(result: dict[str, Any]) -> str | None:
    if result.get("available") and result.get("rows"):
        return result["rows"][0]["topic_id"]
    trends = (
        result if "fastest_growing_subtopic" in result else result.get("fallback_subtopic_trends")
    )
    return (trends or {}).get("fastest_growing_subtopic")


@traceable(
    run_type="chain", process_inputs=lambda i: {"agent": i["agent"], "question": i["question"]}
)
def gather(turn: Turn, agent: str, question: str, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Each specialist's fixed data plan: code chooses the tools and arguments, never the LLM."""
    week, leader, entity = ctx["week"], ctx["leader"], ctx["entity"]
    calls: list[tuple[str, dict[str, Any]]] = {
        "signal_analyst": [("get_topic_series", {"topic": entity or leader or "ai_all"})]
        + (
            [
                (
                    "get_language_coverage",
                    {"topic": entity or leader, "week": week or ctx["signals"].get("week")},
                )
            ]
            if (entity or leader)
            else []
        )
        + ([("get_topic_scores", {"topic_id": entity, "week": week})] if entity else [])
        + ([("get_topic_sources", {"topic_id": entity, "week": week})] if entity else [])
        + ([("get_topic_evidence", {"topic_id": entity, "week": week})] if entity else []),
        "audience_strategist": [
            ("get_topic_series", {"topic": leader or "ai_all", "lang_bucket": "spa"})
        ],
        # no entity named: the ring of the week's #1 topic, so the answer has real neighbours
        "cartographer": (
            [("get_context_1hop", {"entity": entity or leader, "week": week})]
            if (entity or (leader and ":" in leader))
            else []
        )
        + ([] if entity else [("get_graph_facts", {"week": week})]),
        # the pre-written, Auditor-checked brief first when it exists (agents/briefs.py)
        "editor": (
            [("get_topic_brief", {"topic_id": entity or leader, "week": week})]
            if tools.brief_available() and (entity or leader)
            else []
        )
        + [("get_topic_series", {"topic": leader or "ai_all", "lang_bucket": "spa", "weeks": 4})]
        + ([("get_topic_evidence", {"topic_id": entity, "week": week})] if entity else []),
        "scout": [("get_freshness", {}), ("get_cost_ledger", {})],
        "curator": [("get_segment_mix", {"week": week}), ("get_filter_quality", {})],
        # the cost ledger only when asked about cost: given it unasked, the model recast it as
        # an invented weekly cost ("$2.20 por semana", q22 in grounding-gaps)
        "auditor": [("get_backtest", {}), ("get_filter_quality", {})]
        + ([("get_cost_ledger", {})] if _COST_Q.search(question) else []),
    }[agent]
    results = (
        [ctx["signals"]] if agent in {"signal_analyst", "audience_strategist", "editor"} else []
    )
    results += [_run_tool(turn, agent, name, **args) for name, args in calls]
    if agent == "cartographer":
        lens = view_lens(question, entity)
        top10 = [r["topic_id"] for r in (ctx["signals"].get("rows") or [])][:10]
        results.append(
            _run_tool(
                turn,
                agent,
                "update_view",
                view="story" if entity else "temporal",
                caption_es=_lens_caption(lens, entity, leader),
                color_by=lens,
                focus_topic=entity,
                highlight=[entity] if entity else top10,
                week=week,
            )
        )
    return results


_TONE_Q = re.compile(r"tono|emoci|sentimiento|[aá]nimo|negativ|positiv", re.I)
_WINDOW_Q = re.compile(r"ventana|espa[nñ]ol|portugu|llega|a punto|d[ií]as quedan", re.I)
_BRIDGE_Q = re.compile(
    r"puente|conect|cruza|otros? (dominios?|sectores?)|cl[ií]ma|salud|educaci|empleo", re.I
)
_MOMENTUM_Q = re.compile(r"impulso|acelera|sube m[aá]s r[aá]pido|ganando", re.I)
_NOVELTY_Q = re.compile(
    r"nuev[oa]s? (conexion|relacion|v[ií]nculo)|(conexion|relacion|v[ií]nculo)\w* nuev|qu[eé] cambi",
    re.I,
)


def view_lens(question: str, entity: str | None) -> str:
    """The graph lens a question asks for (view_command.color_by), chosen by code."""
    if _TONE_Q.search(question):
        return "tone"
    if _WINDOW_Q.search(question):
        return "window"
    if _NOVELTY_Q.search(question):
        return "novelty"
    if _MOMENTUM_Q.search(question):
        return "momentum"
    if _BRIDGE_Q.search(question) and not entity:
        return "bridge"
    return "segment" if entity else "decision"


def _lens_caption(lens: str, entity: str | None, leader: str | None) -> str:
    name = (entity or leader or "").split(":", 1)[-1]
    if entity:
        return {
            "tone": f"{name}: sus conexiones, coloreadas por tono",
            "window": f"{name}: sus conexiones y cuánto falta para que llegue al español",
        }.get(lens, f"{name}: con qué se conecta esta semana (IA, TI e IA × dominio)")
    return {
        "tone": "Los temas de la semana, coloreados por tono",
        "window": "Los temas de la semana según cuánto falta para que lleguen al español",
        "bridge": "Los temas que conectan la IA con otros dominios (tamaño = cuánto conectan)",
        "momentum": "Los temas que más ganan centralidad esta semana",
        "novelty": "Las conexiones nuevas de esta semana",
    }.get(
        lens,
        f"Los temas de la semana por decisión del radar; el n.º 1 es {name}"
        if name
        else "Los temas de la semana por decisión del radar",
    )


@traceable(
    run_type="chain",
    process_inputs=lambda i: {"agent": i["agent"], "question": i["question"]},
)
def interpret(
    model: ChatModel, turn: Turn, agent: str, question: str, data: list[dict[str, Any]]
) -> str:
    spec = SPECIALISTS[agent]
    system = (
        f"Eres el {spec['name_es']} de la Radar de Señal Temprana. {spec['role']} {rules()} "
        "Interpreta SOLO los datos que te doy, en 2 a 4 líneas, citando sus números."
    )
    payload = json.dumps(data, ensure_ascii=False, default=str)[:12000]
    reply = model.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Pregunta: {question}\n\nDatos: {payload}"},
        ],
        [],
    )
    turn.log(
        agent,
        "answer",
        result_summary=(reply.content or "")[:500],
        latency_ms=reply.latency_ms,
        tokens=reply.tokens,
        model=reply.model,
    )
    return reply.content or ""


@traceable(
    run_type="chain",
    name="media_master_turn",
    process_inputs=lambda i: {"question": i["question"], "week": i.get("week")},
)
def run_turn(
    question: str,
    conversation_id: str | None = None,
    model: ChatModel | None = None,
    week: str | None = None,
) -> dict[str, Any]:
    model = model or NebiusChat()
    turn = Turn(conversation_id or uuid.uuid4().hex[:12])
    if refusal := out_of_scope(question):
        turn.log("media_master", "answer", result_summary="fuera de alcance (ruta por código)")
        answer, bad, decision_vetoed = _audit(turn, refusal, question, [])
        turn.answer_es = answer
        response = turn.as_response() | {"trace_id": _trace_id()}
        _tag_run(["out_of_scope"], bad, decision_vetoed, week)
        _save_trace(question, response)
        return response
    week = week or (m.group(1) if (m := _WEEK_IN_TEXT.search(question)) else None)
    entity = _entity_in_question(question, week)
    needed = route(question)
    if entity and not needed:  # "¿Qué pasa con X?": its scores and its connections
        needed = ["signal_analyst", "cartographer"]
    if entity and _EVIDENCE_Q.search(question) and "signal_analyst" not in needed:
        needed = ["signal_analyst", *needed]  # it reads the topic's articles and outlets
    if not needed:  # unrecognised question: the Media Master delegates freely
        answer = _loop(
            model,
            turn,
            "media_master",
            master_prompt(),
            question,
            [_delegate_spec(a) for a in SPECIALISTS],
        )
    else:
        turn.log(
            "media_master",
            "delegate",
            arguments={"entity": entity},  # the topic the question names (None when none)
            result_summary=f"ruta por código: {', '.join(needed)}",
        )
        signals = _run_tool(turn, "signal_analyst", "get_top10", week=week)
        ctx = {
            "week": week,
            "signals": signals,
            "leader": _leader(signals),
            "entity": entity,
        }
        data = {
            a: gather(turn, a, question, ctx, langsmith_extra={"name": f"gather:{a}"})
            for a in needed
        }
        with ContextThreadPoolExecutor(max_workers=len(needed)) as pool:
            notes = dict(
                zip(
                    needed,
                    pool.map(
                        lambda a: interpret(
                            model, turn, a, question, data[a], langsmith_extra={"name": a}
                        ),
                        needed,
                    ),
                    strict=True,
                )
            )
        team = "\n\n".join(f"{SPECIALISTS[a]['name_es']}: {n}" for a, n in notes.items())
        decides = "signal_analyst" in needed or "editor" in needed
        line = decision_line(turn, entity, question) if decides else ""
        block = evidence_block(turn) if _EVIDENCE_Q.search(question) else ""
        if block:
            line = f"{line}\n\n{block}" if line else block
        facts = graph_facts_line(turn, entity) if "cartographer" in needed else ""
        if facts:
            line = f"{line}\n\n{facts}" if line else facts
        count = outlet_count_line(turn) if _OUTLET_COUNT_Q.search(question) else ""
        if count:
            line = f"{line}\n\n{count}" if line else count
        trust = trust_line(turn) if "auditor" in needed and _TRUST_Q.search(question) else ""
        if trust:
            line = f"{line}\n\n{trust}" if line else trust
        coverage = coverage_line(turn) if decides or entity else ""
        if coverage:
            line = f"{line}\n\n{coverage}" if line else coverage
        instructions = (
            (
                f"El sistema ya escribe la primera línea, calculada por código: «{line}». No la "
                "repitas ni propongas otra decisión. Escribe solo lo que sigue: 'Por qué:' con 2 o 3 "
                "viñetas cortas, y una línea 'Qué hacer:' con una sugerencia de contenido concreta "
                "(formato y enfoque). Máximo 6 líneas en total."
                if decides
                else "Responde la pregunta directamente en 2 a 4 líneas, usando solo lo que dicen "
                "los informes; no agregues KPIs ni decisiones que no estén en ellos."
                + (
                    f" El sistema ya lista los artículos: «{block}». No los repitas."
                    if block
                    else ""
                )
            )
            + (
                f" El sistema ya escribe cómo se arma el grafo: «{facts}». No lo repitas y no "
                "menciones otros umbrales, mínimos de co-menciones ni valores de NPMI."
                if facts
                else ""
            )
            + (
                f" El sistema ya escribe qué tan confiable es el radar: «{trust}». No lo repitas. "
                "No digas que se puede confiar sin condiciones ('puedes confiar', 'es confiable', "
                "'alta precisión'): la confianza es la que dice esa línea."
                if trust
                else ""
            )
            + (
                f" El sistema ya escribe cuántos medios distintos hubo: «{count}». No des otro "
                "número de medios: el número de artículos no es el de medios."
                if count
                else ""
            )
            + (
                f" El sistema ya escribe la cobertura en español y portugués: «{coverage}». No la "
                "repitas. No digas que el tema crece, está presente o se habla de él en Latinoamérica, "
                "LatAm o la región salvo que esa línea muestre artículos en español o portugués."
                if coverage
                else ""
            )
        )
        reply = model.chat(
            [
                {"role": "system", "content": master_prompt()},
                {
                    "role": "user",
                    "content": f"Pregunta: {question}\n\nInformes de tu equipo:\n{team}\n\n"
                    f"{instructions} {PLAIN}",
                },
            ],
            [],
        )
        turn.log(
            "media_master",
            "answer",
            result_summary=(reply.content or "")[:500],
            latency_ms=reply.latency_ms,
            tokens=reply.tokens,
            model=reply.model,
        )
        body = strip_echo((reply.content or "").strip(), line)
        answer = f"{line}\n\n{body}" if line else body
    # cards only when the question is about what to publish, not about cost or freshness
    turn.decision_cards = (
        cards_from_scores(turn)
        if {"signal_analyst", "audience_strategist", "editor"} & set(needed or SPECIALISTS)
        else []
    )
    answer, bad, decision_vetoed = _audit(turn, answer, question, turn.decision_cards)
    turn.answer_es = answer
    for card in turn.decision_cards:
        card["auditor_ok"] = not bad
    response = turn.as_response() | {"trace_id": _trace_id()}
    _tag_run(needed, bad, decision_vetoed, week)
    _save_trace(question, response)
    return response


@traceable(
    run_type="chain",
    name="auditor",
    process_inputs=lambda i: {"answer": i["answer"], "question": i["question"]},
    process_outputs=lambda o: {"answer": o[0], "untraced_numbers": o[1], "decision_vetoed": o[2]},
)
def _decision_code(phrase: str) -> str:
    p = phrase.lower()
    if p.startswith("publicar"):
        return "publicar_ahora"
    if p.startswith("no es"):
        return "no_es_tema_caliente"
    return "preparar"


def _audit(
    turn: Turn, answer: str, question: str, cards: list[dict[str, Any]]
) -> tuple[str, list[str], bool]:
    """The deterministic Auditor: veto decisions no card carries, flag numbers no tool returned.

    A decision phrase stands only when this turn emits a decision card with that decision; a
    decision in the scores that no card shows (q22: "No se recomienda publicar ahora" on a trust
    question) is replaced by "decisión pendiente".
    """
    shown = {c["decision"] for c in cards}
    checked = _DECISION_WORDS.sub(
        lambda m: m.group(0) if _decision_code(m.group(0)) in shown else "decisión pendiente",
        answer,
    )
    decision_vetoed = checked != answer
    if decision_vetoed:
        turn.log(
            "auditor", "veto", result_summary="decisión sin tarjeta de decisión: se marca pendiente"
        )
        answer = checked
    if claims := latam_claims(answer, turn):
        turn.log(
            "auditor",
            "veto",
            result_summary=f"afirmación sobre LatAm sin artículos en español ni portugués: {claims[0][:120]}",
        )
        answer += (
            "\n\n⚠️ El Auditor: los datos no muestran artículos de este tema en español ni en "
            "portugués esta semana; lo que se diga de su crecimiento o presencia en Latinoamérica "
            "no tiene respaldo."
        )
    if claims := trust_claims(answer, turn):
        turn.log(
            "auditor",
            "veto",
            result_summary=f"confianza sin condiciones que el backtest no respalda: {', '.join(claims)}",
        )
        answer += (
            "\n\n⚠️ El Auditor: el backtest no respalda una confianza sin condiciones ("
            + ", ".join(f"«{c}»" for c in claims)
            + "); la confiabilidad medida es la de la línea de arriba."
        )
    if wrong := wrong_outlet_counts(answer, turn):
        turn.log(
            "auditor",
            "veto",
            result_summary=f"número de medios que no es el medido: {', '.join(wrong)}",
        )
        answer += (
            f"\n\n⚠️ El Auditor: el número de medios distintos medido es "
            f"{_sources_result(turn)['n_medios']}; no {', '.join(wrong)}."
        )
    bad = untraced_numbers(answer, turn.tool_results, question)
    if bad:
        turn.log("auditor", "veto", result_summary=f"números sin fuente: {', '.join(bad)}")
        answer += (
            "\n\n⚠️ El Auditor no encontró en los datos estos números: "
            + ", ".join(bad)
            + ". Tómalos como no verificados."
        )
    else:
        turn.log(
            "auditor", "answer", result_summary="todos los números de la respuesta tienen fuente"
        )
    return answer, bad, decision_vetoed


@cache
def _git_sha() -> str:
    git = shutil.which("git")
    if not git:
        return "unknown"
    out = subprocess.run(  # noqa: S603 - fixed arguments, absolute path
        [git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return out.stdout.strip() or "unknown"


def _trace_id() -> str | None:
    """The LangSmith trace of this turn, so a reader's thumbs up or down lands on it; None if off."""
    run = get_current_run_tree()
    return str(run.trace_id) if run is not None else None


def _tag_run(needed: list[str], bad: list[str], decision_vetoed: bool, week: str | None) -> None:
    """Tags and metadata on the LangSmith turn, so runs can be filtered by route, veto and version."""
    run = get_current_run_tree()
    if run is None:  # tracing is off
        return
    run.add_tags(
        [f"agent:{a}" for a in needed or ["free_delegation"]]
        + (["auditor:veto"] if bad or decision_vetoed else ["auditor:ok"])
    )
    run.add_metadata(
        {
            "profile": tools.profile(),
            "git_sha": _git_sha(),
            "week": week,
            "untraced_numbers": len(bad),
            "decision_vetoed": decision_vetoed,
        }
    )


def _save_trace(question: str, response: dict[str, Any]) -> None:
    """Every turn's full response goes to lake/agent_traces/ (git-ignored), for the Auditor and demos."""
    out = lake() / "agent_traces" / f"{response['conversation_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"question": question} | response, ensure_ascii=False, indent=1))
