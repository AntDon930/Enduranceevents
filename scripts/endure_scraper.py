#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
endure_scraper.py
=================

Liest Radrennen, Radtourenfahrten und Triathlons aus dem Kalender von
https://events.endure-cycling.com und ergänzt sie in `events.json`
(siehe `scraper_lib.py` für die gemeinsame Logik: robots.txt-Prüfung,
Geocoding, Dedupe/Merge, CLI).

Rechtslage (geprüft am 22.09.2026, vom Nutzer freigegeben: „Bitte alle
scrapen! Aber auf ein scraping Verbot achten")
------------------------------------------------------------------------
robots.txt (https://events.endure-cycling.com/robots.txt) sperrt nichts.
Das Impressum (endure-cycling.com/imprint) nennt nur den allgemeinen
Urheberrechtshinweis, die Terms (endure-cycling.com/terms) regeln die
Trainings-App und sagen nichts zum Auslesen des Kalenders. Kein Verbot
- anders als runme.at, finishers.com, bike-x.de, brv-breitensport.de,
team-warmduscher.de und dsvdaten.dsv.de, die deshalb NICHT gelesen
werden (siehe README, „Quellen für den großen Datenlauf").

Struktur (am 22.09.2026 an der Live-Seite kalibriert)
-------------------------------------------------------
Astro-Seite, alles server-seitig gerendert, kein --render-js nötig.

* **Listenseiten** je Sport, Land und Jahr:
  `/radrennen/<land>/<jahr>` und `/triathlon/<land>/<jahr>`; Länder
  deutschland, oesterreich, schweiz, italien (Italien nur wegen
  Südtirol - was nicht in der Provinz Bozen liegt, wirft
  `scraper_lib.filter_dach()` über die Koordinaten heraus). Jede Karte
  (`<article>`) trägt Art ("Radrennen", "Radtourenfahrt", "Triathlon"),
  Datum ("5. April 2026", "18.–20. Juni 2026"), Name, Ort · Region,
  Tags (Radmarathon, Gran Fondo, RTF, Gravel, Sprintdistanz, …), km
  und Höhenmeter.
* **Detailseite** `/events/<slug>/` mit JSON-LD `SportsEvent`: exakte
  Start-/Enddaten, Koordinaten (`geo` - damit entfällt das Geocoding),
  `addressCountry`, Beschreibung und `sameAs` = die **offizielle Seite
  des Rennens** (z. B. https://rundumdenharz.com). Genau das ist
  Datenregel 2: `veranstalter_url` ist die Veranstalterseite, nie das
  Portal. Ohne `sameAs` bleibt die endure-Seite als Portallink stehen
  (`PORTAL_DOMAINS` kennt sie; ein späterer Datenlauf ersetzt ihn).

Distanzen
---------
Beim **Radrennen** nennt die Karte EINE Distanz (die Hauptstrecke);
weitere Strecken stehen nur im Beschreibungstext ("Langstrecke 297 km /
2.500 Hm …; Light-Variante 145 km / 1.300 Hm"). Übernommen werden aus
dem Text nur km-Angaben, vor denen ein Streckenwort steht (Strecke,
Variante, Distanz, Runde, Tour, Route, Fondo, Marathon, Lang-/Mittel-/
Kurzstrecke) - eine beliebige Zahl mit "km" im Text ("Anreise 5 km vom
Bahnhof") würde sonst eine Phantom-Strecke erzeugen.
Beim **Triathlon** ist die Karten-km die GESAMTLÄNGE (Sprintdistanz
"30 km" = Summe der Teilstrecken, Datenregel 15); das Format aus dem
Tag wird zum Label ("Sprintdistanz 30 km"). Weitere Formate derselben
Veranstaltung kennt die Karte nicht - geraten wird keines.

Nutzung: `python3 scripts/endure_scraper.py --help`
(Testlauf: `--dry-run --max-details 5`).
"""

from pathlib import Path
import json
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    COUNTRY_CODE_MAP,
    GERMAN_MONTHS,
    Event,
    SiteConfig,
    expand_competitions,
    fetch_page,
    guess_art1,
    guess_art2,
    parse_competitions,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://events.endure-cycling.com"

# Land-Slug der Listenseite -> unser Landesname. "Italien" ist nur ein
# Zwischenstand (Datenregel 4): filter_dach() macht daraus Südtirol,
# wo die Koordinaten in der Provinz Bozen liegen, und wirft den Rest.
LAENDER_SLUGS = [
    ("deutschland", "Deutschland"),
    ("oesterreich", "Österreich"),
    ("schweiz", "Schweiz"),
    ("italien", "Italien"),
]
SPORTARTEN = [("radrennen", "Fahrrad"), ("triathlon", "Triathlon")]

# Ein Streckenwort vor der km-Zahl: nur solche Angaben im Beschreibungs-
# text gelten als weitere Wettbewerbe (siehe Docstring).
_STRECKEN_KM = re.compile(
    r"(?:strecke|variante|distanz|runde|tour|route|fondo|marathon|"
    r"langstrecke|mittelstrecke|kurzstrecke|classic|light|medio|lungo|corto|"
    r"granfondo|mediofondo)[^.;\d]{0,25}?(\d{2,3}(?:[.,]\d)?)\s*km\b",
    re.I,
)

# Drei Schreibweisen: "5. April 2026", "18.–20. Juni 2026", "30. Mai –
# 1. Juni 2026". Der Monat des Starts steht NUR im dritten Fall, und
# dann vor dem Gedankenstrich - so ist das Muster eindeutig (ein
# optionaler Monat direkt vor dem Endmonat hätte "April" in "Apri" +
# "l" zerlegt).
_DATUM = re.compile(
    r"(\d{1,2})\.\s*(?:([A-Za-zÄÖÜäöü]+)\s*[–-]\s*(\d{1,2})\.\s*|[–-]\s*(\d{1,2})\.\s*)?"
    r"([A-Za-zÄÖÜäöü]+)\s+(\d{4})"
)


def parse_zeitraum(text: str) -> tuple[str | None, str | None]:
    """"5. April 2026" -> (2026-04-05, 2026-04-05);
    "18.–20. Juni 2026" -> (2026-06-18, 2026-06-20);
    "30. Mai – 1. Juni 2026" -> (2026-05-30, 2026-06-01)."""
    m = _DATUM.search(text or "")
    if not m:
        return None, None
    d1, mon1, d2a, d2b, mon2, jahr = m.groups()
    d2 = d2a or d2b
    monat_ende = GERMAN_MONTHS.get(mon2.lower())
    monat_start = GERMAN_MONTHS.get((mon1 or mon2).lower())
    if not monat_ende or not monat_start:
        return None, None
    start = parse_flexible_date(f"{int(d1):02d}.{monat_start:02d}.{jahr}")
    ende = parse_flexible_date(f"{int(d2):02d}.{monat_ende:02d}.{jahr}") if d2 else start
    return start, ende or start


def parse_karten(soup: BeautifulSoup) -> list[dict]:
    """Die Karten einer Listenseite: Detail-URL, Art, Datum, Name, Ort,
    Tags, km."""
    karten = []
    for art in soup.select("article"):
        a = art.select_one("a[href^='/events/']")
        if not a:
            continue
        spans = [s.get_text(" ", strip=True) for s in a.select(":scope > div:first-child > span")]
        h3 = a.select_one("h3")
        ort_p = a.select_one("p")
        ort_text = re.sub(r"[\U0001F1E6-\U0001F1FF]", "", ort_p.get_text(" ", strip=True)) if ort_p else ""
        ort = ort_text.split("·")[0].strip()
        region = ort_text.split("·")[1].strip() if "·" in ort_text else ""
        tags = [s.get_text(" ", strip=True) for s in a.select("span.rounded-md")]
        km = None
        for s in a.select("div.flex.gap-4 span"):
            t = s.get_text(" ", strip=True)
            mk = re.match(r"(\d{1,4}(?:[.,]\d)?)\s*km$", t)
            if mk:
                km = float(mk.group(1).replace(",", "."))
        karten.append({
            "url": BASE_URL + a["href"],
            "art": spans[0] if spans else "",
            "datum": spans[1] if len(spans) > 1 else "",
            "name": h3.get_text(" ", strip=True) if h3 else "",
            "ort": ort, "region": region, "tags": tags, "km": km,
        })
    return karten


def parse_detail(html: str) -> dict:
    """JSON-LD SportsEvent der Detailseite: Daten, Koordinaten, Land,
    Beschreibung und die offizielle Seite (`sameAs`)."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in (data if isinstance(data, list) else [data]):
            if not isinstance(item, dict) or item.get("@type") not in ("SportsEvent", "Event"):
                continue
            loc = item.get("location") or {}
            adresse = loc.get("address") or {} if isinstance(loc, dict) else {}
            geo = loc.get("geo") or {} if isinstance(loc, dict) else {}
            lat = lon = None
            try:
                lat, lon = float(geo.get("latitude")), float(geo.get("longitude"))
            except (TypeError, ValueError):
                pass
            same_as = item.get("sameAs")
            if isinstance(same_as, list):
                same_as = same_as[0] if same_as else None
            return {
                "name": item.get("name"),
                "start": parse_flexible_date(str(item.get("startDate") or "")),
                "ende": parse_flexible_date(str(item.get("endDate") or "")),
                "ort": (adresse.get("addressLocality") if isinstance(adresse, dict) else None)
                       or (loc.get("name") if isinstance(loc, dict) else None),
                "land_code": adresse.get("addressCountry") if isinstance(adresse, dict) else None,
                "lat": lat, "lon": lon,
                "beschreibung": item.get("description") or "",
                "official_url": same_as if isinstance(same_as, str) and same_as.startswith("http") else None,
            }
    return {}


def strecken_aus_text(text: str) -> list[float]:
    """km-Angaben mit Streckenwort davor (siehe Docstring), ohne Doppelte."""
    werte: list[float] = []
    for m in _STRECKEN_KM.finditer(text or ""):
        km = float(m.group(1).replace(",", "."))
        if km not in werte:
            werte.append(km)
    return werte


def fetch_endure_events(session, config, delay, max_pages, render_js) -> list[Event]:
    from datetime import date
    jahre = [date.today().year, date.today().year + 1]
    events: list[Event] = []
    details = official = 0
    for sport_slug, art1 in SPORTARTEN:
        for land_slug, land in LAENDER_SLUGS:
            for jahr in jahre:
                url = f"{BASE_URL}/{sport_slug}/{land_slug}/{jahr}"
                print(f"→ Lade Liste {url} ...")
                # Eine Liste, die es (noch) nicht gibt - etwa Schweiz 2027 -
                # antwortet mit 404; das ist kein Fehler, nur leer.
                try:
                    resp = session.get(url, timeout=20)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ⚠ {url}: {exc}")
                    continue
                time.sleep(delay)
                if resp.status_code == 404:
                    print("  (keine Liste - 404)")
                    continue
                if resp.status_code != 200:
                    print(f"  ⚠ HTTP {resp.status_code}")
                    continue
                html = resp.text
                karten = parse_karten(BeautifulSoup(html, "html.parser"))
                print(f"  ✓ {len(karten)} Karte(n).")
                for k in karten:
                    start, ende = parse_zeitraum(k["datum"])
                    ev = Event(land=land, name=k["name"], standort=k["ort"],
                               art1=art1, datum_start=start, datum_ende=ende,
                               veranstalter_url=k["url"])
                    beschreibung = ""
                    if config.fetch_details and (not config.max_details or details < config.max_details):
                        time.sleep(delay)
                        dhtml = fetch_page(session, k["url"], render_js=False)
                        details += 1
                        d = parse_detail(dhtml) if dhtml else {}
                        if d:
                            ev.datum_start = d.get("start") or ev.datum_start
                            ev.datum_ende = d.get("ende") or ev.datum_ende or ev.datum_start
                            ev.standort = d.get("ort") or ev.standort
                            ev.lat, ev.lon = d.get("lat"), d.get("lon")
                            code = str(d.get("land_code") or "").upper()
                            ev.land = COUNTRY_CODE_MAP.get(code) or ev.land
                            beschreibung = d.get("beschreibung") or ""
                            if d.get("official_url"):
                                ev.veranstalter_url = d["official_url"]
                                official += 1
                    if not ev.name or not ev.datum_start:
                        continue
                    ev.datum_ende = ev.datum_ende or ev.datum_start
                    # Sportart: die Karte sagt es ("Radrennen"/"Radtourenfahrt"
                    # -> Fahrrad, "Triathlon" -> Triathlon); guess_art1 darf
                    # einen Duathlon/Swimrun in der Radliste noch umhängen.
                    ev.art1 = guess_art1(f"{ev.name} {k['art']}", config) if art1 == "Fahrrad" else art1
                    if ev.art1 == "Laufen":
                        ev.art1 = art1
                    tags = " ".join(k["tags"])
                    ev.art2 = guess_art2(f"{ev.name} {tags} {k['art']}", config, ev.art1)
                    # Strecken: Karten-km (Hauptstrecke bzw. Gesamtlänge des
                    # Triathlons), beim Rad dazu weitere aus dem Text.
                    kms: list[float] = [k["km"]] if k["km"] else []
                    if ev.art1 == "Fahrrad":
                        for km in strecken_aus_text(beschreibung):
                            if km not in kms:
                                kms.append(km)
                    # Das Label: beim Rad der erste Tag ("Radmarathon"); beim
                    # Triathlon das Format - aber nur, wenn die Karte GENAU EIN
                    # Format nennt. Bei "Sprint" UND "Olympisch" gehört die eine
                    # km-Zahl zu einem der beiden, und welches, sagt die Karte
                    # nicht; dann entscheidet die Summe (Datenregel 21).
                    formate = [t for t in k["tags"] if re.search(r"distanz|sprint|olymp|mittel|lang|ultra|70\.3|140\.6", t, re.I)]
                    if ev.art1 == "Triathlon":
                        label = formate[0] if len(formate) == 1 else ""
                    else:
                        label = k["tags"][0] if k["tags"] else ""
                    texte = [f"{label} {km:g} km".strip() for km in kms]
                    varianten = expand_competitions(ev, parse_competitions(texte, config), config)
                    for v in varianten:
                        # expand_competitions nimmt art2 aus dem Label - das
                        # ist hier der Tag der Karte, den guess_art2 oben
                        # schon gelesen hat; ohne Treffer bleibt unser Wert.
                        if v.art2 is None:
                            v.art2 = ev.art2
                    events.extend(varianten)
    print(f"\n→ {details} Detailseite(n) abgerufen, davon {official} mit offizieller Seite.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=f"{BASE_URL}/radrennen/deutschland/2026",
    default_art1="Fahrrad",
    custom_fetch=fetch_endure_events,
    note="endure_scraper.py: robots.txt erlaubt den Zugriff (22.09.2026); "
         "Listen je Sport/Land/Jahr, Detailseite mit JSON-LD und der "
         "offiziellen Seite (sameAs).",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
