#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper_lib.py
=================

Gemeinsame Bibliothek für die "einfachen" Lauf-Kalender-Scraper in diesem
Verzeichnis (aktuell u. a. `runnersworld_scraper.py`, `runninglife_scraper.py`,
`runningcompany_scraper.py`, `blvsport_scraper.py`, `ahotu_scraper.py`,
`planetmarathon_scraper.py`). Enthält robots.txt-Prüfung, Datum-/Land-/
Kategorie-/Distanz-Erkennung, Geocoding mit Cache, JSON-LD- und
HTML-Fallback-Parsing sowie die komplette CLI/main()-Logik als
`run_scraper_cli(SiteConfig)`.

Dieses Modul ist selbst KEIN eigenständiger Scraper (kein `*_scraper.py`-
Suffix, wird daher von `update_events.py`s Auto-Discovery absichtlich
NICHT als Scraper erkannt und ausgeführt) – jedes einzelne Scraper-Skript
importiert es und liefert nur seine standortspezifische `SiteConfig`.

`laufkalender_scraper.py` und `ironman_scraper.py` (die ersten beiden,
bereits gegen echte Infrastruktur verifizierten Skripte) nutzen dieses
Modul bewusst NICHT, um ihr getestetes Verhalten nicht zu verändern.

Ein neues Scraper-Skript mit dieser Bibliothek anlegen
----------------------------------------------------------
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scraper_lib import SiteConfig, run_scraper_cli

    CONFIG = SiteConfig(
        base_url="https://example.com",
        calendar_url="https://example.com/laufkalender/",
    )

    if __name__ == "__main__":
        run_scraper_cli(CONFIG)

Die HTML-Fallback-Selektoren (`SiteConfig.html_fallback_selectors`) sind
Platzhalter und müssen nach einem Blick in den echten Seitenquelltext der
jeweiligen Seite kalibriert werden, falls dort kein JSON-LD vorhanden ist
(siehe `DEFAULT_HTML_FALLBACK_SELECTORS` unten).
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field, fields, replace
from datetime import date
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON_PATH = REPO_ROOT / "events.json"
# Gemeinsamer Geocoding-Cache mit den anderen Scraper-Skripten.
GEOCODE_CACHE_PATH = REPO_ROOT / "scripts" / ".geocode_cache.json"

USER_AGENT = (
    "EnduranceEventsBot/1.0 "
    "(+https://antdon930.github.io/Enduranceevents/; "
    "privater, nicht-kommerzieller Kalenderabgleich; Kontakt siehe Repo)"
)

DEFAULT_REQUEST_DELAY_SECONDS = 2.0
DEFAULT_MAX_PAGES = 10

DEFAULT_NEXT_PAGE_SELECTORS = [
    'a[rel="next"]',
    "a.pagination-next",
    "a.next",
    'a[aria-label="Nächste Seite"]',
    'a[aria-label="Weiter"]',
    'a[aria-label="Next"]',
]

# TODO: ANPASSEN je Seite (per SiteConfig.html_fallback_selectors
# überschreibbar) – dies sind nur generische Platzhalter. Bewusst KEINE
# Wildcard-Attributselektoren wie div[class*='event'): die matchen sonst
# auch verschachtelte Sub-Elemente der Karte selbst (z.B. .event-location)
# und liefern dann mehrfach kaputte/leere Treffer.
DEFAULT_HTML_FALLBACK_SELECTORS = {
    "event_card": "article.event-card, li.event-item, div.event-teaser, "
                  "tr.event-row, div.race-card, li.race-item, article.race-teaser",
    "name": "h2, h3, .event-title, .race-title, td.name",
    "date": "time, .event-date, .race-date, td.date",
    "location": ".event-location, .event-city, .race-location, td.location",
    "link": "a",
    "category": ".event-category, .event-type, .race-type",
    "distance": ".event-distance, .race-distance, td.distance",
}

# Stichwörter für die Ländererkennung in FREIEM TEXT (Ortsangaben wie
# "9607 Mosnang (Schweiz)"). Bewusst nur ausgeschriebene Ländernamen:
# die zweibuchstabigen Codes ("de", "at", "ch") stehen hier NICHT, weil
# sie in deutschem Fließtext als eigenständige Wörter vorkommen und
# falsch anschlagen. Für explizite Code-Felder (z. B. JSON-LD
# `addressCountry: "DE"`) ist COUNTRY_CODE_MAP zuständig.
LAND_KEYWORDS = {
    "deutschland": "Deutschland", "germany": "Deutschland",
    "österreich": "Österreich", "austria": "Österreich",
    "schweiz": "Schweiz", "switzerland": "Schweiz", "suisse": "Schweiz",
}
COUNTRY_CODE_MAP = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
DACH_LAENDER = {"Deutschland", "Österreich", "Schweiz"}

# Länderkürzel, wie Kalender sie in KLAMMERN hinter den Ort schreiben -
# laufen.de mischt ausgeschriebene Namen und Kürzel: "9607 Mosnang
# (Schweiz)" neben "6020 Innsbruck (AUT)". Ohne diese Tabelle blieb `land`
# bei allen so ausgezeichneten Events leer (echter Bug, an den
# Österreich-Events aufgefallen). Nur in einem Klammerzusatz ausgewertet,
# nie in freiem Text - "A" oder "D" mitten im Satz sagt nichts über das Land.
LAND_ABBREVIATIONS = {
    "D": "Deutschland", "GER": "Deutschland", "DEU": "Deutschland",
    "A": "Österreich", "AUT": "Österreich",
    "CH": "Schweiz", "SUI": "Schweiz", "CHE": "Schweiz",
}
# Klammerzusatz am Ende einer Ortsangabe: "... (Schweiz)" / "... (AUT)".
_LAND_PARENTHETICAL = re.compile(r"\(\s*([A-Za-zÄÖÜäöüß.]{1,20})\s*\)\s*$")

# Deutsche Landschaftsnamen, die das Wort "Schweiz" enthalten, aber
# mitten in Deutschland liegen. Ohne diesen Filter stufte die
# Stichwortsuche z. B. den "25. Fränkische-Schweiz-Marathon" in
# Ebermannstadt (Bayern) als Schweizer Event ein - echter Bug, in
# events.json aufgetreten.
FALSE_LAND_PATTERNS = re.compile(
    r"(fränkische|holsteinische|sächsische|märkische|mecklenburgische|"
    r"schwäbische|thüringer)[ -]schweiz",
    re.I,
)

# Land aus der Postleitzahl: In der DACH-Region sind deutsche PLZ
# fünfstellig, österreichische und schweizerische vierstellig. Vier
# Stellen allein unterscheiden AT und CH also NICHT - in dem Fall
# bleibt `land` leer, statt zu raten (und wird später über die
# Koordinaten per Reverse-Geocoding nachgetragen, siehe
# Geocoder.reverse_land()).
PLZ_DE_PATTERN = re.compile(r"\b\d{5}\b")

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

# Zuordnung Stichwort -> Kategorie (art2), passend zur Projekt-Taxonomie für
# Laufen: Straße, Trail, Bahn, Berg, Cross, Hindernis.
# Reihenfolge ist bewusst NICHT alphabetisch, sondern von spezifisch nach
# generisch: "Straße" (inkl. Marathon/Stadtlauf) steht bewusst ZULETZT.
# Ein Name wie "5. Beck HochRhön Bergtrail 42k Trail-Marathon" enthält das
# Wort "Marathon" - ohne diese Reihenfolge würde die Straße-Regel zuerst
# zutreffen und das Event fälschlich als Straßenlauf einstufen (echter
# Bug, mit realen Daten verifiziert), obwohl "Bergtrail"/"Trail-Marathon"
# eindeutig einen Trail-/Geländelauf beschreibt.
ART2_KEYWORDS_LAUFEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"hindernislauf|obstacle|ocr\b|spartan|tough mudder", re.I), "Hindernis"),
    # Vor "Trail": ein "Backcountry Ultra Trail" ist ein Backcountry Ultra,
    # kein gewöhnlicher Trail. Absichtlich NUR das Wort "backcountry" -
    # ein Backyard Ultra (Rundenformat nach Big's Backyard) ist ein anderes
    # Format und wird nicht automatisch hierher einsortiert.
    (re.compile(r"backcountry", re.I), "Backcountry Ultra"),
    (re.compile(r"trail|geländelauf|ultratrail", re.I), "Trail"),
    # "backyard" steht NACH "Trail" - und das ist der ganze Trick: Ein
    # reiner "Backyard Ultra" (Last-Man-Standing: gleiche Runde zur
    # gleichen Stunde, bis nur noch eine Person weiterläuft) landet hier
    # bei Backcountry Ultra. Heißt das Event dagegen "Backyard Ultra
    # Trail", greift die Trail-Regel eine Zeile höher zuerst - dann ist es
    # ein Trailrun, der das Wort nur im Namen trägt, und genau so soll es
    # sein (ausdrückliche Vorgabe des Nutzers).
    (re.compile(r"backyard|last ?man ?standing|last ?person ?standing", re.I),
     "Backcountry Ultra"),
    # "Höhenmeter" im Text ist ein starkes Indiz für einen Berg-/Gelände-
    # lauf statt eines flachen Straßenlaufs, unabhängig vom Namen.
    (re.compile(r"berglauf|bergrennen|bergmarathon|mountain ?run|gipfel|alpin|gebirg|höhenmeter", re.I), "Berg"),
    (re.compile(r"crosslauf|cross.?country|\bcross\b", re.I), "Cross"),
    (re.compile(r"bahn(meeting)?|leichtathletik.?meeting", re.I), "Bahn"),
    (re.compile(r"halbmarathon|marathon|stadtlauf|straßenlauf|city ?run|\bstraße\b", re.I), "Straße"),
]
DEFAULT_ART2_LAUFEN = "Straße"

KNOWN_DISTANCES_KM_LAUFEN = {
    "marathon": 42.2,
    "halbmarathon": 21.1,
    "10 km": 10.0,
    "5 km": 5.0,
}


# --------------------------------------------------------------------------
# Konfiguration pro Seite
# --------------------------------------------------------------------------

@dataclass
class SiteConfig:
    base_url: str
    calendar_url: str
    default_art1: str = "Laufen"
    html_fallback_selectors: dict = field(default_factory=lambda: dict(DEFAULT_HTML_FALLBACK_SELECTORS))
    next_page_selectors: list = field(default_factory=lambda: list(DEFAULT_NEXT_PAGE_SELECTORS))
    known_distances_km: dict = field(default_factory=lambda: dict(KNOWN_DISTANCES_KM_LAUFEN))
    art2_keywords: list = field(default_factory=lambda: list(ART2_KEYWORDS_LAUFEN))
    default_art2: str | None = DEFAULT_ART2_LAUFEN
    # Land, das verwendet wird, wenn weder JSON-LD/HTML-Text noch PLZ ein Land
    # erkennen lassen - sinnvoll für Seiten mit bekanntem, festem regionalen
    # Fokus (z. B. blv-sport.de: Bayern, planet-marathon.de: nur Deutschland).
    default_land: str | None = None
    dach_only: bool = True
    note: str = ""  # optionaler Hinweis, wird beim Start ausgegeben (z. B. Verdacht auf JS-Rendering)
    # Optionaler Ersatz für fetch_all_events() bei Seiten, deren Struktur
    # (z. B. eine AJAX-Suche, ein Akkordeon aus HTML-Tabellen ohne CSS-Klassen
    # o. Ä.) sich nicht über die generischen HTML-Fallback-Selektoren
    # abbilden lässt. Signatur identisch zu fetch_all_events (ohne config,
    # da die Funktion sich meist ohnehin nur für eine Seite eignet):
    # (session, config, delay, max_pages, render_js) -> list[Event].
    # Wird gesetzt, übernimmt run_scraper_cli() den kompletten Fetch/Parse-
    # Schritt von dieser Funktion statt fetch_all_events(); robots.txt-Prüfung,
    # Geocoding, Dedupe/Merge und das Schreiben von events.json bleiben
    # unverändert gemeinsame Logik.
    custom_fetch: Callable[..., list] | None = None
    # Von run_scraper_cli() aus den CLI-Optionen --no-details/--max-details
    # gesetzt und von `custom_fetch`-Funktionen ausgelesen, die zusätzlich
    # die Detailseite jedes Events abrufen (nur dort stehen bei einigen
    # Quellen die offizielle Veranstalter-Seite und die einzelnen
    # Wettbewerbe). `max_details = 0` bedeutet "alle".
    fetch_details: bool = True
    max_details: int = 0


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
    art1: str = "Laufen"
    art2: str | None = None
    datum_start: str | None = None
    datum_ende: str | None = None
    anmeldeschluss: str | None = None
    laenge_km: float | None = None
    # Zeitlich begrenzte Rennen (24-Stunden-Lauf, 6h, 12h) haben keine feste
    # Streckenlänge - dort steht die Dauer in STUNDEN. In der Liste erscheint
    # sie in derselben Spalte wie die Distanz ("24 h" statt "42.2 km"), siehe
    # formatLength() in events.html. Bewusst ein eigenes Feld: eine Dauer in
    # laenge_km zu schreiben würde Von/Bis-Filter, Sortierung und die
    # Distanz-Kategorien durcheinanderbringen.
    dauer_h: float | None = None
    # Name des konkreten Wettbewerbs innerhalb der Veranstaltung, falls die
    # Quelle mehrere Strecken einzeln ausweist (z. B. "Moslig 8000" und
    # "Halbmarathon" beim Schnebelhorn Panoramatrail). Jede Strecke wird zu
    # einem eigenen Eintrag; dieses Feld sagt, welche gemeint ist.
    wettbewerb: str | None = None
    veranstalter_url: str | None = None

    def is_valid(self) -> bool:
        return bool(self.name and self.datum_start and self.standort)

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        # Einheitlich eine Nachkommastelle, egal woher der Wert kommt
        # (Regex, JSON-LD, manuelles Override) - siehe round_km().
        if d.get("laenge_km") is not None:
            d["laenge_km"] = round_km(d["laenge_km"])
        if d.get("dauer_h") is not None:
            d["dauer_h"] = round(float(d["dauer_h"]), 1)
        return {k: v for k, v in d.items() if v is not None}


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------

def check_robots(session: requests.Session, base_url: str, target_url: str) -> float:
    """Prüft robots.txt live gegen `target_url`. Gibt die zu verwendende
    Pause zwischen Requests zurück (Sekunden). Bricht mit sys.exit(1) ab,
    falls der Pfad gesperrt ist oder robots.txt nicht geladen werden kann."""
    robots_url = urljoin(base_url, "/robots.txt")
    print(f"→ Lade robots.txt von {robots_url} ...")
    try:
        resp = session.get(robots_url, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            # Per robots.txt-Konvention (RFC 9309 §2.3.1.3, ebenso Googles
            # robots.txt-Spezifikation): fehlt robots.txt (404), gelten
            # KEINE Einschränkungen - Crawlen ist dann uneingeschränkt
            # erlaubt. Kein Abbruch, nur ein Hinweis.
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
            "Netzwerk-/Firewall-Proxy blockiert die Domain, oder die Seite "
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
# Hilfsfunktionen: Datum, Land, Kategorie, Distanz
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

    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

    m = re.search(r"\b(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]+)\s+(\d{4})\b", text)
    if m and m.group(2).lower() in GERMAN_MONTHS:
        d, y = int(m.group(1)), int(m.group(3))
        mo = GERMAN_MONTHS[m.group(2).lower()]
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

    m = re.search(r"\b([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})\b", text)
    if m and m.group(1).lower() in ENGLISH_MONTHS:
        mo = ENGLISH_MONTHS[m.group(1).lower()]
        d, y = int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None

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
    """Erkennt das Land aus einer Ortsangabe wie '9607 Mosnang (Schweiz)'.

    Bewusst nur auf ORTSANGABEN anwenden, nicht auf Event-Namen: ein Name
    wie "25. Fränkische-Schweiz-Marathon" enthält das Wort "Schweiz",
    liegt aber in Bayern (siehe FALSE_LAND_PATTERNS, der diesen Fall
    zusätzlich abfängt).
    """
    if not text:
        return None
    cleaned = FALSE_LAND_PATTERNS.sub(" ", text)

    # Zuerst der Klammerzusatz: die verlässlichste Angabe, wenn vorhanden
    # (deckt "(Schweiz)" ebenso wie "(AUT)" ab, siehe LAND_ABBREVIATIONS).
    paren = _LAND_PARENTHETICAL.search(re.sub(r"\s+", " ", cleaned).strip())
    if paren:
        token = paren.group(1).strip(".")
        by_abbrev = LAND_ABBREVIATIONS.get(token.upper())
        if by_abbrev:
            return by_abbrev
        by_name = LAND_KEYWORDS.get(token.casefold())
        if by_name:
            return by_name

    lowered = cleaned.lower()
    for keyword, land in LAND_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return land
    if PLZ_DE_PATTERN.search(cleaned):  # fünfstellige PLZ -> Deutschland
        return "Deutschland"
    return None


def round_km(value: float | int | None) -> float | None:
    """Rundet eine Distanz auf EINE Nachkommastelle.

    Quellen geben dieselbe Strecke unterschiedlich genau an - Marathon als
    "42,195 km", Halbmarathon als "21,0975 km". In der Liste soll einheitlich
    42.2 bzw. 21.1 stehen (Wunsch aus dem Chat), und die Duplikat-Erkennung
    vergleicht Distanzen ohnehin nur auf eine Nachkommastelle.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return round(float(value), 1)


def guess_art2(text: str, config: SiteConfig) -> str | None:
    for pattern, kategorie in config.art2_keywords:
        if pattern.search(text or ""):
            return kategorie
    return config.default_art2


def guess_distance_km(text: str, config: SiteConfig) -> float | None:
    if not text:
        return None
    # Der VORKOMMATEIL erlaubt bis zu fünf Stellen, und (?<!\d) verhindert,
    # dass der Regex mitten in einer Zahl anfängt. Ohne beides wurde eine
    # vierstellige Distanz auf ihre letzten drei Stellen verkürzt - der
    # "Transeuropalauf" über 2067 km stand mit 67 km in events.json
    # (aus "2067" matchte nur "067"). Gleiche Fehlerklasse wie beim
    # Nachkommateil unten.
    # Nachkommateil bewusst UNBEGRENZT (\d+, nicht \d{1,2}/\d{1,3}): die
    # offiziellen Distanzen "42,195 km" (Marathon) und "21,0975 km"
    # (Halbmarathon) haben 3 bzw. 4 Nachkommastellen - mit einer festen
    # Obergrenze matcht der Regex nicht ab der Zahl vor dem Komma, sondern
    # (Bug, echt aufgetreten und mit realen Daten verifiziert) versehentlich
    # nur den Nachkommateil als vermeintlich eigenständige km-Angabe
    # (z. B. "975" aus "21,0975"). Bei mehreren Treffern (z. B. "5 km,
    # 10 km, 42,195 km") wird die größte Distanz übernommen (das
    # "Hauptrennen"). Sowohl "km" als auch ausgeschriebenes "Kilometer"
    # (z. B. running.life-Beschreibungstexte: "Du kannst 5 Kilometer
    # laufen.") werden erkannt.
    matches = re.findall(r"(?<!\d)(\d{1,5}(?:[.,]\d+)?)\s*(?:km\b|Kilometer)", text, re.I)
    if matches:
        # Auf eine Nachkommastelle runden: "42,195 km" -> 42.2 (siehe round_km).
        return round_km(max(float(m.replace(",", ".")) for m in matches))
    # Fallback über bekannte Renn-Bezeichnungen. Bewusst nach Stichwort-
    # LÄNGE absteigend geprüft, nicht in Dict-Reihenfolge: "halbmarathon"
    # enthält die Teilkette "marathon", ein Name wie "35. Halbmarathon
    # Altötting" wurde dadurch mit 42,2 km statt 21,1 km eingetragen
    # (echter, mit realen Daten verifizierter Bug). Das längste passende
    # Stichwort ist immer das spezifischste.
    lowered = text.lower()
    for keyword in sorted(config.known_distances_km, key=len, reverse=True):
        if keyword and keyword in lowered:
            return config.known_distances_km[keyword]
    # Leeres Stichwort "" als bewusster Catch-all (z. B. planet-marathon.de:
    # dort ist laut Seitenhinweis jedes Event ein Marathon) - erst ganz am
    # Ende, damit es echte Stichwort-Treffer nie verdeckt.
    if "" in config.known_distances_km:
        return config.known_distances_km[""]
    return None


# --------------------------------------------------------------------------
# Wettbewerbe: mehrere Strecken einer Veranstaltung -> mehrere Einträge
# --------------------------------------------------------------------------
#
# Fast jede Laufveranstaltung bietet mehrere Strecken an. Früher hat jeder
# Scraper daraus nur EINE Zahl gemacht (die längste) und alle anderen
# Strecken verworfen - beim "10. Schnebelhorn Panoramatrail" etwa stand nur
# der Halbmarathon in der Liste, der ebenfalls angebotene "Moslig 8000"
# über 8,5 km fehlte komplett, obwohl die Quelle ihn ausweist. Die
# folgenden Helfer lesen die Wettbewerbsliste aus und machen daraus je
# einen eigenen Eintrag (gewünschtes Verhalten laut Chat).

# Klammerzusätze wie "(229 hm)" oder "(989 hm)" gehören zur Strecken-
# beschreibung, nicht zum Namen des Wettbewerbs.
_HM_SUFFIX_PATTERN = re.compile(r"\s*\(\s*[\d.,]+\s*(?:hm|höhenmeter|m\b)[^)]*\)", re.I)
# Alles ab dem Trenner "|" ist bei laufen.de die Distanzangabe.
_COMPETITION_SPLIT = re.compile(r"\s*\|\s*")
# running.life schreibt die Strecken als Satz: "VR Bank - BraunenBerg-Lauf:
# 14,6 km, ca. 400 Hm, Strecke endet in Oberalfingen." Alles ab dem
# Doppelpunkt ist Beschreibung, sofern danach eine Zahl folgt (sonst wäre
# ein Name, der auf einen Doppelpunkt endet, fälschlich abgeschnitten).
_LABEL_COLON_SPLIT = re.compile(r"^([^:]{2,80}?):\s*(?=.*\d)")
# Sicherheitsnetz: ein Label ist ein Name, kein Satz.
_MAX_LABEL_LENGTH = 60


def clean_competition_label(text: str) -> str | None:
    """Reduziert einen Wettbewerbs-Eintrag auf seinen Namen.

    'Moslig 8000 (229 hm) | 8,5 km'                    -> 'Moslig 8000'
    'TST 86K | 86 km | + 3500 hm'                      -> 'TST 86K'
    'VR Bank - BraunenBerg-Lauf: 14,6 km, ca. 400 Hm'  -> 'VR Bank - BraunenBerg-Lauf'
    """
    if not text:
        return None
    normalized = re.sub(r"\s+", " ", text).strip()
    label = _COMPETITION_SPLIT.split(normalized)[0]
    colon = _LABEL_COLON_SPLIT.match(label)
    if colon:
        label = colon.group(1)
    label = _HM_SUFFIX_PATTERN.sub("", label).strip(" -–·,;")
    if len(label) > _MAX_LABEL_LENGTH:
        return None  # offensichtlich ein Satz, kein Wettbewerbsname
    return label or None


# Höhenmeter-Angabe einer Strecke: "ca. 1100 Hm", "+ 3500 hm", "(989 hm)",
# "229 Höhenmeter". Der Tausenderpunkt ("1.100 hm") wird mitgelesen.
_ELEVATION_PATTERN = re.compile(r"(\d{1,2}(?:[.\s]\d{3})+|\d{2,5})\s*(?:hm\b|höhenmeter)", re.I)

# Ab diesem Anstieg pro Kilometer gilt eine Strecke als Berglauf, wenn der
# Name nichts Spezifischeres sagt. Hintergrund: Ein flacher Stadt- oder
# Straßenmarathon liegt bei unter 5 m/km, ein Berg-/Traillauf klar darüber
# (BraunenBerg-Lauf: 400 hm auf 14,6 km = 27 m/km; BergBau-Lauf: 248 hm auf
# 8,2 km = 30 m/km; Nordkette Vertical Run: 1332 hm auf 6,7 km = 199 m/km).
# 20 m/km liegt bewusst deutlich über dem Profil eines Straßenlaufs, damit
# ein Stadtlauf mit ein paar Brücken nicht fälschlich zum Berglauf wird.
ELEVATION_BERG_M_PER_KM = 20.0


def parse_elevation_m(text: str) -> float | None:
    """Liest die Höhenmeter aus einer Streckenbeschreibung."""
    if not text:
        return None
    match = _ELEVATION_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(re.sub(r"[.\s]", "", match.group(1)))
    except ValueError:
        return None


# Zeitlich begrenzte Rennen ("24-Stunden-Lauf", "6h Backyard", "12h")
# haben keine feste Streckenlänge. Erkannt wird die Dauer aus dem Namen
# bzw. dem Wettbewerbs-Label; das Ergebnis landet in `dauer_h`.
#
# Zwei Fehlerquellen, gegen die die Regex absichern muss:
#
#   * "229 hm" sind Höhenmeter, keine 229 Stunden. Deshalb steht hinter
#     dem "h" ein negativer Lookahead auf "m"/"öhenmeter".
#   * Ein "Zeitlimit: 6 Stunden" oder "Karenzzeit 6 h" ist eine
#     ZIELSCHLUSSZEIT für einen Lauf mit fester Strecke - das macht aus
#     einem Marathon kein 6-Stunden-Rennen. Steht eines dieser Wörter
#     kurz davor, wird der Treffer verworfen.
#
# Plausibel sind 1 bis 72 Stunden (typisch 6/12/24/48; Backyard-Rennen
# laufen theoretisch länger, geben aber keine Dauer an).
_DURATION_PATTERN = re.compile(
    r"(?<![\w,.:])(\d{1,3}(?:[.,]5)?)\s*[-‑–]?\s*"
    r"(?:h(?![a-zäöü])|std\.?|stunden(?:lauf|rennen)?|stunden-?lauf|hours?|hrs?\b)",
    re.I,
)
_DURATION_FALSE_FRIENDS = re.compile(
    r"(zeit-?limit|limit|karenz|h[öo]chstzeit|zielschluss|cut.?off|"
    r"maximal|max\.?|mindest|start(zeit)?|beginn|uhrzeit|ab\s*$)",
    re.I,
)
_DURATION_CONVERSION = re.compile(
    r"\s*(ergeben|ergibt|entspricht|entsprechen|sind|=|macht)\b", re.I)
DURATION_MIN_H = 1.0
DURATION_MAX_H = 72.0


def parse_duration_h(text: str) -> float | None:
    """Liest die Dauer eines zeitlich begrenzten Rennens in Stunden.

    Gibt None zurück, wenn der Text keine Dauer nennt oder der Treffer
    eine Zielschlusszeit bzw. Höhenmeterangabe ist (siehe
    _DURATION_FALSE_FRIENDS). Auf Unsicherheit hin wird NICHTS gesetzt -
    ein falsch als Zeitrennen markierter Marathon verliert seine Distanz
    in der Anzeige, und das fällt niemandem auf."""
    if not text:
        return None
    for match in _DURATION_PATTERN.finditer(text):
        vorher = text[max(0, match.start() - 24):match.start()]
        if _DURATION_FALSE_FRIENDS.search(vorher):
            continue
        # Umrechnungssatz statt Zeitvorgabe: "6,708 km pro Runde; 24 Stunden
        # ergeben 100 Meilen" beschreibt das Format eines Backyard Ultra,
        # begrenzt ihn aber nicht - der läuft, bis nur noch eine Person übrig
        # ist.
        if _DURATION_CONVERSION.match(text[match.end():]):
            continue
        try:
            wert = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if DURATION_MIN_H <= wert <= DURATION_MAX_H:
            return round(wert, 1)
    return None


def art2_from_elevation(text: str, laenge_km: float | None, current: str | None) -> str | None:
    """Stuft eine Strecke anhand ihres Höhenprofils als "Berg" ein.

    Nur dann, wenn die Stichwortsuche nichts Spezifischeres gefunden hat
    (also `None` oder das generische "Straße"): ein Name wie
    "... Trail ..." oder "Crosslauf" ist die bessere Auskunft und bleibt
    unangetastet.

    Grund für diese Regel: Die Quellen nennen die Höhenmeter pro Strecke,
    der Name aber oft nicht. Der "VR Bank - BraunenBerg-Lauf" über 14,6 km
    mit ca. 400 Hm galt dadurch als Straßenlauf, obwohl das Profil eindeutig
    ein Berglauf ist - genau die Art Fehler, die im Chat beanstandet wurde
    ("Bei den Höhenmetern muss es ein Traillauf sein oder Berglauf eben").
    """
    if current not in (None, "Straße"):
        return current
    if not laenge_km or laenge_km <= 0:
        return current
    elevation = parse_elevation_m(text)
    if elevation is None:
        return current
    return "Berg" if elevation / laenge_km >= ELEVATION_BERG_M_PER_KM else current


@dataclass
class Competition:
    """Ein einzelner Wettbewerb (eine Strecke) innerhalb einer Veranstaltung."""
    label: str | None = None
    laenge_km: float | None = None
    # Dauer in Stunden, falls der Wettbewerb zeitlich begrenzt ist
    # ("24-Stunden-Lauf", "6h") - siehe parse_duration_h().
    dauer_h: float | None = None
    # Zusätzlicher Text, der die Art der Strecke beschreibt und in die
    # Kategorie (art2) einfließt - z. B. das Feld "Trailrun" aus der
    # laufen.de-Wettbewerbsliste.
    hint: str = ""
    # Der unveränderte Quelltext des Eintrags. Nötig für die Auswertung des
    # Höhenprofils: die Höhenmeter stehen gerade in dem Teil, den
    # clean_competition_label() als Beschreibung wegschneidet.
    raw: str = ""


def parse_competitions(
    items: Iterable[str | tuple[str, str]], config: SiteConfig
) -> list[Competition]:
    """Parst eine Wettbewerbsliste in `Competition`-Objekte.

    Akzeptiert je Eintrag entweder einen String in der Form, in der
    Kalender Wettbewerbe typischerweise ausgeben ("<Bezeichnung> | <X> km",
    nur eine Bezeichnung wie "Halbmarathon" oder nur eine Distanz
    "10 km"), oder ein Tupel `(text, hint)`, wenn die Quelle die Art der
    Strecke separat ausweist.

    Einträge ohne erkennbare Distanz UND ohne Label werden verworfen.
    Gleiche Distanzen werden zusammengefasst: manche Veranstalter listen
    dieselbe Strecke mehrfach (Einzel/Staffel/Nordic Walking) - das sind
    keine eigenen Einträge für unsere Liste.
    """
    result: list[Competition] = []
    # Schlüssel ist das PAAR (Distanz, Dauer): Ein "6h" und ein "12h"
    # derselben Veranstaltung haben beide keine Distanz - über die Distanz
    # allein wäre der zweite ein Duplikat des ersten und fiele weg.
    seen: set[tuple[float | None, float | None]] = set()
    for raw in items:
        if isinstance(raw, tuple):
            raw_text, hint = raw
        else:
            raw_text, hint = raw, ""
        text = re.sub(r"\s+", " ", raw_text or "").strip()
        if not text:
            continue
        km = guess_distance_km(text, config)
        dauer = parse_duration_h(text)
        # Nennt der Wettbewerb eine Dauer, ist eine km-Angabe daneben die
        # RUNDENLÄNGE, nicht die Renndistanz. Beispiel (Mad Chicken Run):
        # "24h Solo auf einer 2km MotoCross-Strecke mit je 60HM (2km)" -
        # gelaufen werden 24 Stunden, die 2 km sind eine Runde davon. Die
        # 2 km als Distanz zu speichern wäre doppelt falsch: in der Spalte
        # stünde "2 km", und die 5-km-Mindestdistanz hätte den Eintrag
        # anschließend ganz verworfen (genau das ist passiert - die vier
        # 24h-Wettbewerbe dieser Veranstaltung fehlten in der Liste).
        if dauer is not None:
            km = None
        label = clean_competition_label(text)
        if km is None and dauer is None and not label:
            continue
        if (km, dauer) in seen:
            continue
        seen.add((km, dauer))
        result.append(Competition(label=label, laenge_km=km, dauer_h=dauer,
                                  hint=(hint or "").strip(), raw=text))
    return result


def expand_competitions(
    base: Event,
    competitions: list[Competition],
    config: SiteConfig,
) -> list[Event]:
    """Vervielfacht ein Event zu je einem Eintrag pro Wettbewerb.

    Die Kategorie (art2) wird pro Wettbewerb neu bestimmt: bei einer
    Veranstaltung mit "Halbmarathon" und "Trailrun" ist die eine Strecke
    Straße, die andere Trail. Der Veranstaltungsname bleibt bewusst
    unverändert - er ist Teil des Duplikat-Schlüssels, und ein pro
    Strecke abgewandelter Name würde bereits gespeicherte Einträge nicht
    mehr als dasselbe Event erkennen. Welche Strecke gemeint ist, steht
    im Feld `wettbewerb`.

    Ohne erkannte Wettbewerbe wird das Basis-Event unverändert
    zurückgegeben (ein Eintrag), damit Aufrufer nie leer ausgehen.
    """
    # Brauchbar ist ein Wettbewerb mit Distanz ODER mit Dauer: ein
    # 24-Stunden-Lauf hat keine feste Strecke, ist aber ein eigener
    # Eintrag der Liste.
    usable = [c for c in competitions
              if c.laenge_km is not None or c.dauer_h is not None]
    if not usable:
        return [base]

    events: list[Event] = []
    for comp in usable:
        clone = replace(base)
        clone.laenge_km = round_km(comp.laenge_km) if comp.laenge_km is not None else None
        clone.dauer_h = comp.dauer_h
        clone.wettbewerb = comp.label
        # art2 aus Veranstaltungsname UND Streckenangaben ableiten: bei
        # einer Veranstaltung mit "Halbmarathon" und "Trailrun" ist die
        # eine Strecke Straße, die andere Trail. Der `hint` trägt dabei
        # das, was die Quelle separat über die Strecke sagt.
        clone.art2 = guess_art2(
            f"{base.name or ''} {comp.label or ''} {comp.hint}", config
        )
        # Höhenprofil als zusätzliches Signal, wenn der Name nichts
        # Spezifischeres sagt (siehe art2_from_elevation()). Bewusst auf dem
        # ROHTEXT der Strecke, nicht dem gekürzten Label: die Höhenmeter
        # stehen gerade in dem Teil, den clean_competition_label() entfernt.
        clone.art2 = art2_from_elevation(
            f"{comp.raw} {comp.hint}", clone.laenge_km, clone.art2
        )
        events.append(clone)
    return events


# --------------------------------------------------------------------------
# Geocoding (Stadt -> lat/lon), mit lokalem Cache (geteilt über alle Scraper)
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
        self._reverse = None

    def _ensure_geolocator(self):
        if self._geolocator is None:
            from geopy.extra.rate_limiter import RateLimiter
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
        except Exception as exc:
            print(f"  ⚠ Geocoding fehlgeschlagen für '{query}': {exc}")
            location = None

        result = (location.latitude, location.longitude) if location else None
        self.cache[query] = list(result) if result else None
        self._save()
        return result

    def _ensure_reverse(self):
        if self._reverse is None:
            from geopy.extra.rate_limiter import RateLimiter
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent=USER_AGENT)
            self._reverse = RateLimiter(
                geolocator.reverse, min_delay_seconds=1.5,
                max_retries=4, error_wait_seconds=5.0,
                swallow_exceptions=False,
            )

    def reverse_land(self, lat: float, lon: float) -> str | None:
        """Bestimmt das Land aus Koordinaten (Reverse-Geocoding).

        Die zuverlässigste Quelle für `land`, wenn die Seite es nicht
        selbst nennt: Aus einer vierstelligen PLZ lassen sich Österreich
        und Schweiz nicht unterscheiden, und Ortsnamen sind mehrdeutig.
        Die Koordinaten haben wir für fast alle Events ohnehin schon.

        Der Cache-Schlüssel ist bewusst auf drei Dezimalstellen (~100 m)
        gerundet: nah beieinander liegende Events teilen denselben
        Eintrag, und die Datei bleibt klein.
        """
        if lat is None or lon is None:
            return None
        key = f"land@{round(lat, 3)},{round(lon, 3)}"
        if key in self.cache:
            cached = self.cache[key]
            return cached if isinstance(cached, str) else None

        land = None
        try:
            self._ensure_reverse()
            location = self._reverse((lat, lon), language="de", zoom=5, timeout=10)
        except Exception as exc:
            print(f"  ⚠ Reverse-Geocoding fehlgeschlagen für {lat},{lon}: {exc}")
            location = None

        if location is not None:
            raw = (location.raw or {}).get("address", {})
            code = (raw.get("country_code") or "").upper()
            land = COUNTRY_CODE_MAP.get(code) or guess_land(raw.get("country") or "")

        self.cache[key] = land
        self._save()
        return land

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# --------------------------------------------------------------------------
# Parsing: JSON-LD (bevorzugt)
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
                    continue
                # Manche Kalenderseiten (z. B. running.life) veröffentlichen
                # ihre Events nicht direkt, sondern verpackt als
                # schema.org-ItemList: {"@type":"ItemList","itemListElement":
                # [{"@type":"ListItem","item":{"@type":"SportsEvent",...}}]}.
                if "ItemList" in types:
                    for list_item in sub.get("itemListElement") or []:
                        if not isinstance(list_item, dict):
                            continue
                        event_item = list_item.get("item")
                        if not isinstance(event_item, dict):
                            continue
                        item_types = event_item.get("@type")
                        item_types = item_types if isinstance(item_types, list) else [item_types]
                        if any(t in ("Event", "SportsEvent") for t in item_types if t):
                            raw_events.append({"_source": "jsonld", "_page_url": page_url, **event_item})
    return raw_events


def normalize_jsonld_event(raw: dict, config: SiteConfig) -> Event:
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
        land = guess_land(f"{standort or ''} {name or ''}") or config.default_land

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
    art2 = guess_art2(combined_text, config)
    laenge_km = guess_distance_km(combined_text, config)
    dauer_h = parse_duration_h(combined_text)

    veranstalter_url = raw.get("url") or raw.get("_page_url")

    return Event(
        land=land, name=name.strip() if name else None,
        standort=standort.strip() if standort else None,
        lat=lat, lon=lon, art1=config.default_art1, art2=art2,
        datum_start=datum_start, datum_ende=datum_ende,
        laenge_km=laenge_km, dauer_h=dauer_h, veranstalter_url=veranstalter_url,
    )


# --------------------------------------------------------------------------
# Parsing: HTML-Fallback (Platzhalter-Selektoren, siehe SiteConfig)
# --------------------------------------------------------------------------

def parse_html_fallback(soup: BeautifulSoup, page_url: str, config: SiteConfig) -> list[Event]:
    events: list[Event] = []
    sel = config.html_fallback_selectors
    cards = soup.select(sel["event_card"])
    for card in cards:
        name_el = card.select_one(sel["name"])
        date_el = card.select_one(sel["date"])
        loc_el = card.select_one(sel["location"])
        link_el = card.select_one(sel["link"])
        cat_el = card.select_one(sel.get("category", "")) if sel.get("category") else None
        dist_el = card.select_one(sel.get("distance", "")) if sel.get("distance") else None

        name = name_el.get_text(strip=True) if name_el else None
        date_text = (
            date_el.get("datetime") if date_el and date_el.has_attr("datetime") else None
        ) or (date_el.get_text(strip=True) if date_el else None)
        standort = loc_el.get_text(strip=True) if loc_el else None
        href = link_el.get("href") if link_el else None
        category_text = cat_el.get_text(strip=True) if cat_el else ""
        distance_text = dist_el.get_text(strip=True) if dist_el else ""

        if not name and not date_text:
            # Kein Name UND kein Datum gefunden -> vermutlich kein echter
            # Event-Eintrag, sondern ein zu breit gefasster event_card-Treffer
            # (z.B. ein verschachteltes Sub-Element). Überspringen, statt
            # leere/kaputte Einträge mitzuzählen.
            continue

        datum_start = parse_flexible_date(date_text or "")
        combined_text = " ".join([name or "", category_text, distance_text])

        events.append(
            Event(
                land=guess_land(f"{standort or ''} {combined_text}") or config.default_land,
                name=name, standort=standort, art1=config.default_art1,
                art2=guess_art2(combined_text, config),
                datum_start=datum_start, datum_ende=datum_start,
                laenge_km=guess_distance_km(combined_text, config),
                dauer_h=parse_duration_h(combined_text),
                veranstalter_url=urljoin(page_url, href) if href else None,
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

def find_next_page_url(soup: BeautifulSoup, current_url: str, config: SiteConfig) -> str | None:
    for selector in config.next_page_selectors:
        link = soup.select_one(selector)
        if link and link.get("href"):
            return urljoin(current_url, link["href"])
    return None


def fetch_page(session: requests.Session, url: str, render_js: bool) -> str | None:
    """Lädt eine Seite (optional JS-gerendert) und gibt das HTML zurück.

    Bei einem Netzwerk-/HTTP-Fehler wird None zurückgegeben statt eine
    Exception zu werfen: die Aufrufer brechen die Pagination dann ab und
    verarbeiten die bereits gefundenen Events weiter.
    """
    try:
        if render_js:
            return fetch_rendered_html(url)
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.RequestException as exc:
        print(f"  ❌ Abbruch: {url} konnte nicht geladen werden ({exc}).")
        return None


def fetch_all_events(
    session: requests.Session, config: SiteConfig, delay: float, max_pages: int, render_js: bool
) -> list[Event]:
    all_events: list[Event] = []
    url = config.calendar_url
    seen_urls: set[str] = set()

    for page_num in range(1, max_pages + 1):
        if not url or url in seen_urls:
            break
        seen_urls.add(url)

        print(f"→ Lade Seite {page_num}: {url}")
        html = fetch_page(session, url, render_js)
        if html is None:
            break

        soup = BeautifulSoup(html, "html.parser")

        raw_jsonld = parse_jsonld_events(soup, url)
        if raw_jsonld:
            print(f"  ✓ {len(raw_jsonld)} Event(s) über JSON-LD gefunden.")
            page_events = [normalize_jsonld_event(r, config) for r in raw_jsonld]
        else:
            page_events = parse_html_fallback(soup, url, config)
            if page_events:
                print(f"  ✓ {len(page_events)} Event(s) über HTML-Fallback gefunden.")
            else:
                print(
                    "  ⚠ Kein JSON-LD und kein HTML-Fallback-Treffer. Falls die "
                    "Seite JavaScript-gerendert ist, versuche --render-js. Sonst "
                    "müssen die HTML-Fallback-Selektoren in diesem Skript an die "
                    "echte Seitenstruktur angepasst werden (siehe TODOs)."
                )

        all_events.extend(page_events)

        next_url = find_next_page_url(soup, url, config)
        url = next_url
        if url:
            time.sleep(delay)

    return all_events


def fetch_events_from_api(session: requests.Session, api_url: str, config: SiteConfig) -> list[Event]:
    """Best-effort-Normalisierung einer unbekannten API-JSON-Struktur (nur
    mit --api-url). Rät anhand gängiger Feldnamen - ggf. anpassen, sobald
    die echte API-Antwortstruktur bekannt ist."""
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

    if isinstance(data, dict):
        for key in ("races", "events", "results", "items", "data"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        items = []

    def first_present(d: dict, keys: list[str]):
        for key in keys:
            node = d
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    node = None
                    break
            if node is not None:
                return node
        return None

    events: list[Event] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = first_present(item, ["name", "title", "eventName", "raceName"])
        date_raw = first_present(item, ["startDate", "date", "eventDate", "start_date"])
        standort = first_present(item, ["city", "location.city", "location", "locationName"])
        country_raw = first_present(item, ["country", "location.country", "countryCode"])
        href = first_present(item, ["url", "link", "slug"])
        category_raw = first_present(item, ["category", "type", "raceType", "distance"])

        land = COUNTRY_CODE_MAP.get(str(country_raw).upper()) if country_raw else None
        if not land:
            land = guess_land(str(country_raw or "")) or guess_land(f"{standort or ''} {name or ''}")

        datum_start = parse_flexible_date(str(date_raw or ""))
        combined_text = " ".join(str(x or "") for x in (name, category_raw))

        veranstalter_url = None
        if href:
            href = str(href)
            veranstalter_url = href if href.startswith("http") else urljoin(api_url, href)

        events.append(
            Event(
                land=land, name=str(name).strip() if name else None,
                standort=str(standort).strip() if standort else None,
                art1=config.default_art1, art2=guess_art2(combined_text, config),
                datum_start=datum_start, datum_ende=datum_start,
                laenge_km=guess_distance_km(combined_text, config),
                dauer_h=parse_duration_h(combined_text),
                veranstalter_url=veranstalter_url,
            )
        )
    print(f"  ✓ {len(events)} Event(s) aus der API-Antwort extrahiert.")
    return events


# --------------------------------------------------------------------------
# events.json laden/speichern, DACH-Filter & Deduplizierung
# --------------------------------------------------------------------------

def load_existing_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Duplikaterkennung über Quellgrenzen hinweg
# --------------------------------------------------------------------------

# Füllwörter, die beim Namensvergleich ignoriert werden: verschiedene
# Quellen schreiben dasselbe Event unterschiedlich ("52. Int.
# Bodensee-Marathon" vs. "Bodensee Marathon").
_NAME_STOPWORDS = {
    "int", "internationaler", "internationale", "internationales",
    "lauf", "laufen", "run", "der", "die", "das", "am", "im", "in",
    "und", "mit", "von", "zum", "zur", "e", "v",
}


def normalize_event_name(name: str | None) -> str:
    """Normalisiert einen Event-Namen für den Duplikat-Vergleich: Kleinschreibung,
    Umlaute/ß aufgelöst, führende Auflagen-Nummer ("52. ") entfernt, Satzzeichen
    weg, Füllwörter und reine Zahlen entfernt."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name.lower()).replace("ß", "ss")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"^\s*\d+\s*\.?\s*", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(t for t in s.split() if t and t not in _NAME_STOPWORDS and not t.isdigit())


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _same_place(a: dict, b: dict) -> bool:
    sa, sb = normalize_event_name(a.get("standort")), normalize_event_name(b.get("standort"))
    if sa and sb and (sa == sb or sa in sb or sb in sa):
        return True
    coords = (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon"))
    if all(isinstance(c, (int, float)) for c in coords):
        # 30 km Toleranz: Quellen nennen oft Nachbarorte/Ortsteile desselben
        # Events (z. B. "Hiddestorf" vs. "Hemmingen", "Humfeld" vs. "Dörentrup").
        return _haversine_km(*coords) <= 30
    return False


def _compatible_distance(a: dict, b: dict) -> bool:
    ka, kb = a.get("laenge_km"), b.get("laenge_km")
    if ka is None or kb is None:
        return True  # unbekannte Distanz schließt ein Duplikat nicht aus
    # Toleranz gegen Quellen-Ungenauigkeiten (42,195 vs. 42,2; 21,0 vs. 21,1),
    # aber weit genug unter echten Distanzunterschieden (5 km vs. 10 km),
    # damit mehrere Distanzen desselben Events erhalten bleiben.
    return abs(ka - kb) <= max(0.5, 0.05 * max(ka, kb))


def _same_name(a: dict, b: dict) -> bool:
    """Entscheidet, ob zwei Event-Namen dieselbe Veranstaltung bezeichnen.

    Verglichen werden WORTMENGEN, nicht Zeichenfolgen. Grund: Quellen
    schreiben dieselbe Veranstaltung mit vertauschter Wortstellung -
    "München Marathon by Brooks" gegen "Marathon München by Brooks". Als
    Zeichenfolge sind das nur 0,69 Ähnlichkeit (unter der Schwelle von
    0,88), als Wortmenge sind sie identisch. Genau daran sind der Münchner
    Marathon und Halbmarathon je doppelt in der Liste gelandet.

    Drei Wege zum Treffer:

    1. **Gleiche Wortmenge** - der Fall oben.
    2. **Teilmenge** (die kürzere Menge steckt komplett in der längeren,
       mindestens zwei Wörter): "München Halbmarathon" gegen "Marathon
       München by Brooks" + Wettbewerb "Halbmarathon". Die zwei Wörter
       Minimum verhindern, dass ein einzelnes Wort wie "marathon" schon
       reicht.
    3. **Ähnlichkeit** der sortierten Wörter >= 0,88 - für Tippfehler und
       Wortvarianten.

    Der Wettbewerbs-Name geht mit in den Vergleich ein, weil er oft genau
    das unterscheidende Wort trägt ("Halbmarathon").

    Die gleiche Veranstalter-DOMAIN ist hier bewusst KEIN Kriterium,
    obwohl sie zunächst naheliegend wirkt. Ausprobiert und verworfen:
    Veranstalter und Regionalkalender führen mehrere Rennen unter einer
    Domain, und die Ortsbedingung erlaubt 30 km Abstand. Dadurch wurden
    "Alfhausener Volkslauf" (Alfhausen) und "MBH Benefizlauf"
    (Ibbenbüren) als dasselbe Event zusammengeführt - zwei verschiedene
    Veranstaltungen am selben Tag, verbunden nur durch das Regionalportal
    laufen-os.de. Ebenso wären ein Trailrun und ein Straßenlauf desselben
    Veranstalters verschmolzen. Für die Münchner Duplikate braucht es die
    Regel ohnehin nicht: die greifen über die Teilmengen-Regel.
    """
    ta = _name_tokens(a)
    tb = _name_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(shorter) >= 2 and shorter <= longer:
        return True
    return difflib.SequenceMatcher(
        None, " ".join(sorted(ta)), " ".join(sorted(tb))
    ).ratio() >= 0.88


def _name_tokens(event: dict) -> frozenset:
    """Wortmenge aus Event-Name UND Wettbewerbs-Bezeichnung."""
    text = f"{event.get('name') or ''} {event.get('wettbewerb') or ''}"
    return frozenset(normalize_event_name(text).split())


def is_same_event(a: dict, b: dict) -> bool:
    """True, wenn zwei Event-Dicts dasselbe real existierende Event beschreiben.
    Nötig, weil dieselbe Veranstaltung von mehreren Quellen unter abweichenden
    Namen geliefert wird ("BMW BERLIN-MARATHON" / "52. BMW Berlin-Marathon" /
    "Berlin Marathon"). Bedingungen: identisches Startdatum UND ähnlicher Name
    UND derselbe Ort (Name oder Koordinaten ≤ 30 km) UND kompatible Distanz.
    Die Orts-Bedingung verhindert Fehltreffer bei generischen Namen
    ("Silvesterlauf" in Salzburg vs. München)."""
    if a.get("datum_start") != b.get("datum_start"):
        return False
    if not _same_place(a, b) or not _compatible_distance(a, b):
        return False
    return _same_name(a, b)


def is_same_race(a: dict, b: dict) -> bool:
    """Wie `is_same_event()`, aber OHNE die Distanz zu vergleichen: True,
    wenn beide Einträge zur selben VERANSTALTUNG gehören - egal, welche
    Strecke sie beschreiben.

    Gebraucht wird das dort, wo die Distanz gerade die fragliche Angabe ist:
    Nennt eine Quelle die Wettbewerbe einzeln (32 km, 14,6 km, 8,2 km) und
    eine andere für dieselbe Veranstaltung nur eine einzige, davon
    abweichende Zahl (35 km), dann ist diese Zahl kein weiterer Wettbewerb,
    sondern eine ungenaue Angabe - siehe
    `clean_events.drop_unspecific_duplicates()`.

    Für die normale Duplikat-Prüfung ist diese Funktion NICHT geeignet:
    dort müssen unterschiedliche Distanzen derselben Veranstaltung
    getrennte Einträge bleiben.
    """
    if a.get("datum_start") != b.get("datum_start"):
        return False
    na, nb = normalize_event_name(a.get("name")), normalize_event_name(b.get("name"))
    if not na or not nb:
        return False
    if na == nb:
        name_match = True
    elif len(na) >= 8 and len(nb) >= 8 and (na in nb or nb in na):
        name_match = True
    else:
        name_match = difflib.SequenceMatcher(None, na, nb).ratio() >= 0.88
    return name_match and _same_place(a, b)


def dedupe_key(
    name: str | None, datum_start: str | None, laenge_km: float | None = None
) -> tuple[str, str, float | None] | None:
    """Eindeutiger Schlüssel für ein Event: Name + Startdatum + (gerundete)
    Distanz. Die Distanz ist bewusst Teil des Schlüssels: viele Veranstalter
    bieten unter demselben Namen am selben Tag mehrere Distanzen an (z. B.
    10-km-Lauf, Halbmarathon UND Marathon) - das sind unterschiedliche
    Events und sollen alle in der Liste erscheinen, nicht als "Duplikat"
    des ersten gefundenen Eintrags verworfen werden. Auf eine Nachkomma-
    stelle gerundet, damit winzige Formatierungsunterschiede zwischen
    Quellen (z. B. 42.2 vs. 42.195) nicht als unterschiedliche Distanzen
    gezählt werden.
    """
    if not name or not datum_start:
        return None
    rounded_km = round(laenge_km, 1) if isinstance(laenge_km, (int, float)) else None
    return (name.strip().casefold(), datum_start, rounded_km)


def filter_dach(events: list[Event], include_all: bool) -> tuple[list[Event], int]:
    if include_all:
        return events, 0
    kept = [e for e in events if e.land is None or e.land in DACH_LAENDER]
    skipped = len(events) - len(kept)
    return kept, skipped


# --------------------------------------------------------------------------
# Manuelle Korrekturen (scripts/manual_overrides.json) & Mindestdistanz
# --------------------------------------------------------------------------

MANUAL_OVERRIDES_PATH = REPO_ROOT / "scripts" / "manual_overrides.json"
# LAUF-Events unter dieser Distanz werden nicht aufgenommen (siehe README):
# viele Firmen-/Kinder-/Bambini-/Hobbyläufe sind für dieses Projekt nicht
# relevant. Zwei bewusste Einschränkungen:
#   - Events OHNE bekannte Distanz sind NICHT betroffen - ohne verlässliche
#     Distanz lässt sich das Kriterium nicht anwenden, und ein pauschaler
#     Ausschluss würde auch echte, längere Events verwerfen.
#   - Die Regel gilt nur für art1 == "Laufen". Bei anderen Sportarten sagt
#     die Kilometerzahl etwas völlig anderes aus: 3,5 km Freiwasser-
#     schwimmen sind eine ernsthafte Distanz, ein 3,5-km-Lauf nicht.
MIN_DISTANCE_KM = 5.0
MIN_DISTANCE_ART1 = "Laufen"

# Nur ein sauberes YYYY-MM-DD gilt als vergleichbares Datum (siehe
# filter_past()); Datumsstrings in ISO-Form lassen sich direkt als Text
# vergleichen.
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_manual_overrides_cache: dict | None = None


def load_manual_overrides() -> dict:
    global _manual_overrides_cache
    if _manual_overrides_cache is None:
        if MANUAL_OVERRIDES_PATH.exists():
            _manual_overrides_cache = json.loads(MANUAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        else:
            _manual_overrides_cache = {}
    return _manual_overrides_cache


def override_keys(name: str | None, datum_start: str | None, laenge_km=None) -> list[str]:
    """Die Schlüssel, unter denen ein Event in manual_overrides.json stehen
    kann - vom spezifischsten zum allgemeinsten:

        "<Name>|<Datum>|<km>"   nur diese eine Strecke
        "<Name>|<Datum>"        alle Strecken dieser Veranstaltung

    Die Variante mit Distanz ist nötig, seit jede Strecke einer
    Veranstaltung ein eigener Eintrag ist: "Stadtlauf Tribsees|2026-09-19"
    würde sonst ALLE vier Strecken treffen, obwohl nur die (falsche)
    42,2-km-Zeile gemeint ist.
    """
    base = f"{(name or '').strip()}|{datum_start}"
    if isinstance(laenge_km, (int, float)):
        return [f"{base}|{round(float(laenge_km), 1):g}", base]
    return [base]


def find_override(overrides: dict, name: str | None, datum_start: str | None,
                  laenge_km=None) -> dict | None:
    """Sucht den passendsten Override-Eintrag (siehe override_keys())."""
    lookup = {k.casefold(): v for k, v in overrides.items() if k != "_readme"}
    for key in override_keys(name, datum_start, laenge_km):
        hit = lookup.get(key.casefold())
        if hit is not None:
            return hit
    return None


def apply_manual_overrides(events: list[Event]) -> tuple[list[Event], int]:
    """Wendet scripts/manual_overrides.json an: Quellen ohne verlässliche
    Distanz-/Link-Angabe (v. a. blv-sport.de) werden dort einzeln, per
    Websuche gegen die offizielle Ausschreibung recherchiert, nachgepflegt
    (siehe Docstring/'_readme' in der JSON-Datei). Events mit
    'exclude': true (z. B. verifizierte Duplikate unter anderem Namen oder
    eine per Websuche widerlegte Distanz) werden entfernt. Gibt (Events,
    Anzahl ausgeschlossen) zurück."""
    overrides = load_manual_overrides()
    if not overrides:
        return events, 0

    result: list[Event] = []
    excluded = 0
    for event in events:
        override = find_override(overrides, event.name, event.datum_start, event.laenge_km)
        if override:
            if override.get("exclude"):
                excluded += 1
                continue
            for field in ("laenge_km", "art2", "art1", "land", "standort", "veranstalter_url"):
                if field not in override:
                    continue
                # Ein Override darf einen direkten Veranstalter-Link NIE
                # durch einen Portallink ersetzen: die älteren Einträge
                # stammen aus der Zeit vor der Regel "immer die offizielle
                # Seite" und enthalten teils einen Portal-Fallback, den die
                # Scraper inzwischen übertreffen.
                if (field == "veranstalter_url"
                        and is_portal_link(override[field])
                        and event.veranstalter_url
                        and not is_portal_link(event.veranstalter_url)):
                    continue
                setattr(event, field, override[field])
        result.append(event)
    return result, excluded


def filter_min_distance(events: list[Event], min_km: float = MIN_DISTANCE_KM) -> tuple[list[Event], int]:
    kept = [
        e for e in events
        if e.laenge_km is None
        or e.art1 != MIN_DISTANCE_ART1
        or e.laenge_km >= min_km
    ]
    skipped = len(events) - len(kept)
    return kept, skipped


def filter_past(events: list[Event], today: str | None = None) -> tuple[list[Event], int]:
    """Verwirft Events, die schon vorbei sind. Die Kalender der Quellen
    führen abgelaufene Termine teils monatelang weiter - ohne diesen
    Filter wandert bei jedem Lauf wieder Vergangenheit in die Liste.

    Maßgeblich ist das ENDE (sonst der Start): ein mehrtägiges Rennen,
    das gestern begonnen hat, läuft noch. Der heutige Tag bleibt drin.
    Ein Event mit unlesbarem Datum wird NICHT verworfen - auf Unsicherheit
    hin zu löschen ist in diesem Projekt die falsche Richtung (siehe
    README "Datenqualität"). `clean_events.drop_past_events()` macht
    dasselbe rückwirkend für die bestehende Datei."""
    heute = today or date.today().isoformat()
    kept = []
    for e in events:
        ende = e.datum_ende or e.datum_start
        if not isinstance(ende, str) or not ISO_DATE_PATTERN.match(ende):
            kept.append(e)
        elif ende >= heute:
            kept.append(e)
    return kept, len(events) - len(kept)


def merge_events(existing: list[dict], new_events: Iterable[Event]) -> tuple[list[dict], int, int]:
    """Fügt neue Events an und überspringt Duplikate. Zwei Stufen:

    1. Schneller exakter Abgleich über `dedupe_key()` (Name + Datum + Distanz).
    2. Zusätzlich `is_same_event()` gegen alle Events desselben Datums - das
       erkennt dasselbe Event auch dann, wenn eine andere Quelle es unter
       abweichendem Namen liefert ("52. Int. Bodensee-Marathon" vs.
       "Bodensee Marathon"). Ohne Stufe 2 landete jede Veranstaltung, die in
       mehreren Kalendern steht, mehrfach in der Liste.

    Fehlende Felder eines bereits vorhandenen Eintrags werden dabei aus dem
    Duplikat ergänzt (z. B. Distanz oder Veranstalter-Link, die nur die eine
    Quelle kennt) - so gewinnt der Datensatz durch jede zusätzliche Quelle,
    ohne doppelte Zeilen zu erzeugen.
    """
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
            # Bewusst nicht nur überspringen, sondern den gespeicherten
            # Eintrag aktualisieren - sonst behalten Altbestände für immer
            # ihren Portallink und fehlende Felder (siehe
            # update_existing_event()).
            update_existing_event(twin, candidate)
            skipped += 1
            continue

        merged.append(candidate)
        by_key[key] = candidate
        by_date.setdefault(event.datum_start, []).append(candidate)
        added += 1

    return merged, added, skipped


# Felder, die bei einem erkannten Duplikat aus dem "Zwilling" ergänzt
# werden, falls sie im behaltenen Eintrag fehlen.
# `wettbewerb` steht hier BEWUSST NICHT: Die Bezeichnung gehört untrennbar
# zu der Distanz, aus der sie geparst wurde. Sie aus einem anderen Eintrag
# zu übernehmen erzeugt Widersprüche - real aufgetreten bei drei Events,
# z. B. Label "0,7 km" an einem 7,5-km-Eintrag und "2,5km
# Kreismeisterschaft" an einem mit 25 km.
ENRICHABLE_FIELDS = (
    "laenge_km", "dauer_h", "art2", "land", "standort", "lat", "lon",
    "datum_ende", "anmeldeschluss", "veranstalter_url",
)

# Kalender-/Anmelde-Portale. Ein Link dorthin ist als Notlösung brauchbar,
# aber `veranstalter_url` soll auf die OFFIZIELLE Seite des Laufs zeigen
# (ausdrücklicher Wunsch aus dem Chat): running.life und laufen.de nennen
# die offizielle Seite auf ihrer Detailseite, also gibt es keinen Grund,
# auf das Portal zu verlinken. Wird ein Event erneut gefunden und ist der
# neue Link ein direkter, ersetzt er einen gespeicherten Portallink
# (siehe update_existing_event()).
PORTAL_DOMAINS = (
    "laufen.de", "running.life", "runnersworld.de", "leichtathletik.de",
    "ahotu.com", "blv-sport.de", "planet-marathon.de", "runningcompany.de",
)


def is_portal_link(url: str | None) -> bool:
    return bool(url) and any(domain in url for domain in PORTAL_DOMAINS)


def update_existing_event(target: dict, source: dict) -> None:
    """Bringt einen bereits gespeicherten Eintrag auf den neuen Stand.

    Drei Dinge, und bewusst nur diese drei:

    1. Fehlende Felder aus `source` ergänzen (siehe ENRICHABLE_FIELDS) -
       ein Eintrag aus einem früheren Lauf kann Felder noch nicht haben,
       die wir inzwischen auslesen (z. B. `land`, `wettbewerb`).
    2. Einen PORTALLINK durch einen direkten Veranstalter-Link ersetzen.
       Früher wurde als `veranstalter_url` der Kalenderlink gespeichert,
       weil die offizielle Seite nur auf der Detailseite der Quelle steht.
       Sobald wir sie kennen, ist sie die bessere Angabe. Das gilt auch
       über Quellgrenzen: laufen.de nennt für viele Events gar keine
       offizielle Seite, running.life aber schon - über die
       Duplikat-Erkennung landet sie dann trotzdem im Eintrag.
    3. Das generische "Straße" durch eine SPEZIFISCHERE Kategorie
       ersetzen. Die Quelle sagt oft pro Strecke, um was für einen Lauf es
       sich handelt ("Trailrun"), der Veranstaltungsname dagegen nicht.
       Ohne diesen Schritt blieb z. B. die 86-km-Strecke der Tiroler
       Silberpfad Trophy als "Straße" stehen, während ihre drei kürzeren
       Strecken - dieselbe Veranstaltung! - korrekt als "Trail" gespeichert
       wurden.

    Ohne diesen Schritt bleiben Altbestände für immer unvollständig bzw.
    falsch: die Scraper hängen sonst nur neue Events an und lassen
    vorhandene unberührt.
    """
    for field_name in ENRICHABLE_FIELDS:
        if target.get(field_name) is None and source.get(field_name) is not None:
            target[field_name] = source[field_name]

    new_url, old_url = source.get("veranstalter_url"), target.get("veranstalter_url")
    if new_url and not is_portal_link(new_url) and is_portal_link(old_url):
        target["veranstalter_url"] = new_url

    new_art2 = source.get("art2")
    if new_art2 and new_art2 != "Straße" and target.get("art2") in (None, "Straße"):
        target["art2"] = new_art2


# --------------------------------------------------------------------------
# Gemeinsame CLI/main()-Logik
# --------------------------------------------------------------------------

def run_scraper_cli(config: SiteConfig, script_name: str | None = None) -> None:
    """Vollständige CLI + Ablauflogik für ein Scraper-Skript, parametrisiert
    über `config`. Jedes site-spezifische Skript ruft nur diese Funktion auf."""
    parser = argparse.ArgumentParser(
        description=f"Liest Lauf-Events von {config.calendar_url} aus und "
                     "ergänzt sie in events.json (keine Duplikate)."
    )
    parser.add_argument("--events-json", type=Path, default=EVENTS_JSON_PATH,
                         help=f"Pfad zur events.json (Standard: {EVENTS_JSON_PATH})")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                         help="Maximale Anzahl an Seiten, die abgerufen werden.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Nur anzeigen, was hinzugefügt würde – events.json NICHT verändern.")
    parser.add_argument("--no-geocoding", action="store_true",
                         help="Kein Nominatim-Geocoding durchführen.")
    parser.add_argument("--render-js", action="store_true",
                         help="Seite per Playwright/Chromium mit JavaScript-Ausführung laden.")
    parser.add_argument("--api-url", type=str, default=None,
                         help="Optional: direkte JSON-API-URL statt die HTML-Seite zu parsen.")
    parser.add_argument("--no-details", action="store_true",
                         help="Detailseiten der Events NICHT abrufen. Schneller, liefert "
                              "dann aber nur die Angaben der Kalenderseite (bei manchen "
                              "Quellen also keine offizielle Veranstalter-Seite und nicht "
                              "alle Strecken).")
    parser.add_argument("--max-details", type=int, default=0,
                         help="Höchstens so viele Detailseiten abrufen (0 = alle). "
                              "Nützlich für Testläufe.")
    if config.dach_only:
        parser.add_argument("--include-all-europe", action="store_true",
                             help="Auch Events außerhalb Deutschland/Österreich/Schweiz übernehmen.")
    args = parser.parse_args()

    # An die Config durchreichen, damit `custom_fetch`-Funktionen sie sehen
    # (siehe SiteConfig.fetch_details).
    config.fetch_details = not args.no_details
    config.max_details = args.max_details

    if config.note:
        print(f"ℹ {config.note}\n")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    if args.api_url:
        if args.api_url.startswith(config.base_url):
            check_robots(session, config.base_url, args.api_url)
        else:
            print(
                f"⚠ --api-url zeigt auf eine andere Domain als {config.base_url} – "
                "bitte deren robots.txt/Nutzungsbedingungen manuell prüfen. "
                "Fahre fort ohne automatischen Check."
            )
        raw_events = fetch_events_from_api(session, args.api_url, config)
    else:
        delay = check_robots(session, config.base_url, config.calendar_url)
        if config.custom_fetch:
            raw_events = config.custom_fetch(session, config, delay, args.max_pages, args.render_js)
        else:
            raw_events = fetch_all_events(session, config, delay, args.max_pages, args.render_js)

    print(f"\nInsgesamt {len(raw_events)} rohe Event-Einträge gefunden.")

    if config.dach_only:
        events_to_use, dach_skipped = filter_dach(raw_events, args.include_all_europe)
        if dach_skipped:
            print(f"  ({dach_skipped} Event(s) außerhalb DACH übersprungen – "
                  f"mit --include-all-europe übernehmen.)")
    else:
        events_to_use = raw_events

    events_to_use, overrides_excluded = apply_manual_overrides(events_to_use)
    if overrides_excluded:
        print(f"  ({overrides_excluded} Event(s) laut scripts/manual_overrides.json "
              f"ausgeschlossen, z. B. verifizierte Duplikate unter anderem Namen.)")

    events_to_use, too_short_skipped = filter_min_distance(events_to_use)
    if too_short_skipped:
        print(f"  ({too_short_skipped} Event(s) unter {MIN_DISTANCE_KM:g} km übersprungen.)")

    events_to_use, past_skipped = filter_past(events_to_use)
    if past_skipped:
        print(f"  ({past_skipped} bereits vergangene(s) Event(s) übersprungen.)")

    if not args.no_geocoding:
        geocoder = Geocoder(GEOCODE_CACHE_PATH)
        for event in events_to_use:
            if event.lat is None and event.lon is None and event.standort:
                coords = geocoder.geocode(event.standort, event.land)
                if coords:
                    event.lat, event.lon = coords

    existing_events = load_existing_events(args.events_json)
    merged, added, skipped = merge_events(existing_events, events_to_use)

    print(f"\n→ {added} neue Event(s) würden hinzugefügt, {skipped} übersprungen "
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
