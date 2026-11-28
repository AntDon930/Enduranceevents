#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radsportsh_scraper.py
=====================

Liest die Termine des **Radsportverbands Schleswig-Holstein**
(https://www.radsport-sh.de/termine) und ergänzt die Breitensport-
Veranstaltungen (RTF, CTF, Gravelride) in `events.json` (siehe
`scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
TYPO3-Seite, robots.txt ohne Sperre, Impressum ohne Vorbehalt. Der
einzige deutsche Landesverband neben Hamburg mit frei lesbarer Liste
(siehe README „Landesverbände und Zeitnehmer"); die Liste ist dünn -
Name, Datum und Veranstalterlink.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
`/termine` verlinkt je Termin `/termin/<slug>`. Die Terminseite trägt
`h1` „LTV Almabtrieb (RTF)", „Sparkasse Mittelholstein AG O-CTF in
Westensee (CTF)", „Gravellissimo Waffel Ride (Gravelride)" - das Format
in Klammern -, den Veranstalterlink im Text (`div.news-text-wrap a`,
z. B. ltvkiel-ost.de, nortorf.bike) und das Datum in `.-datum`
(„Samstag, 03.10.2026"). Kein Ort, keine Distanz (außer im Namen:
„… Gravelride 70 km"). Verbandstermine („Fachwartetag") stehen im
selben Kalender. Im September 2026: 8 Termine.

Was daraus wird
---------------
* Fahrrad; Kategorie aus dem Format: RTF → Straße, CTF → Mountainbike,
  Gravelride → Gravel (`ART2_KEYWORDS_FAHRRAD`). Eine Zeile je Termin;
  eine Kilometerzahl im Namen wird die Länge, sonst bleibt sie leer
  (eine RTF hat mehrere Strecken, die die Seite nicht nennt).
* Ort aus dem Namen (`ort_im_text` gegen Schleswig-Holstein und
  Hamburg: „… in Westensee", „RST Lübeck"), sonst aus dem Hostnamen der
  Veranstalterseite (`ltvkiel-ost.de` → Kiel, `nortorf.bike` →
  Nortorf) - dieselbe Regel wie in `veranstalter_links.py`. Ohne Ort kein
  Eintrag („Bungsberg-CTF": ein Berg).
* Termine ohne Format in Klammern (Fachwartetag) fallen weg.
* `veranstalter_url`: der Link im Text; ohne ihn die Terminseite
  (`PORTAL_DOMAINS`).

Nutzung: `python3 scripts/radsportsh_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    guess_art2,
    is_portal_link,
    ort_im_text,
    orte_aus_places,
    parse_flexible_date,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://www.radsport-sh.de"
TERMINE_URL = f"{BASE_URL}/termine"
# Das Format steht in Klammern („LTV Almabtrieb (RTF)") oder im Namen
# („22. RST Lübeck O-CTF", „Bungsberg-CTF"); O-CTF = Orientierungs-CTF.
FORMATE = re.compile(r"\b(?P<format>O-?CTF|CTF|RTF|Gravelride|Gravel|Cyclocross|Radrennen|Zeitfahren)\b", re.I)
_KM = re.compile(r"(\d{2,3})\s*km\b", re.I)


def orte_sh() -> dict:
    orte: dict = {}
    for region in ("Schleswig-Holstein", "Hamburg"):
        for k, v in orte_aus_places("Deutschland", region=region).items():
            orte.setdefault(k, []).extend(v)
    return orte


def parse_termine_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.select("a[href^='/termin/'], a[href*='radsport-sh.de/termin/']"):
        url = urljoin(BASE_URL, a["href"].split("#")[0])
        if url not in links:
            links.append(url)
    return links


def parse_terminseite(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    ergebnis: dict = {}
    h1 = soup.find("h1")
    ergebnis["name"] = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else None
    datum = soup.select_one(".-datum")
    ergebnis["datum"] = parse_flexible_date(datum.get_text(" ", strip=True)) if datum else None
    for a in soup.select("div.news-text-wrap a[href]"):
        href = a["href"].strip()
        if href.startswith("http") and "radsport-sh.de" not in href and not href.startswith("mailto"):
            ergebnis["veranstalter_url"] = href
            break
    return ergebnis


def _umlaute(text: str) -> str:
    return text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def ort_aus_host(url: str | None, orte: dict) -> tuple[str, float | None, float | None] | None:
    """`ltvkiel-ost.de` → Kiel: ein Ortsname ab vier Buchstaben, der im
    Hostnamen steckt (wie `veranstalter_links.host_woerter`)."""
    if not url:
        return None
    host = urlparse(url).netloc.lower().replace("www.", "")
    host = host.rsplit(".", 1)[0].replace("-", "")
    treffer = []
    for name, eintraege in orte.items():
        if len(name) < 4 or len(eintraege) != 1:
            continue
        # „Lübeck" steht im Host als „luebeck" (rst-luebeck.de).
        varianten = {name.replace("-", ""), _umlaute(name.replace("-", ""))}
        if any(v in host for v in varianten):
            treffer.append(eintraege[0])
    if len(treffer) == 1:
        return treffer[0]
    if len(treffer) > 1:
        # Der längste Name gewinnt („Kiel" gegen „Kie…" ist nicht das Problem,
        # „Norderstedt" gegen „Stedt" wäre es).
        treffer.sort(key=lambda t: -len(t[0]))
        if len(treffer[0][0]) > len(treffer[1][0]):
            return treffer[0]
    return None


def event_aus_terminseite(seite: dict, url: str, orte: dict | None = None) -> tuple[Event | None, str | None]:
    name, datum = seite.get("name"), seite.get("datum")
    if not name or not datum:
        return None, "ohne Titel oder Datum"
    m = FORMATE.search(name)
    if not m:
        return None, "kein Radsport-Format im Titel (Verbandstermin?)"
    fmt = m.group("format")
    orte = orte if orte is not None else orte_sh()
    kurz = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    ort = ort_im_text(kurz, orte) or ort_aus_host(seite.get("veranstalter_url"), orte)
    if not ort:
        return None, "kein Ort (weder im Namen noch im Hostnamen)"
    standort, lat, lon = ort
    # „O-CTF und Gravelride 70 km": zwei Formate in einem Namen - die 70 km
    # gehören nur zum Gravelride, die Zeile bleibt ohne Länge.
    km = None
    km_treffer = _KM.findall(name)
    if len(km_treffer) == 1 and len(FORMATE.findall(name)) == 1:
        km = round_km(float(km_treffer[0]))
    ev = Event(land="Deutschland", name=kurz, standort=standort, lat=lat, lon=lon, art1="Fahrrad",
               datum_start=datum, datum_ende=datum, laenge_km=km, wettbewerb=fmt,
               veranstalter_url=seite.get("veranstalter_url") or url)
    ev.art2 = guess_art2(f"{name} {fmt}", CONFIG, "Fahrrad")
    return ev, None


def fetch_radsportsh_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {TERMINE_URL} ...")
    html = fetch_page(session, TERMINE_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    links = parse_termine_links(html)
    print(f"  ✓ {len(links)} Termine.")
    if config.max_details:
        links = links[: config.max_details]
    orte = orte_sh()
    events: list[Event] = []
    for url in links:
        time.sleep(delay)
        seite_html = fetch_page(session, url, render_js=False)
        if not seite_html:
            print(f"   - {url}: nicht abrufbar")
            continue
        ev, grund = event_aus_terminseite(parse_terminseite(seite_html), url, orte)
        if grund:
            print(f"   - {url}: {grund}")
            continue
        print(f"   ✓ {ev.datum_start} {ev.name} ({ev.standort}, {ev.veranstalter_url})")
        events.append(ev)
    print(f"\n→ {len(events)} Termine.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=TERMINE_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_radsportsh_events,
    note="radsportsh_scraper.py: Termine des Radsportverbands Schleswig-Holstein (RTF/CTF/Gravel); "
         "Ort aus Name oder Hostnamen der Veranstalterseite.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
