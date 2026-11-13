#!/usr/bin/env python3
"""
scripts/insta_musik.py
======================

Ein eigener Beat für die Reels – selbst erzeugt, also ohne Lizenzfrage.
Die Musik aus der Instagram-Bibliothek lässt sich über die Schnittstelle
nicht an einen Beitrag hängen; ein stummes Reel wirkt tot, und fremde
Stücke bräuchten eine Lizenz (marketing/instagram/musik/musik.json, die
insta_video.musik_wahl() vorzieht, sobald dort eines mit Lizenz steht).

**Sechs Stile** (seit dem 04.11.2026, vom Nutzer: „Die Musik ist bei jedem
Video gleich und die Einspielungen auch. Das ist zu monoton.“ – bis dahin
gab es nur den einen Elektro-Pop-Beat, Tempo und Tonart wechselten):

    pop         Elektro-Pop, Bassdrum auf jedem Schlag, Akkord-Stöße, Pluck-Melodie
    trap        Halbzeit-Gefühl, 808-Bass mit Gleiten, Hi-Hat-Wirbel, Glocken-Melodie
    lofi        langsam, verschleppte Hi-Hats, E-Piano mit Septakkorden, Knistern
    synthwave   Achtel-Bass, große Snare, Arpeggio in Sechzehnteln, Fläche
    dembow      Latin-Rhythmus (bum-tschk-bum-tschak), Shaker, Marimba-Melodie
    dnb         Drum & Bass, schnell, gebrochener Rhythmus, breiter Bass, Fläche

Jeder Stil hat eigene Instrumente, eigenen Rhythmus (16 Schritte je Takt)
und eine Melodie aus der Moll-Pentatonik, die je Video neu entsteht.
Stil, Übergangs-Geräusch und Schlussschlag rotieren mit dem Datum
(`stil_fuer`, `rotation`): Zwei Tage hintereinander klingen nie gleich,
derselbe Tag immer gleich (die Vorschau im Dashboard = das gepostete Reel).

Ohne numpy (der Actions-Runner hat es nicht): reines Python mit `array`
und `wave`, ~2–4 s Rechenzeit für 20 s Ton.
"""
from __future__ import annotations

import datetime as dt
import math
import random
import wave
from array import array
from pathlib import Path

RATE = 44100

# Tempo je Stil (Auswahl) und die Rotation der Stile über die Tage.
STILE = {
    "pop": (118, 122, 124, 126, 128),
    "trap": (136, 140, 144),
    "lofi": (84, 88, 92),
    "synthwave": (100, 104, 108),
    "dembow": (92, 96, 100),
    "dnb": (170, 174),
}
STIL_FOLGE = ("pop", "lofi", "trap", "dembow", "synthwave", "dnb")
BPM_AUSWAHL = tuple(sorted({b for v in STILE.values() for b in v}))

# Geräusch an jedem Schnitt (Wisch) und der Schlag zu Beginn und am Schluss.
UEBERGAENGE = ("whoosh", "bloop", "riser", "zap", "swish", "reverse")
SCHLUSS = ("boom", "glocke", "drop", "crash", "akkord")

# Akkordfolgen als Halbtöne über dem Grundton (Moll, vier Takte).
FOLGEN = (
    (0, 8, 3, 10),     # i – VI – III – VII  (Am F C G)
    (0, 5, 8, 10),     # i – iv – VI – VII   (Am Dm F G)
    (0, 10, 8, 10),    # i – VII – VI – VII
    (0, 3, 10, 5),     # i – III – VII – iv
    (0, 8, 10, 3),     # i – VI – VII – III
    (0, 5, 3, 8),      # i – iv – III – VI
)
GRUNDTOENE_HZ = (55.0, 58.27, 61.74, 65.41, 49.0, 51.91, 46.25)   # A1 Bb1 B1 C2 G1 Ab1 F#1
PENTATONIK = (0, 3, 5, 7, 10)


def _tag(seed: int) -> int:
    """Der Kalendertag hinter einem Seed JJJJMMTT (so rechnet ihn
    insta_video.rendere aus dem Datum), sonst der Seed selbst."""
    try:
        return dt.date(seed // 10000, seed // 100 % 100, seed % 100).toordinal()
    except (ValueError, OverflowError):
        return seed


def rotation(seed: int, liste, schritt: int = 1):
    """Ein Eintrag der Liste je Tag; Nachbartage nie derselbe (`schritt`
    teilerfremd zur Länge – wechselnde Schritte geben wechselnde Paare)."""
    return liste[(_tag(seed) * schritt) % len(liste)]


def stil_fuer(seed: int) -> str:
    return rotation(seed, STIL_FOLGE, 1)


def bpm_fuer(seed: int) -> int:
    auswahl = STILE[stil_fuer(seed)]
    return auswahl[random.Random(seed).randrange(len(auswahl))]


def schlag_s(bpm: int) -> float:
    return 60.0 / bpm


def _hz(grund: float, halbtoene: float) -> float:
    return grund * 2 ** (halbtoene / 12)


# ---------------------------------------------------------------- Klänge

def _rauschen(r: random.Random, n: int) -> list[float]:
    return [r.random() * 2 - 1 for _ in range(n)]


def _hochpass(x: list[float], k: float = 0.15) -> list[float]:
    tief, aus = 0.0, []
    for v in x:
        tief += k * (v - tief)
        aus.append(v - tief)
    return aus


def _kick(start_hz: float, end_hz: float, abfall: float, dauer: float = 0.32, pegel: float = 0.95) -> list[float]:
    aus = []
    for i in range(int(dauer * RATE)):
        t = i / RATE
        phase = 2 * math.pi * (end_hz * t + (start_hz - end_hz) * (1 - math.exp(-t * 30)) / 30)
        aus.append(pegel * math.sin(phase) * math.exp(-t * abfall))
    return aus


def _snare(r: random.Random, koerper_hz: float, abfall: float, pegel: float, dauer: float = 0.25,
           schwanz: float = 0.0) -> list[float]:
    rausch = _hochpass(_rauschen(r, int((dauer + schwanz) * RATE)), 0.25)
    aus = []
    for i, n_ in enumerate(rausch):
        t = i / RATE
        h = math.exp(-t * abfall) + (0.35 * math.exp(-t * 6) if schwanz else 0.0)
        v = 0.55 * n_ * h + 0.5 * math.sin(2 * math.pi * koerper_hz * t) * math.exp(-t * 28)
        aus.append(pegel * v)
    return aus


def _clap(r: random.Random, pegel: float = 0.32) -> list[float]:
    aus = []
    for i in range(int(0.22 * RATE)):
        t = i / RATE
        huelle = math.exp(-t * 18) * (1.0 if t > 0.012 else 0.6) * (0.7 if 0.006 < t < 0.009 else 1.0)
        aus.append(pegel * (r.random() * 2 - 1) * huelle)
    return aus


def _hat(r: random.Random, abfall: float = 90, pegel: float = 0.11, dauer: float = 0.05) -> list[float]:
    rausch = _hochpass(_rauschen(r, int(dauer * RATE)), 0.5)
    return [pegel * v * math.exp(-(i / RATE) * abfall) for i, v in enumerate(rausch)]


def _rim(pegel: float = 0.22) -> list[float]:
    return [pegel * (math.sin(2 * math.pi * 1750 * i / RATE) + 0.6 * math.sin(2 * math.pi * 520 * i / RATE))
            * math.exp(-(i / RATE) * 60) for i in range(int(0.07 * RATE))]


def _ton(freq: float, laenge: float, art: str, pegel: float, attack: float = 0.004, abfall: float = 3.0,
         gleit_von: float | None = None) -> list[float]:
    """Ein Ton: sine, saw (6 Obertöne), square (ungerade), epiano (mit
    Tremolo), bell (unharmonisch), reese (zwei verstimmte Sägezähne)."""
    aus = []
    phase = phase2 = 0.0
    for i in range(int(laenge * RATE)):
        t = i / RATE
        f = freq
        if gleit_von:
            f = freq + (gleit_von - freq) * math.exp(-t * 18)
        phase += 2 * math.pi * f / RATE
        huelle = min(1.0, t / attack) * math.exp(-t * abfall)
        if art == "sine":
            v = math.sin(phase) + 0.25 * math.sin(2 * phase)
        elif art == "saw":
            v = sum(math.sin(k * phase) / k for k in range(1, 7)) * 0.6
        elif art == "square":
            v = sum(math.sin(k * phase) / k for k in (1, 3, 5, 7)) * 0.75
        elif art == "epiano":
            v = (math.sin(phase) + 0.3 * math.sin(2 * phase) * math.exp(-t * 6)) * (1 + 0.18 * math.sin(2 * math.pi * 4.5 * t))
        elif art == "bell":
            v = (math.sin(phase) + 0.5 * math.sin(2.76 * phase) * math.exp(-t * 4)
                 + 0.25 * math.sin(5.4 * phase) * math.exp(-t * 9))
        elif art == "reese":
            phase2 += 2 * math.pi * f * 1.012 / RATE
            v = sum((math.sin(k * phase) + math.sin(k * phase2)) / k for k in range(1, 6)) * 0.4
        else:
            v = math.sin(phase)
        aus.append(pegel * huelle * v)
    return aus


def _pluck(freq: float, laenge: float, pegel: float, seed: int = 5) -> list[float]:
    """Gezupfte Saite (Karplus-Strong): Rauschstoß durch eine mittelnde
    Verzögerungsleitung."""
    r = random.Random(seed)
    n = max(2, int(RATE / freq))
    puffer = [r.random() * 2 - 1 for _ in range(n)]
    aus = []
    for i in range(int(laenge * RATE)):
        v = puffer[i % n]
        puffer[i % n] = 0.498 * (v + puffer[(i + 1) % n])
        aus.append(pegel * v)
    return aus


def _flaeche(freqs: list[float], laenge: float, pegel: float) -> list[float]:
    """Weiche Fläche: langsames Einblenden, leicht verstimmte Stimmen."""
    aus = []
    phasen = [0.0] * (2 * len(freqs))
    for i in range(int(laenge * RATE)):
        t = i / RATE
        huelle = min(1.0, t / 0.25) * min(1.0, (laenge - t) / 0.2)
        v = 0.0
        for j, f in enumerate(freqs):
            for k, fein in enumerate((0.997, 1.004)):
                phasen[2 * j + k] += 2 * math.pi * f * fein / RATE
                v += math.sin(phasen[2 * j + k]) + 0.2 * math.sin(2 * phasen[2 * j + k])
        aus.append(pegel * huelle * v)
    return aus


# ---------------------------------------------------------------- Geräusche

def uebergang_klang(art: str, seed: int) -> tuple[list[float], float]:
    """Das Geräusch an einem Schnitt und wo darin der Schnitt liegt (s)."""
    r = random.Random(seed * 31 + 7)
    if art == "bloop":                     # kleines „Plopp" genau am Schnitt
        aus, ph = [], 0.0
        for i in range(int(0.16 * RATE)):
            t = i / RATE
            ph += 2 * math.pi * (380 + 900 * (1 - math.exp(-t * 40))) / RATE
            aus.append(0.42 * math.sin(ph) * math.exp(-t * 22))
        return aus, 0.0
    if art == "riser":                     # steigt an, reißt am Schnitt ab
        n = int(0.62 * RATE)
        rausch = _hochpass(_rauschen(r, n), 0.3)
        aus, ph = [], 0.0
        for i in range(n):
            p = i / n
            ph += 2 * math.pi * (260 + 1100 * p * p) / RATE
            aus.append((0.22 * rausch[i] + 0.16 * math.sin(ph)) * p ** 1.6)
        return aus, 0.62
    if art == "zap":                       # Laser nach unten
        aus, ph = [], 0.0
        for i in range(int(0.22 * RATE)):
            t = i / RATE
            ph += 2 * math.pi * (120 + 1700 * math.exp(-t * 22)) / RATE
            aus.append(0.30 * (1 if math.sin(ph) > 0 else -1) * math.exp(-t * 14) * 0.6)
        return aus, 0.0
    if art == "swish":                     # kurzer heller Luftzug
        n = int(0.24 * RATE)
        rausch = _hochpass(_rauschen(r, n), 0.45)
        return [0.5 * v * math.sin(math.pi * i / n) ** 2 for i, v in enumerate(rausch)], 0.14
    if art == "reverse":                   # rückwärts gespieltes Becken
        n = int(0.7 * RATE)
        rausch = _hochpass(_rauschen(r, n), 0.35)
        return [0.36 * v * (i / n) ** 3 for i, v in enumerate(rausch)], 0.7
    # whoosh: Rauschen, das anschwillt und abreißt, mit wanderndem Tiefpass
    aus, tief = [], 0.0
    n = int(0.42 * RATE)
    for i in range(n):
        p = i / n
        huelle = (p / 0.8) ** 2 if p < 0.8 else max(0.0, 1 - (p - 0.8) / 0.2)
        k = 0.02 + 0.25 * p
        tief += k * ((r.random() * 2 - 1) - tief)
        aus.append(0.55 * huelle * tief)
    return aus, 0.34


def schluss_klang(art: str, grund: float = 55.0, terz: int = 3) -> list[float]:
    """Der Schlag zu Beginn und am Schluss (CTA)."""
    r = random.Random(99)
    if art == "glocke":
        f = _hz(grund * 8, 0)
        return [a + b for a, b in zip(_ton(f, 1.3, "bell", 0.32, abfall=2.4),
                                      _ton(_hz(f, 7), 1.3, "bell", 0.18, abfall=2.8))]
    if art == "drop":                      # tiefer Fall
        aus, ph = [], 0.0
        for i in range(int(1.0 * RATE)):
            t = i / RATE
            ph += 2 * math.pi * (32 + 90 * math.exp(-t * 4)) / RATE
            aus.append(0.85 * math.sin(ph) * math.exp(-t * 2.2))
        return aus
    if art == "crash":
        rausch = _hochpass(_rauschen(r, int(1.2 * RATE)), 0.3)
        kick = _kick(110, 42, 7, 0.4)
        return [0.30 * v * math.exp(-(i / RATE) * 2.6) + (kick[i] if i < len(kick) else 0.0)
                for i, v in enumerate(rausch)]
    if art == "akkord":                    # der Grundakkord, kräftig und lang
        teile = [_ton(_hz(grund * 4, h), 1.1, "saw", 0.10, abfall=2.6) for h in (0, terz, 7, 12)]
        kick = _kick(110, 45, 6, 0.4)
        return [sum(t_[i] for t_ in teile) + (kick[i] if i < len(kick) else 0.0) for i in range(len(teile[0]))]
    aus = []                               # boom: tiefer Schlag mit Rauschen
    for i in range(int(0.9 * RATE)):
        t = i / RATE
        phase = 2 * math.pi * (38 * t + 90 * (1 - math.exp(-t * 14)) / 14)
        v = 0.9 * math.sin(phase) * math.exp(-t * 3.2)
        v += 0.25 * (r.random() * 2 - 1) * math.exp(-t * 40)
        aus.append(v)
    return aus


# ---------------------------------------------------------------- Stile

def _melodie(rng: random.Random, grund: float, schritte: tuple[int, ...]) -> list[tuple[int, float]]:
    """Ein Motiv über einen Takt: (Schritt, Frequenz) aus der Moll-Pentatonik,
    meist kleine Schritte, gern auf dem Grundton endend."""
    lage = rng.choice((24, 24, 36))
    idx = rng.randrange(len(PENTATONIK))
    noten = []
    for s in schritte:
        idx = max(0, min(len(PENTATONIK) * 2 - 1, idx + rng.choice((-2, -1, -1, 0, 1, 1, 2))))
        h = PENTATONIK[idx % 5] + 12 * (idx // 5)
        noten.append((s, _hz(grund, lage + h)))
    return noten


def _motiv_schritte(rng: random.Random, dicht: int) -> tuple[int, ...]:
    """Auf welchen der 16 Schritte eines Takts die Melodie spielt."""
    vorlagen = {
        1: ((0, 6, 12), (0, 4, 10), (2, 8, 14), (0, 10)),
        2: ((0, 3, 6, 10, 12), (0, 2, 6, 8, 12, 14), (0, 4, 6, 10, 14), (2, 6, 10, 12, 14)),
        3: ((0, 2, 4, 6, 8, 10, 12, 14), (0, 3, 6, 8, 11, 14), (0, 2, 3, 6, 8, 10, 11, 14)),
    }[dicht]
    return rng.choice(vorlagen)


class _Mix:
    def __init__(self, n: int):
        self.n = n
        self.links = [0.0] * n
        self.rechts = [0.0] * n

    def add(self, zeit: float, werte, pan: float = 0.0, pegel: float = 1.0) -> None:
        start = int(zeit * RATE)
        gl, gr = (1 - max(0.0, pan)) * pegel, (1 + min(0.0, pan)) * pegel
        ende = min(self.n, start + len(werte))
        if start < 0:
            werte = werte[-start:]
            start = 0
        li, re_ = self.links, self.rechts
        for j in range(start, ende):
            v = werte[j - start]
            li[j] += v * gl
            re_[j] += v * gr


def _spiele(mix: _Mix, stil: str, dauer_s: float, bpm: int, rng: random.Random, grund: float,
            folge: tuple[int, ...]) -> None:
    schlag = schlag_s(bpm)
    st = schlag / 4                                     # ein Sechzehntel
    takt = 4 * schlag
    takte = int(dauer_s / takt) + 2
    r = random.Random(rng.random())
    cache: dict = {}

    def c(schluessel, macher):
        if schluessel not in cache:
            cache[schluessel] = macher()
        return cache[schluessel]

    def akkord(stufe: int, lage: int = 3) -> list[float]:
        g = _hz(grund * 2 ** lage, stufe)
        terz = 3 if stufe in (0, 5) else 4
        return [g, _hz(g, terz), _hz(g, 7)]

    swing = 0.0
    melodie_art, melodie_pegel, dicht = "pluck", 0.20, 2
    if stil == "pop":
        kick = c("k", lambda: _kick(150, 48, 9))
        muster = {"kick": (0, 4, 8, 12), "clap": (4, 12), "hat": (2, 6, 10, 14), "hat_leise": (0, 4, 8, 12)}
        melodie_art, dicht = "pluck", 2
    elif stil == "trap":
        kick = c("k", lambda: _kick(170, 45, 5, 0.5))
        muster = {"kick": (0, 7, 10), "clap": (8,), "hat": tuple(range(0, 16, 2))}
        melodie_art, melodie_pegel, dicht = "bell", 0.13, 1
    elif stil == "lofi":
        kick = c("k", lambda: _kick(120, 50, 11, 0.3, 0.8))
        muster = {"kick": (0, 7, 10), "rim": (4, 12), "hat": (0, 2, 4, 6, 8, 10, 12, 14)}
        swing = st * 0.33
        melodie_art, melodie_pegel, dicht = "epiano", 0.11, 1
    elif stil == "synthwave":
        kick = c("k", lambda: _kick(140, 50, 8))
        muster = {"kick": (0, 4, 8, 12), "snare": (4, 12), "hat": tuple(range(16))}
        melodie_art, melodie_pegel, dicht = "square", 0.07, 3
    elif stil == "dembow":
        kick = c("k", lambda: _kick(130, 50, 10))
        muster = {"kick": (0, 4, 8, 12), "rim": (3, 6, 11, 14), "shaker": tuple(range(16))}
        melodie_art, melodie_pegel, dicht = "bell", 0.10, 2
    else:                                                # dnb
        kick = c("k", lambda: _kick(160, 52, 12, 0.25))
        muster = {"kick": (0, 10), "snare": (4, 12), "geist": (7, 14), "hat": tuple(range(0, 16, 2))}
        melodie_art, melodie_pegel, dicht = "bell", 0.10, 1

    motiv = _melodie(rng, grund, _motiv_schritte(rng, dicht))
    motiv_b = _melodie(rng, grund, _motiv_schritte(rng, dicht))
    noten_laenge = {"pluck": 0.45, "bell": 0.9, "epiano": 0.8, "square": st * 1.6}[melodie_art]

    for t_nr in range(takte):
        t0 = t_nr * takt
        if t0 > dauer_s + 0.5:
            break
        stufe = folge[t_nr % len(folge)]
        intro = t_nr == 0
        letzter_vor_wirbel = t_nr % 2 == 1

        def zeit(s: int) -> float:
            return t0 + s * st + (swing if s % 4 == 2 else 0.0)

        # Schlagzeug
        for s in muster.get("kick", ()):
            if not intro or s >= 8:
                mix.add(zeit(s), kick, pegel=0.95)
        for s in muster.get("clap", ()):
            if not intro:
                mix.add(zeit(s), c("clap", lambda: _clap(r)), pan=0.08)
        for s in muster.get("snare", ()):
            if not intro:
                mix.add(zeit(s), c("snare", lambda: _snare(r, 190 if stil == "dnb" else 170, 16 if stil == "dnb" else 9,
                                                         0.36, schwanz=0.25 if stil == "synthwave" else 0.0)), pan=0.05)
        for s in muster.get("geist", ()):
            if not intro:
                mix.add(zeit(s), c("snare", lambda: _snare(r, 190, 16, 0.36)), pegel=0.35)
        for s in muster.get("rim", ()):
            mix.add(zeit(s), c("rim", lambda: _rim(0.16 if stil == "lofi" else 0.2)), pan=0.15)
        for s in muster.get("hat", ()):
            leise = 0.55 if s % 4 == 0 and stil != "synthwave" else 1.0
            if stil == "synthwave":
                leise = 0.5 + 0.5 * (s % 2)
            mix.add(zeit(s), c("hat", lambda: _hat(r)), pan=-0.3 if s % 4 else 0.3, pegel=leise)
        for s in muster.get("hat_leise", ()):
            mix.add(zeit(s), c("hat", lambda: _hat(r)), pegel=0.45)
        for s in muster.get("shaker", ()):
            mix.add(zeit(s), c("shaker", lambda: _hat(r, 45, 0.06, 0.08)), pan=-0.4, pegel=1.0 if s % 2 else 0.6)
        if stil == "trap" and letzter_vor_wirbel and not intro:
            # Hi-Hat-Wirbel in Zweiunddreißigsteln auf dem letzten Schlag
            for k in range(8):
                mix.add(t0 + 3 * schlag + k * st / 2, c("hat", lambda: _hat(r)), pegel=0.5 + 0.06 * k, pan=0.3)
        if stil == "pop" and not intro:
            for s in (2, 6, 10, 14):
                mix.add(zeit(s), c("offen", lambda: _hat(r, 22, 0.07, 0.16)), pan=0.25)
        if stil == "lofi":
            # Plattenknistern
            for _ in range(6):
                mix.add(t0 + r.random() * takt, c("knack", lambda: _hat(r, 400, 0.05, 0.01)), pan=r.uniform(-0.6, 0.6))

        # Bass
        if not intro:
            bf = _hz(grund, stufe)
            if stil == "pop":
                for s in (2, 6, 10, 14):
                    mix.add(zeit(s), c(("bass", stufe), lambda: _ton(bf, schlag * 0.45, "sine", 0.30, abfall=2.2)))
            elif stil == "trap":
                for s, lang in ((0, 7), (7, 3), (10, 6)):
                    mix.add(zeit(s), c(("808", stufe, lang), lambda: _ton(bf, st * lang, "sine", 0.45, abfall=0.9,
                                                                        gleit_von=bf * 1.5)))
            elif stil == "lofi":
                for s, lang in ((0, 6), (10, 5)):
                    mix.add(zeit(s), c(("lbass", stufe, lang), lambda: _ton(bf, st * lang, "sine", 0.28, attack=0.02,
                                                                          abfall=1.4)))
            elif stil == "synthwave":
                for s in range(0, 16, 2):
                    mix.add(zeit(s), c(("sbass", stufe), lambda: _ton(bf, st * 1.7, "saw", 0.17, abfall=5)),
                            pegel=1.0 if s % 4 == 0 else 0.8)
            elif stil == "dembow":
                for s in (0, 3, 8, 11):
                    mix.add(zeit(s), c(("dbass", stufe), lambda: _ton(bf, st * 2.5, "sine", 0.30, abfall=3)))
            else:
                mix.add(t0, c(("reese", stufe), lambda: _ton(bf, takt * 0.98, "reese", 0.09, attack=0.03, abfall=0.4)))

        # Harmonie
        if stil == "pop":
            if not intro:
                for s in (0, 8):
                    mix.add(zeit(s), c(("stoss", stufe), lambda: [sum(x) for x in zip(*[_ton(f, schlag * 0.9, "sine", 0.055, abfall=7)
                                                                                  for f in akkord(stufe)])]),
                            pan=-0.2 if s else 0.2)
        elif stil == "lofi":
            freqs = akkord(stufe) + [_hz(_hz(grund * 8, stufe), 10)]          # mit Septime
            mix.add(t0, c(("ep", stufe), lambda: [sum(x) for x in zip(*[_ton(f, takt, "epiano", 0.045, attack=0.01, abfall=0.9)
                                                                       for f in freqs])]), pan=-0.1)
        elif stil in ("trap", "synthwave", "dnb"):
            mix.add(t0, c(("pad", stufe), lambda: _flaeche(akkord(stufe), takt, 0.022)), pan=0.1)
        elif stil == "dembow" and not intro:
            for s in (2, 6, 10, 14):
                mix.add(zeit(s), c(("dstoss", stufe), lambda: [sum(x) for x in zip(*[_pluck(f, 0.25, 0.06, 3)
                                                                                for f in akkord(stufe)])]), pan=0.25)

        # Arpeggio (Synthwave)
        if stil == "synthwave" and not intro:
            tonleiter = akkord(stufe, 4)
            for s in range(16):
                f = tonleiter[(s if (s // 4) % 2 == 0 else 2 - s) % 3]
                mix.add(zeit(s), c(("arp", f), lambda: _ton(f, st * 0.9, "square", 0.045, abfall=12)), pan=0.35)

        # Melodie: ab dem zweiten Takt, im vierten das zweite Motiv
        if t_nr >= 1:
            noten = motiv_b if t_nr % 4 == 3 else motiv
            for s, f in noten:
                if melodie_art == "pluck":
                    welle = c(("pl", f), lambda: _pluck(f, noten_laenge, melodie_pegel * 1.6, 11))
                else:
                    welle = c(("mel", f), lambda: _ton(f, noten_laenge, melodie_art, melodie_pegel,
                                                       abfall=3 if melodie_art != "square" else 8))
                mix.add(zeit(s), welle, pan=-0.15)


def erzeuge(dauer_s: float, seed: int, bpm: int | None = None,
            schnitte: list[float] | None = None, schlusspunkt: float | None = None,
            stil: str | None = None) -> tuple[array, int]:
    """Stereo-Samples (int16, abwechselnd links/rechts) und das Tempo.
    `schnitte`: Zeiten (s) der Wisch-Übergänge - dort das Übergangs-
    Geräusch des Tages; zum Start und am `schlusspunkt` sein Schlag."""
    rng = random.Random(seed * 7919 + 13)
    stil = stil or stil_fuer(seed)
    bpm = bpm or bpm_fuer(seed)
    folge = FOLGEN[rng.randrange(len(FOLGEN))]
    grund = GRUNDTOENE_HZ[rng.randrange(len(GRUNDTOENE_HZ))]
    n = int(dauer_s * RATE)
    mix = _Mix(n)
    _spiele(mix, stil, dauer_s, bpm, rng, grund, folge)

    if schnitte:
        klang, anker = uebergang_klang(rotation(seed, UEBERGAENGE, 5), seed)
        for i, c_ in enumerate(schnitte):
            mix.add(c_ - anker, klang, pan=-0.25 if i % 2 else 0.25)
    schluss = schluss_klang(rotation(seed, SCHLUSS, 2), grund)
    mix.add(0, schluss, pegel=0.8)
    if schlusspunkt:
        mix.add(schlusspunkt, schluss)

    # Gleich laut über alle Stile (Lofi ist leiser gebaut als Trap), dann
    # weich begrenzen (tanh), ein- und ausblenden, nach int16.
    rms = math.sqrt(sum(v * v for v in mix.links[::7]) / max(1, len(mix.links[::7]))) or 1.0
    pegel = max(0.6, min(1.8, 0.20 / rms))
    proben = array("h")
    aus_ab = max(0, n - int(1.2 * RATE))
    ein = int(0.05 * RATE)
    for i in range(n):
        g = 1.0
        if i < ein:
            g = i / ein
        elif i >= aus_ab:
            g = max(0.0, 1 - (i - aus_ab) / (n - aus_ab))
        proben.append(int(32000 * math.tanh(1.4 * pegel * mix.links[i]) * g))
        proben.append(int(32000 * math.tanh(1.4 * pegel * mix.rechts[i]) * g))
    return proben, bpm


def beschreibung(seed: int, bpm: int) -> str:
    """Für Log und Metadaten: „eigener Beat (Trap, 140 BPM, Zap/Glocke)"."""
    namen = {"pop": "Pop", "trap": "Trap", "lofi": "Lo-Fi", "synthwave": "Synthwave", "dembow": "Dembow",
             "dnb": "Drum & Bass"}
    return (f"eigener Beat ({namen.get(stil_fuer(seed), stil_fuer(seed))}, {bpm} BPM, "
            f"{rotation(seed, UEBERGAENGE, 5)}/{rotation(seed, SCHLUSS, 2)})")


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
    bpm = schreibe_wav(a.ziel, a.dauer, a.seed)
    print(f"{a.ziel}: {beschreibung(a.seed, bpm)}")
