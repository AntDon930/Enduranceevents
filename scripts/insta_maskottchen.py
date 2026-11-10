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
HAUT = (246, 207, 168)
HAUT_SCHATTEN = (226, 184, 146)
HAAR = (74, 48, 36)
BACKE = (244, 140, 130)
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
    "nudeln": {"links": (-25, -95), "rechts": (-15, -150), "mund": "kauen",
               "zubehoer": ["schuessel", "gabel"]},
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
    """Zubehör, das HINTER der Figur liegt (Waage unter den Füßen)."""
    if name == "waage":
        s.rechteck(84, BODEN - 4, 216, BODEN + 14, WEISS, radius=8)
        s.rechteck(130, BODEN + 1, 170, BODEN + 10, CORAL, radius=3, kontur=False)


def _zubehoer(s: _Stift, name: str, haende: dict, img: Image.Image) -> None:
    hl, hr = haende["links"], haende["rechts"]
    k = s.k
    if name == "schuessel":
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
        s.d.chord([(mx - 18) * k, (my - 14) * k, (mx + 18) * k, (my + 18) * k], 0, 180, fill=KONTUR)
        s.d.chord([(mx - 9) * k, (my + 6) * k, (mx + 9) * k, (my + 16) * k], 180, 360, fill=CORAL)
    elif art == "o":
        s.d.ellipse([(mx - 8) * k, (my - 4) * k, (mx + 8) * k, (my + 14) * k], fill=KONTUR)
    elif art == "kauen":
        s.d.ellipse([(mx - 14) * k, (my - 2) * k, (mx + 14) * k, (my + 12) * k], fill=KONTUR)
        s.d.ellipse([(mx - 8) * k, (my + 1) * k, (mx + 8) * k, (my + 9) * k], fill=SOSSE)
    elif art == "streng":
        s.linie([(mx - 14, my + 6), (mx + 14, my + 6)], 5, KONTUR)
    else:  # laecheln
        s.d.arc([(mx - 16) * k, (my - 10) * k, (mx + 16) * k, (my + 12) * k], 20, 160,
                fill=KONTUR, width=int(5 * k))


def _kopf(s: _Stift, pose: str, mund: str) -> None:
    mx, my, r = 150, 104, 66
    k = s.k
    # Haare hinten, Kopf, Stirnband, Haarschopf
    s.kreis(mx, my, r, HAUT)
    s.d.chord([(mx - r) * k, (my - r) * k, (mx + r) * k, (my + r) * k], 206, 334, fill=HAAR)
    for dx, dy in ((-30, -66), (-6, -74), (18, -70), (38, -60)):
        s.d.ellipse([(mx + dx - 14) * k, (my + dy - 10) * k, (mx + dx + 14) * k, (my + dy + 14) * k], fill=HAAR)
    # Stirnband (Coral) mit Knoten und zwei Bandenden rechts
    s.d.rectangle([(mx - r + 2) * k, (my - 40) * k, (mx + r - 2) * k, (my - 24) * k], fill=CORAL)
    s.glied([(mx + r - 4, my - 32), (mx + r + 22, my - 46)], 9, CORAL)
    s.glied([(mx + r - 4, my - 30), (mx + r + 26, my - 22)], 9, CORAL)
    # Kontur des Gesichts erneut (über Haar/Band)
    s.d.arc([(mx - r) * k, (my - r) * k, (mx + r) * k, (my + r) * k], 0, 360, fill=KONTUR, width=int(5 * k))
    # Ohren
    for sx in (-1, 1):
        s.kreis(mx + sx * (r + 2), my + 8, 11, HAUT)
    s.kreis(mx, my, r - 1, HAUT, kontur=False)
    s.d.chord([(mx - r + 1) * k, (my - r + 1) * k, (mx + r - 1) * k, (my + r - 1) * k], 206, 334, fill=HAAR)
    s.d.rectangle([(mx - r + 4) * k, (my - 40) * k, (mx + r - 4) * k, (my - 24) * k], fill=CORAL)
    # Augen
    zwinker = pose == "daumen"
    for sx in (-1, 1):
        ax, ay = mx + sx * 24, my + 4
        if zwinker and sx == 1:
            s.d.arc([(ax - 10) * k, (ay - 8) * k, (ax + 10) * k, (ay + 6) * k], 200, 340,
                     fill=KONTUR, width=int(5 * k))
            continue
        s.d.ellipse([(ax - 8) * k, (ay - 10) * k, (ax + 8) * k, (ay + 10) * k], fill=KONTUR)
        s.d.ellipse([(ax - 1) * k, (ay - 7) * k, (ax + 5) * k, (ay - 1) * k], fill=WEISS)
    # Brauen (streng = zur Mitte hin schräg nach unten)
    for sx in (-1, 1):
        bx, by = mx + sx * 24, my - 15
        if mund == "streng":
            innen, aussen = by + 3, by - 5
        else:
            innen = aussen = by - 2
        s.linie([(bx - sx * 9, innen), (bx + sx * 9, aussen)], 4, HAAR)
    # Bäckchen
    for sx in (-1, 1):
        bx, by = mx + sx * 40, my + 26
        s.d.ellipse([(bx - 11) * k, (by - 7) * k, (bx + 11) * k, (by + 7) * k], fill=BACKE)
    _mund(s, mund, mx, my + 34)


def _figur_gross(pose: str) -> Image.Image:
    p = POSEN[pose]
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
    # Beine und Schuhe
    for sx in (-1, 1):
        hx = 150 + sx * 20
        s.glied([(hx, 270), (hx + sx * 4, BODEN - 14)], 20, HAUT)
        s.glied([(hx + sx * 2, BODEN - 6), (hx + sx * 22, BODEN - 6)], 18, WEISS)
        s.linie([(hx + sx * 4, BODEN - 10), (hx + sx * 18, BODEN - 10)], 4, CORAL)
    # Hose
    s.rechteck(112, 252, 188, 290, MIDNIGHT, radius=10)
    s.d.line([s.p(150, 262), s.p(150, 290)], fill=WEISS, width=int(3 * k))
    # Arme hinter dem Rumpf? Nein: Rumpf zuerst, dann Arme davor
    s.rechteck(108, 176, 192, 266, CORAL, radius=30)
    # Startnummer mit Routenzeichen
    s.rechteck(126, 212, 174, 246, WEISS, radius=5)
    route = [(132, 240), (142, 224), (152, 233), (166, 218)]
    s.linie(route, 4, MIDNIGHT)
    s.d.ellipse([s.p(163, 215)[0], s.p(163, 215)[1], s.p(169, 221)[0], s.p(169, 221)[1]], fill=CORAL)
    for seite in ("links", "rechts"):
        sh, e, h = schultern[seite], ellbogen[seite], haende[seite]
        s.glied([sh, e, h], 17, HAUT)
        s.glied([sh, (sh[0] + (e[0] - sh[0]) * 0.32, sh[1] + (e[1] - sh[1]) * 0.32)], 26, CORAL)
        eigene_hand = (seite == "rechts" and any(z in zub for z in ("stopphand", "daumen", "banane"))) \
            or "kalender" in zub
        if not eigene_hand:
            s.kreis(h[0], h[1], 10, HAUT)
    _kopf(s, pose, p.get("mund", "laecheln"))
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
def figur(pose: str, hoehe: int = 400) -> Image.Image:
    """Die Figur in der Pose `pose`, `hoehe` Pixel hoch, mit weißem
    Sticker-Rand und weichem Schatten; RGBA, freigestellt."""
    if pose not in POSEN:
        raise KeyError(f"unbekannte Pose: {pose} (bekannt: {', '.join(POSEN)})")
    gross = _figur_gross(pose)
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
    bilder = [figur(p, 360) for p in POSEN]
    w = sum(b.width for b in bilder) + 20 * (len(bilder) + 1)
    h = max(b.height for b in bilder) + 40
    bogen = Image.new("RGB", (w, h), SOFT_BLUE)
    x = 20
    for b in bilder:
        bogen.paste(b, (x, 20), b)
        x += b.width + 20
    bogen.save(ziel)
    print(ziel)
