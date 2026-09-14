#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
laufkalender_scraper.py
========================

Liest Lauf-Events vom Laufkalender auf https://laufen.de/laufkalender aus
und ergänzt sie in `events.json` – im selben Format wie die bestehenden
Events, ohne Duplikate zu erzeugen (Abgleich über Name + Startdatum).

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt erlaubt den Zugriff (nur `/contao/` und `/_contao/` sind
gesperrt, `/laufkalender` selbst nicht betroffen).

robots.txt-Prüfung
-------------------
Das Skript lädt robots.txt bei jedem Lauf live von laufen.de und prüft
per `urllib.robotparser`, ob unser User-Agent den Pfad `/laufkalender`
crawlen darf. Ist das nicht der Fall, bricht das Skript sofort ab, OHNE
irgendeine Anfrage an die Kalenderseite zu schicken. Einen evtl. in
robots.txt angegebenen Crawl-Delay respektiert es automatisch.

Parsing-Strategie
-------------------
Die Kalenderseite selbst (`/laufkalender`) enthält kein JSON-LD und im
initial ausgelieferten HTML auch keine Event-Karten – sie lädt die
Ergebnisliste per JavaScript aus einem AJAX-Endpunkt nach (gefunden im
eingebetteten `<script>`-Block der Seite):

    POST https://laufen.de/laufkalender/ajax/search
    Content-Type: application/x-www-form-urlencoded
    Body: search=&radius=&start=&end=&distance_start=&distance_end=
          &distances=[]&page=<N>

Antwort ist JSON mit u. a. `pages` (Gesamtseitenzahl), `events` und
`topevents` (jeweils ein HTML-Fragment mit `<a class="teaser event">`-
Kacheln, die dieses Skript mit BeautifulSoup parst statt die komplette
Kalenderseite zu rendern - kein `--render-js`/Playwright nötig). Jede
Kachel enthält Datum (`.date`, Format "D.M.YYYY", ohne Jahr-Mehrdeutigkeit),
Name (`.headline`), PLZ+Ort (`.location`, wird per Regex getrennt: 5-stellig
= Deutschland, 4-stellig = Österreich/Schweiz, aber anhand der PLZ allein
nicht sicher unterscheidbar - `land` bleibt dann leer statt zu raten) und
Distanz(en) (`.strecken .wettbewerbe`, Format "Strecke(n): X [bis Y]
Kilometer" - bei einer Spanne wird die größere Zahl übernommen).
`topevents` enthält dieselbe Kachel-Struktur (zusätzlich mit Bild/Badge)
für beworbene Veranstaltungen und wird identisch mitgeparst.

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
from datetime import date
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
# Per <script>-Block auf der Kalenderseite gefundener AJAX-Endpunkt, über
# den die Ergebnisliste tatsächlich geladen wird (siehe Docstring).
AJAX_SEARCH_URL = urljoin(BASE_URL, "/laufkalender/ajax/search")

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

# Selektoren für eine einzelne Veranstaltungskachel innerhalb der von
# AJAX_SEARCH_URL gelieferten "events"/"topevents"-HTML-Fragmente (siehe
# Docstring). Kalibriert am echten Seiteninhalt.
TEASER_SELECTORS = {
    "event_card": "a.teaser.event",
    "date": ".tcontainer > .date",
    "name": ".headline",
    "location": ".location",
    "distance": ".strecken .wettbewerbe",
}

LAND_KEYWORDS = {
    "deutschland": "Deutschland", "germany": "Deutschland", "de": "Deutschland",
    "österreich": "Österreich", "austria": "Österreich", "at": "Österreich",
    "schweiz": "Schweiz", "switzerland": "Schweiz", "ch": "Schweiz",
}

# Zuordnung Stichwort -> Kategorie (art2), passend zur im Projekt
# verwendeten Taxonomie für Laufen: Straße, Trail, Bahn, Berg, Cross, Hindernis.
# Reihenfolge ist bewusst NICHT alphabetisch, sondern von spezifisch nach
# generisch: "Straße" (inkl. Marathon/Stadtlauf) steht bewusst ZULETZT,
# siehe ausführlichen Kommentar zu ART2_KEYWORDS_LAUFEN in scraper_lib.py
# (derselbe Bug/Fix, hier dupliziert weil dieses Skript scraper_lib.py
# bewusst nicht nutzt).
ART2_KEYWORDS = [
    (re.compile(r"hindernislauf|obstacle|ocr\b|spartan|tough mudder", re.I), "Hindernis"),
    (re.compile(r"trail|geländelauf|ultratrail", re.I), "Trail"),
    (re.compile(r"berglauf|bergrennen|bergmarathon|mountain ?run|gipfel|alpin|gebirg|höhenmeter", re.I), "Berg"),
    (re.compile(r"crosslauf|cross.?country|\bcross\b", re.I), "Cross"),
    (re.compile(r"bahn(meeting)?|leichtathletik.?meeting", re.I), "Bahn"),
    (re.compile(r"halbmarathon|marathon|stadtlauf|straßenlauf|city ?run|\bstraße\b", re.I), "Straße"),
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
    # explizite Kilometerangabe, z. B. "21,1 km", "10 km" oder (laufen.de-
    # Format) "Strecken: 5 bis 7 Kilometer" - bei mehreren/einer Spanne
    # (z. B. "0,4 bis 21,1 Kilometer") wird die größte Zahl übernommen.
    # Nachkommateil bewusst UNBEGRENZT (\d+, nicht \d{1,2}/\d{1,3}): die
    # offiziellen Distanzen "42,195 Kilometer" (Marathon) und "21,0975 km"
    # (Halbmarathon) haben 3 bzw. 4 Nachkommastellen - mit einer festen
    # Obergrenze matcht der Regex nicht ab der Zahl vor dem Komma, sondern
    # (Bug, echt aufgetreten und mit realen Daten verifiziert) versehentlich
    # nur den Nachkommateil als vermeintlich eigenständige km-Angabe
    # (z. B. "975" statt 21,0975 oder "195" statt 42,195).
    matches = re.findall(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:km\b|Kilometer)", text, re.I)
    if matches:
        return max(float(m.replace(",", ".")) for m in matches)
    # Fallback über bekannte Renn-Bezeichnungen, bewusst nach Stichwort-
    # LÄNGE absteigend geprüft (nicht in Dict-Reihenfolge): "halbmarathon"
    # enthält die Teilkette "marathon" - siehe Kommentar in
    # scraper_lib.guess_distance_km() zu diesem echten Bug.
    lowered = text.lower()
    for keyword in sorted(KNOWN_DISTANCES_KM, key=len, reverse=True):
        if keyword and keyword in lowered:
            return KNOWN_DISTANCES_KM[keyword]
    return None


def parse_location(text: str) -> str | None:
    """Trennt eine PLZ+Ort-Angabe wie '74821           Mosbach        ' in
    den reinen Ortsnamen auf (die PLZ selbst fließt bereits über
    `guess_land()` auf dem unveränderten Text in die Ländererkennung ein)."""
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"^(\d{4,5})\s*(.+)$", normalized)
    return m.group(2).strip() if m else (normalized or None)


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
            from geopy.extra.rate_limiter import RateLimiter  # Lazy-Import, optional
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent=USER_AGENT)
            # Nominatim erlaubt laut Nutzungsbedingungen max. 1 Request/
            # Sekunde - in der Praxis (verifiziert) drosselt es teils
            # strenger (HTTP 429), z. B. bei geteilter Ausgangs-IP. Der
            # RateLimiter hält den Mindestabstand ein UND wiederholt bei
            # HTTP 429/5xx (GeocoderServiceError-Familie) automatisch mit
            # Wartezeit, statt beim ersten 429 sofort aufzugeben.
            self._geolocator = RateLimiter(
                geolocator.geocode, min_delay_seconds=1.5,
                max_retries=4, error_wait_seconds=5.0,
                swallow_exceptions=False,
            )

    def geocode(self, standort: str, land: str | None) -> tuple[float, float] | None:
        query = f"{standort}, {land}" if land else standort
        if query in self.cache:
            cached = self.cache[query]
            return tuple(cached) if cached else None

        try:
            self._ensure_geolocator()
            location = self._geolocator(query, timeout=10)
        except Exception as exc:  # geopy kann diverse Netzwerkfehler werfen
            print(f"  ⚠ Geocoding fehlgeschlagen für '{query}': {exc}")
            location = None

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
# Parsing: Event-Kacheln aus der AJAX-Antwort (siehe Docstring)
# --------------------------------------------------------------------------

def parse_teaser_html(html_fragment: str) -> list[Event]:
    """Parst ein `events`- oder `topevents`-HTML-Fragment aus der
    AJAX-Antwort in Event-Objekte."""
    if not html_fragment:
        return []
    soup = BeautifulSoup(html_fragment, "html.parser")
    events: list[Event] = []

    for card in soup.select(TEASER_SELECTORS["event_card"]):
        date_el = card.select_one(TEASER_SELECTORS["date"])
        name_el = card.select_one(TEASER_SELECTORS["name"])
        loc_el = card.select_one(TEASER_SELECTORS["location"])
        dist_el = card.select_one(TEASER_SELECTORS["distance"])

        name = name_el.get_text(strip=True) if name_el else None
        date_text = date_el.get_text(strip=True) if date_el else ""
        location_text = loc_el.get_text(" ", strip=True) if loc_el else ""
        distance_text = dist_el.get_text(strip=True) if dist_el else ""
        href = card.get("href")

        datum_start = parse_german_date(date_text)
        if not name and not datum_start:
            continue  # kein echter Treffer (z. B. ein zu breit gefasster Sub-Match)

        events.append(
            Event(
                land=guess_land(location_text),
                name=name,
                standort=parse_location(location_text),
                art2=guess_art2(f"{name or ''} {distance_text}"),
                datum_start=datum_start,
                datum_ende=datum_start,
                laenge_km=guess_distance_km(distance_text),
                # href ist site-relativ ("laufkalender/details/ID", ohne
                # führenden Slash) und dadurch nur korrekt auflösbar relativ
                # zur eigentlichen Kalenderseite (CALENDAR_URL), NICHT
                # relativ zu AJAX_SEARCH_URL.
                veranstalter_url=urljoin(CALENDAR_URL, href) if href else None,
            )
        )
    return events


# --------------------------------------------------------------------------
# Seiten abrufen (AJAX-Pagination über den "page"-Parameter)
# --------------------------------------------------------------------------

def fetch_all_events(
    session: requests.Session, delay: float, max_pages: int
) -> list[Event]:
    all_events: list[Event] = []
    total_pages = 1

    for page_num in range(1, max_pages + 1):
        if page_num > total_pages:
            break

        print(f"→ Lade Seite {page_num} von {AJAX_SEARCH_URL} ...")
        try:
            resp = session.post(
                AJAX_SEARCH_URL,
                headers={"X-Requested-With": "XMLHttpRequest"},
                data={
                    "search": "", "radius": "", "start": "", "end": "",
                    "distance_start": "", "distance_end": "",
                    "distances": "[]", "page": page_num,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            print(f"  ❌ Abbruch: AJAX-Suche konnte nicht geladen werden ({exc}).")
            break
        except ValueError as exc:
            print(f"  ❌ Abbruch: Antwort war kein gültiges JSON ({exc}).")
            break

        total_pages = int(data.get("pages") or 1)
        page_events = parse_teaser_html(data.get("topevents") or "") + parse_teaser_html(data.get("events") or "")
        print(f"  ✓ {len(page_events)} Event(s) gefunden (Seite {page_num} von {total_pages}).")
        all_events.extend(page_events)

        if page_num < total_pages:
            time.sleep(delay)

    return all_events


# --------------------------------------------------------------------------
# events.json laden/speichern & Deduplizierung
# --------------------------------------------------------------------------

def load_existing_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# Events unter dieser Distanz werden nicht aufgenommen (siehe Chat/README):
# viele Firmen-/Kinder-/Bambini-/Hobbyläufe sind für dieses Projekt nicht
# relevant. Events OHNE bekannte Distanz sind davon NICHT betroffen.
MIN_DISTANCE_KM = 5.0

MANUAL_OVERRIDES_PATH = REPO_ROOT / "scripts" / "manual_overrides.json"


def apply_manual_overrides(events: list[Event]) -> tuple[list[Event], int]:
    """Siehe scraper_lib.apply_manual_overrides() (identische Logik, hier
    dupliziert, da dieses Skript scraper_lib.py bewusst nicht nutzt).
    Wendet scripts/manual_overrides.json an (v. a. für Events, die
    zusätzlich auch über eine andere, datenärmere Quelle wie blv-sport.de
    unter demselben Namen+Datum gefunden werden)."""
    if not MANUAL_OVERRIDES_PATH.exists():
        return events, 0
    overrides = json.loads(MANUAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
    if not overrides:
        return events, 0

    result: list[Event] = []
    excluded = 0
    for event in events:
        key = f"{(event.name or '').strip()}|{event.datum_start}"
        override = next(
            (v for k, v in overrides.items() if k != "_readme" and k.casefold() == key.casefold()),
            None,
        )
        if override:
            if override.get("exclude"):
                excluded += 1
                continue
            for field in ("laenge_km", "art2", "art1", "land", "standort", "veranstalter_url"):
                if field in override:
                    setattr(event, field, override[field])
        result.append(event)
    return result, excluded


def filter_min_distance(events: list[Event], min_km: float = MIN_DISTANCE_KM) -> tuple[list[Event], int]:
    # Nur für Laufen und nur bei bekannter Distanz, siehe Kommentar zu
    # MIN_DISTANCE_KM in scraper_lib.py.
    kept = [
        e for e in events
        if e.laenge_km is None or e.art1 != "Laufen" or e.laenge_km >= min_km
    ]
    skipped = len(events) - len(kept)
    return kept, skipped


def dedupe_key(
    name: str | None, datum_start: str | None, laenge_km: float | None = None
) -> tuple[str, str, float | None] | None:
    """Eindeutiger Schlüssel: Name + Startdatum + (gerundete) Distanz. Die
    Distanz gehört bewusst zum Schlüssel: viele Veranstalter bieten unter
    demselben Namen am selben Tag mehrere Distanzen an (10 km,
    Halbmarathon, Marathon) - das sind unterschiedliche Events und sollen
    nicht als Duplikat des ersten gefundenen Eintrags verworfen werden.
    Auf eine Nachkommastelle gerundet gegen kleine Formatierungsunterschiede
    (z. B. 42.2 vs. 42.195)."""
    if not name or not datum_start:
        return None
    rounded_km = round(laenge_km, 1) if isinstance(laenge_km, (int, float)) else None
    return (name.strip().casefold(), datum_start, rounded_km)


def merge_events(existing: list[dict], new_events: Iterable[Event]) -> tuple[list[dict], int, int]:
    """Fügt neue Events an, überspringt Duplikate. Zwei Stufen wie in
    `scraper_lib.merge_events()`: exakter Abgleich über `dedupe_key()`
    (Name + Startdatum + Distanz) und zusätzlich `is_same_event()` gegen
    alle Events desselben Datums - damit dasselbe Event nicht doppelt
    erscheint, wenn eine andere Quelle es unter abweichendem Namen liefert.
    Die dafür nötige Namens-/Orts-/Distanz-Logik wird aus `scraper_lib`
    importiert statt hier erneut implementiert (siehe Docstring oben:
    dieses Skript nutzt scraper_lib bewusst nicht für das Abrufen/Parsen,
    reine Vergleichslogik aber sehr wohl - sonst müsste sie doppelt
    gepflegt werden)."""
    from scraper_lib import ENRICHABLE_FIELDS, is_same_event  # lokaler Import, s. o.

    existing_keys = {
        dedupe_key(e.get("name"), e.get("datum_start"), e.get("laenge_km")) for e in existing
    }
    existing_keys.discard(None)

    merged = list(existing)
    by_date: dict[str | None, list[dict]] = {}
    for e in merged:
        by_date.setdefault(e.get("datum_start"), []).append(e)

    added = 0
    skipped = 0

    for event in new_events:
        if not event.is_valid():
            skipped += 1
            continue
        candidate = event.to_dict()
        key = dedupe_key(event.name, event.datum_start, event.laenge_km)
        if key is None or key in existing_keys:
            skipped += 1
            continue

        twin = next(
            (e for e in by_date.get(event.datum_start, []) if is_same_event(e, candidate)),
            None,
        )
        if twin is not None:
            for field in ENRICHABLE_FIELDS:
                if twin.get(field) is None and candidate.get(field) is not None:
                    twin[field] = candidate[field]
            skipped += 1
            continue

        merged.append(candidate)
        by_date.setdefault(event.datum_start, []).append(candidate)
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

    events_to_use, overrides_excluded = apply_manual_overrides(raw_events)
    if overrides_excluded:
        print(f"  ({overrides_excluded} Event(s) laut scripts/manual_overrides.json "
              f"ausgeschlossen, z. B. verifizierte Duplikate unter anderem Namen.)")

    events_to_use, too_short_skipped = filter_min_distance(events_to_use)
    if too_short_skipped:
        print(f"  ({too_short_skipped} Event(s) unter {MIN_DISTANCE_KM:g} km übersprungen.)")

    raw_events = events_to_use

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
