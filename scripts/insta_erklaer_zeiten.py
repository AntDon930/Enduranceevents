"""Trägt `zeiten` und `teile` in eine Erklär-Reel-Vorlage ein – aus der
Sprecheraufnahme (<thema>.mp3 neben der Vorlage).

    python3 scripts/insta_erklaer_zeiten.py marketing/instagram/erklaer/<thema>.json [--stuecke 2,3,1,…]

Die Sprechpausen misst `ffmpeg … silencedetect`. Szenenwechsel ist die Pause, an der
der Anteil der Sprechzeit zum Anteil der Zeichen passt; die
Wörter einer Szene werden an Satzzeichen so auf ihre Stücke verteilt, dass
die Längen am besten passen. Das Ergebnis ausgeben lassen und ANSEHEN – bei
einer verschluckten Pause stimmt die Zuordnung nicht; dann mit `--stuecke`
die Zahl der Sprechstücke je Szene vorgeben (die Stücke zeigt `stuecke()`).
"""
from __future__ import annotations

import itertools
import json
import re
import subprocess
import sys
from pathlib import Path


def stuecke(mp3: Path, laut: str = "-35dB", pause: float = 0.15) -> tuple[list[list[float]], float]:
    aus = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp3), "-af", f"silencedetect=noise={laut}:d={pause}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    dauer = re.search(r"Duration: (\d+):(\d+):([\d.]+)", aus)
    gesamt = int(dauer[1]) * 3600 + int(dauer[2]) * 60 + float(dauer[3])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", aus)]
    enden = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", aus)]
    teile, t = [], 0.0
    for i, s in enumerate(starts):
        if s - t > 0.12:
            teile.append([round(t, 2), round(s, 2)])
        t = enden[i] if i < len(enden) else gesamt
    if gesamt - t > 0.12:
        teile.append([round(t, 2), round(gesamt, 2)])
    return teile, gesamt


def verteile(woerter: list[str], teile: list[list[float]]) -> list[list]:
    """Wörter an Satzzeichen auf die Sprechstücke verteilen."""
    k = len(teile)
    grenzen = [i + 1 for i, w in enumerate(woerter[:-1]) if w[-1] in ".,?!:;"]
    while k > 1 and len(grenzen) < k - 1:          # mehr Pausen als Satzzeichen: Stücke zusammenlegen
        j = min(range(k - 1), key=lambda i: teile[i + 1][0] - teile[i][1])
        teile = teile[:j] + [[teile[j][0], teile[j + 1][1]]] + teile[j + 2:]
        k -= 1
    zeichen = [len(w) + 1 for w in woerter]
    dauer = [b - a for a, b in teile]
    beste, fehler = (), 1e9
    for wahl in itertools.combinations(grenzen, k - 1):
        r = [0, *wahl, len(woerter)]
        anteile = [sum(zeichen[r[i]:r[i + 1]]) / sum(zeichen) for i in range(k)]
        f = sum(abs(a - d / sum(dauer)) for a, d in zip(anteile, dauer))
        if f < fehler:
            beste, fehler = wahl, f
    r = [0, *beste, len(woerter)]
    return [[teile[i][0], teile[i][1], r[i + 1] - r[i]] for i in range(k)]


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    vorlage = Path(args[0])
    fest = [int(x) for x in args[2].split(",")] if len(args) > 2 and args[1] == "--stuecke" else None
    spec = json.loads(vorlage.read_text(encoding="utf-8"))
    alle, gesamt = stuecke(vorlage.with_suffix(".mp3"))
    n = len(spec["szenen"])
    # Szenenwechsel: die Pause, an der der Anteil der gesprochenen Zeit am besten
    # zum Anteil der Zeichen passt; eine längere Pause gewinnt bei Gleichstand.
    zeichen = [len(x["text"]) for x in spec["szenen"]]
    sprech = [b - a for a, b in alle]
    schnitte, ab = [], 0
    for i in range(n - 1):
        ziel = sum(zeichen[:i + 1]) / sum(zeichen)
        wahl = range(ab, len(alle) - (n - 1 - i))
        j = min(wahl, key=lambda j: abs(sum(sprech[:j + 1]) / sum(sprech) - ziel)
                - 0.03 * (alle[j + 1][0] - alle[j][1]))
        schnitte.append(j)
        ab = j + 1
    if fest:                                        # von Hand: Zahl der Sprechstücke je Szene
        if len(fest) != n or sum(fest) != len(alle):
            raise SystemExit(f"--stuecke: {n} Zahlen mit Summe {len(alle)} erwartet")
        schnitte = [sum(fest[:i + 1]) - 1 for i in range(n - 1)]
    gruppen, a = [], 0
    for i in schnitte + [len(alle) - 1]:
        gruppen.append(alle[a:i + 1])
        a = i + 1
    zeiten, von = [], 0.0
    for i, (s, g) in enumerate(zip(spec["szenen"], gruppen)):
        bis = round((g[-1][1] + gruppen[i + 1][0][0]) / 2, 2) if i + 1 < n else round(gesamt + 0.15, 2)
        s["teile"] = verteile(s["text"].split(), g)
        zeiten.append([von, bis])
        von = bis
        print(f"{von:6.2f}  {s['bild']:10s} " + " | ".join(
            f"{t[1] - t[0]:.1f}s:{t[2]}W" for t in s["teile"]) + f"   {s['text'][:50]}")
    spec["zeiten"] = zeiten
    spec["stimme"] = (f"Dennis (Runway, voiceId bGkjVHUyQ9rRhorWJufM, Tempo 1,08) – "
                      f"{vorlage.stem}.mp3 neben dieser Datei")
    vorlage.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
