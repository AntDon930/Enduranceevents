#!/usr/bin/env python3
"""
scripts/insta_musik.py
======================

Ein eigener Beat für die Reels – selbst erzeugt, also ohne Lizenzfrage.
Die Musik aus der Instagram-Bibliothek lässt sich über die Schnittstelle
nicht an einen Beitrag hängen; ein stummes Reel wirkt tot, und fremde
Stücke bräuchten eine Lizenz (marketing/instagram/musik/musik.json, die
insta_video.musik_wahl() vorzieht, sobald dort eines mit Lizenz steht).

Der Beat ist einfacher elektronischer Pop: Bassdrum auf jedem Schlag,
Clap auf 2 und 4, Hi-Hat auf den Achteln, ein Bass auf den Grundtönen und
kurze Akkord-Stöße. Tempo, Tonart und Akkordfolge hängen am `seed` (dem
Datum) – jeder Tag klingt etwas anders, derselbe Tag immer gleich. Die
Folien schneiden im Takt (insta_video.zeitplan() rechnet in Schlägen).

Ohne numpy (der Actions-Runner hat es nicht): reines Python mit `array`
und `wave`, ~1–2 s Rechenzeit für 15 s Ton.
"""
from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path

RATE = 44100
BPM_AUSWAHL = (118, 122, 124, 126, 128)
# Akkordfolgen als Halbtöne über dem Grundton (Moll-Pop, vier Takte).
FOLGEN = (
    (0, 8, 3, 10),     # i – VI – III – VII  (Am F C G)
    (0, 5, 8, 10),     # i – iv – VI – VII   (Am Dm F G)
    (0, 10, 8, 10),    # i – VII – VI – VII
    (0, 3, 10, 5),     # i – III – VII – iv
)
GRUNDTOENE_HZ = (55.0, 58.27, 61.74, 65.41, 49.0)   # A1, Bb1, B1, C2, G1


def bpm_fuer(seed: int) -> int:
    return BPM_AUSWAHL[random.Random(seed).randrange(len(BPM_AUSWAHL))]


def schlag_s(bpm: int) -> float:
    return 60.0 / bpm


def _hz(grund: float, halbtoene: float) -> float:
    return grund * 2 ** (halbtoene / 12)


def _whoosh(seed: int) -> list[float]:
    """Rauschen, das in 0,35 s anschwillt und abreißt, mit wanderndem
    Tiefpass - der Luftzug zum Wisch-Übergang."""
    r = random.Random(seed * 31 + 7)
    aus, tief = [], 0.0
    n = int(0.42 * RATE)
    for i in range(n):
        p = i / n
        huelle = (p / 0.8) ** 2 if p < 0.8 else max(0.0, 1 - (p - 0.8) / 0.2)
        k = 0.02 + 0.25 * p                     # Filter öffnet sich: dunkel → hell
        tief += k * ((r.random() * 2 - 1) - tief)
        aus.append(0.55 * huelle * tief)
    return aus


def _impact() -> list[float]:
    """Tiefer Schlag mit kurzem Rauschen obendrauf (Start und Schluss)."""
    r = random.Random(99)
    aus = []
    for i in range(int(0.9 * RATE)):
        t = i / RATE
        phase = 2 * math.pi * (38 * t + 90 * (1 - math.exp(-t * 14)) / 14)
        v = 0.9 * math.sin(phase) * math.exp(-t * 3.2)
        v += 0.25 * (r.random() * 2 - 1) * math.exp(-t * 40)
        aus.append(v)
    return aus


def erzeuge(dauer_s: float, seed: int, bpm: int | None = None,
            schnitte: list[float] | None = None, schlusspunkt: float | None = None) -> tuple[array, int]:
    """Stereo-Samples (int16, abwechselnd links/rechts) und das Tempo.
    `schnitte`: Zeiten (s) der Wisch-Übergänge - dort ein Whoosh, der genau
    am Schnitt abreißt; zum Start und am `schlusspunkt` ein tiefer Schlag."""
    rng = random.Random(seed * 7919 + 13)
    bpm = bpm or bpm_fuer(seed)
    folge = FOLGEN[rng.randrange(len(FOLGEN))]
    grund = GRUNDTOENE_HZ[rng.randrange(len(GRUNDTOENE_HZ))]
    n = int(dauer_s * RATE)
    links = [0.0] * n
    rechts = [0.0] * n
    schlag = schlag_s(bpm)
    takt = 4 * schlag

    def addiere(start: int, werte, pan: float = 0.0) -> None:
        gl, gr = (1 - max(0.0, pan)), (1 + min(0.0, pan))
        for i, v in enumerate(werte):
            j = start + i
            if j >= n:
                break
            links[j] += v * gl
            rechts[j] += v * gr

    # Bausteine einmal rechnen, dann nur noch kopieren.
    kick = []
    for i in range(int(0.30 * RATE)):
        t = i / RATE
        phase = 2 * math.pi * (48 * t + 110 * (1 - math.exp(-t * 32)) / 32)
        kick.append(0.95 * math.sin(phase) * math.exp(-t * 9))
    clap = []
    r = random.Random(seed)
    for i in range(int(0.22 * RATE)):
        t = i / RATE
        huelle = math.exp(-t * 18) * (1.0 if t > 0.012 else 0.6)
        clap.append(0.32 * (r.random() * 2 - 1) * huelle)
    hat = []
    for i in range(int(0.05 * RATE)):
        t = i / RATE
        rausch = r.random() * 2 - 1
        hat.append(0.11 * rausch * math.exp(-t * 90))

    def bass(freq: float, laenge: float) -> list[float]:
        aus = []
        for i in range(int(laenge * RATE)):
            t = i / RATE
            huelle = min(1.0, t * 200) * math.exp(-t * 2.2)
            x = 2 * math.pi * freq * t
            aus.append(0.30 * huelle * (math.sin(x) + 0.35 * math.sin(2 * x)))
        return aus

    def stoss(freqs: list[float], laenge: float) -> list[float]:
        aus = []
        for i in range(int(laenge * RATE)):
            t = i / RATE
            huelle = min(1.0, t * 300) * math.exp(-t * 7)
            v = sum(math.sin(2 * math.pi * f * t) + 0.25 * math.sin(4 * math.pi * f * t) for f in freqs)
            aus.append(0.055 * huelle * v)
        return aus

    bass_cache: dict[int, list[float]] = {}
    stoss_cache: dict[int, list[float]] = {}
    schlaege = int(dauer_s / schlag) + 1
    for s in range(schlaege):
        t0 = s * schlag
        start = int(t0 * RATE)
        takt_nr = int(t0 // takt)
        stufe = folge[takt_nr % len(folge)]
        im_takt = s % 4
        # Der erste Takt ohne Bassdrum: ein kurzer Auftakt, dann setzt alles ein.
        if takt_nr > 0 or im_takt >= 2:
            addiere(start, kick)
        if im_takt in (1, 3):
            addiere(start, clap, pan=0.1)
        for achtel in (0, 1):
            addiere(start + int(achtel * schlag / 2 * RATE), hat, pan=-0.35 if achtel else 0.35)
        if stufe not in bass_cache:
            bass_cache[stufe] = bass(_hz(grund, stufe), schlag * 0.95)
        if takt_nr > 0:
            addiere(start + int(schlag / 2 * RATE), bass_cache[stufe])
        if im_takt in (0, 2) and takt_nr > 0:
            if stufe not in stoss_cache:
                g = _hz(grund * 4, stufe)
                # Moll-Dreiklang auf i und iv, Dur auf den anderen Stufen.
                terz = 3 if stufe in (0, 5) else 4
                stoss_cache[stufe] = stoss([g, _hz(g, terz), _hz(g, 7)], schlag * 0.9)
            addiere(start, stoss_cache[stufe], pan=0.2 if im_takt else -0.2)

    if schnitte:
        w = _whoosh(seed)
        for c in schnitte:
            addiere(max(0, int((c - 0.34) * RATE)), w, pan=-0.25 if int(c * 10) % 2 else 0.25)
    imp = _impact()
    addiere(0, [0.8 * v for v in imp])
    if schlusspunkt:
        addiere(int(schlusspunkt * RATE), imp)

    # Weich begrenzen (tanh), ein- und ausblenden, nach int16.
    proben = array("h")
    aus_ab = max(0, n - int(1.2 * RATE))
    for i in range(n):
        g = 1.0
        if i < int(0.05 * RATE):
            g = i / (0.05 * RATE)
        elif i >= aus_ab:
            g = max(0.0, 1 - (i - aus_ab) / (n - aus_ab))
        proben.append(int(32000 * math.tanh(1.4 * links[i]) * g))
        proben.append(int(32000 * math.tanh(1.4 * rechts[i]) * g))
    return proben, bpm


def schreibe_wav(ziel: Path, dauer_s: float, seed: int, bpm: int | None = None,
                 schnitte: list[float] | None = None, schlusspunkt: float | None = None) -> int:
    """Schreibt den Beat als WAV (44,1 kHz, 16 Bit, Stereo); gibt das Tempo zurück."""
    proben, bpm = erzeuge(dauer_s, seed, bpm, schnitte, schlusspunkt)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ziel), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(proben.tobytes())
    return bpm


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Einen eigenen Beat als WAV schreiben.")
    ap.add_argument("ziel", type=Path)
    ap.add_argument("--dauer", type=float, default=14.0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    print(f"{a.ziel}: {schreibe_wav(a.ziel, a.dauer, a.seed)} BPM")
