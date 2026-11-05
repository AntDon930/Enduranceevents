#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cyclocrosscup_scraper.py
========================

Liest die Rennseite des **Cyclocross Cups Baden-Württemberg**
(https://cyclocrosscup.de/rennen/) und ergänzt die Rennen in
`events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 30.09.2026, vom Nutzer freigegeben)
-----------------------------------------------------------
robots.txt (WordPress) ohne Sperre (`Disallow:` leer), Impressum ohne
Vorbehalt. Übernommen werden Termine, Orte, Links und der Zeitplan.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Eine Seite, je Rennen ein Abschnitt in `div.entry-content`:
`h2` „2. Lauf – Baiersbronn", `h3` „12. Cross im Park am 18.10.2026 in
Baiersbronn" (Name, Datum, Ort; bei Auslandsrennen „Brumath
(Frankreich)"), dann Absätze „Veranstalter: TV Baiersbronn",
„Informationen: <a>" (die Veranstalterseite, Datenregel 2),
„Ausschreibung: rad-net", „Anmeldung: gregorhoops.de", „Navi & Parken:
…" und eine Tabelle **Zeitplan** (Uhrzeit | Klasse | Renndauer |
Lizenz): „Hobby m U40/Ü40 | 30 min", „Masters 2, Masters 3, Masters 4 |
40 min", „Männer Elite | 50 min", dazu die Nachwuchsklassen U11–U19.
Im September 2026: 7 Läufe, davon einer in Frankreich.

Was daraus wird
---------------
* Fahrrad / Cyclecross. **Eine Zeile je Renndauer** (Datenregel 1;
  Cyclocross fährt auf Zeit, Datenregel 8: `dauer_h`), das Label nennt
  die Klassen dieser Dauer („Hobby, Masters 40 min"). Reine
  Nachwuchsklassen (U11–U19, Schüler, Jugend) fallen weg; eine Zeile
  „Frauen Elite + Juniorinnen" bleibt, weil Erwachsene starten. Ohne
  Zeitplan eine Zeile ohne Maßzahl.
* Nur Rennen in Deutschland, Österreich, der Schweiz oder Südtirol -
  Brumath (Frankreich) fällt weg.
* Ort aus dem `h3` („in Baiersbronn"), Koordinaten aus `places.json`.
* `veranstalter_url`: der Link hinter „Informationen"; ohne ihn die
  Cup-Seite (`PORTAL_DOMAINS`), nie gregorhoops (Anmeldung).

Nutzung: `python3 scripts/cyclocrosscup_scraper.py --help` (Testlauf: `--dry-run`).
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
    is_portal_link,
    ort_im_text,
    orte_aus_places,
    parse_flexible_date,
    run_scraper_cli,
)

BASE_URL = "https://cyclocrosscup.de"
RENNEN_URL = f"{BASE_URL}/rennen/"
CUP = "Cyclocross Cup Baden-Württemberg"

_TITEL = re.compile(r"^(?P<name>.+?)\s+am\s+(?P<datum>\d{1,2}\.\d{1,2}\.\d{4})\s+in\s+(?P<ort>[^()]+?)\s*(?:\((?P<land>[^)]+)\))?\s*$")
# Klassen, in denen nur der Nachwuchs startet.
_NACHWUCHS = re.compile(r"^\s*(?:U\s?\d{1,2}\b|schüler|jugend|kinder|kids|junior(?:en|innen)?\b)", re.I)
_DAUER = re.compile(r"(\d+)\s*min", re.I)
LAENDER = {None: "Deutschland", "Deutschland": "Deutschland", "Österreich": "Österreich",
           "Schweiz": "Schweiz", "Südtirol": "Italien (Südtirol)"}


def _klasse_kurz(klasse: str) -> str:
    """„Hobby m U40/Ü40 (JG 87+)" -> „Hobby", „Masters 2, Masters 3" -> „Masters",
    „Frauen Elite & U19 w" -> „Elite": die Klassenfamilie, ohne Geschlecht,
    Jahrgang und Nummer."""
    for wort in ("Hobby", "Masters", "Elite"):
        if re.search(r"\b" + wort + r"\b", klasse, re.I):
            return wort
    k = re.sub(r"\([^)]*\)", "", klasse)
    k = re.split(r"[,/+&]", k)[0]
    k = re.sub(r"\b(?:m|w|männlich|weiblich)\b|Ü\d+|U\d+|\b\d+\b", " ", k, flags=re.I)
    k = re.sub(r"\s+", " ", k).strip(" -")
    return k or klasse.strip()


def parse_rennen(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    inhalt = soup.select_one("div.entry-content") or soup
    rennen: list[dict] = []
    aktuell: dict | None = None
    for el in inhalt.find_all(["h2", "h3", "p", "table"]):
        text = el.get_text(" ", strip=True)
        if el.name == "h2" and re.match(r"\d+\.\s*Lauf\b", text):
            aktuell = {"lauf": text, "laeufe": []}
            rennen.append(aktuell)
            continue
        if aktuell is None or not text:
            continue
        # Der Titel steht als h3 - beim Heidelberger Lauf als zweite h2.
        if el.name in ("h2", "h3"):
            m = _TITEL.match(text)
            if m:
                aktuell.update(name=m.group("name").strip(), datum=parse_flexible_date(m.group("datum")),
                               ort=m.group("ort").strip(), land=(m.group("land") or "").strip() or None)
            else:
                # „5. Heidelberger Crossrennen 21.11.2026" - ohne „in Ort":
                # der Ort steht dann in der h2 („4. Lauf – Heidelberg").
                datum = parse_flexible_date(text)
                name = re.sub(r"\s*(?:am\s+)?\d{1,2}\.\d{1,2}\.\d{4}\s*$", "", text).strip()
                ort = re.sub(r"^.*?Lauf\s*[–-]\s*", "", aktuell["lauf"]).strip()
                aktuell.update(name=name, datum=datum, ort=ort or None, land=None)
        elif el.name == "p":
            if text.startswith("Veranstalter:"):
                aktuell["veranstalter"] = text.split(":", 1)[1].strip() or None
            elif text.startswith("Informationen:"):
                a = el.find("a", href=True)
                aktuell["url"] = a["href"].strip() if a else None
            elif text.startswith("Navi"):
                aktuell["adresse"] = text.split(":", 1)[1].strip() or None
        elif el.name == "table":
            for tr in el.find_all("tr"):
                zellen = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                if len(zellen) < 3 or not zellen[1] or zellen[1] == "Klasse":
                    continue
                m = _DAUER.search(zellen[2])
                aktuell["laeufe"].append({"klasse": zellen[1], "minuten": int(m.group(1)) if m else None,
                                          "lizenz": zellen[3] if len(zellen) > 3 else ""})
    return [r for r in rennen if r.get("datum")]


def events_aus_rennen(r: dict, orte: dict | None = None) -> tuple[list[Event], str | None]:
    if r.get("land") not in LAENDER:
        return [], f"außerhalb ({r.get('land')})"
    land = LAENDER[r.get("land")]
    orte = orte if orte is not None else orte_aus_places(land)
    # Erst der Ort hinter der PLZ der Anfahrt (eindeutig), dann der Ort aus
    # dem Titel - „Herxheim" gibt es zweimal in Rheinland-Pfalz, ohne PLZ
    # bleibt das offen und wird gemeldet.
    ort = None
    m = re.search(r"\b\d{5}\s+([A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ][\wäöüß-]+)?)", r.get("adresse") or "")
    if m:
        ort = ort_im_text(m.group(1), orte)
    ort = ort or ort_im_text(r.get("ort"), orte)
    if not ort:
        return [], f"kein eindeutiger Ort ({r.get('ort')})"
    standort, lat, lon = ort
    url = r.get("url")
    if not url or is_portal_link(url) and "gregorhoops" in url:
        url = RENNEN_URL
    basis = dict(land=land, name=r["name"], standort=standort, lat=lat, lon=lon, art1="Fahrrad",
                 datum_start=r["datum"], datum_ende=r["datum"], veranstalter_url=url)
    # Je Renndauer eine Zeile, Klassen gesammelt; Nachwuchs raus.
    nach_dauer: dict[int, list[str]] = {}
    for lauf in r.get("laeufe") or []:
        if _NACHWUCHS.match(lauf["klasse"]) or not lauf.get("minuten"):
            continue
        kurz = _klasse_kurz(lauf["klasse"])
        if kurz not in nach_dauer.setdefault(lauf["minuten"], []):
            nach_dauer[lauf["minuten"]].append(kurz)
    events = []
    if not nach_dauer:
        ev = Event(**basis, wettbewerb=f"Cyclocross, {CUP}")
        ev.art2 = "Cyclecross"
        return [ev], None
    for minuten, klassen in sorted(nach_dauer.items()):
        ev = Event(**basis, dauer_h=round(minuten / 60, 2),
                   wettbewerb=f"{', '.join(klassen)} {minuten} min ({CUP})")
        ev.art2 = "Cyclecross"
        events.append(ev)
    return events, None


def fetch_cyclocrosscup_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {RENNEN_URL} ...")
    html = fetch_page(session, RENNEN_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    rennen = parse_rennen(html)
    print(f"  ✓ {len(rennen)} Läufe auf der Seite.")
    orte = orte_aus_places("Deutschland")
    events: list[Event] = []
    for r in rennen:
        neue, grund = events_aus_rennen(r, orte if r.get("land") in (None, "Deutschland") else None)
        if grund:
            print(f"   - {r.get('name')}: {grund}")
        events.extend(neue)
    print(f"\n→ {len(events)} Zeilen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=RENNEN_URL,
    default_art1="Fahrrad",
    default_land="Deutschland",
    custom_fetch=fetch_cyclocrosscup_events,
    note="cyclocrosscup_scraper.py: Cyclocross Cup Baden-Württemberg; eine Zeile je Renndauer "
         "(Zeitrennen), Nachwuchsklassen und Auslandsrennen fallen weg.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
