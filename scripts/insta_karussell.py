#!/usr/bin/env python3
"""Instagram-Karussell zu einem Blogbeitrag: eine Titelseite, vier bis
sechs Themenseiten (Do's, Don'ts, Regeln …) und eine Schlussseite, jede
mit dem Maskottchen (`insta_maskottchen.py`), das etwas zur Seite
Passendes tut.

Vom Nutzer am 10.11.2026 gewünscht: „ein neues Format … das wir mit den
Blogposts verbinden können. Wir schreiben zum Beispiel einen Blogpost
über Carbloading, und daraus machen wir einen informativen Insta-Post.
Auf der ersten Seite sollte in groß stehen um was das Thema geht … Dann
auf den nächsten 4-5 Seiten kommt jeweils ein Thema“ – und: „Die Farben
für alle neuen Insta posts bitte dem Bild entnehmen“ (Soft Blue #B6DFED,
Midnight Navy #002941, Coral Orange #FD6E6E).

Der Inhalt steht je Beitrag in `marketing/instagram/karussell/<slug>.json`
(Titel, Seiten mit Punkten, Pose je Seite, Caption) – geschrieben aus dem
Blogtext, ohne etwas, das dort nicht steht (die Quellen stehen im
Beitrag, die Caption verweist darauf). Die Seiten sind 1080 × 1350 (4:5,
das größte Format im Feed).

    python3 scripts/insta_karussell.py carboloading --aus <ordner>

schreibt `01.jpg` … und `caption.txt`. Gepostet wird bisher von Hand.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insta_maskottchen as maskottchen  # noqa: E402
from insta_video import breite, kondensiert, text_schrift  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORDNER = ROOT / "marketing" / "instagram" / "karussell"

B, H = 1080, 1350
RAND = 72

SOFT_BLUE = maskottchen.SOFT_BLUE
MIDNIGHT = maskottchen.MIDNIGHT
CORAL = maskottchen.CORAL
WEISS = (255, 255, 255)
FARBEN = {"soft_blue": SOFT_BLUE, "midnight": MIDNIGHT, "coral": CORAL}

ZEICHEN = ("ja", "nein", "info")
BIO_HINWEIS = "endurance-events.de"
KONTO = "@ausdauermaschine"


def lade(slug: str) -> dict:
    daten = json.loads((ORDNER / f"{slug}.json").read_text(encoding="utf-8"))
    pruefe(daten)
    return daten


def pruefe(daten: dict) -> None:
    """Wirft ValueError, wenn ein Pflichtfeld fehlt oder eine Pose/ein
    Zeichen unbekannt ist."""
    if daten.get("person") not in (None, *maskottchen.PERSONEN):
        raise ValueError(f"unbekannte Person: {daten.get('person')}")
    for feld in ("titel", "seiten", "schluss", "caption", "blog"):
        if not daten.get(feld):
            raise ValueError(f"Feld fehlt: {feld}")
    if not 3 <= len(daten["seiten"]) <= 8:
        raise ValueError("3 bis 8 Themenseiten")
    posen = [daten.get("figur", "stehen"), daten["schluss"].get("figur", "winken")]
    for s in daten["seiten"]:
        if not s.get("titel") or not s.get("punkte"):
            raise ValueError(f"Seite ohne Titel oder Punkte: {s}")
        posen.append(s.get("figur", "stehen"))
        for p in s["punkte"]:
            if p.get("zeichen", "info") not in ZEICHEN:
                raise ValueError(f"unbekanntes Zeichen: {p.get('zeichen')}")
    for p in posen:
        if p not in maskottchen.POSEN:
            raise ValueError(f"unbekannte Pose: {p}")


# ---------------------------------------------------------------- Bausteine

def _grund(farbe, seed: int) -> Image.Image:
    """Einfarbige Fläche mit feinem Punktraster und zwei weichen Kreisen –
    ruhig genug für Text, nicht ganz leer."""
    img = Image.new("RGB", (B, H), farbe)
    hell = farbe == SOFT_BLUE
    deko = Image.new("RGBA", (B, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(deko)
    punkt = (255, 255, 255, 70) if hell else (182, 223, 237, 26)
    for y in range(40, H, 36):
        for x in range(40 + (y // 36 % 2) * 18, B, 36):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=punkt)
    kreis = (255, 255, 255, 60) if hell else (182, 223, 237, 22)
    cx = 860 if seed % 2 == 0 else 920
    d.ellipse([cx - 360, 820 - 360, cx + 360, 820 + 360], fill=kreis)
    d.ellipse([-180, -160, 220, 240], fill=(253, 110, 110, 38 if hell else 30))
    img.paste(deko, (0, 0), deko)
    return img


def _logo(d: ImageDraw.ImageDraw, x: int, y: int, g: int, kachel, linie) -> None:
    d.rounded_rectangle([x, y, x + g, y + g], radius=g // 5, fill=kachel)
    s = g / 64
    pts = [(x + px * s, y + py * s) for px, py in ((11, 46), (26, 20), (38, 34), (51, 17))]
    d.line(pts, fill=linie, width=max(3, int(7 * s)), joint="curve")
    r = 5 * s
    d.ellipse([pts[-1][0] - r, pts[-1][1] - r, pts[-1][0] + r, pts[-1][1] + r], fill=CORAL)


def _kopfzeile(d: ImageDraw.ImageDraw, nr: int, gesamt: int, hell: bool) -> None:
    text = MIDNIGHT if hell else WEISS
    _logo(d, RAND, 56, 46, MIDNIGHT if hell else WEISS, WEISS if hell else MIDNIGHT)
    d.text((RAND + 62, 79), "AUSDAUERMASCHINE", font=kondensiert(32), fill=text, anchor="lm")
    seite = f"{nr}/{gesamt}"
    f = kondensiert(30)
    w = breite(f, seite) + 36
    d.rounded_rectangle([B - RAND - w, 60, B - RAND, 98], radius=19,
                        fill=(255, 255, 255) if hell else (18, 64, 92))
    d.text((B - RAND - w / 2, 79), seite, font=f, fill=MIDNIGHT if hell else WEISS, anchor="mm")


def _fusszeile(d: ImageDraw.ImageDraw, hell: bool, wischen: bool) -> None:
    farbe = MIDNIGHT if hell else SOFT_BLUE
    d.text((RAND, H - 64), BIO_HINWEIS, font=text_schrift(28, True), fill=farbe, anchor="lm")
    if wischen:
        x = RAND + breite(text_schrift(28, True), BIO_HINWEIS) + 34
        d.text((x, H - 64), "Wischen", font=text_schrift(28), fill=farbe, anchor="lm")
        x += breite(text_schrift(28), "Wischen") + 16
        d.line([(x, H - 64), (x + 40, H - 64)], fill=CORAL, width=5)
        d.polygon([(x + 48, H - 64), (x + 34, H - 74), (x + 34, H - 54)], fill=CORAL)


def _pille(d: ImageDraw.ImageDraw, x: int, y: int, text: str, g: int, fill, text_fill) -> tuple[int, int]:
    f = kondensiert(g)
    h = int(g * 1.5)
    w = breite(f, text) + int(g * 1.2)
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=fill)
    d.text((x + w / 2, y + h / 2), text, font=f, fill=text_fill, anchor="mm")
    return w, h


def _gross(text: str, max_b: int, start: int, max_zeilen: int) -> tuple[int, list[str]]:
    """Größte Schrift, bei der `text` in höchstens `max_zeilen` Zeilen der
    Breite `max_b` passt, ohne ein Wort zu trennen."""
    g = start
    while g > 50:
        f = kondensiert(g)
        zeilen, akt = [], ""
        ok = True
        for wort in text.split():
            if breite(f, wort) > max_b:
                ok = False
                break
            probe = f"{akt} {wort}".strip()
            if breite(f, probe) <= max_b:
                akt = probe
            else:
                zeilen.append(akt)
                akt = wort
        zeilen.append(akt)
        if ok and len(zeilen) <= max_zeilen:
            return g, zeilen
        g -= 6
    return g, [text]


def _zeichen(d: ImageDraw.ImageDraw, art: str, x: int, y: int, hell: bool) -> None:
    """Das Symbol vor einem Punkt: ja = Haken, nein = Kreuz, info = Punkt."""
    r = 30
    if art == "nein":
        d.ellipse([x - r, y - r, x + r, y + r], fill=CORAL)
        for dx, dy in ((1, 1), (1, -1)):
            d.line([(x - 11 * dx, y - 11 * dy), (x + 11 * dx, y + 11 * dy)], fill=WEISS, width=7)
    elif art == "ja":
        d.ellipse([x - r, y - r, x + r, y + r], fill=MIDNIGHT if hell else SOFT_BLUE)
        d.line([(x - 13, y + 1), (x - 4, y + 11), (x + 14, y - 10)],
               fill=WEISS if hell else MIDNIGHT, width=7, joint="curve")
    else:
        d.ellipse([x - r, y - r, x + r, y + r], outline=CORAL, width=6)
        d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=CORAL)


def _absatz(fett: str, text: str, g: int, max_b) -> list[list[tuple[str, object]]]:
    """Bricht „fett + normal“ wortweise um. `max_b(zeile)` gibt die Breite
    je Zeilennummer (schmaler, wo die Figur steht)."""
    worte = [(w, text_schrift(g, True)) for w in fett.split()] + [(w, text_schrift(g)) for w in text.split()]
    zeilen: list[list[tuple[str, object]]] = [[]]
    akt = 0.0
    leer = text_schrift(g).getlength(" ")
    for w, f in worte:
        wb = f.getlength(w)
        grenze = max_b(len(zeilen) - 1)
        if zeilen[-1] and akt + leer + wb > grenze:
            zeilen.append([])
            akt = 0.0
        akt += (leer if zeilen[-1] else 0) + wb
        zeilen[-1].append((w, f))
    return zeilen


def person_fuer(daten: dict) -> str:
    """Wer durch das Karussell führt: „er“ (der Nutzer) oder „sie“ (die
    Läuferin) – vom Nutzer am 10.11.2026: „mal die weibliche Person in einem
    Post und mal ich. Das ist einfach random.“ Fest im JSON (`person`) oder
    zufällig, aber je Beitrag immer gleich (Seed = Slug), damit ein neues
    Rendern dieselbe Figur zeigt."""
    import random
    if daten.get("person") in maskottchen.PERSONEN:
        return daten["person"]
    return random.Random(daten["blog"]).choice(sorted(maskottchen.PERSONEN))


_PERSON = {"wer": "er"}


def _figur_einsetzen(img: Image.Image, pose: str, hoehe: int, x_rechts: int, y_unten: int) -> tuple[int, int]:
    fig = maskottchen.figur(pose, hoehe, _PERSON["wer"])
    x = x_rechts - fig.width
    y = y_unten - fig.height
    img.paste(fig, (x, y), fig)
    return x, y


# ---------------------------------------------------------------- Seiten

def titelseite(daten: dict, gesamt: int) -> Image.Image:
    img = _grund(SOFT_BLUE, 0)
    d = ImageDraw.Draw(img)
    _kopfzeile(d, 1, gesamt, True)
    y = 180
    g, zeilen = _gross(daten["titel"].upper() + "!", B - 2 * RAND, 230, 2)
    for z in zeilen:
        d.text((RAND - 6, y), z, font=kondensiert(g), fill=MIDNIGHT)
        y += int(g * 0.92)
    if daten.get("untertitel"):
        g2, zeilen2 = _gross(daten["untertitel"].upper(), B - 2 * RAND, int(g * 0.62), 1)
        d.text((RAND - 4, y), zeilen2[0], font=kondensiert(g2), fill=CORAL)
        y += int(g2 * 0.95)
    y += 36
    fig_x, fig_y = _figur_einsetzen(img, daten.get("figur", "stehen"), 640, B - 30, H - 50)
    if daten.get("einleitung"):
        f = text_schrift(44)
        akt = ""
        for wort in daten["einleitung"].split():
            probe = f"{akt} {wort}".strip()
            max_b = (fig_x - RAND + 20) if y + 58 > fig_y + 80 else B - 2 * RAND
            if breite(f, probe) > max_b and akt:
                d.text((RAND, y), akt, font=f, fill=MIDNIGHT)
                y += 58
                akt = wort
            else:
                akt = probe
        d.text((RAND, y), akt, font=f, fill=MIDNIGHT)
    _fusszeile(d, True, True)
    return img


def themenseite(seite: dict, nr: int, gesamt: int, thema_nr: int) -> Image.Image:
    hell = nr % 2 == 1
    grund = SOFT_BLUE if hell else MIDNIGHT
    img = _grund(grund, nr)
    d = ImageDraw.Draw(img)
    text = MIDNIGHT if hell else WEISS
    _kopfzeile(d, nr, gesamt, hell)
    # Nummer im Kreis + Überschrift
    y = 168
    d.ellipse([RAND, y, RAND + 78, y + 78], fill=CORAL)
    d.text((RAND + 39, y + 40), str(thema_nr), font=kondensiert(52), fill=WEISS, anchor="mm")
    marke = {"do": "DO'S", "dont": "DON'TS"}.get(seite.get("art"), "")
    if marke and seite["titel"].upper().replace("’", "'") != marke:
        _pille(d, RAND + 100, y + 14, marke, 32, MIDNIGHT if not hell else WEISS, WEISS if not hell else MIDNIGHT)
    y += 110
    g, zeilen = _gross(seite["titel"].upper(), B - 2 * RAND, 136, 2)
    for z in zeilen:
        d.text((RAND - 4, y), z, font=kondensiert(g), fill=text)
        y += int(g * 0.94)
    d.rectangle([RAND, y + 18, RAND + 120, y + 26], fill=CORAL)
    y += 70
    # Figur unten rechts; die Punkte werden daneben schmaler
    fig_x, fig_y = _figur_einsetzen(img, seite.get("figur", "stehen"), 450, B - 36, H - 96)
    tx = RAND + 86

    def anordnen(g_text: int):
        """Setzt die Punkte probehalber; gibt (Zeilen je Punkt, Ende) zurück."""
        zeilen_h = int(g_text * 1.32)
        yy = y
        satz = []
        for p in seite["punkte"]:
            y0 = yy

            def max_b(i, y0=y0):
                unten = y0 + (i + 1) * zeilen_h
                return (fig_x - tx + 10) if unten > fig_y + 40 else (B - RAND - tx)
            zeilen = _absatz(p.get("fett", ""), p.get("text", ""), g_text, max_b)
            satz.append((p, y0, zeilen))
            yy += len(zeilen) * zeilen_h + int(g_text * 0.72)
        return satz, yy, zeilen_h

    # so groß wie möglich, aber über der Fußzeile
    g_text = 47
    satz, ende, zeilen_h = anordnen(g_text)
    while ende > H - 110 and g_text > 34:
        g_text -= 3
        satz, ende, zeilen_h = anordnen(g_text)
    fett = text_schrift(g_text, True)
    for p, y0, zeilen in satz:
        _zeichen(d, p.get("zeichen", "info"), RAND + 30, y0 + int(g_text * 0.64), hell)
        yy = y0
        for z in zeilen:
            x = tx
            for i, (w, f) in enumerate(z):
                if i:
                    x += text_schrift(g_text).getlength(" ")
                farbe = (CORAL if not hell else MIDNIGHT) if f is fett else text
                d.text((x, yy), w, font=f, fill=farbe)
                x += f.getlength(w)
            yy += zeilen_h
    _fusszeile(d, hell, True)
    return img


def schlussseite(daten: dict, nr: int, gesamt: int) -> Image.Image:
    hell = nr % 2 == 1
    img = _grund(SOFT_BLUE if hell else MIDNIGHT, nr)
    d = ImageDraw.Draw(img)
    text = MIDNIGHT if hell else WEISS
    _kopfzeile(d, nr, gesamt, hell)
    s = daten["schluss"]
    fig_x, fig_y = _figur_einsetzen(img, s.get("figur", "winken"), 520, B - 40, H - 96)
    y = 190
    g, zeilen = _gross(s["titel"].upper(), B - 2 * RAND, 150, 3)
    for z in zeilen:
        d.text((RAND - 4, y), z, font=kondensiert(g), fill=text)
        y += int(g * 0.94)
    y += 30
    f = text_schrift(42)
    akt = ""
    for wort in s.get("text", "").split():
        probe = f"{akt} {wort}".strip()
        max_b = (fig_x - RAND) if y + 56 > fig_y + 60 else B - 2 * RAND
        if breite(f, probe) > max_b and akt:
            d.text((RAND, y), akt, font=f, fill=text)
            y += 56
            akt = wort
        else:
            akt = probe
    if akt:
        d.text((RAND, y), akt, font=f, fill=text)
        y += 56
    y += 40
    w, h = _pille(d, RAND, y, "LINK IN DER BIO", 44, CORAL, WEISS)
    _pille(d, RAND, y + h + 20, KONTO.upper(), 36, MIDNIGHT if hell else WEISS, WEISS if hell else MIDNIGHT)
    _fusszeile(d, hell, False)
    return img


def seiten(daten: dict) -> list[Image.Image]:
    gesamt = len(daten["seiten"]) + 2
    _PERSON["wer"] = person_fuer(daten)
    bilder = [titelseite(daten, gesamt)]
    for i, s in enumerate(daten["seiten"]):
        bilder.append(themenseite(s, i + 2, gesamt, i + 1))
    bilder.append(schlussseite(daten, gesamt, gesamt))
    return bilder


def caption(daten: dict) -> str:
    return "\n\n".join(daten["caption"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slug", help="Name der Datei in marketing/instagram/karussell/ (ohne .json)")
    ap.add_argument("--aus", required=True, help="Zielordner für die Bilder")
    a = ap.parse_args(argv)
    daten = lade(a.slug)
    aus = Path(a.aus)
    aus.mkdir(parents=True, exist_ok=True)
    for i, bild in enumerate(seiten(daten), 1):
        bild.save(aus / f"{i:02d}.jpg", quality=92)
    (aus / "caption.txt").write_text(caption(daten) + "\n", encoding="utf-8")
    print(f"{len(daten['seiten']) + 2} Seiten + caption.txt in {aus}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
