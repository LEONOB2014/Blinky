"""Summarise a graph/views/e2e_ai_matrix.mjs run into the pass/fail table.

    python3 graph/views/e2e_ai_matrix.py /tmp/e2e

A lens-week cell passes with no console error or warning, no non-finite node position, a drawn
canvas (labels and legend are hidden for its screenshot, so only WebGL marks count), every one of
that week's top 10 labelled, and the week badge on the week that was set. Uses ffmpeg to read
the screenshots. Exits 1 when a cell or a play run fails.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

MIN_DRAWN = 0.004  # share of sampled canvas pixels that differ from the background
BACKGROUND = (15, 23, 42)  # #0f172a
DIFF = 30  # summed RGB distance from the background that counts as a mark
FFPROBE = shutil.which("ffprobe") or "ffprobe"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def drawn_share(png: str) -> float:
    """Share of sampled pixels (every 2nd row and column) that differ from the background."""
    size = subprocess.check_output(  # noqa: S603 - fixed ffprobe arguments
        [FFPROBE, "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", png]
    )
    w, h = (int(v) for v in size.decode().strip().split(","))
    raw = subprocess.check_output(  # noqa: S603 - fixed ffmpeg arguments
        [FFMPEG, "-v", "error", "-i", png, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    )
    marks = total = 0
    for y in range(0, h, 2):
        row = raw[y * w * 3 : (y + 1) * w * 3]
        for x in range(0, w * 3, 6):
            total += 1
            dist = sum(abs(row[x + k] - BACKGROUND[k]) for k in range(3))
            marks += dist > DIFF
    return marks / total if total else 0.0


def problems(cell: dict) -> list[str]:
    out = []
    if cell["errors"]:
        out.append(f"{len(cell['errors'])} errors")
    if cell.get("nan"):
        out.append(f"{cell['nan']} non-finite")
    if cell["drawn"] < MIN_DRAWN:
        out.append("blank canvas")
    if cell["top10_labelled"] < cell["top10_total"]:
        out.append(f"top10 {cell['top10_labelled']}/{cell['top10_total']}")
    if cell["badge"] != cell["week"]:
        out.append(f"badge {cell['badge']}")
    return out


def main(run: Path) -> int:
    m = json.loads((run / "matrix.json").read_text(encoding="utf-8"))
    for cell in m["rows"]:
        cell["drawn"] = drawn_share(cell["file"])
        cell["problems"] = problems(cell)
    lenses = list(dict.fromkeys(c["lens"] for c in m["rows"]))
    print("| Lens | " + " | ".join(w[-3:] for w in m["weeks"]) + " |")
    print("|---" * (len(m["weeks"]) + 1) + "|")
    for lens in lenses:
        cells = [c for c in m["rows"] if c["lens"] == lens]
        marks = [
            ("pass" if not c["problems"] else "FAIL") + f" {c['top10_labelled']}/{c['top10_total']}"
            for c in cells
        ]
        print(f"| {lens} | " + " | ".join(marks) + " |")
    fails = [c for c in m["rows"] if c["problems"]]
    print(
        f"\ncells {len(m['rows'])}, failing {len(fails)}; "
        f"lowest drawn share {min(c['drawn'] for c in m['rows']):.3f}; "
        f"non-finite {max(c['nan'] or 0 for c in m['rows'])}; "
        f"errors {sum(len(c['errors']) for c in m['rows'])}"
    )
    for c in fails:
        print("  FAIL", c["lens"], c["week"], c["problems"], c.get("missing_top10"))
    for p in m["play"]:
        print(
            f"play {p['lens']}: ends {p['end_week']}, {p['fps']} fps, "
            f"non-finite {p['nan']}, errors {len(p['errors'])}"
        )
    for s in m["sel"]:
        print(
            f"select {s['topic']} at {s['week_set']} (badge {s['badge']}, via {s['how']}): "
            f"focus labelled {s['focus_labelled']}, {s['labels']} labels, errors {len(s['errors'])}"
        )
    print(f"log entries in the run: {len(m['all_logs'])}")
    for line in dict.fromkeys(m["all_logs"]):
        print("  ", line)
    return 1 if fails or any(p["errors"] for p in m["play"]) else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
