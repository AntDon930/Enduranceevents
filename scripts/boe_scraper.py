#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
boe_scraper.py
==============

Liest den Rennkalender des **Berner Oberländischen Radsportverbands /
Swiss Cycling BOE** (https://www.swiss-cycling-boe.ch/rennkalender-<Jahr>/)
und ergänzt die Rennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
Jimdo-Seite: robots.txt sperrt `/app/` und `/j/`, `Crawl-Delay: 5`
(eingehalten); Impressum ohne Vorbehalt. Zwei Seiten je Lauf
(laufendes und nächstes Jahr).

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Eine Seite je Saison (`/rennkalender-2026/`), Abschnitte mit `h2`
(„Frühlingsrennen Hindelbank", „BOE-Strassenmeisterschaft",
„BOE-Bikemeisterschaft"), darin je Rennen ein Download-Modul: Titel
„13.05.  -  Einzelzeitfahren Langnau-Zäziwil" (Tag ohne Jahr - das Jahr
steht in der Adresse), Beschreibung „Organisation: VC Bärau" (Text, kein
Link), die Ausschreibung als PDF. Ein abgesagtes Rennen trägt „Absage"
im Titel. Im September 2026 waren alle 22 Termine der Saison 2026
vorbei; der Kalender 2027 erscheint im Winter.

Was daraus wird
---------------
* Fahrrad, eine Zeile je Rennen ohne Länge (steht nur im PDF). Kategorie
  aus dem Titel (`ART2_KEYWORDS_FAHRRAD`: Zeitfahren, Bergrennen/
  Strassenrennen → Straße), im Abschnitt „Bikemeisterschaft" Mountainbike.
* Ort aus dem Titel (`ort_im_text` gegen den Kanton Bern): „Strassenrennen
  in Deisswil b. Münchenbuchsee" → Münchenbuchsee, „Bergrennen
  Stettlen-Bantiger" → Stettlen (Start). Ohne Ort kein Eintrag („King of
  Elsigen" ist ein Berg).
* „(nur Kids)" und „Absage" fallen weg.
* `veranstalter_url` ist die Kalenderseite (`PORTAL_DOMAINS`) - der
  Veranstalter steht nur als Name.

Nutzung: `python3 scripts/boe_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys
import time
from datetime import date

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

BASE_URL = "https://www.swiss-cycling-boe.ch"


def kalender_url(jahr: int) -> str:
    return f"{BASE_URL}/rennkalender-{jahr}/"


_TITEL = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s*[-–]\s*(.+?)\s*$")
KEIN_RENNEN = re.compile(r"absage|abgesagt|nur kids|kinder|verschoben", re.I)


def parse_kalender(html: str, jahr: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    abschnitt = None
    rennen: list[dict] = []
    for el in soup.find_all(["h2", "div"]):
        if el.name == "h2":
            abschnitt = el.get_text(" ", strip=True)
            continue
        if "cc-m-download-title" not in (el.get("class") or []):
            continue
        titel = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        m = _TITEL.match(titel)
        if not m:
            continue
        tag, monat, name = int(m.group(1)), int(m.group(2)), m.group(3)
        try:
            datum = date(jahr, monat, tag).isoformat()
        except ValueError:
            continue
        beschreibung = el.find_next_sibling("div", class_="cc-m-download-description")
        org = beschreibung.get_text(" ", strip=True) if beschreibung else ""
        org = re.sub(r"^Organisation:\s*", "", org).strip() or None
        rennen.append({"datum": datum, "name": name, "abschnitt": abschnitt, "organisation": org})
    return rennen


def event_aus_rennen(r: dict, jahr_url: str, orte: dict | None = None) -> tuple[Event | None, str | None]:
    if KEIN_RENNEN.search(r["name"]):
        return None, "kein offenes Rennen (Absage/Kids)"
    orte = orte if orte is not None else orte_aus_places("Schweiz", region="Canton de Berne")
    ort = ort_im_text(r["name"], orte)
    if not ort:
        return None, "kein Ort im Titel"
    standort, lat, lon = ort
    name = re.sub(r"\s*\((?:BOE-Rennen[^)]*)\)", "", r["name"]).strip()
    ev = Event(land="Schweiz", name=name, standort=standort, lat=lat, lon=lon, art1="Fahrrad",
               datum_start=r["datum"], datum_ende=r["datum"], veranstalter_url=jahr_url)
    if re.search(r"bike", r.get("abschnitt") or "", re.I) or re.search(r"\bbike", r["name"], re.I):
        ev.art2 = "Mountainbike"
    else:
        ev.art2 = guess_art2(r["name"], CONFIG, "Fahrrad") or "Straße"
    return ev, None


def fetch_boe_events(session, config, delay, max_pages, render_js) -> list[Event]:
    heute = date.today()
    events: list[Event] = []
    orte = orte_aus_places("Schweiz", region="Canton de Berne")
    for i, jahr in enumerate((heute.year, heute.year + 1)):
        if i:
            time.sleep(delay)
        url = kalender_url(jahr)
        print(f"→ Lade {url} ...")
        html = fetch_page(session, url, render_js=False)
        if not html:
            print("  (keine Seite für dieses Jahr)")
            continue
        rennen = parse_kalender(html, jahr)
        print(f"  ✓ {len(rennen)} Termine.")
        for r in rennen:
            ev, grund = event_aus_rennen(r, url, orte)
            if grund:
                print(f"   - {r['datum']} {r['name']}: {grund}")
                continue
            events.append(ev)
    print(f"\n→ {len(events)} Rennen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=kalender_url(date.today().year),
    default_art1="Fahrrad",
    default_land="Schweiz",
    dach_only=True,
    custom_fetch=fetch_boe_events,
    note="boe_scraper.py: Rennkalender Swiss Cycling BOE (Berner Oberland); Ort aus dem Titel, "
         "ohne Ort kein Eintrag; Kalender des laufenden und des nächsten Jahres.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
