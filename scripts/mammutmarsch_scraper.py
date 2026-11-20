#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mammutmarsch_scraper.py
=======================

Liest die Termine des **Mammutmarsch** (https://mammutmarsch.de/) -
Extremwanderungen über 30 bis 100 km in Deutschland, Österreich und
weiteren Ländern - und ergänzt sie in `events.json` (siehe
`scraper_lib.py`).

Vom Nutzer am 17.10.2026 gewünscht („Ja, alle Mammutmarsch aufnehmen.
Aber es muss schon irgendwo gekennzeichnet sein, dass es ein Marsch
ist"): Die Zeilen stehen unter Laufen mit der Kategorie **„Marsch“**
(englisch „Walking“, `scraper_lib.ist_marsch_name()`).

Rechtslage (geprüft am 17.10.2026)
----------------------------------
robots.txt erlaubt alles außer Konto-, Warenkorb- und Admin-Seiten
(`Allow: /`). Impressum und Teilnahmebedingungen enthalten nur den
üblichen Urheberrechtshinweis (Vervielfältigung von Inhalten und Werken)
und keinen Vorbehalt gegen automatisches Auslesen; übernommen werden nur
Tatsachen (Name, Termin, Strecken, Ort) und als Link die Eventseite des
Veranstalters selbst (Datenregel 2 - mammutmarsch.de IST der Veranstalter).

Struktur (am 17.10.2026 kalibriert)
-----------------------------------
EINE Seite: die Startseite trägt in den Next.js-Flight-Daten
(`self.__next_f.push`) die Liste aller kommenden Termine als JSON
(`"events":[{…}]`): `name` („Mammutmarsch Berlin - 30/42/55 KM“),
`slug`, `date`, `address` („Start/Ziel: …, 13405 Berlin“ oder „wird noch
bekannt gegeben“), `city`, `eventCountry` (DE/AT/ES/DK/SE), `status`,
`distances` ([30, 42, 55]). Am 17.10.2026: 30 Termine, 21 in Deutschland,
einer in Österreich (Wien).

Was daraus wird
---------------
* Je Distanz eine Zeile (Datenregel 1), Laufen / Marsch, Label „42 km“.
* Name ohne den Streckenzusatz („Mammutmarsch Berlin“); die Nachtausgabe
  heißt „Nachtmammut …“.
* Ort: die Postleitzahl in der Adresse, gegen `places.json` geprüft
  (Duisburg statt „Ruhr“, Krailling statt „München“); steht der Startort
  noch nicht fest, die Stadt, die der Veranstalter nennt - mit deren
  Koordinaten aus `places.json`. Kennt `places.json` den Ort nicht, kein
  Eintrag (nicht geraten).
* Länder außerhalb der vier Regionen (Spanien, Dänemark, Schweden) und
  abgesagte Termine fallen weg.

Nutzung: `python3 scripts/mammutmarsch_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    run_scraper_cli,
)

BASE_URL = "https://mammutmarsch.de"
KALENDER_URL = BASE_URL + "/"
LAND = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
_PLACES = Path(__file__).resolve().parent.parent / "places.json"
_ORTE: list | None = None


def _orte() -> list:
    global _ORTE
    if _ORTE is None:
        _ORTE = json.loads(_PLACES.read_text(encoding="utf-8"))["orte"]
    return _ORTE


def ort_aus_plz(plz: str, name: str, land_idx: int | None = None,
                kontext: str = "") -> tuple[str, float, float] | None:
    """(Ort, lat, lon) für eine PLZ, deren Ortsname zum genannten passt -
    nur Orte mit Einwohnern (siehe korrekturliste.ort_ueber_plz)."""
    name = name.strip().lower()
    kandidaten = [o for o in _orte()
                  if len(o) > 6 and plz in (o[6] or "").split() and (o[5] or 0) > 0
                  and (land_idx is None or o[1] == land_idx)]
    # Erst genau, dann der LÄNGSTE Ortsname, mit dem die Angabe beginnt
    # („Treffen am Ossiacher See Österreich“ -> Treffen am Ossiacher See,
    # nicht Treffen), zuletzt Orte, die mit der Angabe beginnen.
    passend = [o for o in kandidaten if o[0].lower() == name]
    if not passend:
        vorn = [o for o in kandidaten if name.startswith(o[0].lower() + " ")]
        if vorn:
            laenge = max(len(o[0]) for o in vorn)
            passend = [o for o in vorn if len(o[0]) == laenge]
    if not passend:
        passend = [o for o in kandidaten if o[0].lower().startswith(name)]
    # Die Postanschrift nennt die Gemeinde, der Ort mit dieser PLZ steht
    # im Namen der Anlage („Campingbeach Annenheim …, 9520 Treffen am
    # Ossiacher See“ -> Annenheim).
    if not passend and kontext:
        passend = [o for o in kandidaten if re.search(rf"\b{re.escape(o[0])}\b", kontext)]
    if len({(round(o[3], 2), round(o[4], 2)) for o in passend}) == 1:
        return passend[0][0], passend[0][3], passend[0][4]
    return None


def ort_aus_name(name: str, land_idx: int | None = None) -> tuple[str, float, float] | None:
    """(Ort, lat, lon) für einen Ortsnamen; bei mehreren Orten gleichen
    Namens der größte (die Stadt, die ein Veranstalter als Standort
    nennt, ist die bekannte - „Hannover“, nicht ein Weiler)."""
    n = name.strip().lower()
    treffer = [o for o in _orte() if o[0].lower() == n and (land_idx is None or o[1] == land_idx)]
    if not treffer:
        return None
    o = max(treffer, key=lambda x: x[5] or 0)
    return o[0], o[3], o[4]


LAND_IDX = {"Deutschland": 0, "Österreich": 1, "Schweiz": 2}
_PLZ_ORT = re.compile(r"\b(\d{4,5})\s+([A-ZÄÖÜ][\wäöüß.\- ]*?)(?=\s*(?:,|$|\(|\s{2}|[A-ZÄÖÜ][a-zäöü]+:|\d))")


def standort(adresse: str | None, stadt: str | None, land: str) -> tuple[str, float, float] | None:
    idx = LAND_IDX.get(land)
    for m in _PLZ_ORT.finditer(adresse or ""):
        plz, ort = m.group(1), m.group(2).strip()
        if (land == "Deutschland") != (len(plz) == 5):
            continue
        treffer = ort_aus_plz(plz, ort, idx)
        if treffer:
            return treffer
    return ort_aus_name(stadt or "", idx) if stadt else None


def termine_aus_html(html: str) -> list[dict]:
    """Die Terminliste aus den Flight-Daten der Startseite."""
    stuecke = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    text = "".join(json.loads('"' + s + '"') for s in stuecke)
    i = text.find('"events":[{')
    if i < 0:
        return []
    termine, _ = json.JSONDecoder().raw_decode(text[i + len('"events":'):])
    return termine


def name_ohne_strecken(name: str) -> str:
    return re.sub(r"\s*[-–]\s*[\d/ ]+\s*KM\s*$", "", name or "", flags=re.I).strip()


def events_aus_termin(t: dict) -> tuple[list[Event], str | None]:
    land = LAND.get((t.get("eventCountry") or t.get("country") or "").upper())
    if not land:
        return [], f"Land {t.get('eventCountry')}"
    if (t.get("effectiveStatus") or t.get("status")) not in (None, "ACTIVE"):
        return [], f"Status {t.get('effectiveStatus') or t.get('status')}"
    datum = (t.get("date") or "")[:10]
    if not re.match(r"\d{4}-\d\d-\d\d$", datum):
        return [], "kein Datum"
    ort = standort(t.get("address"), t.get("city"), land)
    if not ort:
        return [], f"Ort unbekannt ({t.get('city')})"
    distanzen = [d for d in (t.get("distances") or []) if isinstance(d, (int, float)) and d > 0]
    if not distanzen:
        distanzen = [int(x) for x in re.findall(r"\d+", (re.search(r"[\d/ ]+\s*KM\s*$", t.get("name") or "", re.I) or [""])[0])]
    if not distanzen:
        return [], "keine Strecke"
    name = name_ohne_strecken(t.get("name"))
    url = f"{BASE_URL}/events/{t['slug']}" if t.get("slug") else KALENDER_URL
    events = []
    for km in sorted(set(distanzen)):
        events.append(Event(
            land=land, name=name, standort=ort[0], lat=ort[1], lon=ort[2],
            art1="Laufen", art2="Marsch", datum_start=datum, datum_ende=datum,
            laenge_km=float(km), wettbewerb=f"{km:g} km", veranstalter_url=url,
        ))
    return events, None


def fetch_mammutmarsch_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {KALENDER_URL} ...")
    html = fetch_page(session, KALENDER_URL, render_js=False)
    if not html:
        print("  ⚠ Startseite nicht abrufbar.")
        return []
    termine = termine_aus_html(html)
    print(f"  ✓ {len(termine)} Termine.")
    events: list[Event] = []
    for t in termine:
        evs, grund = events_aus_termin(t)
        if grund:
            print(f"   - {(t.get('date') or '')[:10]} {t.get('name')}: {grund}")
            continue
        events.extend(evs)
    print(f"\n→ {len(events)} Zeilen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=KALENDER_URL,
    default_art1="Laufen",
    default_land="Deutschland",
    custom_fetch=fetch_mammutmarsch_events,
    note="mammutmarsch_scraper.py: Extremwanderungen (Kategorie Marsch), je Distanz eine Zeile, "
         "Ort über die PLZ der Startadresse, nur DE/AT/CH.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
