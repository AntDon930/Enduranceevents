#!/usr/bin/env python3
"""
scripts/insta_video.py
======================

Baut aus einem geplanten Beitrag (scripts/insta_inhalte.py) ein Reel:
1080 × 1920, 30 Bilder/s, H.264 + AAC, `faststart` - das Format, das
Instagram für Reels verlangt. Dazu ein Titelbild (cover.jpg).

Der Aufbau eines Videos:

  Hintergrund   ein lizenzfreies Video (Pexels, wenn PEXELS_API_KEY
                gesetzt ist), sonst ein langsamer Zoom über die Fotos der
                Startseite (bilder/, Wikimedia Commons, Lizenz und
                Urheber stehen in der Caption) - oder beim Format "clip"
                der Ausschnitt aus einem Clip aus clips.json.
  Abdunkelung   Navy-Verlauf oben und unten, damit Text lesbar bleibt.
  Folien        die Texttafeln aus dem Plan, nacheinander eingeblendet
                (Fade + kleiner Hub von unten), gezeichnet mit Pillow in
                Barlow / Barlow Condensed (marketing/instagram/fonts, OFL).
  Marke         oben das Zeichen der Seite und „AUSDAUERMASCHINE",
                unten ein Fortschrittsbalken in Signal-Orange.
  Ton           ein Stück aus marketing/instagram/musik/ (nur mit
                eingetragener Lizenz, siehe musik.json), sonst ein eigener
                Beat (insta_musik.py, selbst erzeugt, keine Lizenzfrage);
                beim Clip dessen eigener Ton. Die Folien wechseln im Takt.

Seit dem 16.10.2026 („Die Leute wollen keine langweiligen
Zusammenfassungen sehen"): Die ERSTE Folie steht ab dem ersten Bild
(kein Einblenden - die erste Sekunde entscheidet, ob jemand weiterwischt),
Rennen kommen einzeln und groß (Folie „event"), und bei jedem Schnitt
zoomt der Hintergrund kurz an („Punch").

Die Ränder halten Abstand zu dem, was die Instagram-App über ein Reel
legt (oben Kopfzeile, unten Caption und Knöpfe, rechts die Leiste mit
Herz/Kommentar/Teilen): Text nur in x 80…960, y 230…1500.

CLIPS - die Regel: Ein Clip wird nur verarbeitet, wenn in clips.json
`lizenz` UND `urheber` stehen und die Lizenz in ERLAUBTE_LIZENZEN fällt
(CC0, CC BY, CC BY-SA, Pexels, Pixabay, eigenes Material, schriftliche
Genehmigung). Fernsehbilder und Veranstaltervideos ohne Genehmigung
gehören nicht hinein - siehe den Kopf von insta_inhalte.py.
Der beste Ausschnitt wird automatisch gesucht (`highlight()`): je Sekunde
Lautheit des Tons (EBU R128) plus Schnitte im Bild; das lauteste,
bewegteste Fenster gewinnt. `start` in clips.json überstimmt das.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

WURZEL = Path(__file__).resolve().parent.parent
MARKETING = WURZEL / "marketing" / "instagram"
FONTS = MARKETING / "fonts"
MUSIK = MARKETING / "musik"
HINTERGRUENDE = MARKETING / "hintergruende"      # lizenzierte Fotos, Quellen in hintergruende.json
CACHE = MARKETING / ".cache"

B, H = 1080, 1920
FPS = 30
RAND_X = 80
TEXT_BREITE = 880           # 80 … 960, rechts bleibt Platz für die App-Leiste
OBEN = 230
UNTEN = 1500

NAVY = (11, 27, 51)
TIEFE = (22, 59, 107)
SIGNAL = (232, 89, 12)
SONNE = (249, 115, 22)
KREIDE = (244, 242, 237)
WEISS = (255, 255, 255)
GRAU = (190, 198, 212)
SPORTFARBE = {"Laufen": (232, 89, 12), "Fahrrad": (61, 181, 90),
              "Schwimmen": (74, 155, 230), "Triathlon": (154, 123, 240)}

# Wie lange eine Folie steht (Sekunden) - je nach Textmenge. Mit Beat
# wird auf ganze Schläge gerundet (zeitplan()).
DAUER = {"titel": 3.6, "liste": 6.5, "moment": 3.4, "moment_text": 5.0,
         "cta": 2.6, "clip_titel": 5.0, "hook": 2.6, "event": 2.1, "satz": 2.4,
         "logo": 1.0, "top": 2.4}
DAUER_TOP_UEBERSICHT = 3.6
DAUER_JAHR = 1.0             # ein Monat im Format „jahr"
DAUER_BLITZ = 0.5            # Folie „logo" mit blitz=True: ein Schlag je Logo (Format „monat")
DAUER_SCHNELL = 1.5          # Folie „event" mit schnell=True (Saison-Listen)
DAUER_POINTE = 2.9           # Pointe beim Humor: einen Takt länger
EIN = 0.18                  # Einblenden
AUS = 0.12                  # Ausblenden
PUNCH = 0.045               # Zoom des Hintergrunds bei jedem Schnitt
PUNCH_S = 0.45

# Fotos der Startseite als Rückfall-Hintergrund (bilder/QUELLEN.md).
FOTOS = {
    "Laufen": ("laufen.webp", "Thomas Krakow, CC BY-SA 4.0, Wikimedia Commons"),
    "Fahrrad": ("fahrrad.webp", "Dronepicr, CC BY 3.0, Wikimedia Commons"),
    "Schwimmen": ("schwimmen.webp", "Chris Hunkeler, CC BY-SA 2.0, Wikimedia Commons"),
    "Triathlon": ("triathlon.webp", "Steven Fruitsmaak, CC BY-SA 3.0, Wikimedia Commons"),
    None: ("hero.webp", None),     # CC0 - keine Namensnennung nötig
}
PEXELS_SUCHE = {
    "Laufen": ["marathon runners", "running race", "trail running", "runners city"],
    "Fahrrad": ["road cycling", "cyclists race", "gravel bike", "peloton"],
    "Schwimmen": ["open water swimming", "swimming race", "swimmer lake"],
    "Triathlon": ["triathlon", "open water swimming", "road cycling"],
    None: ["marathon runners", "road cycling", "open water swimming"],
}

ERLAUBTE_LIZENZEN = re.compile(
    r"^(cc0|cc[ -]by(-sa)?( \d\.\d)?|public domain|gemeinfrei|pexels|pixabay|"
    r"eigenes material|eigene aufnahme|genehmigung\b.*)$", re.I)


class LizenzFehler(ValueError):
    pass


# ---------------------------------------------------------------- Schrift

_fonts: dict = {}


def schrift(name: str, groesse: int) -> ImageFont.FreeTypeFont:
    key = (name, groesse)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONTS / f"{name}.ttf"), groesse)
    return _fonts[key]


def kondensiert(g: int, fett: bool = True):
    return schrift("BarlowCondensed-700-latin" if fett else "BarlowCondensed-600-latin", g)


def text_schrift(g: int, fett: bool = False):
    return schrift("Barlow-700-latin" if fett else "Barlow-500-latin", g)


_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u200d\ufe0f\u2640\u2642]+")


def ohne_emoji(s: str) -> str:
    """Barlow hat keine Emoji - im Video würden sie als Kästchen stehen."""
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", s or "")).strip()


def breite(font, text: str) -> int:
    return int(font.getlength(text))


def umbrechen(text: str, font, max_breite: int, max_zeilen: int | None = None) -> list[str]:
    zeilen: list[str] = []
    for absatz in text.split("\n"):
        aktuell = ""
        for wort in absatz.split():
            probe = f"{aktuell} {wort}".strip()
            if breite(font, probe) <= max_breite or not aktuell:
                aktuell = probe
            else:
                zeilen.append(aktuell)
                aktuell = wort
        zeilen.append(aktuell)
    if max_zeilen and len(zeilen) > max_zeilen:
        zeilen = zeilen[:max_zeilen]
        letzte = zeilen[-1]
        while letzte and breite(font, letzte + "…") > max_breite:
            letzte = letzte[:-1]
        zeilen[-1] = letzte.rstrip() + "…"
    return zeilen


def passende_groesse(text: str, macher, start: int, max_breite: int, minimum: int = 40) -> int:
    g = start
    while g > minimum and breite(macher(g), text) > max_breite:
        g -= 4
    return g


# ---------------------------------------------------------------- Marke

def zeichne_logo(d: ImageDraw.ImageDraw, x: int, y: int, groesse: int) -> None:
    """Das Zeichen der Seite (favicon.svg): Navy-Kachel, weiße Route,
    oranger Punkt."""
    d.rounded_rectangle([x, y, x + groesse, y + groesse], radius=groesse // 5, fill=NAVY)
    s = groesse / 64
    punkte = [(11, 46), (26, 20), (38, 34), (51, 17)]
    pts = [(x + px * s, y + py * s) for px, py in punkte]
    d.line(pts, fill=WEISS, width=max(3, int(7 * s)), joint="curve")
    for p in pts[:-1]:
        r = 3.5 * s
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=WEISS)
    r = 6 * s
    cx, cy = pts[-1]
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SIGNAL)


_vignette_cache: Image.Image | None = None


def _vignette() -> Image.Image:
    """Abdunklung zu den Rändern (Maske 0…255), einmal gerechnet."""
    global _vignette_cache
    if _vignette_cache is None:
        g = Image.radial_gradient("L").resize((B * 2, H * 2), Image.BILINEAR)
        g = g.crop((B // 2, H // 2, B // 2 + B, H // 2 + H))
        _vignette_cache = g.point(lambda v: int(max(0, v - 70) * 0.62))
    return _vignette_cache


def rahmen_ebene(logo_y: int = 128) -> Image.Image:
    """Was auf jedem Bild gleich ist: Verlauf oben/unten, Marke. Bei
    Stories sitzt die Marke tiefer (oben liegt die Kopfzeile der App)."""
    ebene = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    verlauf = Image.new("L", (1, H))
    for y in range(H):
        oben = max(0.0, 1 - y / 560) * 0.88
        unten = max(0.0, (y - 1000) / 920) * 0.94
        mitte = 0.46          # das Foto ist Stimmung, nicht Inhalt: ruhig halten
        verlauf.putpixel((0, y), int(255 * min(1.0, max(oben, unten, mitte))))
    alpha = ImageChops.lighter(verlauf.resize((B, H)), _vignette())
    farbe = Image.new("RGBA", (B, H), NAVY + (255,))
    farbe.putalpha(alpha)
    ebene = Image.alpha_composite(ebene, farbe)
    d = ImageDraw.Draw(ebene)
    zeichne_logo(d, RAND_X, logo_y, 62)
    d.text((RAND_X + 82, logo_y + 31), "AUSDAUERMASCHINE", font=kondensiert(46), fill=WEISS, anchor="lm")
    return ebene


# ---------------------------------------------------------------- Folien

def pille(d: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill, text_fill=WEISS,
          pad_x: int = 26, hoehe: int | None = None) -> tuple[int, int]:
    hoehe = hoehe or int(font.size * 1.55)
    w = breite(font, text) + 2 * pad_x
    d.rounded_rectangle([x, y, x + w, y + hoehe], radius=hoehe // 2, fill=fill)
    d.text((x + pad_x, y + hoehe / 2), text, font=font, fill=text_fill, anchor="lm")
    return w, hoehe


def _grosser_text(d: ImageDraw.ImageDraw, text: str, y: int, start: int, farbe, max_zeilen: int,
                  upper: bool = True) -> int:
    """Großer Text in Barlow Condensed, so groß wie möglich bei höchstens
    `max_zeilen` Zeilen; gibt das neue y zurück."""
    text = ohne_emoji(text)
    text = text.upper() if upper else text
    if not text:
        return y
    g = start
    zeilen = umbrechen(text, kondensiert(g), TEXT_BREITE, max_zeilen)
    while g > 60 and (len(zeilen) >= max_zeilen and zeilen[-1].endswith("…") or
                      any(breite(kondensiert(g), z) > TEXT_BREITE for z in zeilen)):
        g -= 6
        zeilen = umbrechen(text, kondensiert(g), TEXT_BREITE, max_zeilen)
    for z in zeilen:
        d.text((RAND_X, y), z, font=kondensiert(g), fill=farbe)
        y += int(g * 0.98)
    return y


def hochgezaehlt(text: str, fortschritt: float) -> str:
    """„375" → „0"…„375" (die erste Zahl im Text, mit Tausenderpunkt wie im
    Original), für das Hochzählen der großen Zahl (motion)."""
    if fortschritt >= 1:
        return text
    m = re.search(r"\d[\d.]*", text)
    if not m:
        return text
    roh = m.group(0).rstrip(".")
    try:
        ziel = int(roh.replace(".", ""))
    except ValueError:
        return text
    wert = int(round(ziel * (1 - (1 - max(0.0, fortschritt)) ** 3)))
    neu = f"{wert:,}".replace(",", ".") if "." in roh else str(wert)
    return text[:m.start()] + neu + text[m.start() + len(roh):]


def folie_bild(folie: dict, sport: str | None, fortschritt: float = 1.0) -> Image.Image:
    """Eine Texttafel als transparentes Bild (1080 × 1920). `fortschritt`
    (0…1) nur für animierte Folien (ANIMIERT) – die zeichnet der Renderer
    Bild für Bild neu."""
    img = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    typ = folie.get("typ")
    akzent = SPORTFARBE.get(sport, SIGNAL)

    if typ in ("titel", "moment", "clip_titel"):
        y = 560 if typ != "clip_titel" else 1020
        if folie.get("ueber"):
            _, h = pille(d, RAND_X, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(40, False), SIGNAL)
            y += h + 34
        if typ == "moment" and folie.get("zahl"):
            zahl = folie["zahl"]
            g = passende_groesse(zahl, kondensiert, 230, TEXT_BREITE)
            d.text((RAND_X - 6, y), zahl, font=kondensiert(g), fill=SONNE)
            y += int(g * 1.02)
        titel = ohne_emoji(folie.get("titel", "")).upper()
        g = 124 if typ == "titel" else 92
        f = kondensiert(g)
        zeilen = umbrechen(titel, f, TEXT_BREITE, 4)
        while len(zeilen) > 3 and g > 70:
            g -= 8
            f = kondensiert(g)
            zeilen = umbrechen(titel, f, TEXT_BREITE, 4)
        for z in zeilen:
            d.text((RAND_X, y), z, font=f, fill=WEISS)
            y += int(g * 0.98)
        y += 30
        for z in folie.get("zeilen", [])[:5]:
            z = ohne_emoji(z)
            if not z:
                continue
            d.rectangle([RAND_X, y + 12, RAND_X + 8, y + 50], fill=akzent)
            for teil in umbrechen(z, text_schrift(46), TEXT_BREITE - 30, 2):
                d.text((RAND_X + 30, y), teil, font=text_schrift(46), fill=KREIDE)
                y += 60
            y += 8

    elif typ == "hook":
        y = 470
        if folie.get("ueber"):
            _, h = pille(d, RAND_X, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(42, False), SIGNAL)
            y += h + 30
        if folie.get("zahl"):
            zahl = ohne_emoji(folie["zahl"]).upper()
            g = passende_groesse(zahl, kondensiert, 300, TEXT_BREITE, 120)
            d.text((RAND_X - 8, y), hochgezaehlt(zahl, fortschritt), font=kondensiert(g), fill=SONNE)
            y += int(g * 1.0)
        y = _grosser_text(d, folie.get("titel", ""), y, 104, WEISS, 4)
        y += 26
        for z in folie.get("zeilen", [])[:3]:
            z = ohne_emoji(z)
            if z:
                d.rectangle([RAND_X, y + 12, RAND_X + 8, y + 50], fill=akzent)
                d.text((RAND_X + 30, y), z, font=text_schrift(46), fill=KREIDE)
                y += 68

    elif typ == "event":
        y = 400
        farbe = SPORTFARBE.get(folie.get("sport"), akzent)
        if folie.get("ueber"):
            _, h = pille(d, RAND_X, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(42, False), SIGNAL)
            y += h + 26
        art = " · ".join(t for t in (folie.get("sport"), folie.get("kategorie")) if t)
        if art:
            _, h = pille(d, RAND_X, y, art.upper(), kondensiert(38, False), farbe)
            y += h + 24
        datum = ohne_emoji(folie.get("datum", "")).upper().rstrip(".")
        d.text((RAND_X - 4, y), datum, font=kondensiert(150), fill=SONNE)
        y += 158
        y = _grosser_text(d, folie.get("name", ""), y, 100, WEISS, 3, upper=False)
        y += 18
        if folie.get("ort"):
            d.rectangle([RAND_X, y + 12, RAND_X + 8, y + 52], fill=farbe)
            d.text((RAND_X + 30, y), ohne_emoji(folie["ort"]), font=text_schrift(50), fill=KREIDE)
            y += 84
        if folie.get("strecken"):
            for teil in umbrechen(ohne_emoji(folie["strecken"]), kondensiert(58), TEXT_BREITE - 60, 2):
                _, h = pille(d, RAND_X, y, teil, kondensiert(58), TIEFE, WEISS, pad_x=28)
                y += h + 14
        if folie.get("hinweis"):
            d.text((RAND_X, max(y + 30, 1390)), ohne_emoji(folie["hinweis"]), font=text_schrift(42, True), fill=WEISS)

    elif typ == "satz":
        y = 560
        if folie.get("ueber"):
            _, h = pille(d, RAND_X, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(42, False),
                         SIGNAL if not folie.get("pointe") else TIEFE)
            y += h + 34
        y = _grosser_text(d, folie.get("titel", ""), y, 128, SONNE if folie.get("pointe") else WEISS, 5)
        y += 30
        for z in folie.get("zeilen", [])[:3]:
            z = ohne_emoji(z)
            if z:
                d.text((RAND_X, y), z, font=text_schrift(48, True), fill=KREIDE)
                y += 70

    elif typ == "liste":
        y = 300
        d.text((RAND_X, y), ohne_emoji(folie.get("titel", "")).upper(), font=kondensiert(88), fill=WEISS)
        y += 120
        events = folie.get("events", [])[:5]
        hoehe = 196
        for ev in events:
            farbe = SPORTFARBE.get(ev.get("sport"), akzent)
            panel = Image.new("RGBA", (TEXT_BREITE, hoehe - 18), NAVY + (215,))
            maske = Image.new("L", panel.size, 0)
            ImageDraw.Draw(maske).rounded_rectangle([0, 0, panel.size[0] - 1, panel.size[1] - 1], radius=26, fill=255)
            img.paste(panel, (RAND_X, y), maske)
            d.rounded_rectangle([RAND_X, y, RAND_X + 12, y + hoehe - 18], radius=6, fill=farbe)
            datum = ev.get("datum", "")
            tag, _, rest = datum.partition(" ")
            d.text((RAND_X + 40, y + 30), tag.upper(), font=kondensiert(34, False), fill=GRAU)
            d.text((RAND_X + 40, y + 66), rest.rstrip("."), font=kondensiert(56), fill=WEISS)
            x2 = RAND_X + 200
            name_zeilen = umbrechen(ohne_emoji(ev.get("name", "")), kondensiert(48, False), TEXT_BREITE - 230, 2)
            ny = y + 22 if len(name_zeilen) == 1 else y + 12
            for z in name_zeilen:
                d.text((x2, ny), z, font=kondensiert(48, False), fill=WEISS)
                ny += 52
            info = " · ".join(t for t in (ev.get("ort"), ev.get("strecken")) if t)
            info = umbrechen(info, text_schrift(32), TEXT_BREITE - 230, 1)[0] if info else ""
            d.text((x2, max(ny + 6, y + 112)), info, font=text_schrift(32), fill=GRAU)
            y += hoehe

    elif typ == "moment_text":
        y = 560
        if folie.get("titel"):
            pille(d, RAND_X, y, ohne_emoji(folie["titel"]), text_schrift(38, True), TIEFE)
            y += 100
        f = text_schrift(52)
        zeilen = umbrechen(ohne_emoji(folie.get("text", "")), f, TEXT_BREITE, 11)
        for z in zeilen:
            d.text((RAND_X, y), z, font=f, fill=WEISS)
            y += 72

    elif typ == "logo":
        _logo_folie(img, d, folie)

    elif typ == "top":
        _top_folie(img, d, folie)

    elif typ == "balken":
        _balken_folie(img, d, folie, fortschritt)

    elif typ == "jahr":
        _jahr_folie(img, d, folie)

    elif typ == "duell":
        _duell_folie(img, d, folie, fortschritt)

    elif typ == "cta":
        y = 700
        titel = ohne_emoji(folie.get("titel", "")).upper()
        g = passende_groesse(titel, kondensiert, 120, TEXT_BREITE, 70)
        for z in umbrechen(titel, kondensiert(g), TEXT_BREITE, 3):
            d.text((RAND_X, y), z, font=kondensiert(g), fill=WEISS)
            y += int(g * 0.98)
        y += 40
        for i, z in enumerate(folie.get("zeilen", [])):
            z = ohne_emoji(z)
            if "." in z and " " not in z:          # die Adresse: orange Pille
                _, h = pille(d, RAND_X, y, z, kondensiert(72), SONNE, NAVY, pad_x=34)
                y += h + 30
            else:
                d.text((RAND_X, y), z, font=text_schrift(46, i == len(folie["zeilen"]) - 1), fill=KREIDE)
                y += 70
        # Pfeil nach unten zur Caption ("Link in der Bio" steht im Profil,
        # der Pfeil zeigt auf den Account-Namen unten links).
        ax, ay = RAND_X + 12, y + 30
        d.line([(ax, ay), (ax, ay + 90)], fill=SONNE, width=10)
        d.polygon([(ax - 26, ay + 70), (ax + 26, ay + 70), (ax, ay + 110)], fill=SONNE)
    return img


KARTE = (100, 560, 940, 1060)       # die Logo-Karte (x0, y0, x1, y1), in der sicheren Zone


def logo_karte(img: Image.Image, d: ImageDraw.ImageDraw, box: tuple, logo_id: str | None, name: str,
               radius: int = 44, rand: int = 70, rahmen=None) -> bool:
    """Das Logo eines Events auf einer Karte in `box` - weiß, bei hellen
    Logos Navy (insta_logos.ist_hell). Ohne geprüftes Logo steht der Name
    groß auf der Karte. Gibt zurück, ob ein Logo gezeichnet wurde."""
    import insta_logos
    x0, y0, x1, y1 = box
    logo = insta_logos.logo_bild(logo_id) if logo_id else None
    hell = bool(logo and logo[1])
    d.rounded_rectangle(box, radius=radius, fill=NAVY if hell else WEISS,
                        outline=rahmen, width=8 if rahmen else 0)
    if logo:
        bild = logo[0]
        f = min((x1 - x0 - 2 * rand) / bild.width, (y1 - y0 - 2 * rand) / bild.height, 3.0)
        bild = bild.resize((max(1, int(bild.width * f)), max(1, int(bild.height * f))), Image.LANCZOS)
        img.alpha_composite(bild, ((x0 + x1 - bild.width) // 2, (y0 + y1 - bild.height) // 2))
        return True
    text = ohne_emoji(name).upper()
    breit = x1 - x0 - 2 * max(16, rand // 2)
    g = min(120, int((y1 - y0) * 0.42))
    zeilen = umbrechen(text, kondensiert(g), breit, 3)
    while g > 18 and (zeilen[-1].endswith("…") or len(zeilen) * g * 0.98 > y1 - y0 - 2 * max(10, rand // 3)
                      or any(breite(kondensiert(g), z) > breit for z in zeilen)):
        g -= 2
        zeilen = umbrechen(text, kondensiert(g), breit, 3)
    ty = (y0 + y1) / 2 - len(zeilen) * g * 0.98 / 2
    for z in zeilen:
        d.text(((x0 + x1) / 2, ty), z, font=kondensiert(g), fill=NAVY, anchor="ma")
        ty += g * 0.98
    return False


# ------------------------------------------------------------- Karte

KARTE_GRENZEN = (5.8, 45.75, 17.25, 55.1)      # lon0, lat0, lon1, lat1: DE, AT, CH, Südtirol
_umrisse: list | None = None


def _laender_umrisse() -> list:
    """Die Ringe aus laender.json (Natural Earth, Public Domain) – dieselbe
    Datei wie die Maske auf karte.html."""
    global _umrisse
    if _umrisse is None:
        try:
            daten = json.loads((WURZEL / "laender.json").read_text(encoding="utf-8"))["laender"]
            _umrisse = [ring for ringe in daten.values() for ring in ringe]
        except (OSError, ValueError, KeyError):
            _umrisse = []
    return _umrisse


def karte_bild(w: int, h: int, punkte: list[tuple[float, float, str]], aktiv: int | None,
               farbe=SIGNAL) -> Image.Image:
    """Eine flache Karte der vier Regionen (w × h, transparent) mit
    nummerierten Punkten [(lat, lon, Beschriftung)]. Der aktive Punkt ist
    groß und in `farbe`, die anderen klein und weiß; ohne aktiven Punkt
    sind alle gleich groß. Gezeichnet doppelt so groß und verkleinert –
    so werden die Kanten glatt."""
    s2 = 2
    W, H = w * s2, h * s2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lon0, lat0, lon1, lat1 = KARTE_GRENZEN
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    bw, bh = (lon1 - lon0) * kx, lat1 - lat0
    f = min(W / bw, H / bh) * 0.96
    ox, oy = (W - bw * f) / 2, (H - bh * f) / 2

    def xy(lat: float, lon: float) -> tuple[float, float]:
        return ox + (lon - lon0) * kx * f, oy + (lat1 - lat) * f

    for ring in _laender_umrisse():
        if len(ring) > 2:
            d.polygon([xy(lat, lon) for lon, lat in ring], fill=TIEFE + (235,), outline=(160, 180, 210, 255))
    for ring in _laender_umrisse():
        if len(ring) > 2:
            d.line([xy(lat, lon) for lon, lat in ring] + [xy(ring[0][1], ring[0][0])],
                   fill=(170, 190, 220, 255), width=3)
    reihenfolge = [i for i in range(len(punkte)) if i != aktiv] + ([aktiv] if aktiv is not None else [])
    for i in reihenfolge:
        lat, lon, text = punkte[i]
        if lat is None or lon is None:
            continue
        x, y = xy(lat, lon)
        gross = aktiv is None or i == aktiv
        r = (34 if i == aktiv else 26 if aktiv is None else 16) * s2
        if i == aktiv:
            d.ellipse([x - r * 1.8, y - r * 1.8, x + r * 1.8, y + r * 1.8], fill=farbe[:3] + (70,))
        d.ellipse([x - r, y - r, x + r, y + r], fill=farbe if i == aktiv or aktiv is None else WEISS,
                  outline=WEISS, width=3 * s2)
        if gross and text:
            d.text((x, y + 1), text, font=kondensiert(int(r * 1.15)), anchor="mm",
                   fill=WEISS if (i == aktiv or aktiv is None) else NAVY)
    return img.resize((w, h), Image.LANCZOS)


def _starter_text(n: int | None) -> str:
    if not n:
        return ""
    gerundet = round(n, -3) if n >= 10000 else round(n, -2)
    return f"ca. {gerundet:,} am Start".replace(",", ".")


def _raster(n: int, x0: int, y0: int, x1: int, y1: int, spalten: int, luecke: int = 18,
            max_h: int = 180) -> list[tuple[int, int, int, int]]:
    """n Kästen in `spalten` Spalten, zeilenweise, mittig in der Fläche."""
    zeilen = (n + spalten - 1) // spalten
    w = (x1 - x0 - (spalten - 1) * luecke) // spalten
    h = min(max_h, (y1 - y0 - (zeilen - 1) * luecke) // zeilen, int(w * 0.62))
    boxen = []
    for i in range(n):
        z, sp = divmod(i, spalten)
        rest = n - z * spalten
        in_zeile = min(spalten, rest)
        versatz = (spalten - in_zeile) * (w + luecke) // 2      # letzte Zeile mittig
        bx = x0 + versatz + sp * (w + luecke)
        by = y0 + z * (h + luecke)
        boxen.append((bx, by, bx + w, by + h))
    return boxen


def _gedaempft(img: Image.Image, box: tuple, radius: int) -> None:
    """Navy über eine Karte legen (nicht durchsichtig machen – sonst scheint
    das Foto durch und das Logo wirkt verwaschen)."""
    schleier = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(schleier).rounded_rectangle(box, radius=radius, fill=NAVY + (150,))
    img.alpha_composite(schleier)


def _event_text(d: ImageDraw.ImageDraw, e: dict, x: int, y: int, breite_px: int, gross: int = 76) -> int:
    """Datum (orange), Name, Ort · Teilnehmende; gibt das neue y zurück."""
    d.text((x, y), ohne_emoji(e.get("datum", "")).upper(), font=kondensiert(gross), fill=SONNE)
    y += int(gross * 1.08)
    for z in umbrechen(ohne_emoji(e["name"]), kondensiert(58, False), breite_px, 2):
        d.text((x, y), z, font=kondensiert(58, False), fill=WEISS)
        y += 60
    info = " · ".join(t for t in (e.get("ort"), _starter_text(e.get("starter"))) if t)
    for z in umbrechen(ohne_emoji(info), text_schrift(36), breite_px, 2):
        d.text((x, y + 4), z, font=text_schrift(36), fill=KREIDE)
        y += 46
    return y


def _top_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict) -> None:
    """Die größten Events einer Kategorie (Format „top", insta_inhalte) –
    keine Rangfolge, nach Datum. Vier Designs, damit sich die Reels nicht
    gleichen (vom Nutzer: „unterschiedliche Designs in der Darstellung"):

      karte       oben die Logos (eine oder zwei Reihen, das aktive
                  hervorgehoben), darunter die Angaben, unten die Karte
      einzeln     das Datum riesig, das Logo groß, Angaben und eine kleine
                  Karte; die Übersicht als Liste mit Logos
      raster      die Logos füllen nacheinander ein Raster in zwei Spalten,
                  das neue umrandet, darunter seine Angaben
      zeitleiste  eine Achse von oben nach unten über die zwölf Monate,
                  die Logos hängen nacheinander an ihrem Termin

    `aktiv` = das gerade vorgestellte Event (Index), None = Übersicht."""
    eintraege = folie.get("eintraege") or []
    n = len(eintraege)
    aktiv = folie.get("aktiv")
    design = folie.get("variante")
    farbe = SPORTFARBE.get(folie.get("sport"), SIGNAL)
    titel = ohne_emoji(folie.get("titel", "")).upper()
    punkte = [(e.get("lat"), e.get("lon"), str(i + 1)) for i, e in enumerate(eintraege)]

    if design == "einzeln":
        if aktiv is None:
            pille(d, RAND_X, 250, titel, kondensiert(46, False), farbe)
            zeile_h = min(172, 1180 // max(1, n))
            y = 350
            for e in eintraege:
                kh = zeile_h - 22
                logo_karte(img, d, (RAND_X, y, RAND_X + int(kh * 1.6), y + kh), e.get("logo_id"), e["name"],
                           radius=max(10, kh // 6), rand=max(6, kh // 9))
                tx = RAND_X + int(kh * 1.6) + 28
                g = max(30, min(52, kh // 2 - 4))
                d.text((tx, y + kh // 2 - g // 2 - 4),
                       umbrechen(ohne_emoji(e["name"]), kondensiert(g, False), 960 - tx, 1)[0],
                       font=kondensiert(g, False), fill=WEISS, anchor="lm")
                d.text((tx, y + kh // 2 + g // 2 + 4), ohne_emoji(e.get("datum", "")),
                       font=text_schrift(max(24, g * 2 // 3)), fill=SONNE, anchor="lm")
                y += zeile_h
            return
        e = eintraege[aktiv]
        pille(d, RAND_X, 250, f"{titel} · {aktiv + 1}/{n}", kondensiert(42, False), farbe)
        tag, _, rest = ohne_emoji(e.get("datum", "")).upper().partition(" ")
        d.text((RAND_X - 8, 330), tag, font=kondensiert(300), fill=SONNE)
        d.text((RAND_X + 10 + breite(kondensiert(300), tag), 400), rest, font=kondensiert(110), fill=WEISS)
        logo_karte(img, d, (RAND_X, 680, 960, 1030), e.get("logo_id"), e["name"], radius=40, rand=60)
        y = 1070
        for z in umbrechen(ohne_emoji(e["name"]), kondensiert(62, False), 540, 2):
            d.text((RAND_X, y), z, font=kondensiert(62, False), fill=WEISS)
            y += 64
        for z in (e.get("ort", ""), _starter_text(e.get("starter"))):
            if z:
                d.text((RAND_X, y + 6), ohne_emoji(z), font=text_schrift(38), fill=KREIDE)
                y += 52
        img.alpha_composite(karte_bild(330, 380, [punkte[aktiv]], 0, farbe), (630, 1090))
        return

    if design == "raster":
        pille(d, RAND_X, 250, titel, kondensiert(46, False), farbe)
        spalten = 2 if n <= 8 else 3
        unten = 1180 if aktiv is not None else 1460
        boxen = _raster(n, RAND_X, 350, 960, unten, spalten, max_h=230)
        sichtbar = n if aktiv is None else aktiv + 1
        for i in range(sichtbar):
            r = max(14, (boxen[i][3] - boxen[i][1]) // 7)
            logo_karte(img, d, boxen[i], eintraege[i].get("logo_id"), eintraege[i]["name"], radius=r,
                       rand=max(10, (boxen[i][3] - boxen[i][1]) // 8),
                       rahmen=SONNE if i == aktiv else None)
            if aktiv is not None and i != aktiv:
                _gedaempft(img, boxen[i], r)
        for i in range(sichtbar, n):                       # leere Plätze, die noch kommen
            r = max(14, (boxen[i][3] - boxen[i][1]) // 7)
            d.rounded_rectangle(boxen[i], radius=r, outline=(255, 255, 255, 90), width=4)
        if aktiv is not None:
            _event_text(d, eintraege[aktiv], RAND_X, max(boxen[-1][3] + 40, 1210), TEXT_BREITE, gross=70)
        return

    if design == "zeitleiste":
        pille(d, RAND_X, 250, titel, kondensiert(46, False), farbe)
        y0, y1, ax = 360, 1470, RAND_X + 70
        d.line([(ax, y0), (ax, y1)], fill=(255, 255, 255, 170), width=6)
        start = folie.get("start")                        # erster Monat der 12 (YYYY-MM)
        try:
            j, m = (int(t) for t in str(start).split("-")[:2])
        except ValueError:
            j, m = 2027, 1
        monate = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]
        for k in range(13):
            yy = y0 + (y1 - y0) * k / 12
            d.line([(ax - 14, yy), (ax + 14, yy)], fill=(255, 255, 255, 170), width=4)
            if k < 12:
                d.text((ax - 26, yy + (y1 - y0) / 24), monate[(m - 1 + k) % 12], font=kondensiert(30, False),
                       fill=GRAU, anchor="rm")
        kh = min(150, (y1 - y0 - (n - 1) * 12) // n)
        kw = int(kh * 1.7)
        x_k = ax + 70

        def y_termin(e: dict) -> float:
            try:
                ej, em = (int(t) for t in str(e.get("monat_iso", "")).split("-")[:2])
                tag = int(e.get("tag") or 15)
            except ValueError:
                return (y0 + y1) / 2
            k = (ej - j) * 12 + (em - m) + (tag - 1) / 31
            return y0 + (y1 - y0) * max(0.0, min(12.0, k)) / 12

        # Karten der Reihe nach, ohne Überlappung, so nah wie möglich am Termin
        lagen, naechst = [], y0
        for i, e in enumerate(eintraege):
            ziel = y_termin(e) - kh / 2
            lagen.append(max(naechst, min(ziel, y1 - (n - i) * (kh + 12) + 12)))
            naechst = lagen[-1] + kh + 12
        sichtbar = n if aktiv is None else aktiv + 1
        for i in range(sichtbar):
            e, ky = eintraege[i], int(lagen[i])
            punkt_y = y_termin(e)
            linie = SONNE if (aktiv is None or i == aktiv) else (255, 255, 255, 120)
            d.line([(ax, punkt_y), (x_k - 10, ky + kh / 2)], fill=linie, width=4)
            d.ellipse([ax - 12, punkt_y - 12, ax + 12, punkt_y + 12], fill=linie)
            box = (x_k, ky, x_k + kw, ky + kh)
            r = max(12, kh // 6)
            logo_karte(img, d, box, e.get("logo_id"), e["name"], radius=r, rand=max(8, kh // 9),
                       rahmen=SONNE if i == aktiv else None)
            if aktiv is not None and i != aktiv:
                _gedaempft(img, box, r)
            tx = x_k + kw + 24
            if aktiv is None or i == aktiv:
                g = max(28, min(46, kh // 3))
                d.text((tx, ky + kh / 2 - g * 0.6), umbrechen(ohne_emoji(e["name"]), kondensiert(g, False),
                                                               960 - tx, 1)[0],
                       font=kondensiert(g, False), fill=WEISS, anchor="lm")
                d.text((tx, ky + kh / 2 + g * 0.6), ohne_emoji(e.get("datum", "")),
                       font=text_schrift(max(22, g * 2 // 3)), fill=SONNE, anchor="lm")
        return

    # Design „karte"
    pille(d, RAND_X, 250, titel, kondensiert(44, False), farbe)
    boxen = _raster(n, RAND_X, 350, 960, 350 + (150 if n <= 5 else 290), min(n, 5), luecke=14, max_h=150)
    for i, e in enumerate(eintraege):
        r = max(14, (boxen[i][3] - boxen[i][1]) // 6)
        logo_karte(img, d, boxen[i], e.get("logo_id"), e["name"], radius=r,
                   rand=max(10, (boxen[i][3] - boxen[i][1]) // 9),
                   rahmen=SONNE if (aktiv is not None and i == aktiv) else None)
        if aktiv is not None and i != aktiv:
            _gedaempft(img, boxen[i], r)
    y = boxen[-1][3] + 36
    if aktiv is None:
        for z in umbrechen(ohne_emoji(folie.get("schluss", "")).upper(), kondensiert(84), TEXT_BREITE, 2):
            d.text((RAND_X, y), z, font=kondensiert(84), fill=WEISS)
            y += 84
        oben = boxen[-1][3] + 250
    else:
        # das vorgestellte Event groß: Logo-Karte über die ganze Breite
        e = eintraege[aktiv]
        name_unten = logo_karte(img, d, (RAND_X, y, 960, y + 250), e.get("logo_id"), e["name"], radius=36, rand=44)
        y += 276
        d.text((RAND_X, y), ohne_emoji(e.get("datum", "")).upper(), font=kondensiert(76), fill=SONNE)
        y += 80
        if name_unten:
            d.text((RAND_X, y), umbrechen(ohne_emoji(e["name"]), kondensiert(56, False), TEXT_BREITE, 1)[0],
                   font=kondensiert(56, False), fill=WEISS)
            y += 62
        info = " · ".join(t for t in (e.get("ort"), _starter_text(e.get("starter"))) if t)
        d.text((RAND_X, y), ohne_emoji(info), font=text_schrift(36), fill=KREIDE)
        oben = boxen[-1][3] + 36 + 276 + 80 + 62 + 66
    hoehe = 1490 - oben
    img.alpha_composite(karte_bild(TEXT_BREITE, hoehe, punkte, aktiv, farbe), (RAND_X, oben))


ANIMIERT = {"balken", "duell"}          # Folien, die sich während sie stehen bewegen
BALKEN_TAKT = 0.55             # Sekunden je Balken
BALKEN_WACHSEN = 0.45


def _balken_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict, fortschritt: float) -> None:
    """Animierte Balkengrafik (Format „laengste"): je Feld (Laufen, Rad) die
    Rennen von oben nach unten nach Länge; die Balken wachsen nacheinander
    vom KÜRZESTEN (unten) zum längsten (oben), die Kilometer zählen dabei
    hoch, Name und Termin blenden mit ein. Jedes Feld hat seinen eigenen
    Maßstab – 5.000 km Rad neben 1.284 km Laufen ließen sonst die Läufe
    verschwinden."""
    felder = folie.get("felder") or []
    t = fortschritt * float(folie.get("dauer") or 6.0)
    pille(d, RAND_X, 250, ohne_emoji(folie.get("titel", "")).upper(), kondensiert(44, False), SIGNAL)
    oben, unten = 350, 1480
    feld_h = (unten - oben) / max(1, len(felder))
    k = 0                                          # laufende Nummer des Balkens (Reihenfolge der Animation)
    for fi, feld in enumerate(felder):
        zeilen = feld.get("zeilen") or []
        farbe = SPORTFARBE.get(feld.get("sport"), SIGNAL)
        y0 = oben + fi * feld_h
        kopf = 0
        deckung = min(1.0, max(0.0, (t - 0.05) / 0.3))     # die Fläche blendet mit den ersten Balken ein
        if deckung > 0:
            flaeche = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(flaeche).rounded_rectangle([RAND_X - 24, int(y0) - 18, 984, int(y0 + feld_h) - 22],
                                                      radius=30, fill=NAVY + (int(190 * deckung),))
            img.alpha_composite(flaeche)
        if len(felder) > 1:
            pille(d, RAND_X, int(y0), ohne_emoji(feld.get("titel", "")).upper(), kondensiert(36, False), farbe)
            kopf = 66
        zeile_h = (feld_h - kopf - 10) / max(1, len(zeilen))
        maxkm = max((z["km"] for z in zeilen), default=1)
        maxbreite = TEXT_BREITE - 190
        g_name = int(max(30, min(46, zeile_h * 0.38)))
        balken_h = int(max(18, min(40, zeile_h * 0.30)))
        for i in range(len(zeilen) - 1, -1, -1):       # unten (kürzester) zuerst
            z = zeilen[i]
            start = 0.25 + k * BALKEN_TAKT
            k += 1
            if t < start:
                continue
            p = min(1.0, (t - start) / BALKEN_WACHSEN)
            glatt = 1 - (1 - p) ** 3
            y = y0 + kopf + i * zeile_h
            alpha = int(255 * min(1.0, (t - start) / 0.2))
            name = umbrechen(ohne_emoji(z["name"]), kondensiert(g_name, False), TEXT_BREITE - 20, 1)[0]
            ebene = Image.new("RGBA", img.size, (0, 0, 0, 0))
            e = ImageDraw.Draw(ebene)
            e.text((RAND_X, y), name, font=kondensiert(g_name, False), fill=WEISS + (alpha,))
            e.text((RAND_X + breite(kondensiert(g_name, False), name) + 14, y + g_name * 0.22),
                   ohne_emoji(f"{z.get('datum', '')} · {z.get('ort', '')}"), font=text_schrift(int(g_name * 0.62)),
                   fill=GRAU + (alpha,))
            by = y + g_name + 8
            bw = max(10, int(maxbreite * (z["km"] / maxkm) * glatt))
            e.rounded_rectangle([RAND_X, by, RAND_X + bw, by + balken_h], radius=balken_h // 2,
                                fill=farbe + (alpha,))
            wert = z["km"] * glatt
            text = (f"{wert:,.0f} km".replace(",", ".") if p < 1 else z.get("km_text", ""))
            e.text((RAND_X + bw + 14, by + balken_h / 2), text, font=kondensiert(int(balken_h * 1.25)),
                   fill=SONNE + (alpha,), anchor="lm")
            img.alpha_composite(ebene)


def _logo_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict) -> None:
    """Ein Event als Logo (Formate „monat" und „anmeldung", insta_inhalte):
    das Logo groß auf einer Karte - weiß, bei hellen Logos Navy -, darunter
    Datum, Name und Ort. Liegt kein Logo im Cache (insta_logos.py), steht
    der Name groß auf der Karte."""
    x0, y0, x1, y1 = KARTE
    y = y0 - 110
    if folie.get("ueber"):
        pille(d, RAND_X + 20, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(46, False), SIGNAL)
    name_unten = logo_karte(img, d, KARTE, folie.get("logo_id"), folie.get("name", ""), radius=44, rand=70)
    y = y1 + 44
    if folie.get("datum"):
        d.text((RAND_X + 20, y), ohne_emoji(folie["datum"]).upper().rstrip("."), font=kondensiert(104), fill=SONNE)
        y += 112
    if name_unten and folie.get("name"):
        for z in umbrechen(ohne_emoji(folie["name"]), kondensiert(62, False), TEXT_BREITE - 40, 2):
            d.text((RAND_X + 20, y), z, font=kondensiert(62, False), fill=WEISS)
            y += 64
        y += 6
    if folie.get("ort"):
        d.text((RAND_X + 20, y), ohne_emoji(folie["ort"]), font=text_schrift(42), fill=KREIDE)


MONATE_GROSS = ["JANUAR", "FEBRUAR", "MÄRZ", "APRIL", "MAI", "JUNI", "JULI", "AUGUST", "SEPTEMBER",
                "OKTOBER", "NOVEMBER", "DEZEMBER"]
MONATE_KURZ_GROSS = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]


def _jahr_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict) -> None:
    """„Dein Rennjahr" (Format „jahr"): je Monat das größte Event - der
    Monat riesig, darunter eine Leiste der zwölf Monate (der aktuelle
    leuchtet), das Logo und die Angaben. `aktiv` None = die Übersicht:
    alle zwölf Logos in einem Raster 3 × 4 mit ihrem Monat."""
    eintraege = folie.get("eintraege") or []
    aktiv = folie.get("aktiv")
    farbe = SPORTFARBE.get(folie.get("sport"), SIGNAL)
    if aktiv is None:
        pille(d, RAND_X, 250, ohne_emoji(folie.get("titel", "")).upper(), kondensiert(46, False), SIGNAL)
        spalten, luecke = 3, 22
        w = (TEXT_BREITE - (spalten - 1) * luecke) // spalten
        zeilen = (len(eintraege) + spalten - 1) // spalten
        zeile_h = min(290, (1490 - 350) // max(1, zeilen))
        for i, e in enumerate(eintraege):
            z, sp = divmod(i, spalten)
            x, y = RAND_X + sp * (w + luecke), 350 + z * zeile_h
            d.text((x + 4, y), MONATE_KURZ_GROSS[e["monat"] - 1], font=kondensiert(40), fill=SONNE)
            kh = zeile_h - 70
            logo_karte(img, d, (x, y + 50, x + w, y + 50 + kh), e.get("logo_id"), e["name"],
                       radius=max(14, kh // 7), rand=max(10, kh // 8))
        return
    e = eintraege[aktiv]
    monat = MONATE_GROSS[e["monat"] - 1]
    g = passende_groesse(monat, kondensiert, 230, TEXT_BREITE - 150, 120)
    d.text((RAND_X - 6, 255), monat, font=kondensiert(g), fill=WEISS)
    d.text((RAND_X + breite(kondensiert(g), monat) + 18, 255 + int(g * 0.52)), str(e["jahr"]),
           font=kondensiert(64), fill=SONNE)
    # die zwölf Monate als Leiste
    y_l, n = 255 + int(g * 1.02) + 10, len(eintraege)
    seg = (TEXT_BREITE - (n - 1) * 10) / max(1, n)
    for i in range(n):
        x0 = RAND_X + i * (seg + 10)
        box = [x0, y_l, x0 + seg, y_l + 16]
        if i < aktiv:
            d.rounded_rectangle(box, radius=8, fill=farbe)
        elif i == aktiv:
            d.rounded_rectangle([x0, y_l - 4, x0 + seg, y_l + 20], radius=12, fill=SONNE)
        else:
            d.rounded_rectangle(box, radius=8, outline=(255, 255, 255, 110), width=3)
    box = (RAND_X, y_l + 70, 960, y_l + 70 + 430)
    name_unten = logo_karte(img, d, box, e.get("logo_id"), e["name"], radius=44, rand=64)
    y = box[3] + 40
    d.text((RAND_X, y), ohne_emoji(e.get("datum", "")).upper(), font=kondensiert(96), fill=SONNE)
    y += 104
    if name_unten:
        for z in umbrechen(ohne_emoji(e["name"]), kondensiert(60, False), TEXT_BREITE, 2):
            d.text((RAND_X, y), z, font=kondensiert(60, False), fill=WEISS)
            y += 62
    info = " · ".join(t for t in (e.get("ort"), _starter_text(e.get("starter"))) if t)
    d.text((RAND_X, y + 6), ohne_emoji(info), font=text_schrift(40), fill=KREIDE)


DUELL_EIN = 0.9            # bis die Logos stehen
DUELL_ZEILE = 0.85         # Abstand der Vergleichszeilen


def _duell_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict, fortschritt: float) -> None:
    """Zwei große Events im direkten Vergleich (Format „duell"): die
    Logos fahren von links und rechts herein, dazwischen springt das VS,
    dann kommen Zeile für Zeile Termin, Ort, Teilnehmende, Strecken - der
    größere Wert leuchtet. Zum Schluss die Frage."""
    t = fortschritt * float(folie.get("dauer") or 7.0)
    a, b = folie["links"], folie["rechts"]
    farbe = SPORTFARBE.get(folie.get("sport"), SIGNAL)
    pille(d, RAND_X, 250, ohne_emoji(folie.get("titel", "DUELL")).upper(), kondensiert(46, False), farbe)
    spalte = [(RAND_X, 500), (560, 960)]
    for k, e in enumerate((a, b)):
        p = _ease_back(min(1.0, max(0.0, (t - 0.1 * k) / 0.55)))
        dx = int((1 - p) * (-520 if k == 0 else 520))
        x0, x1 = spalte[k]
        ebene = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ed = ImageDraw.Draw(ebene)
        logo_karte(ebene, ed, (x0, 350, x1, 640), e.get("logo_id"), e["name"], radius=32, rand=34)
        y = 668
        for z in umbrechen(ohne_emoji(e["name"]), kondensiert(42, False), x1 - x0, 2):
            ed.text(((x0 + x1) / 2, y), z, font=kondensiert(42, False), fill=WEISS, anchor="ma")
            y += 46
        img.alpha_composite(ebene, (dx, 0) if dx >= 0 else (0, 0), (0, 0) if dx >= 0 else (-dx, 0))
    # VS
    p = min(1.0, max(0.0, (t - 0.45) / 0.35))
    if p > 0:
        r = int(66 * _ease_back(p, 2.4))
        cx, cy = 530, 495
        d.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], fill=farbe + (120,))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SONNE, outline=WEISS, width=6)
        if r > 20:
            d.text((cx, cy + 2), "VS", font=kondensiert(int(r * 0.95)), fill=NAVY, anchor="mm")
    zeilen = folie.get("zeilen") or []
    y0 = 800
    # eine ruhige Fläche hinter dem Vergleich, damit die Zahlen auf jedem Foto lesbar sind
    p_flaeche = _ease_aus(min(1.0, max(0.0, (t - DUELL_EIN + 0.25) / 0.4)))
    if p_flaeche > 0:
        flaeche = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(flaeche).rounded_rectangle([RAND_X - 20, y0 - 50, 980, y0 + 150 * len(zeilen) + 100],
                                                  radius=36, fill=NAVY + (int(205 * p_flaeche),))
        img.alpha_composite(flaeche)
    for i, (label, wl, wr, besser) in enumerate(zeilen):
        start = DUELL_EIN + i * DUELL_ZEILE
        if t < start:
            continue
        p = _ease_aus(min(1.0, (t - start) / 0.4))
        alpha = int(255 * p)
        y = y0 + i * 150
        ebene = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ed = ImageDraw.Draw(ebene)
        if i:
            ed.line([(RAND_X + 20, y - 18), (940, y - 18)], fill=(255, 255, 255, int(50 * p)), width=2)
        ed.text((530, y), label.upper(), font=kondensiert(32, False), fill=KREIDE + (int(alpha * 0.8),), anchor="ma")
        versatz = int((1 - p) * 60)
        for k, wert in enumerate((wl, wr)):
            x0, x1 = spalte[k]
            f = kondensiert(60)
            text = umbrechen(ohne_emoji(str(wert)), f, x1 - x0 - 20, 1)[0]
            fill = (SONNE if besser == k else WEISS) + (alpha,)
            mx = (x0 + x1) / 2 + (versatz if k == 0 else -versatz)
            ed.text((mx, y + 42), text, font=f, fill=fill, anchor="ma")
        img.alpha_composite(ebene)
    start = DUELL_EIN + len(zeilen) * DUELL_ZEILE + 0.2
    if t >= start and folie.get("frage"):
        p = _ease_back(min(1.0, (t - start) / 0.45))
        f = kondensiert(max(10, int(70 * p)))
        d.text((530, y0 + 150 * len(zeilen) + 40), ohne_emoji(folie["frage"]).upper(), font=f, fill=SONNE,
               anchor="mm")


def credit_ebene(text: str | None) -> Image.Image | None:
    if not text:
        return None
    img = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = text_schrift(24)
    zeile = umbrechen(ohne_emoji(text), f, TEXT_BREITE, 1)[0]
    d.text((RAND_X, 1540), zeile, font=f, fill=(255, 255, 255, 150))
    return img


# ---------------------------------------------------------------- Zeitplan

def folien_dauer(f: dict) -> float:
    if f.get("typ") == "logo" and f.get("blitz"):
        return DAUER_BLITZ
    if f.get("typ") == "jahr":
        return DAUER_JAHR if f.get("aktiv") is not None else DAUER_TOP_UEBERSICHT + 0.6
    if f.get("typ") in ("balken", "duell"):
        return float(f.get("dauer") or 6.0)
    if f.get("typ") == "top":
        return DAUER_TOP_UEBERSICHT if f.get("aktiv") is None else float(f.get("dauer") or DAUER["top"])
    if f.get("typ") == "event" and f.get("schnell"):
        return DAUER_SCHNELL
    if f.get("pointe"):
        return DAUER_POINTE
    return DAUER.get(f.get("typ"), 4.0)


def zeitplan(folien: list[dict], gesamt: float | None = None,
             schlag: float | None = None) -> list[tuple[float, float, dict]]:
    """[(start, ende, folie)] - bei `gesamt` (Clip-Länge) gestreckt, bei
    `schlag` (Sekunden je Schlag des Beats) auf ganze Schläge gerundet,
    damit jeder Schnitt auf einem Schlag liegt."""
    dauern = [folien_dauer(f) for f in folien]
    if gesamt:
        faktor = gesamt / sum(dauern)
        dauern = [d * faktor for d in dauern]
    elif schlag:
        dauern = [max(1 if f.get("typ") == "logo" or f.get("blitz") else 2, round(d / schlag)) * schlag
                  for f, d in zip(folien, dauern)]
    plan, t = [], 0.0
    for f, d in zip(folien, dauern):
        plan.append((t, t + d, f))
        t += d
    return plan


def sichtbarkeit(t: float, start: float, ende: float, letzte: bool, hart: bool = False) -> tuple[float, int]:
    """(Deckung 0…1, Versatz in px) einer Folie zur Zeit t: einblenden
    mit kleinem Hub von unten, ausblenden - die letzte bleibt stehen. Die
    ERSTE Folie (Start bei 0) steht sofort: Wer in der ersten Sekunde nur
    Hintergrund sieht, wischt weiter. `hart`: harter Schnitt ohne Blende
    (Logo-Folien im Takt)."""
    if t < start or t >= ende:
        return 0.0, 0
    if hart:
        return 1.0, 0
    ein = 1.0 if start <= 0 else min(1.0, (t - start) / EIN)
    aus = 1.0 if letzte else min(1.0, (ende - t) / AUS)
    glatt = 1 - (1 - ein) ** 3
    return max(0.0, min(ein, aus)), int(46 * (1 - glatt))


def _ist_blitz(plan: list[tuple[float, float, dict]], schnitt: float) -> bool:
    """Schnitte zwischen Blitz-Logos (Format „monat") bekommen keinen Wisch –
    die Logos wechseln im Takt hart, das ist dort der Effekt."""
    for s, _, f in plan:
        if abs(s - schnitt) < 1e-6:
            return bool(f.get("blitz"))
    return False


def punch(bild: Image.Image, t: float, plan: list[tuple[float, float, dict]]) -> Image.Image:
    """Kurzer Zoom des Hintergrunds nach jedem Schnitt (nicht beim ersten)."""
    for start, _, _ in plan[1:]:
        dt_ = t - start
        if 0 <= dt_ < PUNCH_S:
            z = 1 + PUNCH * (1 - dt_ / PUNCH_S) ** 2
            bw, bh = B / z, H / z
            return bild.resize((B, H), Image.BILINEAR, box=((B - bw) / 2, (H - bh) / 2, (B + bw) / 2, (H + bh) / 2))
    return bild


# ---------------------------------------------------------------- Hintergründe

def _ffmpeg(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          check=True, **kw)


def dauer_von(pfad: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(pfad)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip() or 0)


def hat_ton(pfad: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", str(pfad)], capture_output=True, text=True)
    return bool(out.stdout.strip())


def foto_pool(sport: str | None) -> list[tuple[Path, str | None]]:
    """Alle Fotos, die für eine Sportart in Frage kommen: die Sammlung in
    marketing/instagram/hintergruende/ (hintergruende.json, je Bild Sportart,
    Urheber, Lizenz, Quelle) plus das Foto der Startseite. Ohne Sportart
    (Formate über alle Sportarten) die ganze Sammlung."""
    pool: list[tuple[Path, str | None]] = []
    try:
        liste = json.loads((HINTERGRUENDE / "hintergruende.json").read_text(encoding="utf-8"))["fotos"]
    except (OSError, ValueError, KeyError):
        liste = []
    for f in liste:
        if sport is None or f.get("sport") == sport:
            pool.append((HINTERGRUENDE / f["datei"], f"{f['urheber']}, {f['lizenz']}, Wikimedia Commons"))
    datei, credit = FOTOS.get(sport) or FOTOS[None]
    pool.append((WURZEL / "bilder" / datei, credit))
    return [(p, c) for p, c in pool if p.exists()]


def foto_wahl(sport: str | None, seed: int) -> tuple[Path, str | None]:
    """Ein Foto aus dem Pool. Die Reihenfolge ist je Sportart einmal fest
    gemischt, der Seed (Tag als Ordinalzahl) läuft sie ab: Zwei aufeinander
    folgende Tage bekommen nie dasselbe Bild, und erst nach einem ganzen
    Durchgang kommt eines wieder. Vorher war es je Sportart immer DASSELBE
    Foto (vom Nutzer am 17.10.2026 bemerkt) - ohne Pexels-Schlüssel die
    Regel, nicht die Ausnahme."""
    pool = sorted(foto_pool(sport), key=lambda x: x[0].name)
    random.Random(f"pool-{sport}").shuffle(pool)
    return pool[seed % len(pool)]


def farbgrad(bild: Image.Image, sport: str | None = None) -> Image.Image:
    """Ein eigener Look statt Handyfoto: mehr Kontrast, weniger Sättigung,
    Schatten in Navy, Lichter warm (leichter Duoton), getönt mit der
    Sportfarbe – jedes Reel sieht nach derselben Marke aus."""
    bild = ImageEnhance.Contrast(bild).enhance(1.14)
    bild = ImageEnhance.Color(bild).enhance(0.78)
    akzent = SPORTFARBE.get(sport, SIGNAL)
    hell = tuple(int(0.82 * 246 + 0.18 * c) for c in akzent)
    duo = ImageOps.colorize(ImageOps.grayscale(bild), black=(6, 14, 30), white=hell, mid=(96, 110, 132))
    return Image.blend(bild, duo, 0.30)


def foto_frames(sport: str | None, dauer: float, seed: int):
    """Langsamer Zoom (Ken Burns) über ein Foto aus dem Pool (foto_wahl).
    Ausschnitt, Richtung und Zoom wechseln mit dem Seed, damit auch
    dasselbe Foto nicht zweimal gleich aussieht."""
    pfad, _ = foto_wahl(sport, seed)
    bild = Image.open(pfad).convert("RGB")
    rng = random.Random(seed * 7919 + 1)
    # Auf 9:16 zuschneiden - die Lage des Ausschnitts wechselt -, dann
    # groß genug für den Zoom.
    w, h = bild.size
    if w / h > 9 / 16:
        ziel_w = int(h * 9 / 16)
        links = int((w - ziel_w) * rng.uniform(0.2, 0.8))
        bild = bild.crop((links, 0, links + ziel_w, h))
    else:
        ziel_h = int(w * 16 / 9)
        oben = int((h - ziel_h) * rng.uniform(0.2, 0.8))
        bild = bild.crop((0, oben, w, oben + ziel_h))
    bild = bild.resize((1188, 2112), Image.LANCZOS)
    if rng.random() < 0.5:
        bild = bild.transpose(Image.FLIP_LEFT_RIGHT)
    bild = farbgrad(bild.filter(ImageFilter.GaussianBlur(2.6)), sport)   # Tiefenschärfe: die Grafik ist vorn
    richtung = rng.choice([-1, 1])
    hinein = rng.random() < 0.65
    senkrecht = rng.random() < 0.4
    n = int(dauer * FPS)
    for i in range(n):
        p = i / max(1, n - 1)
        zoom = 1.0 + 0.10 * (p if hinein else 1 - p)
        cw, ch = 1188 / zoom, 2112 / zoom
        cx = 594 + (0 if senkrecht else richtung * 40 * p)
        cy = 1056 + (richtung * 70 * p if senkrecht else 0)
        cx = min(max(cx, cw / 2), 1188 - cw / 2)
        cy = min(max(cy, ch / 2), 2112 - ch / 2)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        yield bild.resize((B, H), Image.BILINEAR, box=box)


def video_frames(pfad: Path, dauer: float, start: float = 0.0, fuellen: str = "crop"):
    """Bilder eines Videos, auf 1080 × 1920 gebracht. `fuellen`: crop
    (Mitte ausschneiden) oder blur (ganzes Bild über unscharfem Hintergrund
    - für Querformat-Clips, bei denen der Schnitt zu viel wegnähme)."""
    if fuellen == "blur":
        vf = (f"[0:v]fps={FPS},split[a][b];[a]scale={B}:{H}:force_original_aspect_ratio=increase,"
              f"crop={B}:{H},boxblur=28:2,eq=brightness=-0.08[bg];"
              f"[b]scale={B}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-80,format=rgb24")
        filt = ["-filter_complex", vf]
    else:
        filt = ["-vf", f"fps={FPS},scale={B}:{H}:force_original_aspect_ratio=increase,crop={B}:{H},format=rgb24"]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{start:.2f}",
           "-i", str(pfad), "-t", f"{dauer:.2f}", *filt, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    groesse = B * H * 3
    letztes = None
    n = int(dauer * FPS)
    try:
        for _ in range(n):
            roh = proc.stdout.read(groesse)
            if len(roh) < groesse:
                break
            letztes = Image.frombytes("RGB", (B, H), roh)
            yield letztes
        else:
            return
        # Video zu kurz (sollte durch -stream_loop nicht passieren):
        # letztes Bild stehen lassen.
        while letztes is not None and n > 0:
            n -= 1
            yield letztes
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


def pexels_video(sport: str | None, seed: int, cache: Path = CACHE) -> tuple[Path, str] | None:
    """Ein Hochformat-Video von Pexels (Lizenz: frei, auch kommerziell,
    Namensnennung freiwillig - wir nennen sie trotzdem). None ohne Schlüssel
    oder bei jedem Fehler - dann gilt das Foto."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        import requests
        rng = random.Random(seed)
        suche = rng.choice(PEXELS_SUCHE.get(sport) or PEXELS_SUCHE[None])
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                         params={"query": suche, "orientation": "portrait", "size": "medium", "per_page": 20},
                         timeout=30)
        r.raise_for_status()
        videos = [v for v in r.json().get("videos", []) if 6 <= v.get("duration", 0) <= 60]
        if not videos:
            return None
        v = videos[rng.randrange(len(videos))]
        dateien = [f for f in v.get("video_files", [])
                   if f.get("height") and f.get("width") and f["height"] >= 1280 and f["height"] > f["width"]]
        if not dateien:
            return None
        datei = min(dateien, key=lambda f: abs(f["height"] - 1920))
        cache.mkdir(parents=True, exist_ok=True)
        ziel = cache / f"pexels-{v['id']}-{datei['height']}.mp4"
        if not ziel.exists():
            with requests.get(datei["link"], stream=True, timeout=120) as dl:
                dl.raise_for_status()
                with open(ziel, "wb") as fh:
                    for block in dl.iter_content(1 << 20):
                        fh.write(block)
        name = (v.get("user") or {}).get("name") or "Pexels"
        return ziel, f"Video: {name} / Pexels"
    except Exception as e:                                   # noqa: BLE001
        print(f"  Pexels nicht erreichbar ({e}) - Foto als Hintergrund")
        return None


# ---------------------------------------------------------------- Clips

def pruefe_lizenz(clip: dict) -> None:
    lizenz = (clip.get("lizenz") or "").strip()
    if not lizenz or not (clip.get("urheber") or "").strip():
        raise LizenzFehler(f"Clip {clip.get('id')}: lizenz und urheber sind Pflicht")
    if not ERLAUBTE_LIZENZEN.match(lizenz):
        raise LizenzFehler(f"Clip {clip.get('id')}: Lizenz „{lizenz}“ ist nicht freigegeben "
                           "(CC0, CC BY, CC BY-SA, Pexels, Pixabay, eigenes Material, Genehmigung …)")
    if re.search(r"\bnc\b|non-?commercial|\bnd\b|no-?deriv", lizenz, re.I):
        raise LizenzFehler(f"Clip {clip.get('id')}: NC/ND-Lizenzen erlauben kein Reel")


def lade_clip(clip: dict, cache: Path = CACHE) -> Path:
    pruefe_lizenz(clip)
    quelle = clip.get("datei") or clip.get("url")
    if not quelle:
        raise ValueError(f"Clip {clip.get('id')}: weder datei noch url")
    if not re.match(r"https?://", quelle):
        pfad = (MARKETING / quelle) if not os.path.isabs(quelle) else Path(quelle)
        if not pfad.exists():
            raise FileNotFoundError(pfad)
        return pfad
    import requests
    cache.mkdir(parents=True, exist_ok=True)
    endung = os.path.splitext(quelle.split("?")[0])[1] or ".mp4"
    ziel = cache / f"clip-{re.sub(r'[^a-z0-9-]', '', clip['id'].lower())}{endung}"
    if not ziel.exists():
        with requests.get(quelle, stream=True, timeout=180,
                          headers={"User-Agent": "AusdauerMaschine/1.0 (+https://endurance-events.de)"}) as dl:
            dl.raise_for_status()
            with open(ziel, "wb") as fh:
                for block in dl.iter_content(1 << 20):
                    fh.write(block)
    return ziel


def _lautheit_je_sekunde(pfad: Path) -> list[float]:
    """Lautheit je Sekunde (RMS in dB) - der Ton als 8-kHz-Mono-PCM aus
    ffmpeg, gerechnet ohne numpy (läuft auf jedem Actions-Runner)."""
    if not hat_ton(pfad):
        return []
    from array import array
    erg = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(pfad), "-vn",
                          "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    proben = array("h")
    proben.frombytes(erg.stdout[: len(erg.stdout) // 2 * 2])
    werte = []
    for i in range(0, len(proben), 8000):
        stueck = proben[i:i + 8000]
        if not stueck:
            break
        rms = math.sqrt(sum(x * x for x in stueck) / len(stueck))
        werte.append(20 * math.log10(max(rms, 1.0) / 32768))
    return werte


def _schnitte_je_sekunde(pfad: Path) -> dict[int, float]:
    """Bildwechsel je Sekunde (scdet-Wert aufsummiert) - viel Bewegung
    oder ein Schnitt heißt: hier passiert etwas."""
    erg = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad), "-an",
                          "-vf", "scale=320:-2,scdet=threshold=100,metadata=print", "-f", "null", "-"],
                         capture_output=True, text=True)
    schnitte: dict[int, float] = {}
    zeit = 0.0
    for zeile in erg.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", zeile)
        if m:
            zeit = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scd\.score=([\d.]+)", zeile)
        if m:
            sek = int(zeit)
            schnitte[sek] = schnitte.get(sek, 0) + float(m.group(1))
    return schnitte


def highlight(pfad: Path, laenge: float) -> float:
    """Start (s) des spannendsten Fensters von `laenge` Sekunden:
    Lautheit (Jubel, Zieleinlauf) zählt doppelt, Schnitte/Bewegung einfach.
    Die ersten und letzten 1,5 s eines Clips (Abblenden, Logos) fallen weg."""
    gesamt = dauer_von(pfad)
    if gesamt <= laenge + 1:
        return 0.0
    laut = _lautheit_je_sekunde(pfad)
    schnitte = _schnitte_je_sekunde(pfad)
    n = int(gesamt)
    if laut:
        lo, hi = min(laut), max(laut)
        laut_n = [(v - lo) / (hi - lo) if hi > lo else 0 for v in laut] + [0] * max(0, n - len(laut))
    else:
        laut_n = [0.0] * n
    s_max = max(schnitte.values(), default=0) or 1
    wert = [2 * laut_n[i] + min(1.0, schnitte.get(i, 0) / s_max) for i in range(n)]
    fenster = max(1, int(round(laenge)))
    best, best_start = -1.0, 1.5
    erster = 1
    letzter = max(erster, int(gesamt - laenge - 1.5))
    for s in range(erster, letzter + 1):
        summe = sum(wert[s:s + fenster])
        if summe > best:
            best, best_start = summe, float(s)
    return best_start


# ---------------------------------------------------------------- Musik

def musik_wahl(seed: int) -> Path | None:
    """Ein Stück aus marketing/instagram/musik/ - nur, wenn es in
    musik.json mit Lizenz steht (gleiche Regel wie bei Clips)."""
    liste = MUSIK / "musik.json"
    if not liste.exists():
        return None
    try:
        stuecke = [s for s in json.loads(liste.read_text(encoding="utf-8")).get("stuecke", [])
                   if s.get("lizenz") and (MUSIK / s.get("datei", "")).is_file()]
    except (ValueError, OSError):
        return None
    if not stuecke:
        return None
    return MUSIK / random.Random(seed).choice(stuecke)["datei"]


# ---------------------------------------------------------------- Rendern

# ---------------------------------------------------------------- Motion
#
# Seit dem 27.10.2026 (vom Nutzer: „Die Videos sollen nicht so billig
# aussehen … Steck gerne noch viele tokens in die Bearbeitung"). Eine
# Schicht über ALLEN Folientypen, statt jeden Typ einzeln zu animieren:
#
#   Schatten   weicher Schlagschatten unter jedem Text und jeder Karte
#              (aus dem Alphakanal der Folie)
#   Staffel    die Folie wird in waagerechte Bänder zerlegt (Zeilen,
#              Karten – dort, wo der Alphakanal zeilenweise etwas trägt);
#              jedes Band kommt nacheinander von unten mit leichtem
#              Überschwingen, große Bänder (Karten, Logos) mit „Pop"
#   Abgang     die alte Folie gleitet in den letzten Zehnteln nach oben weg
#   Wisch      bei jedem Schnitt fährt ein schräges Band in der Akzentfarbe
#              durchs Bild
#   Look       Filmkorn (vier Rauschbilder im Wechsel), ein langsam
#              wandernder warmer Lichtschimmer; der Farbgrad sitzt im Foto
#              (farbgrad), die Vignette im Rahmen
#
# Zählt eine Folie hoch (Hook mit Zahl), zeichnet sie sich in den ersten
# Zehnteln Bild für Bild neu (ZAEHLEN).

STAFFEL = 0.075            # Sekunden zwischen zwei Bändern
BAND_DAUER = 0.42          # so lange braucht ein Band
ABGANG = 0.16              # Abgang der alten Folie
WISCH = 0.34               # Dauer des Wischs
ZAEHLEN = 0.75             # Hochzählen der großen Zahl


def _ease_aus(p: float) -> float:
    return 1 - (1 - p) ** 3


def _ease_back(p: float, s: float = 1.6) -> float:
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def mit_schatten(fb: Image.Image) -> Image.Image:
    """Weicher Schatten unter allem, was die Folie zeichnet."""
    a = fb.getchannel("A")
    if not a.getbbox():
        return fb
    weich = a.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.62))
    schatten = Image.new("RGBA", fb.size, (2, 8, 20, 0))
    schatten.putalpha(weich)
    unten = Image.new("RGBA", fb.size, (0, 0, 0, 0))
    unten.alpha_composite(schatten, (0, 8))
    return Image.alpha_composite(unten, fb)


def baender(fb: Image.Image, luecke: int = 18) -> list[tuple[int, int]]:
    """Waagerechte Bänder mit Inhalt: (y0, y1), von oben nach unten."""
    zeilen = fb.getchannel("A").resize((1, H), Image.BOX)
    werte = list(zeilen.getdata())
    aus, start, leer = [], None, 0
    for y, v in enumerate(werte):
        if v > 2:
            if start is None:
                start = y
            leer = 0
        elif start is not None:
            leer += 1
            if leer > luecke:
                aus.append((start, y - leer + 1))
                start, leer = None, 0
    if start is not None:
        aus.append((start, H))
    return [(max(0, a - 6), min(H, b + 14)) for a, b in aus if b - a > 3]


def gestaffelt(fb: Image.Image, bands: list[tuple[int, int]], u: float, schnell: bool = False) -> Image.Image:
    """Die Folie zur Zeit u (Sekunden seit ihrem Beginn): Band für Band."""
    staffel = 0.0 if schnell else STAFFEL
    dauer = 0.16 if schnell else BAND_DAUER
    if u >= dauer + staffel * max(0, len(bands) - 1):
        return fb
    aus = Image.new("RGBA", fb.size, (0, 0, 0, 0))
    for i, (y0, y1) in enumerate(bands):
        p = (u - i * staffel) / dauer
        if p <= 0:
            continue
        if p >= 1:
            aus.alpha_composite(fb.crop((0, y0, B, y1)), (0, y0))
            continue
        e = _ease_back(p)
        stueck = fb.crop((0, y0, B, y1))
        hoehe = y1 - y0
        if hoehe > 200:                                    # Karte/Logo: Pop
            f = 0.90 + 0.10 * e
            w2, h2 = max(1, int(B * f)), max(1, int(hoehe * f))
            stueck = stueck.resize((w2, h2), Image.BILINEAR)
            x, y = (B - w2) // 2, y0 + (hoehe - h2) // 2
        else:                                              # Zeile: von unten
            x, y = 0, y0 + int((1 - e) * 46)
        alpha = _ease_aus(min(1.0, p * 1.4))
        if alpha < 1:
            stueck.putalpha(stueck.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        if 0 <= y < H:
            aus.alpha_composite(stueck, (max(0, x), y), (max(0, -x), 0))
    return aus


def abgang(fb: Image.Image, rest: float) -> Image.Image:
    """Die letzten Zehntel einer Folie: nach oben weg und ausblenden."""
    p = 1 - max(0.0, rest) / ABGANG
    if p <= 0:
        return fb
    dy = int(_ease_aus(p) * 60)
    aus = Image.new("RGBA", fb.size, (0, 0, 0, 0))
    aus.alpha_composite(fb.crop((0, dy, B, H)), (0, 0))
    aus.putalpha(aus.getchannel("A").point(lambda v, a=1 - p: int(v * a)))
    return aus


def wisch(bild: Image.Image, t: float, schnitte: list[float], farbe) -> None:
    """Ein schräges Band in der Akzentfarbe fährt bei jedem Schnitt durchs
    Bild (von links unten nach rechts oben), dahinter ein dünnes helles."""
    for c in schnitte:
        p = (t - (c - WISCH / 2)) / WISCH
        if not 0 <= p <= 1:
            continue
        e = p * p * (3 - 2 * p)
        x = -700 + e * (B + 1400)
        d = ImageDraw.Draw(bild)
        for versatz, breite_b, f in ((0, 230, farbe + (235,)), (-120, 36, (255, 255, 255, 120))):
            x0 = x + versatz
            d.polygon([(x0, H), (x0 + breite_b, H), (x0 + breite_b + 520, 0), (x0 + 520, 0)], fill=f)


_korn: list[Image.Image] = []
_schimmer: Image.Image | None = None


def korn(i: int) -> Image.Image:
    """Filmkorn: vier Rauschbilder, alle zwei Bilder ein anderes."""
    if not _korn:
        for k in range(4):
            r = Image.effect_noise((B // 2, H // 2), 48).resize((B, H), Image.NEAREST)
            hell = r.point(lambda v: max(0, v - 150) // 3)
            ebene = Image.new("RGBA", (B, H), (255, 255, 255, 0))
            ebene.putalpha(hell)
            dunkel = r.point(lambda v: max(0, 106 - v) // 3)
            d2 = Image.new("RGBA", (B, H), (0, 0, 0, 0))
            d2.putalpha(dunkel)
            _korn.append(Image.alpha_composite(ebene, d2))
    return _korn[(i // 2) % len(_korn)]


def schimmer(bild: Image.Image, t: float, gesamt: float, seed: int) -> None:
    """Ein großer, weicher, warmer Lichtfleck, der langsam übers Bild
    wandert (Lichteinfall statt flacher Fläche)."""
    global _schimmer
    if _schimmer is None:
        g = Image.radial_gradient("L").resize((1500, 1500), Image.BILINEAR)
        maske = g.point(lambda v: int(max(0, 200 - v) * 0.30))
        _schimmer = Image.new("RGBA", (1500, 1500), SONNE + (0,))
        _schimmer.putalpha(maske)
    rng = random.Random(seed)
    sx, sy = rng.uniform(-400, 300), rng.uniform(-500, 400)
    p = t / max(1.0, gesamt)
    x = int(sx + p * rng.choice((-1, 1)) * 380 - 750 + B / 2)
    y = int(sy + p * 520 - 750 + H / 3)
    links, oben = max(0, x), max(0, y)
    q = (links - x, oben - y, min(1500, B - x), min(1500, H - y))
    if q[2] > q[0] and q[3] > q[1]:
        bild.alpha_composite(_schimmer, (links, oben), q)


def rendere(beitrag: dict, ausgabe: Path, seed: int | None = None) -> dict:
    """Schreibt reel.mp4 und cover.jpg nach `ausgabe` und gibt die
    Metadaten zurück (Dauer, Hintergrund, Nachweis)."""
    ausgabe.mkdir(parents=True, exist_ok=True)
    seed = seed if seed is not None else int(str(beitrag.get("datum", "0")).replace("-", "") or 0)
    sport = beitrag.get("sport")
    folien = beitrag["folien"]
    ton: Path | None = None
    ton_start = 0.0
    nachweis = None
    beat_bpm: int | None = None

    if beitrag["format"] == "clip":
        clip = beitrag["clip"]
        pfad = lade_clip(clip)
        laenge = float(clip.get("dauer") or 14)
        laenge = min(laenge, max(3.0, dauer_von(pfad) - 0.2))
        start = float(clip["start"]) if clip.get("start") is not None else highlight(pfad, laenge)
        plan = zeitplan(folien, laenge)
        gesamt = laenge
        hochkant = False
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                  "stream=width,height", "-of", "csv=p=0", str(pfad)],
                                 capture_output=True, text=True, check=True).stdout.strip().split(",")
            hochkant = int(out[1]) > int(out[0])
        except Exception:                                    # noqa: BLE001
            pass
        frames = video_frames(pfad, gesamt, start, "crop" if hochkant else clip.get("fuellen", "blur"))
        if hat_ton(pfad) and clip.get("ton", True):
            ton, ton_start = pfad, start
        nachweis = f"Video: {clip['urheber']} · {clip['lizenz']}"
        hintergrund = {"art": "clip", "id": clip["id"], "start": start}
    else:
        ton = musik_wahl(seed)
        if ton is None:
            import insta_musik
            beat_bpm = insta_musik.bpm_fuer(seed)
            plan = zeitplan(folien, schlag=insta_musik.schlag_s(beat_bpm))
        else:
            plan = zeitplan(folien)
        gesamt = plan[-1][1]
        # Formate über mehrere Sportarten (laengste: Lauf + Rad) wählen das
        # Foto über `foto_sport` - sonst kam auch ein Schwimmfoto in Frage.
        foto_sport = beitrag.get("foto_sport") or sport
        pex = pexels_video(foto_sport, seed)
        if pex:
            frames = video_frames(pex[0], gesamt, 0.0, "crop")
            nachweis = pex[1]
            hintergrund = {"art": "pexels", "datei": pex[0].name}
        else:
            pfad, credit = foto_wahl(foto_sport, seed)
            frames = foto_frames(foto_sport, gesamt, seed)
            nachweis = f"Foto: {credit}" if credit else None
            hintergrund = {"art": "foto", "datei": pfad.name}

    schwarzweiss = beitrag.get("stil") == "sw"
    rahmen = rahmen_ebene()
    credit = credit_ebene(nachweis)
    if credit:
        rahmen = Image.alpha_composite(rahmen, credit)
    # Korn liegt auf dem Hintergrund, unter der Schrift (die bleibt
    # gestochen scharf) - vier fertige Ebenen Rahmen + Korn.
    rahmen_korn = [Image.alpha_composite(korn(2 * k), rahmen) for k in range(4)]
    folien_bilder = [mit_schatten(folie_bild(f, sport)) for _, _, f in plan]
    folien_baender = [baender(fb) for fb in folien_bilder]
    schnitte = [s for s, _, _ in plan[1:]]
    akzent = SPORTFARBE.get(sport, SIGNAL) if sport else SIGNAL
    n_frames = int(round(gesamt * FPS))

    with tempfile.TemporaryDirectory() as tmp:
        stumm = Path(tmp) / "bild.mp4"
        enc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{B}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
             "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
             "-maxrate", "12M", "-bufsize", "24M", "-g", str(FPS * 2), str(stumm)],
            stdin=subprocess.PIPE)
        cover = None
        # Das Titelbild: wenn die erste Folie ganz steht
        cover_zeit = max(0.0, min(plan[0][1] - 0.2, 1.3))
        try:
            for i, bg in enumerate(frames):
                if i >= n_frames:
                    break
                t = i / FPS
                bild = Image.alpha_composite(punch(bg, t, plan).convert("RGBA"), rahmen_korn[(i // 2) % 4])
                schimmer(bild, t, gesamt, seed)
                for k, (s, e, f) in enumerate(plan):
                    letzte = k == len(plan) - 1
                    if t < s or (t >= e and not letzte):
                        continue
                    u = t - s
                    # die erste Folie steht ab dem ersten Bild schon fast ganz
                    if k == 0:
                        u += 0.32
                    fb = folien_bilder[k]
                    if f.get("typ") in ANIMIERT:
                        fb = mit_schatten(folie_bild(f, sport, min(1.0, (t - s) / max(0.01, e - s))))
                    elif f.get("typ") == "hook" and str(f.get("zahl", "")).strip() and u < ZAEHLEN:
                        fb = mit_schatten(folie_bild(f, sport, u / ZAEHLEN))
                    else:
                        fb = gestaffelt(fb, folien_baender[k], u, schnell=f.get("typ") == "logo" or f.get("blitz"))
                    if not letzte and e - t < ABGANG and f.get("typ") != "logo" and not f.get("blitz"):
                        fb = abgang(fb, e - t)
                    bild.alpha_composite(fb)
                wisch(bild, t, [c for c in schnitte if not _ist_blitz(plan, c)], akzent)
                # Fortschritt: dünn, mit leuchtendem Kopf
                d = ImageDraw.Draw(bild)
                d.rectangle([RAND_X, 1592, RAND_X + TEXT_BREITE, 1595], fill=(255, 255, 255, 55))
                xe = RAND_X + int(TEXT_BREITE * (t / gesamt))
                d.rectangle([RAND_X, 1591, xe, 1596], fill=akzent)
                d.ellipse([xe - 7, 1586, xe + 7, 1600], fill=WEISS)
                rgb = bild.convert("RGB")
                if schwarzweiss:
                    rgb = rgb.convert("L").convert("RGB")
                if cover is None and t >= cover_zeit:
                    cover = rgb.copy()
                enc.stdin.write(rgb.tobytes())
        finally:
            enc.stdin.close()
            enc.wait()
        if enc.returncode != 0:
            raise RuntimeError("ffmpeg (Bild) fehlgeschlagen")

        reel = ausgabe / "reel.mp4"
        if beat_bpm:
            import insta_musik
            ton = Path(tmp) / "beat.wav"
            wische = [c for c in schnitte if not _ist_blitz(plan, c)]
            insta_musik.schreibe_wav(ton, gesamt + 0.3, seed, beat_bpm, wische, plan[-1][0])
        if ton:
            audio = ["-ss", f"{ton_start:.2f}", "-i", str(ton)]
            af = f"afade=t=in:d=0.3,afade=t=out:st={max(0.0, gesamt - 1.2):.2f}:d=1.2"
        else:
            audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            af = "anull"
        _ffmpeg("-i", str(stumm), *audio, "-map", "0:v", "-map", "1:a", "-af", af,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
                "-t", f"{gesamt:.2f}", "-movflags", "+faststart", str(reel))
    (cover or Image.new("RGB", (B, H), NAVY)).save(ausgabe / "cover.jpg", quality=90)
    if beat_bpm:
        musik = f"eigener Beat {beat_bpm} BPM"
    else:
        musik = ton.name if ton and beitrag["format"] != "clip" else None
    return {"dauer_s": round(gesamt, 2), "thumb_offset_ms": int(cover_zeit * 1000),
            "hintergrund": hintergrund, "nachweis": nachweis, "musik": musik}


def rendere_story(story: dict, ziel: Path, seed: int) -> Path:
    """Eine Story als Bild (1080 × 1920 JPEG): Foto der Sportart, Verlauf,
    Marke tiefer als im Reel (oben liegt die Kopfzeile der App), darauf
    die eine Folie. Bilder statt Videos: Stories laufen nur 24 Stunden,
    und ein Bild verarbeitet Instagram sofort."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    sport = story.get("sport")
    bg = next(foto_frames(sport, 1.0, seed)).convert("RGBA")
    rahmen = rahmen_ebene(logo_y=250)
    _, credit = foto_wahl(sport, seed)
    ebene = credit_ebene(f"Foto: {credit}" if credit else None)
    if ebene:
        rahmen = Image.alpha_composite(rahmen, ebene)
    bild = Image.alpha_composite(Image.alpha_composite(bg, rahmen), mit_schatten(folie_bild(story["folie"], sport)))
    bild.convert("RGB").save(ziel, quality=90)
    return ziel


def vorschau(beitrag: dict, ausgabe: Path) -> list[Path]:
    """Jede Folie als PNG über dem Foto-Hintergrund - schnell, ohne Video."""
    ausgabe.mkdir(parents=True, exist_ok=True)
    rahmen = rahmen_ebene()
    bg = next(foto_frames(beitrag.get("sport"), 1.0, 1)).convert("RGBA")
    pfade = []
    for i, f in enumerate(beitrag["folien"], 1):
        bild = Image.alpha_composite(Image.alpha_composite(bg, rahmen), mit_schatten(folie_bild(f, beitrag.get("sport"))))
        p = ausgabe / f"folie-{i}.png"
        bild = bild.convert("RGB")
        if beitrag.get("stil") == "sw":
            bild = bild.convert("L").convert("RGB")
        bild.save(p)
        pfade.append(p)
    return pfade


def ffmpeg_vorhanden() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
