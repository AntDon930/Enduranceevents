#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runningcompany_scraper.py
============================

Liest Lauf-Events vom Laufkalender auf
https://www.runningcompany.de/runners-high/laufkalender/ aus und ergänzt
sie in `events.json` (siehe `scraper_lib.py` für die gemeinsame Logik).

WICHTIG: Netzwerkzugriff auf runningcompany.de war in der
Entwicklungsumgebung blockiert – nicht gegen die echte Seite getestet.

Besonderheit dieser Seite: Die vom Nutzer angegebene URL enthält ein
`#januar`-Fragment (https://.../laufkalender/#januar) – das deutet darauf
hin, dass die Seite nach Monaten sortiert/gegliedert ist, entweder als
eine lange Seite mit Sprungankern (dann liefert ein normaler Abruf ALLE
Monate auf einmal, kein Problem) oder als JavaScript-gesteuerte
Tab-Ansicht, bei der nur der aktuell sichtbare Monat im initialen HTML
steht (dann fehlen ggf. Events anderer Monate im HTML-Fallback-Ergebnis
und `--render-js` wäre nötig, ggf. sogar mit Klick-Interaktion pro
Tab – das müsste dann in `scraper_lib.fetch_rendered_html` erweitert
werden, aktuell lädt es nur die Seite, klickt aber keine Tabs). Die
Fragment-URL selbst (`#...`) wird beim Laden ignoriert
(CONFIG.calendar_url enthält bewusst kein Fragment, da HTTP-Requests
Fragmente ohnehin nicht an den Server senden).

Nutzung: `python3 scripts/runningcompany_scraper.py --help`.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import SiteConfig, run_scraper_cli  # noqa: E402

CONFIG = SiteConfig(
    base_url="https://www.runningcompany.de",
    calendar_url="https://www.runningcompany.de/runners-high/laufkalender/",
    default_art1="Laufen",
    note="runningcompany_scraper.py: nicht gegen die echte Seite getestet. "
         "Die Original-URL hatte ein #januar-Fragment (Monats-Tabs?) - "
         "falls Events fehlen, könnte die Seite die Monate per JS "
         "nachladen, siehe Docstring.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
