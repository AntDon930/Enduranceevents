#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fricktal_scraper.py
===================

Liest den Kalender des **Raiffeisen Fricktaler Cups** (Swiss Cycling
Fricktal, https://www.swisscycling-fricktal.ch/kalender) - eine
Mountainbike-Rennserie im Aargau - und ergänzt die Rennen in
`events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
ClubDesk-Seite: robots.txt sperrt nur Aktions-Adressen (`/*?action`,
`/*.ics`, `/*?pr&`), der Kalender selbst ist frei; Impressum ohne
Vorbehalt. Eine Seite je Lauf.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
`div.event-list` mit je Termin einem `h3` („Sonntag 18.10.2026") und
einer Kachel: `.cd-tile-h-main-heading` „Bikerennen Wittnau - 38.
Raiffeisen Fricktaler Cup 2026", Detailzeilen „Ort" („Turnhalle
Wittnau") und „Text". Vereinsanlässe stehen im selben Kalender
(„Absenden/Preisverteilung", Generalversammlung). Im September 2026:
ein künftiges Rennen (Saisonfinale Wittnau), die Saison 2027 kommt im
Frühjahr.

Was daraus wird
---------------
* Fahrrad / Mountainbike („Bikerennen" ist in der Schweiz das
  MTB-Rennen), eine Zeile je Rennen ohne Länge.
* Nur Kacheln, deren Titel ein Rennen nennt (`RENNEN`); Absenden,
  GV, Training fallen weg.
* Ort aus der „Ort"-Zeile, sonst aus dem Titel (`ort_im_text` gegen
  den Kanton Aargau, dann die ganze Schweiz); ohne Ort kein Eintrag.
* `veranstalter_url` ist der Kalender (`PORTAL_DOMAINS`).

Nutzung: `python3 scripts/fricktal_scraper.py --help` (Testlauf: `--dry-run`).
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
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.swisscycling-fricktal.ch"
KALENDER_URL = f"{BASE_URL}/kalender"
RENNEN = re.compile(r"rennen|race|cup-lauf|cross|marathon", re.I)
KEIN_RENNEN = re.compile(r"absenden|preisverteilung|generalversammlung|\bgv\b|training|sitzung|helfer", re.I)


def parse_kalender(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    liste = soup.select_one("div.event-list") or soup
    eintraege: list[dict] = []
    datum = None
    for el in liste.find_all(["h3", "div"]):
        if el.name == "h3":
            datum = parse_flexible_date(el.get_text(" ", strip=True))
            continue
        if "cd-tile-h-box" not in (el.get("class") or []):
            continue
        titel = el.select_one(".cd-tile-h-main-heading")
        eintrag = {"datum": datum, "name": titel.get_text(" ", strip=True) if titel else None, "ort": None}
        for li in el.select("li"):
            label = li.select_one(".cd-tile-h-detail-label")
            wert = li.select_one(".cd-tile-h-detail-value")
            if label and wert and label.get_text(strip=True) == "Ort":
                eintrag["ort"] = wert.get_text(" ", strip=True)
        eintraege.append(eintrag)
    return eintraege


def event_aus_eintrag(e: dict, orte: dict | None = None, orte_ch: dict | None = None) -> tuple[Event | None, str | None]:
    if not e.get("datum") or not e.get("name"):
        return None, "ohne Datum oder Titel"
    if KEIN_RENNEN.search(e["name"]) or not RENNEN.search(e["name"]):
        return None, "kein Rennen"
    orte = orte if orte is not None else orte_aus_places("Schweiz", region="Kanton Aargau")
    orte_ch = orte_ch if orte_ch is not None else orte_aus_places("Schweiz")
    ort = None
    for text in (e.get("ort"), e["name"]):
        ort = ort_im_text(text, orte) or ort_im_text(text, orte_ch)
        if ort:
            break
    if not ort:
        return None, f"kein Ort ({e.get('ort')})"
    standort, lat, lon = ort
    ev = Event(land="Schweiz", name=e["name"], standort=standort, lat=lat, lon=lon, art1="Fahrrad",
               datum_start=e["datum"], datum_ende=e["datum"], veranstalter_url=KALENDER_URL)
    ev.art2 = "Mountainbike"
    return ev, None


def fetch_fricktal_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {KALENDER_URL} ...")
    html = fetch_page(session, KALENDER_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    eintraege = parse_kalender(html)
    print(f"  ✓ {len(eintraege)} Kalendereinträge.")
    orte = orte_aus_places("Schweiz", region="Kanton Aargau")
    orte_ch = orte_aus_places("Schweiz")
    events: list[Event] = []
    for e in eintraege:
        ev, grund = event_aus_eintrag(e, orte, orte_ch)
        if grund:
            print(f"   - {e.get('datum')} {e.get('name')}: {grund}")
            continue
        events.append(ev)
    print(f"\n→ {len(events)} Rennen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=KALENDER_URL,
    default_art1="Fahrrad",
    default_land="Schweiz",
    custom_fetch=fetch_fricktal_events,
    note="fricktal_scraper.py: Raiffeisen Fricktaler Cup (MTB, Aargau); nur Rennen, Ort aus der "
         "Ort-Zeile oder dem Titel.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
