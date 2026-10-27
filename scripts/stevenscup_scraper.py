#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stevenscup_scraper.py
=====================

Liest den Rennkalender des **Stevens Cyclo-Cross Cups**
(https://www.stevenscup.de/rennen) - die norddeutsche Querfeldein-Serie
(Hamburg, Schleswig-Holstein, Niedersachsen, Mecklenburg-Vorpommern,
Bremen) - und ergänzt die Rennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben: „bitte alle
die es erlauben einbauen")
----------------------------------------------------------------------
robots.txt (Contao) sperrt nur `/contao/`; das Impressum trägt keinen
Vorbehalt gegen das Auslesen. Übernommen werden Termine, Orte und
Links, keine Texte.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Eine Seite, je Rennen ein `div.event` (`.upcoming` für die kommenden,
darunter „Vergangene Rennen"): `h1` „#02 - Hannover" (Nummer im Cup und
Ort der Serie), `h3` „Cyclocross Hannover City mit Bezirksmeisterschaft"
(der Name des Rennens, in Anführungszeichen, gelegentlich fehlend),
`p.info time[datetime]`, `p.location` „Adresse: … 30459 Hannover | …",
`div.racedata` mit „Ausrichter: <a href=…>RSG Hannover</a>" (die
Veranstalterseite, Datenregel 2; ohne Link steht der Ausrichter als
Text) und „Meldeschluss: 30.09.2026", `p.apply_link` mit raceresult-
Anmeldung und rad-net-Ausschreibung. Im September 2026: 16 Rennen.

Was daraus wird
---------------
* Fahrrad / Cyclecross, eine Zeile je Rennen - ein Querfeldeinrennen
  hat keine Renndistanz (Rundenrennen auf Zeit je Klasse, die Seite
  nennt keine Dauer), die Länge bleibt leer.
* Name: der `h3`-Titel ohne Anführungszeichen, sonst „Stevens Cyclo-Cross
  Cup <Ort>". Das Label nennt Cup und Lauf („Stevens Cyclo-Cross Cup #02").
* Ort: der Ort hinter der PLZ in der Adresse (dort liegt die Strecke -
  „#04 - Mölln" fährt in Grambek), gegen `places.json` geprüft, sonst der
  Ort aus `h1`; Koordinaten aus `places.json`, kein Nominatim.
* `veranstalter_url`: der Ausrichter-Link; ohne ihn die raceresult-
  Anmeldung, sonst die Cup-Seite (beide in `PORTAL_DOMAINS`).
* Anmeldeschluss aus „Meldeschluss".

Nutzung: `python3 scripts/stevenscup_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    ort_im_text,
    orte_aus_places,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.stevenscup.de"
RENNEN_URL = f"{BASE_URL}/rennen"
CUP = "Stevens Cyclo-Cross Cup"

_PLZ_ORT = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß.-]+(?:\s+(?:am|an|bei|in|im|an der|in der|ob)\s+[A-ZÄÖÜ][\wäöüß-]+|\s+[A-ZÄÖÜ][\wäöüß-]+)?)")


def parse_rennen(html: str) -> list[dict]:
    """Alle `div.event`-Blöcke als Wörterbücher (nummer, ort_cup, name,
    datum, adresse, ausrichter, ausrichter_url, meldeschluss, anmeldung)."""
    soup = BeautifulSoup(html, "html.parser")
    rennen = []
    for block in soup.select("div.event"):
        h1 = block.find("h1")
        if not h1:
            continue
        m = re.match(r"\s*#?\s*(\d+)\s*[-–]\s*(.+?)\s*$", h1.get_text(" ", strip=True))
        eintrag: dict = {"nummer": m.group(1) if m else None,
                         "ort_cup": m.group(2) if m else h1.get_text(" ", strip=True)}
        h3 = block.find("h3")
        eintrag["name"] = h3.get_text(" ", strip=True).strip("„“\"' ") if h3 else None
        zeit = block.find("time")
        eintrag["datum"] = parse_flexible_date(zeit.get("datetime") or zeit.get_text()) if zeit else None
        loc = block.select_one("p.location")
        eintrag["adresse"] = re.sub(r"^\s*Adresse:\s*", "", loc.get_text(" ", strip=True)) if loc else None
        eintrag["ausrichter"] = eintrag["ausrichter_url"] = eintrag["meldeschluss"] = None
        for p in block.select("div.racedata p"):
            text = p.get_text(" ", strip=True)
            if text.startswith("Ausrichter"):
                a = p.find("a", href=True)
                eintrag["ausrichter"] = re.sub(r"^Ausrichter:\s*", "", text).strip() or None
                eintrag["ausrichter_url"] = a["href"].strip() if a else None
            elif text.startswith("Meldeschluss"):
                eintrag["meldeschluss"] = parse_flexible_date(text)
        anm = block.select_one("p.apply_link a[href*='raceresult']")
        eintrag["anmeldung"] = anm["href"] if anm else None
        eintrag["vergangen"] = "upcoming" not in (block.get("class") or [])
        rennen.append(eintrag)
    return rennen


def ort_aus_adresse(adresse: str | None, orte: dict) -> tuple[str, float | None, float | None] | None:
    """„Herbrink 30, 38667 Bad Harzburg" -> Bad Harzburg (mit Koordinaten aus
    places.json). Geprüft wird der Ort hinter der PLZ, nicht die Straße."""
    for m in _PLZ_ORT.finditer(adresse or ""):
        kandidat = m.group(2).strip()
        treffer = ort_im_text(kandidat, orte)
        if treffer:
            return treffer
    return None


def event_aus_rennen(r: dict, orte: dict | None = None) -> tuple[Event | None, str | None]:
    if not r.get("datum"):
        return None, "kein Datum"
    orte = orte if orte is not None else orte_aus_places("Deutschland")
    ort = ort_aus_adresse(r.get("adresse"), orte) or ort_im_text(r.get("ort_cup"), orte)
    if not ort:
        return None, f"kein Ort ({r.get('adresse') or r.get('ort_cup')})"
    standort, lat, lon = ort
    name = r.get("name") or f"{CUP} {r.get('ort_cup')}"
    label = f"Cyclocross, {CUP}" + (f" #{r['nummer']}" if r.get("nummer") else "")
    url = r.get("ausrichter_url") or r.get("anmeldung") or RENNEN_URL
    ev = Event(land="Deutschland", name=name, standort=standort, lat=lat, lon=lon,
               art1="Fahrrad", datum_start=r["datum"], datum_ende=r["datum"],
               anmeldeschluss=r.get("meldeschluss"), wettbewerb=label, veranstalter_url=url)
    ev.art2 = "Cyclecross"
    return ev, None


def fetch_stevenscup_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {RENNEN_URL} ...")
    html = fetch_page(session, RENNEN_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    rennen = parse_rennen(html)
    print(f"  ✓ {len(rennen)} Rennen auf der Seite ({sum(1 for r in rennen if r['vergangen'])} vergangene).")
    orte = orte_aus_places("Deutschland")
    events: list[Event] = []
    for r in rennen:
        if r["vergangen"]:
            continue
        ev, grund = event_aus_rennen(r, orte)
        if grund:
            print(f"   - #{r.get('nummer')} {r.get('ort_cup')}: {grund}")
            continue
        events.append(ev)
    print(f"\n→ {len(events)} Rennen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=RENNEN_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_stevenscup_events,
    note="stevenscup_scraper.py: Stevens Cyclo-Cross Cup (Norddeutschland); eine Zeile je "
         "Rennen ohne Distanz, Ort aus der Adresse, Ausrichter-Link als Veranstalterseite.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
