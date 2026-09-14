#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runninglife_scraper.py
=========================

Liest Lauf-Events vom Laufkalender auf
https://running.life/laufkalender/deutschland aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik:
robots.txt-Prüfung, Geocoding, Dedupe/Merge, CLI).

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt erlaubt `/laufkalender/deutschland` (gesperrt sind nur
`/xx/map/`-Pfade und `/demo-*`). Die Seite liefert die Events server-
seitig gerendert (kein React/Next.js-Nachladen, kein `--render-js`
erforderlich), und zwar in ZWEI sich ergänzenden Formen:

1. als schema.org-**ItemList** mit `itemListElement[].item` =
   `SportsEvent` - darin Name, Start-/Enddatum, Ort, Land
   (`addressCountry`) und Koordinaten (`geo`);
2. als HTML-Kacheln `.event-card-row` - darin zusätzlich die
   **einzelnen Strecken** als Chips (`.event-card-distances
   .label-distance`, z. B. "5 km", "10 km", "Halbmarathon").

`fetch_runninglife_events()` unten liest beides und führt es über die
Event-URL zusammen, denn keine der beiden Formen allein genügt:

* Das JSON-LD nennt **keine Distanzen**. Früher hat dieses Skript daher
  nur das JSON-LD ausgewertet und die Distanz aus dem Beschreibungstext
  geraten - bei einem Event mit "5 km, 10 km, Halbmarathon" landete
  dadurch nur EINE Zahl in events.json, die anderen Strecken fehlten
  komplett.
* Die Kacheln nennen weder Koordinaten noch ein normiertes Datum.

Jede erkannte Strecke wird zu einem eigenen Eintrag
(`scraper_lib.expand_competitions()`); die Kategorie (art2) wird pro
Strecke bestimmt, damit bei einer Veranstaltung mit "Halbmarathon" und
"Trailrun" nicht beide Zeilen dieselbe Kategorie bekommen.

Jede Seite enthält 20 Events, `<a rel="next">` verlinkt zur nächsten
Seite (`?page=2`, `?page=3`, ...). Für Österreich/Schweiz analog
`/laufkalender/oesterreich` bzw. `/laufkalender/schweiz` als
`CONFIG.calendar_url` in einer Kopie dieses Skripts eintragen.

Offen: Kalendertiefe
---------------------
Die Paginierung reicht aktuell bis Seite ~101, der Kalender enthält für
Deutschland also grob 2000 Events. Abgerufen werden aber nur
`scraper_lib.DEFAULT_MAX_PAGES` (= 10) Seiten, also rund 200. Das ist
bewusst noch nicht erhöht: es würde `events.json` etwa verzehnfachen,
und diese Entscheidung gehört nicht in einen Bugfix. Zum Erhöhen genügt
`--max-pages 110` bzw. ein Eintrag in `SCRIPT_EXTRA_ARGS` in
`scripts/update_events.py`. Reine Kalenderseiten, keine Detailseiten -
110 Seiten kosten bei 2 s Pause nur wenige Minuten.

Nutzung: `python3 scripts/runninglife_scraper.py --help`.
"""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    COUNTRY_CODE_MAP,
    Event,
    SiteConfig,
    expand_competitions,
    fetch_page,
    find_next_page_url,
    normalize_jsonld_event,
    parse_competitions,
    parse_jsonld_events,
    run_scraper_cli,
)

# Kachel-Selektoren, am echten Seiteninhalt kalibriert (siehe Docstring).
CARD_SELECTORS = {
    "card": ".event-card-row",
    "link": ".event-card-title-link",
    "title": ".event-card-title",
    "location": ".event-card-location",
    # Chips mit den einzelnen Strecken.
    "distances": ".event-card-distances .label-distance",
    # Länderflagge als Bild, z. B. "/img/flags/deu.svg" -> Deutschland.
    "flag": ".event-card-flag img",
}

# Dateinamen der Flaggen-Grafiken -> Land. Die Flagge ist die einzige
# Landesangabe auf der Kachel; im JSON-LD steht das Land zwar auch, aber
# nicht bei jedem Event.
FLAG_TO_LAND = {
    "deu": "Deutschland", "de": "Deutschland",
    "aut": "Österreich", "at": "Österreich",
    "che": "Schweiz", "sui": "Schweiz", "ch": "Schweiz",
}


def _land_from_flag(card) -> str | None:
    img = card.select_one(CARD_SELECTORS["flag"])
    src = (img.get("src") or "") if img else ""
    stem = src.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    return FLAG_TO_LAND.get(stem) or COUNTRY_CODE_MAP.get(stem.upper())


def parse_cards(soup: BeautifulSoup) -> dict[str, dict]:
    """Liest die Strecken-Chips und die Länderflagge je Event-Kachel.

    Schlüssel des Ergebnisses ist die Event-URL - über sie werden die
    Kacheldaten mit den JSON-LD-Events zusammengeführt (siehe Docstring).
    """
    result: dict[str, dict] = {}
    for card in soup.select(CARD_SELECTORS["card"]):
        link = card.select_one(CARD_SELECTORS["link"])
        url = (link.get("href") or "").strip() if link else ""
        if not url:
            continue
        result[url] = {
            "distances": [
                el.get_text(" ", strip=True)
                for el in card.select(CARD_SELECTORS["distances"])
            ],
            "land": _land_from_flag(card),
        }
    return result


def fetch_runninglife_events(session, config, delay, max_pages, render_js) -> list[Event]:
    """Seiten-spezifischer Abruf: JSON-LD + Kachel-Chips zusammenführen."""
    all_events: list[Event] = []
    url = config.calendar_url
    seen_urls: set[str] = set()

    for page_num in range(1, max_pages + 1):
        if not url or url in seen_urls:
            break
        seen_urls.add(url)

        print(f"→ Lade Seite {page_num}: {url} ...")
        html = fetch_page(session, url, render_js)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        cards = parse_cards(soup)
        raw_events = parse_jsonld_events(soup, url)
        page_events: list[Event] = []

        for raw in raw_events:
            event = normalize_jsonld_event(raw, config)
            card = cards.get(event.veranstalter_url or "") or {}
            if not event.land and card.get("land"):
                event.land = card["land"]

            competitions = parse_competitions(card.get("distances") or [], config)
            # Ohne Chips bleibt es bei dem einen Eintrag samt der aus dem
            # Beschreibungstext geratenen Distanz (expand_competitions gibt
            # dann das unveränderte Basis-Event zurück).
            page_events.extend(expand_competitions(event, competitions, config))

        multi = sum(1 for c in cards.values() if len(c.get("distances") or []) > 1)
        print(f"  ✓ {len(raw_events)} Event(s), davon {multi} mit mehreren "
              f"Strecken -> {len(page_events)} Einträge.")
        all_events.extend(page_events)

        url = find_next_page_url(soup, url, config)
        if url:
            time.sleep(delay)

    return all_events


CONFIG = SiteConfig(
    base_url="https://running.life",
    calendar_url="https://running.life/laufkalender/deutschland",
    default_art1="Laufen",
    custom_fetch=fetch_runninglife_events,
    note="runninglife_scraper.py: robots.txt erlaubt den Zugriff. Events "
         "kommen server-seitig als JSON-LD-ItemList plus HTML-Kacheln mit "
         "den einzelnen Strecken; kein --render-js nötig.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
