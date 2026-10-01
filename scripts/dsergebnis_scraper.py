#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dsergebnis_scraper.py
=====================

Liest die Terminliste des Zeitnehmers **DS Ergebnisdienst**
(https://www.dsergebnis.de) und ergänzt die Straßenrennen in
`events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
Jimdo-Seite: robots.txt sperrt `/app/` und `/j/` und verlangt
`Crawl-Delay: 5` (eingehalten über `check_robots()`); das Impressum
trägt keinen Vorbehalt. Abgerufen wird eine einzige Seite.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Die Startseite trägt unter der Überschrift „Termine <Jahr>" einen
Textblock mit einer Zeile je Rennen: „14.03.2027 Herforder
Frühjahrspreis", „25.04.2027 43. Überherrner Straßenrennen auf dem
Wallerfanger Saargau", „03./04.07.2027 100 Jahre Rund in Serrig",
„11.09.2027 Termin reserviert". Kein Ort, kein Link - nur Datum und
Name. Im September 2026: 19 Zeilen für 2027, zwei davon mit der
Jahreszahl 2026 (Tippfehler der Seite), zwei „Termin reserviert".

Was daraus wird
---------------
* Fahrrad / Straße (DS misst Straßenrennen und Kriterien; „Rundfahrt"
  bleibt Straße). Eine Zeile je Rennen, ohne Distanz - die Seite nennt
  keine.
* Der **Ort kommt aus dem Namen** (`scraper_lib.ort_im_text`, gegen
  `places.json`): „Herforder Frühjahrspreis" → Herford, „Rund um das
  Stadttheater Gießen" → Gießen, „36. Spee-Cup in Genthin" → Genthin.
  Ohne eindeutigen Ort **kein Eintrag** (Datenregel 4): „Gr. Preis der
  Südlichen Weinstrasse", „Kometen Schmitter Nacht", „GP von Buchholz"
  (fünf Orte dieses Namens) werden gemeldet, nicht geraten. „Radrennen
  in Offenbach" steht in `NICHT_EINDEUTIG`: `places.json` kennt nur
  Offenbach am Main, das Rennen könnte aber ebenso in Offenbach an der
  Queich liegen.
* Eine Zeile unter „Termine 2027" mit einem anderen Jahr ist ein
  Tippfehler der Seite - gemeldet, nicht korrigiert (kein Raten).
* „Termin reserviert" ist kein Rennen.
* `veranstalter_url` ist die Terminseite selbst (`PORTAL_DOMAINS`) -
  die Veranstalterseite sucht `veranstalter_links.py`.

Nutzung: `python3 scripts/dsergebnis_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    guess_art2,
    ort_im_text,
    orte_aus_places,
    run_scraper_cli,
)

BASE_URL = "https://www.dsergebnis.de"
LISTE_URL = f"{BASE_URL}/"

_ZEILE = re.compile(r"^\s*(\d{1,2})\.(?:/(\d{1,2})\.)?(\d{1,2})\.(\d{4})\s+(.+?)\s*$")
_TERMINE_JAHR = re.compile(r"^\s*Termine\s+(\d{4})\s*$")
KEIN_RENNEN = re.compile(r"termin reserviert|abgesagt|entfällt", re.I)
# Orte, die places.json nur einmal kennt, in Wirklichkeit aber mehrfach
# vorkommen - hier wird nicht geraten.
NICHT_EINDEUTIG = {"Offenbach"}


def parse_termine(html: str) -> list[dict]:
    """Alle Zeilen unter „Termine <Jahr>" als {jahr, datum_start, datum_ende, name}."""
    soup = BeautifulSoup(html, "html.parser")
    zeilen: list[dict] = []
    jahr = None
    for el in soup.find_all(["h1", "h2", "h3", "p"]):
        text = el.get_text(" ", strip=True).replace("\xa0", " ")
        m = _TERMINE_JAHR.match(text)
        if m:
            jahr = int(m.group(1))
            continue
        if jahr is None or el.name != "p":
            continue
        m = _ZEILE.match(text)
        if not m:
            continue
        tag1, tag2, monat, y, name = m.groups()
        start = f"{int(y):04d}-{int(monat):02d}-{int(tag1):02d}"
        ende = f"{int(y):04d}-{int(monat):02d}-{int(tag2):02d}" if tag2 else start
        zeilen.append({"jahr": jahr, "datum_start": start, "datum_ende": ende,
                       "name": re.sub(r"\s+", " ", name)})
    return zeilen


def event_aus_zeile(z: dict, orte: dict | None = None) -> tuple[Event | None, str | None]:
    if KEIN_RENNEN.search(z["name"]):
        return None, "kein Rennen"
    if not z["datum_start"].startswith(str(z["jahr"])):
        return None, f"Jahr passt nicht zur Überschrift Termine {z['jahr']} (Tippfehler der Seite)"
    orte = orte if orte is not None else orte_aus_places("Deutschland")
    ort = ort_im_text(z["name"], orte)
    if not ort:
        return None, "kein eindeutiger Ort im Namen"
    standort, lat, lon = ort
    if standort in NICHT_EINDEUTIG:
        return None, f"Ort {standort} nicht eindeutig"
    ev = Event(land="Deutschland", name=z["name"], standort=standort, lat=lat, lon=lon,
               art1="Fahrrad", datum_start=z["datum_start"], datum_ende=z["datum_ende"],
               veranstalter_url=LISTE_URL)
    # „City Cross", „Cross Cup", „Galoppcross" sind Querfeldeinrennen; die
    # Stichwortliste kennt nur „Cyclocross"/„Querfeldein".
    ev.art2 = guess_art2(z["name"], CONFIG, "Fahrrad") or ("Cyclecross" if re.search(r"cross", z["name"], re.I) else "Straße")
    return ev, None


def fetch_dsergebnis_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    zeilen = parse_termine(html)
    print(f"  ✓ {len(zeilen)} Terminzeilen.")
    orte = orte_aus_places("Deutschland")
    events: list[Event] = []
    for z in zeilen:
        ev, grund = event_aus_zeile(z, orte)
        if grund:
            print(f"   - {z['datum_start']} {z['name']}: {grund}")
            continue
        events.append(ev)
    print(f"\n→ {len(events)} Rennen mit Ort.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_dsergebnis_events,
    note="dsergebnis_scraper.py: Terminliste des Zeitnehmers DS Ergebnisdienst; Ort aus dem "
         "Namen (places.json), ohne eindeutigen Ort kein Eintrag.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
