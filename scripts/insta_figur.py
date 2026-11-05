#!/usr/bin/env python3
"""Die kleine Figur der Reels: ein Läufer (bzw. bei Radformaten eine
Radlerin), der auf der Fortschrittslinie unten im Bild bis zur
Zielflagge läuft und dort jubelt.

Vom Nutzer am 04.11.2026 gewünscht: „einen blauen Hintergrund … und
vielleicht eine kleine Animation von einem Läufer irgendwo, dass wir bei
den Videos bisschen mit Animation arbeiten wie diese Konstruktion
Animation bei der Club Seite. Das sieht dann süß aus und bereitet den
Leuten Freude.“ – Stil deshalb wie der Bauarbeiter in clubs.html: flache
Flächen, Navy-Kontur, großer runder Kopf, rote Bäckchen; dazu ein weißer
Sticker-Rand, damit die Figur auf dem Navy-Grund steht.

Alles mit Pillow, viermal so groß gezeichnet und verkleinert (glatte
Kanten). Eine Haltung je Phase des Laufschritts wird einmal gerechnet und
gemerkt (`PHASEN` Stück), die Figur kostet je Bild also nur ein Einfügen.
Kein Bild von außen, keine Schrift.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

NAVY = (11, 27, 51)
WEISS = (255, 255, 255)
SIGNAL = (232, 89, 12)
SONNE = (249, 115, 22)
HAUT = (246, 207, 168)
HAUT_HINTEN = (222, 178, 140)
HOSE = (44, 90, 146)
HOSE_HINTEN = (33, 70, 116)
HAAR = (60, 40, 33)
BACKE = (242, 139, 130)
METALL = (154, 166, 184)

PHASEN = 24                 # Haltungen je Laufschritt-Zyklus
SS = 4                      # Supersampling
HOEHE = 150                 # Höhe der Figur im Video (px, ohne Rand)
RAND = 5                    # weißer Sticker-Rand (px)
EINHEIT_H = 270             # Zeichenfläche in Einheiten (Füße bei y≈258)
EINHEIT_B = 240
BODEN = 258


def _kontur(k: float) -> float:
    return 5.0 * k


class _Stift:
    """Zeichnet in Einheiten; k = Pixel je Einheit (mit Supersampling)."""

    def __init__(self, d: ImageDraw.ImageDraw, k: float):
        self.d, self.k = d, k

    def p(self, x: float, y: float) -> tuple[float, float]:
        return x * self.k, y * self.k

    def kreis(self, x: float, y: float, r: float, fill, kontur: bool = True) -> None:
        o = _kontur(self.k) if kontur else 0
        x, y, r = x * self.k, y * self.k, r * self.k
        if kontur:
            self.d.ellipse([x - r - o, y - r - o, x + r + o, y + r + o], fill=NAVY)
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def glied(self, punkte: list[tuple[float, float]], breite: float, fill, kontur: bool = True) -> None:
        """Ein dicker Strich mit runden Enden und Navy-Kontur (Arm, Bein,
        Rumpf)."""
        pts = [self.p(*q) for q in punkte]
        b = breite * self.k
        o = _kontur(self.k)
        for farbe, extra in (((NAVY, o) if kontur else (None, 0)), (fill, 0)):
            if farbe is None:
                continue
            w = b + 2 * extra
            if len(pts) > 1:
                self.d.line(pts, fill=farbe, width=int(round(w)), joint="curve")
            for x, y in pts:
                self.d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=farbe)


def _bein(s: _Stift, hufte: tuple[float, float], p: float, hinten: bool) -> None:
    """Ein Bein in der Phase p (Bogenmaß): Oberschenkel schwingt vor und
    zurück, das Knie beugt sich in der Schwungphase stark (Ferse zum Po),
    beim Aufsetzen ist es fast gestreckt."""
    th = 0.72 * math.sin(p)
    beuge = 0.18 + 1.45 * max(0.0, math.cos(p)) ** 1.4
    hx, hy = hufte
    kx, ky = hx + 42 * math.sin(th), hy + 42 * math.cos(th)
    a = th - beuge
    ax, ay = kx + 44 * math.sin(a), ky + 44 * math.cos(a)
    haut = HAUT_HINTEN if hinten else HAUT
    s.glied([(hx, hy), (kx, ky), (ax, ay)], 15, haut)
    # Schuh: zeigt nach vorn, senkrecht zum Unterschenkel
    fx, fy = math.cos(a), -math.sin(a)
    zx, zy = ax + 20 * fx, ay + 20 * fy
    s.glied([(ax - 3 * fx, ay - 3 * fy), (zx, zy)], 17, SONNE if not hinten else SIGNAL)
    # Sohle: ein weißer Strich auf der Unterseite des Schuhs
    nx, ny = math.sin(a), math.cos(a)
    s.glied([(ax - 1 * fx + 6 * nx, ay - 1 * fy + 6 * ny), (zx + 6 * nx, zy + 6 * ny)], 4.5, WEISS,
            kontur=False)
    # Hosenbein über dem Oberschenkel
    hose = HOSE_HINTEN if hinten else HOSE
    s.glied([(hx, hy), (hx + 16 * math.sin(th), hy + 16 * math.cos(th))], 25, hose)


def _arm(s: _Stift, schulter: tuple[float, float], q: float, hinten: bool,
         oben: float | None = None, winken: float = 0.0) -> None:
    """Ein Arm: schwingt gegen das Bein derselben Seite, angewinkelt.
    Mit `oben` (Winkel von unten, im Bogenmaß) hoch gestreckt – Jubel."""
    sx, sy = schulter
    if oben is None:
        ua = 0.78 * math.sin(q)
        fa = ua + 1.75
    else:
        ua = oben
        fa = oben + 0.35 * math.sin(winken)
    ex, ey = sx + 30 * math.sin(ua), sy + 30 * math.cos(ua)
    hx, hy = ex + 27 * math.sin(fa), ey + 27 * math.cos(fa)
    haut = HAUT_HINTEN if hinten else HAUT
    s.glied([(sx, sy), (ex, ey), (hx, hy)], 13, haut)
    s.kreis(hx, hy, 8.5, haut)
    # kurzer Ärmel
    s.glied([(sx, sy), (sx + 9 * math.sin(ua), sy + 9 * math.cos(ua))], 22,
            SIGNAL if not hinten else (200, 74, 8))


def _kopf(s: _Stift, mx: float, my: float, p: float, img: Image.Image) -> None:
    """Großer runder Kopf, Dreiviertelansicht nach rechts: Haare, Stirnband
    mit flatternden Enden, zwei Augen mit Lichtpunkt, Bäckchen, Lächeln."""
    k = s.k
    r = 40
    # Bandenden flattern nach hinten (links), zwei Wellen je Schritt
    for i, (laenge, dy) in enumerate(((34, -6), (28, 6))):
        w = math.sin(2 * p + i * 1.3)
        x0, y0 = mx - 30, my - 16
        x1, y1 = x0 - laenge, y0 + dy + 9 * w
        x2, y2 = x1 - 4, y1 + 8 - 3 * w
        s.glied([(x0, y0), (x1, y1), (x2, y2)], 9, SONNE)
    s.kreis(mx, my, r, HAUT)
    # Haare und Stirnband auf eigener Ebene, auf den Kopf beschnitten
    lage = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lage)
    cx, cy, rr = mx * k, my * k, r * k
    ld.ellipse([cx - rr * 1.25, cy - rr * 1.45, cx + rr * 0.95, cy - rr * 0.18], fill=HAAR)
    ld.ellipse([cx - rr * 1.3, cy - rr * 1.1, cx - rr * 0.35, cy + rr * 0.55], fill=HAAR)
    band = [(cx - rr * 1.2, cy - rr * 0.62), (cx + rr * 1.2, cy - rr * 0.48),
            (cx + rr * 1.2, cy - rr * 0.22), (cx - rr * 1.2, cy - rr * 0.36)]
    ld.polygon(band, fill=SONNE)
    ld.line([(cx - rr * 1.2, cy - rr * 0.49), (cx + rr * 1.2, cy - rr * 0.35)], fill=WEISS,
            width=max(1, int(3.2 * k)))
    maske = Image.new("L", img.size, 0)
    ImageDraw.Draw(maske).ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=255)
    img.alpha_composite(Image.composite(lage, Image.new("RGBA", img.size, (0, 0, 0, 0)), maske))
    o = _kontur(k)
    s.d.ellipse([cx - rr - o / 2, cy - rr - o / 2, cx + rr + o / 2, cy + rr + o / 2], outline=NAVY,
                width=int(round(o)))
    # Gesicht
    for ax in (mx + 4, mx + 25):
        s.d.ellipse([(ax - 4.6) * k, (my + 3) * k, (ax + 4.6) * k, (my + 16) * k], fill=NAVY)
        s.d.ellipse([(ax - 0.6) * k, (my + 4.5) * k, (ax + 2.8) * k, (my + 7.9) * k], fill=WEISS)
    for bx, by in ((mx - 6, my + 21), (mx + 33, my + 20)):
        s.d.ellipse([(bx - 7) * k, (by - 4.5) * k, (bx + 7) * k, (by + 4.5) * k], fill=BACKE + (170,))
    s.d.arc([(mx + 5) * k, (my + 13) * k, (mx + 25) * k, (my + 29) * k], 20, 160, fill=NAVY,
            width=int(round(3.6 * k)))


def _rumpf(s: _Stift, schulter, hufte) -> None:
    s.glied([schulter, hufte], 44, SIGNAL)
    # Startnummer mit dem Zeichen der Marke (Route + Punkt), keine Schrift
    mx = (schulter[0] + hufte[0]) / 2 + 6
    my = (schulter[1] + hufte[1]) / 2 + 2
    k = s.k
    s.d.rounded_rectangle([(mx - 14) * k, (my - 11) * k, (mx + 14) * k, (my + 11) * k],
                          radius=3 * k, fill=WEISS, outline=NAVY, width=int(round(2.5 * k)))
    s.d.line([((mx - 9) * k, (my + 5) * k), ((mx - 3) * k, (my - 3) * k), ((mx + 2) * k, (my + 2) * k),
              ((mx + 7) * k, (my - 5) * k)], fill=NAVY, width=int(round(2.6 * k)), joint="curve")
    s.d.ellipse([(mx + 5) * k, (my - 8) * k, (mx + 10.5) * k, (my - 2.5) * k], fill=SIGNAL)
    # Hose: kurz, unter dem Shirt
    hx, hy = hufte
    k = s.k
    o = _kontur(k)
    s.d.rounded_rectangle([(hx - 24) * k - o, (hy - 13) * k - o, (hx + 24) * k + o, (hy + 13) * k + o],
                          radius=12 * k + o, fill=NAVY)
    s.d.rounded_rectangle([(hx - 24) * k, (hy - 13) * k, (hx + 24) * k, (hy + 13) * k], radius=12 * k,
                          fill=HOSE)


def _sticker(img: Image.Image) -> Image.Image:
    """Verkleinern, dann weißer Rand um die ganze Figur (Sticker-Look) und
    ein weicher Schatten darunter."""
    klein = img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
    w, h = klein.width + 2 * (RAND + 4), klein.height + 2 * (RAND + 4)
    voll = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    voll.alpha_composite(klein, (RAND + 4, RAND + 4))
    a = voll.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    rand = a.filter(ImageFilter.MaxFilter(2 * RAND + 1)).filter(ImageFilter.GaussianBlur(0.8))
    schatten = rand.filter(ImageFilter.GaussianBlur(5)).point(lambda v: v * 45 // 100)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sch = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    sch.putalpha(schatten)
    out.alpha_composite(sch, (0, 3))
    weiss = Image.new("RGBA", (w, h), WEISS + (255,))
    weiss.putalpha(rand)
    out.alpha_composite(weiss)
    out.alpha_composite(voll)
    return out


def _flaeche() -> tuple[Image.Image, _Stift]:
    k = HOEHE / EINHEIT_H * SS
    img = Image.new("RGBA", (int(EINHEIT_B * k), int(EINHEIT_H * k)), (0, 0, 0, 0))
    return img, _Stift(ImageDraw.Draw(img, "RGBA"), k)


@lru_cache(maxsize=None)
def laeufer(phase_i: int, jubel_i: int | None = None) -> Image.Image:
    """Die Figur als Sticker (RGBA). `phase_i` 0…PHASEN-1: Haltung im
    Laufschritt. Mit `jubel_i` (0…PHASEN-1) die Jubel-Haltung: beide Arme
    hoch, kleiner Hüpfer."""
    img, s = _flaeche()
    if jubel_i is None:
        p = 2 * math.pi * phase_i / PHASEN
        bob = 5 * math.cos(2 * p)
        schulter = (124, 116 + bob)
        hufte = (110, 166 + bob)
        _arm(s, schulter, p, hinten=True)
        _bein(s, hufte, p + math.pi, hinten=True)
        _rumpf(s, schulter, hufte)
        _bein(s, hufte, p, hinten=False)
        _kopf(s, 132, 70 + bob, p, img)
        _arm(s, schulter, p + math.pi, hinten=False)
    else:
        # Jubel von vorn: Arme in einem V nach oben, kleiner Hüpfer
        w = 2 * math.pi * jubel_i / PHASEN
        sprung = -12 * abs(math.sin(w))
        hufte = (120, 166 + sprung)
        schulter = (120, 116 + sprung)
        for dx, seite in ((-10, -1), (10, 1)):
            hx, hy = hufte[0] + dx, hufte[1]
            ax, ay = hx + dx * 0.35, hy + 85
            s.glied([(hx, hy), (ax, ay)], 15, HAUT)
            s.glied([(ax - 9 * (seite < 0), ay), (ax + 9 * (seite > 0) + 4, ay)], 17, SONNE)
            s.glied([(ax - 8 * (seite < 0), ay + 6), (ax + 9 * (seite > 0) + 3, ay + 6)], 4.5, WEISS,
                    kontur=False)
            s.glied([(hx, hy), (hx + dx * 0.15, hy + 16)], 25, HOSE)
        _rumpf(s, schulter, hufte)
        _kopf(s, 122, 68 + sprung, w, img)
        for sx, seite in ((101, -1), (139, 1)):
            ua = math.pi - seite * 0.8
            fa = math.pi - seite * (0.25 + 0.2 * math.sin(w + (seite > 0)))
            sy = 120 + sprung
            ex, ey = sx + 30 * math.sin(ua), sy + 30 * math.cos(ua)
            hx_, hy_ = ex + 27 * math.sin(fa), ey + 27 * math.cos(fa)
            s.glied([(sx, sy), (ex, ey), (hx_, hy_)], 13, HAUT)
            s.kreis(hx_, hy_, 8.5, HAUT)
            s.glied([(sx, sy), (sx + 9 * math.sin(ua), sy + 9 * math.cos(ua))], 22, SIGNAL)
    return _sticker(img)


# ---------------------------------------------------------------- Rad

def _rad(s: _Stift, mx: float, my: float, r: float, drehung: float) -> None:
    k = s.k
    o = _kontur(k)
    s.d.ellipse([(mx - r) * k - o, (my - r) * k - o, (mx + r) * k + o, (my + r) * k + o], outline=NAVY,
                width=int(round(7 * k + o)))
    for i in range(5):
        a = drehung + i * 2 * math.pi / 5
        s.d.line([(mx * k, my * k), ((mx + (r - 6) * math.cos(a)) * k, (my + (r - 6) * math.sin(a)) * k)],
                 fill=METALL, width=int(round(2.2 * k)))
    s.d.ellipse([(mx - 5) * k, (my - 5) * k, (mx + 5) * k, (my + 5) * k], fill=NAVY)


@lru_cache(maxsize=None)
def radler(phase_i: int, jubel_i: int | None = None) -> Image.Image:
    """Dieselbe Figur auf dem Rennrad: Räder drehen sich, Beine treten.
    Beim Jubel ein Arm hoch."""
    img, s = _flaeche()
    p = 2 * math.pi * phase_i / PHASEN
    k = s.k
    hinten_x, vorn_x, achse_y, r = 52, 190, 222, 34
    tritt_x, tritt_y = 118, 214
    sattel = (106, 152)
    lenker = (172, 150)
    # Rahmen
    for a, b in ((hinten_x, achse_y), (tritt_x, tritt_y)), ((tritt_x, tritt_y), sattel), \
                (sattel, (hinten_x, achse_y)), (sattel, (162, 160)), ((162, 160), (tritt_x, tritt_y)), \
                ((162, 160), (vorn_x, achse_y)):
        s.glied([a, b], 7, SIGNAL)
    s.glied([(162, 160), lenker, (180, 156), (182, 168)], 6, NAVY, kontur=False)
    s.glied([(sattel[0] - 10, sattel[1] - 4), (sattel[0] + 10, sattel[1] - 4)], 7, NAVY, kontur=False)
    _rad(s, hinten_x, achse_y, r, -p * 2)
    _rad(s, vorn_x, achse_y, r, -p * 2)
    # Rumpf vorgebeugt, Kopf vorn
    schulter = (150, 108)
    hufte = (106, 140)
    # Beine auf den Pedalen (Kurbel 18 Einheiten)
    for q, hinten in ((p + math.pi, True), (p, False)):
        px, py = tritt_x + 18 * math.cos(q), tritt_y + 18 * math.sin(q)
        # Knie über Gelenk-Dreieck (Oberschenkel 44, Unterschenkel 46)
        dx, dy = px - hufte[0], py - hufte[1]
        dist = min(89.0, math.hypot(dx, dy))
        a = math.atan2(dy, dx)
        cos_b = (44 ** 2 + dist ** 2 - 46 ** 2) / (2 * 44 * dist)
        b = math.acos(max(-1.0, min(1.0, cos_b)))
        kx, ky = hufte[0] + 44 * math.cos(a - b), hufte[1] + 44 * math.sin(a - b)
        haut = HAUT_HINTEN if hinten else HAUT
        if hinten:
            s.glied([hufte, (kx, ky), (px, py)], 14, haut)
            s.glied([(px - 4, py + 3), (px + 14, py + 3)], 13, SIGNAL)
        else:
            front = ((kx, ky), (px, py))
    _rumpf(s, schulter, hufte)
    kx, ky = front[0]
    px, py = front[1]
    s.glied([hufte, (kx, ky), (px, py)], 14, HAUT)
    s.glied([(px - 4, py + 3), (px + 14, py + 3)], 13, SONNE)
    s.glied([hufte, (hufte[0] + 0.36 * (kx - hufte[0]), hufte[1] + 0.36 * (ky - hufte[1]))], 24, HOSE)
    # Helm statt Stirnband
    _kopf(s, 168, 76, p, img)
    hk = s.k
    s.d.chord([(168 - 43) * hk, (76 - 46) * hk, (168 + 43) * hk, (76 + 30) * hk], 180, 360, fill=WEISS,
              outline=NAVY, width=int(round(_kontur(hk))))
    s.d.line([((168 - 20) * hk, (76 - 38) * hk), ((168 + 18) * hk, (76 - 38) * hk)], fill=SIGNAL,
             width=int(round(5 * hk)))
    if jubel_i is not None:
        w = 2 * math.pi * jubel_i / PHASEN
        _arm(s, schulter, 0, hinten=False, oben=math.pi + 0.35, winken=w)
    else:
        s.glied([schulter, (164, 132), lenker], 12, HAUT)
        s.kreis(lenker[0], lenker[1], 7.5, HAUT)
    return _sticker(img)


# ---------------------------------------------------------------- Szene

LINIE_Y = 1592               # Fortschrittslinie (insta_video.rendere)
LINKS, RECHTS = 80, 960
JUBEL_S = 1.3                # so lange jubelt die Figur am Ziel


def figur_fuer(sport: str | None) -> str:
    return "radler" if sport == "Fahrrad" else "laeufer"


def _flagge(d: ImageDraw.ImageDraw, x: int, boden: int, t: float) -> None:
    """Zielflagge: Stange und karierte Fahne, die leicht weht."""
    d.rounded_rectangle([x - 3, boden - 96, x + 3, boden + 4], radius=3, fill=WEISS)
    feld, spalten, zeilen = 11, 5, 3
    for i in range(spalten):
        for j in range(zeilen):
            w0 = math.sin(t * 6 + i * 0.9) * 3.5
            w1 = math.sin(t * 6 + (i + 1) * 0.9) * 3.5
            x0, x1 = x + 3 + i * feld, x + 3 + (i + 1) * feld
            y0, y1 = boden - 94 + j * feld, boden - 94 + (j + 1) * feld
            farbe = WEISS if (i + j) % 2 == 0 else NAVY
            d.polygon([(x0, y0 + w0), (x1, y0 + w1), (x1, y1 + w1), (x0, y1 + w0)], fill=farbe)
    d.rectangle([x + 3, boden - 94, x + 3 + spalten * feld, boden - 94 + zeilen * feld], outline=WEISS)


def _konfetti(bild: Image.Image, x: int, y: int, dt: float, seed: int, farben) -> None:
    rng = random.Random(seed)
    d = ImageDraw.Draw(bild, "RGBA")
    for _ in range(46):
        vx = rng.uniform(-260, 260)
        vy = rng.uniform(-620, -260)
        g = 900
        px = x + vx * dt
        py = y + vy * dt + 0.5 * g * dt * dt
        if py > LINIE_Y + 40:
            continue
        a = rng.uniform(0, math.pi) + dt * rng.uniform(4, 10)
        lw, lh = rng.uniform(5, 9), rng.uniform(10, 16)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(px + ca * dx - sa * dy, py + sa * dx + ca * dy)
               for dx, dy in ((-lw / 2, -lh / 2), (lw / 2, -lh / 2), (lw / 2, lh / 2), (-lw / 2, lh / 2))]
        alpha = int(255 * max(0.0, min(1.0, 1.6 - dt)))
        d.polygon(pts, fill=rng.choice(farben) + (alpha,))


def zeichne(bild: Image.Image, t: float, gesamt: float, sport: str | None, akzent, schritt_s: float = 0.5,
            seed: int = 0) -> None:
    """Fortschrittslinie, Zielflagge und Figur in das Bild (RGBA). Die
    Figur ist der Fortschritt: Die Linie füllt sich bis zu ihr, am Ziel
    jubelt sie die letzten `JUBEL_S` Sekunden."""
    d = ImageDraw.Draw(bild, "RGBA")
    ziel_x = RECHTS - 66
    lauf_ende = max(0.5, gesamt - JUBEL_S)
    p = min(1.0, t / lauf_ende)
    p = p * p * (3 - 2 * p) * 0.25 + p * 0.75          # sanftes Anlaufen und Ankommen
    start_x = LINKS + 40
    x = start_x + (ziel_x - start_x) * p
    # Linie: Strecke weiß und dünn, gelaufen in der Akzentfarbe
    d.rounded_rectangle([LINKS, LINIE_Y - 2, RECHTS, LINIE_Y + 2], radius=2, fill=(255, 255, 255, 60))
    d.rounded_rectangle([LINKS, LINIE_Y - 3, int(x), LINIE_Y + 3], radius=3, fill=akzent)
    _flagge(d, RECHTS, LINIE_Y, t)
    am_ziel = t >= lauf_ende
    art = figur_fuer(sport)
    if am_ziel:
        ji = int((t - lauf_ende) / 0.5 * PHASEN) % PHASEN
        fig = (radler if art == "radler" else laeufer)(0, ji)
        _konfetti(bild, RECHTS - 10, LINIE_Y - 110, t - lauf_ende, seed,
                  [SIGNAL, SONNE, WEISS, (61, 181, 90), (77, 157, 230), (151, 117, 250)])
    else:
        pi = int(t / schritt_s * PHASEN) % PHASEN
        fig = (radler if art == "radler" else laeufer)(pi)
        # Tempo-Striche hinter der Figur
        for i, (dy, laenge) in enumerate(((-96, 34), (-66, 46), (-36, 30))):
            w = 0.5 + 0.5 * math.sin(t * 9 + i * 1.7)
            x1 = x - 52 - 6 * i
            x0 = x1 - laenge * (0.6 + 0.4 * w)
            if x0 > LINKS - 20:
                d.rounded_rectangle([x0, LINIE_Y + dy - 2, x1, LINIE_Y + dy + 2], radius=2,
                                    fill=(255, 255, 255, int(70 + 70 * w)))
    # Füße auf der Linie: die Figur hat unten RAND + 4 px Luft
    fy = LINIE_Y - fig.height + RAND + 4 + int((EINHEIT_H - BODEN) * HOEHE / EINHEIT_H)
    bild.alpha_composite(fig, (int(x - fig.width / 2), int(fy)))
