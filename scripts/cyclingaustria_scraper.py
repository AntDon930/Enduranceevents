#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cyclingaustria_scraper.py
=========================

Liest den Rennkalender des Österreichischen Radsport-Verbands
(https://www.cyclingaustria.at/kalender?view=events) und ergänzt die
Rennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026)
----------------------------------
Der Nutzer hat die Adresse am 24.09.2026 in seiner Linkliste geschickt
(„Bitte alle checken"). robots.txt ist die Joomla-Voreinstellung (sperrt
nur `/administrator/`, `/api/`, `/cache/` …, nicht `/index.php` und nicht
`/kalender`); das Impressum (Österreichischer Radsport-Verband, Wien)
nennt nur den Bildnachweis, kein Verbot des Auslesens, AGB gibt es nicht.

Struktur (am 24.09.2026 kalibriert)
-----------------------------------
* Die Liste (`/kalender?view=events&page=N`, ~20 Karten je Seite, im
  September 2026 vier Seiten mit 72 Rennen bis September 2027) hat je
  Rennen ein `<div data-disziplin="…" data-date="YYYY-MM-DD">` mit dem
  Link `/index.php?option=com_events&view=event&id=<32 Hex>`. Eine Seite
  jenseits der letzten liefert wieder die erste Karte - gelesen wird,
  bis keine neue Kennung mehr kommt.
* Die **Rennseite** nennt „Start/Ziel" (PLZ + Ort), „Datum" („Sa, 21.
  November 2026–So, 22. November 2026" bei zwei Tagen), „Sparte"
  (Straße, MTB, Cyclocross, Bahn …), „Disziplin", je Wettbewerb einen
  Block „Rennen N" mit Klassen, Disziplin, Distanz (km) oder Renndauer
  (H:min) und den Veranstalter mit dem Knopf „zur Website" (Datenregel 2;
  ein fehlender Link steht dort als `https://-`). Die Nennung läuft über
  raceresult - ein Portallink, wird nicht übernommen.

Was daraus wird
---------------
* **Alle Klassen, auch Lizenzrennen** - dieselbe Entscheidung des Nutzers
  wie bei BRV Timing (24.09.2026: „Bitte auch die mit BDR Lizenz
  aufnehmen"). Der ÖRV-Kalender ist ohnehin fast nur Lizenzsport;
  „Cycling 4 All" und „Touristik" sind die Jedermann-Formate.
* **Nicht übernommen** (`NICHT_AUSDAUER_DISZIPLIN`): Kunstrad und Radball
  (kein Rennen), Downhill, Enduro, E-MTB und Technikparcours
  (Fahrtechnik, kein Ausdauer-Format), Madison und Mannschaftszeitfahren
  (Teams - Datenregel 16), Kinderrennen („Unlizenziert Kinder", Klassen
  nur bis U17 - `_nur_nachwuchs` - oder „Kids"/„Youngster"/„Nachwuchs" im
  Namen, `NACHWUCHS_IM_NAMEN`). Umkehrbar über die Listen; jeder
  Ausschluss wird gemeldet.
* Je verschiedener Distanz bzw. Renndauer der übrigen „Rennen N" EIN
  Eintrag (Datenregel 1), Label = Disziplin + Maß („Cyclocross 40 min",
  „Einzelzeitfahren 47,2 km"). Ein Cyclocross ohne Kilometerangabe ist
  ein Zeitrennen über 40 Minuten (`dauer_h`, Datenregel 8). Ohne
  „Rennen"-Blöcke (viele 2027er Termine sind noch nicht ausgeschrieben)
  bleibt eine Zeile ohne Maß mit der Disziplin als Label.
* `art2` aus Sparte und Disziplin über `ART2_KEYWORDS_FAHRRAD`; ohne
  Treffer entscheidet die Sparte (`SPARTE_ART2`).
* Ort = „Start/Ziel" ohne PLZ (`ort_aus_veranstaltungsort`), Land
  Österreich (österreichische Postleitzahl), Koordinaten holt der
  Geocoder des Laufs.

Nutzung: `python3 scripts/cyclingaustria_scraper.py --help`
(Testlauf: `--dry-run --max-details 5`).
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
    ort_aus_veranstaltungsort,
    parse_flexible_date,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://www.cyclingaustria.at"
LISTE_URL = f"{BASE_URL}/kalender?view=events"
MAX_SEITEN = 30

# Disziplinen, die kein Ausdauer-Rennen sind (Begründung im Modul-Kopf).
NICHT_AUSDAUER_DISZIPLIN = re.compile(
    r"kunstrad|radball|downhill|enduro|e-?mtb|technikparcours|madison|"
    r"mannschaftszeitfahren|kinder", re.I)
# Klassen, die nur Nachwuchs bezeichnen - ein Rennen, das NUR aus ihnen
# besteht, ist ein Kinder-/Jugendrennen.
_NACHWUCHS = re.compile(r"\bu\s?(?:7|9|11|13|15|17)\b|jugend|schüler|kinder|kids", re.I)
# "Youngster Grand Prix", "Kids Bike Trophy", "Nachwuchsenduro": ein Rennen,
# das sich schon im Namen an den Nachwuchs richtet (Rennen-Blöcke fehlen
# bei vielen 2027er Terminen noch, die Klassen wären sonst der Beleg).
NACHWUCHS_IM_NAMEN = re.compile(r"kids|nachwuchs|youngster|kinder|jugend|schüler", re.I)
SPARTE_ART2 = {"straße": "Straße", "strasse": "Straße", "mtb": "Mountainbike",
               "cyclocross": "Cyclecross", "bahn": "Bahn", "gravel": "Gravel"}
_KEIN_LINK = re.compile(r"^https?://-?/?$")


def parse_liste(html: str) -> list[dict]:
    """Die Karten einer Listenseite: [{id, url, name, datum, disziplin}, …]."""
    soup = BeautifulSoup(html, "html.parser")
    karten = []
    for div in soup.select("div[data-disziplin]"):
        a = div.select_one("a[href*='view=event']")
        if not a:
            continue
        m = re.search(r"id=([0-9A-Fa-f]{32})", a.get("href", ""))
        if not m:
            continue
        titel = div.select_one("h3")
        karten.append({
            "id": m.group(1).upper(),
            "url": urljoin(BASE_URL, a["href"].replace("&amp;", "&")),
            "name": titel.get_text(" ", strip=True) if titel else None,
            "datum": div.get("data-date"),
            "disziplin": div.get("data-disziplin", ""),
        })
    return karten


def _wert(soup, label: str) -> str | None:
    for h in soup.select("h2.uk-h5, h3.uk-h5"):
        if h.get_text(" ", strip=True).rstrip(":") == label:
            nxt = h.find_next_sibling("div")
            return nxt.get_text(" ", strip=True) if nxt else None
    return None


def parse_rennseite(html: str) -> dict:
    """Name, Ort, Datum (Start/Ende), Sparte, Disziplin, Veranstalterlink
    und die Blöcke „Rennen N" (Klassen, Disziplin, Distanz, Renndauer)."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("h1")
    datum_text = _wert(soup, "Datum") or ""
    teile = re.split(r"\s*[–-]\s*(?=[A-Za-z]{2},)", datum_text)
    datum_start = parse_flexible_date(teile[0]) if teile else None
    datum_ende = parse_flexible_date(teile[-1]) if len(teile) > 1 else datum_start
    rennen = []
    for kopf in soup.select("div.uk-heading-small"):
        if not kopf.get_text(strip=True).startswith("Rennen"):
            continue
        karte = kopf.find_parent("div", class_="uk-card")
        if karte is None:
            continue
        klassen = karte.select_one("h2.uk-h3")
        r = {"klassen": klassen.get_text(" ", strip=True) if klassen else ""}
        for h in karte.select("h3.uk-h5"):
            nxt = h.find_next_sibling("div")
            r[h.get_text(" ", strip=True).rstrip(":")] = nxt.get_text(" ", strip=True) if nxt else None
        rennen.append(r)
    web = None
    for a in soup.select("a.uk-button"):
        if "zur Website" in a.get_text():
            href = (a.get("href") or "").strip()
            host = urlparse(href).netloc.lower()
            if href and not _KEIN_LINK.match(href) and "." in host and "cyclingaustria.at" not in host:
                web = href
            break
    return {
        "name": h1.get_text(" ", strip=True) if h1 else None,
        "ort": _wert(soup, "Start/Ziel"),
        "datum_start": datum_start, "datum_ende": datum_ende,
        "sparte": _wert(soup, "Sparte"), "disziplin": _wert(soup, "Disziplin") or "",
        "veranstalter_url": web, "rennen": rennen,
    }


def _nur_nachwuchs(klassen: str) -> bool:
    teile = [k.strip() for k in re.split(r",", klassen or "") if k.strip()]
    return bool(teile) and all(_NACHWUCHS.search(k) for k in teile)


def _mass(r: dict) -> tuple[float | None, float | None]:
    """(km, Stunden) eines Rennen-Blocks."""
    mk = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*km", r.get("Distanz") or "", re.I)
    if mk:
        km = round_km(float(mk.group(1).replace(",", ".")))
        if km:
            return km, None
    md = re.search(r"(\d{1,2}):(\d{2})", r.get("Renndauer") or "")
    if md:
        h = int(md.group(1)) + int(md.group(2)) / 60
        if h > 0:
            return None, round(h, 2)
    return None, None


def events_aus_rennseite(seite: dict, url: str, karte: dict | None,
                         config: SiteConfig) -> tuple[list[Event], str | None]:
    """Ein Event je Maß der zugelassenen Rennen - oder ([], Grund)."""
    name = seite.get("name") or (karte or {}).get("name")
    datum = seite.get("datum_start") or (karte or {}).get("datum")
    if not name or not datum:
        return [], "kein Name/Datum"
    # "4171 Sankt Peter am Wimberg": die PLZ vorher weg, sonst bleibt nur "Sankt".
    ort = ort_aus_veranstaltungsort(re.sub(r"^\s*\d{4,5}\s+", "", seite.get("ort") or ""))
    if not ort:
        return [], "kein Start/Ziel"
    if NACHWUCHS_IM_NAMEN.search(name):
        return [], "Nachwuchsrennen (laut Name)"
    disziplin = seite.get("disziplin") or (karte or {}).get("disziplin") or ""
    zugelassen = [d.strip() for d in disziplin.split(",") if d.strip() and not NICHT_AUSDAUER_DISZIPLIN.search(d)]
    if disziplin and not zugelassen:
        return [], f"Disziplin nicht übernommen ({disziplin})"
    sparte = (seite.get("sparte") or "").strip()
    veranstalter = seite.get("veranstalter_url") or url
    basis = dict(land="Österreich", name=name, standort=ort, art1="Fahrrad",
                 datum_start=datum, datum_ende=seite.get("datum_ende") or datum,
                 veranstalter_url=veranstalter)

    def kategorie(text: str) -> str | None:
        # Erst die Disziplin des Rennens (ein Einzelzeitfahren beim Radquer-
        # feldein-Tag ist Zeitfahren), dann Sparte und Name, zuletzt die Sparte.
        return (guess_art2(text, config, "Fahrrad") or guess_art2(f"{sparte} {name}", config, "Fahrrad")
                or SPARTE_ART2.get(sparte.lower()))

    events: list[Event] = []
    gesehen: set = set()
    for r in seite.get("rennen") or []:
        rd = (r.get("Disziplin") or "").strip()
        if NICHT_AUSDAUER_DISZIPLIN.search(rd) or _nur_nachwuchs(r.get("klassen", "")):
            continue
        km, stunden = _mass(r)
        schluessel = (km, stunden)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        label = rd or zugelassen[0] if zugelassen else rd
        if km:
            label = f"{label} {km:g} km".strip()
        elif stunden:
            label = f"{label} {round(stunden * 60):d} min".strip()
        ev = Event(**basis, laenge_km=km, dauer_h=stunden, wettbewerb=label or None)
        ev.art2 = kategorie(rd)
        events.append(ev)
    if not events:
        if seite.get("rennen"):
            return [], "nur Nachwuchs- oder ausgeschlossene Rennen"
        ev = Event(**basis, wettbewerb=", ".join(zugelassen) or None)
        ev.art2 = kategorie(disziplin)
        events.append(ev)
    return events, None


def fetch_cyclingaustria_events(session, config, delay, max_pages, render_js) -> list[Event]:
    karten: list[dict] = []
    gesehen: set = set()
    seiten = 0
    for seite in range(1, MAX_SEITEN + 1):
        if max_pages and seite > max_pages:
            break
        url = LISTE_URL if seite == 1 else f"{LISTE_URL}&page={seite}"
        print(f"→ Lade {url} ...")
        html = fetch_page(session, url, render_js=False)
        if not html:
            break
        neue = [k for k in parse_liste(html) if k["id"] not in gesehen]
        if not neue:
            break
        seiten += 1
        for k in neue:
            gesehen.add(k["id"])
            karten.append(k)
        time.sleep(delay)
    print(f"  ✓ {len(karten)} Rennen auf {seiten} Listenseite(n).")
    events: list[Event] = []
    uebersprungen: list[str] = []
    for i, k in enumerate(karten):
        if config.max_details and i >= config.max_details:
            break
        time.sleep(delay)
        html = fetch_page(session, k["url"], render_js=False)
        if not html:
            uebersprungen.append(f"{k['name']}: Rennseite nicht abrufbar")
            continue
        seite = parse_rennseite(html)
        neue, grund = events_aus_rennseite(seite, k["url"], k, config)
        if grund:
            uebersprungen.append(f"{seite.get('name') or k['name']} ({k['datum']}): {grund}")
        events.extend(neue)
    if uebersprungen:
        print(f"\n  Übersprungen ({len(uebersprungen)}):")
        for zeile in uebersprungen:
            print(f"   - {zeile}")
    mit_link = sum(1 for e in events if "cyclingaustria.at" not in (e.veranstalter_url or ""))
    print(f"\n→ {len(events)} Wettbewerbe aus {len(karten)} Rennen, {mit_link} mit Veranstalterseite.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Fahrrad",
    default_land="Österreich",
    custom_fetch=fetch_cyclingaustria_events,
    note="cyclingaustria_scraper.py: ÖRV-Rennkalender; Listenseiten -> Rennseite mit "
         "Start/Ziel, Datum, Sparte, Rennen-Blöcken und Veranstalterlink. Alle Klassen, "
         "auch Lizenz (Entscheidung des Nutzers 24.09.2026); kein Kunstrad/Radball/"
         "Downhill/Enduro/Kinder/Teamzeitfahren.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
