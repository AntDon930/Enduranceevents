#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runnersworld_scraper.py
==========================

Liest Lauf-Events vom Laufkalender auf https://www.runnersworld.de/laufkalender/
aus und ergänzt sie in `events.json` (siehe `scraper_lib.py` für die
gemeinsame Logik: robots.txt-Prüfung, JSON-LD-/HTML-Fallback-Parsing,
Geocoding, Dedupe/Merge).

WICHTIG: Wie bei den anderen Scraper-Skripten in diesem Verzeichnis war der
Netzwerkzugriff auf runnersworld.de in der Entwicklungsumgebung blockiert
(Firewall-/Proxy-Richtlinie) – dieses Skript wurde daher NICHT gegen die
echte Seite getestet. Die HTML-Fallback-Selektoren
(`CONFIG.html_fallback_selectors`) sind Platzhalter aus `scraper_lib.py`
und sollten nach einem Blick in den echten Seitenquelltext kalibriert
werden, falls die Seite kein JSON-LD liefert. Runner's World ist ein
etabliertes Laufmagazin (Hearst/Motorpresse) – Kalenderseiten solcher
Magazine sind oft serverseitig gerendert (kein --render-js nötig), das
ist aber nicht verifiziert.

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
    run_scraper_cli(CONFIG)
