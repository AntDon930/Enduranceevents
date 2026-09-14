#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runninglife_scraper.py
=========================

Liest Lauf-Events vom Laufkalender auf
https://running.life/laufkalender/deutschland aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

WICHTIG: Netzwerkzugriff auf running.life war in der Entwicklungsumgebung
blockiert – nicht gegen die echte Seite getestet. Der moderne Domainname
und die Pfadstruktur (`/laufkalender/deutschland`, vermutlich auch
`/laufkalender/oesterreich`, `/laufkalender/schweiz` – ggf. als eigene
`--calendar-url`-Läufe ergänzen, indem man `CONFIG.calendar_url` unten
anpasst oder das Skript kopiert) deuten auf eine moderne
React/Next.js-Seite hin, die ihre Events evtl. per JavaScript aus einer
API nachlädt – falls JSON-LD und HTML-Fallback beide 0 Events finden,
zuerst `--render-js` probieren, dann den echten API-Endpunkt per
Browser-Entwicklertools suchen und mit `--api-url` nutzen.

Nutzung: `python3 scripts/runninglife_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="https://running.life",
    calendar_url="https://running.life/laufkalender/deutschland",
    default_art1="Laufen",
    note="runninglife_scraper.py: nicht gegen die echte Seite getestet. "
         "Vermutlich moderne JS-Seite - bei 0 gefundenen Events zuerst "
         "--render-js probieren, siehe Docstring.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
