#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crosscup_scraper.py
===================

Liest den **GUNSHA Crosscup** (https://crosscup.org) - die mitteldeutsche
Querfeldein-Serie (Sachsen, Sachsen-Anhalt, Thüringen) - und ergänzt die
Rennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
robots.txt (WordPress) sperrt nur `/wp-admin/`; das Impressum trägt
keinen Vorbehalt. Übernommen werden Termine, Orte, Koordinaten und der
Veranstalterlink. Die Anmeldung läuft über zpn-timing.de, dessen
Nutzungsbedingungen die private Nutzung vorbehalten - die Seite wird
deshalb NICHT abgerufen (`PORTAL_DOMAINS`).

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Das Menü der Startseite verlinkt je Rennen `/rennen/<slug>/` („11.10. –
Borna"; der Slug ist nicht immer der Ort: `dornburg` ist der Lauf in
Jena). Die Rennseite nennt im Text „Termin: 11.10.26 / 10:00 Uhr",
„Ort: Borna" (auch „Mühlhäuser Radibor"), „GPS-Daten: 51.13386715,
12.4962859", „Streckenlänge: 2,4km" (die RUNDE - keine Renndistanz,
Datenregel 8/Backyard-Lehre), „Internetseite des Veranstalters:
https://rsvborna.de" (Datenregel 2). Im September 2026: 7 Rennen.

Was daraus wird
---------------
* Fahrrad / Cyclecross, eine Zeile je Rennen ohne Länge (die Seite
  nennt keine Renndauer je Klasse).
* Name „GUNSHA Crosscup <Ort>", Label „Cyclocross, GUNSHA Crosscup".
* Ort aus „Ort:", Koordinaten aus „GPS-Daten" (die Strecke selbst -
  genauer als jeder Geocoder); ohne Koordinaten gegen `places.json`.
* Termin: Tag aus der Rennseite („11.10.26"), zweistelliges Jahr.
* `veranstalter_url`: die Veranstalterseite; ohne sie die Rennseite
  des Cups (`PORTAL_DOMAINS`).

Nutzung: `python3 scripts/crosscup_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    ort_im_text,
    orte_aus_places,
    run_scraper_cli,
)

BASE_URL = "https://crosscup.org"
CUP = "GUNSHA Crosscup"

# Radibor schreibt „Termin : 25.10.26" mit Leerzeichen vor dem Doppelpunkt
# und den Veranstalter ohne Schema („www.rsv-bautzen.de").
# places.json führt die Stadt unter ihrem amtlichen Namen.
ORTSNAMEN = {"Wittenberg": "Lutherstadt Wittenberg"}
_TERMIN = re.compile(r"Termin\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
_ORT = re.compile(r"\bOrt\s*:\s*(.+?)\s+(?:GPS-Daten|Umkleide|Rennstrecke|Streckenl|Internetseite)")
_GPS = re.compile(r"GPS-Daten\s*:\s*(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")
_VERANSTALTER = re.compile(r"Internetseite des Veranstalters\s*:\s*((?:https?://)?[\w.-]+\.[a-z]{2,}\S*)", re.I)


def parse_rennen_links(html: str) -> list[tuple[str, str]]:
    """(Adresse, Beschriftung) je Rennseite aus dem Menü - „29.11. – Wittenberg";
    die Beschriftung ist der zweite Ortskandidat, wenn die Rennseite nur
    „Volkspark Piesteritz" nennt."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    gesehen: set[str] = set()
    for a in soup.select("a[href*='/rennen/']"):
        url = urljoin(BASE_URL, a["href"].split("#")[0])
        if re.search(r"/rennen/[^/]+/?$", url) and url not in gesehen:
            gesehen.add(url)
            label = re.sub(r"^\s*\d{1,2}\.\d{1,2}\.\s*[–-]?\s*", "", a.get_text(" ", strip=True))
            links.append((url, label))
    return links


def _seitentext(html: str) -> str:
    """Der Seitentext in EINER Zeile - „Termin:" und Wert stehen in
    getrennten Tags. Die Meta-Beschreibung (og:description) trägt dieselben
    Angaben und kommt zuerst, dann der Fließtext."""
    soup = BeautifulSoup(html, "html.parser")
    teile = []
    meta = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        teile.append(meta["content"])
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    teile.append(soup.get_text(" "))
    return re.sub(r"\s+", " ", " ".join(teile))


def parse_rennseite(html: str) -> dict:
    text = _seitentext(html)
    ergebnis: dict = {}
    m = _TERMIN.search(text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        ergebnis["datum"] = f"{y:04d}-{mo:02d}-{d:02d}"
    m = _ORT.search(text)
    if m:
        ergebnis["ort"] = m.group(1).strip()
    m = _GPS.search(text)
    if m:
        ergebnis["lat"], ergebnis["lon"] = float(m.group(1)), float(m.group(2))
    m = _VERANSTALTER.search(text)
    if m:
        url = m.group(1).rstrip(".,;")
        ergebnis["veranstalter_url"] = url if "://" in url else "https://" + url
    return ergebnis


def event_aus_rennseite(seite: dict, url: str, orte: dict | None = None,
                        menue_ort: str | None = None) -> tuple[Event | None, str | None]:
    if not seite.get("datum"):
        return None, "kein Termin"
    if not seite.get("ort") and not menue_ort:
        return None, "kein Ort"
    orte = orte if orte is not None else orte_aus_places("Deutschland")
    treffer = (ort_im_text(seite.get("ort"), orte, mehrdeutig_ok=True)
               or ort_im_text(menue_ort, orte, ausnahmen=ORTSNAMEN, mehrdeutig_ok=True))
    if not treffer:
        return None, f"kein Ort in places.json ({seite.get('ort')} / {menue_ort})"
    standort = treffer[0]
    lat, lon = seite.get("lat"), seite.get("lon")
    if lat is None and treffer:
        lat, lon = treffer[1], treffer[2]
    ev = Event(land="Deutschland", name=f"{CUP} {standort}", standort=standort, lat=lat, lon=lon,
               art1="Fahrrad", datum_start=seite["datum"], datum_ende=seite["datum"],
               wettbewerb=f"Cyclocross, {CUP}", veranstalter_url=seite.get("veranstalter_url") or url)
    ev.art2 = "Cyclecross"
    return ev, None


def fetch_crosscup_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {BASE_URL} ...")
    html = fetch_page(session, BASE_URL + "/", render_js=False)
    if not html:
        print("  ⚠ Startseite nicht abrufbar.")
        return []
    links = parse_rennen_links(html)
    print(f"  ✓ {len(links)} Rennseiten im Menü.")
    if config.max_details:
        links = links[: config.max_details]
    orte = orte_aus_places("Deutschland")
    events: list[Event] = []
    for url, label in links:
        time.sleep(delay)
        seite_html = fetch_page(session, url, render_js=False)
        if not seite_html:
            print(f"   - {url}: nicht abrufbar")
            continue
        ev, grund = event_aus_rennseite(parse_rennseite(seite_html), url, orte, label)
        if grund:
            print(f"   - {url}: {grund}")
            continue
        print(f"   ✓ {ev.datum_start} {ev.name} ({ev.veranstalter_url})")
        events.append(ev)
    print(f"\n→ {len(events)} Rennen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=BASE_URL + "/",
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_crosscup_events,
    note="crosscup_scraper.py: GUNSHA Crosscup (Mitteldeutschland); eine Zeile je Rennen, "
         "Koordinaten aus der Rennseite, Rundenlänge ist keine Distanz.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
