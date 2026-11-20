#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swimsports_scraper.py
=====================

Liest den Schwimmkalender von swimsports.ch (Verband der Schweizer
Schwimmschulen, https://www.swimsports.ch/schwimmkalender) und ergänzt
die Freiwasser-Anlässe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026)
----------------------------------
Vom Nutzer am 24.09.2026 in seiner Linkliste geschickt („Bitte alle
checken"). robots.txt ist die Drupal-Voreinstellung (sperrt `/admin/`,
`/user/` usw., nicht `/node/` und nicht `/schwimmkalender`); Impressum
und Datenschutz nennen kein Verbot des Auslesens. Die Adresse mit
Sprachpräfix (`/de/schwimmkalender`) antwortet „Zugriff verweigert" -
das ist kein Bot-Schutz, nur der falsche Pfad; die Adresse des Nutzers
ohne Präfix liefert die Liste.

Struktur (am 24.09.2026 kalibriert)
-----------------------------------
* Die Liste hat je Anlass ein `<article class="swimming-calendar">` mit
  Link `/node/<nr>`, `<time datetime>` und dem Ort
  (`field--name-field-calendar-location`: „Beinwil am See", „Zürich,
  Strandbad Mythenquai", „Greppen/LU"). Keine weiteren Seiten; im
  September 2026 33 Anlässe, fast alle 2026 (die Saison 2027 kommt im
  Frühjahr), dazu ein Termin 2027 (Rhyschwümme 08.08.2027).
* Die **Detailseite** (`/node/<nr>`) nennt Distanz („2 km", „1.8 Km",
  „Ca. 11 km", „Schwimmen 1.1 km/SUP Fun 1.5 km/…", „Libre"), Gewässer,
  Start, Ziel, Organisation/Kontakt und die Homepage des Anlasses
  (Datenregel 2). Ohne Homepage bleibt die swimsports-Seite als
  Portallink stehen (`PORTAL_DOMAINS`).

Was daraus wird
---------------
* Je verschiedener Distanz EIN Eintrag (Datenregel 1); SUP-Angaben
  (Stand-up-Paddling) zählen nicht - „Schwimmen 1.1 km/SUP Fun 1.5 km"
  ergibt 1,1 km, nicht 8. Ohne Zahl („Libre") bleibt die Zeile ohne
  Maß. Die 500-m-Grenze (Datenregel 5) greift danach von selbst
  (Samichlaus-Schwimmen: 111 m).
* Ein Anlass, dessen Name „Abgesagt" trägt, fällt weg (Datenregel 18) -
  außer der Name nennt den eigenen Termin als „nächstes Schwimmen"
  („Rhyschwümme 2026 - Abgesagt - Das nächste Schwimmen findet am
  08.08.2027 statt", Eintrag am 08.08.2027): dann bleibt der Name vor
  dem ersten Gedankenstrich.
* Alles ist Freiwasser (See, Fluss, Kanal) - `art2` „Freiwasser", außer
  `ART2_KEYWORDS_SCHWIMMEN` erkennt ein Becken.
* Ort = erster Teil der Ortsangabe (`ort_aus_veranstaltungsort`, ohne
  Kantonskürzel), Land Schweiz; Koordinaten holt der Geocoder des Laufs.

Nutzung: `python3 scripts/swimsports_scraper.py --help`
(Testlauf: `--dry-run --max-details 3`).
"""

from pathlib import Path
import re
import sys
import time
from datetime import date
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    guess_art2,
    ort_aus_veranstaltungsort,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://www.swimsports.ch"
LISTE_URL = f"{BASE_URL}/schwimmkalender"
_KANTON = re.compile(r"\s*[/ ]\s*(?:AG|AI|AR|BE|BL|BS|FR|GE|GL|GR|JU|LU|NE|NW|OW|SG|SH|SO|SZ|TG|TI|UR|VD|VS|ZG|ZH)$")


def parse_liste(html: str) -> list[dict]:
    """[{url, name, datum, ort}, …] - nur Einträge mit Datum."""
    soup = BeautifulSoup(html, "html.parser")
    eintraege = []
    for art in soup.select("article.swimming-calendar"):
        a = art.select_one("a[href^='/node/']")
        t = art.select_one("time[datetime]")
        if not a or not t:
            continue
        loc = art.select_one(".field--name-field-calendar-location")
        eintraege.append({
            "url": urljoin(BASE_URL, a["href"]),
            "name": a.get_text(" ", strip=True),
            "datum": t["datetime"][:10],
            "ort": loc.get_text(" ", strip=True) if loc else None,
        })
    return eintraege


def _feld(soup, name: str) -> str | None:
    el = soup.select_one(f".field--name-field-{name} .field--item") or soup.select_one(f".field--name-field-{name}")
    if el is None:
        return None
    a = el.select_one("a[href]")
    if name == "home-page" and a:
        return a["href"].strip()
    return el.get_text(" ", strip=True) or None


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    homepage = _feld(soup, "home-page")
    if homepage and not homepage.lower().startswith("http"):
        homepage = "https://" + homepage
    return {
        "distanz": _feld(soup, "distance"),
        "gewaesser": _feld(soup, "water"),
        "ort": _feld(soup, "calendar-location"),
        "organisation": _feld(soup, "organization-contact"),
        "homepage": homepage,
    }


def distanzen_aus_text(text: str | None) -> list[float]:
    """Alle Schwimmdistanzen einer Distanz-Angabe in km, ohne SUP-Teile."""
    km_liste: list[float] = []
    for teil in re.split(r"[/;]|\bund\b|\boder\b", text or ""):
        if re.search(r"\bsup\b|paddel|paddle", teil, re.I):
            continue
        for m in re.finditer(r"(\d{1,2}[.,'’]\d{3}|\d{1,5}(?:[.,]\d+)?)\s*(km|m\b|meter)", teil, re.I):
            zahl_text, einheit = m.group(1), m.group(2).lower()
            if einheit != "km" and re.fullmatch(r"\d{1,2}[.,'’]\d{3}", zahl_text):
                zahl = float(re.sub(r"[.,'’]", "", zahl_text))  # 1'500 m, 1.500 m
            else:
                zahl = float(zahl_text.replace("'", "").replace("’", "").replace(",", "."))
            km = zahl if einheit == "km" else zahl / 1000
            km = round_km(km) if km >= 1 else round(km, 2)
            if km and km not in km_liste:
                km_liste.append(km)
    return km_liste


def bereinige_name(name: str, datum: str) -> str | None:
    """None, wenn der Anlass abgesagt ist; sonst der Name ohne Zusatz."""
    if re.search(r"abgesagt|annul[ée]|cancel", name, re.I):
        tag = date.fromisoformat(datum).strftime("%d.%m.%Y")
        if tag not in name:
            return None
        return re.split(r"\s+[-–]\s+", name)[0].strip() or None
    return name.strip()


def events_aus_eintrag(eintrag: dict, detail: dict, config: SiteConfig) -> tuple[list[Event], str | None]:
    name = bereinige_name(eintrag["name"], eintrag["datum"])
    if not name:
        return [], "abgesagt"
    ort_text = detail.get("ort") or eintrag.get("ort")
    ort = ort_aus_veranstaltungsort(_KANTON.sub("", ort_text or ""))
    if not ort:
        return [], "kein Ort"
    text = f"{name} {detail.get('gewaesser') or ''} {detail.get('distanz') or ''}"
    basis = dict(land="Schweiz", name=name, standort=ort, art1="Schwimmen",
                 datum_start=eintrag["datum"], datum_ende=eintrag["datum"],
                 veranstalter_url=detail.get("homepage") or eintrag["url"])
    art2 = guess_art2(text, config, "Schwimmen") or "Freiwasser"
    distanzen = distanzen_aus_text(detail.get("distanz"))
    if not distanzen:
        ev = Event(**basis)
        ev.art2 = art2
        return [ev], None
    events = []
    for km in distanzen:
        ev = Event(**basis, laenge_km=km, wettbewerb=f"{km:g} km" if len(distanzen) > 1 else None)
        ev.art2 = art2
        events.append(ev)
    return events, None


def fetch_swimsports_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, render_js=False)
    if not html:
        print("  ⚠ Liste nicht abrufbar.")
        return []
    liste = parse_liste(html)
    heute = date.today().isoformat()
    kommend = [e for e in liste if e["datum"] >= heute]
    print(f"  ✓ {len(liste)} Anlässe in der Liste, {len(kommend)} ab heute.")
    events: list[Event] = []
    uebersprungen: list[str] = []
    for i, e in enumerate(kommend):
        if config.max_details and i >= config.max_details:
            break
        time.sleep(delay)
        detail_html = fetch_page(session, e["url"], render_js=False)
        if not detail_html:
            uebersprungen.append(f"{e['name']}: Detailseite nicht abrufbar")
            continue
        neue, grund = events_aus_eintrag(e, parse_detail(detail_html), config)
        if grund:
            uebersprungen.append(f"{e['name']} ({e['datum']}): {grund}")
        events.extend(neue)
    if uebersprungen:
        print(f"\n  Übersprungen ({len(uebersprungen)}):")
        for zeile in uebersprungen:
            print(f"   - {zeile}")
    print(f"\n→ {len(events)} Strecken aus {len(kommend)} kommenden Anlässen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Schwimmen",
    default_land="Schweiz",
    custom_fetch=fetch_swimsports_events,
    note="swimsports_scraper.py: Schwimmkalender Schweiz (Freiwasser); Liste -> "
         "Detailseite mit Distanz, Gewässer und Homepage. Adresse ohne /de/ - "
         "mit Sprachpräfix antwortet die Seite 'Zugriff verweigert'.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
