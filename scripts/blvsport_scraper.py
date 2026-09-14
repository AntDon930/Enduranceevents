#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blvsport_scraper.py
======================

Liest Lauf-Events vom Laufkalender auf
https://blv-sport.de/laufsport/laufkalender aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt liefert 404 (keine robots.txt vorhanden) -> laut Konvention
uneingeschränkt erlaubt (siehe `scraper_lib.check_robots`).

Die Seite ist eine klassische TYPO3-Tabelle ohne JSON-LD:

    <table class="termin-tbl">
      <tr><th>Datum</th><th>Bezeichnung</th><th>Ort</th></tr>
      <tr><td>05.09.2026</td><td class="bezeichnung">47. Gaißacher Berglauf</td><td>Gaißach</td></tr>
      ...
    </table>

Keine Distanz- oder Link-Spalte vorhanden, daher bleiben `laenge_km` und
`veranstalter_url` bei diesen Events leer.

Besonderheit: Die Seite hat oben ein Formular (Jahr/Monat-Auswahl), das
aber weder per GET-Query-Parametern noch per POST (`su_jahr`/`su_monat`,
getestet für mehrere Jahre/Monate inkl. "alle Monate") einen anderen
Tabelleninhalt liefert als der einfache Aufruf ohne Parameter – die Seite
zeigt serverseitig offenbar immer dieselbe (vermutlich rollierende,
auf die nächsten Monate begrenzte) Liste an "anstehenden" Terminen,
unabhängig von der Filterauswahl. Ein einfacher GET-Request auf die
Kalender-URL liefert daher bereits alle verfügbaren Events; es gibt
keine Pagination.

BLV = Bayerischer Leichtathletik-Verband - die gelisteten Läufe liegen
praktisch ausschließlich in Bayern (Deutschland), daher
`default_land="Deutschland"` als Fallback (die reine Ortsangabe ohne PLZ
lässt sonst kein Land erkennen).

Nutzung: `python3 scripts/blvsport_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="https://blv-sport.de",
    calendar_url="https://blv-sport.de/laufsport/laufkalender",
    default_art1="Laufen",
    default_land="Deutschland",
    # event_card ist bewusst nur "tr": Kopf-/Trennzeilen der Tabelle haben
    # weder eine .bezeichnung-Zelle noch ein erkennbares Datum in Spalte 1
    # und werden dadurch automatisch von parse_html_fallback verworfen
    # (weder Name noch Datum gefunden).
    html_fallback_selectors={
        "event_card": "table.termin-tbl tr",
        "name": "td.bezeichnung",
        "date": "td:nth-child(1)",
        "location": "td:nth-child(3)",
        "link": "a",
        "category": "",
        "distance": "",
    },
    note="blvsport_scraper.py: robots.txt nicht vorhanden (404) -> erlaubt. "
         "Tabelle ohne Distanz-/Link-Spalte; Jahr/Monat-Filter der Seite "
         "wirkt sich serverseitig nicht auf den Inhalt aus, ein einfacher "
         "Abruf liefert bereits alle Events ohne Pagination.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
