"""Write the scored ISO weeks the demo week selector can offer.

The list is the radar JSON already copied into ``web/public/data/radar/``.
The output is git-ignored with the rest of ``web/public/data/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WEEK = re.compile(r"^\d{4}-W\d{2}$")


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    radar = repo / "web" / "public" / "data" / "radar"
    weeks = sorted(path.stem for path in radar.glob("*.json") if WEEK.match(path.stem))
    radar.mkdir(parents=True, exist_ok=True)
    (radar / "weeks.json").write_text(
        json.dumps({"weeks": weeks}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
