#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kilometerliebe_scraper.py
=========================

Liest den Laufkalender **Kilometerliebe** (https://www.kilometerliebe.de,
Laufen, Trail, Triathlon und Wander-Events in Deutschland) und ergänzt
die Veranstaltungen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben: „Bitte die
Webseiten die du unkritisch siehst gleich auf die Webseite aufnehmen")
---------------------------------------------------------------------
robots.txt: `Allow: /`, gesperrt nur `/api/` und Suchparameter
(`?search=`, `?q=`, `?page=`) - die Jahres- und Monatsseiten und die
Eventseiten sind frei. Impressum (Privatperson) mit dem üblichen
Urheberrechtshinweis („Inhalte und Werke … unterliegen dem deutschen
Urheberrecht"), kein Verbot des Auslesens. Übernommen werden Termine,
Orte, Distanzen und der Veranstalterlink, keine Texte.

Struktur (am 30.09.2026 kalibriert, Astro, statisch)
----------------------------------------------------
Die Monatsseiten `/2026/oktober/` … `/2027/dezember/` verlinken jeden
Termin als `/events/<slug>/` (das JSON-LD `ItemList` dort nennt nur die
ersten 50, die Links im HTML alle). Die **Eventseite** trägt ein JSON-LD `SportsEvent`
(`name`, `startDate`, `endDate`, `location` mit Ort, Bundesland, Land
und Koordinaten, `eventStatus`), eine Faktenliste `dl` (Termin, Ort,
Distanzen „5 km, 9,5 km, 18 km" oder „6 h", Kategorie Lauf/Trail/
Stadtlauf/Triathlon/Wandern, Status „Geplant") und in der Seitenleiste
den Knopf **„Event-Website"** (`a.ev-bib__action`, ein externer Link) -
die Veranstalterseite (Datenregel 2). Bei Triathlons stehen die Formate
in der Beschreibung („Angebotene Wertungen: Olympische Distanz (…),
Mitteldistanz (…)"). Im September 2026: 1.287 Eventseiten in der
Sitemap, 378 Laufevents, 78 Triathlons, 45 Wander-Events für 2026/27.

Was daraus wird
---------------
* Nur Kategorien Lauf/Trail/Stadtlauf/Naturlauf/Firmenlauf (Laufen) und
  Triathlon; **Wandern (Megamarsch, Mammutmarsch) fällt weg** - das
  ist kein Lauf. Abgesagte Termine (Status) fallen weg.
* Je Distanz eine Zeile (Datenregel 1), „6 h" als Zeitrennen
  (`dauer_h`, Datenregel 8). Triathlon: je Format eine Zeile ohne
  Kilometer, das Format im Label (wie `fsieben_scraper.py`), „Duathlon"
  im Namen → Kategorie Duathlon.
* Ort, Land und Koordinaten aus dem JSON-LD (kein Nominatim).
* `veranstalter_url`: der Event-Website-Link; fehlt er, die
  Kilometerliebe-Seite (`PORTAL_DOMAINS`).
* Gelesen werden nur Termine ab heute (Jahresseiten des laufenden und
  des nächsten Jahres); `--max-details N` begrenzt die Eventseiten.

Nutzung: `python3 scripts/kilometerliebe_scraper.py --help`
(Testlauf: `--dry-run --max-details 20`).
"""

from pathlib import Path
import json
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
    guess_art2,
    parse_duration_h,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://www.kilometerliebe.de"
LAND = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
KATEGORIE_LAUFEN = {"lauf", "trail", "stadtlauf", "naturlauf", "firmenlauf", "ultramarathon", "marathon", "halbmarathon", "laufen"}
KATEGORIE_TRIATHLON = {"triathlon", "duathlon"}
FORMATE = [
    (re.compile(r"super.?sprint", re.I), "Super-Sprint"),
    (re.compile(r"sprint|volks|jedermann", re.I), "Sprint"),
    (re.compile(r"olympisch|kurzdistanz", re.I), "Olympisch"),
    (re.compile(r"mitteldistanz|70\.3|halbdistanz", re.I), "Mitteldistanz"),
    (re.compile(r"langdistanz|140\.6|ironman", re.I), "Langdistanz"),
]
_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*km\b", re.I)
_STUNDEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*h\b", re.I)


MONATE = ["januar", "februar", "maerz", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "dezember"]


def event_links(html: str, ab: str | None = None) -> list[tuple[str, str, str]]:
    """(Datum, Name, Adresse) je Termin einer Monatsseite. Gelesen werden
    die Karten im HTML (`<time datetime>` + Link `/events/<slug>/`) - das
    JSON-LD `ItemList` der Seite nennt nur die ersten 50 Termine (Oktober
    2026: 126 Termine, 50 im ItemList), die Seite selbst alle. Mit `ab`
    (ISO-Datum) bleiben nur Termine ab diesem Tag - die Eventseiten der
    vergangenen muss niemand abrufen."""
    html = _utf8(html)
    links: list[tuple[str, str, str]] = []
    gesehen: set[str] = set()
    teile = re.split(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})[^"]*"', html)
    for i in range(1, len(teile) - 1, 2):
        datum, block = teile[i], teile[i + 1]
        m = re.search(r'href="((?:https://www\.kilometerliebe\.de)?/events/([^"/?#]+)/?)"[^>]*>(.*?)</a>', block, re.S)
        if not m or m.group(2) in ("map", "nearby"):
            continue
        url = urljoin(BASE_URL, m.group(1).split("#")[0])
        if url in gesehen or (ab and datum < ab):
            continue
        gesehen.add(url)
        name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(3))).strip()
        links.append((datum, name, url))
    return links


def _utf8(html: str) -> str:
    """Die Seite liefert UTF-8 ohne Zeichensatz im Header; `fetch_page()`
    (requests) rät dann Latin-1, und aus „Köln" wird „KÃ¶ln"."""
    if "Ã" in html or "â€" in html:
        try:
            return html.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return html
    return html


def parse_eventseite(html: str) -> dict:
    soup = BeautifulSoup(_utf8(html), "html.parser")
    e: dict = {}
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            daten = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        for obj in daten.get("@graph", [daten]) if isinstance(daten, dict) else []:
            if obj.get("@type") in ("SportsEvent", "Event"):
                loc = obj.get("location") or {}
                adr = loc.get("address") or {}
                geo = loc.get("geo") or {}
                e.update(name=obj.get("name"), datum_start=obj.get("startDate"), datum_ende=obj.get("endDate"),
                         beschreibung=obj.get("description") or "", ort=adr.get("addressLocality") or loc.get("name"),
                         region=adr.get("addressRegion"), land_code=adr.get("addressCountry"),
                         lat=geo.get("latitude"), lon=geo.get("longitude"), status=obj.get("eventStatus") or "")
    for dl in soup.select("dl"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            k, v = dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)
            if k == "Kategorie":
                e["kategorie"] = v
            elif k in ("Distanzen", "Distanz"):
                e["distanzen"] = v
            elif k == "Status":
                e["status_text"] = v
    for a in soup.select("a.ev-bib__action[href]"):
        href = a["href"].strip()
        if href.startswith("http") and "kilometerliebe.de" not in href and not a.get("download"):
            e["veranstalter_url"] = href
            break
    return e


def _distanzen(text: str) -> list[tuple[float | None, float | None, str]]:
    """„5 km, 9,5 km, 18 km" -> [(5, None, '5 km'), …]; „6 h" -> [(None, 6, '6 h')]."""
    ergebnis = []
    # Getrennt wird an „·" und an Komma PLUS Leerzeichen - „9,5 km" ist
    # ein Dezimalkomma, kein Trenner.
    for teil in re.split(r"\s*·\s*|,\s+", text or ""):
        teil = teil.strip()
        if not teil:
            continue
        m = _KM.search(teil)
        if m:
            ergebnis.append((round_km(float(m.group(1).replace(",", "."))), None, teil))
            continue
        m = _STUNDEN.search(teil)
        if m:
            ergebnis.append((None, float(m.group(1).replace(",", ".")), teil))
    return ergebnis


def events_aus_seite(e: dict, seite_url: str, config: SiteConfig) -> tuple[list[Event], str | None]:
    if not e.get("name") or not e.get("datum_start"):
        return [], "ohne Name oder Datum"
    if "Cancelled" in (e.get("status") or "") or re.search(r"abgesagt", e.get("status_text") or "", re.I):
        return [], "abgesagt"
    kat = (e.get("kategorie") or "").strip().lower()
    if kat in KATEGORIE_TRIATHLON:
        art1 = "Triathlon"
    elif kat in KATEGORIE_LAUFEN:
        art1 = "Laufen"
    elif kat == "wandern":
        return [], "Wandern"
    else:
        return [], f"Kategorie {kat or '?'} unbekannt"
    land = LAND.get(e.get("land_code") or "DE")
    if not land:
        return [], f"Land {e.get('land_code')}"
    if not e.get("ort"):
        return [], "kein Ort"
    basis = dict(land=land, name=e["name"].strip(), standort=e["ort"], lat=e.get("lat"), lon=e.get("lon"),
                 art1=art1, datum_start=e["datum_start"], datum_ende=e.get("datum_ende") or e["datum_start"],
                 veranstalter_url=e.get("veranstalter_url") or seite_url)
    events: list[Event] = []
    if art1 == "Triathlon":
        text = f"{e['name']} {e.get('beschreibung', '')}"
        art2 = "Duathlon" if re.search(r"duathlon", e["name"], re.I) else ("Cross" if re.search(r"\bcross", e["name"], re.I) else "Straße")
        formate = [label for muster, label in FORMATE if muster.search(e.get("beschreibung", "").split("Angebotene Wertungen:")[-1])]
        if not formate:
            ev = Event(**basis)
            ev.art2 = art2
            return [ev], None
        for f in formate:
            ev = Event(**basis, wettbewerb=f)
            ev.art2 = art2
            events.append(ev)
        return events, None
    strecken = _distanzen(e.get("distanzen") or "")
    if not strecken:
        ev = Event(**basis)
        ev.art2 = guess_art2(f"{e['name']} {kat}", config, "Laufen")
        return [ev], None
    for km, stunden, label in strecken:
        ev = Event(**basis, laenge_km=km, dauer_h=stunden, wettbewerb=label)
        ev.art2 = guess_art2(f"{e['name']} {kat}", config, "Laufen")
        events.append(ev)
    return events, None


def fetch_kilometerliebe_events(session, config, delay, max_pages, render_js) -> list[Event]:
    heute = date.today()
    links: list[tuple[str, str]] = []
    # Monatsseiten ab dem laufenden Monat bis Dezember des nächsten Jahres -
    # die Jahresseite führt auch die vergangenen Termine, deren Eventseiten
    # wir nicht abrufen müssen.
    monate = [(heute.year, m) for m in range(heute.month, 13)] + [(heute.year + 1, m) for m in range(1, 13)]
    for jahr, monat in monate:
        url = f"{BASE_URL}/{jahr}/{MONATE[monat - 1]}/"
        html = fetch_page(session, url, render_js=False)
        if not html:
            continue
        neue = [l for l in event_links(html, ab=heute.isoformat()) if l[2] not in {u for _, _, u in links}]
        print(f"  {jahr}-{monat:02d}: {len(neue)} Termine")
        links.extend(neue)
        time.sleep(delay)
    print(f"→ {len(links)} Termine ab {heute.isoformat()}.")
    if config.max_details:
        links = links[: config.max_details]
    events: list[Event] = []
    gruende: dict[str, int] = {}
    for i, (_, name, url) in enumerate(links, 1):
        time.sleep(delay)
        html = fetch_page(session, url, render_js=False)
        if not html:
            gruende["nicht abrufbar"] = gruende.get("nicht abrufbar", 0) + 1
            continue
        seite = parse_eventseite(html)
        if seite.get("datum_start") and seite["datum_start"] < heute.isoformat():
            gruende["vergangen"] = gruende.get("vergangen", 0) + 1
            continue
        neue, grund = events_aus_seite(seite, url, config)
        if grund:
            gruende[grund] = gruende.get(grund, 0) + 1
            continue
        events.extend(neue)
        if i % 50 == 0:
            print(f"  … {i}/{len(links)} Eventseiten, {len(events)} Zeilen")
    for grund, n in sorted(gruende.items(), key=lambda x: -x[1]):
        print(f"  ({n}× übersprungen: {grund})")
    print(f"\n→ {len(events)} Zeilen aus {len(links)} Eventseiten.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=f"{BASE_URL}/{date.today().year}/",
    default_art1="Laufen",
    default_land="Deutschland",
    custom_fetch=fetch_kilometerliebe_events,
    note="kilometerliebe_scraper.py: Laufkalender Kilometerliebe (Deutschland); Eventseiten mit "
         "JSON-LD und Event-Website-Link, Wander-Events fallen weg.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
