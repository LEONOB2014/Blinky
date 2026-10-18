# ruff: noqa: E501, N806, S603, S607  (one-off media build script, run by hand from the lake)
"""Assemble the v0.4 demo video: one segment per narration block, then concat and loudnorm.

    python3 build.py            # every block, then the final video
    python3 build.py b04 b08    # only those blocks (then re-run with no args to assemble)

Each segment lasts its narration (voice/fast/bNN.wav) plus a short lead and tail. Visual cues inside a block are
placed by the character position of a phrase in the narration (an estimate of when it is spoken).
"""

import json
import subprocess
import sys
from pathlib import Path

V = Path(__file__).parent.resolve()
G, C, OUT = V / "gfx" / "png", V / "clips", V / "build"
AV = (V / ".." / "avatar").resolve()
OUT.mkdir(exist_ok=True)
DUR = json.loads((V / "voice" / "fast" / "durations.json").read_text())
TEXT = {b["id"]: b["text"] for b in json.loads((V / "agents" / "script_final.json").read_text())}
LEAD, TAIL, FADE = 0.25, 0.65, 0.4
BG = "0x10172C"  # the avatar images' own background
ENC = [
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-r",
    "30",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-ar",
    "48000",
    "-ac",
    "2",
]


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def dur(b):
    return round(LEAD + DUR[b] + TAIL, 3)


def cue(b, phrase):
    t = TEXT[b]
    return round(LEAD + t.index(phrase) / len(t) * DUR[b], 2)


def ease(f0, f1):
    u = f"clip((on-{f0})/{max(f1 - f0, 1)},0,1)"
    return f"({u}*{u}*(3-2*{u}))"


def rect_zoom(t0, t1, x, y, w, iw=1920):
    """zoompan from the full frame to the rect (x, y, w x w*9/16), eased between t0 and t1 (seconds)."""
    p = ease(int(t0 * 30), int(t1 * 30))
    return f"zoompan=z='{iw}/({iw}-{p}*{iw - w})':x='{p}*{x}':y='{p}*{y}':d=1:s=1920x1080:fps=30"


def slow_zoom(n, z0, z1, cx=0.5, cy=0.5):
    """Linear zoom z0 -> z1 over n frames around (cx, cy), on a 2x upscaled frame for smooth motion."""
    return (
        f"scale=3840:2160,zoompan=z='{z0}+({z1}-{z0})*on/{n}':x='(iw-iw/zoom)*{cx}':y='(ih-ih/zoom)*{cy}'"
        ":d=1:s=1920x1080:fps=30"
    )


def mux(b, inputs, graph, vout):
    """Encode a segment: inputs (list of ffmpeg args), filter graph producing [vout]; adds the narration."""
    d = dur(b)
    n = sum(1 for a in inputs if a == "-i")
    graph += (
        f";[{vout}]trim=start=0:end={d},setpts=PTS-STARTPTS,fade=in:st=0:d=0.25:c=0x0F152B,"
        f"fade=out:st={d - 0.3}:d=0.3:c=0x0F152B[vfin]"
        f";[{n}:a]adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},apad,atrim=start=0:end={d}[afin]"
    )
    run(
        [
            *inputs,
            "-i",
            str(V / "voice" / "fast" / f"{b}.wav"),
            "-filter_complex",
            graph,
            "-map",
            "[vfin]",
            "-map",
            "[afin]",
            "-t",
            str(d),
            *ENC,
            str(OUT / f"{b}.mp4"),
        ]
    )
    print(b, d)


def still(png, d):
    return ["-loop", "1", "-framerate", "30", "-t", str(d), "-i", str(png)]


def overlays(base, caps, first_input):
    """Overlay transparent PNG captions [(png, t_in, t_out)] on [base], fading their alpha; returns graph, label."""
    g, cur = [], base
    for k, (_, t_in, t_out) in enumerate(caps):
        i = first_input + k
        g.append(
            f"[{i}:v]format=rgba,fade=in:st={t_in}:d=0.45:alpha=1,fade=out:st={t_out - 0.45}:d=0.45:alpha=1[c{k}]"
        )
        g.append(f"[{cur}][c{k}]overlay=0:0:format=auto[o{k}]")
        cur = f"o{k}"
    return g, cur


# ---------- avatar shots ----------
def avatar_shot(name, img, d, offx, motion, overlay_png=None, flash=False):
    """One still-avatar shot rendered to build/shots/<name>.mp4 (no audio)."""
    shots = OUT / "shots"
    shots.mkdir(exist_ok=True)
    n = int(d * 30)
    ins = ["-f", "lavfi", "-i", f"color=c={BG}:s=1920x1080:r=30:d={d}", *still(AV / img, d)]
    if motion == "shake":
        g = [
            "[1:v]scale=1934:1080,setsar=1[a]",
            f"[0:v][a]overlay=x='{offx}+18*sin(t*48)*exp(-2.2*t)':y='12*cos(t*41)*exp(-2.2*t)'[m]",
        ]
    else:
        g = ["[1:v]scale=1934:1080,setsar=1[a]", f"[0:v][a]overlay={offx}:0[b]"]
        if motion == "in":
            g.append(f"[b]{slow_zoom(n, 1.0, 1.07, 0.3, 0.45)}[m]")
        elif motion == "out":
            g.append(f"[b]{slow_zoom(n, 1.08, 1.0, 0.3, 0.45)}[m]")
        elif motion == "punch":
            g.append(
                "[b]scale=3840:2160,zoompan=z='1+0.16*exp(-on/7)':x='(iw-iw/zoom)*0.3':y='(ih-ih/zoom)*0.45'"
                ":d=1:s=1920x1080:fps=30[m]"
            )
    cur = "m"
    if flash:
        ins += ["-f", "lavfi", "-i", f"color=c=white:s=1920x1080:r=30:d={d}"]
        g.append(f"[2:v]format=rgba,fade=out:st=0:d=0.4:alpha=1[w];[{cur}][w]overlay[fl]")
        cur = "fl"
    if overlay_png:
        k = sum(1 for a in ins if a == "-i")
        ins += still(G / f"{overlay_png}.png", d)
        g.append(f"[{k}:v]format=rgba,fade=in:st=0.2:d=0.45:alpha=1[t];[{cur}][t]overlay[ov]")
        cur = "ov"
    g.append(f"[{cur}]trim=start=0:end={d},setpts=PTS-STARTPTS,format=yuv420p[v]")
    out = shots / f"{name}.mp4"
    run(
        [
            *ins,
            "-filter_complex",
            ";".join(g),
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-r",
            "30",
            str(out),
        ]
    )
    return out


def xstack(n_inputs_before, lens, transitions):
    """Cross-dissolve consecutive inputs (ffmpeg 4.2 has no xfade): each later shot is shifted to its offset and
    faded (or slid) in over the previous ones. Each len includes FADE except the last; returns graph, label."""
    total = sum(lens) - FADE * (len(lens) - 1)
    g = [f"color=c=0x0F152B:s=1920x1080:r=30:d={total:.3f}[bg0]"]
    cur, off = "bg0", 0.0
    for i, ln in enumerate(lens):
        idx = n_inputs_before + i
        tr = transitions[i - 1] if i else "cut"
        g.append(
            f"[{idx}:v]format=yuva420p,setpts=PTS-STARTPTS+{off:.3f}/TB"
            + (f",fade=in:st={off:.3f}:d={FADE}:alpha=1" if tr == "fade" else "")
            + f"[s{i}]"
        )
        x = (
            f"'if(lt(t,{off + FADE:.3f}),1920*(1-(t-{off:.3f})/{FADE}),0)'"
            if tr == "slide"
            else "0"
        )
        g.append(f"[{cur}][s{i}]overlay=x={x}:y=0:eof_action=pass[m{i}]")
        cur = f"m{i}"
        off += ln - FADE
    return g, cur


def xchain(files, lens, transitions):
    ins = []
    for f in files:
        ins += ["-i", str(f)]
    g, cur = xstack(0, lens, transitions)
    return ins, g, cur


def spans(b, cues):
    """Shot lengths from cue times (first shot starts at 0); every shot but the last gets the FADE overlap."""
    edges = [0.0, *cues, dur(b)]
    lens = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    return [x + FADE if i < len(lens) - 1 else x for i, x in enumerate(lens)]


def b01():
    b = "b01"
    cs = [cue(b, "Veníamos"), cue(b, "y el reto"), cue(b, "¿No te lo"), cue(b, "Así que")]
    L = spans(b, cs)
    files = [
        avatar_shot("b01_1", "f1_blinky_calm.png", L[0], -230, "in", "intro_0"),
        avatar_shot("b01_2", "f1_blinky_calm.png", L[1], -230, "out", "intro_1"),
        avatar_shot("b01_3", "f2_blinky_shock.png", L[2], -230, "shake", "intro_2"),
        avatar_shot("b01_4", "f3_blinky_explode.png", L[3], -230, "punch", "intro_3", flash=True),
        avatar_shot("b01_5", "f4_blinky_radar.png", L[4], -260, "in", "intro_4"),
    ]
    ins, g, cur = xchain(files, L, ["fade", "slide", "cut", "fade"])
    mux(b, ins, ";".join(g) if g else "", cur)


def b11():
    b = "b11"
    d = dur(b)
    c = cue(b, "Radar de Señal Temprana")
    shot = avatar_shot("b11_av", "f4_blinky_radar.png", d, -260, "in")
    ins = ["-i", str(shot), *still(G / "closing_0.png", d), *still(G / "closing_1.png", d)]
    g, cur = overlays("0:v", [("closing_0", 0.3, c + 0.45), ("closing_1", c, d + 1)], 1)
    mux(b, ins, ";".join(g), cur)


# ---------- cards revealed in steps ----------
def card_block(b, prefix, phrases):
    cs = [cue(b, p) for p in phrases]
    L = spans(b, cs)
    ins = []
    for k, ln in enumerate(L):
        ins += still(G / f"{prefix}_{k}.png", ln)
    g, cur = xstack(0, L, ["fade"] * (len(L) - 1))
    g.append(f"[{cur}]{slow_zoom(int(dur(b) * 30), 1.0, 1.035)}[z]")
    mux(b, ins, ";".join(g), "z")


# ---------- app clips, retimed, with zooms and captions ----------
def app_block(b, pieces, zoom=None, caps=()):
    """pieces: [(clip, start, end, stretch)]; zoom: (t0, t1, x, y, w) or None; caps: [(png, t_in, t_out)]."""
    d = dur(b)
    ins, g = [], []
    for i, (clip, s, e, k) in enumerate(pieces):
        # input seeking: the trim filter's start is not honoured on these clips by ffmpeg 4.2
        ins += ["-ss", str(s), "-t", str(round(e - s, 3)), "-i", str(C / f"{clip}.mp4")]
        if k < 1:  # speed-up by keeping every n-th frame (fps in 4.2 pads to the unscaled EOF time)
            g.append(f"[{i}:v]select='not(mod(n\\,{round(1 / k)}))',setpts=N/30/TB,setsar=1[p{i}]")
        else:
            g.append(f"[{i}:v]setpts=(PTS-STARTPTS)*{k},fps=30,setsar=1[p{i}]")
    g.append(
        "".join(f"[p{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0,"
        f"tpad=stop_mode=clone:stop_duration={d},trim=start=0:end={d},setpts=PTS-STARTPTS[raw]"
    )
    cur = "raw"
    if zoom:
        g.append(f"[raw]{rect_zoom(*zoom)}[zm]")
        cur = "zm"
    n = len(pieces)
    for png, _, _ in caps:
        ins += still(G / f"{png}.png", d)
    og, cur = overlays(cur, list(caps), n)
    mux(b, ins, ";".join(g + og), cur)


def b04():
    b = "b04"
    app_block(
        b,
        [("01_default", 0, 5, 1.5), ("02_card_ring", 0, 9, 1.5)],
        caps=[
            ("cap_despegando", 0.6, cue(b, "Un clic")),
            ("cap_ring", cue(b, "Un clic") + 0.3, dur(b) - 0.2),
        ],
    )


def b05():
    b = "b05"
    app_block(
        b,
        [("03_leaders", 0, 7.95, 1.0)],
        zoom=(8.6, 10.8, 0, 60, 1000),
        caps=[("cap_leaders", 1.6, 8.4)],
    )


def b06():
    b = "b06"
    app_block(
        b,
        [
            ("04_play", 0, 10.95, 1.0),
            ("05_lenses", 0.1, 2.2, 1.4),
            ("05_lenses", 2.2, 4.3, 1.4),
            ("05_lenses", 10.6, 12.7, 2.0),
        ],
        caps=[("cap_graph", 0.8, dur(b) - 0.2)],
    )


def b07():
    b = "b07"
    app_block(
        b,
        [
            ("05_lenses", 6.4, 8.5, 2.5),
            ("05_lenses", 4.3, 6.4, 2.5),
            ("05_lenses", 8.5, 10.6, 2.5),
            ("05_lenses", 12.7, 14.8, 2.5),
            ("05_lenses", 14.8, 17.5, 2.5),
        ],
        caps=[("cap_lenses", cue(b, "Y el radar convierte"), dur(b) - 0.2)],
    )


def b08():
    b = "b08"
    app_block(
        b,
        [("07_chat", 0, 5, 1.0), ("07_chat", 5, 19, 1 / 7), ("07_chat", 19, 35, 1.0)],
        zoom=(7.6, 9.0, 1060, 520, 860),
        caps=[("cap_chat", 0.5, 7.4)],
    )


def b09():
    b = "b09"
    app_block(
        b,
        [("06_trust", 0, 7.0, 1.0)],
        zoom=(2.2, 3.6, 1110, 60, 810),
        caps=[("cap_trust", 0.3, 2.3)],
    )


BLOCKS = {
    "b01": b01,
    "b02": lambda: card_block(
        "b02",
        "chain",
        [
            "Primero aparecen",
            "luego en las noticias",
            "después en Google",
            "Solo al final",
            "Si observas",
        ],
    ),
    "b03": lambda: card_block(
        "b03", "gdelt", ["extrae", "Se actualiza", "Aquí clasificamos", "en BigQuery", "Su valor"]
    ),
    "b04": b04,
    "b05": b05,
    "b06": b06,
    "b07": b07,
    "b08": b08,
    "b09": b09,
    "b10": lambda: card_block("b10", "eng", ["desplegado", "ciento treinta", "trazas", "El costo"]),
    "b11": b11,
}


def assemble():
    lst = OUT / "concat.txt"
    lst.write_text("".join(f"file '{OUT / f'{b}.mp4'}'\n" for b in BLOCKS))
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(OUT / "joined.mp4")])
    final = V / "radar_demo_v04.mp4"
    run(
        [
            "-i",
            str(OUT / "joined.mp4"),
            "-c:v",
            "copy",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    print("final", final)


if __name__ == "__main__":
    want = sys.argv[1:] or list(BLOCKS)
    for name in want:
        BLOCKS[name]()
    if not sys.argv[1:]:
        assemble()
