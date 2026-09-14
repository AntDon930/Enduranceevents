#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planetmarathon_scraper.py
============================

Liest Marathon-Events von http://www.planet-marathon.de/marathon_d.html
aus und ergänzt sie in `events.json` (siehe `scraper_lib.py` für die
gemeinsame Logik).

WICHTIG: Netzwerkzugriff auf planet-marathon.de war in der
Entwicklungsumgebung blockiert – nicht gegen die echte Seite getestet.

Besonderheiten dieser Seite:
- Nur **http://**, kein https – `requests` kommt damit problemlos klar,
  aber falls die Seite serverseitig auf https umleitet, folgt `requests`
  dem automatisch (Redirects sind standardmäßig aktiv).
- Der Dateiname (`marathon_d.html`, kein CMS-Pfad wie bei den anderen
  Seiten) deutet stark auf eine ältere, statische HTML-Seite hin (der
  Stil vieler Marathon-/Laufsport-Linklisten aus den 2000er-Jahren).
  Solche Seiten nutzen oft schlichte `<table>`-Layouts OHNE CSS-Klassen
  oder gar `<font>`-Tags statt moderner Selektoren wie `.event-card` –
  die generischen `HTML_FALLBACK_SELECTORS` aus `scraper_lib.py` greifen
  bei so einer Seite mit hoher Wahrscheinlichkeit ins Leere (0 Treffer).
  **TODO**: Falls JSON-LD und der generische HTML-Fallback beide 0
  Events liefern, lohnt sich hier eher ein bewusst bespoke Parser statt
  CSS-Selektoren – z. B. mit `soup.find_all("table")` und
  `table.find_all("tr")`, wobei jede Zeile positionell (per
  `row.find_all("td")[N].get_text()`) statt über Klassennamen
  ausgelesen wird. Da unbekannt ist, wie viele Spalten es gibt und in
  welcher Reihenfolge (Datum/Name/Ort/Land?), ist das ohne Blick auf die
  echte Seite nicht seriös vorwegzunehmen – bitte den Seitenquelltext
  einmal ansehen und `HTML_FALLBACK_SELECTORS`/diesen Kommentar
  entsprechend ersetzen.
- Vermutlich ausschließlich Marathons (art2 daher meist "Straße",
  laenge_km meist 42.2 km) – CONFIG nutzt trotzdem die volle
  Distanz-/Kategorie-Erkennung aus `scraper_lib.py`, falls die Seite
  auch andere Distanzen (Halbmarathon o. ä.) auflistet.

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
    note="planetmarathon_scraper.py: nicht gegen die echte Seite getestet. "
         "Vermutlich alte, klassenlose HTML-Tabellenseite - generische "
         "CSS-Selektoren finden dort mit hoher Wahrscheinlichkeit nichts, "
         "ein bespoke Tabellen-Parser wäre dann nötig. Siehe Docstring.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
