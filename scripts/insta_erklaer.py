#!/usr/bin/env python3
"""Erklär-Reel „Zahl als Bild“ (seit 22.11.2026, vom Nutzer gewünscht).

Eine Frage als Hook, raten lassen, die Entwarnung, die echte Antwort als
Bild, etwas zum Mitnehmen, Schluss mit Frage – gezeichnet in flachen
Flächen mit unserem Maskottchen, Untertitel Wort für Wort. Die Bilder
entstehen hier (Pillow → ffmpeg), nichts davon kommt aus einem KI-Video:
Zahlen und Schrift müssen exakt sein, und die Figur soll in jeder Szene
dieselbe bleiben. Nur die Sprecherstimme kommt von Runway (`--stimme`).

Die Vorlage ist `marketing/instagram/erklaer/<thema>.json`:

    {"seed": 5, "szenen": [{"bild": "hook", "text": "…"}, …]}

`bild` wählt die Zeichenroutine (`SZENEN`), `text` ist der Sprechertext
und zugleich der Untertitel. Ohne Stimme wird die Dauer je Szene aus der
Textlänge geschätzt; mit `--stimme` und `"zeiten": [[von, bis], …]` in der
Vorlage (Sprechpausen aus `ffmpeg … silencedetect`) liegt sie genau.

    python3 scripts/insta_erklaer.py marketing/instagram/erklaer/schwelle.json --aus reel.mp4
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insta_maskottchen as M  # noqa: E402
import insta_musik  # noqa: E402
from insta_video import kondensiert, text_schrift  # noqa: E402

B, H, FPS = 1080, 1920, 30
MIDNIGHT, SOFT_BLUE, CORAL, WEISS = M.MIDNIGHT, M.SOFT_BLUE, M.CORAL, M.WEISS
CREME = (255, 249, 238)
NACHT_HELL = (0, 58, 88)
HIMMEL = (196, 230, 242)
HUEGEL_1, HUEGEL_2 = (132, 190, 208), (88, 156, 180)
STRASSE = (20, 58, 82)
GRUEN = (70, 170, 130)
GELB = (250, 196, 84)
ZEICHEN_JE_S = 16.5     # geschätztes Sprechtempo ohne Stimme
PAUSE_S = 0.35


# --- Helfer ---------------------------------------------------------------

def weich(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def federn(t: float) -> float:
    """0 → 1 mit kleinem Überschwinger (für alles, was „aufpoppt“)."""
    t = max(0.0, min(1.0, t))
    return 1 - math.cos(t * math.pi * 1.5) * (1 - t) ** 2 if t < 1 else 1.0


def schrift(g: float, fett: bool = True):
    return kondensiert(max(8, int(round(g / 4) * 4)), fett)


def text(d: ImageDraw.ImageDraw, x: float, y: float, s: str, g: float, fill=WEISS, kontur=MIDNIGHT,
         rand: int = 8) -> None:
    d.text((x, y), s, font=schrift(g), fill=fill, anchor="mm",
           stroke_width=rand if kontur else 0, stroke_fill=kontur)


def pop(d, x, y, s, g, t, **kw) -> None:
    """Text, der ab t = 0 aufpoppt (t in Sekunden seit seinem Einsatz)."""
    if t > 0:
        text(d, x, y, s, g * federn(t / 0.35), **kw)


def aufkleben(bild: Image.Image, teil: Image.Image, mx: float, unten: float) -> None:
    bild.alpha_composite(teil, (int(mx - teil.width / 2), int(unten - teil.height)))


def blase(d, x, y, s, g, t, spitze_x: float | None = None) -> None:
    """Sprechblase (Creme, Midnight-Kontur), poppt ab t = 0 auf."""
    if t <= 0:
        return
    k = federn(t / 0.3)
    f = schrift(g * k)
    w, h = f.getlength(s) / 2 + 46 * k, (g * 0.62 + 30) * k
    d.rounded_rectangle([x - w - 7, y - h - 7, x + w + 7, y + h + 7], radius=h + 7, fill=MIDNIGHT)
    if spitze_x is not None:
        d.polygon([(x - 30 * k, y + h - 4), (x + 22 * k, y + h - 4), (spitze_x, y + h + 62 * k)], fill=MIDNIGHT)
        d.polygon([(x - 18 * k, y + h - 8), (x + 12 * k, y + h - 8), (spitze_x, y + h + 44 * k)], fill=CREME)
    d.rounded_rectangle([x - w, y - h, x + w, y + h], radius=h, fill=CREME)
    d.text((x, y), s, font=f, fill=MIDNIGHT, anchor="mm")


# --- Die Figur von der Seite (läuft) -----------------------------------------

PHASEN = 20


def _glied(d, pts, w, fill, k, kontur=True):
    pts = [(x * k, y * k) for x, y in pts]
    for farbe, extra in (((MIDNIGHT, 5 * k),) if kontur else ()) + ((fill, 0),):
        b = w * k + 2 * extra
        if len(pts) > 1:
            d.line(pts, fill=farbe, width=int(round(b)), joint="curve")
        for x, y in pts:
            d.ellipse([x - b / 2, y - b / 2, x + b / 2, y + b / 2], fill=farbe)


@lru_cache(maxsize=None)
def laeufer(phase_i: int, hoehe: int = 560, mund: str = "laecheln") -> Image.Image:
    """Unser Maskottchen im Laufschritt, Blick nach rechts (RGBA).

    `mund`: "laecheln" (lockerer Lauf), "angestrengt" (schnell – Brauen
    gerade, Mund leicht offen, kein böser Blick) oder "o" (fliegt vom Band).
    Kurze Haare nur oben am Kopf (bis zum Ohr, nicht in den Nacken – sonst
    liest man einen Bob), Oberkörper schlank und leicht nach vorn geneigt.
    """
    ss = 3
    k = hoehe / 300 * ss
    img = Image.new("RGBA", (int(300 * k), int(300 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = 2 * math.pi * phase_i / PHASEN
    bob = 5 * math.cos(2 * p)
    hufte, schulter, kopf = (140, 170 + bob), (158, 100 + bob), (170, 60 + bob)

    def bein(q, hinten):
        a = 0.85 * math.sin(q)
        b = a - (0.2 + 1.2 * max(0.0, math.cos(q)))
        knie = (hufte[0] + 55 * math.sin(a), hufte[1] + 55 * math.cos(a))
        fuss = (knie[0] + 58 * math.sin(b), knie[1] + 58 * math.cos(b))
        haut = M.HAUT_SCHATTEN if hinten else M.HAUT
        _glied(d, [hufte, knie, fuss], 19, haut, k)
        spitze = (fuss[0] + 20 * math.cos(b), fuss[1] - 20 * math.sin(b))
        _glied(d, [fuss, spitze], 17, WEISS, k)
        _glied(d, [fuss, spitze], 4, CORAL, k, kontur=False)
        _glied(d, [hufte, (hufte[0] + 20 * math.sin(a), hufte[1] + 20 * math.cos(a))], 22, M.HOSE, k)

    def arm(q, hinten):
        ua = -0.9 * math.sin(q)
        fa = ua + 1.5
        e = (schulter[0] + 34 * math.sin(ua), schulter[1] + 34 * math.cos(ua))
        h = (e[0] + 30 * math.sin(fa), e[1] + 30 * math.cos(fa))
        _glied(d, [schulter, e, h], 16, M.HAUT_SCHATTEN if hinten else M.HAUT, k)
        _glied(d, [schulter, (schulter[0] + 12 * math.sin(ua), schulter[1] + 12 * math.cos(ua))], 21,
               M.SHIRT, k)

    arm(p, True)
    bein(p + math.pi, True)
    rumpf_unten = (hufte[0] + 2, hufte[1] - 12)
    _glied(d, [schulter, rumpf_unten], 40, M.SHIRT, k)
    # Seitenstreifen vorn an der Flanke (nicht am Rücken)
    _glied(d, [(schulter[0] + 7, schulter[1] + 12), (rumpf_unten[0] + 9, rumpf_unten[1] - 6)], 5, SOFT_BLUE, k,
           kontur=False)
    _glied(d, [(hufte[0] + 4, hufte[1] - 4), (hufte[0] + 3, hufte[1] + 5)], 34, M.HOSE, k)
    bein(p, False)
    kx, ky, r, o = kopf[0] * k, kopf[1] * k, 30 * k, 5 * k
    d.ellipse([kx - r - o, ky - r - o, kx + r + o, ky + r + o], fill=MIDNIGHT)
    d.ellipse([kx - r, ky - r, kx + r, ky + r], fill=M.HAUT)
    # kurze Haare: auf den Kopf beschnitten, runder Ansatz über der Stirn,
    # hinten nur bis Ohrhöhe – kein Dutt, kein Bob
    maske = Image.new("L", img.size, 0)
    ImageDraw.Draw(maske).ellipse([kx - r, ky - r, kx + r, ky + r], fill=255)
    haar = Image.new("L", img.size, 0)
    hd = ImageDraw.Draw(haar)
    hd.ellipse([kx - r * 1.25, ky - r * 1.35, kx + r * 0.95, ky - r * 0.05], fill=255)
    hd.ellipse([kx - r * 1.15, ky - r * 0.6, kx - r * 0.25, ky + r * 0.25], fill=255)
    from PIL import ImageChops
    img.paste(Image.new("RGBA", img.size, M.HAAR + (255,)), (0, 0), ImageChops.multiply(maske, haar))
    # Ohr
    d.ellipse([kx - 8 * k, ky - 3 * k, kx + 2 * k, ky + 9 * k], fill=M.HAUT_SCHATTEN)
    d.ellipse([kx + 11 * k, ky - 4 * k, kx + 18 * k, ky + 5 * k], fill=MIDNIGHT)
    w = int(3.5 * k)
    if mund == "laecheln":
        d.line([(kx + 7 * k, ky - 12 * k), (kx + 20 * k, ky - 13 * k)], fill=MIDNIGHT, width=w)
        d.arc([kx + 9 * k, ky + 4 * k, kx + 27 * k, ky + 20 * k], 10, 120, fill=MIDNIGHT, width=w)
    elif mund == "angestrengt":
        d.line([(kx + 7 * k, ky - 11 * k), (kx + 21 * k, ky - 13 * k)], fill=MIDNIGHT, width=w)
        d.ellipse([kx + 15 * k, ky + 10 * k, kx + 24 * k, ky + 18 * k], fill=MIDNIGHT)
        # ein Schweißtropfen hinten an der Stirn
        tx, ty = kx + 38 * k, ky - 18 * k
        d.polygon([(tx, ty - 10 * k), (tx - 5 * k, ty), (tx + 5 * k, ty)], fill=SOFT_BLUE)
        d.ellipse([tx - 5 * k, ty - 4 * k, tx + 5 * k, ty + 6 * k], fill=SOFT_BLUE)
    else:
        d.line([(kx + 7 * k, ky - 14 * k), (kx + 20 * k, ky - 16 * k)], fill=MIDNIGHT, width=w)
        d.ellipse([kx + 12 * k, ky + 8 * k, kx + 24 * k, ky + 21 * k], fill=MIDNIGHT)
    arm(p + math.pi, False)
    return img.resize((img.width // ss, img.height // ss), Image.LANCZOS)


def lauf(t: float, tempo: float = 1.6, **kw) -> Image.Image:
    """Laufschritt im Takt; locker (tempo <= 1.6) mit Lächeln, schneller angestrengt."""
    kw.setdefault("mund", "laecheln" if tempo <= 1.6 else "angestrengt")
    return laeufer(int(t * tempo * PHASEN) % PHASEN, **kw)


# --- Hintergründe -----------------------------------------------------------

@lru_cache(maxsize=None)
def nacht() -> Image.Image:
    img = Image.new("RGBA", (B, H), MIDNIGHT + (255,))
    ImageDraw.Draw(img).ellipse([B / 2 - 520, 980 - 520, B / 2 + 520, 980 + 520], fill=NACHT_HELL)
    return img


def tag(t: float, tempo: float = 1.0) -> Image.Image:
    img = Image.new("RGBA", (B, H), HIMMEL + (255,))
    d = ImageDraw.Draw(img)
    for i, (x0, y0, r) in enumerate(((180, 300, 150), (760, 190, 190), (1300, 380, 130))):
        x = (x0 - t * 22 * tempo) % 1500 - 200
        for dx, dr in ((0, 0), (r * 0.7, -30), (-r * 0.7, -40)):
            d.ellipse([x + dx - r - dr, y0 - (r + dr) * 0.55, x + dx + r + dr, y0 + (r + dr) * 0.55], fill=CREME)
    for farbe, basis, hoehe_, breite, speed in ((HUEGEL_1, 1250, 420, 900, 40), (HUEGEL_2, 1330, 300, 640, 90)):
        for i in range(-1, 4):
            x = i * breite * 0.8 - (t * speed * tempo) % (breite * 0.8)
            d.polygon([(x, basis), (x + breite / 2, basis - hoehe_), (x + breite, basis)], fill=farbe)
        d.rectangle([0, basis, B, H], fill=farbe)
    d.rectangle([0, 1380, B, H], fill=STRASSE)
    d.rectangle([0, 1380, B, 1394], fill=MIDNIGHT)
    for i in range(-1, 6):
        x = i * 300 - (t * 620 * tempo) % 300
        d.rounded_rectangle([x, 1590, x + 150, 1606], radius=8, fill=CREME)
    return img


# --- Szenen: f(bild, t, dauer) ----------------------------------------------

def sz_hook(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = tag(t)
    d = ImageDraw.Draw(img)
    aufkleben(img, lauf(t, hoehe=640), B / 2 - 40, 1404)
    # Tacho mit Fragezeichen
    mx, my, r = B / 2, 720, 240
    d.pieslice([mx - r - 12, my - r - 12, mx + r + 12, my + r + 12], 180, 360, fill=MIDNIGHT)
    d.pieslice([mx - r, my - r, mx + r, my + r], 180, 360, fill=CREME)
    d.pieslice([mx - r, my - r, mx + r, my + r], 300, 360, fill=CORAL)
    d.pieslice([mx - r + 70, my - r + 70, mx + r - 70, my + r - 70], 180, 360, fill=MIDNIGHT)
    w = math.radians(200 + 140 * (0.5 + 0.5 * math.sin(t * 2.3)) * weich(t / 0.8))
    d.line([(mx, my), (mx + (r - 30) * math.cos(w), my + (r - 30) * math.sin(w))], fill=CORAL, width=18)
    d.ellipse([mx - 30, my - 30, mx + 30, my + 30], fill=CREME, outline=MIDNIGHT, width=8)
    pop(d, mx, my - 95, "?", 150, t - dauer * 0.5, fill=CREME, kontur=None)
    pop(d, B / 2, 1490, p.get("zeile", "DEINE SCHWELLE?"), p.get("g", 120), t - dauer * 0.55, fill=CORAL)
    return img


def laufband(d: ImageDraw.ImageDraw, t: float, tempo: float, anzeige: str) -> None:
    d.rounded_rectangle([150, 1396, 860, 1476], radius=40, fill=(10, 30, 46))
    d.rounded_rectangle([170, 1404, 840, 1452], radius=24, fill=(48, 74, 96))
    for i in range(10):
        x = 190 + (i * 66 - t * 420 * tempo) % 640
        d.rectangle([x, 1404, x + 16, 1418], fill=(10, 30, 46))
    d.rounded_rectangle([812, 1010, 838, 1410], radius=10, fill=(48, 74, 96))
    d.rounded_rectangle([730, 960, 930, 1024], radius=14, fill=(48, 74, 96))
    d.rounded_rectangle([760, 870, 930, 980], radius=18, fill=(10, 30, 46), outline=(48, 74, 96), width=10)
    d.text((845, 925), anzeige, font=schrift(64), fill=GRUEN, anchor="mm")
    for i in range(7):
        d.rectangle([i * 170, 1476, i * 170 + 85, H], fill=(0, 50, 76))


def sz_raten(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    stufe = min(2, int(t / (dauer / 3)))
    lt = t - stufe * dauer / 3
    tempo = (1.4, 2.0, 3.0)[stufe]
    abflug = t - dauer * 0.86
    anz = p.get("anzeigen", ["12", "16", "25"])
    laufband(d, t, tempo, anz[stufe] if abflug < 0 else anz[2])
    w3 = p.get("worte", ["VOLLGAS?", "5-KM-TEMPO?", "PULS 180?!"])
    wort, farbe, g = ((w3[0], CREME, 170), (w3[1], CREME, 150), (w3[2], CORAL, 190))[stufe]
    g = min(g, 1700 / max(1, len(wort)) + 20)
    pop(d, B / 2, 620, wort, g, lt, fill=farbe, kontur=None)
    if abflug < 0:
        aufkleben(img, lauf(t, tempo), 470 - 90 * stufe, 1420)
    else:
        f = lauf(t, 3.0, mund="o").rotate(60 + abflug * 520, resample=Image.BICUBIC, expand=True)
        x, y = 290 - abflug * 1500, 1280 - abflug * 700 + abflug * abflug * 2600
        img.alpha_composite(f, (int(x - f.width / 2), int(y - f.height / 2)))
        for i in range(5):
            w = i * 1.3 + abflug * 4
            rr = 44 + 30 * abflug + 8 * math.sin(i)
            cx, cy = 200 + 52 * math.cos(w), 1400 + 34 * math.sin(w)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=CREME)
    return img


def sz_entwarnung(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = tag(t * 0.25)
    d = ImageDraw.Draw(img)
    atem = 1 + 0.015 * math.sin(t * 3.2)
    f = M.figur(p.get("pose", "daumen"), int(840 * atem))
    aufkleben(img, f, B / 2 - 60, 1410)
    blase(d, 770, 560, p.get("blase", "PUH!"), p.get("blase_g", 130), t - 0.25, spitze_x=650)
    pop(d, B / 2, 1490, p.get("zeile", "VIEL ENTSPANNTER"), p.get("g", 118), t - dauer * 0.45, fill=CREME)
    return img


def sz_stunde(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    mx, my, r = B / 2, 880, 320
    k = federn(t / 0.4)
    r = max(130.0, r * k)
    d.rounded_rectangle([mx - 44, my - r - 92, mx + 44, my - r + 10], radius=16, fill=CORAL, outline=MIDNIGHT, width=10)
    d.ellipse([mx - r - 26, my - r - 26, mx + r + 26, my + r + 26], fill=MIDNIGHT)
    d.ellipse([mx - r - 12, my - r - 12, mx + r + 12, my + r + 12], fill=CORAL)
    d.ellipse([mx - r + 22, my - r + 22, mx + r - 22, my + r - 22], fill=CREME)
    for i in range(12):
        w = math.radians(i * 30)
        d.line([(mx + (r - 50) * math.sin(w), my - (r - 50) * math.cos(w)),
                (mx + (r - 82) * math.sin(w), my - (r - 82) * math.cos(w))], fill=MIDNIGHT, width=10)
    anteil = weich((t - 0.4) / (dauer * 0.6))
    d.pieslice([mx - r + 90, my - r + 90, mx + r - 90, my + r - 90], -90, -90 + 360 * anteil, fill=SOFT_BLUE)
    w = math.radians(360 * anteil)
    d.line([(mx, my), (mx + (r - 110) * math.sin(w), my - (r - 110) * math.cos(w))], fill=CORAL, width=16)
    minuten = int(round(60 * anteil))
    d.rounded_rectangle([mx - 190, my - 70, mx + 190, my + 70], radius=24, fill=MIDNIGHT)
    d.text((mx, my), f"{minuten:02d}:00", font=schrift(124), fill=GRUEN, anchor="mm")
    pop(d, B / 2, 1350, "CA. 60 MINUTEN", 150, t - dauer * 0.5, fill=CORAL)
    pop(d, B / 2, 1470, "SO LANGE HÄLTST DU ES DURCH", 62, t - dauer * 0.6, fill=CREME, kontur=None)
    return img


def sz_fass(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    ueber = weich((t - dauer * 0.58) / 0.6)                 # 0 = an der Schwelle, 1 = darüber
    x0, x1, oben, unten = 320, 760, 620, 1280
    stand = 0.48 + 0.02 * math.sin(t * 3) + 0.52 * weich((t - dauer * 0.58) / (dauer * 0.22))
    y = unten - (unten - oben) * min(1.0, stand)
    zu = 26 + 46 * ueber
    # Zulauf
    d.rounded_rectangle([120, 420, 470, 500], radius=24, fill=(48, 74, 96), outline=MIDNIGHT, width=8)
    d.rectangle([430 - zu / 2, 500, 430 + zu / 2, max(500, y)], fill=CORAL)
    # Fass
    d.rounded_rectangle([x0 - 14, oben - 14, x1 + 14, unten + 14], radius=44, fill=MIDNIGHT)
    d.rounded_rectangle([x0, oben, x1, unten], radius=32, fill=CREME)
    pts = [(x0 + 6, unten - 6), (x0 + 6, y)]
    for i in range(0, 21):
        px = x0 + 6 + (x1 - x0 - 12) * i / 20
        pts.append((px, y + 9 * math.sin(i * 0.9 + t * 5)))
    pts += [(x1 - 6, unten - 6)]
    d.polygon(pts, fill=CORAL)
    for yy in (oben + 150, unten - 150):
        d.rectangle([x0 - 14, yy - 9, x1 + 14, yy + 9], fill=MIDNIGHT)
    d.text(((x0 + x1) / 2, unten - 250), "LAKTAT", font=schrift(96), fill=CREME, anchor="mm",
           stroke_width=6, stroke_fill=MIDNIGHT)
    # Abfluss
    d.rounded_rectangle([x1 - 4, unten - 110, x1 + 150, unten - 50], radius=18, fill=(48, 74, 96),
                        outline=MIDNIGHT, width=8)
    d.rectangle([x1 + 104, unten - 50, x1 + 130, 1420], fill=CORAL)
    if stand >= 0.97:
        s = weich((t - dauer * 0.8) / 0.4)
        for xx in (x0 - 40, x1 + 14):
            d.rounded_rectangle([xx, oben - 10, xx + 26, oben - 10 + 700 * s], radius=13, fill=CORAL)
        d.rounded_rectangle([x0 - 40, oben - 34, x1 + 40, oben + 4], radius=19, fill=CORAL)
    d.ellipse([x1 + 20, 1400, x1 + 220, 1450], fill=CORAL)
    if ueber < 0.5:
        pop(d, B / 2, 1500, "ZULAUF = ABFLUSS", 104, t - 0.5, fill=GRUEN)
    else:
        pop(d, B / 2, 1500, "ZU SCHNELL: ES LÄUFT ÜBER", 88, t - dauer * 0.62, fill=CORAL)
    return img


def sz_test(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    k = federn(t / 0.4)
    x0, x1, y0, y1 = 130, 950, 520, 1500
    y1 = y0 + (y1 - y0) * k
    d.rounded_rectangle([x0 + 22, y0 + 26, x1 + 22, y1 + 26], radius=40, fill=(0, 22, 36))
    d.rounded_rectangle([x0, y0, x1, y1], radius=40, fill=CREME)
    d.rounded_rectangle([x0, y0, x1, y0 + 170], radius=40, fill=CORAL)
    d.rectangle([x0, y0 + 120, x1, y0 + 170], fill=CORAL)
    for i in range(6):
        cx = x0 + 90 + i * 128
        d.rounded_rectangle([cx - 11, y0 - 44, cx + 11, y0 + 36], radius=11, fill=CREME, outline=MIDNIGHT, width=6)
    titel = p.get("titel", "DEIN TEST")
    d.text(((x0 + x1) / 2, y0 + 96), titel, font=schrift(min(120, 1450 / len(titel))), fill=WEISS, anchor="mm")
    zeilen = p.get("zeilen", (("30", "MINUTEN"), ("1", "ALLEIN LAUFEN"), ("=", "GLEICHMÄSSIG")))
    for i, (z, wort) in enumerate(zeilen):
        tt = t - dauer * (0.12 + 0.17 * i)
        if tt <= 0 or k < 1:
            continue
        yy = y0 + 280 + i * 180
        if i % 2:
            d.rectangle([x0 + 16, yy - 86, x1 - 16, yy + 86], fill=(244, 234, 216))
        s = federn(tt / 0.3)
        d.ellipse([x0 + 60, yy - 62 * s, x0 + 60 + 124 * s, yy + 62 * s], fill=MIDNIGHT)
        d.text((x0 + 60 + 62 * s, yy), z, font=schrift(76 * s), fill=CREME, anchor="mm")
        d.text((x0 + 220, yy), wort, font=schrift(min(76, 1250 / max(1, len(wort)))), fill=MIDNIGHT, anchor="lm")
    tt = t - dauer * 0.66
    if tt > 0:
        s = federn(tt / 0.35)
        d.rounded_rectangle([B / 2 - 400 * s, 1385 - 74 * s, B / 2 + 400 * s, 1385 + 74 * s], radius=74, fill=GRUEN,
                            outline=MIDNIGHT, width=8)
        fz = p.get("fazit", "DEIN SCHNITT = SCHWELLE")
        d.text((B / 2, 1385), fz, font=schrift(min(76, 1800 / len(fz)) * s), fill=WEISS, anchor="mm")
    return img


def sz_gefuehl(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = tag(t * 0.25)
    d = ImageDraw.Draw(img)
    aufkleben(img, M.figur("winken", 800), B / 2 - 170, 1410)
    pop(d, B / 2, 520, "ANGENEHM HART", 150, t - dauer * 0.12, fill=CORAL)
    a = dauer * 0.42
    for i, (wort, x, y) in enumerate((("Ein", 700, 700), ("paar", 850, 840), ("Worte", 790, 990))):
        blase(d, x, y, wort, 84, t - a - i * 0.3, spitze_x=600 if i == 0 else None)
    tt = t - dauer * 0.74
    if tt > 0:
        blase(d, 880, 1150, "…", 84, tt)
        s = federn(tt / 0.3 - 0.6)
        if s > 0:
            d.line([(810, 1090), (810 + 140 * s, 1090 + 120 * s)], fill=CORAL, width=16)
            d.line([(950, 1090), (950 - 140 * s, 1090 + 120 * s)], fill=CORAL, width=16)
    return img


def sz_schluss(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    p = p or {}
    img = tag(t * 0.4)
    d = ImageDraw.Draw(img)
    sprung = abs(math.sin(t * 5.2)) * 46
    aufkleben(img, M.figur("jubeln", 820), B / 2, 1410 - sprung)
    rng = random.Random(7)
    for i in range(46):
        x = rng.uniform(40, B - 40)
        y = (rng.uniform(-400, 900) + t * rng.uniform(260, 520)) % 1500
        w = rng.uniform(0, 3.1) + t * 4
        farbe = (CORAL, CREME, GELB, GRUEN, MIDNIGHT)[i % 5]
        d.line([(x - 15 * math.cos(w), y - 15 * math.sin(w)), (x + 15 * math.cos(w), y + 15 * math.sin(w))],
               fill=farbe, width=11)
    pop(d, B / 2, 500, p.get("frage", "KENNST DU DEINE?"), p.get("g", 132), t - 0.2, fill=CORAL)
    blase(d, B / 2, 1490, p.get("blase", "4:45 /km – und du?"), 88, t - dauer * 0.45)
    return img


# --- Allgemeine Szenen (Texte und Zahlen kommen aus der Vorlage) -------------

METALL_E = (176, 188, 202)


@lru_cache(maxsize=None)
def gym() -> Image.Image:
    """Kraftraum: Wand mit Streifen, Gummiboden, Hantelständer mit Scheiben."""
    img = Image.new("RGBA", (B, H), (210, 232, 240, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, B, 820], fill=SOFT_BLUE)
    d.rectangle([0, 1380, B, H], fill=(38, 52, 66))
    d.rectangle([0, 1380, B, 1394], fill=MIDNIGHT)
    for x in range(0, B, 180):
        d.line([(x, 1394), (x - 120, H)], fill=(52, 68, 84), width=6)
    # Kurzhanteln im Regal rechts
    d.rounded_rectangle([780, 1250, 1060, 1272], radius=8, fill=MIDNIGHT)
    for x in (800, 1040):
        d.rounded_rectangle([x - 10, 1262, x + 10, 1390], radius=6, fill=MIDNIGHT)
    for i, x in enumerate((830, 905, 980)):
        g = 26 + i * 6
        d.rounded_rectangle([x - 30, 1222, x + 30, 1234], radius=5, fill=METALL_E, outline=MIDNIGHT, width=4)
        for dx in (-30, 30):
            d.rounded_rectangle([x + dx - 11, 1228 - g, x + dx + 11, 1228 + g * 0.4], radius=6,
                                fill=CORAL if i != 1 else MIDNIGHT, outline=MIDNIGHT, width=4)
    # Wandscheiben links
    for i, (x, r) in enumerate(((120, 70), (260, 56))):
        d.ellipse([x - r, 560 - r, x + r, 560 + r], fill=MIDNIGHT)
        d.ellipse([x - r + 12, 560 - r + 12, x + r - 12, 560 + r - 12], fill=CORAL if i == 0 else SOFT_BLUE)
        d.ellipse([x - 12, 548, x + 12, 572], fill=MIDNIGHT)
    return img


@lru_cache(maxsize=None)
def bad() -> Image.Image:
    """Badezimmer: Fliesenwand, Boden – für die Waage am Morgen."""
    img = Image.new("RGBA", (B, H), (232, 242, 246, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, 1380, 120):
        d.line([(0, y), (B, y)], fill=(200, 222, 232), width=5)
    for x in range(0, B, 120):
        d.line([(x, 0), (x, 1380)], fill=(200, 222, 232), width=5)
    d.rectangle([0, 1380, B, H], fill=(120, 160, 180))
    d.rectangle([0, 1380, B, 1394], fill=MIDNIGHT)
    for x in range(-60, B, 160):
        d.line([(x, 1394), (x - 80, H)], fill=(104, 144, 166), width=6)
    # runder Spiegel mit Glanz, daneben ein Handtuch am Haken
    d.ellipse([40, 440, 320, 800], fill=(214, 236, 244), outline=MIDNIGHT, width=10)
    d.line([(110, 540), (170, 480)], fill=CREME, width=14)
    d.line([(120, 600), (220, 500)], fill=CREME, width=8)
    d.ellipse([168, 880, 192, 904], fill=MIDNIGHT)
    d.rounded_rectangle([120, 896, 240, 1140], radius=16, fill=CORAL, outline=MIDNIGHT, width=6)
    for y in (1080, 1104):
        d.line([(124, y), (236, y)], fill=CREME, width=6)
    return img


def winter(t: float, tempo: float = 1.0) -> Image.Image:
    """Wintertag: blasser Himmel, verschneite Hügel, Schneefall, Straße mit Schnee am Rand."""
    img = tag(t, tempo)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, B, 1250], fill=(214, 230, 238))
    for farbe, basis, hoehe_, breite, speed in (((236, 244, 248), 1250, 420, 900, 40), ((250, 252, 253), 1330, 300, 640, 90)):
        for i in range(-1, 4):
            x = i * breite * 0.8 - (t * speed * tempo) % (breite * 0.8)
            d.polygon([(x, basis), (x + breite / 2, basis - hoehe_), (x + breite, basis)], fill=farbe,
                      outline=(176, 200, 214), width=4)
        d.rectangle([0, basis, B, 1380], fill=farbe)
    d.rectangle([0, 1366, B, 1384], fill=WEISS)
    rng = random.Random(11)
    for _ in range(90):
        x0, y0, r, v = rng.uniform(0, B), rng.uniform(0, 1500), rng.uniform(5, 13), rng.uniform(90, 200)
        x = (x0 - t * 60 * tempo + 18 * math.sin(t * 1.3 + y0)) % B
        y = (y0 + t * v) % 1500
        d.ellipse([x - r, y - r, x + r, y + r], fill=WEISS)
    return img


# Die Figur im Hook passt zum Thema: läuft (Standard), hebt die Langhantel,
# hält den Countdown-Kalender, steht auf der Waage, läuft durch den Schnee.
AKTIONEN = ("lauf", "hantel", "kalender", "waage", "winter")


def sz_frage(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Hook: die Figur tut, worum es geht; darüber ein großes Fragezeichen und die Frage."""
    p = p or {}
    aktion = p.get("aktion", "lauf")
    if aktion == "lauf":
        img = tag(t)
        aufkleben(img, lauf(t, hoehe=640), B / 2 - 40, 1404)
    elif aktion == "hantel":
        img = gym().copy()
        # eine Wiederholung je Sekunde, oben kurz halten
        w = 0.5 - 0.5 * math.cos(t * 2 * math.pi * 0.9)
        stufe = min(4, int(w * 5))
        aufkleben(img, M.figur(f"curl{stufe}", 760), B / 2 - 130, 1420)
    elif aktion == "kalender":
        img = tag(t * 0.25)
        von = int(p.get("von", 14))
        tag_ = max(1, von - int(t / max(0.2, dauer * 0.8) * (von - 1)))
        aufkleben(img, M.figur("kalender", 760, text=str(tag_)), B / 2 - 130, 1420)
    elif aktion == "winter":
        img = winter(t, 0.8)
        aufkleben(img, lauf(t, tempo=1.3, hoehe=640), B / 2 - 40, 1404)
        d0 = ImageDraw.Draw(img)
        for i in range(3):                       # Atemwolken vor dem Gesicht
            a = (t * 1.4 + i / 3) % 1
            r = 18 + 40 * a
            x, y = B / 2 + 150 + 120 * a, 880 - 40 * a
            d0.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=WEISS)
    elif aktion == "waage":
        img = bad().copy()
        wippen = int(6 * abs(math.sin(t * 5))) if t < 1.2 else 0
        aufkleben(img, M.figur("waage", 760), B / 2 - 40, 1420 + wippen)
    else:
        raise KeyError(f"unbekannte Aktion: {aktion} (bekannt: {', '.join(AKTIONEN)})")
    d = ImageDraw.Draw(img)
    k = federn(t / 0.4)
    wackeln = 14 * math.sin(t * 3.4)
    r = 170 * k
    mx, my = B / 2 + 250, 560 if aktion == "lauf" else 440
    d.ellipse([mx - r - 12, my - r - 12, mx + r + 12, my + r + 12], fill=MIDNIGHT)
    d.ellipse([mx - r, my - r, mx + r, my + r], fill=CORAL)
    d.polygon([(mx - 130 * k, my + 90 * k), (mx - 50 * k, my + 150 * k), (mx - 200 * k, my + 240 * k)], fill=MIDNIGHT)
    d.text((mx + wackeln * 0.3, my), p.get("symbol", "?"), font=schrift(min(280, 520 / len(p.get("symbol", "?")) + 20) * k), fill=CREME, anchor="mm")
    pop(d, B / 2, 1490, p.get("zeile", "?"), p.get("g", 110), t - dauer * 0.5, fill=CORAL)
    return img


def sz_denken(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Raten lassen: die Figur überlegt, drei Antworten poppen nacheinander auf."""
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    aufkleben(img, M.figur(p.get("pose", "denken"), 720), 230, 1500)
    worte = p.get("worte", ["?", "?", "?"])
    n = len(worte)
    for i, w in enumerate(worte):
        tt = t - dauer * (0.06 + 0.9 * i / n)
        letzte = i == n - 1
        blase(d, 730 - 40 * (i % 2), 560 + i * 230, w, min(100, 1250 / max(6, len(w))), tt,
              spitze_x=420 if i == 0 else None)
        if letzte and tt > 0.5 and p.get("kreuz", True):
            s = federn((tt - 0.5) / 0.3)
            for j in range(n):
                y = 560 + j * 230
                x = 730 - 40 * (j % 2)
                d.line([(x - 250 * s, y - 60 * s), (x + 250 * s, y + 60 * s)], fill=CORAL, width=18)
    return img


def sz_zahl(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Die Zahl als Bild: zählt hoch, darunter Einheit und eine Zeile."""
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    ziel = float(p.get("zahl", 0))
    anteil = weich((t - 0.2) / max(0.6, dauer * 0.45))
    wert = ziel * anteil
    fmt = p.get("format", "{:.0f}")
    if fmt == "min":
        s = f"{int(wert // 60)}:{int(wert % 60):02d}"
    elif fmt == "tausend":
        s = f"{int(round(wert)):,}".replace(",", ".")
    else:
        s = fmt.format(wert).replace(".", ",")
    s = p.get("vor", "") + s + p.get("nach", "")
    g = min(430, 1750 / max(1, len(s)) * 1.75)
    pop(d, B / 2, 560, p.get("oben", ""), 84, t - 0.1, fill=CREME, kontur=None)
    puls = 1 + 0.03 * math.sin(t * 6) * (anteil >= 1)
    d.text((B / 2, 860), s, font=schrift(g * puls), fill=CORAL, anchor="mm", stroke_width=10, stroke_fill=MIDNIGHT)
    pop(d, B / 2, 1120, p.get("einheit", ""), min(140, 1750 / max(1, len(p.get("einheit", "")))), t - dauer * 0.3, fill=CREME, kontur=None)
    pop(d, B / 2, 1330, p.get("zeile", ""), p.get("g", 84), t - dauer * 0.5, fill=GRUEN, kontur=None)
    pop(d, B / 2, 1450, p.get("klein", ""), 60, t - dauer * 0.6, fill=SOFT_BLUE, kontur=None)
    return img


def sz_kacheln(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Zehn Läufe als Kacheln: die meisten locker (blau), wenige hart (coral)."""
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    n, hart = int(p.get("n", 10)), int(p.get("hart", 2))
    spalten = 5
    kb, luecke = 168, 24
    x0 = (B - spalten * kb - (spalten - 1) * luecke) / 2
    y0 = 560
    pop(d, B / 2, 470, p.get("oben", "10 LÄUFE"), 96, t - 0.05, fill=CREME, kontur=None)
    for i in range(n):
        tt = t - 0.15 - i * dauer * 0.045
        if tt <= 0:
            continue
        k = federn(tt / 0.3)
        cx = x0 + (i % spalten) * (kb + luecke) + kb / 2
        cy = y0 + (i // spalten) * (kb + luecke + 60) + kb / 2
        ist_hart = i >= n - hart
        farbe = CORAL if ist_hart else SOFT_BLUE
        h = kb / 2 * k
        d.rounded_rectangle([cx - h - 8, cy - h - 8, cx + h + 8, cy + h + 8], radius=36, fill=(0, 22, 36))
        d.rounded_rectangle([cx - h, cy - h, cx + h, cy + h], radius=30, fill=farbe)
        f = laeufer((i * 3 + int(t * (30 if ist_hart else 14))) % PHASEN, hoehe=150,
                    mund="angestrengt" if ist_hart else "laecheln")
        f = f.resize((int(f.width * k) or 1, int(f.height * k) or 1))
        img.alpha_composite(f, (int(cx - f.width / 2), int(cy - f.height / 2)))
    tt = t - dauer * 0.55
    if tt > 0:
        s = federn(tt / 0.35)
        d.rounded_rectangle([110, 1090 - 0, 110 + 520 * s, 1090 + 150], radius=40, fill=SOFT_BLUE, outline=MIDNIGHT, width=8)
        if s > 0.9:
            d.text((370, 1165), p.get("links", "8 LOCKER"), font=schrift(96), fill=MIDNIGHT, anchor="mm")
    tt = t - dauer * 0.7
    if tt > 0:
        s = federn(tt / 0.35)
        d.rounded_rectangle([970 - 310 * s, 1090, 970, 1090 + 150], radius=40, fill=CORAL, outline=MIDNIGHT, width=8)
        if s > 0.9:
            d.text((815, 1165), p.get("rechts", "2 HART"), font=schrift(96), fill=WEISS, anchor="mm")
    pop(d, B / 2, 1400, p.get("zeile", ""), p.get("g", 88), t - dauer * 0.8, fill=CREME, kontur=None)
    return img


def sz_balken(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Balken nebeneinander: [[Beschriftung, Wert, Text am Balken, Farbe], …]."""
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    balken = p.get("balken", [])
    n = max(1, len(balken))
    hoechst = max([b[1] for b in balken] or [1])
    boden, voll = 1280, 640
    breite = min(220, (B - 200) / n - 40)
    pop(d, B / 2, 480, p.get("oben", ""), p.get("oben_g", 96), t - 0.05, fill=CREME, kontur=None)
    d.rectangle([90, boden, B - 90, boden + 10], fill=CREME)
    farben = {"coral": CORAL, "blau": SOFT_BLUE, "gruen": GRUEN, "gelb": GELB}
    for i, b in enumerate(balken):
        tt = t - 0.3 - i * dauer * 0.16
        if tt <= 0:
            continue
        k = weich(tt / 0.6)
        cx = B / 2 + (i - (n - 1) / 2) * (breite + 90)
        h = voll * b[1] / hoechst * k
        farbe = farben.get(b[3] if len(b) > 3 else "blau", SOFT_BLUE)
        d.rounded_rectangle([cx - breite / 2 - 8, boden - h - 8, cx + breite / 2 + 8, boden], radius=26, fill=(0, 22, 36))
        d.rounded_rectangle([cx - breite / 2, boden - h, cx + breite / 2, boden], radius=20, fill=farbe)
        if k > 0.95:
            d.text((cx, boden - h - 60), b[2], font=schrift(84), fill=CREME, anchor="mm")
        d.text((cx, boden + 62), b[0], font=schrift(52), fill=SOFT_BLUE, anchor="mm")
    pop(d, B / 2, 1450, p.get("zeile", ""), p.get("g", 88), t - dauer * 0.7, fill=GRUEN, kontur=None)
    return img


def sz_schichten(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Das Zwiebelprinzip im Schnitt: unten die Haut, darüber drei Schichten, die
    nacheinander auftauchen – Schweiß wandert nach außen.
    `schichten`: [[Titel, Zeile, Farbe, Anteil der Dauer], …] von innen nach außen."""
    p = p or {}
    img = nacht().copy()
    d = ImageDraw.Draw(img)
    farben = {"coral": CORAL, "blau": SOFT_BLUE, "gruen": GRUEN, "gelb": GELB, "creme": CREME}
    pop(d, B / 2, 420, p.get("oben", "DAS ZWIEBELPRINZIP"), p.get("oben_g", 110), t - 0.05, fill=CORAL)
    links, rechts, hoehe, unten = 120, B - 120, 200, 1300
    d.rounded_rectangle([links, unten, rechts, unten + 90], radius=28, fill=(232, 190, 160), outline=MIDNIGHT, width=8)
    d.text((B / 2, unten + 45), p.get("haut", "HAUT"), font=schrift(56), fill=MIDNIGHT, anchor="mm")
    schichten = p.get("schichten", [])
    sichtbar = 0
    for i, (titel, zeile, farbe, ab) in enumerate(schichten):
        tt = t - dauer * ab
        if tt <= 0:
            continue
        sichtbar = i + 1
        k = federn(tt / 0.4)
        y1 = unten - 14 - i * (hoehe + 14)
        y0 = y1 - hoehe * k
        f = farben.get(farbe, SOFT_BLUE)
        d.rounded_rectangle([links, y0, rechts, y1], radius=30, fill=f, outline=MIDNIGHT, width=8)
        if k > 0.9:
            schrift_farbe = MIDNIGHT if farbe in ("blau", "creme", "gelb") else WEISS
            d.text((links + 50, y1 - hoehe + 62), titel, font=schrift(74), fill=schrift_farbe, anchor="lm")
            d.text((links + 50, y1 - hoehe + 142), zeile, font=schrift(50, fett=False), fill=schrift_farbe, anchor="lm")
    oben_rand = unten - 14 - sichtbar * (hoehe + 14) + 14
    # Schweißtropfen wandern von der Haut nach außen (nur durch sichtbare Schichten)
    for j in range(4):
        a = (t * 0.45 + j / 4) % 1
        y = unten - a * (unten - oben_rand + 60)
        x = rechts - 120 - 46 * j
        r = 16
        d.polygon([(x, y - r * 1.8), (x - r, y), (x + r, y)], fill=CREME)
        d.ellipse([x - r, y - r, x + r, y + r], fill=CREME)
    pop(d, B / 2, 1490, p.get("zeile", ""), p.get("g", 88), t - dauer * 0.9, fill=GRUEN, kontur=None)
    return img


def sz_figur(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Die Figur in einer Pose, Titel oben, Sprechblasen nacheinander, Zeile unten."""
    p = p or {}
    img = tag(t * 0.25) if p.get("grund", "tag") == "tag" else nacht().copy()
    d = ImageDraw.Draw(img)
    atem = 1 + 0.012 * math.sin(t * 3.2)
    aufkleben(img, M.figur(p.get("pose", "zeigen"), int(800 * atem), p.get("person", "er")), B / 2 - 190, 1410)
    pop(d, B / 2, 500, p.get("titel", ""), p.get("titel_g", 130), t - dauer * 0.08, fill=CORAL)
    blasen = p.get("blasen", [])
    for i, w in enumerate(blasen):
        blase(d, 750 + 20 * (i % 2), 720 + i * 170, w, min(84, 960 / max(6, len(w))),
              t - dauer * (0.3 + 0.5 * i / max(1, len(blasen))), spitze_x=590 if i == 0 else None)
    pop(d, B / 2, 1490, p.get("zeile", ""), p.get("g", 96), t - dauer * 0.6, fill=CREME)
    return img


def radler(t: float, hoehe: int = 620) -> Image.Image:
    """Unser Maskottchen auf dem Rennrad, Blick nach rechts (RGBA): Helm mit
    Mütze darunter, Jacke vorn in Coral (winddicht), hinten Soft Blue
    (luftig), dunkle Überschuhe; die Kurbel dreht sich."""
    ss = 2
    k = hoehe / 520 * ss
    img = Image.new("RGBA", (int(620 * k), int(520 * k)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hinten_rad, vorn_rad, tretlager = (130, 400), (470, 400), (285, 400)
    sattel, lenker, steuer = (235, 245), (440, 238), (420, 262)
    r = 100
    for cx, cy in (hinten_rad, vorn_rad):
        X, Y = cx * k, cy * k
        d.ellipse([X - (r + 8) * k, Y - (r + 8) * k, X + (r + 8) * k, Y + (r + 8) * k], fill=MIDNIGHT)
        d.ellipse([X - (r - 6) * k, Y - (r - 6) * k, X + (r - 6) * k, Y + (r - 6) * k], fill=(214, 230, 238))
        for i in range(6):
            a = t * 9 + i * math.pi / 3
            d.line([(X, Y), (X + (r - 8) * k * math.cos(a), Y + (r - 8) * k * math.sin(a))],
                   fill=(150, 176, 190), width=int(3 * k))
        d.ellipse([X - 9 * k, Y - 9 * k, X + 9 * k, Y + 9 * k], fill=MIDNIGHT)
    rahmen = [(hinten_rad, tretlager), (tretlager, sattel), (sattel, hinten_rad), (sattel, steuer),
              (tretlager, steuer), (steuer, vorn_rad)]
    for a, b in rahmen:
        _glied(d, [a, b], 9, CORAL, k)
    _glied(d, [steuer, lenker, (452, 262)], 7, MIDNIGHT, k, kontur=False)
    huefte, schulter, kopf = (232, 228), (360, 168), (405, 128)
    a = t * 9

    def bein(q, hinten):
        pedal = (tretlager[0] + 42 * math.cos(q), tretlager[1] + 42 * math.sin(q))
        dx, dy = pedal[0] - huefte[0], pedal[1] - huefte[1]
        dist = min(math.hypot(dx, dy), 238)
        winkel = math.atan2(dy, dx)
        beuge = math.acos(max(-1, min(1, dist / 240)))
        knie = (huefte[0] + 120 * math.cos(winkel - beuge), huefte[1] + 120 * math.sin(winkel - beuge))
        _glied(d, [huefte, knie, pedal], 26, (40, 46, 56) if hinten else M.HOSE, k)
        _glied(d, [(pedal[0] - 18, pedal[1] + 2), (pedal[0] + 26, pedal[1] + 4)], 22,
               (20, 30, 44) if hinten else MIDNIGHT, k)

    bein(a + math.pi, True)
    _glied(d, [huefte, schulter], 58, SOFT_BLUE, k)                   # Rücken: luftig
    _glied(d, [(huefte[0] + 22, huefte[1] + 14), (schulter[0] + 14, schulter[1] + 20)], 30, CORAL, k,
           kontur=False)                                               # Front: winddicht
    bein(a, False)
    _glied(d, [schulter, (402, 214), lenker], 20, CORAL, k)
    _glied(d, [lenker], 18, MIDNIGHT, k)                               # Handschuh
    kx, ky, rk = kopf[0] * k, kopf[1] * k, 36 * k
    d.ellipse([kx - rk - 5 * k, ky - rk - 5 * k, kx + rk + 5 * k, ky + rk + 5 * k], fill=MIDNIGHT)
    d.ellipse([kx - rk, ky - rk, kx + rk, ky + rk], fill=M.HAUT)
    d.chord([kx - rk - 4 * k, ky - rk - 2 * k, kx + rk + 4 * k, ky + rk], 180, 360, fill=SOFT_BLUE)   # Mütze
    d.chord([kx - rk - 12 * k, ky - rk - 22 * k, kx + rk + 10 * k, ky + rk - 18 * k], 180, 360,
            fill=CORAL, outline=MIDNIGHT, width=int(5 * k))                                         # Helm
    d.ellipse([kx + 14 * k, ky + 2 * k, kx + 22 * k, ky + 10 * k], fill=MIDNIGHT)
    d.arc([kx + 12 * k, ky + 12 * k, kx + 30 * k, ky + 26 * k], 10, 120, fill=MIDNIGHT, width=int(4 * k))
    return img.resize((img.width // ss, img.height // ss), Image.LANCZOS)


def sz_rad(t: float, dauer: float, p: dict | None = None) -> Image.Image:
    """Auf dem Rad: Fahrtwind von vorn, Hinweise zeigen auf Brust, Rücken, Kopf, Füße.
    `hinweise`: [[Text, Ziel (brust/ruecken/kopf/fuss), Anteil der Dauer], …]."""
    p = p or {}
    img = winter(t, 1.8)
    d = ImageDraw.Draw(img)
    rng = random.Random(3)
    for _ in range(9):                                   # Fahrtwind
        y, l, v = rng.uniform(700, 1250), rng.uniform(80, 200), rng.uniform(900, 1400)
        x = B - (rng.uniform(0, B) + t * v) % (B + 300)
        d.line([(x, y), (x + l, y)], fill=WEISS, width=10)
    fahrer = radler(t, 700)
    x0, unten = B / 2 - fahrer.width / 2, 1420
    img.alpha_composite(fahrer, (int(x0), int(unten - fahrer.height)))
    s = fahrer.width / 620
    ziele = {"kopf": (405, 85), "brust": (390, 205), "ruecken": (250, 190), "fuss": (300, 440)}
    orte = {"kopf": (780, 580), "brust": (830, 1010), "ruecken": (230, 760), "fuss": (210, 1150)}
    d = ImageDraw.Draw(img)
    pop(d, B / 2, 440, p.get("titel", "AUF DEM RAD"), p.get("titel_g", 110), t - 0.05, fill=CORAL)
    for txt, ziel, ab in p.get("hinweise", []):
        tt = t - dauer * ab
        if tt <= 0:
            continue
        zx, zy = x0 + ziele[ziel][0] * s, unten - fahrer.height + ziele[ziel][1] * s
        ox, oy = orte[ziel]
        k = weich(tt / 0.25)
        d.line([(ox, oy), (ox + (zx - ox) * k, oy + (zy - oy) * k)], fill=MIDNIGHT, width=8)
        d.ellipse([zx - 14, zy - 14, zx + 14, zy + 14], fill=CORAL, outline=MIDNIGHT, width=5) if k >= 1 else None
        blase(d, ox, oy, txt, min(70, 820 / max(6, len(txt))), tt)
    return img


SZENEN = {"frage": sz_frage, "denken": sz_denken, "zahl": sz_zahl, "kacheln": sz_kacheln,
          "balken": sz_balken, "figur": sz_figur, "schichten": sz_schichten, "rad": sz_rad, "hook": sz_hook, "raten": sz_raten, "entwarnung": sz_entwarnung, "stunde": sz_stunde,
          "fass": sz_fass, "test": sz_test, "gefuehl": sz_gefuehl, "schluss": sz_schluss}


# --- Untertitel: Wort für Wort ----------------------------------------------

def wortzeiten(szenen: list[dict]) -> list[tuple[str, float, float, int]]:
    """(Wort, von, bis, Gruppe) – die Zeit je Wort nach seiner Länge verteilt.

    Mit Sprecher nennt die Vorlage je Szene `teile`: [[von, bis, Wörter], …] –
    die Satzstücke der Aufnahme (aus `ffmpeg … silencedetect`), damit das
    markierte Wort auch nach einer Sprechpause stimmt.
    """
    aus, gruppe = [], 0
    for s in szenen:
        woerter = s["text"].split()
        teile = s.get("teile") or [[s["von"], s["sprech_bis"], len(woerter)]]
        if sum(t[2] for t in teile) != len(woerter):
            raise ValueError(f"teile passen nicht zum Text: {s['text']!r}")
        zeile, i = 0, 0
        for von, bis, n in teile:
            stueck = woerter[i:i + n]
            i += n
            gesamt = sum(len(w) + 1 for w in stueck)
            t = von
            for w in stueck:
                dt = (bis - von) * (len(w) + 1) / gesamt
                if zeile + len(w) > 17 and zeile:
                    gruppe, zeile = gruppe + 1, 0
                aus.append((w, t, t + dt, gruppe))
                zeile += len(w) + 1
                t += dt
                if w[-1] in ".?!:":
                    gruppe, zeile = gruppe + 1, 0
        gruppe += 1
    return aus


def untertitel(img: Image.Image, woerter, t: float) -> None:
    aktiv = [w for w in woerter if w[1] <= t < w[2]] or [w for w in woerter if w[1] <= t][-1:]
    if not aktiv:
        return
    zeile = [w for w in woerter if w[3] == aktiv[0][3]]
    f = text_schrift(64, True)
    breiten = [f.getlength(w[0]) for w in zeile]
    luecke = 22
    gesamt = sum(breiten) + luecke * (len(zeile) - 1)
    x, y = (B - gesamt) / 2, 300
    ebene = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ebene)
    d.rounded_rectangle([x - 34, y - 56, x + gesamt + 34, y + 56], radius=30, fill=MIDNIGHT + (200,))
    for w, b in zip(zeile, breiten):
        if w is aktiv[0]:
            d.rounded_rectangle([x - 12, y - 42, x + b + 12, y + 42], radius=20, fill=CORAL + (255,))
        farbe = WEISS if w[1] <= t else (150, 176, 190)
        d.text((x, y), w[0], font=f, fill=farbe, anchor="lm")
        x += b + luecke
    img.alpha_composite(ebene)


# --- Rendern ----------------------------------------------------------------

def plane(spec: dict) -> list[dict]:
    szenen, t = [], 0.0
    zeiten = spec.get("zeiten")
    for i, s in enumerate(spec["szenen"]):
        ende = None
        if zeiten:
            # [von, bis] oder [von, bis, Ende des Sprechens] aus der Aufnahme
            von, bis, *rest = zeiten[i]
            ende = rest[0] if rest else None
        else:
            von, bis = t, t + len(s["text"]) / ZEICHEN_JE_S + PAUSE_S
        szenen.append({**s, "von": von, "bis": bis, "sprech_bis": ende or bis - PAUSE_S * 0.6})
        t = bis
    return szenen


def bild_bei(szenen: list[dict], woerter, t: float) -> Image.Image:
    s = next((x for x in szenen if x["von"] <= t < x["bis"]), szenen[-1])
    img = SZENEN[s["bild"]](t - s["von"], s["bis"] - s["von"], s)
    untertitel(img, woerter, t)
    return img


def rendere(vorlage: Path, ziel: Path, stimme: Path | None = None) -> float:
    spec = json.loads(vorlage.read_text(encoding="utf-8"))
    szenen = plane(spec)
    woerter = wortzeiten(szenen)
    gesamt = szenen[-1]["bis"] + 0.6
    with tempfile.TemporaryDirectory() as tmp:
        beat = Path(tmp) / "beat.wav"
        insta_musik.schreibe_wav(beat, gesamt + 0.2, int(spec.get("seed", 5)),
                                 schnitte=[s["von"] for s in szenen[1:]])
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{B}x{H}",
               "-r", str(FPS), "-i", "-", "-i", str(beat)]
        if stimme:
            cmd += ["-i", str(stimme), "-filter_complex",
                    "[1:a]volume=0.16[b];[2:a]volume=1.0[s];[s][b]amix=inputs=2:duration=longest:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-filter_complex", "[1:a]volume=0.5[a]", "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-b:a", "192k", "-t", f"{gesamt:.2f}", "-movflags", "+faststart", str(ziel)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(int(gesamt * FPS)):
            p.stdin.write(bild_bei(szenen, woerter, i / FPS).convert("RGB").tobytes())
        p.stdin.close()
        if p.wait():
            raise RuntimeError("ffmpeg ist gescheitert")
    return gesamt


def rendere_beitrag(thema: str, ordner: Path) -> dict:
    """Für den täglichen Lauf (insta_lauf.rendere_beitrag): reel.mp4 und
    cover.jpg nach `ordner`, Metadaten wie insta_video.rendere. Die
    Sprecheraufnahme liegt neben der Vorlage (<thema>.mp3); ohne sie läuft
    nur der Beat."""
    vorlage = Path(__file__).resolve().parent.parent / "marketing" / "instagram" / "erklaer" / f"{thema}.json"
    stimme = vorlage.with_suffix(".mp3")
    ordner.mkdir(parents=True, exist_ok=True)
    dauer = rendere(vorlage, ordner / "reel.mp4", stimme if stimme.exists() else None)
    szenen = plane(json.loads(vorlage.read_text(encoding="utf-8")))
    t = szenen[0]["von"] + (szenen[0]["bis"] - szenen[0]["von"]) * 0.9
    bild_bei(szenen, wortzeiten(szenen), t).convert("RGB").save(ordner / "cover.jpg", quality=90)
    return {"dauer_s": round(dauer, 1), "thumb_offset_ms": int(t * 1000), "hintergrund": {"art": "gezeichnet"},
            "nachweis": None, "musik": "Sprecher + Beat" if stimme.exists() else "Beat",
            "einstieg": None, "uebergang": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vorlage", type=Path)
    ap.add_argument("--aus", type=Path, required=True)
    ap.add_argument("--stimme", type=Path, help="Sprachaufnahme (mp3/wav)")
    ap.add_argument("--bogen", type=Path, help="statt des Videos: ein Bild je Szene als Übersicht")
    a = ap.parse_args(argv)
    if a.bogen:
        spec = json.loads(a.vorlage.read_text(encoding="utf-8"))
        szenen = plane(spec)
        woerter = wortzeiten(szenen)
        zeiten = [s["von"] + (s["bis"] - s["von"]) * f for s in szenen for f in (0.35, 0.9)]
        bogen = Image.new("RGB", (270 * 8, 480 * math.ceil(len(zeiten) / 8)), MIDNIGHT)
        for i, t in enumerate(zeiten):
            bogen.paste(bild_bei(szenen, woerter, t).convert("RGB").resize((270, 480)), (i % 8 * 270, i // 8 * 480))
        bogen.save(a.bogen)
        print(a.bogen)
        return 0
    t = rendere(a.vorlage, a.aus, a.stimme)
    print(f"{a.aus} ({t:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
