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
Name (`.headline`), PLZ+Ort (`.location`) und eine Distanz-SPANNE
(`.strecken .wettbewerbe`, Format "Strecke(n): X [bis Y] Kilometer").
`topevents` enthält dieselbe Kachel-Struktur (zusätzlich mit Bild/Badge)
für beworbene Veranstaltungen und wird identisch mitgeparst.

Detailseiten (wichtig für die Datenqualität)
---------------------------------------------
Die Ergebnisliste allein reicht nicht: sie nennt weder das Land noch die
einzelnen Wettbewerbe. Beim "10. Schnebelhorn Panoramatrail" etwa stand
dort nur "9607 Mosnang" (ohne "Schweiz") und "Strecken: 0,4 bis 21,1
Kilometer" - in events.json landete dadurch nur der Halbmarathon, der
ebenfalls angebotene "Moslig 8000" über 8,5 km fehlte komplett, und
`land` blieb leer.

`enrich_from_details()` ruft daher zusätzlich die Detailseite jedes
Events ab (`--no-details` schaltet das ab, `--max-details N` begrenzt es
für Testläufe) und liest dort:

* **Land**: `.teaser.event .location` nennt es hinter dem Ort, mal
  ausgeschrieben ("(Schweiz)"), mal als Kürzel ("(AUT)") - beides deckt
  `scraper_lib.guess_land()` ab.
* **Alle Wettbewerbe**, in zwei auf der Seite vorkommenden Layouts:
  `ul.all > li` ("Moslig 8000 (229 hm) | 8,5 km") und das ausführlichere
  `ul.races` mit `li.title` ("TST 86K | 86 km | + 3500 hm") plus
  `li.course` ("Trailrun"). Jede Strecke wird zu einem eigenen Eintrag,
  die Kategorie (art2) pro Strecke bestimmt.
* **Den echten Veranstalter-Link** ("Mehr Infos und Anmeldung", z. B.
  https://panoramatrail.ch/) statt des laufen.de-Portallinks.

Bereits gespeicherte Events werden dabei nachträglich vervollständigt
(siehe `update_existing()`), nicht nur übersprungen - sonst behielten die
aus früheren Läufen stammenden Einträge ihr fehlendes `land` und den
Portallink.

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
from urllib.parse import urljoin, urlparse
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
# Pfad-Präfix einer Event-Detailseite, z. B.
# /laufkalender/details/26I00000000000036 (siehe detail_url_from_href()).
DETAIL_PATH_PREFIX = "/laufkalender/details/"

# Höflicher, ehrlicher User-Agent (kein Fake-Browser-UA) – erleichtert es
# dem Seitenbetreiber, uns bei Bedarf zu blockieren oder zu kontaktieren.
USER_AGENT = (
    "EnduranceEventsBot/1.0 "
    "(+https://antdon930.github.io/Enduranceevents/; "
    "privater, nicht-kommerzieller Kalenderabgleich; Kontakt siehe Repo)"
)

DEFAULT_REQUEST_DELAY_SECONDS = 2.0  # Fallback, falls robots.txt keinen Crawl-Delay nennt
# Der Kalender liefert derzeit 25 Ergebnisseiten (die AJAX-Antwort nennt die
# Gesamtzahl in `pages`, die Schleife stoppt von selbst danach). Der frühere
# Wert 20 war KLEINER als das und hat die letzten fünf Seiten - also rund
# 150 Events - stillschweigend nie abgerufen. Bewusst mit Luft nach oben
# gesetzt; der Wert ist nur eine Endlosschleifen-Bremse, keine Zielgröße.
DEFAULT_MAX_PAGES = 40

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

# Selektoren auf der DETAILSEITE eines Events (siehe Docstring, Abschnitt
# "Detailseiten"). Am echten Seiteninhalt kalibriert.
DETAIL_SELECTORS = {
    # Ortsangabe MIT Land: "9607 Mosnang (Schweiz)" - in der Ergebnisliste
    # steht nur "9607 Mosnang", das Land fehlt dort komplett.
    "location": ".teaser.event .location",
    # Wettbewerbsliste, Variante A (schlichte Liste): je <li>
    # "<Bezeichnung> | <X> km".
    "competitions": ".mod_laufkalender_lauf_detail.strecken ul.all > li",
    # Variante B (ausführliche Darstellung): ein <ul class="races"> pro
    # Wettbewerb mit <li class="title"> ("TST 86K | 86 km | + 3500 hm")
    # und <li class="course"> ("Trailrun"). Kommt bei Veranstaltungen mit
    # detailliert gepflegten Strecken vor - ohne diese Variante fanden wir
    # dort KEINE Wettbewerbe und behielten nur die längste Strecke aus der
    # Ergebnisliste.
    "competitions_detailed": ".mod_laufkalender_lauf_detail.strecken ul.races",
    "competition_title": "li.title",
    "competition_course": "li.course",
    # "Mehr Infos und Anmeldung" / "Mehr Infos zum Event" -> echte
    # Veranstalter-Domain statt des laufen.de-Portallinks.
    "organizer_link": ".mod_laufkalender_lauf_detail .info.buttons a[href]",
}

# Bewusst nur ausgeschriebene Ländernamen, keine zweibuchstabigen Codes
# ("de"/"at"/"ch") - die schlagen in deutschem Fließtext falsch an.
LAND_KEYWORDS = {
    "deutschland": "Deutschland", "germany": "Deutschland",
    "österreich": "Österreich", "austria": "Österreich",
    "schweiz": "Schweiz", "switzerland": "Schweiz", "suisse": "Schweiz",
}

# Zuordnung Stichwort -> Kategorie (art2), passend zur im Projekt
# verwendeten Taxonomie für Laufen: Straße, Trail, Bahn, Hindernis
# ("Trail", "Cross" und "Berglauf" sind EINE Kategorie, siehe scraper_lib.py).
# Reihenfolge ist bewusst NICHT alphabetisch, sondern von spezifisch nach
# generisch: "Straße" (inkl. Marathon/Stadtlauf) steht bewusst ZULETZT,
# siehe ausführlichen Kommentar zu ART2_KEYWORDS_LAUFEN in scraper_lib.py
# (derselbe Bug/Fix, hier dupliziert weil dieses Skript scraper_lib.py
# bewusst nicht nutzt).
ART2_KEYWORDS = [
    (re.compile(r"hindernislauf|obstacle|ocr\b|spartan|tough mudder", re.I), "Hindernis"),
    (re.compile(r"trail|geländelauf|ultratrail", re.I), "Trail"),
    (re.compile(r"berglauf|bergrennen|bergmarathon|mountain ?run|gipfel|alpin|gebirg|höhenmeter", re.I), "Trail"),
    (re.compile(r"crosslauf|cross.?country|\bcross\b", re.I), "Trail"),
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
    wettbewerb: str | None = None
    veranstalter_url: str | None = None
    # Interner Zwischenspeicher, KEIN Ausgabefeld: die laufen.de-Detailseite
    # zu diesem Event (siehe fetch_detail()). Wird von to_dict() bewusst
    # nicht mitgeschrieben - der gespeicherte veranstalter_url soll nach dem
    # Detail-Abruf auf die Veranstalter-Seite zeigen, nicht auf das Portal.
    detail_url: str | None = None

    def is_valid(self) -> bool:
        """Minimalanforderung, damit ein Event überhaupt brauchbar ist."""
        return bool(self.name and self.datum_start and self.standort)

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d.pop("detail_url", None)  # rein intern, siehe Feldkommentar
        if d.get("laenge_km") is not None:
            d["laenge_km"] = round(float(d["laenge_km"]), 1)
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
    """Land aus einer Ortsangabe.

    Die Detailseite nennt es hinter dem Ort, mal ausgeschrieben
    ("9607 Mosnang (Schweiz)"), mal als Kürzel ("6020 Innsbruck (AUT)");
    in der Ergebnisliste steht nur die PLZ, und eine vierstellige PLZ
    unterscheidet Österreich und Schweiz nicht - dann bleibt `land` leer
    und wird später per Reverse-Geocoding aus den Koordinaten ergänzt.

    Die Logik dafür steht in scraper_lib und wird hier bewusst NICHT
    erneut implementiert: sie ist reine Textauswertung ohne Abruf-/
    Parsing-Bezug, und zwei Kopien davon sind schon einmal
    auseinandergelaufen.
    """
    from scraper_lib import guess_land as shared_guess_land
    return shared_guess_land(text)


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
    # Der VORKOMMATEIL erlaubt bis zu fünf Stellen, und (?<!\d) verhindert,
    # dass der Regex mitten in einer Zahl anfängt. Ohne beides wurde eine
    # vierstellige Distanz auf ihre letzten drei Stellen verkürzt - der
    # "Transeuropalauf" über 2067 km stand mit 67 km in events.json
    # (aus "2067" matchte nur "067"). Gleiche Fehlerklasse wie beim
    # Nachkommateil unten.
    # Nachkommateil bewusst UNBEGRENZT (\d+, nicht \d{1,2}/\d{1,3}): die
    # offiziellen Distanzen "42,195 Kilometer" (Marathon) und "21,0975 km"
    # (Halbmarathon) haben 3 bzw. 4 Nachkommastellen - mit einer festen
    # Obergrenze matcht der Regex nicht ab der Zahl vor dem Komma, sondern
    # (Bug, echt aufgetreten und mit realen Daten verifiziert) versehentlich
    # nur den Nachkommateil als vermeintlich eigenständige km-Angabe
    # (z. B. "975" statt 21,0975 oder "195" statt 42,195).
    matches = re.findall(r"(?<!\d)(\d{1,5}(?:[.,]\d+)?)\s*(?:km\b|Kilometer)", text, re.I)
    if matches:
        # Einheitlich eine Nachkommastelle: "42,195 km" -> 42.2
        # (siehe scraper_lib.round_km()).
        return round(max(float(m.replace(",", ".")) for m in matches), 1)
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
    """Trennt eine Ortsangabe in den reinen Ortsnamen auf.

    Ergebnisliste: '74821           Mosbach'
    Detailseite:   '9607 Mosnang (Schweiz)'

    PLZ und Landesangabe in Klammern werden entfernt - beide fließen
    bereits über `guess_land()` auf dem unveränderten Text in die
    Ländererkennung ein und gehören nicht in den Ortsnamen.
    """
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"\s*\((?:[^)]*)\)\s*$", "", normalized).strip()
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
                # Nur ECHTE Detailseiten auf laufen.de merken: einzelne
                # Kacheln verlinken direkt auf die Veranstalter-Seite
                # (z. B. www.lh-lauf.de). Die als Detailseite abzurufen
                # geht schief (404/SSL-Fehler beim Veranstalter, real
                # aufgetreten) und liefert ohnehin keine laufen.de-Struktur.
                # Als veranstalter_url ist so ein Link dagegen perfekt - er
                # steht oben schon drin.
                detail_url=detail_url_from_href(href),
            )
        )
    return events


def detail_url_from_href(href: str | None) -> str | None:
    """Gibt die absolute laufen.de-Detailseiten-URL zurück - oder None,
    wenn der Link woanders hinzeigt (siehe Kommentar oben)."""
    if not href:
        return None
    absolute = urljoin(CALENDAR_URL, href)
    return absolute if f"{BASE_URL}{DETAIL_PATH_PREFIX}" in absolute else None


# --------------------------------------------------------------------------
# Detailseiten: Land, alle Wettbewerbe, echter Veranstalter-Link
# --------------------------------------------------------------------------

def parse_detail_page(html: str, page_url: str) -> dict:
    """Liest die für uns relevanten Felder aus einer Event-Detailseite.

    Gibt ein Dict mit `location_text`, `competitions` (Rohtexte der
    <li>-Einträge) und `organizer_url` zurück; fehlende Teile fehlen
    einfach im Dict statt einen Fehler zu werfen - die Detailseiten sind
    nicht alle gleich vollständig.
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    loc_el = soup.select_one(DETAIL_SELECTORS["location"])
    if loc_el:
        result["location_text"] = loc_el.get_text(" ", strip=True)

    # Variante B zuerst: sie ist die ausführlichere Darstellung und nennt
    # zusätzlich die Art der Strecke ("Trailrun").
    competitions: list[tuple[str, str]] = []
    for block in soup.select(DETAIL_SELECTORS["competitions_detailed"]):
        title_el = block.select_one(DETAIL_SELECTORS["competition_title"])
        course_el = block.select_one(DETAIL_SELECTORS["competition_course"])
        if not title_el:
            continue
        competitions.append((
            title_el.get_text(" ", strip=True),
            course_el.get_text(" ", strip=True) if course_el else "",
        ))

    if not competitions:
        competitions = [
            (li.get_text(" ", strip=True), "")
            for li in soup.select(DETAIL_SELECTORS["competitions"])
        ]

    if competitions:
        result["competitions"] = competitions

    for link in soup.select(DETAIL_SELECTORS["organizer_link"]):
        href = (link.get("href") or "").strip()
        # Nur externe Links (die internen Buttons "Zurück zu den
        # Suchergebnissen"/"Neue Suche" zeigen wieder auf laufen.de) und
        # keine Shop-/Checkout-Links des Portals.
        if href.startswith("http") and "laufen.de" not in href:
            result["organizer_url"] = href
            break

    return result


# Wohin laufen.de eine Detailseite weiterleitet, ohne dass das der
# Veranstalter-Link wäre: Anmeldeportale, Zeitnehmer, soziale Netze -
# und laufen.de selbst (www-Variante). Ein Ziel auf einem dieser Hosts
# ist kein besserer Link als der Portallink, den wir schon haben.
WEITERLEITUNG_KEIN_VERANSTALTER = (
    # Zeitnehmer, Anmeldeplattformen und Kalender stehen seit dem
    # 19.09.2026 alle in PORTAL_DOMAINS (scraper_lib.py); die Prüfung
    # unten fragt is_portal_link(). Hier bleiben nur die sozialen Netze.
    "facebook.com", "fb.me", "instagram.com",
)


def veranstalter_link_aus_weiterleitung(detail_url: str, location: str | None) -> str | None:
    """Der Veranstalter-Link, auf den eine laufen.de-Detailseite weiterleitet
    - oder None, wenn das Ziel keiner ist.

    Jeder Detaillink `laufen.de/laufkalender/details/<id>` leitet per 302
    auf den Veranstalter-Link weiter, den der DLV-Kalender hinterlegt hat
    (gefunden am 19.09.2026: 182 von 208 gespeicherten Detaillinks). Vorher
    folgte `session.get()` der Weiterleitung stillschweigend,
    `parse_detail_page()` parste dann die Veranstalterseite als wäre sie
    eine laufen.de-Seite - fand dort natürlich keinen "Mehr Infos"-Link,
    und der Portallink blieb stehen. 215 Zeilen trugen deshalb einen
    laufen.de-Link, der in Wahrheit auf die offizielle Seite zeigte.

    Genommen wird das Ziel nur, wenn es auf einem fremden Host liegt und
    dieser weder Portal (`is_portal_link`) noch Anmeldung/Zeitnahme/
    soziales Netz ist (WEITERLEITUNG_KEIN_VERANSTALTER). Vom Nutzer am
    19.09.2026 freigegeben (Entscheidungspunkt 15 in CLAUDE.md).
    """
    # Wie überall in diesem Skript: scraper_lib erst bei Bedarf laden.
    from scraper_lib import is_portal_link

    if not location:
        return None
    ziel = urljoin(detail_url, location.strip())
    parsed = urlparse(ziel)
    if parsed.scheme not in ("http", "https"):
        return None
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    if not host or "." not in host:
        return None
    if any(host == d or host.endswith("." + d) for d in WEITERLEITUNG_KEIN_VERANSTALTER):
        return None
    if is_portal_link(ziel):
        return None
    return ziel


def enrich_from_details(
    session: requests.Session,
    events: list[Event],
    delay: float,
    max_details: int,
) -> list[Event]:
    """Ruft für jedes Event die Detailseite ab und macht daraus je einen
    Eintrag pro Wettbewerb.

    Warum überhaupt: Die Ergebnisliste (AJAX) nennt weder das Land noch die
    einzelnen Wettbewerbe - sie zeigt nur eine Spanne ("Strecken: 0,4 bis
    21,1 Kilometer") und eine PLZ ohne Land. Dadurch landete vom
    "10. Schnebelhorn Panoramatrail" nur der Halbmarathon in events.json,
    der ebenfalls angebotene "Moslig 8000" über 8,5 km fehlte, und das Land
    (Schweiz) blieb leer. Beides steht auf der Detailseite.

    Events, deren Detailseite nicht geladen werden kann, bleiben unverändert
    erhalten (Stand aus der Ergebnisliste) statt verloren zu gehen.
    """
    from scraper_lib import SiteConfig, expand_competitions, parse_competitions

    # Für parse_competitions()/expand_competitions() wird eine SiteConfig
    # nur als Träger der Stichwortlisten gebraucht; Abruf/Parsing macht
    # dieses Skript selbst (siehe Docstring).
    helper_config = SiteConfig(base_url=BASE_URL, calendar_url=CALENDAR_URL)

    todo = [e for e in events if e.detail_url]
    if max_details and len(todo) > max_details:
        print(f"ℹ Detail-Abruf auf die ersten {max_details} von {len(todo)} "
              f"Events begrenzt (--max-details).")
        todo = todo[:max_details]
    todo_ids = {id(e) for e in todo}

    print(f"\n→ Rufe {len(todo)} Detailseite(n) ab (je {delay:.1f}s Pause, "
          f"also ca. {len(todo) * delay / 60:.0f} Minuten) ...")

    result: list[Event] = []
    fetched = failed = expanded = weitergeleitet = 0

    for event in events:
        if id(event) not in todo_ids:
            result.append(event)
            continue

        # Zwischenstand, damit ein langer Lauf nicht minutenlang stumm ist.
        if (fetched + failed) % 50 == 0 and (fetched + failed) > 0:
            print(f"  … {fetched + failed}/{len(todo)} Detailseiten verarbeitet.")

        try:
            # Ohne allow_redirects: Die Weiterleitung IST die Information
            # (siehe veranstalter_link_aus_weiterleitung()).
            resp = session.get(event.detail_url, timeout=20, allow_redirects=False)
            if 300 <= resp.status_code < 400:
                ziel = resp.headers.get("Location")
                link = veranstalter_link_aus_weiterleitung(event.detail_url, ziel)
                if link:
                    event.veranstalter_url = link
                    weitergeleitet += 1
                # Weitergeleitet wird auch auf Portale und Anmeldungen -
                # dann bleibt der Portallink. In beiden Fällen gibt es
                # keine laufen.de-Detailseite zum Parsen: Wettbewerbe und
                # Land bleiben auf dem Stand der Ergebnisliste.
                result.append(event)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            detail = parse_detail_page(resp.text, event.detail_url)
            fetched += 1
        except requests.exceptions.RequestException as exc:
            print(f"  ⚠ Detailseite nicht ladbar ({event.name}): {exc}")
            failed += 1
            result.append(event)
            time.sleep(delay)
            continue

        location_text = detail.get("location_text")
        if location_text:
            land = guess_land(location_text)
            if land:
                event.land = land
            ort = parse_location(location_text)
            if ort:
                event.standort = ort

        # Der Portallink bleibt als Fallback, wenn die Detailseite keinen
        # externen Link anbietet.
        if detail.get("organizer_url"):
            event.veranstalter_url = detail["organizer_url"]

        competitions = parse_competitions(detail.get("competitions") or [], helper_config)
        variants = expand_competitions(event, competitions, helper_config)
        if len(variants) > 1:
            expanded += 1
        result.extend(variants)

        time.sleep(delay)

    print(f"\n→ Detailseiten: {fetched} geladen, {weitergeleitet} auf den "
          f"Veranstalter weitergeleitet, {failed} fehlgeschlagen; "
          f"{expanded} Veranstaltung(en) in mehrere Wettbewerbe aufgeteilt "
          f"({len(events)} -> {len(result)} Einträge).")
    return result


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
    from scraper_lib import is_same_event  # lokaler Import, s. o.

    merged = list(existing)
    by_key: dict[tuple, dict] = {}
    for e in merged:
        key = dedupe_key(e.get("name"), e.get("datum_start"), e.get("laenge_km"))
        if key is not None:
            by_key.setdefault(key, e)

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
        if key is None:
            skipped += 1
            continue

        twin = by_key.get(key)
        if twin is None:
            twin = next(
                (e for e in by_date.get(event.datum_start, []) if is_same_event(e, candidate)),
                None,
            )

        if twin is not None:
            # Bewusst NICHT nur überspringen: ein bereits gespeicherter
            # Eintrag kann aus einem früheren Lauf stammen, dem noch
            # Felder fehlen (z. B. `land`, weil es nur auf der Detailseite
            # steht). Die jetzt vollständigeren Daten werden ergänzt.
            update_existing(twin, candidate)
            skipped += 1
            continue

        merged.append(candidate)
        by_key[key] = candidate
        by_date.setdefault(event.datum_start, []).append(candidate)
        added += 1

    return merged, added, skipped


def update_existing(target: dict, source: dict) -> None:
    """Ergänzt fehlende Felder eines gespeicherten Events und ersetzt einen
    Portal-Link durch den echten Veranstalter-Link. Gemeinsame Logik, siehe
    `scraper_lib.update_existing_event()`."""
    from scraper_lib import update_existing_event  # lokaler Import, s. merge_events

    update_existing_event(target, source)


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
        "--no-details", action="store_true",
        help="Detailseiten der Events NICHT abrufen. Schneller, liefert aber "
             "kein Land und nur die längste Strecke statt aller Wettbewerbe.",
    )
    parser.add_argument(
        "--max-details", type=int, default=0,
        help="Höchstens so viele Detailseiten abrufen (0 = alle). Nützlich für Testläufe.",
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

    # Detailseiten liefern Land, alle Wettbewerbe und den echten
    # Veranstalter-Link (siehe enrich_from_details()). Das ist der teure
    # Teil (ein Request pro Event, mit robots.txt-Pause), deshalb
    # abschaltbar.
    if not args.no_details:
        raw_events = enrich_from_details(session, raw_events, delay, args.max_details)

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
