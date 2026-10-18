"""Ask the Media Master from the terminal: `uv run python -m agents "¿qué publico esta semana?"`.

The full response (answer, cards, view commands, trace) is also written to lake/agent_traces/.
"""

import json
import sys

from agents.runtime import run_turn
from radar.paths import lake


def main() -> None:
    question = " ".join(sys.argv[1:]) or "¿Qué tema de IA está subiendo esta semana y por qué?"
    response = run_turn(question)
    out = lake() / "agent_traces" / f"{response['conversation_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"question": question} | response, ensure_ascii=False, indent=1))
    print(response["answer_es"])
    print("\n--- traza ---")
    for step in response["trace"]:
        print(
            step["step"],
            step["agent"],
            step["action"],
            step["tool"] or "",
            step["latency_ms"] or "",
        )
    print(
        f"\n{len(response['view_commands'])} vista(s), {len(response['decision_cards'])} tarjeta(s) -> {out}"
    )


if __name__ == "__main__":
    main()
