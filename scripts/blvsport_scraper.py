#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blvsport_scraper.py
======================

Liest Lauf-Events vom Laufkalender auf
https://blv-sport.de/laufsport/laufkalender aus und ergänzt sie in
`events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

WICHTIG: Netzwerkzugriff auf blv-sport.de war in der Entwicklungsumgebung
blockiert – nicht gegen die echte Seite getestet.

Hinweis zum Geltungsbereich: BLV steht vermutlich für den Bayerischen
Leichtathletik-Verband - die dort gelisteten Läufe dürften überwiegend
oder ausschließlich in Bayern (Deutschland) stattfinden. Das ist mit dem
DACH-Fokus dieses Projekts kompatibel (Bayern ⊂ Deutschland), es werden
also voraussichtlich keine Events durch den (Land bereits Deutschland)
Filter aussortiert.

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
    note="blvsport_scraper.py: nicht gegen die echte Seite getestet. "
         "BLV = vermutlich Bayerischer Leichtathletik-Verband, Events "
         "voraussichtlich regional auf Bayern (Deutschland) begrenzt.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
