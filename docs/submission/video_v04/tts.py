# ruff: noqa: E501, PTH123, RET503, S310, S603, S607, SIM115  (one-off media build script, run by hand from the lake)
"""One ElevenLabs take per block (voice BRIAN C. 2, eleven_multilingual_v2), with the neighbours' text for continuity."""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

V = Path(__file__).parent
MODEL = "eleven_multilingual_v2"
VOICE = "cjVigY5qzO86Huf0OWal"  # Eric (premade): library voices need a paid plan


def key():
    for line in open("/Users/andresbecerra/Documents/30x_Blinky/radar/.env", encoding="utf-8-sig"):
        m = re.match(r"\s*ELEVENLABS_API_KEY\s*=\s*(\S+)", line)
        if m:
            return m.group(1).strip().strip("\"'")


s = json.loads((V / "agents" / "script_final.json").read_text())
only = set(sys.argv[1:])
durs = {}
for k, b in enumerate(s):
    out = V / "voice" / f"{b['id']}.mp3"
    if not only or b["id"] in only:
        body = {
            "text": b["text"],
            "model_id": MODEL,
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.8,
                "style": 0.25,
                "use_speaker_boost": True,
            },
        }
        if k > 0:
            body["previous_text"] = s[k - 1]["text"]
        if k + 1 < len(s):
            body["next_text"] = s[k + 1]["text"]
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": key(), "Content-Type": "application/json"},
        )
        out.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    durs[b["id"]] = float(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(out),
            ]
        )
    )
    print(f"{b['id']}: {durs[b['id']]:.1f} s, {len(b['text'])} chars")
(V / "voice" / "durations.json").write_text(json.dumps(durs, indent=1))
print(f"total {sum(durs.values()):.1f} s, {sum(len(b['text']) for b in s)} chars")
