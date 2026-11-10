#!/usr/bin/env python3
"""Das Maskottchen der Instagram-Karussells: eine kleine Karikatur, die
auf jeder Seite eines Beitrags etwas tut, das zum Inhalt passt (Nudeln
essen, auf der Waage stehen, „Stopp!“ zeigen …).

Vom Nutzer am 10.11.2026 gewünscht: „einen fiktiven Charakter …, der
einen auf den Seiten begleitet und immer eine Aktivität macht oder etwas
zusammenhängendes mit der Seite. Einfach eine kleine Karikatur, die die
Seite bisschen interessanter macht. So ein bisschen ein Maskottchen, das
auf allen Instagram Posts begleitet.“

Stil wie die Laufende Figur der Reels (`insta_figur.py`) und der
Bauarbeiter in clubs.html: flache Flächen, dunkle Kontur, großer runder
Kopf, Bäckchen, weißer Sticker-Rand. Die Farben sind die neuen
Instagram-Farben (Soft Blue, Midnight Navy, Coral Orange, siehe
`insta_karussell.FARBEN`).

Die Figur steht von vorn. Jede Pose legt nur die Arme (zwei Winkel je
Arm), den Mund und ein Zubehör fest; `figur(pose, hoehe)` gibt ein
RGBA-Bild mit Sticker-Rand zurück. Alles mit Pillow, viermal so groß
gezeichnet und verkleinert. Neue Pose: Eintrag in `POSEN`, Zubehör in
`_zubehoer()`; `test_insta_karussell` zeichnet jede Pose.
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Die neuen Instagram-Farben (Bild des Nutzers vom 10.11.2026)
SOFT_BLUE = (182, 223, 237)     # #B6DFED
MIDNIGHT = (0, 41, 65)          # #002941
CORAL = (253, 110, 110)         # #FD6E6E
WEISS = (255, 255, 255)

KONTUR = MIDNIGHT
HAUT = (240, 200, 166)
HAUT_SCHATTEN = (222, 178, 142)
HAAR = (62, 44, 34)           # dunkelbraun
BART = (132, 100, 76)         # kurzer Vollbart, heller als das Haar
BRILLE = (176, 104, 52)       # Hornbrille, Schildpatt
GLAS = (205, 228, 238)
SHIRT = (22, 70, 100)         # Laufshirt: dunkles Petrol, Soft-Blue-Streifen
SHIRT_STREIFEN = SOFT_BLUE
HOSE = (54, 60, 70)
HAAR_SIE = (122, 80, 50)      # mittelbraun, Pferdeschwanz

# Zwei Figuren, die sich abwechseln (vom Nutzer am 10.11.2026: „auch noch
# bitte eine weibliche Person … mal die weibliche Person in einem Post und
# mal ich. Das ist einfach random. Die Posts sollen aber nicht nach
# mansplaining aussehen“): „er“ = der Nutzer, „sie“ = eine Läuferin mit
# Pferdeschwanz. Beide gleichwertig: dieselben Posen, dieselbe Rolle.
PERSONEN = {
    "er": {"haar": HAAR, "shirt": (22, 70, 100), "streifen": SOFT_BLUE, "hose": HOSE},
    "sie": {"haar": HAAR_SIE, "shirt": CORAL, "streifen": MIDNIGHT, "hose": MIDNIGHT},
}
HOLZ = (176, 122, 78)
HOLZ_DUNKEL = (140, 94, 58)
NUDEL = (246, 206, 92)
SOSSE = (226, 72, 58)
BANANE = (250, 214, 74)
METALL = (176, 188, 202)

SS = 4                 # Supersampling
EIN_B, EIN_H = 300, 360  # Zeichenfläche in Einheiten
BODEN = 344            # Fußsohlen

# Arm: (Oberarm, Unterarm) als Winkel in Grad, 0 = senkrecht nach unten,
# positiv = zur Bildmitte hin gedreht ist NICHT gemeint: Winkel zeigen im
# Bild, 90 = waagerecht nach außen (links für den linken Arm, rechts für
# den rechten), 180 = nach oben.
POSEN: dict[str, dict] = {
    "stehen": {"links": (20, 20), "rechts": (20, 20), "mund": "laecheln"},
    "winken": {"links": (20, 20), "rechts": (150, 175), "mund": "lachen", "zubehoer": ["wink"]},
    "nudeln": {"links": (-35, -70), "rechts": (-10, -150), "mund": "kauen",
               "zubehoer": ["stuhl", "tisch", "gabel"], "sitzen": True},
    "banane": {"links": (20, 25), "rechts": (120, 150), "mund": "lachen", "zubehoer": ["banane"]},
    "zeigen": {"links": (-35, -95), "rechts": (125, 140), "mund": "laecheln", "zubehoer": ["zeigefinger"]},
    "denken": {"links": (-30, -110), "rechts": (-20, -160), "mund": "o", "zubehoer": ["fragezeichen"]},
    "stopp": {"links": (20, 20), "rechts": (115, 175), "mund": "streng", "zubehoer": ["stopphand"]},
    "daumen": {"links": (20, 20), "rechts": (110, 165), "mund": "lachen", "zubehoer": ["daumen"]},
    "waage": {"links": (75, 120), "rechts": (75, 120), "mund": "o", "zubehoer": ["waage"]},
    "kalender": {"links": (-30, -100), "rechts": (-30, -100), "mund": "laecheln", "zubehoer": ["kalender"]},
    "jubeln": {"links": (150, 165), "rechts": (150, 165), "mund": "lachen", "zubehoer": ["konfetti"]},
}


class _Stift:
    def __init__(self, d: ImageDraw.ImageDraw, k: float):
        self.d, self.k = d, k

    def p(self, x, y):
        return x * self.k, y * self.k

    @property
    def o(self) -> float:
        return 5.0 * self.k

    def kreis(self, x, y, r, fill, kontur=True):
        x, y, r, o = x * self.k, y * self.k, r * self.k, self.o
        if kontur:
            self.d.ellipse([x - r - o, y - r - o, x + r + o, y + r + o], fill=KONTUR)
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill, kontur=True):
        o = self.o if kontur else 0
        x0, y0, x1, y1 = (v * self.k for v in (x0, y0, x1, y1))
        if kontur:
            self.d.ellipse([x0 - o, y0 - o, x1 + o, y1 + o], fill=KONTUR)
        self.d.ellipse([x0, y0, x1, y1], fill=fill)

    def rechteck(self, x0, y0, x1, y1, fill, radius=8, kontur=True):
        o = self.o if kontur else 0
        x0, y0, x1, y1 = (v * self.k for v in (x0, y0, x1, y1))
        r = radius * self.k
        if kontur:
            self.d.rounded_rectangle([x0 - o, y0 - o, x1 + o, y1 + o], radius=r + o, fill=KONTUR)
        self.d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill)

    def glied(self, punkte, breite, fill, kontur=True):
        pts = [self.p(*q) for q in punkte]
        b = breite * self.k
        for farbe, extra in ((KONTUR, self.o) if kontur else (None, 0), (fill, 0)):
            if farbe is None:
                continue
            w = b + 2 * extra
            if len(pts) > 1:
                self.d.line(pts, fill=farbe, width=int(round(w)), joint="curve")
            for x, y in pts:
                self.d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=farbe)

    def linie(self, punkte, breite, fill):
        pts = [self.p(*q) for q in punkte]
        w = breite * self.k
        self.d.line(pts, fill=fill, width=max(1, int(round(w))), joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def _arm_punkte(schulter, winkel, seite):
    """Ellbogen und Hand aus zwei Winkeln (Grad, 0 = unten, 90 = außen,
    180 = oben, negativ = zur Körpermitte)."""
    sx, sy = schulter
    s = -1 if seite == "links" else 1
    a1, a2 = (math.radians(w) for w in winkel)
    ex, ey = sx + s * 46 * math.sin(a1), sy + 46 * math.cos(a1)
    hx, hy = ex + s * 42 * math.sin(a2), ey + 42 * math.cos(a2)
    return (ex, ey), (hx, hy)


def _schrift(g: int) -> ImageFont.FreeTypeFont | None:
    from pathlib import Path
    pfad = Path(__file__).resolve().parent.parent / "marketing" / "instagram" / "fonts" / "BarlowCondensed-700-latin.ttf"
    try:
        return ImageFont.truetype(str(pfad), g)
    except OSError:
        return None


def _zubehoer_hinten(s: _Stift, name: str, haende: dict) -> None:
    """Zubehör, das HINTER der Figur liegt (Waage unter den Füßen, Stuhl)."""
    if name == "stuhl":
        s.rechteck(92, 150, 208, 270, HOLZ_DUNKEL, radius=14)
        s.rechteck(104, 162, 196, 270, HOLZ, radius=10, kontur=False)
    if name == "waage":
        s.rechteck(84, BODEN - 4, 216, BODEN + 14, WEISS, radius=8)
        s.rechteck(130, BODEN + 1, 170, BODEN + 10, CORAL, radius=3, kontur=False)


def _zubehoer(s: _Stift, name: str, haende: dict, img: Image.Image) -> None:
    hl, hr = haende["links"], haende["rechts"]
    k = s.k
    if name == "tisch":
        # Tischplatte vor dem Bauch, Tischtuch in Soft Blue, Teller Nudeln
        s.rechteck(18, 252, 282, 272, HOLZ, radius=6)
        s.rechteck(26, 270, 274, 314, SOFT_BLUE, radius=4)
        for x in range(36, 270, 24):
            s.d.line([s.p(x, 272), s.p(x, 312)], fill=WEISS, width=int(5 * s.k))
        for x in (44, 256):
            s.rechteck(x - 7, 314, x + 7, BODEN + 6, HOLZ_DUNKEL, radius=3)
        # Teller mit Nudeln und Soße
        x, y = 196, 252
        s.ellipse(x - 52, y - 16, x + 52, y + 10, WEISS)
        for i, dx in enumerate((-30, -16, -2, 12, 26)):
            s.linie([(x + dx, y - 4), (x + dx + 7, y - 20 - (i % 2) * 6), (x + dx + 14, y - 6)], 4.4, NUDEL)
        s.kreis(x - 4, y - 16, 8, SOSSE, kontur=False)
        s.kreis(x + 14, y - 12, 4, (90, 150, 70), kontur=False)
        # Glas Wasser links
        s.rechteck(52, 214, 76, 252, (220, 238, 246), radius=3)
        s.d.rectangle([s.p(55, 226)[0], s.p(55, 226)[1], s.p(73, 250)[0], s.p(73, 250)[1]], fill=SOFT_BLUE)
    elif name == "schuessel":
        x, y = hl[0] + 30, hl[1] - 4
        # Nudelberg, dann die Schüssel davor
        for i, dx in enumerate((-26, -12, 2, 16, 28)):
            s.linie([(x + dx, y - 6), (x + dx + 6, y - 22 - (i % 2) * 6), (x + dx + 12, y - 8)], 4.2, NUDEL)
        s.kreis(x - 6, y - 16, 6, SOSSE, kontur=False)
        s.ellipse(x - 44, y - 10, x + 44, y + 34, WEISS)
        s.d.rectangle([(x - 50) * k, (y - 14) * k, (x + 50) * k, (y + 6) * k], fill=(0, 0, 0, 0))
        s.d.line([s.p(x - 46, y + 6), s.p(x + 46, y + 6)], fill=KONTUR, width=int(5 * k))
        s.d.ellipse([(x - 40) * k, (y + 12) * k, (x + 40) * k, (y + 18) * k], fill=SOFT_BLUE)
    elif name == "gabel":
        x, y = hr
        s.linie([(x, y + 14), (x - 4, y - 30)], 5, METALL)
        for dx in (-9, -3, 3):
            s.linie([(x - 4 + dx, y - 30), (x - 4 + dx, y - 44)], 2.6, METALL)
        # eine Nudel hängt herunter
        s.linie([(x - 6, y - 40), (x - 14, y - 22), (x - 8, y - 6)], 3.6, NUDEL)
    elif name == "banane":
        # eine große Banane, die senkrecht aus der erhobenen Faust ragt:
        # Mittellinie als Bogen nach außen, Breite zur Mitte hin am größten
        x, y = hr
        links, rechts = [], []
        for i in range(15):
            t = i / 14
            mx_ = x + 2 + 20 * math.sin(math.pi * t)
            my_ = y - 8 - 92 * (1 - t)
            w = 3 + 13 * math.sin(math.pi * t) ** 0.8
            links.append((mx_ - w, my_))
            rechts.append((mx_ + w, my_))
        s.d.polygon([s.p(*q) for q in links + rechts[::-1]], fill=BANANE, outline=KONTUR,
                    width=int(5 * k))
        s.linie([(links[3][0] + 9, links[3][1] + 8), (links[10][0] + 11, links[10][1])], 3, (226, 180, 40))
        s.linie([(x + 1, y - 100), (x - 3, y - 112)], 7, HAAR)
        s.kreis(x, y, 11, HAUT)
    elif name == "zeigefinger":
        x, y = hr
        s.glied([(x, y), (x + 10, y - 22)], 7, HAUT)
    elif name == "stopphand":
        x, y = hr
        for dx in (-10, -3.5, 3.5, 10):
            s.glied([(x + dx, y - 6), (x + dx * 1.1, y - 24)], 6.5, HAUT)
        s.glied([(x - 12, y + 2), (x - 22, y - 8)], 6.5, HAUT)
        s.kreis(x, y, 13, HAUT)
    elif name == "daumen":
        x, y = hr
        s.kreis(x, y, 12, HAUT)
        s.glied([(x - 2, y - 8), (x - 4, y - 28)], 8, HAUT)
    elif name == "wink":
        x, y = hr
        for i, r in enumerate((26, 38)):
            s.d.arc([(x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k], 290 - i * 6, 340,
                    fill=CORAL, width=int(4 * k))
    elif name == "fragezeichen":
        f = _schrift(int(70 * k))
        if f:
            s.d.text(((hr[0] + 46) * k, (hr[1] - 120) * k), "?", font=f, fill=CORAL, anchor="mm",
                     stroke_width=int(4 * k), stroke_fill=WEISS)
    elif name == "kalender":
        x = (hl[0] + hr[0]) / 2
        y = min(hl[1], hr[1]) - 10
        s.rechteck(x - 46, y - 60, x + 46, y + 20, WEISS, radius=8)
        s.d.rectangle([(x - 46) * k, (y - 60) * k, (x + 46) * k, (y - 38) * k], fill=CORAL)
        for dx in (-24, 24):
            s.linie([(x + dx, y - 70), (x + dx, y - 52)], 6, KONTUR)
        f = _schrift(int(54 * k))
        if f:
            s.d.text((x * k, (y - 8) * k), "2", font=f, fill=KONTUR, anchor="mm")
        for h in (hl, hr):
            s.kreis(h[0], h[1], 10, HAUT)
    elif name == "konfetti":
        import random
        r = random.Random(4)
        for _ in range(22):
            x, y = r.uniform(20, 280), r.uniform(10, 120)
            w = r.uniform(0, math.pi)
            farbe = r.choice((CORAL, SOFT_BLUE, NUDEL))
            dx, dy = 7 * math.cos(w), 7 * math.sin(w)
            s.linie([(x - dx, y - dy), (x + dx, y + dy)], 4.5, farbe)


def _mund(s: _Stift, art: str, mx: float, my: float) -> None:
    k = s.k
    if art == "lachen":
        s.d.chord([(mx - 18) * k, (my - 10) * k, (mx + 18) * k, (my + 18) * k], 0, 180, fill=KONTUR)
        s.d.chord([(mx - 15) * k, (my - 6) * k, (mx + 15) * k, (my + 8) * k], 0, 180, fill=WEISS)
    elif art == "o":
        s.d.ellipse([(mx - 8) * k, (my - 4) * k, (mx + 8) * k, (my + 14) * k], fill=KONTUR)
    elif art == "kauen":
        s.d.ellipse([(mx - 14) * k, (my - 2) * k, (mx + 14) * k, (my + 12) * k], fill=KONTUR)
        s.d.ellipse([(mx - 8) * k, (my + 1) * k, (mx + 8) * k, (my + 9) * k], fill=(150, 60, 60))
    elif art == "streng":
        s.linie([(mx - 14, my + 6), (mx + 14, my + 6)], 5, KONTUR)
    else:  # laecheln
        s.d.arc([(mx - 16) * k, (my - 10) * k, (mx + 16) * k, (my + 12) * k], 20, 160,
                fill=KONTUR, width=int(5 * k))


def _mische(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _kopf(s: _Stift, pose: str, mund: str, person: str = "er") -> None:
    """Der Kopf. „er“ nach den Fotos des Nutzers (10.11.2026: „Kannst du
    mich darstellen als Maskottchen“, dann „Kurze Haare … Keine Brille“ und
    zuletzt „Dann ohne Bart“): ovales Gesicht, kurze dunkelbraune Haare
    mit etwas Schwung vorn, kein Bart, keine Brille. „sie“: dieselbe
    Gesichtsform, mittelbraunes Haar mit Pferdeschwanz, Ohrstecker."""
    mx, my = 150, 108
    rx, ry = 56, 68
    k = s.k
    # Ohren
    for sx in (-1, 1):
        s.kreis(mx + sx * (rx + 2), my + 8, 11, HAUT)
    # Gesicht: Oval, unten etwas kantiger (Kinn)
    form = []
    for w in range(0, 360, 4):
        r = math.radians(w)
        x, y = math.cos(r), math.sin(r)
        if y > 0:                       # untere Hälfte: breiterer Kiefer
            x *= 1.0 + 0.08 * y
        form.append((mx + rx * x, my + ry * y))
    s.d.polygon([s.p(*q) for q in form], fill=HAUT, outline=KONTUR, width=int(5 * k))
    if person == "sie":
        _haar_sie_vorn(s, mx, my, rx)
    else:
        _haar_er(s, mx, my, rx)
    _gesicht(s, pose, mund, mx, my, person)


def _haar_er(s: _Stift, mx, my, rx) -> None:
    """Kurze Haare: eng am Kopf, vorn ein kleiner Schwung nach rechts."""
    k = s.k
    haar = [(mx - rx - 3, my + 2), (mx - rx - 6, my - 30), (mx - 40, my - 64), (mx - 8, my - 78),
            (mx + 30, my - 76), (mx + 52, my - 56), (mx + rx + 4, my - 26), (mx + rx + 3, my + 2),
            (mx + rx - 6, my - 20), (mx + 34, my - 40), (mx + 6, my - 46), (mx - 20, my - 44),
            (mx - 42, my - 34), (mx - rx + 6, my - 14)]
    s.d.polygon([s.p(*q) for q in haar], fill=HAAR, outline=KONTUR, width=int(5 * k))
    s.linie([(mx - 14, my - 70), (mx + 22, my - 62), (mx + 44, my - 46)], 3.2, (98, 72, 56))


def _haar_sie_hinten(s: _Stift, mx=150, my=108, rx=56) -> None:
    """Hinterkopf und Pferdeschwanz (hinter dem Gesicht)."""
    s.ellipse(mx - rx - 6, my - 80, mx + rx + 6, my + 20, HAAR_SIE)
    zopf = [(mx + 40, my - 58), (mx + 78, my - 52), (mx + 96, my - 20), (mx + 92, my + 30),
            (mx + 78, my + 62), (mx + 74, my + 24), (mx + 66, my - 10), (mx + 44, my - 30)]
    s.d.polygon([s.p(*q) for q in zopf], fill=HAAR_SIE, outline=KONTUR, width=int(5 * s.k))
    s.rechteck(mx + 52, my - 62, mx + 66, my - 42, CORAL, radius=4)


def _haar_sie_vorn(s: _Stift, mx, my, rx) -> None:
    """Haar vorn: zurückgekämmt mit einer seitlichen Strähne."""
    k = s.k
    haar = [(mx - rx - 3, my + 4), (mx - rx - 6, my - 32), (mx - 38, my - 68), (mx - 4, my - 80),
            (mx + 34, my - 74), (mx + rx + 2, my - 40), (mx + rx + 3, my + 4), (mx + rx - 6, my - 24),
            (mx + 30, my - 46), (mx - 6, my - 50), (mx - 34, my - 36), (mx - rx + 4, my - 6)]
    s.d.polygon([s.p(*q) for q in haar], fill=HAAR_SIE, outline=KONTUR, width=int(5 * k))
    s.linie([(mx - 22, my - 72), (mx - 30, my - 40)], 3.2, (150, 104, 70))
    s.linie([(mx + 4, my - 76), (mx + 36, my - 56)], 3.2, (150, 104, 70))


def _gesicht(s: _Stift, pose: str, mund: str, mx, my, person: str) -> None:
    k = s.k
    haar = PERSONEN[person]["haar"]
    # Brauen
    for sx in (-1, 1):
        bx, by = mx + sx * 23, my - 14
        if mund == "streng":
            innen, aussen = by + 4, by - 4
        else:
            innen, aussen = by - 1, by - 1
        s.linie([(bx - sx * 11, innen), (bx, by - 4), (bx + sx * 11, aussen + 1)],
                5 if person == "er" else 3.8, haar)
    # Augen: freundlich, mit Lichtpunkt
    zwinker = pose == "daumen"
    for sx in (-1, 1):
        ax, ay = mx + sx * 23, my + 4
        if zwinker and sx == 1:
            s.d.arc([(ax - 9) * k, (ay - 6) * k, (ax + 9) * k, (ay + 6) * k], 200, 340,
                     fill=KONTUR, width=int(4.5 * k))
            continue
        s.d.ellipse([(ax - 6.5) * k, (ay - 7.5) * k, (ax + 6.5) * k, (ay + 7.5) * k], fill=KONTUR)
        s.d.ellipse([(ax - 0.5) * k, (ay - 5) * k, (ax + 3.5) * k, (ay - 1) * k], fill=WEISS)
        if person == "sie":       # zwei kleine Wimpern außen
            s.linie([(ax + sx * 5, ay - 6), (ax + sx * 10, ay - 10)], 2.6, KONTUR)
            s.linie([(ax + sx * 6.5, ay - 2), (ax + sx * 11.5, ay - 4)], 2.6, KONTUR)
    # Nase
    s.d.arc([(mx - 6) * k, (my + 10) * k, (mx + 8) * k, (my + 24) * k], 20, 130, fill=KONTUR,
            width=int(3.5 * k))
    if person == "sie":           # kleine Ohrstecker
        for sx in (-1, 1):
            s.kreis(mx + sx * 58, my + 18, 3.2, CORAL, kontur=False)
    _mund(s, mund, mx, my + 40)


def _figur_gross(pose: str, person: str = "er") -> Image.Image:
    p = POSEN[pose]
    farben = PERSONEN[person]
    k = SS
    img = Image.new("RGBA", (EIN_B * k, EIN_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = _Stift(d, k)
    schultern = {"links": (116, 196), "rechts": (184, 196)}
    haende = {}
    ellbogen = {}
    for seite in ("links", "rechts"):
        e, h = _arm_punkte(schultern[seite], p[seite], seite)
        ellbogen[seite], haende[seite] = e, h
    zub = p.get("zubehoer", [])
    for z in zub:
        _zubehoer_hinten(s, z, haende)
    sitzt = p.get("sitzen", False)
    if not sitzt:
        # Beine und Schuhe
        for sx in (-1, 1):
            hx = 150 + sx * 20
            s.glied([(hx, 270), (hx + sx * 4, BODEN - 14)], 21, HAUT)
            s.glied([(hx + sx * 2, BODEN - 6), (hx + sx * 22, BODEN - 6)], 18, WEISS)
            s.linie([(hx + sx * 4, BODEN - 10), (hx + sx * 18, BODEN - 10)], 4, CORAL)
        # Laufhose
        s.rechteck(110, 252, 190, 292, farben["hose"], radius=10)
        s.d.line([s.p(150, 262), s.p(150, 292)], fill=KONTUR, width=int(3 * k))
    # Laufshirt mit breiten Schultern, Soft-Blue-Streifen an der Seite
    breit = 0 if person == "er" else 6          # sie: etwas schmalere Schultern
    s.rechteck(104 + breit, 174, 196 - breit, 266, farben["shirt"], radius=26)
    for sx in (-1, 1):
        s.d.line([s.p(150 + sx * (40 - breit), 190), s.p(150 + sx * (40 - breit), 262)],
                 fill=farben["streifen"], width=int(6 * k))
    s.d.arc([s.p(130, 164)[0], s.p(130, 164)[1], s.p(170, 188)[0], s.p(170, 188)[1]], 20, 160,
            fill=farben["streifen"], width=int(5 * k))
    # Startnummer mit Routenzeichen
    s.rechteck(124, 210, 176, 246, WEISS, radius=5)
    route = [(131, 239), (142, 222), (152, 232), (167, 216)]
    s.linie(route, 4, MIDNIGHT)
    s.d.ellipse([s.p(164, 213)[0], s.p(164, 213)[1], s.p(170, 219)[0], s.p(170, 219)[1]], fill=CORAL)
    for seite in ("links", "rechts"):
        sh, e, h = schultern[seite], ellbogen[seite], haende[seite]
        s.glied([sh, e, h], 19, HAUT)
        s.glied([sh, (sh[0] + (e[0] - sh[0]) * 0.34, sh[1] + (e[1] - sh[1]) * 0.34)], 28, farben["shirt"])
        eigene_hand = (seite == "rechts" and any(z in zub for z in ("stopphand", "daumen", "banane"))) \
            or "kalender" in zub
        if not eigene_hand:
            s.kreis(h[0], h[1], 11, HAUT)
    if person == "sie":
        _haar_sie_hinten(s)
    _kopf(s, pose, p.get("mund", "laecheln"), person)
    for z in zub:
        _zubehoer(s, z, haende, img)
    return img


def _sticker(img: Image.Image, rand: int) -> Image.Image:
    a = img.split()[-1]
    gross = a.filter(ImageFilter.MaxFilter(rand * 2 + 1))
    weiss = Image.new("RGBA", img.size, WEISS + (255,))
    weiss.putalpha(gross)
    weiss.alpha_composite(img)
    return weiss


@lru_cache(maxsize=64)
def figur(pose: str, hoehe: int = 400, person: str = "er") -> Image.Image:
    """Die Figur in der Pose `pose`, `hoehe` Pixel hoch, mit weißem
    Sticker-Rand und weichem Schatten; RGBA, freigestellt."""
    if pose not in POSEN:
        raise KeyError(f"unbekannte Pose: {pose} (bekannt: {', '.join(POSEN)})")
    if person not in PERSONEN:
        raise KeyError(f"unbekannte Person: {person} (bekannt: {', '.join(PERSONEN)})")
    gross = _figur_gross(pose, person)
    b = round(EIN_B * hoehe / EIN_H)
    klein = gross.resize((b, hoehe), Image.LANCZOS)
    rand = max(3, hoehe // 70)
    pad = rand * 4
    flaeche = Image.new("RGBA", (b + 2 * pad, hoehe + 2 * pad), (0, 0, 0, 0))
    flaeche.alpha_composite(klein, (pad, pad))
    mit_rand = _sticker(flaeche, rand)
    schatten = Image.new("RGBA", mit_rand.size, (0, 20, 40, 0))
    alpha = mit_rand.split()[-1].point(lambda v: int(v * 0.28))
    schatten.putalpha(alpha.filter(ImageFilter.GaussianBlur(rand * 2)))
    erg = Image.new("RGBA", mit_rand.size, (0, 0, 0, 0))
    erg.alpha_composite(schatten.transform(schatten.size, Image.AFFINE, (1, 0, -rand, 0, 1, -rand * 2)))
    erg.alpha_composite(mit_rand)
    return erg


if __name__ == "__main__":
    import sys
    ziel = sys.argv[1] if len(sys.argv) > 1 else "maskottchen.png"
    bilder = [figur(p, 360, person) for person in PERSONEN for p in POSEN]
    w = sum(b.width for b in bilder) + 20 * (len(bilder) + 1)
    h = max(b.height for b in bilder) + 40
    bogen = Image.new("RGB", (w, h), SOFT_BLUE)
    x = 20
    for b in bilder:
        bogen.paste(b, (x, 20), b)
        x += b.width + 20
    bogen.save(ziel)
    print(ziel)
