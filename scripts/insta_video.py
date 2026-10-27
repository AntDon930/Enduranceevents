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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
         "logo": 1.0}
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


def rahmen_ebene(logo_y: int = 128) -> Image.Image:
    """Was auf jedem Bild gleich ist: Verlauf oben/unten, Marke. Bei
    Stories sitzt die Marke tiefer (oben liegt die Kopfzeile der App)."""
    ebene = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    verlauf = Image.new("L", (1, H))
    for y in range(H):
        oben = max(0.0, 1 - y / 520) * 0.85
        unten = max(0.0, (y - 1050) / 870) * 0.92
        mitte = 0.48
        verlauf.putpixel((0, y), int(255 * min(1.0, max(oben, unten, mitte))))
    alpha = verlauf.resize((B, H))
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


def folie_bild(folie: dict, sport: str | None) -> Image.Image:
    """Eine Texttafel als transparentes Bild (1080 × 1920)."""
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
            d.text((RAND_X - 8, y), zahl, font=kondensiert(g), fill=SONNE)
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


def _logo_folie(img: Image.Image, d: ImageDraw.ImageDraw, folie: dict) -> None:
    """Ein Event als Logo (Formate „monat" und „anmeldung", insta_inhalte):
    das Logo groß auf einer Karte - weiß, bei hellen Logos Navy -, darunter
    Datum, Name und Ort. Liegt kein Logo im Cache (insta_logos.py), steht
    der Name groß auf der Karte."""
    import insta_logos
    x0, y0, x1, y1 = KARTE
    y = y0 - 110
    if folie.get("ueber"):
        pille(d, RAND_X + 20, y, ohne_emoji(folie["ueber"]).upper(), kondensiert(46, False), SIGNAL)
    logo = insta_logos.logo_bild(folie["logo_id"]) if folie.get("logo_id") else None
    hell = bool(logo and logo[1])
    d.rounded_rectangle(KARTE, radius=44, fill=NAVY if hell else WEISS)
    if logo:
        bild = logo[0]
        rand = 70
        f = min((x1 - x0 - 2 * rand) / bild.width, (y1 - y0 - 2 * rand) / bild.height, 3.0)
        bild = bild.resize((max(1, int(bild.width * f)), max(1, int(bild.height * f))), Image.LANCZOS)
        img.alpha_composite(bild, ((x0 + x1 - bild.width) // 2, (y0 + y1 - bild.height) // 2))
        name_unten = True
    else:
        name = ohne_emoji(folie.get("name", "")).upper()
        g = 120
        zeilen = umbrechen(name, kondensiert(g), x1 - x0 - 100, 3)
        while g > 60 and (zeilen[-1].endswith("…") or len(zeilen) * g * 0.98 > y1 - y0 - 80):
            g -= 6
            zeilen = umbrechen(name, kondensiert(g), x1 - x0 - 100, 3)
        ty = (y0 + y1) / 2 - len(zeilen) * g * 0.98 / 2
        for z in zeilen:
            d.text(((x0 + x1) / 2, ty), z, font=kondensiert(g), fill=NAVY, anchor="ma")
            ty += g * 0.98
        name_unten = False
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
        dauern = [max(1 if f.get("typ") == "logo" else 2, round(d / schlag)) * schlag
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


def punch(bild: Image.Image, t: float, plan: list[tuple[float, float, dict]]) -> Image.Image:
    """Kurzer Zoom des Hintergrunds nach jedem Schnitt (nicht beim ersten)."""
    for start, _, _ in plan[1:]:
        dt_ = t - start
        if 0 <= dt_ < PUNCH_S:
            z = 1 + PUNCH * (1 - dt_ / PUNCH_S) ** 2
            w, h = int(B * z), int(H * z)
            return bild.resize((w, h), Image.BILINEAR).crop(((w - B) // 2, (h - H) // 2, (w - B) // 2 + B, (h - H) // 2 + H))
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
    bild = bild.filter(ImageFilter.GaussianBlur(1.2))
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
        pex = pexels_video(sport, seed)
        if pex:
            frames = video_frames(pex[0], gesamt, 0.0, "crop")
            nachweis = pex[1]
            hintergrund = {"art": "pexels", "datei": pex[0].name}
        else:
            pfad, credit = foto_wahl(sport, seed)
            frames = foto_frames(sport, gesamt, seed)
            nachweis = f"Foto: {credit}" if credit else None
            hintergrund = {"art": "foto", "datei": pfad.name}

    schwarzweiss = beitrag.get("stil") == "sw"
    rahmen = rahmen_ebene()
    credit = credit_ebene(nachweis)
    if credit:
        rahmen = Image.alpha_composite(rahmen, credit)
    folien_bilder = [folie_bild(f, sport) for _, _, f in plan]
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
        cover_zeit = max(0.0, min(plan[0][1] - 0.3, 1.2))
        try:
            for i, bg in enumerate(frames):
                if i >= n_frames:
                    break
                t = i / FPS
                bild = Image.alpha_composite(punch(bg, t, plan).convert("RGBA"), rahmen)
                for k, (s, e, f) in enumerate(plan):
                    a, versatz = sichtbarkeit(t, s, e, k == len(plan) - 1, f.get("typ") == "logo")
                    if a <= 0:
                        continue
                    fb = folien_bilder[k]
                    if versatz:
                        fb = fb.transform(fb.size, Image.AFFINE, (1, 0, 0, 0, 1, -versatz))
                    if a < 1:
                        fb = fb.copy()
                        fb.putalpha(fb.getchannel("A").point(lambda v, a=a: int(v * a)))
                    bild = Image.alpha_composite(bild, fb)
                # Fortschritt
                d = ImageDraw.Draw(bild)
                d.rectangle([RAND_X, 1590, RAND_X + TEXT_BREITE, 1596], fill=(255, 255, 255, 60))
                d.rectangle([RAND_X, 1590, RAND_X + int(TEXT_BREITE * (t / gesamt)), 1596], fill=SIGNAL)
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
            insta_musik.schreibe_wav(ton, gesamt + 0.3, seed, beat_bpm)
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
    bild = Image.alpha_composite(Image.alpha_composite(bg, rahmen), folie_bild(story["folie"], sport))
    bild.convert("RGB").save(ziel, quality=90)
    return ziel


def vorschau(beitrag: dict, ausgabe: Path) -> list[Path]:
    """Jede Folie als PNG über dem Foto-Hintergrund - schnell, ohne Video."""
    ausgabe.mkdir(parents=True, exist_ok=True)
    rahmen = rahmen_ebene()
    bg = next(foto_frames(beitrag.get("sport"), 1.0, 1)).convert("RGBA")
    pfade = []
    for i, f in enumerate(beitrag["folien"], 1):
        bild = Image.alpha_composite(Image.alpha_composite(bg, rahmen), folie_bild(f, beitrag.get("sport")))
        p = ausgabe / f"folie-{i}.png"
        bild = bild.convert("RGB")
        if beitrag.get("stil") == "sw":
            bild = bild.convert("L").convert("RGB")
        bild.save(p)
        pfade.append(p)
    return pfade


def ffmpeg_vorhanden() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
