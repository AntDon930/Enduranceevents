#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nws_scraper.py
==============

Liest den Laufkalender Nordwestschweiz und Region
(https://www.laufkalender-nws.ch) und ergänzt die Läufe in
`events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 22.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
robots.txt sperrt `/app/` und `/j/` und verlangt `Crawl-delay: 5` -
das Skript hält die fünf Sekunden über `check_robots()` ein. Die Seite
"über NWS" nennt kein Verbot des Auslesens; Betreiber ist die
Interessengemeinschaft der Laufveranstalter selbst.

Struktur (am 22.09.2026 kalibriert, Jimdo-Seite)
-------------------------------------------------
Zwei Listenseiten (Herbst/Winter = Startseite, Frühjahr/Sommer), je
Lauf ein Block mit `<h3>` und einem Link `/nws/<slug>/` ("weitere
Infos"). Die **Detailseite** trägt

* den Titel (`<h1>`/`<h2>`, meist in GROSSBUCHSTABEN - wird auf
  Wortanfang-Groß gebracht, "20. BELCHEN-BERGLAUF" -> "20. Belchen-Berglauf"),
* die Zeile "19. September 2026 – D-Schönau": Datum und Ort. "D-" =
  Deutschland, "F-" = Frankreich (fällt heraus), sonst Schweiz; ein
  angehängtes Kantonskürzel ("Liestal BL") wird abgeschnitten;
* die Tabelle Kategorie | Distanz | Team-Wertung ("Lauf | 11,4 km /
  824 Hm") - je Zeile ein Wettbewerb (`expand_competitions`);
* unter "Organisation" den Veranstalter mit Link auf seine Seite -
  die `veranstalter_url` (Datenregel 2). Ohne Link bleibt die
  NWS-Seite als Portallink (PORTAL_DOMAINS).

Nutzung: `python3 scripts/nws_scraper.py --help`
(Testlauf: `--dry-run --max-details 3`).
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
    expand_competitions,
    fetch_page,
    guess_art2,
    guess_distance_km,
    is_portal_link,
    parse_competitions,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://www.laufkalender-nws.ch"
LISTEN = [
    f"{BASE_URL}/",
    f"{BASE_URL}/fr%C3%BChjahr-i-sommer-l%C3%A4ufe/",
]

_DATUM_ORT = re.compile(r"(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+\s+\d{4})\s*[–-]\s*(.+)$")
_KANTON_SUFFIX = re.compile(r"\s+(?:AG|AI|AR|BE|BL|BS|FR|GE|GL|GR|JU|LU|NE|NW|OW|SG|SH|SO|SZ|TG|TI|UR|VD|VS|ZG|ZH)$")


def schoener_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name or "").strip()
    if name and name.upper() == name:
        name = "-".join(t.capitalize() for t in name.split("-"))
        name = " ".join(w if w[:1].isdigit() else w[:1].upper() + w[1:] for w in name.split(" "))
    return name


def parse_ort(text: str) -> tuple[str | None, str | None]:
    """"D-Schönau" -> ("Schönau", "Deutschland"); "Liestal BL" ->
    ("Liestal", "Schweiz"); "Basel (Staffellauf)" -> ("Basel", "Schweiz")."""
    text = re.sub(r"\s*\([^)]*\)\s*$", "", (text or "").strip())
    land = "Schweiz"
    m = re.match(r"^([A-Z]{1,2})-(.+)$", text)
    if m:
        land = {"D": "Deutschland", "A": "Österreich", "CH": "Schweiz", "F": "Frankreich",
                "I": "Italien"}.get(m.group(1), m.group(1))
        text = m.group(2)
    text = _KANTON_SUFFIX.sub("", text).strip()
    return (text or None), land


def parse_liste(soup: BeautifulSoup) -> list[str]:
    links = []
    for a in soup.select("a[href^='/nws/']"):
        url = urljoin(BASE_URL, a["href"].split("#")[0])
        if url not in links:
            links.append(url)
    return links


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}
    titel = soup.select_one("h1") or soup.select_one("h2")
    result["name"] = schoener_name(titel.get_text(" ", strip=True)) if titel else None
    # Die Zeile "19. September 2026 – D-Schönau" steht als Beschreibung
    # in den Meta-Angaben (og:description) - sauber abgegrenzt, anders als
    # im Fließtext, wo die Beschreibung des Laufs direkt anschließt.
    meta = soup.find("meta", attrs={"property": "og:description"}) \
        or soup.find("meta", attrs={"name": "twitter:description"})
    m = _DATUM_ORT.search(re.sub(r"\s+", " ", meta.get("content", "")) if meta else "")
    if m:
        result["datum"] = parse_flexible_date(m.group(1))
        result["ort"], result["land"] = parse_ort(m.group(2).strip())
    strecken = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        kopf = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])] if rows else []
        if not kopf or not kopf[0].startswith("Kategorie"):
            continue
        for tr in rows[1:]:
            zellen = [c.get_text(" ", strip=True).replace("\xa0", " ") for c in tr.find_all(["th", "td"])]
            if len(zellen) < 2 or not zellen[1]:
                continue
            # "5,6 km / 10,0 km" sind ZWEI Strecken (Muttenzer Herbstlauf),
            # "11,4 km / 824 Hm" ist EINE mit Höhenmetern - geteilt wird
            # nur, wenn mehr als ein Teil eine km-Angabe trägt.
            teile = [t.strip() for t in zellen[1].split("/")]
            km_teile = [t for t in teile if re.search(r"\d\s*km\b", t, re.I)]
            if len(km_teile) > 1:
                for t in km_teile:
                    strecken.append(f"{zellen[0]} {t}".strip())
            else:
                strecken.append(f"{zellen[0]} {zellen[1]}".strip())
    if strecken:
        result["strecken"] = strecken
    org = soup.find(["h2", "h3"], string=re.compile(r"^\s*Organisation\s*$"))
    if org:
        block = org.find_parent("div")
        block = block.find_next_sibling("div") if block else None
        kandidaten = []
        for a in (block.select("a[href^='http']") if block else []):
            href = a["href"]
            if "jimdo" in href or "facebook" in href or is_portal_link(href):
                continue
            kandidaten.append((bool(a.get_text(strip=True)), href))
        if kandidaten:
            kandidaten.sort(key=lambda k: not k[0])
            result["official_url"] = kandidaten[0][1]
    return result


def fetch_nws_events(session, config, delay, max_pages, render_js) -> list[Event]:
    links: list[str] = []
    for url in LISTEN:
        print(f"→ Lade {url} ...")
        html = fetch_page(session, url, render_js)
        if html is None:
            continue
        for link in parse_liste(BeautifulSoup(html, "html.parser")):
            if link not in links:
                links.append(link)
        time.sleep(delay)
    print(f"  ✓ {len(links)} Lauf-Seite(n).")
    events: list[Event] = []
    details = official = 0
    for url in links:
        if config.max_details and details >= config.max_details:
            break
        html = fetch_page(session, url, False)
        details += 1
        time.sleep(delay)
        d = parse_detail(html) if html else {}
        if not d.get("name") or not d.get("datum"):
            continue
        ev = Event(land=d.get("land"), name=d["name"], standort=d.get("ort"), art1="Laufen",
                   datum_start=d["datum"], datum_ende=d["datum"],
                   veranstalter_url=d.get("official_url") or url)
        if d.get("official_url"):
            official += 1
        # Ohne Strecken-Tabelle bleibt, was der Name sagt ("Muttenz Marathon").
        ev.laenge_km = guess_distance_km(ev.name, config)
        ev.art2 = guess_art2(ev.name, config, ev.art1)
        events.extend(expand_competitions(ev, parse_competitions(d.get("strecken") or [], config), config))
    print(f"\n→ {details} Detailseite(n), davon {official} mit Veranstalterseite; {len(events)} Einträge.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTEN[0],
    default_art1="Laufen",
    default_land="Schweiz",
    custom_fetch=fetch_nws_events,
    note="nws_scraper.py: Laufkalender Nordwestschweiz, robots.txt erlaubt "
         "(Crawl-delay 5 s); zwei Listen, Detailseite mit Strecken-Tabelle "
         "und Organisation-Link.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
