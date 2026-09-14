#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runningcompany_scraper.py
============================

Liest Lauf-Events vom Laufkalender auf
https://www.runningcompany.de/runners-high/laufkalender/ aus und ergänzt
sie in `events.json` (siehe `scraper_lib.py` für die gemeinsame Logik:
robots.txt-Prüfung, Geocoding, Dedupe/Merge, CLI). Das eigentliche
Abrufen/Parsen übernimmt eine seiten-spezifische `custom_fetch`-Funktion
(siehe `SiteConfig.custom_fetch` in `scraper_lib.py`), weil die
Seitenstruktur nicht in das generische Karten/CSS-Selektor-Schema passt.

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt erlaubt den Zugriff (nur `/wp-admin/` ist gesperrt).

Die Seite ist "Laufkalender München und Münchner Region": ein
Akkordeon mit einer Sektion pro Monat (Anker `#januar` .. `#dezember`,
daher das `#januar`-Fragment in der ursprünglich genannten URL), jede
Sektion enthält eine ganz normale HTML-`<table>` mit vier Spalten pro
Zeile:

    <tr>
      <td>Sa, 16.1.–</td>
      <td><a href="..."><strong>Name</strong></a></td>
      <td>Ort</td>
      <td>Distanz(en) oder Freitext</td>
    </tr>

Alle zwölf Monatstabellen stehen bereits serverseitig im HTML (kein
JavaScript-Nachladen, kein `--render-js` nötig).

Besonderheiten, die `fetch_runningcompany_events()` unten behandelt:

1. **Kein Jahr im Datum**: Spalte 1 enthält nur Tag.Monat (z. B. "6.1."),
   dazu ein "vss." (voraussichtlich)-Präfix und/oder eine Wochentags-
   abkürzung. Das Jahr steht stattdessen einmalig im Seitentext ("... wo
   und wann du **2026** bei einem Volkslauf starten kannst.") und wird
   per Regex daraus gelesen (Fallback: aktuelles Jahr) - funktioniert
   dadurch auch noch, wenn der Betreiber die Seite für 2027 aktualisiert.
2. **Eigene Angebote vs. echte Laufevents**: Die Tabelle enthält neben
   echten (immer extern verlinkten) Laufveranstaltungen auch RUNNING
   Companys eigene Laufreisen/Laufcamps/Trainingskurse (Links auf die
   eigene Domain, z. B. `/produkte/...`, `/training/...`). Verifiziert:
   von 90 Tabellenzeilen verlinken genau 74 auf eine externe Domain
   (= echte Rennen) und genau 16 auf runningcompany.de selbst (= eigene
   Angebote, u. a. alle mehrtägigen mit über zwei Zeilen "16.1.–" /
   "–30.1." gesplitteten Termine). Interne Links werden daher komplett
   übersprungen statt versucht, sie als Renn-Events zu normalisieren -
   das erspart auch das Zusammenführen der gesplitteten Start-/End-Zeile,
   da ausschließlich diese eigenen Angebote dieses Zwei-Zeilen-Muster
   nutzen.
3. **Mehrere Distanzen pro Zeile** (z. B. "10 km, 20 km"): `laenge_km`
   wird auf die größte gefundene Distanz gesetzt (nicht die erste).

Die Seite deckt nur die Region München/Bayern ab, daher
`default_land="Deutschland"` als Fallback.

Nutzung: `python3 scripts/runningcompany_scraper.py --help`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import Event, SiteConfig, guess_art2, guess_land, run_scraper_cli  # noqa: E402

YEAR_HINT_PATTERN = re.compile(
    r"wo und wann du\s*(\d{4})\s*bei einem", re.I
)
DATE_CELL_PATTERN = re.compile(r"(\d{1,2})\.(\d{1,2})\.")
KM_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*km\b", re.I)


def _extract_year(soup: BeautifulSoup) -> int:
    m = YEAR_HINT_PATTERN.search(soup.get_text(" ", strip=True))
    if m:
        return int(m.group(1))
    return date.today().year


def _parse_date_cell(text: str, year: int) -> str | None:
    m = DATE_CELL_PATTERN.search(text or "")
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _max_distance_km(text: str, config: SiteConfig) -> float | None:
    matches = KM_PATTERN.findall(text or "")
    if matches:
        return max(float(m.replace(",", ".")) for m in matches)
    from scraper_lib import guess_distance_km  # lazy, um Zirkularimport zu vermeiden
    return guess_distance_km(text, config)


def _is_internal_link(href: str | None, base_url: str) -> bool:
    if not href:
        return True
    if href.startswith(("http://", "https://")):
        from urllib.parse import urlparse
        return urlparse(base_url).netloc in urlparse(href).netloc
    return True  # relative Links sind per Definition auf der eigenen Domain


def fetch_runningcompany_events(session, config: SiteConfig, delay: float, max_pages: int, render_js: bool) -> list[Event]:
    print(f"→ Lade Seite: {config.calendar_url}")
    resp = session.get(config.calendar_url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    year = _extract_year(soup)
    print(f"  ℹ Kalenderjahr aus Seitentext erkannt: {year}")

    events: list[Event] = []
    skipped_internal = 0

    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        link_el = cells[1].find("a")
        href = link_el.get("href") if link_el else None
        if _is_internal_link(href, config.base_url):
            skipped_internal += 1
            continue  # eigenes Laufreise-/Laufcamp-/Trainingsangebot statt echtem Renn-Event

        name = (link_el or cells[1]).get_text(strip=True)
        location = cells[2].get_text(strip=True)
        distance_text = cells[3].get_text(strip=True)
        iso_date = _parse_date_cell(cells[0].get_text(strip=True), year)

        if not name or not location or not iso_date:
            continue

        combined_text = " ".join([name, distance_text])
        events.append(
            Event(
                land=guess_land(f"{location} {combined_text}") or config.default_land,
                name=name,
                standort=location,
                art1=config.default_art1,
                art2=guess_art2(combined_text, config),
                datum_start=iso_date,
                datum_ende=iso_date,
                laenge_km=_max_distance_km(distance_text, config),
                veranstalter_url=urljoin(config.calendar_url, href),
            )
        )

    print(f"  ✓ {len(events)} Event(s) gefunden ({skipped_internal} eigene "
          f"Laufreise-/Laufcamp-/Trainingsangebote übersprungen).")
    return events


CONFIG = SiteConfig(
    base_url="https://www.runningcompany.de",
    calendar_url="https://www.runningcompany.de/runners-high/laufkalender/",
    default_art1="Laufen",
    default_land="Deutschland",
    custom_fetch=fetch_runningcompany_events,
    note="runningcompany_scraper.py: robots.txt erlaubt den Zugriff. "
         "Akkordeon aus 12 Monatstabellen (kein JS-Nachladen nötig), "
         "eigene Laufreise-/Trainingsangebote werden anhand ihres "
         "(im Gegensatz zu echten Renn-Events) internen Links erkannt "
         "und übersprungen, siehe Docstring.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
