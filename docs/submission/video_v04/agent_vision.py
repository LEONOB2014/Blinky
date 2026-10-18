# ruff: noqa: E501, S603, S607  (one-off media build script, run by hand from the lake)
"""Vision agent: describe what each recorded clip shows, from three key frames (start, middle, end)."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nebius import chat, image_part

V = Path(__file__).parent
MODEL = "nvidia/Nemotron-3.5-Super-VL"
out = {}
for clip in sorted((V / "clips").glob("*.mp4")):
    d = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(clip),
            ]
        )
    )
    frames = []
    for k, t in enumerate((0.3, d / 2, max(0.3, d - 0.4))):
        f = V / "keyframes" / f"{clip.stem}_{k}.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{t:.2f}",
                "-i",
                str(clip),
                "-frames:v",
                "1",
                "-vf",
                "scale=1280:-1",
                str(f),
            ],
            check=True,
        )
        frames.append(f)
    msg = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Three frames (start, middle, end) of a screen recording of a web app, 'Radar de Señal Temprana', which ranks AI topics and draws them as a graph. "
                    "In Spanish, in 4-6 short bullet points: what the viewer sees change from start to end (which panel, which list, which lens or button, what appears). "
                    "Describe only what is visible; do not invent numbers that are not legible; no opinions.",
                }
            ]
            + [image_part(f) for f in frames],
        }
    ]
    out[clip.stem] = {
        "duration_s": round(d, 1),
        "seen": chat(MODEL, msg, max_tokens=3000, temperature=0.2),
    }
    print(f"== {clip.stem} ({d:.1f} s)\n{out[clip.stem]['seen']}\n")
(V / "agents" / "vision.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
