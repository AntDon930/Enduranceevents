#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_events.py
===================

Hauptskript: führt alle Scraper-Skripte in diesem Verzeichnis (Namensmuster
`*_scraper.py`, z. B. `laufkalender_scraper.py`, `ironman_scraper.py`)
nacheinander aus und führt ihre Ergebnisse in einer gemeinsamen
`events.json` zusammen.

Wie die Zusammenführung funktioniert
--------------------------------------
Jedes Scraper-Skript dedupliziert sein Ergebnis bereits selbst (Abgleich
über Name + Startdatum) und schreibt direkt in `events.json`. Die
"Zusammenführung" hier entsteht einfach dadurch, dass die Skripte
nacheinander dieselbe Datei lesen und aktualisieren: Skript 2 sieht damit
automatisch die von Skript 1 hinzugefügten Events und dedupliziert
dagegen, Skript 3 gegen die Ergebnisse von 1 und 2, usw. Ein einzelnes
fehlschlagendes Skript (z. B. weil eine Quelle gerade nicht erreichbar
ist oder ihre robots.txt den Zugriff verbietet) bricht den Gesamtlauf
NICHT ab – die übrigen Skripte laufen trotzdem, und die Ergebnisse der
erfolgreichen Skripte werden übernommen. Am Ende steht eine Zusammen-
fassung, welche Skripte erfolgreich waren.

Neue Scraper hinzufügen
------------------------
Einfach eine Datei `scripts/<irgendwas>_scraper.py` mit demselben
CLI-Vertrag wie die bestehenden Skripte anlegen (mindestens
`--events-json PATH` und `--dry-run` unterstützen, Exit-Code 0 bei
Erfolg) – sie wird automatisch erkannt und mit ausgeführt, ganz ohne
Änderung an diesem Skript. `SCRIPT_ORDER` unten ist nur für eine
lesbare, deterministische Log-Reihenfolge der bekannten Skripte; alles
Weitere wird alphabetisch angehängt.

Nutzung
-------
    python3 scripts/update_events.py                        # echter Lauf
    python3 scripts/update_events.py --dry-run               # nichts verändern/committen
    python3 scripts/update_events.py --list                  # gefundene Scraper anzeigen
    python3 scripts/update_events.py --only ironman_scraper.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
EVENTS_JSON_PATH = REPO_ROOT / "events.json"

# Nur für die Log-Reihenfolge relevant – neue Scraper müssen hier NICHT
# eingetragen werden, sie werden automatisch (alphabetisch) angehängt.
SCRIPT_ORDER = [
    "laufkalender_scraper.py",
    "ironman_scraper.py",
]

# Zusätzliche, feste CLI-Argumente für einzelne Skripte, z. B. um
# --include-all-europe für ironman_scraper.py dauerhaft zu aktivieren.
# Standardmäßig leer (nutzt die Skript-eigenen Defaults).
SCRIPT_EXTRA_ARGS: dict[str, list[str]] = {
    # "ironman_scraper.py": ["--include-all-europe"],
}


def discover_scripts() -> list[Path]:
    all_scrapers = sorted(SCRIPTS_DIR.glob("*_scraper.py"))
    ordered = [SCRIPTS_DIR / name for name in SCRIPT_ORDER if (SCRIPTS_DIR / name) in all_scrapers]
    remaining = [p for p in all_scrapers if p not in ordered]
    return ordered + remaining


def count_events(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return 0


def run_script(script: Path, events_json: Path, dry_run: bool, extra_args: list[str]) -> bool:
    cmd = [sys.executable, str(script), "--events-json", str(events_json)]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(extra_args)

    print(f"\n{'=' * 70}\n→ Starte {script.name}\n  Befehl: {' '.join(cmd)}\n{'=' * 70}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    success = result.returncode == 0
    status = "✅ erfolgreich" if success else f"❌ fehlgeschlagen (exit code {result.returncode})"
    print(f"← {script.name}: {status}")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Führt alle Scraper-Skripte (scripts/*_scraper.py) nacheinander "
                     "aus und führt die Ergebnisse in events.json zusammen."
    )
    parser.add_argument(
        "--events-json", type=Path, default=EVENTS_JSON_PATH,
        help=f"Pfad zur events.json (Standard: {EVENTS_JSON_PATH})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="An alle Scraper durchgereicht: events.json NICHT verändern.",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Nur die gefundenen Scraper-Skripte auflisten, nichts ausführen.",
    )
    parser.add_argument(
        "--only", type=str, default=None,
        help="Nur ein einzelnes Scraper-Skript ausführen (Dateiname, z. B. ironman_scraper.py).",
    )
    args = parser.parse_args()

    scripts = discover_scripts()

    if args.list:
        print("Gefundene Scraper-Skripte (Ausführungsreihenfolge):")
        for s in scripts:
            print(f"  - {s.name}")
        return

    if args.only:
        scripts = [s for s in scripts if s.name == args.only]
        if not scripts:
            print(f"❌ Kein Scraper-Skript namens '{args.only}' in {SCRIPTS_DIR} gefunden.")
            sys.exit(1)

    if not scripts:
        print(f"⚠ Keine Scraper-Skripte ({SCRIPTS_DIR}/*_scraper.py) gefunden. Nichts zu tun.")
        return

    before = count_events(args.events_json)
    print(f"events.json vor dem Update: {before} Events.")
    print(
        f"Werde {len(scripts)} Scraper-Skript(e) nacheinander ausführen: "
        f"{', '.join(s.name for s in scripts)}"
    )

    results: dict[str, bool] = {}
    for script in scripts:
        extra_args = SCRIPT_EXTRA_ARGS.get(script.name, [])
        results[script.name] = run_script(script, args.events_json, args.dry_run, extra_args)

    after = count_events(args.events_json)

    print(f"\n{'=' * 70}\nZusammenfassung\n{'=' * 70}")
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")

    if not args.dry_run:
        diff = after - before
        sign = "+" if diff >= 0 else ""
        print(f"\nevents.json: {before} -> {after} Events ({sign}{diff}).")
    else:
        print("\n--dry-run aktiv: events.json wurde nicht verändert.")

    failed = [name for name, ok in results.items() if not ok]
    if failed and len(failed) == len(results):
        print(f"\n❌ Alle Scraper-Skripte sind fehlgeschlagen: {', '.join(failed)}.")
        sys.exit(1)
    elif failed:
        print(
            f"\n⚠ {len(failed)} von {len(results)} Scraper-Skript(en) fehlgeschlagen: "
            f"{', '.join(failed)}. Die Ergebnisse der übrigen Skripte wurden trotzdem "
            "übernommen. (Bewusst kein Gesamt-Fehlschlag: eine einzelne blockierte/"
            "geänderte Quelle soll den täglichen Lauf nicht komplett rot färben.)"
        )
    else:
        print("\n✅ Alle Scraper-Skripte erfolgreich.")


if __name__ == "__main__":
    main()
