#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blvsport_scraper.py
======================

Liest Lauf-Events vom Laufkalender auf
https://blv-sport.de/laufsport/laufkalender aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

⚠ ABSICHTLICH NICHT AKTIV GENUTZT (Datenqualität, nicht robots.txt)
----------------------------------------------------------------------
Anders als bei den drei anderen übersprungenen Quellen (ironman.com,
runnersworld.de, ahotu.com) ist der Zugriff hier technisch und rechtlich
einwandfrei erlaubt - diese Quelle ist bewusst wegen ihrer DATENQUALITÄT
deaktiviert:

Die Tabelle liefert ausschließlich Datum, Bezeichnung und Ort - KEINE
Distanz und KEINEN Veranstalter-Link. Damit fehlen genau die zwei
Angaben, von denen die Qualität dieses Projekts abhängt: ohne Distanz
greift die 5-km-Mindestdistanz-Regel nicht (reine Kinder-/Bambiniläufe
landen unbemerkt in der Liste), und ohne Link kann niemand die Angaben
gegenprüfen. Beide Lücken lassen sich nur durch manuelle Recherche pro
Event schließen (das ist die Aufgabe von `scripts/manual_overrides.json`,
dort sind die 40 zum Recherchezeitpunkt gelisteten Events einzeln gegen
die offizielle Ausschreibung geprüft) - und diese Handarbeit müsste bei
jedem neuen Event erneut geleistet werden, sonst sinkt die Qualität mit
jedem Lauf des Scrapers wieder. Dieser Aufwand steht in keinem
Verhältnis zum Mehrwert, zumal ein Großteil der bayerischen Läufe
ohnehin über laufen.de mit Distanz UND Link erfasst wird.

Das Skript bricht deshalb sofort mit Exit-Code 0 ab (kein
Netzwerkzugriff) und bleibt nur als dokumentierte, funktionsfähige
Vorlage im Repo - falls blv-sport.de seine Tabelle künftig um Distanz-
und Link-Spalten erweitert, genügt es, den `sys.exit(0)`-Block unten zu
entfernen. Die bereits recherchierten Events sind in `events.json`
erhalten geblieben.

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
    print(
        "⏭  blvsport_scraper.py: bewusst übersprungen, OHNE die Seite abzurufen. "
        "Der Zugriff wäre erlaubt, aber die Tabelle liefert weder Distanz noch "
        "Veranstalter-Link - ohne beides greift die 5-km-Mindestdistanz-Regel "
        "nicht und die Angaben sind nicht überprüfbar (Datenqualität), siehe "
        "Docstring oben. events.json bleibt unverändert."
    )
    sys.exit(0)
