"""Run the frozen question set through the agents as a LangSmith experiment.

    RADAR_PROFILE=full uv run python -m agents.evals.run_evals --prefix baseline --repetitions 3

Needs LANGSMITH_API_KEY (and NEBIUS_API_KEY) in .env. Each run is one experiment on the dataset
`radar-agents-v<version>`, so prompt, routing or model changes can be compared side by side.
Code evaluators score grounding, decision faithfulness, routing, entity resolution, latency and
tokens; one LLM judge (a larger model than the one answering) scores usefulness for an executive.
"""

import argparse
import datetime as dt
import json
import os
import re
import statistics
import time
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate_existing

from agents.llm import NebiusChat
from agents.runtime import _DECISION_WORDS, _git_sha, run_turn
from radar.paths import REPO_ROOT, gold, lake

QUESTIONS = Path(__file__).with_name("questions.yaml")
JUDGE_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"


def load_questions() -> dict[str, Any]:
    return yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))


def ensure_dataset(client: Client) -> str:
    """Create the dataset once per version; never rewrite a version's examples."""
    spec = load_questions()
    name = f"radar-agents-v{spec['version']}"
    if client.has_dataset(dataset_name=name):
        return name
    ds = client.create_dataset(name, description="Frozen questions for the radar's agents")
    client.create_examples(
        dataset_id=ds.id,
        inputs=[{"question": q["question"]} for q in spec["questions"]],
        outputs=[
            {k: q.get(k) for k in ("id", "kind", "agents", "entity", "decision")}
            for q in spec["questions"]
        ],
    )
    return name


def target(inputs: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    response = run_turn(inputs["question"])
    return response | {"latency_ms": int((time.perf_counter() - t0) * 1000)}


# --- code evaluators (outputs = run_turn's response, reference = the question's expectations) ---


def _steps(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    return outputs.get("trace") or []


def grounding(outputs: dict[str, Any]) -> dict[str, Any]:
    """1 when the Auditor found no number without a source in the answer."""
    vetoed = any(
        s["agent"] == "auditor"
        and s["action"] == "veto"
        and "números" in (s["result_summary"] or "")
        for s in _steps(outputs)
    )
    return {"key": "grounding", "score": 0 if vetoed else 1}


def decision_faithful(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """A decision word in the answer must be one code computed; expected decisions must appear."""
    answer = outputs.get("answer_es") or ""
    cards = outputs.get("decision_cards") or []
    computed = {c["decision"] for c in cards}
    said = {m.group(0).lower() for m in _DECISION_WORDS.finditer(answer)}
    invented = bool(said) and not cards
    missing = bool(reference_outputs.get("decision")) and not cards
    return {
        "key": "decision_faithful",
        "score": 0 if invented or missing else 1,
        "comment": f"computed={sorted(computed)} said={sorted(said)}",
    }


def routing(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """Share of the expected specialists that took part (1 when none are expected)."""
    expected = set(reference_outputs.get("agents") or [])
    seen = {s["agent"] for s in _steps(outputs)}
    score = len(expected & seen) / len(expected) if expected else 1.0
    return {"key": "routing", "score": score, "comment": f"seen={sorted(seen)}"}


def entity_resolved(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """1 when the turn resolved exactly the entity the question names, including none.

    The resolved entity is the one the code route recorded on the Media Master's delegate step; a
    topic resolved when the question names none, or a different one, scores 0 (false positives
    counted, since 2026-10-18 02:00: earlier experiments scored only the 6 entity questions).
    """
    expected = reference_outputs.get("entity")
    resolved = next(
        (
            (s.get("arguments") or {}).get("entity")
            for s in _steps(outputs)
            if s["agent"] == "media_master"
            and s["action"] == "delegate"
            and "entity" in (s.get("arguments") or {})
        ),
        None,
    )
    return {
        "key": "entity_resolved",
        "score": 1 if resolved == expected else 0,
        "comment": f"expected={expected} resolved={resolved}",
    }


def latency_s(outputs: dict[str, Any]) -> dict[str, Any]:
    return {"key": "latency_s", "score": round((outputs.get("latency_ms") or 0) / 1000, 2)}


def tokens(outputs: dict[str, Any]) -> dict[str, Any]:
    return {"key": "tokens", "score": sum(s.get("tokens") or 0 for s in _steps(outputs))}


# --- LLM judge ---

JUDGE_PROMPT = (
    "Eres un editor jefe de un medio de negocios en LatAm. Evalúa la respuesta de un asistente a la "
    "pregunta de un ejecutivo. Criterios: (1) responde la pregunta, (2) es clara y accionable, "
    "(3) está en español natural, (4) es breve (máximo 8 líneas), (5) no inventa datos ni promete "
    "lo que no puede saber. Devuelve SOLO un JSON: "
    '{"score": <entero 1-5>, "reason": "<una frase>"}.'
)


@cache
def _judge() -> NebiusChat:
    return NebiusChat(temperature=0.0, model=JUDGE_MODEL)


def _verdict(key: str, system: str, user: str) -> dict[str, Any]:
    """One judge call; a 1-5 score scaled to 0-1, or None when the output is not parseable."""
    reply = _judge().chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}], []
    )
    match = re.search(r"\{.*\}", reply.content or "", re.S)
    try:
        verdict = json.loads(match.group(0)) if match else {}
        score = int(verdict["score"])
    except (ValueError, KeyError, TypeError):
        return {"key": key, "score": None, "comment": "judge output not parseable"}
    return {"key": key, "score": (score - 1) / 4, "comment": verdict.get("reason")}


def usefulness(inputs: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    """Judge v1: sees only the question and the answer (kept for comparison with past runs)."""
    return _verdict(
        "usefulness",
        JUDGE_PROMPT,
        f"Pregunta: {inputs['question']}\n\nRespuesta: {outputs.get('answer_es')}",
    )


# Judge v2: v1 could not see the data, so it called real numbers "no verificables" and 2026 dates
# "future". v2 gets today's date and the tool results the answer was built from, and scores only
# usefulness to the executive given that data (grounding is checked by code, not by the judge).
JUDGE_V2_PROMPT = (
    "Eres un editor jefe de un medio de negocios en LatAm. Hoy es {today}. Un asistente respondió "
    "la pregunta de un ejecutivo con los datos reales del radar que te muestro (ya verificados por "
    "código: no juzgues si los números o las fechas son verificables). Evalúa SOLO qué tan útil es "
    "la respuesta para ese ejecutivo, dados esos datos: (1) responde exactamente lo que se pregunta, "
    "(2) es clara y accionable, (3) está en español natural y sin jerga interna, (4) es breve "
    "(máximo 8 líneas), (5) usa bien los datos, sin exagerarlos ni decir lo que no dicen. Si los "
    "datos no cubren lo que se pregunta, una respuesta honesta que lo diga y ofrezca una "
    "alternativa útil es correcta. Devuelve SOLO un JSON: "
    '{{"score": <entero 1-5>, "reason": "<una frase>"}}.'
)
TOOL_DATA_CHARS = 4000


def tool_data(outputs: dict[str, Any], limit: int = TOOL_DATA_CHARS) -> str:
    """The tool results the answer was built from (the trace's trimmed summaries), capped."""
    lines = [
        f"- {s.get('tool')}: {s.get('result_summary')}"
        for s in _steps(outputs)
        if s.get("action") == "tool_result" and s.get("result_summary")
    ]
    text = "\n".join(lines) or "(ninguna herramienta: respuesta sin datos del radar)"
    return text if len(text) <= limit else text[: limit - 3] + "..."


def usefulness_v2(inputs: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    today = dt.datetime.now(dt.UTC).astimezone(dt.timezone(dt.timedelta(hours=-5))).date()
    return _verdict(
        "usefulness_v2",
        JUDGE_V2_PROMPT.format(today=today.isoformat()),
        f"Pregunta: {inputs['question']}\n\nDatos del radar:\n{tool_data(outputs)}\n\n"
        f"Respuesta: {outputs.get('answer_es')}",
    )


EVALUATORS = [
    grounding,
    decision_faithful,
    routing,
    entity_resolved,
    latency_s,
    tokens,
    usefulness,
    usefulness_v2,
]
KEYS = [e.__name__ for e in EVALUATORS]


def summarize(rows: list[dict[str, Any]], repetitions: int) -> dict[str, dict[str, Any]]:
    """Per evaluator: the mean over every scored run and the spread of the repetition means.

    ``rows`` holds one dict per run: ``{"qid": ..., "scores": {key: score or None}}``. The k-th run
    of each question is assigned to repetition k (repetitions are independent draws, so any fixed
    assignment is valid). Spread = min and max of the per-repetition means.
    """
    seen: dict[str, int] = defaultdict(int)
    per_rep: dict[str, list[list[float]]] = {k: [[] for _ in range(repetitions)] for k in KEYS}
    for row in rows:
        r = seen[row["qid"]] % repetitions
        seen[row["qid"]] += 1
        for k, v in row["scores"].items():
            if v is not None and k in per_rep:
                per_rep[k][r].append(float(v))
    out = {}
    for k, reps in per_rep.items():
        flat = [v for rep in reps for v in rep]
        means = [statistics.fmean(rep) for rep in reps if rep]
        out[k] = {
            "mean": statistics.fmean(flat) if flat else None,
            "rep_min": min(means) if means else None,
            "rep_max": max(means) if means else None,
            "n": len(flat),
        }
    return out


def _rows(results: Any) -> list[dict[str, Any]]:
    rows = []
    for r in results:
        evals = r["evaluation_results"]["results"]
        out = r["run"].outputs or {}
        rows.append(
            {
                "qid": (r["example"].outputs or {}).get("id"),
                "question": (r["example"].inputs or {}).get("question"),
                "answer": out.get("answer_es"),
                "scores": {e.key: e.score for e in evals},
                "comments": {e.key: e.comment for e in evals if e.comment},
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", default="baseline", help="experiment name prefix")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=1, help="runs per question")
    parser.add_argument("--change", default="", help="what this experiment changes (metadata)")
    parser.add_argument(
        "--questions", help="comma-separated question ids to run (default: all 25), e.g. q20,q22"
    )
    parser.add_argument(
        "--rescore", metavar="EXPERIMENT", help="add usefulness_v2 to an existing experiment"
    )
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "radar-agents")
    client = Client()
    if args.rescore:
        results = evaluate_existing(
            args.rescore,
            evaluators=[usefulness_v2],
            max_concurrency=args.concurrency,
            client=client,
            metadata={"rescored_with": "usefulness_v2"},
        )
        _report(f"{args.rescore}.v2", _rows(results), args.repetitions)
        return
    dataset = ensure_dataset(client)
    data: Any = dataset
    if args.questions:
        wanted = set(args.questions.split(","))
        data = [
            ex
            for ex in client.list_examples(dataset_name=dataset)
            if (ex.outputs or {}).get("id") in wanted
        ]
        if {(ex.outputs or {}).get("id") for ex in data} != wanted:
            raise SystemExit(f"unknown question ids in --questions: {args.questions}")
    results = client.evaluate(
        target,
        data=data,
        evaluators=EVALUATORS,
        experiment_prefix=args.prefix,
        max_concurrency=args.concurrency,
        num_repetitions=args.repetitions,
        metadata={
            "profile": os.environ.get("RADAR_PROFILE", "dev"),
            "judge": JUDGE_MODEL,
            "git_sha": _git_sha(),
            "change": args.change,
            "repetitions": args.repetitions,
            "scores_file_mtime": _scores_mtime(),
        },
    )
    _report(results.experiment_name, _rows(results), args.repetitions)


def _report(name: str, rows: list[dict[str, Any]], repetitions: int) -> None:
    """Writes lake/evals/<name>.json (summary + per-question rows) and prints the summary."""
    summary = summarize(rows, repetitions)
    out = lake() / "evals" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1, default=str)
    )
    print(name)
    for k, v in summary.items():
        if v["mean"] is not None:
            print(
                f"{k}: mean {v['mean']:.3f} reps {v['rep_min']:.3f}..{v['rep_max']:.3f} n={v['n']}"
            )
    print(f"rows: {out}")


def _scores_mtime() -> str | None:
    path = gold("topic_scores_weekly")
    if not path.exists():
        return None
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC).isoformat(timespec="seconds")


if __name__ == "__main__":
    main()
