#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_web_data.py
=================

Schreibt aus `events.json` die kompakte Fassung `events.web.json`, die
die Seiten zuerst laden (`EF.loadEvents()` in filters.js). Aufruf:

    python3 scripts/build_web_data.py            # events.web.json schreiben
    python3 scripts/build_web_data.py --pruefen  # nur Rückweg prüfen, nichts schreiben

Warum: `events.json` ist lesbar und einzeln diffbar - das muss so
bleiben, der wöchentliche Commit soll durchsehbar sein. Für den Browser
ist dieselbe Datei aber teuer: Bei über 20.000 Events sind es ~830 KB
gzip, unter Handy-Bedingungen 5,4 s (README, "Vorbereitung auf über
20.000 Events"). Was zählt, ist die STRUKTUR, nicht der Schlüsselname:
ein Array je Feld, und je Feld ein Wörterbuch der vorkommenden Werte
plus Zahlen-Indizes je Zeile. Gemessen: 300 statt 830 KB gzip.

Das Format (`endurance-web-1`):

    {"format": "endurance-web-1", "stand": "2026-09-21", "anzahl": 3861,
     "felder": ["land", "name", ...],
     "werte":  {"land": ["Deutschland", "Österreich"], ...},   # Wörterbuch je Feld
     "zeilen": {"land": [0, 0, 1, ...], ...}}                 # Index je Zeile, -1 = Feld fehlt

Drei Entscheidungen:

- **Verlustfrei.** `dekodieren(kodieren(events)) == events`, Zeile für
  Zeile - auch der Unterschied zwischen "Feld fehlt" (Index -1) und
  "Feld ist null" (null steht als Wert im Wörterbuch). Der Test
  `test_web_data` prüft den Rückweg in Python UND mit dem echten
  Dekodierer aus filters.js in node; ein Format, das etwas verliert,
  fällt sofort auf.
- **Jedes Feld bekommt ein Wörterbuch**, auch Name und Link. Ein Name
  kommt je Strecke einmal vor, ein Ort hundertmal - gzip macht aus den
  Index-Arrays ohnehin wenig, und eine Regel "Wörterbuch nur ab x %
  Wiederholung" wäre eine zweite Codepfad-Variante für nichts.
- **Nicht committet.** Die Datei entsteht im Pages-Workflow vor dem
  Upload (und im Rauchtest); sie steht in .gitignore. Committet wäre
  sie in jedem wöchentlichen Datenlauf ein 2-MB-Klotz, der sich komplett
  ändert, sobald ein Event dazukommt. Fehlt sie (lokal mit
  `python3 -m http.server`), fällt der Loader auf `events.json` zurück.

`stand` ist der Tag des letzten Commits, der `events.json` geändert hat
(`git log`), sonst der heutige Tag - die Werkzeugleiste zeigt ihn als
"Stand: …". Vorher kam er aus dem Last-Modified-Header der Datei; bei
einer erzeugten Datei wäre das der Deploy-Zeitpunkt, nicht der Datenstand.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

FORMAT = "endurance-web-1"
WURZEL = Path(__file__).resolve().parent.parent
EVENTS = WURZEL / "events.json"
ZIEL = WURZEL / "events.web.json"


def kodieren(events: list[dict], stand: str | None = None) -> dict:
    """Spalten + Wörterbuch je Feld; Reihenfolge der Felder = erstes Auftreten."""
    felder: list[str] = []
    for e in events:
        for k in e:
            if k not in felder:
                felder.append(k)
    werte: dict[str, list] = {}
    zeilen: dict[str, list[int]] = {}
    for f in felder:
        woerterbuch: list = []
        # Ein dict als Index geht nicht für null/float-Mischungen sauber
        # (json-Schlüssel), deshalb der Umweg über den JSON-Text als Schlüssel.
        index: dict[str, int] = {}
        spalte: list[int] = []
        for e in events:
            if f not in e:
                spalte.append(-1)
                continue
            schluessel = json.dumps(e[f], ensure_ascii=False, sort_keys=True)
            nr = index.get(schluessel)
            if nr is None:
                nr = len(woerterbuch)
                index[schluessel] = nr
                woerterbuch.append(e[f])
            spalte.append(nr)
        werte[f] = woerterbuch
        zeilen[f] = spalte
    return {"format": FORMAT, "stand": stand or datenstand(), "anzahl": len(events),
            "felder": felder, "werte": werte, "zeilen": zeilen}


def dekodieren(daten: dict) -> list[dict]:
    """Der Rückweg - dieselbe Logik wie `decodeWebData()` in filters.js."""
    if daten.get("format") != FORMAT:
        raise ValueError(f"unbekanntes Format: {daten.get('format')!r}")
    n = daten["anzahl"]
    out: list[dict] = [{} for _ in range(n)]
    for f in daten["felder"]:
        w = daten["werte"][f]
        for i, k in enumerate(daten["zeilen"][f]):
            if k >= 0:
                out[i][f] = w[k]
    return out


def datenstand() -> str:
    """Tag des letzten Commits an events.json (ISO), sonst heute."""
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "events.json"],
                           cwd=WURZEL, capture_output=True, text=True, timeout=30)
        tag = r.stdout.strip()
        if r.returncode == 0 and len(tag) == 10:
            return tag
    except (OSError, subprocess.SubprocessError):
        pass
    return dt.date.today().isoformat()


def schreiben(ziel: Path = ZIEL) -> dict:
    events = json.loads(EVENTS.read_text(encoding="utf-8"))
    daten = kodieren(events)
    if dekodieren(daten) != events:
        raise SystemExit("Rückweg verliert etwas - events.web.json NICHT geschrieben")
    ziel.write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return daten


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="events.web.json aus events.json erzeugen")
    p.add_argument("--pruefen", action="store_true", help="nur den Rückweg prüfen, nichts schreiben")
    p.add_argument("--ziel", default=str(ZIEL))
    args = p.parse_args(argv)
    events = json.loads(EVENTS.read_text(encoding="utf-8"))
    if args.pruefen:
        ok = dekodieren(kodieren(events)) == events
        print("Rückweg verlustfrei" if ok else "Rückweg VERLIERT etwas")
        return 0 if ok else 1
    ziel = Path(args.ziel)
    daten = schreiben(ziel)
    print(f"{ziel.name}: {daten['anzahl']} Events, {ziel.stat().st_size // 1024} KB "
          f"(events.json: {EVENTS.stat().st_size // 1024} KB), Stand {daten['stand']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
