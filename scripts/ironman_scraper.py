#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ironman_scraper.py
====================

Liest Triathlon-Events von der IRONMAN-Renn-Übersicht
https://www.ironman.com/races?facet%5B0%5D=region%3AEurope aus und ergänzt
sie in `events.json` – im selben Format wie die bestehenden Events, ohne
Duplikate (Abgleich über Name + Startdatum). Nur Events in Deutschland,
Österreich und der Schweiz werden standardmäßig übernommen (siehe
`--include-all-europe`, falls du auch die übrigen europäischen IRONMAN-Rennen
willst).

WICHTIG – bitte vor dem ersten produktiven Lauf lesen
-------------------------------------------------------
Dieses Skript wurde NICHT gegen die echte Seite getestet: In der Umgebung,
in der es geschrieben wurde, ist der Netzwerkzugriff auf ironman.com durch
eine Firewall-/Proxy-Richtlinie blockiert (robots.txt und die Renn-Seite
selbst waren nicht erreichbar). Führe es deshalb zunächst mit
`--dry-run --max-pages 1` aus, bevor du events.json wirklich verändern lässt.

Vermutlich JavaScript-gerenderte Seite
-----------------------------------------
Die Renn-Übersicht filtert per URL-Facette (`?facet[0]=region:Europe`) –
ein typisches Merkmal moderner React/Next.js-Seiten, bei denen die
eigentliche Renn-Liste erst im Browser per JavaScript aus einer API
nachgeladen wird. Ein einfacher `requests.get()` liefert dann u. U. nur ein
leeres HTML-Gerüst ohne die Events. Für diesen Fall gibt es zwei Auswege,
in der Reihenfolge der Zuverlässigkeit:

  1. **API-Endpunkt direkt nutzen (empfohlen)**: Browser-Entwicklertools
     öffnen -> Tab "Netzwerk"/"Network" -> Seite neu laden -> nach
     XHR/Fetch-Requests suchen, die JSON mit den Renndaten liefern
     (oft ein Pfad wie `/api/races` oder eine GraphQL-Route). Die
     gefundene URL per `--api-url "https://..."` übergeben – das Skript
     versucht dann, die JSON-Antwort generisch zu normalisieren
     (`parse_api_json`, Feldnamen ggf. dort anpassen).
  2. **JavaScript-Rendering per Playwright**: `--render-js` aktiviert
     einen Playwright-Chromium-Render-Durchlauf, der die Seite wie ein
     echter Browser lädt (inkl. JS-Ausführung) und danach den fertigen
     DOM an den Parser übergibt. Erfordert `pip install playwright` und
     einmalig `playwright install chromium` (bzw. den `PLAYWRIGHT_BROWSERS_
     PATH`, falls Chromium schon anderswo vorinstalliert ist).

Ohne beides versucht das Skript zunächst JSON-LD (schema.org Event) und
danach einen HTML-Selektor-Fallback – falls die Seite serverseitig doch
gerenderte Daten oder eingebettetes JSON-LD liefert, funktioniert es auch
ohne API-URL oder Playwright.

robots.txt-Prüfung
-------------------
Das Skript lädt robots.txt bei jedem Lauf live von ironman.com und prüft
per `urllib.robotparser`, ob unser User-Agent den Renn-Übersicht-Pfad
crawlen darf (geprüft wird die tatsächliche Ziel-URL inkl. Facette). Ist
das nicht der Fall, bricht das Skript sofort ab, OHNE irgendeine weitere
Anfrage zu schicken. Ein evtl. angegebener Crawl-Delay wird respektiert.
Das gilt NICHT für `--api-url`, falls die API auf einer anderen Domain
liegt – prüfe deren robots.txt / Nutzungsbedingungen in dem Fall selbst.

Nutzung
-------
    pip install -r scripts/requirements.txt

    # Testlauf ohne events.json zu verändern:
    python3 scripts/ironman_scraper.py --dry-run --max-pages 1

    # Falls die Seite JS-gerendert ist:
    pip install playwright && playwright install chromium
    python3 scripts/ironman_scraper.py --dry-run --render-js

    # Falls du den API-Endpunkt per Entwicklertools gefunden hast:
    python3 scripts/ironman_scraper.py --dry-run --api-url "https://www.ironman.com/api/..."

    # Echter Lauf, ergänzt events.json im Repo-Root:
    python3 scripts/ironman_scraper.py

Optionen: siehe `python3 scripts/ironman_scraper.py --help`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------

BASE_URL = "https://www.ironman.com"
CALENDAR_URL = "https://www.ironman.com/races?facet%5B0%5D=region%3AEurope"

USER_AGENT = (
    "EnduranceEventsBot/1.0 "
    "(+https://antdon930.github.io/Enduranceevents/; "
    "privater, nicht-kommerzieller Kalenderabgleich; Kontakt siehe Repo)"
)

DEFAULT_REQUEST_DELAY_SECONDS = 2.0
DEFAULT_MAX_PAGES = 10

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON_PATH = REPO_ROOT / "events.json"
# Gemeinsamer Geocoding-Cache mit laufkalender_scraper.py (gleiches
# Cache-Format "Stadt, Land" -> [lat, lon]), spart doppelte Nominatim-Anfragen.
GEOCODE_CACHE_PATH = REPO_ROOT / "scripts" / ".geocode_cache.json"

# TODO: ANPASSEN, falls Pagination anders funktioniert. IRONMAN-Seiten mit
# Facetten-Filtern laden weitere Ergebnisse häufig per "Load more"-Button
# (AJAX) statt klassischer <a>-Links – dafür eignet sich eher
# --page-param/--max-pages (siehe unten) als diese Selektoren.
NEXT_PAGE_SELECTORS = [
    'a[rel="next"]',
    "a.pagination-next",
    "a.next",
    'a[aria-label="Next"]',
    'a[aria-label="Next page"]',
]

# TODO: ANPASSEN an die echte Seitenstruktur, falls weder JSON-LD noch
# --api-url/--render-js funktionieren bzw. nötig sind.
HTML_FALLBACK_SELECTORS = {
    "event_card": "article.race-card, li.race-item, div.race-teaser, div[data-race]",
    "name": "h2, h3, .race-title, .race-name",
    "date": "time, .race-date",
    "location": ".race-location, .race-city",
    "link": "a",
    "distance": ".race-type, .race-distance",
}

# Land-Erkennung: Ländernamen (DE/EN) und ISO-Codes -> unser Schema.
LAND_KEYWORDS = {
    "deutschland": "Deutschland", "germany": "Deutschland", "de": "Deutschland",
    "österreich": "Österreich", "austria": "Österreich", "at": "Österreich",
    "schweiz": "Schweiz", "switzerland": "Schweiz", "ch": "Schweiz",
}
COUNTRY_CODE_MAP = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
DACH_LAENDER = {"Deutschland", "Österreich", "Schweiz"}

GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
}
ENGLISH_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Renntyp -> Gesamtdistanz in km (Reihenfolge wichtig: spezifischere Muster
# zuerst prüfen, "ironman" allein ist der unspezifische Catch-all für die
# volle Langdistanz und muss daher zuletzt kommen).
RACE_TYPE_DISTANCE_KM: list[tuple[re.Pattern, float]] = [
    (re.compile(r"70\.3", re.I), 113.0),          # Mitteldistanz
    (re.compile(r"\b5150\b", re.I), 51.5),          # Olympische Distanz
    (re.compile(r"\bsprint\b", re.I), 25.75),       # Sprintdistanz
    (re.compile(r"\bvr\b|virtual", re.I), None),     # Virtual Race: keine reale Distanz zuordenbar
    (re.compile(r"ironman", re.I), 226.0),          # volle Langdistanz (Fallback)
]


# --------------------------------------------------------------------------
# Datenmodell (Feldreihenfolge identisch zu events.json)
# --------------------------------------------------------------------------

@dataclass
class Event:
    land: str | None = None
    name: str | None = None
    standort: str | None = None
    lat: float | None = None
    lon: float | None = None
    art1: str = "Triathlon"
    art2: str | None = None  # Triathlon hat laut Projekt-Taxonomie keine Kategorie-Unterteilung
    datum_start: str | None = None
    datum_ende: str | None = None
    anmeldeschluss: str | None = None
    laenge_km: float | None = None
    veranstalter_url: str | None = None

    def is_valid(self) -> bool:
        return bool(self.name and self.datum_start and self.standort)

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        return {k: v for k, v in d.items() if v is not None}


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------

def check_robots(session: requests.Session, target_url: str) -> float:
    """Prüft robots.txt live gegen `target_url` für unseren User-Agent.

    Gibt die zu verwendende Pause zwischen Requests zurück (Sekunden).
    Bricht das Programm ab, falls der Pfad gesperrt ist.
    """
    robots_url = urljoin(BASE_URL, "/robots.txt")
    print(f"→ Lade robots.txt von {robots_url} ...")
    try:
        resp = session.get(robots_url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(
            f"\n❌ robots.txt konnte nicht geladen werden: {exc}\n"
            "   Mögliche Ursachen: kein Internetzugriff von hier aus, ein "
            "Netzwerk-/Firewall-Proxy blockiert die Domain, oder ironman.com "
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

    allowed = rp.can_fetch(USER_AGENT, target_url)
    if not allowed:
        print(
            f"\n❌ robots.txt verbietet unserem User-Agent den Zugriff auf "
            f"{target_url}. Breche ab, ohne die Seite abzurufen."
        )
        sys.exit(1)

    delay = rp.crawl_delay(USER_AGENT)
    if delay is None:
        rate = rp.request_rate(USER_AGENT)
        if rate is not None and rate.requests:
            delay = rate.seconds / rate.requests
    delay = max(float(delay or 0), DEFAULT_REQUEST_DELAY_SECONDS)

    print(f"✅ robots.txt erlaubt den Zugriff. Verwende {delay:.1f}s Pause zwischen Requests.\n")
    return delay


# --------------------------------------------------------------------------
# Hilfsfunktionen: Datum, Land, Distanz
# --------------------------------------------------------------------------

def parse_flexible_date(text: str) -> str | None:
    """Wandelt diverse Datumsformate (deutsch, englisch, ISO) in
    'YYYY-MM-DD' um. Gibt None zurück, wenn nichts erkannt werden konnte."""
    if not text:
        return None
    text = text.strip()

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

    # "27. September 2026" (deutsch)
    m = re.search(r"\b(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})\b", text)
    if m and m.group(2).lower() in GERMAN_MONTHS:
        d, y = int(m.group(1)), int(m.group(3))
        mo = GERMAN_MONTHS[m.group(2).lower()]
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

    # "September 27, 2026" oder "Sep 27, 2026" (englisch, IRONMAN-Seiten sind meist englisch)
    m = re.search(r"\b([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if m and m.group(1).lower() in ENGLISH_MONTHS:
        mo = ENGLISH_MONTHS[m.group(1).lower()]
        d, y = int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

    # "27 September 2026" (englisch, Tag zuerst)
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\.?,?\s+(\d{4})\b", text)
    if m and m.group(2).lower() in ENGLISH_MONTHS:
        d, y = int(m.group(1)), int(m.group(3))
        mo = ENGLISH_MONTHS[m.group(2).lower()]
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
    return None


def guess_distance_km(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*km\b", text, re.I)
    if m:
        return float(m.group(1).replace(",", "."))
    for pattern, km in RACE_TYPE_DISTANCE_KM:
        if pattern.search(text):
            return km
    return None


# --------------------------------------------------------------------------
# Geocoding (Stadt -> lat/lon), mit lokalem Cache (geteilt mit laufkalender_scraper.py)
# --------------------------------------------------------------------------

class Geocoder:
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
            from geopy.geocoders import Nominatim
            self._geolocator = Nominatim(user_agent=USER_AGENT)

    def geocode(self, standort: str, land: str | None) -> tuple[float, float] | None:
        query = f"{standort}, {land}" if land else standort
        if query in self.cache:
            cached = self.cache[query]
            return tuple(cached) if cached else None

        try:
            self._ensure_geolocator()
            location = self._geolocator.geocode(query, timeout=10)
        except Exception as exc:
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
# Parsing: JSON-LD (bevorzugt, falls serverseitig vorhanden)
# --------------------------------------------------------------------------

def parse_jsonld_events(soup: BeautifulSoup, page_url: str) -> list[dict]:
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
        land = COUNTRY_CODE_MAP.get(str(land_raw).upper()) or guess_land(str(land_raw or ""))
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

    datum_start = parse_flexible_date(str(raw.get("startDate") or ""))
    datum_ende = parse_flexible_date(str(raw.get("endDate") or "")) or datum_start

    combined_text = " ".join(str(raw.get(k) or "") for k in ("name", "description"))
    laenge_km = guess_distance_km(combined_text)

    veranstalter_url = raw.get("url") or raw.get("_page_url")

    return Event(
        land=land, name=name.strip() if name else None,
        standort=standort.strip() if standort else None,
        lat=lat, lon=lon,
        datum_start=datum_start, datum_ende=datum_ende,
        laenge_km=laenge_km, veranstalter_url=veranstalter_url,
    )


# --------------------------------------------------------------------------
# Parsing: HTML-Fallback (Platzhalter-Selektoren, siehe Kopf-Kommentar)
# --------------------------------------------------------------------------

def parse_html_fallback(soup: BeautifulSoup, page_url: str) -> list[Event]:
    events: list[Event] = []
    cards = soup.select(HTML_FALLBACK_SELECTORS["event_card"])
    for card in cards:
        name_el = card.select_one(HTML_FALLBACK_SELECTORS["name"])
        date_el = card.select_one(HTML_FALLBACK_SELECTORS["date"])
        loc_el = card.select_one(HTML_FALLBACK_SELECTORS["location"])
        link_el = card.select_one(HTML_FALLBACK_SELECTORS["link"])
        dist_el = card.select_one(HTML_FALLBACK_SELECTORS["distance"])

        name = name_el.get_text(strip=True) if name_el else None
        date_text = (
            date_el.get("datetime") if date_el and date_el.has_attr("datetime") else None
        ) or (date_el.get_text(strip=True) if date_el else None)
        standort = loc_el.get_text(strip=True) if loc_el else None
        href = link_el.get("href") if link_el else None
        distance_text = dist_el.get_text(strip=True) if dist_el else ""

        datum_start = parse_flexible_date(date_text or "")
        combined_text = " ".join([name or "", distance_text])

        events.append(
            Event(
                land=guess_land(f"{standort or ''} {combined_text}"),
                name=name, standort=standort,
                datum_start=datum_start, datum_ende=datum_start,
                laenge_km=guess_distance_km(combined_text),
                veranstalter_url=urljoin(page_url, href) if href else None,
            )
        )
    return events


# --------------------------------------------------------------------------
# Parsing: generisches JSON-API-Ergebnis (nur mit --api-url)
# --------------------------------------------------------------------------

def _first_present(d: dict, keys: list[str]) -> Any:
    for key in keys:
        # unterstützt einfache "a.b.c"-Pfade
        node: Any = d
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                node = None
                break
        if node is not None:
            return node
    return None


def parse_api_json(data: Any, page_url: str) -> list[Event]:
    """Best-effort-Normalisierung einer unbekannten API-JSON-Struktur.

    TODO: ANPASSEN, sobald die echte API-Antwortstruktur bekannt ist –
    diese Funktion rät anhand gängiger Feldnamen (name/title,
    startDate/date/eventDate, location.city/city, ...). Passe die
    Schlüssel-Listen unten an die tatsächliche Struktur an, falls nötig.
    """
    # Versuche, die Liste der Renn-Objekte in verschachtelten Strukturen zu finden.
    if isinstance(data, dict):
        for key in ("races", "results", "items", "data", "events"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    events: list[Event] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _first_present(item, ["name", "title", "raceName", "eventName"])
        date_raw = _first_present(
            item, ["startDate", "date", "eventDate", "raceDate", "start_date"]
        )
        standort = _first_present(
            item, ["city", "location.city", "venue.city", "location", "locationName"]
        )
        country_raw = _first_present(
            item, ["country", "location.country", "venue.country", "countryCode"]
        )
        href = _first_present(item, ["url", "link", "slug", "raceUrl"])
        race_type = _first_present(item, ["raceType", "type", "distance", "category"])

        land = COUNTRY_CODE_MAP.get(str(country_raw).upper()) if country_raw else None
        if not land:
            land = guess_land(str(country_raw or ""))
        if not land:
            land = guess_land(f"{standort or ''} {name or ''}")

        datum_start = parse_flexible_date(str(date_raw or ""))
        combined_text = " ".join(str(x or "") for x in (name, race_type))

        veranstalter_url = None
        if href:
            href = str(href)
            veranstalter_url = href if href.startswith("http") else urljoin(page_url, href)

        events.append(
            Event(
                land=land,
                name=str(name).strip() if name else None,
                standort=str(standort).strip() if standort else None,
                datum_start=datum_start, datum_ende=datum_start,
                laenge_km=guess_distance_km(combined_text),
                veranstalter_url=veranstalter_url,
            )
        )
    return events


# --------------------------------------------------------------------------
# Optionales JS-Rendering per Playwright
# --------------------------------------------------------------------------

def fetch_rendered_html(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "\n❌ --render-js benötigt Playwright: `pip install playwright` "
            "und einmalig `playwright install chromium` ausführen."
        )
        sys.exit(1)

    print(f"  → Rendere {url} per Playwright/Chromium (JS-Ausführung) ...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
        finally:
            browser.close()
    return html


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
    session: requests.Session, delay: float, max_pages: int, render_js: bool
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
            if render_js:
                html = fetch_rendered_html(url)
            else:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
                html = resp.text
        except requests.exceptions.RequestException as exc:
            print(f"  ❌ Abbruch: {url} konnte nicht geladen werden ({exc}).")
            break

        soup = BeautifulSoup(html, "html.parser")

        raw_jsonld = parse_jsonld_events(soup, url)
        if raw_jsonld:
            print(f"  ✓ {len(raw_jsonld)} Event(s) über JSON-LD gefunden.")
            page_events = [normalize_jsonld_event(r) for r in raw_jsonld]
        else:
            page_events = parse_html_fallback(soup, url)
            if page_events:
                print(f"  ✓ {len(page_events)} Event(s) über HTML-Fallback gefunden.")
            else:
                print(
                    "  ⚠ Kein JSON-LD und kein HTML-Fallback-Treffer. Falls die "
                    "Seite JavaScript-gerendert ist, versuche --render-js oder "
                    "finde den API-Endpunkt und nutze --api-url (siehe Docstring "
                    "am Kopf des Skripts)."
                )

        all_events.extend(page_events)

        next_url = find_next_page_url(soup, url)
        url = next_url
        if url:
            time.sleep(delay)

    return all_events


def fetch_events_from_api(session: requests.Session, api_url: str) -> list[Event]:
    print(f"→ Lade API-Antwort von {api_url} ...")
    try:
        resp = session.get(api_url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        print(f"❌ API-Abruf fehlgeschlagen: {exc}")
        sys.exit(1)
    except ValueError as exc:
        print(f"❌ API-Antwort war kein gültiges JSON: {exc}")
        sys.exit(1)

    events = parse_api_json(data, api_url)
    print(f"  ✓ {len(events)} Event(s) aus der API-Antwort extrahiert.")
    return events


# --------------------------------------------------------------------------
# events.json laden/speichern, DACH-Filter & Deduplizierung
# --------------------------------------------------------------------------

def load_existing_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def dedupe_key(name: str | None, datum_start: str | None) -> tuple[str, str] | None:
    if not name or not datum_start:
        return None
    return (name.strip().casefold(), datum_start)


def filter_dach(events: list[Event], include_all: bool) -> tuple[list[Event], int]:
    if include_all:
        return events, 0
    kept = [e for e in events if e.land in DACH_LAENDER]
    skipped = len(events) - len(kept)
    return kept, skipped


def merge_events(existing: list[dict], new_events: Iterable[Event]) -> tuple[list[dict], int, int]:
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
        description="Liest IRONMAN-Triathlon-Events (Europa) aus und ergänzt "
                     "sie in events.json (keine Duplikate, standardmäßig nur DACH)."
    )
    parser.add_argument(
        "--events-json", type=Path, default=EVENTS_JSON_PATH,
        help=f"Pfad zur events.json (Standard: {EVENTS_JSON_PATH})",
    )
    parser.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_PAGES,
        help="Maximale Anzahl an Seiten, die abgerufen werden (Schutz vor Endlosschleifen).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur anzeigen, was hinzugefügt würde – events.json NICHT verändern.",
    )
    parser.add_argument(
        "--no-geocoding", action="store_true",
        help="Kein Nominatim-Geocoding durchführen (lat/lon bleiben leer, falls nicht in den Daten enthalten).",
    )
    parser.add_argument(
        "--render-js", action="store_true",
        help="Seite per Playwright/Chromium mit JavaScript-Ausführung laden (für React/Next.js-Seiten).",
    )
    parser.add_argument(
        "--api-url", type=str, default=None,
        help="Optional: direkte JSON-API-URL (z. B. per Browser-Entwicklertools gefunden), "
             "statt die HTML-Seite zu parsen. Umgeht robots.txt-Check der Renn-Seite NICHT "
             "den der API-Domain – bitte ggf. selbst prüfen.",
    )
    parser.add_argument(
        "--include-all-europe", action="store_true",
        help="Auch Events außerhalb Deutschland/Österreich/Schweiz übernehmen "
             "(Standard: nur DACH, passend zum Fokus dieses Projekts).",
    )
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if args.api_url:
        # robots.txt der Haupt-Domain trotzdem prüfen, falls die API auf
        # ironman.com selbst liegt; bei Fremd-Domains greift das nicht.
        if args.api_url.startswith(BASE_URL):
            check_robots(session, args.api_url)
        else:
            print(
                f"⚠ --api-url zeigt auf eine andere Domain als {BASE_URL} – "
                "bitte deren robots.txt/Nutzungsbedingungen manuell prüfen. "
                "Fahre fort ohne automatischen Check."
            )
        raw_events = fetch_events_from_api(session, args.api_url)
    else:
        delay = check_robots(session, CALENDAR_URL)
        raw_events = fetch_all_events(session, delay, args.max_pages, args.render_js)

    print(f"\nInsgesamt {len(raw_events)} rohe Event-Einträge gefunden.")

    dach_events, dach_skipped = filter_dach(raw_events, args.include_all_europe)
    if dach_skipped:
        print(f"  ({dach_skipped} Event(s) außerhalb DACH übersprungen – "
              f"mit --include-all-europe übernehmen.)")

    if not args.no_geocoding:
        geocoder = Geocoder(GEOCODE_CACHE_PATH)
        for event in dach_events:
            if event.lat is None and event.lon is None and event.standort:
                coords = geocoder.geocode(event.standort, event.land)
                if coords:
                    event.lat, event.lon = coords

    existing_events = load_existing_events(args.events_json)
    merged, added, skipped = merge_events(existing_events, dach_events)

    print(f"\n→ {added} neue Event(s) würden hinzugefügt, {skipped} übersprungen "
          f"(Duplikat, oder Pflichtfelder fehlen: Name/Datum/Standort).")

    if args.dry_run:
        print("\n--dry-run aktiv: events.json wurde NICHT verändert. "
              "Neue Events zur Kontrolle:")
        for e in merged[len(existing_events):]:
            print(f"  - {e.get('name')} | {e.get('datum_start')} | {e.get('standort')} | {e.get('laenge_km')} km")
        return

    args.events_json.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n✅ {args.events_json} aktualisiert ({len(existing_events)} -> {len(merged)} Events).")


if __name__ == "__main__":
    main()
