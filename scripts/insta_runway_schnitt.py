#!/usr/bin/env python3
"""Schneidet ein Reel aus Runway-Clips, einer Sprachaufnahme und eigenen
Einblendungen zusammen.

Runway liefert nur die Bilder und die Stimme (siehe
`marketing/instagram/runway/<thema>.md`); Schrift, Farben (Soft Blue /
Midnight Navy / Coral) und ein leiser Beat kommen von uns – KI-Videos
schreiben deutschen Text unzuverlässig, und so bleibt der Look gleich.

Die Vorlage ist `marketing/instagram/runway/<thema>.json`:

    {"stimme": "<mp3>", "beat_seed": 7, "szenen": [
       {"clip": "<mp4>", "von": 0, "bis": 4.1,
        "texte": [{"text": "…", "von": 0.1, "bis": 2.0, "art": "gross"}]}]}

`von`/`bis` der Szene sind Zeiten im fertigen Reel (Schnitte in die
Sprechpausen legen); ist der Clip kürzer als die Szene, läuft er
entsprechend langsamer (höchstens 1,4-fach), sonst wird er gekürzt.
Clip- und Stimmdateien liegen nicht im Repo (zu groß); `--medien` nennt
den Ordner, sonst gilt der Ordner der JSON-Datei. Arten der Einblendung: `gross`
(Kondensiert, Versalien), `text` (Barlow), `liste` (eine Zeile einer
Aufzählung, bleibt bis `bis` stehen und rückt unter die vorige), `klein`.

    python3 scripts/insta_runway_schnitt.py marketing/instagram/runway/tapering.json \
        --medien <ordner mit clips> --aus reel.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insta_musik  # noqa: E402
from insta_video import kondensiert, text_schrift, umbrechen  # noqa: E402

B, H = 1080, 1920
RAND = 72
MIDNIGHT = (0, 41, 65)
CORAL = (253, 110, 110)
SOFT_BLUE = (182, 223, 237)
WEISS = (255, 255, 255)
OBEN = 330          # Einblendungen im oberen Drittel – unten liegt die Reels-Leiste
MAX_LANGSAM = 1.4
BEAT_PEGEL = 0.16   # leise unter der Stimme


def dauer(datei: Path) -> float:
    aus = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(datei)], capture_output=True, text=True, check=True).stdout
    return float(aus.strip())


def _kasten(text: str, art: str) -> Image.Image:
    """Ein Textkasten (RGBA): Midnight-Navy-Fläche mit Coral-Kante links."""
    if art == "gross":
        f, zh = kondensiert(84), 86
        zeilen = umbrechen(text.upper(), f, B - 2 * RAND - 80)
    elif art == "klein":
        f, zh = text_schrift(40, True), 50
        zeilen = umbrechen(text, f, B - 2 * RAND - 80)
    else:
        f, zh = text_schrift(50, True), 62
        zeilen = umbrechen(text, f, B - 2 * RAND - 80)
    w = max(int(f.getlength(z)) for z in zeilen) + 80
    h = len(zeilen) * zh + 44
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=22, fill=MIDNIGHT + (232,))
    d.rounded_rectangle([0, 0, 12, h - 1], radius=6, fill=CORAL + (255,))
    y = 22
    for z in zeilen:
        d.text((44, y), z, font=f, fill=WEISS)
        y += zh
    return img


def einblendungen(szenen: list[dict], arbeit: Path) -> list[tuple[Path, float, float, int]]:
    """PNG je Einblendung mit Position: (Datei, von, bis, y)."""
    aus = []
    n = 0
    for s in szenen:
        y = OBEN
        for t in s.get("texte", []):
            bild = _kasten(t["text"], t.get("art", "text"))
            if t.get("art") != "liste":
                y = OBEN
            datei = arbeit / f"t{n:02d}.png"
            bild.save(datei)
            aus.append((datei, t["von"], t["bis"], y))
            n += 1
            y += bild.height + 18
    return aus


def schneide(vorlage: Path, ziel: Path, medien: Path | None = None) -> float:
    spec = json.loads(vorlage.read_text(encoding="utf-8"))
    basis = medien or vorlage.parent
    szenen = spec["szenen"]
    stimme = (basis / spec["stimme"]).resolve()
    gesamt = max(szenen[-1]["bis"], dauer(stimme) + 0.4)
    szenen[-1]["bis"] = gesamt
    with tempfile.TemporaryDirectory() as tmp:
        arbeit = Path(tmp)
        teile = []
        for i, s in enumerate(szenen):
            clip = (basis / s["clip"]).resolve()
            soll = s["bis"] - s["von"]
            faktor = max(1.0, min(MAX_LANGSAM, soll / dauer(clip)))
            teil = arbeit / f"s{i}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-an", "-vf",
                 f"setpts={faktor:.4f}*PTS,scale={B}:{H}:force_original_aspect_ratio=increase,"
                 f"crop={B}:{H},fps=30,format=yuv420p",
                 "-t", f"{soll:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(teil)],
                check=True)
            teile.append(teil)
        (arbeit / "liste.txt").write_text("".join(f"file '{t}'\n" for t in teile), encoding="utf-8")
        roh = arbeit / "roh.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
                        str(arbeit / "liste.txt"), "-c", "copy", str(roh)], check=True)

        beat = arbeit / "beat.wav"
        insta_musik.schreibe_wav(beat, gesamt + 0.2, int(spec.get("beat_seed", 7)),
                                 schnitte=[s["von"] for s in szenen[1:]])

        texte = einblendungen(szenen, arbeit)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(roh), "-i", str(stimme), "-i", str(beat)]
        for datei, *_ in texte:
            cmd += ["-loop", "1", "-t", f"{gesamt:.2f}", "-i", str(datei)]
        filt, vor = [], "[0:v]"
        for k, (_, von, bis, y) in enumerate(texte):
            nach = f"[v{k}]"
            ein = f"[{k + 3}:v]format=rgba,fade=t=in:st={von:.2f}:d=0.25:alpha=1,fade=t=out:st={bis - 0.25:.2f}:d=0.25:alpha=1[e{k}]"
            filt.append(ein)
            filt.append(f"{vor}[e{k}]overlay=x={RAND}:y={y}:enable='between(t,{von:.2f},{bis:.2f})'{nach}")
            vor = nach
        filt.append(f"[1:a]adelay=150|150,volume=1.0[st];[2:a]volume={BEAT_PEGEL}[bt];"
                    f"[st][bt]amix=inputs=2:duration=longest:normalize=0[a]")
        cmd += ["-filter_complex", ";".join(filt), "-map", vor, "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{gesamt:.2f}", "-movflags", "+faststart", str(ziel)]
        subprocess.run(cmd, check=True)
    return gesamt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vorlage", type=Path)
    ap.add_argument("--aus", type=Path, required=True)
    ap.add_argument("--medien", type=Path, help="Ordner mit Clips und Stimme")
    a = ap.parse_args(argv)
    t = schneide(a.vorlage.resolve(), a.aus, a.medien.resolve() if a.medien else None)
    print(f"{a.aus} ({t:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
