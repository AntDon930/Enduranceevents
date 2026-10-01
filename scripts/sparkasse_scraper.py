#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sparkasse_scraper.py
====================

Liest den Laufkalender von Erste Bank Sparkasse Running
(https://www.sparkasse.at/running/laufkalender) und ergänzt die Läufe
in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 22.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
robots.txt sperrt nur die Bank-Bereiche, `/running/` nicht; das
Impressum nennt kein Verbot des Auslesens.

Struktur (am 22.09.2026 kalibriert)
-----------------------------------
Die Kalenderseite listet alle Läufe als Kacheln (`<article>` mit `<h3>`
und dem Knopf "zum Lauf" -> `/running/laufkalender/<jahr>/<slug>`); die
Filter (Distanz, Bundesland, Monat) arbeiten im Browser über dieselben
Kacheln, es gibt keine weiteren Seiten. Am 22.09.2026 waren es 16
kommende Läufe (2026) - ein kleiner, aber österreichischer Kalender mit
Veranstalterlinks.

Die **Detailseite** nennt "Wo: <Ort>", "Wann: <Datum>" und einen Knopf
"zur Anmeldung", der auf die **Veranstalterseite** zeigt (z. B.
https://www.lechlauf.at/). Zeigt er auf ein Anmeldeportal, bleibt der
Sparkassen-Link als Portallink stehen (PORTAL_DOMAINS), damit ein
späterer Lauf ihn ersetzen kann. Distanzen nennt die Seite nur im Text,
`guess_distance_km()` liest sie aus Name und Beschreibung.

Nutzung: `python3 scripts/sparkasse_scraper.py --help`
(Testlauf: `--dry-run --max-details 3`).
"""

from pathlib import Path
import re
import sys
import time
from datetime import date
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    guess_art1,
    guess_art2,
    guess_distance_km,
    is_portal_link,
    ort_aus_veranstaltungsort,
    parse_duration_h,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.sparkasse.at"
LISTE_URL = f"{BASE_URL}/running/laufkalender"

def parse_liste(soup: BeautifulSoup) -> list[dict]:
    karten = []
    for a in soup.select("a[href^='/running/laufkalender/']"):
        href = a.get("href") or ""
        m = re.match(r"/running/laufkalender/(\d{4})/[^/]+$", href)
        if not m or int(m.group(1)) < date.today().year:
            continue
        art = a.find_parent("article")
        h3 = art.select_one("h3") if art else None
        karten.append({"url": urljoin(BASE_URL, href),
                       "name": h3.get_text(" ", strip=True) if h3 else ""})
    # Doppelte (mobile + Desktop-Kachel) fallen über die URL zusammen.
    gesehen: set[str] = set()
    return [k for k in karten if not (k["url"] in gesehen or gesehen.add(k["url"]))]


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {"text": ""}
    text_teile = []
    for p in soup.select("[data-testid='rich-text'] p"):
        t = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        text_teile.append(t)
        m = re.match(r"Wo\s*:\s*(.+)$", t)
        if m and "ort" not in result:
            result["ort"] = ort_aus_veranstaltungsort(m.group(1))
        m = re.match(r"Wann\s*:\s*(.+)$", t)
        if m and "datum" not in result:
            result["datum"] = parse_flexible_date(m.group(1))
    result["text"] = " ".join(text_teile)
    for a in soup.select("a[href^='http']"):
        href = a["href"]
        if BASE_URL in href or "erstegroup" in href or "sparkasse" in href:
            continue
        if not is_portal_link(href):
            result["official_url"] = href
            break
    return result


def fetch_sparkasse_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, render_js)
    if html is None:
        return []
    karten = parse_liste(BeautifulSoup(html, "html.parser"))
    print(f"  ✓ {len(karten)} Kachel(n) für {date.today().year} und später.")
    events: list[Event] = []
    details = official = 0
    for k in karten:
        ev = Event(land="Österreich", name=k["name"], art1="Laufen", veranstalter_url=k["url"])
        text = k["name"]
        if config.fetch_details and (not config.max_details or details < config.max_details):
            time.sleep(delay)
            dhtml = fetch_page(session, k["url"], False)
            details += 1
            d = parse_detail(dhtml) if dhtml else {}
            ev.standort = d.get("ort")
            ev.datum_start = ev.datum_ende = d.get("datum")
            text = f"{k['name']} {d.get('text', '')}"
            if d.get("official_url"):
                ev.veranstalter_url = d["official_url"]
                official += 1
        ev.art1 = guess_art1(text, config)
        ev.art2 = guess_art2(text, config, ev.art1)
        ev.laenge_km = guess_distance_km(text, config)
        ev.dauer_h = parse_duration_h(text)
        if ev.laenge_km is None and ev.dauer_h is None:
            ev.laenge_km = guess_distance_km(k["name"], config)
        events.append(ev)
    print(f"\n→ {details} Detailseite(n), davon {official} mit Veranstalterseite.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Laufen",
    default_land="Österreich",
    custom_fetch=fetch_sparkasse_events,
    note="sparkasse_scraper.py: Erste Bank Sparkasse Running, robots.txt erlaubt "
         "/running/; Kacheln -> Detailseite mit Ort, Datum und Veranstalterlink.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
