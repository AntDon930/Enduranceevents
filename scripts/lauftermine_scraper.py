#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lauftermine_scraper.py
======================

Liest den Schweizer Laufkalender https://www.lauftermine.ch und ergänzt
die Läufe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 22.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
Keine robots.txt (404 = keine Einschränkung), kein Impressum mit
Nutzungsbedingungen; die Seite ist ein privates Verzeichnis
("Aufgelistet wird: Lauf in der Schweiz …, Trail, Hindernislauf").

Struktur (am 22.09.2026 kalibriert)
-----------------------------------
Eine einzige Seite; der ganze Kalender steht als JavaScript darin:

    mo("Januar 2026","janvier 2026","gennaio 2026","january 2026")
    v(1,"www.neujahrsmarathon.ch","Neujahrsmarathon Schlieren","42.2 / 18 / 12 / 6","","ZH","")
    //v(7,"www.zueriraennt.ch/…","Züri rännt ploggen"," ","","ZH","")

`mo(...)` setzt den Monat (nur der erste trägt das Jahr), `v(tag, url,
name, distanzen, höhenmeter, kanton, cup)` ist ein Lauf. Auskommentierte
Zeilen (`//v(`) sind abgesagte oder nicht mehr gelistete Läufe und
werden übersprungen. Die Distanzen sind Kilometer, mit "/" getrennt -
jede wird ein Eintrag (`expand_competitions`); die `url` ist die
**Veranstalterseite** (ohne Schema), Datenregel 2 ist damit von der
Quelle her erfüllt.

Der Ort steht nicht als eigenes Feld, nur der Kanton. Deshalb wird er
aus dem NAMEN gelesen: das letzte Wort ("Neujahrsmarathon Schlieren",
"Cross Eschlikon"), mit Vorsilbe bei "St. Gallen"/"Bad Ragaz"/"La
Chaux-de-Fonds". Endet der Name auf ein Laufwort statt einen Ort
("Zürcher Silvesterlauf"), wird der Lauf ÜBERSPRUNGEN - ein geratener
Ort wäre schlechter als kein Eintrag (die Läufe stehen meist auch bei
running.life). Geocodiert wird "<Ort>, Schweiz".

Nutzung: `python3 scripts/lauftermine_scraper.py --help`
(Testlauf: `--dry-run`).
"""

from pathlib import Path
import html as html_mod
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    GERMAN_MONTHS,
    Event,
    SiteConfig,
    expand_competitions,
    fetch_page,
    parse_competitions,
    run_scraper_cli,
)

BASE_URL = "https://www.lauftermine.ch"

# Nicht zeilenweise: Der erste Monat steht hinter "id=2;" auf derselben
# Zeile ("id=2;mo(\"Januar 2026\",…)"). Ein Kommentar "//v(" wird als
# solcher erkannt, weil der Treffer am "//" beginnt.
_ZEILE = re.compile(r'(//)?\s*\b(mo|v)\(([^\n]*)')

# Wörter, die KEIN Ort sind - endet der Name darauf, fehlt der Ort.
_KEIN_ORT = re.compile(
    r"(lauf|run|marathon|trail|cross|cup|walk|race|meile|km|serie|challenge|"
    r"stafette|sprint|night|classic|tour|jogging|trophy|memorial|rennen|athlon|"
    # französische Herkunftsformen ("Corrida Bulloise" = Bulle): kein Ort
    r"oise|euse|ienne|aise)$", re.I)
_VORSILBEN = {"st.", "st", "bad", "la", "le", "les", "san", "san.", "oberer", "unterer"}
LAND_KANTON = {"FL": "Liechtenstein"}


def ort_aus_name(name: str) -> str | None:
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    # Anhängsel wie "3/4" (Cup-Zählung) oder Jahreszahlen fallen weg.
    while tokens and re.fullmatch(r"[\d/.]+|\(.*\)", tokens[-1]):
        tokens.pop()
    if not tokens:
        return None
    ort = tokens[-1].strip(",;")
    # Ein einzelnes Wort ist der NAME, kein Ort ("Bierathlon").
    if len(tokens) < 2 or not ort[:1].isupper() or _KEIN_ORT.search(ort) or len(ort) < 3:
        return None
    if len(tokens) >= 2 and tokens[-2].lower() in _VORSILBEN:
        ort = f"{tokens[-2]} {ort}"
    return ort


def parse_kalender(html: str) -> list[dict]:
    """Alle aktiven v(...)-Zeilen mit Datum, Name, Distanzen, Kanton, URL."""
    eintraege = []
    jahr = None
    monat = None
    for m in _ZEILE.finditer(html):
        kommentar, art, rest = m.groups()
        if art == "mo":
            mm = re.match(r'"([^"]+)"', rest)
            if not mm:
                continue
            titel = html_mod.unescape(mm.group(1))
            mj = re.match(r"([A-Za-zÄÖÜäöü]+)(?:\s+(\d{4}))?", titel)
            if not mj:
                continue
            neu = GERMAN_MONTHS.get(mj.group(1).lower())
            if neu is None:
                continue
            if mj.group(2):
                jahr = int(mj.group(2))
            elif monat and neu < monat and jahr:
                jahr += 1
            monat = neu
            continue
        if kommentar or not jahr or not monat:
            continue
        mv = re.match(r'(\d+),"([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)",', rest)
        if not mv:
            continue
        tag, url, name, distanzen, hm, kanton = mv.groups()
        eintraege.append({
            "datum": f"{jahr:04d}-{monat:02d}-{int(tag):02d}",
            "url": html_mod.unescape(url).strip(),
            "name": re.sub(r"\s+", " ", html_mod.unescape(name)).strip(),
            "distanzen": [d.strip() for d in distanzen.split("/") if d.strip()],
            "hm": hm.strip(),
            "kanton": kanton.strip(),
        })
    return eintraege


def fetch_lauftermine_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {BASE_URL}/ ...")
    html = fetch_page(session, f"{BASE_URL}/", render_js)
    if html is None:
        return []
    eintraege = parse_kalender(html)
    print(f"  ✓ {len(eintraege)} aktive Einträge im Kalender.")
    events: list[Event] = []
    ohne_ort = 0
    for e in eintraege:
        ort = ort_aus_name(e["name"])
        if not ort:
            ohne_ort += 1
            continue
        url = e["url"]
        if url and not url.startswith("http"):
            url = "https://" + url
        ev = Event(land=LAND_KANTON.get(e["kanton"], "Schweiz"), name=e["name"], standort=ort,
                   art1="Laufen", datum_start=e["datum"], datum_ende=e["datum"],
                   veranstalter_url=url or f"{BASE_URL}/")
        texte = []
        for d in e["distanzen"]:
            if re.fullmatch(r"\d+(?:[.,]\d+)?", d):
                texte.append(f"{d} km" + (f" / {e['hm']} hm" if e["hm"] else ""))
        events.extend(expand_competitions(ev, parse_competitions(texte, config), config))
    print(f"\n→ {len(events)} Einträge; {ohne_ort} Lauf/Läufe ohne erkennbaren Ort im Namen übersprungen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=f"{BASE_URL}/",
    default_art1="Laufen",
    default_land="Schweiz",
    custom_fetch=fetch_lauftermine_events,
    note="lauftermine_scraper.py: Schweizer Laufkalender, keine robots.txt; "
         "der Kalender steht als v(...)-Aufrufe im Inline-JavaScript.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
