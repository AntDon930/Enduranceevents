#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runninglife_scraper.py
=========================

Liest Lauf-Events vom Laufkalender auf
https://running.life/laufkalender/deutschland aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

Echt getestet (Stand: verifiziert gegen die Live-Seite)
--------------------------------------------------------
robots.txt erlaubt `/laufkalender/deutschland` (gesperrt sind nur
`/xx/map/`-Pfade und `/demo-*`). Die Seite liefert die Events server-
seitig gerendert als schema.org-**ItemList** mit `itemListElement[].item`
= `SportsEvent` (kein React/Next.js-Nachladen nötig, kein `--render-js`
erforderlich) - `scraper_lib.parse_jsonld_events()` entpackt dieses
ItemList-Muster automatisch. Jede Seite enthält 20 Events, `<a rel="next">`
verlinkt zur nächsten Seite (`?page=2`, `?page=3`, ...) - Pagination
funktioniert daher bereits mit den `DEFAULT_NEXT_PAGE_SELECTORS` aus
`scraper_lib.py`. Für Österreich/Schweiz analog `/laufkalender/oesterreich` bzw.
`/laufkalender/schweiz` in einer Kopie dieses Skripts als
`CONFIG.calendar_url` eintragen.

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
    note="runninglife_scraper.py: robots.txt erlaubt den Zugriff. Events "
         "kommen server-seitig als JSON-LD-ItemList, kein --render-js nötig.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
