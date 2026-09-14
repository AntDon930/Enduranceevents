#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ahotu_scraper.py
===================

Liest Lauf-Events vom Kalender auf
https://www.ahotu.com/de/kalender/laufen/deutschland aus und ergänzt sie
in `events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

⚠ ABSICHTLICH NICHT AKTIV GENUTZT (Cloudflare-Bot-Challenge)
----------------------------------------------------------------
Verifiziert per echtem Abruf: Schon `https://www.ahotu.com/robots.txt`
liefert HTTP 403 mit einer Cloudflare-"Just a moment..."-JavaScript-
Challenge-Seite statt Klartext - die Domain ist komplett hinter einem
aktiven Bot-Erkennungsmechanismus, der automatisierte Anfragen ohne
Browser-JS-Ausführung pauschal aussperrt, noch bevor überhaupt geprüft
werden kann, was robots.txt erlauben würde. Diese Challenge gezielt zu
umgehen (z. B. durch Nachbau des Browser-Verhaltens oder Lösen des
Challenge-Tokens) wäre eine Umgehung einer ausdrücklichen technischen
Zugriffssperre und damit keine legitime Auslegung von "automatisiertes
Auslesen ist nicht explizit verboten" - das macht dieses Projekt bewusst
nicht. `ahotu.com` wird deshalb aktuell NICHT von `update_events.py` mit
produktiven Daten befüllt; das Skript bleibt als dokumentierte Vorlage
im Repo, falls sich das künftig ändert (z. B. über einen offiziellen
API-Zugang).

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
    print(
        "⏭  ahotu_scraper.py: bewusst übersprungen, OHNE die Seite abzurufen. "
        "Schon ahotu.com/robots.txt liefert HTTP 403 mit einer aktiven "
        "Cloudflare-Bot-Challenge statt Klartext - siehe Docstring oben. "
        "events.json bleibt unverändert."
    )
    sys.exit(0)
