#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lvpfalz_scraper.py
==================

Liest die **Terminliste Volksläufe des Leichtathletikverbands Pfalz**
(https://www.lv-pfalz.de/terminliste-volkslaeufe.html) und ergänzt die
Läufe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben: „Bitte die
Webseiten die du unkritisch siehst gleich auf die Webseite aufnehmen")
---------------------------------------------------------------------
robots.txt 404 (= frei), Impressum des Verbands ohne Vorbehalt.
Übernommen werden Termine, Strecken und der Veranstalterlink.

Struktur (am 30.09.2026 kalibriert, Contao-Eventliste)
------------------------------------------------------
Je Lauf ein `div.event` mit `itemtype=schema.org/Event`: `h2[itemprop=name]`,
`time[itemprop=startDate]`, in der Beschreibung die Absätze „Veranstalter:
TSG Maxdorf", die Strecken („10 km Gemüselauf; 0,8 km Junges Gemüse"),
eine verschleierte E-Mail und **der Link auf die Veranstalterseite**
(`https://…`). Kein Ort - der Verein steht dafür (TSG Maxdorf → Maxdorf),
sonst der Name („Bad Dürkheimer Berglauf" → Bad Dürkheim); geprüft gegen
`places.json` (Rheinland-Pfalz). Im September 2026: 12 Läufe, die
Hälfte schon im Bestand - der Wert der Liste sind die Veranstalterlinks
und die kleinen Vereinsläufe, die in keinem Portal stehen.

Was daraus wird
---------------
* Laufen, je Strecke eine Zeile (`expand_competitions` über die mit
  Semikolon getrennten Wettbewerbe; Datenregel 1); Kategorie aus dem
  Text (Crosslauf → Trail, Berglauf → Trail).
* Ort aus dem Vereinsnamen oder dem Laufnamen (`ort_im_text`), ohne
  Treffer kein Eintrag.
* `veranstalter_url`: der http-Link der Beschreibung; ohne ihn die
  Terminliste (`PORTAL_DOMAINS`).

Nutzung: `python3 scripts/lvpfalz_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    expand_competitions,
    fetch_page,
    guess_art2,
    ort_im_text,
    orte_aus_places,
    parse_competitions,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.lv-pfalz.de"
LISTE_URL = f"{BASE_URL}/terminliste-volkslaeufe.html"
# Vereinskürzel vor dem Ort: „TSG Maxdorf", „LC Bad Dürkheim", „TuS 06 Heltersberg".
_VEREIN = re.compile(r"^(?:(?:[A-Z][A-Za-zÄÖÜäöü]{0,4}|\d{2,4}|Blau-Weiß|Rot-Weiß|Schwarz-Weiß|Eintracht|Germania|Viktoria|Concordia|Alemannia|Fortuna)\s+)+", re.I)


def parse_liste(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    laeufe: list[dict] = []
    for block in soup.select("div.event"):
        h2 = block.find("h2")
        zeit = block.find("time")
        if not h2 or not zeit:
            continue
        eintrag: dict = {"name": h2.get_text(" ", strip=True),
                         "datum": parse_flexible_date(zeit.get("datetime") or zeit.get_text()),
                         "veranstalter": None, "strecken": None, "url": None}
        for p in block.select("p"):
            text = p.get_text(" ", strip=True)
            a = p.find("a", href=True)
            if a and a["href"].startswith("http"):
                eintrag["url"] = a["href"].strip()
            elif text.startswith("Veranstalter:"):
                eintrag["veranstalter"] = text.split(":", 1)[1].strip()
            elif re.search(r"\d\s*(?:km|m)\b|lauf|cross|marathon|walking", text, re.I) and not a and "time" not in str(p):
                eintrag["strecken"] = text
        laeufe.append(eintrag)
    return laeufe


def ort_fuer(lauf: dict, orte: dict) -> tuple[str, float | None, float | None] | None:
    verein = lauf.get("veranstalter") or ""
    ohne_kuerzel = _VEREIN.sub("", verein).strip()
    for kandidat in (ohne_kuerzel, verein, lauf["name"]):
        treffer = ort_im_text(kandidat, orte)
        if treffer:
            return treffer
    return None


def events_aus_lauf(lauf: dict, config: SiteConfig, orte: dict | None = None) -> tuple[list[Event], str | None]:
    if not lauf.get("datum"):
        return [], "kein Datum"
    orte = orte if orte is not None else orte_aus_places("Deutschland", region="Rheinland-Pfalz")
    ort = ort_fuer(lauf, orte)
    if not ort:
        return [], f"kein Ort ({lauf.get('veranstalter')})"
    standort, lat, lon = ort
    ev = Event(land="Deutschland", name=lauf["name"], standort=standort, lat=lat, lon=lon, art1="Laufen",
               datum_start=lauf["datum"], datum_ende=lauf["datum"], veranstalter_url=lauf.get("url") or LISTE_URL)
    strecken = [s.strip() for s in re.split(r"\s*;\s*", lauf.get("strecken") or "") if s.strip()]
    if not strecken:
        return [ev], None
    events = expand_competitions(ev, parse_competitions(strecken, config), config)
    for x in events:
        if not x.art2:
            x.art2 = guess_art2(f"{lauf['name']} {x.wettbewerb or ''}", config, "Laufen") or "Straße"
    return events, None


def fetch_lvpfalz_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    laeufe = parse_liste(html)
    print(f"  ✓ {len(laeufe)} Läufe in der Terminliste.")
    orte = orte_aus_places("Deutschland", region="Rheinland-Pfalz")
    events: list[Event] = []
    for lauf in laeufe:
        neue, grund = events_aus_lauf(lauf, config, orte)
        if grund:
            print(f"   - {lauf['datum']} {lauf['name']}: {grund}")
        events.extend(neue)
    print(f"\n→ {len(events)} Zeilen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Laufen",
    default_land="Deutschland",
    custom_fetch=fetch_lvpfalz_events,
    note="lvpfalz_scraper.py: Volkslauf-Terminliste des LV Pfalz; Ort aus Verein oder Name, "
         "Veranstalterlink aus der Beschreibung.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
