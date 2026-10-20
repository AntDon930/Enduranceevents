#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oelv_scraper.py
===============

Liest den Laufkalender des Österreichischen Leichtathletik-Verbands
(ÖLV) und ergänzt die Läufe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 22.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
Der Kalender auf oelv.at (`/de/sport/laufkalender`) verweist auf die
Verbandsanwendung **https://oelv.athmin.at/events.aspx**. Deren
robots.txt gibt 404 (= keine Einschränkung, RFC 9309); das Impressum
von oelv.at nennt kein Verbot des Auslesens. Der Verband bittet die
Veranstalter selbst um den Eintrag ("Laufveranstaltung anmelden").

Struktur (am 22.09.2026 kalibriert)
-----------------------------------
ASP.NET-WebForms: Die Filter und die Seitenblätterung laufen über
POST-Postbacks mit `__VIEWSTATE`/`__EVENTVALIDATION`. Das Skript

1. lädt `events.aspx` (GET),
2. schickt das Formular mit `drpRunType = -2` ("Alle Läufe" - ohne
   Stadionmeetings), `drpEventStatus = -2` ("Standard", also ohne
   abgesagte/verschobene, Datenregel 18) und `drpRecords = 50` ab
   (`btnFilter`),
3. blättert mit `btnNext`, bis der Knopf `disabled` ist (der Kalender
   hatte am 22.09.2026 179 Einträge inkl. Stadion, "Seite 1 / 9").

Jede Zeile: Datum, Name, Verein, Ort ("Ebreichsdorf", "OÖ - 4020 Linz,
PHDL Linz (…)", "Wien - Hauptallee …", international "Ames (ESP)"), und
`event-details.aspx?event=<id>`. Die **Detailseite** liefert

* **Homepage** (`#main_lblHomepage` + Link) = die Veranstalterseite,
  ersatzweise den Link "Ausschreibung", wenn er keine PDF ist;
* die **Bewerbe** (Tabelle, Spalte "Bewerb": "10km Straßenlauf",
  "Halbmarathon", "Berglauf 12 km"), je einer ein Eintrag
  (`expand_competitions`); nur Bewerbe mit erkennbarer Distanz zählen,
  Altersklassen-Doppelungen (AK - M / AK - W) fallen über die Distanz
  zusammen.

Land: Österreich, außer der Ort trägt ein Länderkürzel in Klammern
((GER), (SUI), (ITA) -> Deutschland/Schweiz/Italien, alles andere
fällt über filter_dach() heraus).

Nutzung: `python3 scripts/oelv_scraper.py --help`
(Testlauf: `--dry-run --max-pages 1 --max-details 3`).
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
    ort_aus_veranstaltungsort,
    parse_competitions,
    parse_duration_h,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://oelv.athmin.at"
LISTE_URL = f"{BASE_URL}/events.aspx"

FILTER = {
    "ctl00$main$drpRunType": "-2",       # Alle Läufe (kein Stadion)
    "ctl00$main$drpEventStatus": "-2",   # Standard (nicht abgesagt/verschoben)
    "ctl00$main$drpRecords": "50",
}

LAND_KUERZEL = {"GER": "Deutschland", "AUT": "Österreich", "SUI": "Schweiz", "ITA": "Italien"}
_LAND_IN_KLAMMERN = re.compile(r"\(([A-Z]{3})\)\s*$")


def formularfelder(soup: BeautifulSoup) -> dict:
    """Alle Felder des Formulars mit ihren aktuellen Werten (ViewState,
    Selects, Textfelder) - so, wie ein Browser sie zurückschicken würde."""
    felder: dict[str, str] = {}
    form = soup.find("form")
    if not form:
        return felder
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name or inp.get("type") in ("submit", "button"):
            continue
        if inp.get("type") in ("checkbox", "radio") and not inp.has_attr("checked"):
            continue
        felder[name] = inp.get("value") or ""
    for sel in form.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        felder[name] = opt.get("value", "") if opt else ""
    return felder


def parse_ort(text: str) -> tuple[str | None, str]:
    """"OÖ - 4020 Linz, PHDL Linz (…)" -> ("Linz", "Österreich");
    "Wien - Prater" -> ("Wien", …); "Ames (ESP)" -> ("Ames", "ESP" ->
    unbekanntes Land, fällt über filter_dach heraus). Das Herausschälen
    des Ortes macht scraper_lib.ort_aus_veranstaltungsort()."""
    text = re.sub(r"\s+", " ", text or "").strip()
    land = "Österreich"
    m = _LAND_IN_KLAMMERN.search(text)
    if m:
        land = LAND_KUERZEL.get(m.group(1), m.group(1))
        text = text[:m.start()].strip()
    return ort_aus_veranstaltungsort(text), land


def parse_liste(soup: BeautifulSoup) -> tuple[list[dict], bool]:
    """Zeilen der Liste und ob es eine nächste Seite gibt."""
    zeilen = []
    for tr in soup.select("table tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        link = tr.select_one("a[href*='event-details.aspx']")
        if not link:
            continue
        name_td = tds[1]
        for icon in name_td.find_all("span"):
            icon.decompose()
        zeilen.append({
            "datum": tds[0].get_text(" ", strip=True),
            "name": re.sub(r"\s+", " ", name_td.get_text(" ", strip=True)),
            "verein": tds[2].get_text(" ", strip=True),
            "ort": tds[3].get_text(" ", strip=True),
            "url": urljoin(BASE_URL, link["href"]),
        })
    weiter = soup.find("button", attrs={"name": "ctl00$main$btnNext"})
    hat_naechste = bool(weiter) and not weiter.has_attr("disabled")
    return zeilen, hat_naechste


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}
    hp = soup.select_one("#main_lblHomepage")
    link = hp.find_next("a", href=True) if hp else None
    if link and link["href"].startswith("http"):
        result["official_url"] = link["href"]
    if "official_url" not in result:
        for a in soup.find_all("a", href=True):
            if "Ausschreibung" in a.get_text(" ", strip=True) and a["href"].startswith("http") \
                    and not a["href"].lower().endswith(".pdf"):
                result["official_url"] = a["href"]
                break
    bewerbe: list[str] = []
    for table in soup.find_all("table"):
        kopf = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not kopf or kopf[0] != "Bewerb":
            continue
        for tr in table.find_all("tr")[1:]:
            td = tr.find("td")
            if not td:
                continue
            # Erste Zelle: "10km Straßenlauf" plus Kurzform in einem
            # zweiten Element - nur der erste Textknoten ist der Name.
            text = td.find(string=True, recursive=True)
            name = re.sub(r"\s+", " ", str(text)).strip() if text else ""
            if name and name not in bewerbe:
                bewerbe.append(name)
    if bewerbe:
        result["bewerbe"] = bewerbe
    return result


def fetch_oelv_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, False)
    if html is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    felder = formularfelder(soup)
    felder.update(FILTER)
    felder["ctl00$main$btnFilter"] = "ctl00$main$btnFilter"
    time.sleep(delay)
    resp = session.post(LISTE_URL, data=felder, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    zeilen: list[dict] = []
    for seite in range(1, max_pages + 1):
        neue, hat_naechste = parse_liste(soup)
        print(f"  ✓ Seite {seite}: {len(neue)} Lauf/Läufe.")
        zeilen.extend(neue)
        if not hat_naechste or not neue:
            break
        felder = formularfelder(soup)
        felder.update(FILTER)
        felder["ctl00$main$btnNext"] = "ctl00$main$btnNext"
        time.sleep(delay)
        resp = session.post(LISTE_URL, data=felder, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    events: list[Event] = []
    details = official = 0
    for z in zeilen:
        ort, land = parse_ort(z["ort"])
        ev = Event(land=land, name=z["name"], standort=ort, art1="Laufen",
                   datum_start=parse_flexible_date(z["datum"]),
                   veranstalter_url=z["url"])
        ev.datum_ende = ev.datum_start
        # Grundwerte aus dem Namen ("4. Haager Lies Halbmarathon"): sie
        # gelten, wenn die Detailseite keine Bewerbe nennt oder nicht
        # abgerufen wird; die Bewerbe überschreiben sie je Strecke.
        ev.laenge_km = guess_distance_km(ev.name, config)
        ev.dauer_h = parse_duration_h(ev.name)
        ev.art2 = guess_art2(ev.name, config, ev.art1)
        bewerbe: list[str] = []
        if config.fetch_details and (not config.max_details or details < config.max_details):
            time.sleep(delay)
            dhtml = fetch_page(session, z["url"], False)
            details += 1
            d = parse_detail(dhtml) if dhtml else {}
            if d.get("official_url"):
                ev.veranstalter_url = d["official_url"]
                official += 1
            bewerbe = d.get("bewerbe") or []
        events.extend(expand_competitions(ev, parse_competitions(bewerbe, config), config))
    print(f"\n→ {details} Detailseite(n), davon {official} mit Homepage; "
          f"{len(zeilen)} Läufe -> {len(events)} Einträge.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Laufen",
    default_land="Österreich",
    custom_fetch=fetch_oelv_events,
    note="oelv_scraper.py: ÖLV-Laufkalender (oelv.athmin.at, robots.txt 404 = "
         "keine Einschränkung); Filter 'Alle Läufe' per Postback, Detailseite "
         "mit Homepage und Bewerben.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
