#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
laufkalender_scraper.py
========================

Liest Lauf-Events vom Laufkalender auf https://laufen.de/laufkalender aus
und ergänzt sie in `events.json` – im selben Format wie die bestehenden
Events, ohne Duplikate zu erzeugen (Abgleich über Name + Startdatum).

WICHTIG – bitte vor dem ersten produktiven Lauf lesen
-------------------------------------------------------
Dieses Skript wurde NICHT gegen die echte Seite getestet: In der Umgebung,
in der es geschrieben wurde, ist der Netzwerkzugriff auf laufen.de durch
eine Firewall-/Proxy-Richtlinie blockiert (bestätigt: robots.txt und die
Kalenderseite selbst waren nicht erreichbar). Führe es deshalb zunächst
mit `--dry-run --max-pages 1` aus und wirf einen Blick auf die Ausgabe,
bevor du events.json wirklich überschreiben lässt.

robots.txt-Prüfung
-------------------
Das Skript lädt robots.txt bei jedem Lauf live von laufen.de und prüft
per `urllib.robotparser`, ob unser User-Agent den Pfad `/laufkalender`
crawlen darf. Ist das nicht der Fall, bricht das Skript sofort ab, OHNE
irgendeine Anfrage an die Kalenderseite zu schicken. Einen evtl. in
robots.txt angegebenen Crawl-Delay respektiert es automatisch.

Parsing-Strategie
-------------------
1. Zuerst wird nach eingebetteten `<script type="application/ld+json">`
   Blöcken mit schema.org-`Event`/`SportsEvent`-Daten gesucht. Viele
   Kalenderseiten liefern darüber strukturierte, stabile Daten – falls
   laufen.de das tut, sollte das Skript "out of the box" funktionieren.
2. Findet sich kein JSON-LD, greift ein HTML-Fallback (`parse_html_fallback`)
   mit CSS-Selektoren. Diese sind als Platzhalter markiert (`# TODO:
   ANPASSEN`) und müssen anhand des echten Seitenquelltexts kalibriert
   werden (Browser: Rechtsklick -> "Seitenquelltext anzeigen", oder besser:
   Tab "Netzwerk" der Entwicklertools öffnen und prüfen, ob die Events per
   JSON von einer API-Route nachgeladen werden – das wäre deutlich
   zuverlässiger zu parsen als HTML und sollte bevorzugt werden, falls
   vorhanden).

Nutzung
-------
    pip install requests beautifulsoup4 geopy

    # Testlauf ohne events.json zu verändern:
    python3 scripts/laufkalender_scraper.py --dry-run --max-pages 1

    # Echter Lauf, ergänzt events.json im Repo-Root:
    python3 scripts/laufkalender_scraper.py

Optionen: siehe `python3 scripts/laufkalender_scraper.py --help`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

BASE_URL = "https://laufen.de"
CALENDAR_PATH = "/laufkalender"
CALENDAR_URL = urljoin(BASE_URL, CALENDAR_PATH)

# Höflicher, ehrlicher User-Agent (kein Fake-Browser-UA) – erleichtert es
# dem Seitenbetreiber, uns bei Bedarf zu blockieren oder zu kontaktieren.
USER_AGENT = (
    "EnduranceEventsBot/1.0 "
    "(+https://antdon930.github.io/Enduranceevents/; "
    "privater, nicht-kommerzieller Kalenderabgleich; Kontakt siehe Repo)"
)

DEFAULT_REQUEST_DELAY_SECONDS = 2.0  # Fallback, falls robots.txt keinen Crawl-Delay nennt
DEFAULT_MAX_PAGES = 20

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON_PATH = REPO_ROOT / "events.json"
GEOCODE_CACHE_PATH = REPO_ROOT / "scripts" / ".geocode_cache.json"

# TODO: ANPASSEN, falls die Pagination anders aufgebaut ist (z. B. über
# einen Query-Parameter wie ?page=2 statt eines "Weiter"-Links). Das
# Skript folgt zunächst <a rel="next"> und versucht danach ein paar
# gängige Klassennamen als Fallback.
NEXT_PAGE_SELECTORS = [
    'a[rel="next"]',
    "a.pagination-next",
    "a.next",
    'a[aria-label="Nächste Seite"]',
    'a[aria-label="Weiter"]',
]

# TODO: ANPASSEN an die echte Seitenstruktur, falls kein JSON-LD gefunden
# wird. `event_card` ist der Selektor für eine einzelne Veranstaltung in
# der Liste; die übrigen Selektoren sind relativ dazu (BeautifulSoup
# `.select_one(...)` innerhalb der Karte).
HTML_FALLBACK_SELECTORS = {
    "event_card": "article.event-card, li.event-item, div.event-teaser",
    "name": "h2, h3, .event-title",
    "date": "time, .event-date",
    "location": ".event-location, .event-city",
    "link": "a",
    "category": ".event-category, .event-type",
    "distance": ".event-distance",
}

LAND_KEYWORDS = {
    "deutschland": "Deutschland", "germany": "Deutschland", "de": "Deutschland",
    "österreich": "Österreich", "austria": "Österreich", "at": "Österreich",
    "schweiz": "Schweiz", "switzerland": "Schweiz", "ch": "Schweiz",
}

# Bekannte PLZ-Präfixe/Länder-Codes, falls das Land nicht im Text steht.
COUNTRY_CODE_MAP = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}

# Zuordnung Stichwort -> Kategorie (art2), passend zur im Projekt
# verwendeten Taxonomie für Laufen: Straße, Trail, Bahn, Berg, Cross, Hindernis.
ART2_KEYWORDS = [
    (re.compile(r"halbmarathon|marathon|stadtlauf|straßenlauf|city ?run|\bstraße\b", re.I), "Straße"),
    (re.compile(r"trail|geländelauf|ultratrail|mountainrun(?!.*berg)", re.I), "Trail"),
    (re.compile(r"berglauf|bergrennen|mountain run|gipfel", re.I), "Berg"),
    (re.compile(r"crosslauf|\bcross\b", re.I), "Cross"),
    (re.compile(r"hindernislauf|obstacle|ocr|spartan|tough mudder", re.I), "Hindernis"),
    (re.compile(r"bahn(meeting)?|leichtathletik.?meeting", re.I), "Bahn"),
]
DEFAULT_ART2 = "Straße"  # häufigster Fall (Stadt-/Straßenläufe), falls nichts erkannt wird

GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
}

# Bekannte offizielle Distanzen (km) für die Umwandlung von Textangaben
# wie "Marathon" oder "Halbmarathon" in eine Zahl, falls keine explizite
# km-Angabe gefunden wird.
KNOWN_DISTANCES_KM = {
    "marathon": 42.2,
    "halbmarathon": 21.1,
    "10 km": 10.0,
    "5 km": 5.0,
}


# --------------------------------------------------------------------------
# Datenmodell (Feldreihenfolge bewusst identisch zu events.json)
# --------------------------------------------------------------------------

@dataclass
class Event:
    land: str | None = None
    name: str | None = None
    standort: str | None = None
    lat: float | None = None
    lon: float | None = None
    art1: str = "Laufen"
    art2: str | None = None
    datum_start: str | None = None  # YYYY-MM-DD
    datum_ende: str | None = None   # YYYY-MM-DD
    anmeldeschluss: str | None = None
    laenge_km: float | None = None
    veranstalter_url: str | None = None

    def is_valid(self) -> bool:
        """Minimalanforderung, damit ein Event überhaupt brauchbar ist."""
        return bool(self.name and self.datum_start and self.standort)

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        # Optionale Felder, die fehlen, nicht mit "null" in die JSON
        # schreiben, sondern ganz weglassen (wie im bisherigen events.json
        # üblich, siehe README: "fehlt es bei einem Event, zeigt die
        # Tabelle dort '–'").
        return {k: v for k, v in d.items() if v is not None}


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------

def check_robots(session: requests.Session) -> float:
    """Prüft robots.txt live gegen CALENDAR_PATH für unseren User-Agent.

    Gibt die zu verwendende Pause zwischen Requests zurück (Sekunden).
    Bricht das Programm ab, falls der Pfad gesperrt ist.
    """
    robots_url = urljoin(BASE_URL, "/robots.txt")
    print(f"→ Lade robots.txt von {robots_url} ...")
    try:
        resp = session.get(robots_url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            # Per robots.txt-Konvention (RFC 9309 §2.3.1.3): fehlt
            # robots.txt (404), gelten keine Einschränkungen - Zugriff
            # ist dann uneingeschränkt erlaubt. Kein Abbruch.
            print(
                f"ℹ robots.txt liefert 404 (nicht vorhanden) unter {robots_url}. "
                "Laut robots.txt-Konvention bedeutet das: keine Einschränkungen "
                "angegeben, Zugriff ist erlaubt. Fahre fort."
            )
            return DEFAULT_REQUEST_DELAY_SECONDS
        print(
            f"\n❌ robots.txt konnte nicht geladen werden: {exc}\n"
            "   Breche ab, ohne events.json zu verändern."
        )
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(
            f"\n❌ robots.txt konnte nicht geladen werden: {exc}\n"
            "   Mögliche Ursachen: kein Internetzugriff von hier aus, ein "
            "Netzwerk-/Firewall-Proxy blockiert die Domain, oder laufen.de "
            "ist gerade nicht erreichbar. Breche ab, ohne events.json zu "
            "verändern."
        )
        sys.exit(1)

    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(resp.text.splitlines())

    print("---- robots.txt (Volltext) ----")
    print(resp.text.strip())
    print("--------------------------------")

    allowed = rp.can_fetch(USER_AGENT, CALENDAR_URL)
    if not allowed:
        print(
            f"\n❌ robots.txt verbietet unserem User-Agent den Zugriff auf "
            f"{CALENDAR_PATH}. Breche ab, ohne die Kalenderseite abzurufen."
        )
        sys.exit(1)

    delay = rp.crawl_delay(USER_AGENT)
    if delay is None:
        # request_rate ist die ältere robots.txt-Direktive (Requests/Sekunden)
        rate = rp.request_rate(USER_AGENT)
        if rate is not None and rate.requests:
            delay = rate.seconds / rate.requests
    delay = max(float(delay or 0), DEFAULT_REQUEST_DELAY_SECONDS)

    print(f"✅ robots.txt erlaubt {CALENDAR_PATH}. Verwende {delay:.1f}s Pause zwischen Requests.\n")
    return delay


# --------------------------------------------------------------------------
# Hilfsfunktionen: Datum, Land, Kategorie, Distanz
# --------------------------------------------------------------------------

def parse_german_date(text: str) -> str | None:
    """Wandelt diverse deutsche Datumsformate in ISO 'YYYY-MM-DD' um.

    Unterstützt u. a. "27.09.2026", "27. September 2026" und ISO-Strings.
    Gibt None zurück, wenn nichts erkannt werden konnte.
    """
    if not text:
        return None
    text = text.strip()

    # Bereits ISO? (z. B. aus JSON-LD "startDate": "2026-09-27")
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        try:
            return date(*(int(g) for g in iso_match.groups())).isoformat()
        except ValueError:
            pass

    # "27.09.2026" / "27.9.2026"
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

    # "27. September 2026"
    m = re.search(r"\b(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})\b", text)
    if m:
        d = int(m.group(1))
        month_name = m.group(2).lower()
        y = int(m.group(3))
        mo = GERMAN_MONTHS.get(month_name)
        if mo:
            try:
                return date(y, mo, d).isoformat()
            except ValueError:
                return None

    return None


def guess_land(text: str) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    for keyword, land in LAND_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return land
    # Schweizer PLZ (4-stellig) sind mehrdeutig, daher hier nicht geraten.
    # Deutsche PLZ (5-stellig) als schwaches Signal:
    if re.search(r"\b\d{5}\b", text):
        return "Deutschland"
    return None


def guess_art2(text: str) -> str:
    for pattern, kategorie in ART2_KEYWORDS:
        if pattern.search(text or ""):
            return kategorie
    return DEFAULT_ART2


def guess_distance_km(text: str) -> float | None:
    if not text:
        return None
    # explizite Kilometerangabe, z. B. "21,1 km" oder "10 km"
    m = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b", text, re.I)
    if m:
        return float(m.group(1).replace(",", "."))
    lowered = text.lower()
    for keyword, km in KNOWN_DISTANCES_KM.items():
        if keyword in lowered:
            return km
    return None


# --------------------------------------------------------------------------
# Geocoding (Stadt -> lat/lon), mit lokalem Cache
# --------------------------------------------------------------------------

class Geocoder:
    """Dünner Wrapper um geopy/Nominatim mit Platte-Cache, damit wiederholte
    Läufe nicht jedes Mal dieselben Städte erneut anfragen (Nominatim erlaubt
    laut Nutzungsbedingungen max. 1 Request/Sekunde)."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache: dict[str, list[float] | None] = {}
        if cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.cache = {}
        self._geolocator = None

    def _ensure_geolocator(self):
        if self._geolocator is None:
            from geopy.geocoders import Nominatim  # Lazy-Import, optional
            self._geolocator = Nominatim(user_agent=USER_AGENT)

    def geocode(self, standort: str, land: str | None) -> tuple[float, float] | None:
        query = f"{standort}, {land}" if land else standort
        if query in self.cache:
            cached = self.cache[query]
            return tuple(cached) if cached else None

        try:
            self._ensure_geolocator()
            location = self._geolocator.geocode(query, timeout=10)
        except Exception as exc:  # geopy kann diverse Netzwerkfehler werfen
            print(f"  ⚠ Geocoding fehlgeschlagen für '{query}': {exc}")
            location = None
        finally:
            time.sleep(1.0)  # Nominatim-Nutzungsbedingungen: max. 1 req/s

        result = (location.latitude, location.longitude) if location else None
        self.cache[query] = list(result) if result else None
        self._save()
        return result

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# --------------------------------------------------------------------------
# Parsing: JSON-LD (bevorzugt)
# --------------------------------------------------------------------------

def parse_jsonld_events(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Sucht nach schema.org Event/SportsEvent-Daten in <script
    type="application/ld+json">-Blöcken. Liefert rohe Dicts (noch nicht
    auf unser events.json-Schema normalisiert)."""
    raw_events: list[dict] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            # @graph-Wrapper auflösen (häufig bei größeren JSON-LD-Blöcken)
            graph = item.get("@graph")
            sub_candidates = graph if isinstance(graph, list) else [item]
            for sub in sub_candidates:
                if not isinstance(sub, dict):
                    continue
                types = sub.get("@type")
                types = types if isinstance(types, list) else [types]
                if any(t in ("Event", "SportsEvent") for t in types if t):
                    raw_events.append({"_source": "jsonld", "_page_url": page_url, **sub})
    return raw_events


def normalize_jsonld_event(raw: dict) -> Event:
    name = raw.get("name")

    location = raw.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") if isinstance(location, dict) else None
    if isinstance(address, dict):
        standort = address.get("addressLocality") or location.get("name")
        land_raw = address.get("addressCountry")
        if isinstance(land_raw, dict):
            land_raw = land_raw.get("name") or land_raw.get("id")
        land = COUNTRY_CODE_MAP.get(str(land_raw).upper(), None) or guess_land(str(land_raw or ""))
    else:
        standort = location.get("name") if isinstance(location, dict) else None
        land = None

    if not land:
        land = guess_land(f"{standort or ''} {name or ''}")

    lat = lon = None
    geo = location.get("geo") if isinstance(location, dict) else None
    if isinstance(geo, dict):
        try:
            lat = float(geo.get("latitude"))
            lon = float(geo.get("longitude"))
        except (TypeError, ValueError):
            lat = lon = None

    datum_start = parse_german_date(str(raw.get("startDate") or ""))
    datum_ende = parse_german_date(str(raw.get("endDate") or "")) or datum_start

    description = " ".join(
        str(raw.get(k) or "") for k in ("description", "name")
    )
    art2 = guess_art2(description)
    laenge_km = guess_distance_km(description)

    veranstalter_url = raw.get("url") or raw.get("_page_url")

    return Event(
        land=land,
        name=name.strip() if name else None,
        standort=standort.strip() if standort else None,
        lat=lat,
        lon=lon,
        art2=art2,
        datum_start=datum_start,
        datum_ende=datum_ende,
        laenge_km=laenge_km,
        veranstalter_url=veranstalter_url,
    )


# --------------------------------------------------------------------------
# Parsing: HTML-Fallback (Platzhalter-Selektoren, siehe Kopf-Kommentar)
# --------------------------------------------------------------------------

def parse_html_fallback(soup: BeautifulSoup, page_url: str) -> list[Event]:
    events: list[Event] = []
    cards = soup.select(HTML_FALLBACK_SELECTORS["event_card"])
    if not cards:
        return events

    for card in cards:
        name_el = card.select_one(HTML_FALLBACK_SELECTORS["name"])
        date_el = card.select_one(HTML_FALLBACK_SELECTORS["date"])
        loc_el = card.select_one(HTML_FALLBACK_SELECTORS["location"])
        link_el = card.select_one(HTML_FALLBACK_SELECTORS["link"])
        cat_el = card.select_one(HTML_FALLBACK_SELECTORS["category"])
        dist_el = card.select_one(HTML_FALLBACK_SELECTORS["distance"])

        name = name_el.get_text(strip=True) if name_el else None
        date_text = (
            date_el.get("datetime") if date_el and date_el.has_attr("datetime") else None
        ) or (date_el.get_text(strip=True) if date_el else None)
        standort = loc_el.get_text(strip=True) if loc_el else None
        href = link_el.get("href") if link_el else None
        category_text = cat_el.get_text(strip=True) if cat_el else ""
        distance_text = dist_el.get_text(strip=True) if dist_el else ""

        datum_start = parse_german_date(date_text or "")
        combined_text = " ".join([name or "", category_text, distance_text])

        events.append(
            Event(
                land=guess_land(f"{standort or ''} {combined_text}"),
                name=name,
                standort=standort,
                art2=guess_art2(combined_text),
                datum_start=datum_start,
                datum_ende=datum_start,
                laenge_km=guess_distance_km(combined_text),
                veranstalter_url=urljoin(page_url, href) if href else None,
            )
        )
    return events


# --------------------------------------------------------------------------
# Seiten abrufen (mit Pagination)
# --------------------------------------------------------------------------

def find_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    for selector in NEXT_PAGE_SELECTORS:
        link = soup.select_one(selector)
        if link and link.get("href"):
            return urljoin(current_url, link["href"])
    return None


def fetch_all_events(
    session: requests.Session, delay: float, max_pages: int
) -> list[Event]:
    all_events: list[Event] = []
    url = CALENDAR_URL
    seen_urls: set[str] = set()

    for page_num in range(1, max_pages + 1):
        if not url or url in seen_urls:
            break
        seen_urls.add(url)

        print(f"→ Lade Seite {page_num}: {url}")
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"  ❌ Abbruch: {url} konnte nicht geladen werden ({exc}).")
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        raw_jsonld = parse_jsonld_events(soup, url)
        if raw_jsonld:
            print(f"  ✓ {len(raw_jsonld)} Event(s) über JSON-LD gefunden.")
            page_events = [normalize_jsonld_event(r) for r in raw_jsonld]
        else:
            print("  ⚠ Kein JSON-LD gefunden – versuche HTML-Fallback "
                  "(Selektoren ggf. anpassen, siehe TODOs im Skript).")
            page_events = parse_html_fallback(soup, url)
            print(f"  ✓ {len(page_events)} Event(s) über HTML-Fallback gefunden.")

        all_events.extend(page_events)

        next_url = find_next_page_url(soup, url)
        url = next_url
        if url:
            time.sleep(delay)

    return all_events


# --------------------------------------------------------------------------
# events.json laden/speichern & Deduplizierung
# --------------------------------------------------------------------------

def load_existing_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def dedupe_key(name: str | None, datum_start: str | None) -> tuple[str, str] | None:
    if not name or not datum_start:
        return None
    return (name.strip().casefold(), datum_start)


def merge_events(existing: list[dict], new_events: Iterable[Event]) -> tuple[list[dict], int, int]:
    """Fügt neue Events an, überspringt Duplikate (Abgleich über Name +
    Startdatum). Gibt (gemergte Liste, Anzahl neu hinzugefügt, Anzahl
    übersprungen) zurück."""
    existing_keys = {
        dedupe_key(e.get("name"), e.get("datum_start")) for e in existing
    }
    existing_keys.discard(None)

    merged = list(existing)
    added = 0
    skipped = 0

    for event in new_events:
        if not event.is_valid():
            skipped += 1
            continue
        key = dedupe_key(event.name, event.datum_start)
        if key is None or key in existing_keys:
            skipped += 1
            continue
        merged.append(event.to_dict())
        existing_keys.add(key)
        added += 1

    return merged, added, skipped


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Liest Lauf-Events von laufen.de/laufkalender aus und "
                     "ergänzt sie in events.json (keine Duplikate)."
    )
    parser.add_argument(
        "--events-json", type=Path, default=EVENTS_JSON_PATH,
        help=f"Pfad zur events.json (Standard: {EVENTS_JSON_PATH})",
    )
    parser.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_PAGES,
        help="Maximale Anzahl an Kalenderseiten, die abgerufen werden (Schutz vor Endlosschleifen).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur anzeigen, was hinzugefügt würde – events.json NICHT verändern.",
    )
    parser.add_argument(
        "--no-geocoding", action="store_true",
        help="Kein Nominatim-Geocoding durchführen (lat/lon bleiben leer, falls nicht in JSON-LD enthalten).",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    delay = check_robots(session)

    raw_events = fetch_all_events(session, delay, args.max_pages)
    print(f"\nInsgesamt {len(raw_events)} rohe Event-Einträge gefunden.\n")

    if not args.no_geocoding:
        geocoder = Geocoder(GEOCODE_CACHE_PATH)
        for event in raw_events:
            if event.lat is None and event.lon is None and event.standort:
                coords = geocoder.geocode(event.standort, event.land)
                if coords:
                    event.lat, event.lon = coords

    existing_events = load_existing_events(args.events_json)
    merged, added, skipped = merge_events(existing_events, raw_events)

    print(f"→ {added} neue Event(s) würden hinzugefügt, {skipped} übersprungen "
          f"(Duplikat, oder Pflichtfelder fehlen: Name/Datum/Standort).")

    if args.dry_run:
        print("\n--dry-run aktiv: events.json wurde NICHT verändert. "
              "Neue Events zur Kontrolle:")
        for e in merged[len(existing_events):]:
            print(f"  - {e.get('name')} | {e.get('datum_start')} | {e.get('standort')}")
        return

    args.events_json.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n✅ {args.events_json} aktualisiert ({len(existing_events)} -> {len(merged)} Events).")


if __name__ == "__main__":
    main()
