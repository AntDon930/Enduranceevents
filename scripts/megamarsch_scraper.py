#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
megamarsch_scraper.py
=====================

Liest die Termine des **Megamarsch** (https://www.megamarsch.de/) -
Extremwanderungen über 25 km in 6 h, 50 km in 12 h und 100 km in 24 h in
Deutschland, Österreich und der Schweiz - und ergänzt sie in
`events.json` (siehe `scraper_lib.py`).

Vom Nutzer am 17.10.2026 gewünscht („Es gibt ja schon sehr viele Marsch
Events. Bitte alle aufnehmen"): Laufen mit der Kategorie **„Marsch“**
(englisch „Walking“).

Rechtslage (geprüft am 17.10.2026)
----------------------------------
robots.txt (Wix) erlaubt alles außer Lightbox-Adressen; gesperrt sind nur
einzelne fremde Bots (PetalBot). Impressum, AGB und Teilnahmebedingungen
tragen nur den üblichen Urheberrechtshinweis, keinen Vorbehalt gegen
automatisches Auslesen. Übernommen werden nur Tatsachen (Termin, Strecke,
Startort), als Link die Eventseite des Veranstalters.

Struktur (am 17.10.2026 kalibriert)
-----------------------------------
* `/megamärsche` („Alle Events auf einen Blick“): je Termin drei Zeilen
  Text - „HANNOVER“, „50KM // 12H“, „08.05.2027“ - und die Links auf die
  Eventseiten (`/hannover`, `/dresden-25-km`, `/weserbergland-bei-nacht`).
  Am 17.10.2026: 36 Termine, davon zwei auf Mallorca.
* Eventseite: „STARTORT:“ mit Anschrift und Postleitzahl („Messeparkplatz,
  Kronsbergstraße 80, 30880 Laatzen“).

Was daraus wird
---------------
* Je Termin und Distanz eine Zeile, Name „Megamarsch <Ort>“ wie der
  Veranstalter die Ausgabe nennt („Megamarsch Weserbergland bei Nacht“),
  Label „50 km“; das Zeitlimit (12 h) ist keine Renndauer.
* Ort: die PLZ des Startorts gegen `places.json` (Laatzen, nicht
  Hannover); ohne Startort oder unbekannt kein Eintrag. Mallorca fällt
  damit von selbst heraus (die spanische Postleitzahl trifft keinen Ort
  in DE/AT/CH mit passendem Namen).

Nutzung: `python3 scripts/megamarsch_scraper.py --help` (Testlauf: `--dry-run`).
"""

from pathlib import Path
import html as htmlmod
import re
import sys
import time
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    run_scraper_cli,
)
from mammutmarsch_scraper import ort_aus_name, ort_aus_plz  # noqa: E402

BASE_URL = "https://www.megamarsch.de"
KALENDER_URL = BASE_URL + "/" + quote("megamärsche")
LAND_JE_IDX = {0: "Deutschland", 1: "Österreich", 2: "Schweiz"}


def text_von(html: str) -> str:
    """Sichtbarer Text, eine Zeile je Element."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    t = htmlmod.unescape(re.sub(r"<[^>]+>", "\n", t)).replace("​", "")
    return re.sub(r"\n\s*\n+", "\n", t)


_TERMIN = re.compile(r"\n([^\n]+)\n(\d+)\s*KM\s*//\s*(\d+)\s*H\n(\d\d)\.(\d\d)\.(\d{4})", re.I)


def termine(html: str) -> list[dict]:
    """[{ort, km, h, datum}] aus der Übersichtsseite."""
    out = []
    for m in _TERMIN.finditer(text_von(html)):
        out.append({"ort": m.group(1).strip(), "km": int(m.group(2)), "h": int(m.group(3)),
                    "datum": f"{m.group(6)}-{m.group(5)}-{m.group(4)}"})
    return out


def eventseiten(html: str) -> set[str]:
    """Pfade der Eventseiten, die die Übersicht verlinkt (dekodiert)."""
    return {unquote(p).lower() for p in re.findall(r'href="https://www\.megamarsch\.de/([^"#?/]+)"', html)}


def _slug(text: str) -> str:
    return re.sub(r"[^a-zäöü0-9]+", "-", text.lower()).strip("-")


def seite_fuer(ort: str, km: int, seiten: set[str]) -> str | None:
    """Die Eventseite eines Termins: „HANNOVER“ -> hannover, „DRESDEN“ mit
    25 km -> dresden-25-km, „WESERBERGLAND bei Nacht“ ->
    weserbergland-bei-nacht, „BERLIN bei Nacht“ -> berlin (nur so
    verlinkt). Umlaute auch als ae/oe/ue (mönchengladbach -> moenchengladbach)."""
    basis = _slug(ort)
    ohne_nacht = re.sub(r"-bei-nacht$", "", basis)
    varianten = []
    for b in dict.fromkeys([basis, ohne_nacht]):
        umschrift = b.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        for x in dict.fromkeys([b, umschrift]):
            if km == 25:
                varianten += [f"{x}-25-km", f"{x}-25km", f"{x}s-25km"]
            varianten.append(x)
    for v in varianten:
        if v in seiten:
            return v
    for s in seiten:  # „duessseldorf-25km“ (so verlinkt, mit drei s)
        if km == 25 and "25" in s and s.startswith(ohne_nacht[:6]):
            return s
    return None


# „STARTORT:“, „STARTORT“ ohne Doppelpunkt, „START:“ (Ostsee, mit zwei
# Strecken) und „START- & ZIELORT:“ (Düsseldorf) - bis zum Ziel oder zur
# Verpflegung.
_STARTORT = re.compile(r"\nSTART(?:ORT|- ?& ?ZIELORT)?:?\s*\n(.*?)\n\s*(?:ZIEL|VERPFLEGUNG)", re.S | re.I)
_PLZ_ORT = re.compile(r"\b(\d{4,5})\s+([A-ZÄÖÜ][^\n,]*)")


def startort(html: str, stadt: str | None = None) -> tuple[str, float, float, str] | None:
    """(Ort, lat, lon, Land) aus „STARTORT:“ der Eventseite. Steht dort
    „Wird noch bekannt gegeben“ (Luzern, Bern), die Stadt, nach der der
    Veranstalter die Ausgabe benennt - nur wenn places.json sie kennt
    („Ostsee“ oder „Weserbergland“ ist kein Ort)."""
    m = _STARTORT.search(text_von(html))
    if not m or "bekannt gegeben" in m.group(1).lower():
        if stadt:
            for idx, land in LAND_JE_IDX.items():
                treffer = ort_aus_name(stadt, idx)
                if treffer:
                    return treffer[0], treffer[1], treffer[2], land
        return None
    for pm in _PLZ_ORT.finditer(m.group(1)):
        plz, ort = pm.group(1), pm.group(2).strip(" )")
        for idx, land in LAND_JE_IDX.items():
            if (idx == 0) != (len(plz) == 5):
                continue
            treffer = ort_aus_plz(plz, ort, idx, kontext=m.group(1))
            if treffer:
                return treffer[0], treffer[1], treffer[2], land
    return None


def anzeigename(ort: str) -> str:
    """„WESERBERGLAND bei Nacht“ -> „Weserbergland bei Nacht“, „OSSIACHER
    SEE“ -> „Ossiacher See“, „MÖNCHENGLADBACH“ -> „Mönchengladbach“."""
    return " ".join(w.capitalize() if w.isupper() else w for w in ort.split())


def fetch_megamarsch_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {KALENDER_URL} ...")
    html = fetch_page(session, KALENDER_URL, render_js=False)
    if not html:
        print("  ⚠ Übersicht nicht abrufbar.")
        return []
    liste = termine(html)
    seiten = eventseiten(html)
    print(f"  ✓ {len(liste)} Termine, {len(seiten)} verlinkte Seiten.")
    cache: dict[str, tuple | None] = {}
    events: list[Event] = []
    for t in liste:
        seite = seite_fuer(t["ort"], t["km"], seiten)
        if not seite:
            print(f"   - {t['datum']} {t['ort']} {t['km']} km: keine Eventseite")
            continue
        if seite not in cache:
            time.sleep(delay)
            stadt = anzeigename(re.sub(r"\s+bei Nacht$", "", t["ort"], flags=re.I))
            cache[seite] = startort(fetch_page(session, f"{BASE_URL}/{quote(seite)}", render_js=False) or "",
                                    stadt)
        ort = cache[seite]
        if not ort:
            print(f"   - {t['datum']} {t['ort']} {t['km']} km: Startort nicht in DE/AT/CH erkannt")
            continue
        events.append(Event(
            land=ort[3], name=f"Megamarsch {anzeigename(t['ort'])}", standort=ort[0],
            lat=ort[1], lon=ort[2], art1="Laufen", art2="Marsch",
            datum_start=t["datum"], datum_ende=t["datum"], laenge_km=float(t["km"]),
            wettbewerb=f"{t['km']} km", veranstalter_url=f"{BASE_URL}/{quote(seite)}",
        ))
    print(f"\n→ {len(events)} Zeilen.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=KALENDER_URL,
    default_art1="Laufen",
    default_land="Deutschland",
    custom_fetch=fetch_megamarsch_events,
    note="megamarsch_scraper.py: Extremwanderungen (Kategorie Marsch) 25/50/100 km, "
         "Ort über die PLZ des Startorts, nur DE/AT/CH.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
