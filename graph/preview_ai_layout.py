"""Offline preview of the AI temporal graph: one week as an SVG, with the UI's visual rules.

Used to tune the layout and the size, colour and width rules without a WebGL browser:
    uv run python -m graph.preview_ai_layout lake/views/temporal.json out.svg [--week -1]
Node size 6 + 26·sqrt(importance), family colour, edge width 0.6 + 1.6·log1p(n), edge alpha by
NPMI, frameless labels with a dark halo for the nodes the export marks show_label.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path


def render(data: dict, week: int, size: int = 1400) -> str:
    meta = data["_meta"]
    colours = {f["id"]: f["color"] for f in meta.get("family_legend", [])}
    nodes = data["nodes"]
    e = data["edges"]
    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0) or 1.0
    pad = 60

    def sx(x: float) -> float:
        return pad + (x - x0) / span * (size - 2 * pad)

    def sy(y: float) -> float:
        return pad + (y - y0) / span * (size - 2 * pad)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'style="font-family:Inter,Helvetica,sans-serif">'
        f'<rect width="100%" height="100%" fill="#0f172a"/>'
    ]
    present = set()
    for i in range(len(e["week"])):
        if e["week"][i] != week:
            continue
        u, v = e["source"][i], e["target"][i]
        present.update((u, v))
        n_val, npmi = e["n"][i], e["npmi"][i] or 0.1
        width = min(9.0, 0.6 + 1.6 * math.log1p(n_val))
        alpha = 0.25 + 0.7 * min(1.0, max(0.0, (npmi - 0.1) / 0.6))
        col = colours.get(nodes[u].get("family"), "#94a3b8")
        out.append(
            f'<line x1="{sx(nodes[u]["x"]):.1f}" y1="{sy(nodes[u]["y"]):.1f}" '
            f'x2="{sx(nodes[v]["x"]):.1f}" y2="{sy(nodes[v]["y"]):.1f}" stroke="{col}" '
            f'stroke-opacity="{alpha:.2f}" stroke-width="{width:.1f}" stroke-linecap="round"/>'
        )
    order = sorted(range(len(nodes)), key=lambda i: nodes[i]["importance"][week] or 0.0)
    for i in order:
        n = nodes[i]
        imp = n["importance"][week] or 0.0
        r = (6 + 26 * math.sqrt(imp)) / 2
        col = colours.get(n.get("family"), "#94a3b8")
        op = 0.95 if i in present else 0.35
        out.append(
            f'<circle cx="{sx(n["x"]):.1f}" cy="{sy(n["y"]):.1f}" r="{r:.1f}" fill="{col}" '
            f'fill-opacity="{op}" stroke="#0f172a" stroke-width="1.5"/>'
        )
    for i in order:
        n = nodes[i]
        if not n.get("show_label"):
            continue
        imp = n["importance"][week] or 0.0
        r = (6 + 26 * math.sqrt(imp)) / 2
        fs = 11 + 4 * imp
        label = html.escape(n.get("label_es") or n["id"])
        out.append(
            f'<text x="{sx(n["x"]) + r + 4:.1f}" y="{sy(n["y"]) + fs / 3:.1f}" '
            f'font-size="{fs:.1f}" '
            f'font-weight="600" fill="#f1f5f9" stroke="#0f172a" stroke-width="3" '
            f'paint-order="stroke">{label}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("temporal_json")
    ap.add_argument("out_svg")
    ap.add_argument("--week", type=int, default=-1)
    args = ap.parse_args()
    data = json.loads(Path(args.temporal_json).read_text(encoding="utf-8"))
    week = args.week % len(data["_meta"]["weeks"])
    Path(args.out_svg).write_text(render(data, week), encoding="utf-8")


if __name__ == "__main__":
    main()
