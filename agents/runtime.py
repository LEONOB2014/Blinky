"""The Media Master and its specialists (contracts/agents.yaml).

One turn: the Media Master reads the question and delegates to specialists through `ask_<agent>`
tools; each specialist answers with its own tools over the lake. Code assembles the decision cards and
view commands from tool results; the Auditor checks that every number in the answer came from a tool.
Every step is recorded as an `agent_trace` row.
"""

import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from agents import tools
from agents.llm import ChatModel, NebiusChat

MAX_ROUNDS = 3

SPECIALISTS: dict[str, dict[str, Any]] = {
    "signal_analyst": {
        "name_es": "Analista de señales",
        "tools": ["list_subtopic_trends", "get_topic_series", "get_top10", "get_topic_scores"],
        "role": "Mides qué temas de IA crecen, en qué etapa están y su carga emocional, con las "
        "señales normalizadas de GDELT (participación del día, z_7d, crecimiento, tono, controversia). "
        "Empieza por get_top10; si dice que no está disponible, usa list_subtopic_trends y "
        "get_topic_series, y aclara que la decisión formal aún no está calculada.",
    },
    "cartographer": {
        "name_es": "Cartógrafo",
        "tools": ["get_context_1hop", "update_view"],
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
        "tools": ["get_topic_series", "get_context_1hop"],
        "role": "Propones formato, dos ganchos y un guion de 30-45 s en español, apoyado solo en los "
        "datos que consultas.",
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

RULES = (
    "Reglas: responde en español claro para ejecutivos de medios. Usa SOLO números que devuelvan las "
    "herramientas, sin inventar ni redondear de forma engañosa; si una herramienta dice que algo no "
    "está disponible, dilo tal cual. Las decisiones (publicar ahora, preparar, esperar, no es tema "
    "caliente) las calcula el código del Analista de señales: nunca las inventes. Si los datos son "
    "de desarrollo, menciónalo. Sé breve: máximo 8 líneas."
)

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
    + RULES
)


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


def run_specialist(model: ChatModel, turn: Turn, agent: str, question: str) -> str:
    spec = SPECIALISTS[agent]
    system = f"Eres el {spec['name_es']} de la Radar de Señal Temprana. {spec['role']} {RULES}"
    return _loop(
        model, turn, agent, system, question, [tools.TOOLS[t].spec() for t in spec["tools"]]
    )


# --- Auditor (deterministic) ------------------------------------------------------------------

_NUM = re.compile(r"(?<![\w-])-?\d+(?:[.,]\d+)?%?")


def _numbers(text: str) -> list[str]:
    return [m.group(0) for m in _NUM.finditer(text)]


def _as_float(token: str) -> float:
    return float(token.rstrip("%").replace(",", "."))


def _source_numbers(results: list[dict[str, Any]], extra: str) -> list[float]:
    found = [_as_float(t) for t in _numbers(extra)]
    for r in results:
        found += [_as_float(t) for t in _numbers(json.dumps(r["result"], default=str))]
    return found


def untraced_numbers(answer: str, results: list[dict[str, Any]], question: str) -> list[str]:
    """Numbers in the answer that match no tool result (allowing rounding and % of a share)."""
    sources = _source_numbers(results, question)
    bad = []
    for token in _numbers(answer):
        value = _as_float(token)
        if abs(value) <= 12 and value == int(value):
            continue  # small counts such as "top 10" or "2 ganchos"
        candidates = [value, value / 100] if token.endswith("%") else [value, value / 100]
        decimals = len(token.rstrip("%").replace(",", ".").partition(".")[2])
        tol = 0.5 * 10**-decimals
        if not any(abs(s - c) <= max(tol, abs(c) * 0.005) for s in sources for c in candidates):
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


ROUTES = [
    (
        re.compile(r"grafo|graf|red |muestr|mu[eé]stra|visual|vista|conect|vecin|comunidad", re.I),
        "cartographer",
    ),
    (
        re.compile(r"public|sube|subiendo|crece|caliente|tendenc|top|semana|tema", re.I),
        "signal_analyst",
    ),
    (re.compile(r"[aá]ngulo|ejecutiv|latam|audiencia|encaj", re.I), "audience_strategist"),
    (re.compile(r"contenido|guion|gancho|post|formato|escrib|brief", re.I), "editor"),
    (re.compile(r"costo|cuesta|fresc|actualiz|fuente", re.I), "scout"),
    (re.compile(r"conf[ií]a|backtest|precisi|evidencia|calidad", re.I), "auditor"),
]


def route(question: str) -> list[str]:
    """Specialists the question needs, by keyword (Qwen3-30B routes poorly on its own)."""
    return [agent for pattern, agent in ROUTES if pattern.search(question)]


_DECISION_WORDS = re.compile(r"publicar ahora|no es tema caliente|\bpreparar\b(?= ya| ahora)", re.I)


def _decisions_by_code(turn: Turn) -> dict[str, str]:
    """Decisions present in WS4's scores that a tool returned this turn (topic -> decision)."""
    out = {}
    for r in turn.tool_results:
        if r["tool"] in {"get_top10", "get_topic_scores"} and r["result"].get("available"):
            out |= {row["topic_id"]: row["decision"] for row in r["result"]["rows"]}
    return out


_WEEK_IN_TEXT = re.compile(r"\b(\d{4}-W\d{2})\b")


def _entity_in_question(question: str, week: str | None) -> str | None:
    """The longest graph node whose name appears in the question (e.g. 'openai' -> 'org:openai')."""
    q = question.lower()
    names = tools.graph_nodes(week)
    hits = [n for n in names if len(n.split(":", 1)[1]) > 3 and n.split(":", 1)[1] in q]
    return max(hits, key=len) if hits else None


def _run_tool(turn: Turn, agent: str, name: str, **args: Any) -> dict[str, Any]:
    turn.log(agent, "tool_call", tool=name, arguments=args)
    result = tools.call(name, args)
    source = turn.log(agent, "tool_result", tool=name, result_summary=_summary(result))
    turn.tool_results.append({"source": source, "tool": name, "args": args, "result": result})
    if name == "update_view" and result.get("available"):
        turn.view_commands.append(result["view_command"])
    return result


def _leader(result: dict[str, Any]) -> str | None:
    trends = (
        result if "fastest_growing_subtopic" in result else result.get("fallback_subtopic_trends")
    )
    return (trends or {}).get("fastest_growing_subtopic")


def gather(turn: Turn, agent: str, question: str, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Each specialist's fixed data plan: code chooses the tools and arguments, never the LLM."""
    week, leader, entity = ctx["week"], ctx["leader"], ctx["entity"]
    calls: list[tuple[str, dict[str, Any]]] = {
        "signal_analyst": [("get_topic_series", {"topic": leader or "ai_all"})],
        "audience_strategist": [
            ("get_topic_series", {"topic": leader or "ai_all", "lang_bucket": "spa"})
        ],
        "cartographer": [("get_context_1hop", {"entity": entity, "week": week})] if entity else [],
        "editor": [
            ("get_topic_series", {"topic": leader or "ai_all", "lang_bucket": "spa", "weeks": 4})
        ],
        "scout": [("get_freshness", {}), ("get_cost_ledger", {})],
        "curator": [("get_segment_mix", {"week": week}), ("get_filter_quality", {})],
        "auditor": [("get_backtest", {}), ("get_filter_quality", {}), ("get_cost_ledger", {})],
    }[agent]
    results = (
        [ctx["signals"]] if agent in {"signal_analyst", "audience_strategist", "editor"} else []
    )
    results += [_run_tool(turn, agent, name, **args) for name, args in calls]
    if agent == "cartographer":
        label = tools.labels_es().get(leader, leader) if leader else None
        caption = (
            f"Vecinos de {entity} esta semana"
            if entity
            else f"Grafo de la semana; el subtema que más crece es {label}"
            if label
            else "Grafo de la semana"
        )
        results.append(
            _run_tool(
                turn,
                agent,
                "update_view",
                view="story" if entity else "temporal",
                caption_es=caption,
                focus_topic=entity,
                week=week,
            )
        )
    return results


def interpret(
    model: ChatModel, turn: Turn, agent: str, question: str, data: list[dict[str, Any]]
) -> str:
    spec = SPECIALISTS[agent]
    system = (
        f"Eres el {spec['name_es']} de la Radar de Señal Temprana. {spec['role']} {RULES} "
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


def run_turn(
    question: str,
    conversation_id: str | None = None,
    model: ChatModel | None = None,
    week: str | None = None,
) -> dict[str, Any]:
    model = model or NebiusChat()
    turn = Turn(conversation_id or uuid.uuid4().hex[:12])
    week = week or (m.group(1) if (m := _WEEK_IN_TEXT.search(question)) else None)
    needed = route(question)
    if not needed:  # unrecognised question: the Media Master delegates freely
        answer = _loop(
            model,
            turn,
            "media_master",
            MASTER_PROMPT,
            question,
            [_delegate_spec(a) for a in SPECIALISTS],
        )
    else:
        turn.log("media_master", "delegate", result_summary=f"ruta por código: {', '.join(needed)}")
        signals = _run_tool(turn, "signal_analyst", "get_top10", week=week)
        ctx = {
            "week": week,
            "signals": signals,
            "leader": _leader(signals),
            "entity": _entity_in_question(question, week),
        }
        data = {a: gather(turn, a, question, ctx) for a in needed}
        with ThreadPoolExecutor(max_workers=len(needed)) as pool:
            notes = dict(
                zip(
                    needed,
                    pool.map(lambda a: interpret(model, turn, a, question, data[a]), needed),
                    strict=True,
                )
            )
        team = "\n\n".join(f"{SPECIALISTS[a]['name_es']}: {n}" for a, n in notes.items())
        decided = _decisions_by_code(turn)
        decision_line = (
            ", ".join(f"{k}: {v}" for k, v in decided.items())
            if decided
            else "PENDIENTE (las puntuaciones formales aún no están calculadas)"
        )
        reply = model.chat(
            [
                {"role": "system", "content": MASTER_PROMPT},
                {
                    "role": "user",
                    "content": f"Pregunta: {question}\n\nInformes de tu equipo:\n{team}\n\n"
                    + (
                        f"Decisión calculada por código: {decision_line}. Cópiala tal cual en una "
                        "línea 'Decisión:'; no propongas otra. Luego integra (máx. 8 líneas): por qué, "
                        "KPIs con sus números y qué contenido preparar."
                        if "signal_analyst" in needed or "editor" in needed
                        else "Responde la pregunta directamente (máx. 5 líneas) usando solo lo que "
                        "dicen los informes; no agregues KPIs ni decisiones que no estén en ellos."
                    ),
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
        answer = reply.content or ""
    if not _decisions_by_code(turn) and _DECISION_WORDS.search(answer):
        turn.log(
            "auditor", "veto", result_summary="decisión sin cálculo de código: se marca pendiente"
        )
        answer = _DECISION_WORDS.sub("decisión pendiente", answer)
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
    turn.answer_es = answer
    turn.decision_cards = cards_from_scores(turn)
    for card in turn.decision_cards:
        card["auditor_ok"] = not bad
    return turn.as_response()
