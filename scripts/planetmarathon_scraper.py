#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planetmarathon_scraper.py
============================

Liest Marathon-Events von http://www.planet-marathon.de/marathon_d.html
aus und ergänzt sie in `events.json` (siehe `scraper_lib.py` für die
gemeinsame Logik).

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt (http://www.planet-marathon.de/robots.txt) erlaubt den Zugriff
(nur /bilder/, /temp/ und /beispiel.html sind gesperrt).

Wie im ursprünglichen TODO vermutet: eine einzelne, alte, klassenlose
HTML-Tabelle (`marathon_d.html` listet ausschließlich Deutschland, siehe
Seitentitel "Marathontermine in Deutschland" - Europa/Welt liegen unter
separaten URLs). Kein JSON-LD. Struktur pro Datenzeile:

    <tr>
        <td>05.09.2026</td>
        <td><a href="...">46. Usedom Marathon</a></td>
        <td>17431</td>
        <td>Wolgast</td>
    </tr>

Dazwischen liegen reine Kopf-/Trenn-/Monatsüberschriftzeilen (z. B. nur
"&nbsp;"-Zellen oder eine Zeile mit dem Monatsnamen statt eines Datums in
Spalte 1) - die werden automatisch übersprungen, weil sich aus ihnen kein
Datum extrahieren lässt (`Event.is_valid()` verlangt Name + Datum +
Standort). Die Seite lädt alle Events auf einmal (kein "nächste Seite"
-Link), Pagination ist daher nicht nötig.

Die Seite selbst weist ausdrücklich darauf hin: "Eingetragen werden
grundsätzlich nur Marathonveranstaltungen mit offizieller
Marathondistanz von 42,195 km." - `known_distances_km={"": 42.2}` nutzt
das aus (der leere String ist Teilstring jedes Namens, daher greift die
42,2-km-Annahme immer, außer eine explizite "NN km"-Angabe im Namen
überschreibt sie).

Nutzung: `python3 scripts/planetmarathon_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="http://www.planet-marathon.de",
    calendar_url="http://www.planet-marathon.de/marathon_d.html",
    default_art1="Laufen",
    default_land="Deutschland",
    known_distances_km={"": 42.2},
    html_fallback_selectors={
        # Bewusst "tr" statt eines spezifischeren Selektors: die Tabelle hat
        # keine CSS-Klassen, und Kopf-/Trennzeilen werden ohnehin verworfen,
        # weil sich aus ihnen weder Name noch Datum extrahieren lässt.
        "event_card": "table tr",
        # Name = der Linktext in Spalte 2 (nicht die ganze Zelle, die bei
        # manchen Events noch einen "*(...)"-Zusatztext nach dem Link hat).
        "name": "td:nth-child(2) a, th:nth-child(2) a",
        "date": "td:nth-child(1), th:nth-child(1)",
        # Spalte 3 ist die PLZ, Spalte 4 der Ortsname (teils selbst mit
        # verlinktem Facebook-Auftritt) - für "standort" reicht Spalte 4,
        # get_text() zieht den Text auch aus einem verschachtelten <a>.
        "location": "td:nth-child(4), th:nth-child(4)",
        "link": "a",
        "category": "",
        "distance": "",
    },
    note="planetmarathon_scraper.py: robots.txt erlaubt den Zugriff. "
         "Klassenlose HTML-Tabelle wie vermutet, generischer tr-Selektor "
         "mit Positions-Selektoren (nth-child) statt CSS-Klassen.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
