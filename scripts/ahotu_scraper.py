#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ahotu_scraper.py
===================

Liest Lauf-Events vom Kalender auf
https://www.ahotu.com/de/kalender/laufen/deutschland aus und ergänzt sie
in `events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

WICHTIG: Netzwerkzugriff auf ahotu.com war in der Entwicklungsumgebung
blockiert – nicht gegen die echte Seite getestet.

ahotu.com ist eine internationale, mehrsprachige Eventplattform für viele
Sportarten und Länder (dieselbe Seite, die als gestalterische Inspiration
für die Willkommensseite dieses Projekts diente) - technisch sehr
wahrscheinlich eine moderne React/Next.js-Anwendung mit clientseitigem
Nachladen der Ergebnisse, ähnlich wie ironman.com (siehe
`ironman_scraper.py`). Bei 0 gefundenen Events also zuerst `--render-js`
probieren, sonst über die Browser-Entwicklertools den JSON-API-Endpunkt
suchen und mit `--api-url` nutzen.

Die Ziel-URL ist bereits auf "/deutschland" eingeschränkt, der
DACH-Filter (`--include-all-europe` zum Deaktivieren) bleibt trotzdem als
Sicherheitsnetz aktiv, falls die Seite dennoch auch Events aus
Nachbarländern mit ausliefert.

Nutzung: `python3 scripts/ahotu_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="https://www.ahotu.com",
    calendar_url="https://www.ahotu.com/de/kalender/laufen/deutschland",
    default_art1="Laufen",
    note="ahotu_scraper.py: nicht gegen die echte Seite getestet. "
         "Vermutlich moderne JS-Seite (wie ironman.com) - bei 0 "
         "gefundenen Events zuerst --render-js probieren, siehe Docstring.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
