#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radsportevents_scraper.py
=========================

Liest die JSON-API von https://radsport-events.de (Rennrad, Mountainbike
und Gravel: RTF, CTF, Radmarathons, Jedermannrennen, Cyclocross, Gravel-
Races, Brevets, Ultracycling, dazu einige Duathlons/Triathlons) und ergänzt
sie in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026)
----------------------------------
Am 21.09.2026 stand die Seite auf Wunsch des Nutzers auf der Liste der
ausgeschlossenen Quellen ("sperren den Abruf oder verbieten ihn"). Am
24.09.2026 erneut geprüft: robots.txt `User-agent: * Allow: /` (gesperrt
sind nur Nutzerbereiche wie /users, /dashboard, /favorites), das Impressum
(GSK-IT UG, Isernhagen) nennt kein Verbot, Nutzungsbedingungen oder AGB
gibt es nicht (404), die API-Domain hat keine robots.txt. Der Nutzer hat
die Seite am selben Tag mit sechs Adressen in seiner Linkliste geschickt
("Bitte alle checken") - das gilt hier als sein Ja. Wer das umdreht, nimmt
das Skript aus dem Lauf (`--only`-Liste in update_events.py) oder löscht es.

Struktur (am 24.09.2026 kalibriert)
-----------------------------------
Die Webseite ist eine React-Anwendung; die Daten kommen von
`https://api.radsport-events.de/api/v1/events?page=N&size=200&category=K
&country=L` mit K in ROAD/MTB/GRAVEL und L in DE/AT/CH/IT (die Seite kennt
weitere Länder, die wir nicht brauchen). Antwort: `content` (Liste),
`totalPages`. **Jeder Listeneintrag ist vollständig** - eine Detailseite
ist nicht nötig:

* `title`, `eventDate`, `endDate`, `tentative` (Termin vorläufig →
  `datum_vorlaeufig`), `cancelled` (→ übersprungen), `status`;
* `city`, `bundesland`, `country`, `latitude`/`longitude` (Koordinaten,
  Nominatim entfällt; bei `country == "IT"` entscheidet `filter_dach()`
  über die Koordinaten, ob es Südtirol ist);
* `category` (ROAD/MTB/GRAVEL) und `eventType` (RADMARATHON, RTF, CTF,
  JEDERMANN, HOBBYRENNEN, CYCLOCROSS, GRAVEL_RACE, ULTRA, BREVET, …);
  `secondaryCategories` (dieselbe Veranstaltung erscheint dann in
  mehreren Kategorielisten - `id` dedupliziert);
* `distances`: je Strecke `distanceKm`, `durationMinutes`, `label`;
* `organizerUrl` = die Seite des Veranstalters (Datenregel 2), sonst bleibt
  `radsport-events.de/events/<id>` als Portallink stehen.

Was daraus wird
---------------
* **Übersprungen** werden Italien außerhalb Südtirols (Koordinaten gegen
  den Umriss in `laender.json`), abgesagte Termine, `VIRTUELLE_RTF` (virtuelle
  Läufe, Datenregel 14), `GRAVEL_CAMP` und `ETAPPENTOUR` (Camps und
  geführte Touren, keine Veranstaltung mit Startlinie) und
  `MANNSCHAFTSZEITFAHREN` (Teamwettbewerb, Datenregel 16).
* **Je Strecke ein Eintrag** (Datenregel 1). Eine Strecke mit dem Label
  „Runde"/„pro Runde" ist die RUNDENLÄNGE und keine Renndistanz
  (Datenregel 8) - sie fällt weg; `durationMinutes` (Cyclocross 40 min,
  2-Stunden-Rennen) wird zur Dauer `dauer_h`; ein `RENNEN_24H` ohne
  Angabe bekommt 24 h. `distanceKm` 0 gilt als unbekannt.
* **Sportart**: ROAD → Straße (Zeitfahren-Typen → Zeitfahren), MTB →
  Mountainbike (CYCLOCROSS → Cyclecross), GRAVEL → Gravel. TRIATHLON,
  DUATHLON und DUATHLON_CROSS werden Triathlon (Duathlon: das Format
  steht vor dem Gelände, Datenregel 11). Bei ihnen ist die Länge die
  SUMME der Teilstrecken (Datenregel 15) - aber nur, wenn die Labels die
  Teilstrecken benennen („Lauf", „Rad", „Laufstrecke", „Radstrecke").
  Unbeschriftete Zahlen eines Duathlons (3 km und 14 km beim Speck-Race:
  Lauf und Rad, oder zwei Wettbewerbe?) sind nicht zu deuten - dann bleibt
  der Eintrag ohne Länge, geraten wird nicht.
* Das Label ist der Veranstaltungstyp auf Deutsch samt Strecke
  („Radmarathon 200 km", „Gravel Race 96 km", „Cyclocross 40 min").
* Cyclocross- und Hobbyrennen sind Rennen mit Klassen; ob eine
  Jedermann-Klasse dabei ist, sagt die API nicht. Sie bleiben drin - die
  Seite nennt sich selbst „Termine für Hobby- und Jedermannrennen".

Stand 24.09.2026: 387 Veranstaltungen (ROAD 200, MTB 168, GRAVEL 90 mit
Überschneidungen), davon 42 in Italien (Südtirol-Filter über die
Koordinaten), Termine bis Oktober 2027.

Nutzung: `python3 scripts/radsportevents_scraper.py --help`
(Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    COUNTRY_CODE_MAP,
    Event,
    SiteConfig,
    guess_art1,
    guess_art2,
    in_suedtirol,
    parse_flexible_date,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://radsport-events.de"
API_URL = "https://api.radsport-events.de/api/v1/events"
KATEGORIEN = ("ROAD", "MTB", "GRAVEL")
LAENDER = ("DE", "AT", "CH", "IT")
SEITENGROESSE = 200

# Veranstaltungstypen, die keine Veranstaltung mit Startlinie sind
# (oder nach den Datenregeln nicht in die Liste gehören).
UEBERSPRINGEN = {"VIRTUELLE_RTF", "GRAVEL_CAMP", "ETAPPENTOUR", "MANNSCHAFTSZEITFAHREN"}
MEHRSPORT = {"TRIATHLON": "Triathlon", "DUATHLON": "Duathlon", "DUATHLON_CROSS": "Duathlon"}
ZEITFAHREN = {"EINZELZEITFAHREN", "BERGZEITFAHREN", "HILLCLIMB"}

TYP_LABEL = {
    "RADMARATHON": "Radmarathon", "RTF": "RTF", "CTF": "CTF", "JEDERMANN": "Jedermannrennen",
    "HOBBYRENNEN": "Hobbyrennen", "VOLKSRADFAHREN": "Volksradfahren", "CYCLOCROSS": "Cyclocross",
    "CROSSCOUNTRY": "Cross-Country", "MTB_MARATHON": "MTB-Marathon", "ENDURO": "Enduro",
    "DOWNHILL": "Downhill", "SONSTIGE_MTB": "MTB", "GRAVEL_RACE": "Gravel Race",
    "GRAVEL_TOUR": "Gravel Tour", "GRAVEL_RIDE": "Gravel Ride", "GRAVEL_BREVET": "Gravel Brevet",
    "GRAVEL_SONSTIGES": "Gravel", "ULTRA": "Ultracycling", "BIKEPACKING": "Bikepacking",
    "BREVET": "Brevet", "EINZELZEITFAHREN": "Einzelzeitfahren", "BERGZEITFAHREN": "Bergzeitfahren",
    "HILLCLIMB": "Hillclimb", "RENNEN_24H": "24-Stunden-Rennen", "RENNEN_2_3_6H": "Stundenrennen",
    "ETAPPENRENNEN": "Etappenrennen", "VINTAGE_TOUR": "Vintage-Tour", "TRIATHLON": "Triathlon",
    "DUATHLON": "Duathlon", "DUATHLON_CROSS": "Cross-Duathlon", "SONSTIGE": "",
}
KATEGORIE_ART2 = {"ROAD": "Straße", "MTB": "Mountainbike", "GRAVEL": "Gravel"}

_RUNDE = re.compile(r"runde", re.I)
_TEILSTRECKE = re.compile(r"^(lauf|rad|schwimm)", re.I)


def _strecken(item: dict) -> list[tuple[float | None, float | None, str]]:
    """(km, Stunden, Label) je Strecke - ohne Rundenlängen, 0 km = unbekannt."""
    out = []
    for d in item.get("distances") or []:
        label = (d.get("label") or "").strip()
        if _RUNDE.search(label):
            continue
        km = d.get("distanceKm")
        km = round_km(km) if isinstance(km, (int, float)) and km > 0 else None
        minuten = d.get("durationMinutes")
        stunden = round(minuten / 60, 1) if isinstance(minuten, (int, float)) and minuten > 0 else None
        if km is None and stunden is None:
            continue
        out.append((km, stunden, label))
    return out


def _label(typ: str | None, km: float | None, stunden: float | None, zusatz: str = "") -> str | None:
    teile = [TYP_LABEL.get(typ or "", "")]
    if zusatz:
        teile.append(zusatz)
    if km is not None:
        teile.append(f"{km:g} km")
    elif stunden is not None:
        teile.append(f"{stunden:g} h")
    text = " ".join(t for t in teile if t).strip()
    return text or None


def parse_item(item: dict, config: SiteConfig) -> list[Event]:
    """Ein API-Eintrag -> null, ein oder mehrere Events."""
    typ = item.get("eventType")
    if item.get("cancelled") or typ in UEBERSPRINGEN or item.get("status", "PUBLISHED") != "PUBLISHED":
        return []
    name = (item.get("title") or "").strip()
    start = parse_flexible_date(str(item.get("eventDate") or ""))
    if not name or not start:
        return []
    ende = parse_flexible_date(str(item.get("endDate") or "")) or start
    kategorie = item.get("category") or "ROAD"
    lat, lon = item.get("latitude"), item.get("longitude")
    # Italien nur, wo die Koordinaten in Südtirol liegen (Datenregel 4):
    # Gran Fondos in Bergamo oder Olbia landen sonst als "Italien" in
    # events.json und fliegen erst beim nächsten Aufräumen wieder heraus.
    if str(item.get("country") or "").upper() == "IT" and not in_suedtirol(lat, lon):
        return []
    url = item.get("organizerUrl") or f"{BASE_URL}/events/{item.get('id')}"
    if not re.match(r"^https?://", url):
        url = "https://" + url
    basis = dict(
        land=COUNTRY_CODE_MAP.get(str(item.get("country") or "").upper()),
        name=name, standort=(item.get("city") or "").strip() or None,
        lat=lat if isinstance(lat, (int, float)) else None,
        lon=lon if isinstance(lon, (int, float)) else None,
        datum_start=start, datum_ende=ende, veranstalter_url=url,
        datum_vorlaeufig=True if item.get("tentative") else None,
    )
    strecken = _strecken(item)
    if typ == "RENNEN_24H" and not strecken:
        strecken = [(None, 24.0, "")]

    if typ in MEHRSPORT:
        # Mehrsport: Summe der beschrifteten Teilstrecken (Datenregel 15),
        # sonst ohne Länge - unbeschriftete Zahlen sind nicht zu deuten.
        ev = Event(**basis, art1="Triathlon")
        ev.art2 = guess_art2(f"{name} {MEHRSPORT[typ]}", config, "Triathlon") or MEHRSPORT[typ]
        teile = [(km, label) for km, _, label in strecken if km and _TEILSTRECKE.match(label)]
        if teile and len(teile) == len(strecken):
            summe = round_km(sum(km for km, _ in teile))
            ev.laenge_km = summe
            ev.wettbewerb = f"{TYP_LABEL[typ]} {summe:g} km (" + " / ".join(
                f"{km:g} km {label}" for km, label in teile) + ")"
        else:
            ev.wettbewerb = TYP_LABEL[typ]
        return [ev]

    art1 = guess_art1(name, config)  # ein "Swimrun" im Radkalender bliebe sonst Fahrrad
    if art1 == "Laufen":
        art1 = "Fahrrad"
    art2 = KATEGORIE_ART2[kategorie]
    if typ in ZEITFAHREN:
        art2 = "Zeitfahren"
    elif typ == "CYCLOCROSS":
        art2 = "Cyclecross"
    elif kategorie == "ROAD":
        art2 = guess_art2(name, config, "Fahrrad") or art2
    if not strecken:
        return [Event(**basis, art1=art1, art2=art2, wettbewerb=_label(typ, None, None))]
    events = []
    gesehen = set()
    for km, stunden, label in strecken:
        schluessel = (km, stunden)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ev = Event(**basis, art1=art1, art2=art2, laenge_km=km, dauer_h=stunden,
                   wettbewerb=_label(typ, km, stunden, label))
        events.append(ev)
    return events


def fetch_radsportevents(session, config, delay, max_pages, render_js) -> list[Event]:
    gesehen: set = set()
    events: list[Event] = []
    roh = 0
    for kategorie in KATEGORIEN:
        for land in LAENDER:
            seite = 0
            while True:
                url = f"{API_URL}?page={seite}&size={SEITENGROESSE}&category={kategorie}&country={land}"
                print(f"→ Lade {kategorie} {land} Seite {seite} ...")
                try:
                    resp = session.get(url, timeout=30)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ⚠ {exc}")
                    break
                time.sleep(delay)
                if resp.status_code != 200:
                    print(f"  ⚠ HTTP {resp.status_code}")
                    break
                try:
                    daten = resp.json()
                except ValueError:
                    print("  ⚠ keine JSON-Antwort")
                    break
                inhalt = daten.get("content") or []
                for item in inhalt:
                    if item.get("id") in gesehen:
                        continue
                    gesehen.add(item.get("id"))
                    roh += 1
                    events.extend(parse_item(item, config))
                seite += 1
                if seite >= int(daten.get("totalPages") or 1) or not inhalt or seite >= max_pages:
                    break
    print(f"\n→ {roh} Veranstaltungen der API, {len(events)} Strecken-Einträge.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=f"{BASE_URL}/rennrad-events",
    default_art1="Fahrrad",
    custom_fetch=fetch_radsportevents,
    note="radsportevents_scraper.py: JSON-API (api.radsport-events.de), robots.txt frei, "
         "Impressum ohne Verbot (24.09.2026); je Kategorie und Land eine Liste, keine Detailseiten.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
