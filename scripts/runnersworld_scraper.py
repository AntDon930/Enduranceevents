#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runnersworld_scraper.py
==========================

Liest Lauf-Events vom Laufkalender auf https://www.runnersworld.de/laufkalender/
aus und ergänzt sie in `events.json` (siehe `scraper_lib.py` für die
gemeinsame Logik: robots.txt-Prüfung, JSON-LD-/HTML-Fallback-Parsing,
Geocoding, Dedupe/Merge).

⚠ ABSICHTLICH NICHT AKTIV GENUTZT (robots.txt verbietet automatisiertes
Auslesen ausdrücklich in einem rechtlichen Hinweis)
----------------------------------------------------------------------
Verifiziert per echtem Abruf von `https://www.runnersworld.de/robots.txt`:
Die technischen `Disallow`-Regeln selbst würden `/laufkalender/` nicht
sperren, die Datei enthält aber zusätzlich diesen expliziten rechtlichen
Hinweis im Klartext:

    # Legal notice: [https://www.runnersworld.de/] expressly reserves
    # the right to use its content for commercial text and data mining
    # (§ 44b UrhG).
    # The use of robots or other automated means to access
    # [https://www.runnersworld.de/] or collect or mine data without the
    # express permission of [https://www.runnersworld.de/] is strictly
    # prohibited. If you would like to apply for permission to crawl
    # [https://www.runnersworld.de/], collect or use data, please contact
    # [ompi@motorpresse.de]

Das ist ein ausdrückliches Verbot von automatisiertem Auslesen ohne
vorherige Erlaubnis (inkl. Verweis auf den in § 44b UrhG vorgesehenen
Rechtsvorbehalt gegen Text- und Data-Mining) - unabhängig davon, welche
Pfade die technischen `Disallow`-Zeilen konkret nennen. Dieses Projekt
respektiert das und ruft `runnersworld.de` daher NICHT automatisiert ab.
`runnersworld.de` wird deshalb aktuell NICHT von `update_events.py` mit
produktiven Daten befüllt; das Skript bleibt als dokumentierte Vorlage im
Repo, falls künftig eine Erlaubnis bei `ompi@motorpresse.de` eingeholt
wird.

Nutzung: siehe README.md ("Automatisch von ... importieren") bzw.
`python3 scripts/runnersworld_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="https://www.runnersworld.de",
    calendar_url="https://www.runnersworld.de/laufkalender/",
    default_art1="Laufen",
    note="runnersworld_scraper.py: nicht gegen die echte Seite getestet "
         "(Netzwerkzugriff in der Entwicklungsumgebung blockiert). "
         "HTML-Fallback-Selektoren ggf. kalibrieren, siehe Docstring.",
)

if __name__ == "__main__":
    print(
        "⏭  runnersworld_scraper.py: bewusst übersprungen, OHNE die Seite "
        "abzurufen. runnersworld.de/robots.txt enthält einen ausdrücklichen "
        "rechtlichen Hinweis, dass automatisiertes Auslesen ohne Erlaubnis "
        "strikt verboten ist - siehe Docstring oben. events.json bleibt "
        "unverändert."
    )
    sys.exit(0)
