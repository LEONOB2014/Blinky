"""Run the frozen question set through the agents as a LangSmith experiment.

    RADAR_PROFILE=full uv run python -m agents.evals.run_evals --prefix baseline

Needs LANGSMITH_API_KEY (and NEBIUS_API_KEY) in .env. Each run is one experiment on the dataset
`radar-agents-v<version>`, so prompt, routing or model changes can be compared side by side.
Code evaluators score grounding, decision faithfulness, routing, entity resolution, latency and
tokens; one LLM judge (a larger model than the one answering) scores usefulness for an executive.
"""

import argparse
import json
import os
import re
import time
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langsmith import Client

from agents.llm import NebiusChat
from agents.runtime import _DECISION_WORDS, run_turn
from radar.paths import REPO_ROOT

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
    """The named entity reached a tool as its graph id."""
    entity = reference_outputs.get("entity")
    if not entity:
        return {"key": "entity_resolved", "score": None}
    args = json.dumps([s.get("arguments") for s in _steps(outputs)], ensure_ascii=False)
    views = json.dumps(outputs.get("view_commands") or [], ensure_ascii=False)
    hit = entity in args or entity in views
    return {"key": "entity_resolved", "score": 1 if hit else 0}


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


def usefulness(inputs: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    reply = _judge().chat(
        [
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": f"Pregunta: {inputs['question']}\n\nRespuesta: {outputs.get('answer_es')}",
            },
        ],
        [],
    )
    match = re.search(r"\{.*\}", reply.content or "", re.S)
    try:
        verdict = json.loads(match.group(0)) if match else {}
        score = int(verdict["score"])
    except (ValueError, KeyError, TypeError):
        return {"key": "usefulness", "score": None, "comment": "judge output not parseable"}
    return {"key": "usefulness", "score": (score - 1) / 4, "comment": verdict.get("reason")}


EVALUATORS = [grounding, decision_faithful, routing, entity_resolved, latency_s, tokens, usefulness]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prefix", default="baseline", help="experiment name prefix")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "radar-agents")
    client = Client()
    dataset = ensure_dataset(client)
    results = client.evaluate(
        target,
        data=dataset,
        evaluators=EVALUATORS,
        experiment_prefix=args.prefix,
        max_concurrency=args.concurrency,
        metadata={"profile": os.environ.get("RADAR_PROFILE", "dev"), "judge": JUDGE_MODEL},
    )
    print(results.experiment_name)


if __name__ == "__main__":
    main()
