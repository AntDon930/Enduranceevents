#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fsieben_scraper.py
==================

Liest den „Triathlon-Kalender Österreich" von F7 Ausdauertraining
(https://www.fsieben.at/tools/triathlon-kalender-oesterreich/) und
ergänzt die Bewerbe in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026)
----------------------------------
Vom Nutzer am 24.09.2026 in seiner Linkliste geschickt („Bitte alle
checken"). robots.txt (WordPress) sperrt nur `/wp-admin/`; das Impressum
trägt den üblichen Urheberrechtshinweis („Verwendung, welche
urheberrechtlich untersagt ist, bedarf schriftlicher Zustimmung") - kein
Verbot des Auslesens, und übernommen werden Termine, Orte und Links,
keine Texte. Die Seite selbst schreibt: „bitte vor der Anmeldung auf der
offiziellen Event-Seite prüfen" - genau die steht bei uns als
`veranstalter_url`.

Struktur (am 24.09.2026 kalibriert)
-----------------------------------
Die Seite ist eine **Rechercheliste** („Stand der Recherche:
29.07.2026"), keine Datenbank: Alle Bewerbe stehen als JSON-Array in
`<pre id="f7-ev-data">`, je Bewerb `n` (Name), `so` (ISO-Datum),
`d` (Datumstext, bei mehreren Tagen „19.–20. Juni 2027"), `o` (Ort),
`b` (Bundesland), `t` (Formate: Sprint, Olympisch, Mitteldistanz,
Langdistanz, Cross, Duathlon, Aquathlon, Kids, Staffel), `u`
(Event-Seite), `st` (Status: bestätigt, unbestätigt, erwartet), `hi`
(„zuletzt 22.08.2026" bei „Termin folgt"). Im September 2026: 94
Bewerbe, davon **52 „erwartet"** mit `so` = 9999-12-31 - die haben
keinen Termin. **Seit dem 08.10.2026 kommen sie mit einem geschätzten
Termin** (vom Nutzer entschieden: „Ja aufnehmen, und in den Stern halt noch
schreiben das es to be confirmed noch sein muss. Aber dann können die
Leute sich drauf vorbereiten"): `hi` nennt den letzten Termin, die neue
Ausgabe liegt am selben Wochentag ein Jahr später (`naechster_termin`).
Solche Zeilen tragen `datum_vorlaeufig` (Anzeige „Aug. 2027*", „Termin noch
zu bestätigen") UND `gedaechtnis` (die Formate sind die des Vorjahrs);
`clean_events.zurueckziehen_prognosen()` nimmt sie heraus, sobald eine
Quelle den echten Termin liefert (auch fsieben selbst). Nur Bewerbe mit
einem Einzelformat (nicht nur Kids/Staffel) und ohne „Kids" im Namen.
19 datierte künftige Bewerbe, 15 davon schon im
Bestand (running.life, endure). Die Ausbeute ist klein; der Scraper
läuft trotzdem wöchentlich mit, damit ein nachgetragener Termin
automatisch ankommt.

Was daraus wird
---------------
* Nur Bewerbe mit Datum (`so` < 9999). Status „unbestätigt" setzt
  `datum_vorlaeufig` (die Quelle sagt es selbst, das ist keine
  Vermutung). „Ort noch offen" und Schulmeisterschaften fallen weg.
* Je Format in `t` EIN Eintrag (Datenregel 1) - ohne Kilometer, die
  Seite nennt keine; das Format steht im Label („Sprint", „Olympisch",
  „Mitteldistanz"), damit `triathlonFormat()` es anzeigt und der Filter
  greift. Kids (Datenregel 5/Kinder) und Staffel (Datenregel 16) sind
  keine Zeilen; Cross → Cross-Triathlon, Duathlon und Aquathlon ihre
  eigene Kategorie. Nennt `t` kein Einzelformat, bleibt eine Zeile
  ohne Label.
* Ort: die Angabe („Traun (Ödtsee)", „Pichlingersee, Linz", „Zell am
  See / Kaprun") wird an Klammern, Komma, Schrägstrich und Pfeil
  geteilt; der erste Teil, der laut `places.json` ein Ort in
  Österreich ist, gilt - mit Koordinaten von dort (Lektion 3 der
  Einzelprüfung: „Pichlingersee" ist ein See, Linz der Ort). Ohne
  Treffer der erste Teil, den der Geocoder des Laufs sucht.
* `u` ist die Event-Seite (Datenregel 2); Verbandskalender
  (triathlon-austria.at) und Zeitnehmer stehen in `PORTAL_DOMAINS` und
  werden bei einem späteren Lauf ersetzt.

Nutzung: `python3 scripts/fsieben_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import html as html_lib
import json
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    orte_aus_places,
    ort_aus_veranstaltungsort,
    run_scraper_cli,
)

BASE_URL = "https://www.fsieben.at"
LISTE_URL = f"{BASE_URL}/tools/triathlon-kalender-oesterreich/"

# Format in `t` -> (Label, art2). Kids und Staffel sind keine Zeilen.
FORMATE = {
    "Sprint": ("Sprint", "Straße"),
    "Olympisch": ("Olympisch", "Straße"),
    "Mitteldistanz": ("Mitteldistanz", "Straße"),
    "Langdistanz": ("Langdistanz", "Straße"),
    "Cross": ("Cross-Triathlon", "Cross"),
    "Duathlon": ("Duathlon", "Duathlon"),
    "Aquathlon": ("Aquathlon", "Aquathlon"),
}
# Schulmeisterschaften sind nicht offen (Datenregel 18). "Firmentriathlon" NICHT
# hier: der Steeltownman trägt "(+ OÖ Firmentriathlon)" als Zusatz zum offenen Rennen.
NICHT_OFFEN = re.compile(r"schulmeisterschaft", re.I)
_TRENNER = re.compile(r"\s*(?:\(|→|/|,)\s*")


def parse_kalender(html: str) -> list[dict]:
    m = re.search(r'<pre id="f7-ev-data"[^>]*>(.*?)</pre>', html, re.S)
    if not m:
        return []
    return json.loads(html_lib.unescape(m.group(1)))


def ort_und_koordinaten(text: str | None, orte: dict) -> tuple[str, float | None, float | None] | None:
    """Der erste Teil der Ortsangabe, der ein österreichischer Ort ist."""
    text = re.sub(r"\s*\([^)]*\)", "", text or "").strip()
    # "Feldkirchen b. Graz" heißt in places.json "Feldkirchen bei Graz".
    text = re.sub(r"\bb\.\s*", "bei ", text)
    if not text or re.search(r"noch offen", text, re.I):
        return None
    for teil in _TRENNER.split(text):
        teil = teil.strip(" .-")
        kandidaten = [teil, re.sub(r"\s+(?:am|an der|bei|im)\s+.*$", "", teil)]
        for k in kandidaten:
            treffer = orte.get(k.lower())
            if treffer and len(treffer) == 1:
                return treffer[0]
    ort = ort_aus_veranstaltungsort(text)
    return (ort, None, None) if ort else None


def datum_ende(eintrag: dict) -> str:
    """„19.–20. Juni 2027" -> 2027-06-20; sonst das Startdatum."""
    start = eintrag["so"]
    m = re.match(r"\s*(\d{1,2})\.\s*[–-]\s*(\d{1,2})\.", eintrag.get("d") or "")
    if m:
        tage = int(m.group(2)) - int(m.group(1))
        if 0 < tage < 10:
            return (date.fromisoformat(start) + timedelta(days=tage)).isoformat()
    return start


_ZULETZT = re.compile(r"(\d{1,2})\.(?:\s*[–-]\s*(\d{1,2})\.)?(\d{1,2})\.(\d{4})")


def naechster_termin(hi: str | None, heute: date | None = None) -> tuple[str, str] | None:
    """„zuletzt 22.08.2026" -> (2027-08-21, 2027-08-21): derselbe Wochentag
    ein Jahr später, dem Kalenderdatum am nächsten (52 Wochen, notfalls
    53). „zuletzt 12.–13.09.2026" behält die Dauer. Liegt das Ergebnis
    nicht in der Zukunft, nichts."""
    m = _ZULETZT.search(hi or "")
    if not m:
        return None
    t1, t2, monat, jahr = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
    try:
        start = date(jahr, monat, int(t1))
        ende = date(jahr, monat, int(t2)) if t2 else start
        jahrestag = date(jahr + 1, monat, int(t1))
    except ValueError:
        return None
    if ende < start:
        return None
    neu = start + timedelta(weeks=52)
    if (jahrestag - neu).days > 3:
        neu += timedelta(weeks=1)
    if neu <= (heute or date.today()):
        return None
    return neu.isoformat(), (neu + (ende - start)).isoformat()


def events_aus_eintrag(eintrag: dict, orte: dict | None = None,
                       heute: date | None = None) -> tuple[list[Event], str | None]:
    prognose = False
    if not eintrag.get("so") or eintrag["so"] >= "9999":
        termin = naechster_termin(eintrag.get("hi"), heute)
        if not termin:
            return [], "Termin folgt"
        if re.search(r"\bkids?\b", eintrag.get("n") or "", re.I):
            return [], "Termin folgt"
        if not [f for f in eintrag.get("t") or [] if f in FORMATE]:
            return [], "Termin folgt"
        eintrag = dict(eintrag, so=termin[0], d="")
        prognose_ende = termin[1]
        prognose = True
    name = (eintrag.get("n") or "").strip()
    if not name:
        return [], "kein Name"
    if NICHT_OFFEN.search(name):
        return [], "nicht für jeden offen"
    if orte is None:
        # Die Orte des Bundeslands: "Linz" gibt es in Oberösterreich UND in
        # Kärnten - mit dem Bundesland (`b`) ist der Name eindeutig.
        try:
            orte = orte_aus_places("Österreich", region=eintrag.get("b") or None)
        except ValueError:
            orte = orte_aus_places("Österreich")
    ort = ort_und_koordinaten(eintrag.get("o"), orte)
    if not ort:
        return [], f"kein Ort ({eintrag.get('o')})"
    standort, lat, lon = ort
    status = (eintrag.get("st") or "").lower()
    basis = dict(land="Österreich", name=name, standort=standort, lat=lat, lon=lon,
                 art1="Triathlon", datum_start=eintrag["so"], datum_ende=datum_ende(eintrag),
                 veranstalter_url=(eintrag.get("u") or "").strip() or LISTE_URL,
                 datum_vorlaeufig=True if status.startswith("unbest") else None)
    if prognose:
        # Die Auflage des Vorjahrs („11. Kraigerseetriathlon") wäre falsch.
        basis.update(name=re.sub(r"^\d{1,3}\.\s*", "", name), datum_ende=prognose_ende,
                     datum_vorlaeufig=True, gedaechtnis=True)
    formate = [f for f in eintrag.get("t") or [] if f in FORMATE]
    if not formate:
        ev = Event(**basis)
        ev.art2 = "Straße"
        return [ev], None
    events = []
    for f in formate:
        label, art2 = FORMATE[f]
        ev = Event(**basis, wettbewerb=label)
        ev.art2 = art2
        events.append(ev)
    return events, None


def fetch_fsieben_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {LISTE_URL} ...")
    html = fetch_page(session, LISTE_URL, render_js=False)
    if not html:
        print("  ⚠ Seite nicht abrufbar.")
        return []
    eintraege = parse_kalender(html)
    stand = re.search(r"Stand der Recherche:\s*([\d.]+)", html)
    print(f"  ✓ {len(eintraege)} Bewerbe im Kalender" + (f" (Stand der Recherche {stand.group(1)})." if stand else "."))
    events: list[Event] = []
    gruende: dict[str, int] = {}
    for e in eintraege:
        neue, grund = events_aus_eintrag(e)
        if grund:
            gruende[grund.split(" (")[0]] = gruende.get(grund.split(" (")[0], 0) + 1
            if not grund.startswith("Termin folgt"):
                print(f"   - {e.get('n')}: {grund}")
        events.extend(neue)
    for grund, n in gruende.items():
        print(f"  ({n}× übersprungen: {grund})")
    print(f"\n→ {len(events)} Bewerbe mit Termin.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=LISTE_URL,
    default_art1="Triathlon",
    default_land="Österreich",
    custom_fetch=fetch_fsieben_events,
    note="fsieben_scraper.py: Triathlon-Kalender Österreich (Rechercheliste als JSON "
         "in der Seite); nur datierte Bewerbe, je Format eine Zeile ohne Kilometer.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
