#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schwimmkalender_scraper.py
==========================

Liest https://www.schwimmkalender.de (Termine für Freiwasserschwimmen,
24-Stunden-Schwimmen, Winterschwimmen und SwimRun) und ergänzt die
Schwimm-Events in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026, vom Nutzer mit dem Link freigegeben)
------------------------------------------------------------------------
robots.txt: `User-agent: *` ohne ein einziges `Disallow` (nur die
Sitemap). Die Datenschutzerklärung nennt die Seite "ein privat,
unkommerziell und privat finanzierter Web-Auftritt zum Zwecke der
Verbreitung von Terminen rund um den Schwimmsport"; ein Verbot des
Auslesens steht nirgends. Impressum, Kontakt und Datenschutz sind
Unterseiten derselben Sitzungsmechanik (siehe unten).

Warum die Seite früher als "sperrt den Abruf" galt
--------------------------------------------------
Die Seite ist eine PHP-Anwendung, bei der JEDE Antwort eine neue
Sitzungsnummer (`id`, 41 Ziffern) trägt und die Sitzung an die
**IP-Adresse des Aufrufers** gebunden ist (ein Aufruf mit fremder id
landet auf `../user/index.php?d=0&r=<IP>`). Aus einer Sandbox, deren
Ausgangs-IP je Verbindung wechselt, sieht das wie eine Sperre aus: Die
Startseite kommt, jeder Klick darauf liefert wieder die Startseite. Über
EINE wiederverwendete Verbindung (`requests.Session`, Keep-Alive) und
GET-Aufrufe funktioniert es; in GitHub Actions ist die IP ohnehin je
Job fest. POST-Formulare verlieren die Sitzung auch dann, deshalb nur
GET - die Menü-Links der Seite selbst sind GET-Aufrufe derselben Form.

Struktur (am 24.09.2026 kalibriert)
-----------------------------------
* Startseite `/` → Weiterleitung auf `sk_kalender/views/start.php?d=0&id=…`;
  im HTML steht `<input name='id' value='…'>`.
* Kategorie-Liste: `sk_kalender/main/main.php?d=0&Action=views/start.php
  &fOK=userevents|K|K|K|K&id=…` mit K = 63 Freiwasser, 67 24h Freiluft,
  64 24h Halle, 69 SwimRun, 71 Winterschwimmen (118 = alle). Die
  Antwort ist eine Tabelle `<tr><td>03.10.2026</td><td><a href='…fOK=
  update|userevents|7055…' class='kat63'>Hafenschwimmen, Wilhelmshaven
  (3k)</a></td><td>Niedersachsen</td></tr>`. Die Seite listet nur
  KÜNFTIGE Termine (die Saison 2027 wird erst im Frühjahr eingetragen -
  im September 2026 standen zwei Freiwasser-Termine drin).
* Detailseite: `…&Action=views/lstuserevents.php&fOK=update|userevents|<nr>
  &id=…` mit den Feldern `#iKategorieNr`, `#iBezeichnung`, `#iDatum`,
  `#iEndDatum` ("-" = eintägig), `#iLandNr` (Bundesland oder Staat) und
  unter "Links" die Seite des Veranstalters - die `veranstalter_url`
  (Datenregel 2). Es gibt keinen Ort und keine Koordinaten.

Was daraus wird
---------------
* Die DISTANZ steht in der Bezeichnung in Klammern: "(3k)", "(1k)",
  "(3,8k)", "(2k/5k)" - je Zahl ein Eintrag (Datenregel 1). "24h"/"25h"
  am Anfang ist ein Zeitrennen (`dauer_h`, Datenregel 8).
* Der ORT kommt aus der Bezeichnung: hinter dem letzten Komma
  ("Hafenschwimmen, Wilhelmshaven"), hinter der Stundenzahl ("24h
  Friedberg"), sonst das letzte Wort samt Vorsilbe ("Waging am See",
  "Schwarzenbach a. Wald"). Endet der Name auf ein Schwimmwort
  ("Berliner Spreeschwimmen"), gilt bei den Stadtstaaten das Land als
  Ort, sonst wird der Eintrag ÜBERSPRUNGEN - ein geratener Ort wäre
  schlechter als kein Eintrag (dieselbe Linie wie bei lauftermine.ch).
* Das LAND: ein deutsches Bundesland → Deutschland; Österreich, Schweiz,
  Italien wie genannt (Italien wird erst über die Koordinaten zu
  "Italien (Südtirol)" oder fällt heraus, Datenregel 4); alles andere
  (Dänemark, Kroatien, …) sortiert `filter_dach()` aus.
* SPORTART: Schwimmen, die SwimRun-Kategorie ist Triathlon/Swimrun
  (Datenregel 11: die Mehrsport-Schublade). KATEGORIE: Freiwasser und
  Winter → "Freiwasser", 24h Halle → "Becken", 24h Freiluft ohne
  Voreinstellung (Freibad oder See - die Seite sagt es nicht).
* Danach dieselben Regeln wie überall: 500-m-Mindestdistanz und
  Meisterschafts-Ausschluss fürs Schwimmen (24.09.2026), Dedupe.

Nutzung: `python3 scripts/schwimmkalender_scraper.py --help`
(Testlauf: `--dry-run --max-details 3`).
"""

from pathlib import Path
import html as html_mod
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    GEOCODE_CACHE_PATH,
    Event,
    Geocoder,
    SiteConfig,
    fetch_page,
    guess_art1,
    guess_art2,
    is_portal_link,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.schwimmkalender.de"
MAIN_URL = f"{BASE_URL}/sk_kalender/main/main.php"

# Kategorie-Nummer → (Anzeigename, art1, art2-Voreinstellung)
KATEGORIEN: dict[int, tuple[str, str, str | None]] = {
    63: ("Freiwasser", "Schwimmen", "Freiwasser"),
    67: ("24h Freiluft", "Schwimmen", None),
    64: ("24h Halle", "Schwimmen", "Becken"),
    69: ("SwimRun", "Triathlon", "Swimrun"),
    71: ("Winterschwimmen", "Schwimmen", "Freiwasser"),
}

BUNDESLAENDER = {
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg",
    "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen",
    "Rheinland-Pfalz", "Rheinland Pfalz", "Saarland", "Sachsen", "Sachsen-Anhalt",
    "Schleswig-Holstein", "Thüringen",
}
STADTSTAATEN = {"Berlin", "Hamburg", "Bremen"}

_ID_RE = re.compile(r"name='id'\s+value='(\d{20,})'")
_ZEILE_RE = re.compile(
    r"<tr>\s*<td[^>]*>\s*(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td[^>]*>\s*"
    r"<a href='[^']*fOK=update\|userevents\|(\d+)[^']*'\s+class='kat(\d+)'[^>]*>(.*?)</a>"
    r"\s*</td>\s*<td[^>]*>(.*?)</td>", re.S)
_KLAMMER_RE = re.compile(r"\(([^()]*)\)")
_KM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*k(?:m)?\b", re.I)
_METER_RE = re.compile(r"(\d{3,5})\s*m\b", re.I)
_DAUER_RE = re.compile(r"^\s*(\d{1,3})\s*h\b", re.I)
# Die Dauer steht vorn ("24h Friedberg") oder in einer Klammer ("Rotary
# Charity-Schwimmen (24h Freising)").
_DAUER_IRGENDWO_RE = re.compile(r"(?:^|\()\s*(\d{1,3})\s*h\b", re.I)
# Endet der Name darauf, ist das letzte Wort kein Ort.
_KEIN_ORT = re.compile(
    r"(schwimm\w*|swim\w*|challenge|cup|crossing|querung|meile|marathon|"
    r"race|open|water|serie|festival|\d+)$", re.I)
# Zwei Sorten Vorsilben: Ein PRÄFIX gehört zum Ortsnamen ("Bad Tölz",
# "St. Gallen"), ein BINDEWORT steht ZWISCHEN zwei Teilen des Ortsnamens
# ("Waging am See", "Schwarzenbach a. Wald", "Frankfurt an der Oder") -
# dann gehört auch das Wort davor dazu.
_PRAEFIX = {"bad", "st.", "st", "sankt", "neu", "groß", "klein", "ober", "unter"}
_BINDEWORT = {"am", "an", "im", "bei", "a.", "a", "ob", "auf", "der", "dem", "zum", "zur", "in"}


def sitzungs_id(html: str) -> str | None:
    """Die Sitzungsnummer aus einer Antwortseite - jede Antwort trägt eine."""
    m = _ID_RE.search(html or "")
    return m.group(1) if m else None


def kategorie_url(nr: int, sid: str) -> str:
    return f"{MAIN_URL}?d=0&Action=views/start.php&fOK=userevents|{nr}|{nr}|{nr}|{nr}&id={sid}"


def detail_url(nr: int, sid: str) -> str:
    return f"{MAIN_URL}?d=0&Action=views/lstuserevents.php&fOK=update|userevents|{nr}&id={sid}"


def parse_liste(html: str) -> list[dict]:
    """Die Zeilen einer Kategorie-Liste: Datum, Detailnummer, Kategorie,
    Bezeichnung, Land. Leer, wenn die Antwort keine Liste ist (dann hat
    die Sitzung nicht gehalten - siehe Modul-Doku)."""
    zeilen = []
    for datum, nr, kat, name, land in _ZEILE_RE.findall(html or ""):
        zeilen.append({
            "datum": datum,
            "nr": int(nr),
            "kategorie": int(kat),
            "name": html_mod.unescape(re.sub(r"<[^>]+>", "", name)).strip(),
            "land": html_mod.unescape(re.sub(r"<[^>]+>", "", land)).strip(),
        })
    return zeilen


def ist_liste(html: str) -> bool:
    """Hat die Antwort die Kategorie-Liste (auch eine leere) gebracht?"""
    return bool(re.search(r"Eintr(?:ag|äge) gefunden", html or ""))


def parse_detail(html: str) -> dict:
    """Die Felder der Detailseite."""
    soup = BeautifulSoup(html or "", "html.parser")

    def feld(id_: str) -> str | None:
        el = soup.find(id=id_)
        if not el:
            return None
        text = el.get_text(" ", strip=True)
        return text or None

    links: list[str] = []
    box = soup.find(id="textarea")
    if box:
        for a in box.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and href not in links:
                links.append(href)
    ende = feld("iEndDatum")
    return {
        "kategorie": feld("iKategorieNr"),
        "name": feld("iBezeichnung"),
        "datum_start": parse_flexible_date(feld("iDatum") or ""),
        "datum_ende": parse_flexible_date(ende) if ende and ende != "-" else None,
        "land": feld("iLandNr"),
        "links": links,
        "infos": feld("simpletextarea"),
    }


def distanzen_aus_name(name: str) -> list[float]:
    """Die Distanzen aus den Klammern der Bezeichnung: "(3k)" → [3.0],
    "(2k/5k)" → [2.0, 5.0], "(750m)" → [0.75]. Nur in Klammern - eine
    Zahl im Namen selbst ("100 x 100 Hamburg") ist keine Distanz."""
    km: list[float] = []
    for inhalt in _KLAMMER_RE.findall(name or ""):
        for zahl in _KM_RE.findall(inhalt):
            wert = float(zahl.replace(",", "."))
            if wert not in km:
                km.append(wert)
        if not _KM_RE.search(inhalt):
            for zahl in _METER_RE.findall(inhalt):
                wert = int(zahl) / 1000
                if wert not in km:
                    km.append(wert)
    return km


def dauer_aus_name(name: str) -> float | None:
    """"24h Friedberg" → 24.0, "25h Handorf" → 25.0, "… (24h Freising)"
    → 24.0, sonst None."""
    m = _DAUER_IRGENDWO_RE.search(name or "")
    return float(m.group(1)) if m else None


def name_ohne_zusatz(name: str) -> str:
    """Die Bezeichnung ohne die Distanz-Klammer und ohne das Komma vor
    dem Ort: "Hafenschwimmen, Wilhelmshaven (3k)" → "Hafenschwimmen
    Wilhelmshaven". Eine Klammer OHNE Distanz bleibt ("(24h Freising)")."""
    text = name or ""

    def ersetze(m: re.Match) -> str:
        return "" if _KM_RE.search(m.group(1)) or _METER_RE.search(m.group(1)) else m.group(0)

    text = _KLAMMER_RE.sub(ersetze, text)
    text = re.sub(r"\s*,\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -")


def ort_aus_name(name: str, land: str | None = None) -> str | None:
    """Der Ort aus der Bezeichnung (siehe Modul-Doku). None, wenn er
    sich nicht ablesen lässt."""
    text = _KLAMMER_RE.sub("", name or "")
    text = re.sub(r"\s+", " ", text).strip(" -,")
    if not text:
        return None
    if "," in text:
        kandidat = text.rsplit(",", 1)[1].strip()
    elif _DAUER_RE.match(text):
        kandidat = _DAUER_RE.sub("", text, count=1).strip()
    else:
        kandidat = _letzter_ort(text)
    if not kandidat:
        # "Rotary Charity-Schwimmen (24h Freising)": der Ort steht in
        # einer Klammer ohne Distanz, hinter der Dauer.
        for inhalt in _KLAMMER_RE.findall(name or ""):
            if _KM_RE.search(inhalt) or _METER_RE.search(inhalt):
                continue
            kandidat = _letzter_ort(_DAUER_RE.sub("", inhalt, count=1).strip())
            if kandidat:
                break
    kandidat = (kandidat or "").strip(" -,")
    if kandidat and not _KEIN_ORT.search(kandidat.split(" ")[-1]):
        return kandidat
    if land in STADTSTAATEN:
        return land
    return None


def _letzter_ort(text: str) -> str:
    """Das letzte Wort samt Vorsilben - oder "", wenn es ein Schwimmwort
    ist ("Berliner Spreeschwimmen")."""
    tokens = [t for t in text.split(" ") if t]
    if not tokens:
        return ""
    i = len(tokens) - 1
    # "Waging am See", "Frankfurt an der Oder": Bindewörter sammeln,
    # dann das Wort davor dazu.
    j = i
    while j > 0 and tokens[j - 1].lower() in _BINDEWORT:
        j -= 1
    if j < i and j > 0:
        i = j - 1
    # "Bad Tölz", "St. Gallen"
    while i > 0 and tokens[i - 1].lower() in _PRAEFIX:
        i -= 1
    kandidat = " ".join(tokens[i:])
    if _KEIN_ORT.search(kandidat.split(" ")[-1]):
        return ""
    return kandidat


def land_aus_feld(land: str | None) -> str | None:
    if not land:
        return None
    land = land.strip()
    if land in BUNDESLAENDER:
        return "Deutschland"
    return land


def build_events(detail: dict, kategorie_nr: int | None, config: SiteConfig) -> list[Event]:
    """Aus einer Detailseite die Event-Zeilen (eine je Distanz)."""
    name_roh = detail.get("name") or ""
    if not name_roh or not detail.get("datum_start"):
        return []
    kat = KATEGORIEN.get(kategorie_nr or 0)
    art1 = guess_art1(name_roh, config)
    if kat and kat[1] != "Schwimmen":
        # SwimRun: Sportart UND Kategorie kommen aus der Kategorie der
        # Seite - die Triathlon-Voreinstellung ("Straße") passt nicht.
        art1, art2 = kat[1], kat[2]
    else:
        art2 = guess_art2(name_roh, config, art1)
        if art2 is None and kat:
            art2 = kat[2]
    land = land_aus_feld(detail.get("land"))
    ort = ort_aus_name(name_roh, detail.get("land"))
    if not ort:
        return []
    url = next((u for u in detail.get("links", []) if not is_portal_link(u)
                and not re.search(r"facebook|instagram|youtube", u, re.I)), None)
    name = name_ohne_zusatz(name_roh)
    dauer = dauer_aus_name(name_roh)
    distanzen = [] if dauer is not None else distanzen_aus_name(name_roh)
    basis = dict(
        land=land, name=name, standort=ort, art1=art1, art2=art2,
        datum_start=detail.get("datum_start"), datum_ende=detail.get("datum_ende"),
        dauer_h=dauer, veranstalter_url=url,
    )
    if not distanzen:
        return [Event(**basis)]
    events = []
    for km in distanzen:
        label = f"{km:g} km".replace(".", ",") if len(distanzen) > 1 else None
        events.append(Event(**basis, laenge_km=km, wettbewerb=label))
    return events


def fetch_schwimmkalender_events(session, config, delay, max_pages, render_js) -> list[Event]:
    """Startseite → Sitzungsnummer → je Kategorie die Liste → je Termin die
    Detailseite. Alles über dieselbe `session` (Keep-Alive), siehe
    Modul-Doku zur IP-Bindung."""
    html = fetch_page(session, BASE_URL + "/", render_js)
    sid = sitzungs_id(html or "")
    if not sid:
        print("  ❌ Keine Sitzungsnummer auf der Startseite - Struktur geändert?")
        return []
    zeilen: list[dict] = []
    gesehen: set[int] = set()
    for nr in KATEGORIEN:
        time.sleep(delay)
        seite = fetch_page(session, kategorie_url(nr, sid), render_js)
        if seite and not ist_liste(seite):
            # Sitzung verloren (neue IP?) - einmal neu beginnen.
            print(f"  ⚠ Kategorie {nr}: Sitzung nicht gehalten, neuer Anlauf.")
            time.sleep(delay)
            html = fetch_page(session, BASE_URL + "/", render_js)
            sid = sitzungs_id(html or "") or sid
            time.sleep(delay)
            seite = fetch_page(session, kategorie_url(nr, sid), render_js)
        if not seite:
            continue
        neu = [z for z in parse_liste(seite) if z["nr"] not in gesehen]
        for z in neu:
            gesehen.add(z["nr"])
        print(f"→ {KATEGORIEN[nr][0]}: {len(neu)} Termin(e)")
        zeilen.extend(neu)
        sid = sitzungs_id(seite) or sid

    events: list[Event] = []
    details_geladen = details_fehlgeschlagen = 0
    geocoder: Geocoder | None = None
    for i, z in enumerate(zeilen, 1):
        if not config.fetch_details or (config.max_details and i > config.max_details):
            # Ohne Detailseite: nur, was die Liste hergibt (kein Link,
            # kein Enddatum).
            detail = {"name": z["name"], "datum_start": parse_flexible_date(z["datum"]),
                      "datum_ende": None, "land": z["land"], "links": []}
        else:
            time.sleep(delay)
            seite = fetch_page(session, detail_url(z["nr"], sid), render_js)
            detail = parse_detail(seite or "")
            if not detail.get("name"):
                # Sitzung verloren - einmal neu beginnen, sonst die Listenzeile.
                time.sleep(delay)
                html = fetch_page(session, BASE_URL + "/", render_js)
                sid = sitzungs_id(html or "") or sid
                time.sleep(delay)
                seite = fetch_page(session, detail_url(z["nr"], sid), render_js)
                detail = parse_detail(seite or "")
            if not detail.get("name"):
                details_fehlgeschlagen += 1
                print(f"  ⚠ Detailseite {z['nr']} ohne Inhalt - nehme die Listenzeile.")
                detail = {"name": z["name"], "datum_start": parse_flexible_date(z["datum"]),
                          "datum_ende": None, "land": z["land"], "links": []}
            else:
                details_geladen += 1
                sid = sitzungs_id(seite or "") or sid
        for e in build_events(detail, z["kategorie"], config):
            # Das Bundesland macht den Ort eindeutig: "Freiberg" liegt in
            # Sachsen UND in Baden-Württemberg, "Handorf" in Niedersachsen
            # UND in Nordrhein-Westfalen; Nominatim nähme ohne den Zusatz
            # den bekannteren. Deshalb hier geocodieren, mit Bundesland -
            # run_scraper_cli() lässt Zeilen mit Koordinaten in Ruhe.
            bundesland = (detail.get("land") or "").strip()
            if config.geocoding and e.land == "Deutschland" and bundesland in BUNDESLAENDER:
                if geocoder is None:
                    geocoder = Geocoder(GEOCODE_CACHE_PATH)
                coords = geocoder.geocode(f"{e.standort}, {bundesland}", "Deutschland")
                if coords:
                    e.lat, e.lon = coords
            events.append(e)
    mit_link = sum(1 for e in events if e.veranstalter_url)
    print(f"→ Detailseiten: {details_geladen} geladen, {details_fehlgeschlagen} fehlgeschlagen; "
          f"{mit_link} von {len(events)} Einträgen mit Veranstalterseite.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=BASE_URL + "/",
    default_art1="Schwimmen",
    custom_fetch=fetch_schwimmkalender_events,
    note="schwimmkalender.de bindet die Sitzung an die IP-Adresse - alle Abrufe "
         "laufen über eine Verbindung (siehe Modul-Doku).",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
