# ruff: noqa: B905, E501, S603, S607  (one-off media build script, run by hand from the lake)
"""Encode each recorded scene (timestamped JPEG frames) to a 1080p 30 fps H.264 clip with its real timing."""

import json
import subprocess
import sys
from pathlib import Path

raw, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
for scene in sorted(p for p in raw.iterdir() if p.is_dir()):
    stamps = json.loads((scene / "stamps.json").read_text())
    lines = []
    for (i, t), nxt in zip(stamps, stamps[1:] + [None]):
        dur = (nxt[1] - t) / 1000 if nxt else 0.04
        lines += [f"file '{scene}/f{i:04d}.jpg'", f"duration {dur:.3f}"]
    lines.append(f"file '{scene}/f{stamps[-1][0]:04d}.jpg'")
    lst = scene / "list.txt"
    lst.write_text("\n".join(lines) + "\n")
    dst = out / f"{scene.name}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-vf",
            "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(dst),
        ],
        check=True,
    )
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
                str(dst),
            ]
        )
    )
    print(f"{dst.name}: {d:.1f} s, {dst.stat().st_size / 1e6:.1f} MB")
