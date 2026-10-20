#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lck_scraper.py
==============

Liest den **Laufkalender des Läuferclubs Kaltern** (https://www.lck.it/Kalender.php,
Südtirol) und ergänzt die Läufe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben: „Bitte die
Webseiten die du unkritisch siehst gleich auf die Webseite aufnehmen")
---------------------------------------------------------------------
robots.txt sperrt `/admin/`, `/Verein.php` und `/Aktuelles.php` - der
Kalender und sein Fragment `inc_kalender.php` sind frei; Impressum
(Amateur-Sportverein seit 1982) ohne Vorbehalt. Übernommen werden
Termine, Distanzen und der Veranstalterlink, keine Texte.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
`Kalender.php` lädt seinen Inhalt per JavaScript aus
`inc_kalender.php?kategorie=&id=<id>`; die Seitenleiste nennt die
kommenden Läufe mit ihrer `id` (im September 2026: 21). Jedes Fragment
zeigt ein FENSTER von vier Terminen um die id: `h5` Kategorie („Berglauf,
Trail", „VSS - Dorflauf, Kinder- und Jugendlauf"), Stand („ausgetragen"
oder „noch N Tage"), `p` „Sonntag, 27.09.2026", `h2` Name, „Distanz:
15km (230hm)" bzw. „5km - 10km", Beschreibung, Veranstalterlink (`a`).
**Keinen Ort** - er kommt aus dem Namen („Dorflauf Niederdorf") oder aus
der Beschreibung („oberhalb von Jenesien"), geprüft gegen die 750
Südtiroler Orte in `places.json` (Datenregel 4: Südtirol ist die
Provinz Bozen; ein Trentiner Lauf wie der Fiemme Ultra Sky hat keinen
Südtiroler Ort und fällt weg). Der Kalender führt auch Kinder- und
Jugendläufe (Kategorie) - die kommen nicht.

Was daraus wird
---------------
* Laufen, „Italien (Südtirol)", je Distanz eine Zeile (Datenregel 1;
  Höhenmeter in Klammern sind keine Distanz), Kategorie aus der
  Kalender-Kategorie (Berglauf/Trail → Trail, sonst Straße).
* Koordinaten aus `places.json`, kein Nominatim.
* `veranstalter_url`: der Link im Eintrag; ohne ihn der Kalender
  (`PORTAL_DOMAINS`); ein Link auf den VSS-Terminkalender ist ebenfalls
  ein Portal.

Nutzung: `python3 scripts/lck_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    SUEDTIROL,
    Event,
    SiteConfig,
    fetch_page,
    ort_im_text,
    orte_aus_places,
    parse_flexible_date,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://www.lck.it"
KALENDER_URL = f"{BASE_URL}/Kalender.php"
FRAGMENT_URL = f"{BASE_URL}/inc_kalender.php?kategorie=&id={{id}}"
_KM = re.compile(r"(\d+(?:[.,]\d+)?)\s*km\b", re.I)
NACHWUCHS = re.compile(r"kinder|jugend", re.I)


def sidebar_ids(html: str) -> list[int]:
    return sorted({int(x) for x in re.findall(r"\?id=(\d+)&kategorie=", html)})


def parse_fragment(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    eintraege: list[dict] = []
    for h2 in soup.find_all("h2"):
        block = h2.find_parent("div", class_="sm:flex") or h2.parent
        e: dict = {"name": h2.get_text(" ", strip=True)}
        h5 = block.find_previous("h5")
        e["kategorie"] = h5.get_text(" ", strip=True) if h5 else ""
        datum = None
        for p in block.find_all("p"):
            t = p.get_text(" ", strip=True)
            if not datum and re.search(r"\d{2}\.\d{2}\.\d{4}", t):
                datum = parse_flexible_date(t)
            elif t.startswith("Distanz"):
                e["distanz"] = t.split(":", 1)[1].strip()
        e["datum"] = datum
        e["text"] = " ".join(p.get_text(" ", strip=True) for p in block.find_all("p"))
        a = block.find("a", href=True)
        e["url"] = a["href"].strip() if a and a["href"].startswith("http") else None
        eintraege.append(e)
    return eintraege


def distanzen(text: str) -> list[tuple[float, str]]:
    """„15km (230hm)" -> [(15, '15km')], „120km - 80km - 55km" -> drei."""
    text = re.sub(r"\([^)]*\)", "", text or "")
    return [(round_km(float(m.group(1).replace(",", "."))), m.group(0).strip()) for m in _KM.finditer(text)]


def events_aus_eintrag(e: dict, orte: dict | None = None) -> tuple[list[Event], str | None]:
    if not e.get("datum") or not e.get("name"):
        return [], "ohne Datum oder Name"
    if NACHWUCHS.search(e.get("kategorie") or "") and not re.search(r"dorflauf|volkslauf|berglauf|strassenlauf|halbmarathon|marathon", e.get("kategorie") or "", re.I):
        return [], "Kinder- und Jugendlauf"
    orte = orte if orte is not None else orte_aus_places(SUEDTIROL)
    ort = ort_im_text(e["name"], orte)
    if not ort:
        # Der Ort steht oft nur im Text ("oberhalb von Jenesien").
        for m in re.finditer(r"[A-ZÄÖÜ][\wäöüß-]+(?:\s+(?:am|an|im|in)\s+[A-ZÄÖÜ][\wäöüß-]+)?", e.get("text") or ""):
            treffer = orte.get(m.group(0).lower())
            if treffer and len(treffer) == 1:
                ort = treffer[0]
                break
    if not ort:
        return [], "kein Südtiroler Ort"
    standort, lat, lon = ort
    art2 = "Trail" if re.search(r"berglauf|trail|cross", e.get("kategorie") or "", re.I) else "Straße"
    basis = dict(land=SUEDTIROL, name=e["name"], standort=standort, lat=lat, lon=lon, art1="Laufen",
                 datum_start=e["datum"], datum_ende=e["datum"], veranstalter_url=e.get("url") or KALENDER_URL)
    strecken = distanzen(e.get("distanz") or "")
    if not strecken:
        ev = Event(**basis)
        ev.art2 = art2
        return [ev], None
    events = []
    for km, label in strecken:
        ev = Event(**basis, laenge_km=km, wettbewerb=label)
        ev.art2 = art2
        events.append(ev)
    return events, None


def fetch_lck_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {KALENDER_URL} ...")
    html = fetch_page(session, KALENDER_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    ids = sidebar_ids(html)
    print(f"  ✓ {len(ids)} kommende Läufe in der Seitenleiste.")
    if config.max_details:
        ids = ids[: config.max_details]
    orte = orte_aus_places(SUEDTIROL)
    gesehen: set[tuple[str, str]] = set()
    events: list[Event] = []
    gruende: dict[str, int] = {}
    for i in ids:
        time.sleep(delay)
        frag = fetch_page(session, FRAGMENT_URL.format(id=i), render_js=False)
        if not frag:
            continue
        for e in parse_fragment(frag):
            key = (e.get("name") or "", e.get("datum") or "")
            if key in gesehen:
                continue
            gesehen.add(key)
            neue, grund = events_aus_eintrag(e, orte)
            if grund:
                gruende[grund] = gruende.get(grund, 0) + 1
                if grund == "kein Südtiroler Ort":
                    print(f"   - {e.get('datum')} {e.get('name')}: {grund}")
                continue
            events.extend(neue)
    for grund, n in gruende.items():
        print(f"  ({n}× übersprungen: {grund})")
    print(f"\n→ {len(events)} Zeilen aus {len(gesehen)} Terminen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=KALENDER_URL,
    default_art1="Laufen",
    default_land=SUEDTIROL,
    custom_fetch=fetch_lck_events,
    note="lck_scraper.py: Laufkalender des Läuferclubs Kaltern (Südtirol); Ort aus Name oder Text "
         "gegen places.json, Trentiner Läufe fallen weg.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
