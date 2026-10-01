#!/usr/bin/env python3
"""Hängt an die geteilten Skripte/Stylesheets in den HTML-Dateien einen
Inhalts-Stempel (`?v=<8 Hex>`) an.

Warum: GitHub Pages liefert jede Datei mit `Cache-Control: max-age=600`.
Ein Browser kann deshalb die NEUE `events.html` mit einer bis zu zehn
Minuten alten `filters.js` kombinieren. Genau das ist passiert: Die alte
Datei kannte `EF.uniqueSorted` noch nicht, das Inline-Skript brach in der
ersten Zeile ab - die Seite blieb leer (blauer Kopf, sonst nichts).

Mit dem Stempel ändert sich die Adresse der Datei, sobald sich ihr Inhalt
ändert; der Browser MUSS sie dann neu holen. Wer eines der Module
anfasst, ruft danach:

    python3 scripts/stamp_assets.py

`scripts/test_scraper_lib.py` prüft die Stempel mit und schlägt Alarm,
wenn sie nicht zum Inhalt passen - vergessen kann man es also nicht.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Die Dateien, die mehrere Seiten gemeinsam nutzen. Nur bei denen kann ein
# halber Cache-Stand die Seite zerlegen; die Inline-Skripte stecken in der
# HTML-Datei selbst und sind damit immer passend.
ASSETS = ("site.css", "filters.js", "filter-ui.js", "filter-ui.css", "event-detail.js", "event-detail.css")

HTML_FILES = ("index.html", "events.html", "karte.html")


def stempel(pfad: Path) -> str:
    """Die ersten acht Hex-Stellen des SHA-256 über den Dateiinhalt."""
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:8]


def stempel_aller_assets() -> dict[str, str]:
    werte = {}
    for name in ASSETS:
        pfad = ROOT / name
        if pfad.exists():
            werte[name] = stempel(pfad)
    return werte


def _muster(name: str) -> re.Pattern[str]:
    # href="filters.js" / src="filters.js?v=abc12345" - mit und ohne Stempel.
    return re.compile(r'((?:src|href)=")' + re.escape(name) + r'(?:\?v=[0-9a-f]+)?(")')


def pruefe() -> list[str]:
    """Gibt eine Liste der Abweichungen zurück (leer = alles passt)."""
    soll = stempel_aller_assets()
    probleme = []
    for html in HTML_FILES:
        pfad = ROOT / html
        if not pfad.exists():
            continue
        text = pfad.read_text(encoding="utf-8")
        for name, wert in soll.items():
            for treffer in re.finditer(
                r'(?:src|href)="' + re.escape(name) + r'(\?v=([0-9a-f]+))?"', text
            ):
                ist = treffer.group(2)
                if ist != wert:
                    probleme.append(
                        f"{html}: {name} trägt {'?v=' + ist if ist else 'keinen Stempel'}, "
                        f"erwartet ?v={wert}"
                    )
    return probleme


def schreibe() -> int:
    soll = stempel_aller_assets()
    geaendert = 0
    for html in HTML_FILES:
        pfad = ROOT / html
        if not pfad.exists():
            continue
        text = alt = pfad.read_text(encoding="utf-8")
        for name, wert in soll.items():
            text = _muster(name).sub(rf"\g<1>{name}?v={wert}\g<2>", text)
        if text != alt:
            pfad.write_text(text, encoding="utf-8")
            geaendert += 1
            print(f"  {html} gestempelt")
    for name, wert in soll.items():
        print(f"  {name} -> ?v={wert}")
    return geaendert


def main(argv: list[str]) -> int:
    if "--check" in argv:
        probleme = pruefe()
        if probleme:
            print("Stempel passen nicht zum Inhalt:")
            for p in probleme:
                print("  " + p)
            print("\nBitte 'python3 scripts/stamp_assets.py' ausführen.")
            return 1
        print("Stempel sind aktuell.")
        return 0
    schreibe()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
