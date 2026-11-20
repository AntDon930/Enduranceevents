#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dealgrid_scraper.py
===================

Liest den **Gravel-Kalender von DealGrid**
(https://dealgrid.de/gravel-events-deutschland-2026/) - Gravel-Rennen,
-Touren, Bikepacking und Ultracycling in Deutschland, Österreich und der
Schweiz - und ergänzt sie in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 08.10.2026, vom Nutzer freigegeben: „Ja für dealgrid")
------------------------------------------------------------------------------
robots.txt (Yoast) sperrt nichts (`User-agent: * / Disallow:`), kein
`ai.txt`, kein `tdmrep.json`, kein `noindex`. Impressum (Beerchen
Fotografie, Waghäusel) und Datenschutz tragen keinen Vorbehalt gegen
automatisches Auslesen. Die Seite verdient an Partnerlinks (Amazon) -
übernommen wird deshalb nur, was zum Termin gehört, und als Link immer
die VERANSTALTERSEITE, die der Kalender je Termin nennt (Datenregel 2),
nie dealgrid.de selbst.

Struktur (am 08.10.2026 kalibriert)
-----------------------------------
EINE Seite. Ein JSON-LD-Block `@graph` mit je Termin einem `SportsEvent`
(Name, startDate/endDate, `location.address` mit Ort, Bundesland und
Ländercode, `geo`, `url` = Veranstalterseite, `eventStatus`). Daneben je
Termin eine Listenzeile `li.dgkal-row`, deren `.dgkal-meta` die Strecken
nennt („Waltrop, Nordrhein-Westfalen · 43 · 67 · 101 km · 8 · 10 €") und
deren `.dgkal-kicker-s` die Art („Rennen", „Tour", „Bikepacking",
„Camp", „Serie", „Straße · Ultracycling"). Am 08.10.2026: 80 Termine.

Was daraus wird
---------------
* Fahrrad, je Distanz eine Zeile (Datenregel 1). Die Zahlen der
  Meta-Zeile werden gelesen, wie sie dastehen: „43 · 67 · 101 km" sind
  drei Strecken, „8 · 10 €" sind Preise, „10 × 5,8 km" ist ein Rennen
  über 58 km. **Nicht geraten**: Spannen („20 bis 100 km", „100–120 km",
  „bis 155 km" - die Route ist frei oder variabel), Rundenlängen („17,7-km-
  Runde"), Kinderstrecken, Vorjahreswerte („Strecken 2027 folgen (2026:
  …)", „(Stand 2026)"). Bleibt keine Zahl, eine Zeile ohne Länge.
* Kategorie: Was das Label nennt (CTF → Mountainbike), sonst „Straße" bei
  Ultracycling auf Asphalt, sonst Gravel.
* **Raus**: Camps und ganzjährige Serien (kein Termin, an dem man
  startet), abgesagte Termine, Länder außerhalb der vier Regionen
  (Elsass), und Orte, die `places.json` nicht kennt („Harz",
  „Pfälzerwald", „Rundkurs mit Basecamp", „deutschlandweit") - eine
  Gegend ist kein Ort, und die Arber-Lehre (Siebzehnter Durchgang: Start
  in Regensburg, nicht im Bayerischen Wald) sagt, warum hier nicht
  geraten wird.
* Ort: der Ort aus `addressLocality`, gegen `places.json` geprüft (erst
  der ganze Name, dann der Teil vor dem Bindestrich: „Stuttgart-Wangen" →
  Stuttgart). Koordinaten aus dem JSON-LD, wenn sie höchstens 30 km vom
  Ort entfernt liegen - sonst die des Ortes (Lektion 3: Koordinaten sind
  Daten).
* Name: „CANYON Rhein Hunsrück Bike Marathon, Gravel" heißt wie die
  Veranstaltung (ohne „, Gravel"), damit er auf die vorhandenen Zeilen
  trifft; die Gattung steht im Label.

Nutzung: `python3 scripts/dealgrid_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import html as htmlmod
import json
import math
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    SUEDTIROL,
    Event,
    SiteConfig,
    fetch_page,
    in_suedtirol,
    orte_aus_places,
    run_scraper_cli,
)

BASE_URL = "https://dealgrid.de"
KALENDER_URL = BASE_URL + "/gravel-events-deutschland-2026/"

LAND = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
# Kein Termin, an dem man startet.
KICKER_RAUS = re.compile(r"\b(?:camp|serie)\b", re.I)
_NAME_GRAVEL_ZUSATZ = re.compile(r",\s*(gravel(?:-?\s*\w+)?)\s*$", re.I)

_ZAHL = re.compile(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+(?:,\d+)?")
_SPANNE = re.compile(r"\d\s*(?:–|-|bis)\s*\d|(?:^|\s)bis\s+\d", re.I)
_RUNDEN_MAL = re.compile(r"(\d+)\s*(?:×|x|runden\s+(?:à|a|je|zu))\s*(\d+(?:,\d+)?)\s*km", re.I)
_NUR_ZAHL = re.compile(r"(?:ca\.\s*)?\d[\d.,]*")
_NICHT_DISTANZ = re.compile(r"€|startgeld|\bhm\b|\d\s*h\b|%|\bstart\s+\d|\bkids?\b|kinder|\bfolg|stand\s+20\d\d|"
                            r"20\d\d\s*:|k\.\s*a\.|frei\s+wählbar|runde\b|-runde|\brunden\b", re.I)
# Nur diese Wörter kommen ins Label - „self-supported", „ca." oder
# „Schotterrunden" sagen nichts über den Wettbewerb.
_LABEL_WORT = re.compile(r"\b(?:gravel(?:-tour|-rennen|-strecke)?|race|ride|ctf|rtf|mtb|rennen|tour)\b", re.I)


def _zahl(text: str) -> float:
    return float(text.replace(".", "").replace(",", ".")) if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text) \
        else float(text.replace(",", "."))


def _km(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def strecken_aus_meta(meta: str) -> list[tuple[float, str]]:
    """(km, Label) je Strecke aus der Meta-Zeile; der erste Abschnitt ist
    der Ort. Zahlen ohne Einheit („43 · 67 · 101 km") gelten erst, wenn
    der nächste Abschnitt sie als km ausweist - „8 · 10 €" sind Preise."""
    meta = htmlmod.unescape(meta or "")
    # Eine Klammer mit Jahreszahl nennt die Strecken des VORJAHRS
    # („Strecken 2027 folgen (2026: 40 · 96 · 126 km)", „56 · 94 km (Stand
    # 2026)") - dann lieber keine Zahl. Andere Klammern („(ca. 41 km)",
    # „(RTF-Kalender)") sind Zusätze und fallen weg.
    if re.search(r"\([^)]*\b20\d\d\b[^)]*\)", meta):
        return []
    meta = re.sub(r"\([^)]*\)", "", meta)
    teile = [t.strip() for t in meta.split(" · ")[1:]]
    ergebnis: list[tuple[float, str]] = []
    offen: list[float] = []

    def nimm(werte: list[float], label_wort: str) -> None:
        for km in werte:
            if km >= 1 and km not in {k for k, _ in ergebnis}:
                ergebnis.append((km, f"{label_wort} {_km(km)} km".strip()))

    for teil in teile:
        m = _RUNDEN_MAL.search(teil)
        if m:
            km = round(int(m.group(1)) * _zahl(m.group(2)), 1)
            ergebnis.append((km, f"{_km(km)} km ({m.group(0)})"))
            offen = []
            continue
        if _NICHT_DISTANZ.search(teil):
            offen = []
            continue
        if _SPANNE.search(teil):
            # „65 · 100–120 km": die 65 davor sind km, die Spanne nicht.
            if re.search(r"\bkm\b", teil):
                nimm(offen, "")
            offen = []
            continue
        wort = " ".join(m.group(0) for m in _LABEL_WORT.finditer(teil))
        zahlen = [_zahl(z) for z in _ZAHL.findall(teil)]
        if re.search(r"\bkm\b", teil):
            nimm(offen + zahlen, wort)
            offen = []
        elif zahlen and _NUR_ZAHL.fullmatch(re.sub(r"^[A-Za-zÄÖÜäöü-]+\s+", "", teil)):
            offen += zahlen
        else:
            offen = []
    return ergebnis


def parse_kalender(html: str) -> list[dict]:
    """Je Termin ein dict aus JSON-LD plus Listenzeile (Art, Meta, Status)."""
    soup = BeautifulSoup(html, "html.parser")
    ld: list[dict] = []
    for skript in soup.find_all("script", type="application/ld+json"):
        try:
            daten = json.loads(skript.string or "")
        except (ValueError, TypeError):
            continue
        for x in daten.get("@graph", []) if isinstance(daten, dict) else []:
            if x.get("@type") == "SportsEvent":
                ld.append(x)
    zeilen: dict[str, list[dict]] = {}
    for li in soup.select("li.dgkal-row"):
        a = li.select_one("a.dgkal-name")
        if not a:
            continue
        txt = lambda sel: (li.select_one(sel).get_text(" ", strip=True) if li.select_one(sel) else "")  # noqa: E731
        zeilen.setdefault(a.get_text(" ", strip=True), []).append(
            {"art": txt(".dgkal-kicker-s"), "meta": txt(".dgkal-meta"), "status": txt(".dgkal-pill")})
    termine = []
    for x in ld:
        name = htmlmod.unescape(x.get("name") or "").strip()
        zeile = (zeilen.get(name) or [{}]).pop(0) if zeilen.get(name) else {}
        loc = x.get("location") or {}
        adr = loc.get("address") or {}
        geo = loc.get("geo") or {}
        termine.append({
            "name": name, "datum_start": x.get("startDate"), "datum_ende": x.get("endDate") or x.get("startDate"),
            "ort": htmlmod.unescape(adr.get("addressLocality") or "").strip(),
            "land_code": adr.get("addressCountry"),
            "lat": geo.get("latitude"), "lon": geo.get("longitude"),
            "url": htmlmod.unescape(x.get("url") or "") or None,
            "status": x.get("eventStatus") or "", **zeile,
        })
    return termine


def _abstand_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _kompakt(name: str) -> str:
    """Vergleichsform eines Ortsnamens: klein, „St." = „Sankt", ohne
    Leerzeichen und Bindestriche („Velden am Wörthersee" = „Velden am
    Wörther See")."""
    name = re.sub(r"\bst\.\s*", "sankt ", name.lower())
    return re.sub(r"[\s-]+", "", name)


def standort_finden(ort: str, lat, lon, orte: dict) -> tuple[str, float, float] | None:
    """(Ort, lat, lon) - der Ort muss in places.json stehen. Geprüft wird
    der ganze Name, dann der Teil vor dem Bindestrich („Stuttgart-Wangen"),
    und - nur mit Koordinaten der Quelle, höchstens 15 km entfernt - ein
    längerer oder kürzerer Name desselben Ortes („Freiburg" = „Freiburg im
    Breisgau", „Bockenheim an der Weinstraße" = „Bockenheim"). Eine
    Gegend („Harz", „Bayerischer Wald") ist kein Ort; ein mehrdeutiger
    Name zählt nur, wenn die Koordinaten der Quelle einen Treffer
    bestätigen."""
    ort = re.sub(r"\(.*?\)", "", ort or "").strip()
    ort = re.sub(r"^(?:start|ostseebad|nordseebad)\s+", "", ort, flags=re.I).strip()
    if not ort:
        return None
    quelle = (float(lat), float(lon)) if lat is not None and lon is not None else None
    for name in (ort, ort.split("-")[0].strip()):
        kandidaten = orte.get(name.lower(), [])
        if not kandidaten:
            continue
        if quelle:
            nah = sorted((k for k in kandidaten if _abstand_km(quelle, (k[1], k[2])) <= 30),
                         key=lambda k: _abstand_km(quelle, (k[1], k[2])))
            if nah:
                return nah[0][0], quelle[0], quelle[1]
            continue
        if len(kandidaten) == 1:
            return kandidaten[0]
    if not quelle:
        return None
    k_ort = _kompakt(ort)
    beste = None
    for liste in orte.values():
        for k in liste:
            k_name = _kompakt(k[0])
            if len(k_name) < 4 or not (k_ort.startswith(k_name) or k_name.startswith(k_ort)):
                continue
            d = _abstand_km(quelle, (k[1], k[2]))
            if d <= 15 and (beste is None or d < beste[0]):
                beste = (d, k)
    if not beste:
        return None
    # Der längere Name ist der genauere („Bockenheim an der Weinstraße",
    # „Freiburg im Breisgau", „Nürburgring").
    name = ort if len(ort) >= len(beste[1][0]) else beste[1][0]
    return name, quelle[0], quelle[1]


def events_aus_termin(t: dict, orte_je_land: dict | None = None) -> tuple[list[Event], str | None]:
    if not t.get("name") or not t.get("datum_start"):
        return [], "ohne Name oder Datum"
    if re.search(r"Cancelled|Postponed", t.get("status") or "") or re.search(r"abgesagt", t.get("status_text", "") + (t.get("status") or ""), re.I):
        return [], "abgesagt"
    if KICKER_RAUS.search(t.get("art") or ""):
        return [], f"kein Renntermin ({t.get('art')})"
    code = t.get("land_code")
    land = LAND.get(code)
    if code == "IT" and in_suedtirol(t.get("lat"), t.get("lon")):
        land = SUEDTIROL
    if not land:
        return [], f"außerhalb der Regionen ({code})"
    orte_je_land = orte_je_land if orte_je_land is not None else {}
    if land not in orte_je_land:
        orte_je_land[land] = orte_aus_places(land)
    st = standort_finden(t.get("ort"), t.get("lat"), t.get("lon"), orte_je_land[land])
    if not st:
        return [], f"Ort nicht eindeutig ({t.get('ort')})"
    name = t["name"].replace("’", "'")
    zusatz = ""
    m = _NAME_GRAVEL_ZUSATZ.search(name)
    if m:
        zusatz, name = m.group(1), name[: m.start()].strip()
    art = t.get("art") or ""
    basis = dict(land=land, name=name, standort=st[0], lat=st[1], lon=st[2], art1="Fahrrad",
                 datum_start=t["datum_start"], datum_ende=t.get("datum_ende") or t["datum_start"],
                 veranstalter_url=t.get("url") or KALENDER_URL)

    def kategorie(label: str) -> str:
        from scraper_lib import ART2_KEYWORDS_FAHRRAD
        for text in (label, ):
            for muster, wert in ART2_KEYWORDS_FAHRRAD:
                if text and muster.search(text):
                    return wert
        if re.search(r"straße", art, re.I):
            return "Straße"
        if re.search(r"gravel", f"{art} {name} {zusatz}", re.I):
            return "Gravel"
        for muster, wert in ART2_KEYWORDS_FAHRRAD:
            if muster.search(f"{art} {name}"):
                return wert
        return "Gravel"

    strecken = strecken_aus_meta(t.get("meta") or "")
    if not strecken:
        ev = Event(**basis, wettbewerb=zusatz or None)
        ev.art2 = kategorie(zusatz)
        return [ev], None
    events = []
    for km, label in strecken:
        if zusatz and not re.search(r"[A-Za-zÄÖÜäöü]{3}", label.replace("km", "")):
            label = f"{zusatz} {label}"
        ev = Event(**basis, laenge_km=km, wettbewerb=label)
        ev.art2 = kategorie(label.replace("km", ""))
        events.append(ev)
    return events, None


def fetch_dealgrid_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {KALENDER_URL} ...")
    html = fetch_page(session, KALENDER_URL, render_js=False)
    if not html:
        print("  ⚠ Kalender nicht abrufbar.")
        return []
    termine = parse_kalender(html)
    print(f"  ✓ {len(termine)} Termine.")
    events: list[Event] = []
    orte: dict = {}
    for t in termine:
        evs, grund = events_aus_termin(t, orte)
        if grund:
            print(f"   - {t.get('datum_start')} {t.get('name')}: {grund}")
            continue
        events.extend(evs)
    print(f"\n→ {len(events)} Zeilen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=KALENDER_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_dealgrid_events,
    note="dealgrid_scraper.py: Gravel-Kalender DealGrid (DE/AT/CH); je Distanz eine Zeile, "
         "Veranstalterlink je Termin, Spannen und Vorjahreswerte werden nicht geraten.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
