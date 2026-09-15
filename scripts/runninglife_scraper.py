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

Detailseiten: offizielle Veranstalter-Seite + genaue Strecken
--------------------------------------------------------------
Zusätzlich wird die Detailseite jedes Events abgerufen (`--no-details`
schaltet das ab, `--max-details N` begrenzt es für Testläufe). Sie
liefert zwei Dinge, die auf der Kalenderseite fehlen:

* **Die offizielle Seite des Laufs**, als Button "Webseite" (z. B.
  https://www.braunenberg-lauf.de/ beim BraunenBerg-Lauf). Als
  `veranstalter_url` stand vorher die running.life-Seite - ein Portallink,
  obwohl die Quelle die offizielle Seite kennt. Der daneben liegende
  Button "Anmeldung" zeigt auf ein Anmeldeportal (my.raceresult.com o. Ä.)
  und wird nur als Notlösung genommen, wenn es keinen "Webseite"-Button
  gibt.
* **Die genauen Streckenlängen**, als Aufzählung im Beschreibungstext
  hinter einem einleitenden Absatz ("Die angebotenen Strecken:"). Beim
  BraunenBerg-Lauf stehen dort 32 km, 14,6 km und 8,2 km - die
  Zusammenfassungs-Karten derselben Seite zeigen dafür nur gerundete
  "32 km / 15 km / 8 km", und die Chips der Kalenderseite ebenso. Nur das
  <ul> direkt hinter diesem Einleitungssatz wird gelesen: eine beliebige
  Aufzählung im Text (Verpflegungsstellen "bei etwa 9 km, 16 km, 24 km")
  würde sonst Phantom-Strecken erzeugen. Kinder-/Bambiniläufe in der
  Liste sind in METERN angegeben ("500 m") und fallen dadurch von allein
  heraus.

Sind die Chips der Kalenderseite vollständiger als eine nur gerundete
Kartenliste, gewinnen die Chips - beim Kraichgau-Lauf etwa nennen die
Karten 10 km und 5 km, die Chips zusätzlich Halbmarathon und Marathon.

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
import re
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

# Selektoren auf der DETAILSEITE eines Events (siehe Docstring, Abschnitt
# "Detailseiten"). Am echten Seiteninhalt kalibriert.
DETAIL_SELECTORS = {
    # Die Buttons "Webseite" und "Anmeldung" über der Beschreibung. Der
    # "Webseite"-Button zeigt auf die OFFIZIELLE Seite des Laufs.
    "action_btn": "a.race-detail-action-btn",
    # Beschreibungstext; darin steht die genaue Streckenliste als <ul>
    # hinter einem einleitenden Absatz ("Die angebotenen Strecken:").
    "description": ".markdown-text",
    # Zusammenfassungs-Karten. Nur Fallback: sie zeigen GERUNDETE Werte
    # ("15 km" für 14,6 km) und sind nicht immer vollständig.
    "distance_cards": "div.text-primary-500.font-medium.text-2xl",
}

# Einleitungssatz vor der Streckenliste, z. B. "Die angebotenen Strecken:"
# oder "Es werden zwei offizielle Distanzen angeboten:". Nur das <ul>
# direkt dahinter wird als Wettbewerbsliste gelesen - eine beliebige
# Aufzählung im Beschreibungstext (Verpflegungsstellen "bei etwa 9 km,
# 16 km, 24 km") würde sonst Phantom-Strecken erzeugen.
DISTANCE_LIST_INTRO = re.compile(
    r"(strecken|distanzen|wettbewerbe|läufe|bewerbe)\b[^:]{0,60}:\s*$", re.I
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


def parse_detail_page(html: str) -> dict:
    """Liest offizielle Veranstalter-Seite und genaue Streckenliste aus
    einer Event-Detailseite.

    Rückgabe: `official_url` (falls vorhanden) und `competitions` (Liste
    von Rohtexten). Fehlende Teile fehlen im Dict, statt einen Fehler zu
    werfen - die Detailseiten sind nicht alle gleich vollständig.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    # "Webseite" ist die offizielle Seite des Laufs. Der daneben liegende
    # "Anmeldung"-Button zeigt auf ein Anmeldeportal (my.raceresult.com
    # o. Ä.) und ist NICHT die offizielle Seite - deshalb nur als
    # Notlösung, wenn es keinen "Webseite"-Button gibt.
    fallback_url = None
    for link in soup.select(DETAIL_SELECTORS["action_btn"]):
        href = (link.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        label = link.get_text(" ", strip=True).casefold()
        if label.startswith("webseite"):
            result["official_url"] = href
            break
        if label.startswith("anmeldung") and fallback_url is None:
            fallback_url = href
    if "official_url" not in result and fallback_url:
        result["official_url"] = fallback_url

    description = soup.select_one(DETAIL_SELECTORS["description"])
    competitions: list[str] = []
    if description:
        for paragraph in description.find_all("p"):
            text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True))
            if not DISTANCE_LIST_INTRO.search(text):
                continue
            ul = paragraph.find_next_sibling("ul")
            if ul:
                competitions = [
                    re.sub(r"\s+", " ", li.get_text(" ", strip=True))
                    for li in ul.find_all("li", recursive=False)
                ]
                break

    if competitions:
        result["competitions"] = competitions
    else:
        # Fallback: die gerundeten Zusammenfassungs-Karten.
        cards = [
            el.get_text(" ", strip=True)
            for el in soup.select(DETAIL_SELECTORS["distance_cards"])
        ]
        if cards:
            result["competitions"] = cards
            result["rounded"] = True

    return result


def fetch_runninglife_events(session, config, delay, max_pages, render_js) -> list[Event]:
    """Seiten-spezifischer Abruf: JSON-LD + Kachel-Chips zusammenführen."""
    all_events: list[Event] = []
    url = config.calendar_url
    seen_urls: set[str] = set()
    details_fetched = official_links = expanded = 0

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
            detail_url = event.veranstalter_url  # JSON-LD `url` = running.life-Seite
            card = cards.get(detail_url or "") or {}
            if not event.land and card.get("land"):
                event.land = card["land"]

            # Strecken zunächst aus den Chips der Kalenderseite.
            distances = list(card.get("distances") or [])

            if config.fetch_details and detail_url and (
                not config.max_details or details_fetched < config.max_details
            ):
                detail = fetch_detail(session, detail_url, delay)
                details_fetched += 1
                if detail.get("official_url"):
                    event.veranstalter_url = detail["official_url"]
                    official_links += 1
                # Die Streckenliste im Beschreibungstext ist genauer als die
                # Chips: sie nennt 14,6 km statt der gerundeten 15 km. Die
                # Chips sind dafür manchmal vollständiger, deshalb gewinnt
                # die längere der beiden Listen bei gerundeten Angaben.
                found = detail.get("competitions") or []
                if found and not (detail.get("rounded") and len(distances) > len(found)):
                    distances = found

            competitions = parse_competitions(distances, config)
            # Ohne erkannte Strecken bleibt es bei dem einen Eintrag samt der
            # aus dem Beschreibungstext geratenen Distanz (expand_competitions
            # gibt dann das unveränderte Basis-Event zurück).
            variants = expand_competitions(event, competitions, config)
            if len(variants) > 1:
                expanded += 1
            page_events.extend(variants)

        print(f"  ✓ {len(raw_events)} Event(s) -> {len(page_events)} Einträge.")
        all_events.extend(page_events)

        url = find_next_page_url(soup, url, config)
        if url:
            time.sleep(delay)

    print(f"\n→ {details_fetched} Detailseite(n) abgerufen, davon "
          f"{official_links} mit offizieller Veranstalter-Seite; "
          f"{expanded} Veranstaltung(en) in mehrere Wettbewerbe aufgeteilt.")
    return all_events


def fetch_detail(session, url: str, delay: float) -> dict:
    """Ruft eine Event-Detailseite ab und parst sie. Ein Fehlschlag ist
    kein Abbruch: das Event bleibt dann mit den Angaben der Kalenderseite
    erhalten."""
    time.sleep(delay)
    html = fetch_page(session, url, render_js=False)
    if html is None:
        return {}
    return parse_detail_page(html)


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
