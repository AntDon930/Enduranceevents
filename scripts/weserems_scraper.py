#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weserems_scraper.py
===================

Liest die Terminseite des **Weser-Ems-Cups** (Querfeldein-Serie im
Nordwesten Niedersachsens, https://www.radsport-weser-ems.de/termine/)
und ergänzt die Rennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
Jimdo-Seite: robots.txt sperrt `/app/` und `/j/`, `Crawl-Delay: 5`
(eingehalten); Impressum ohne Vorbehalt. Eine Seite je Lauf.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Ein Textblock, eine Zeile je Rennen: „26.09.2026  WEC Cross Oldenburg",
„11.10.2026  BL Lohne mit Wertung für Hobby u. U 11 / 13" (die
Bezirksliga), „25.10.2026  WEC Cross Os - Bornheide" (Os = Osnabrück),
„18.10.2026  WEC Cross Bad Essen / Pr. Oldendorf" (zwei Orte: Start in
Bad Essen), „24.01.2027  WEC Cross Endlauf Bad - Essen / Pr. Oldendorf".
Kein Link, keine Distanz. Im September 2026: 11 Termine.

Was daraus wird
---------------
* Fahrrad / Cyclecross, eine Zeile je Rennen ohne Länge.
* Der Ort kommt aus der Zeile (`ort_im_text` gegen die Orte in
  Niedersachsen und Nordrhein-Westfalen - Rheine und Preußisch
  Oldendorf liegen jenseits der Landesgrenze); `KUERZEL` löst „Os" und
  „Pr. Oldendorf" auf und schreibt den Namen aus. Bei zwei Orten gilt
  der erste (Start). Ohne Ort kein Eintrag.
* `veranstalter_url` ist die Terminseite (`PORTAL_DOMAINS`).

Nutzung: `python3 scripts/weserems_scraper.py --help` (Testlauf: `--dry-run`).
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
    ort_im_text,
    orte_aus_places,
    run_scraper_cli,
)

BASE_URL = "https://www.radsport-weser-ems.de"
TERMINE_URL = f"{BASE_URL}/termine/"
CUP = "Weser-Ems-Cup"

_ZEILE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(.+?)\s*$")
# Kürzel und Ortsteile der Terminzeilen: Os = Osnabrück, Engter ist ein
# Stadtteil von Bramsche (places.json kennt nur die Stadt).
KUERZEL = {"Os": "Osnabrück", "Pr. Oldendorf": "Preußisch Oldendorf", "Bad - Essen": "Bad Essen",
           "Engter": "Bramsche (Engter)", "u.": "und"}


def orte_weser_ems() -> dict:
    orte: dict = {}
    for region in ("Niedersachsen", "Nordrhein-Westfalen", "Bremen"):
        for k, v in orte_aus_places("Deutschland", region=region).items():
            orte.setdefault(k, []).extend(v)
    return orte


def parse_termine(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    zeilen: list[dict] = []
    for p in soup.find_all(["p", "li"]):
        text = re.sub(r"\s+", " ", p.get_text(" ", strip=True).replace("\xa0", " "))
        m = _ZEILE.match(text)
        if not m:
            continue
        d, mo, y, name = m.groups()
        try:
            datum = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            continue
        zeilen.append({"datum": datum, "name": name})
    return zeilen


def event_aus_zeile(z: dict, orte: dict | None = None) -> tuple[Event | None, str | None]:
    orte = orte if orte is not None else orte_weser_ems()
    name = z["name"]
    for kurz, lang in KUERZEL.items():
        name = re.sub(r"(?<![\wäöüß])" + re.escape(kurz) + r"(?![\wäöüß])", lang, name)
    name = re.sub(r"\s+", " ", name).strip()
    # Bei „Bad Essen / Preußisch Oldendorf" zählt der erste Ort (Start).
    ort = ort_im_text(name.split("/")[0], orte) or ort_im_text(name, orte)
    if not ort:
        return None, "kein Ort in der Zeile"
    standort, lat, lon = ort
    ev = Event(land="Deutschland", name=name, standort=standort, lat=lat, lon=lon, art1="Fahrrad",
               datum_start=z["datum"], datum_ende=z["datum"], wettbewerb=f"Cyclocross, {CUP}",
               veranstalter_url=TERMINE_URL)
    ev.art2 = "Cyclecross"
    return ev, None


def fetch_weserems_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {TERMINE_URL} ...")
    html = fetch_page(session, TERMINE_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    zeilen = parse_termine(html)
    print(f"  ✓ {len(zeilen)} Terminzeilen.")
    orte = orte_weser_ems()
    events: list[Event] = []
    for z in zeilen:
        ev, grund = event_aus_zeile(z, orte)
        if grund:
            print(f"   - {z['datum']} {z['name']}: {grund}")
            continue
        events.append(ev)
    print(f"\n→ {len(events)} Rennen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=TERMINE_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_weserems_events,
    note="weserems_scraper.py: Weser-Ems-Cup (Querfeldein, Niedersachsen); Ort aus der "
         "Terminzeile, ohne Ort kein Eintrag.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
