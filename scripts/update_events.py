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
über Name + Startdatum + Distanz - bewusst MIT Distanz: viele Events
bieten unter demselben Namen am selben Tag mehrere Distanzen an, z. B.
10 km, Halbmarathon UND Marathon, das sind unterschiedliche Einträge und
sollen alle erhalten bleiben) und schreibt direkt in `events.json`. Die
"Zusammenführung" hier entsteht einfach dadurch, dass die Skripte
nacheinander dieselbe Datei lesen und aktualisieren: Skript 2 sieht damit
automatisch die von Skript 1 hinzugefügten Events und dedupliziert
dagegen, Skript 3 gegen die Ergebnisse von 1 und 2, usw. Ein einzelnes
fehlschlagendes Skript (z. B. weil eine Quelle gerade nicht erreichbar
ist oder ihre robots.txt den Zugriff verbietet) bricht den Gesamtlauf
NICHT ab – die übrigen Skripte laufen trotzdem, und die Ergebnisse der
erfolgreichen Skripte werden übernommen. Am Ende steht eine Zusammen-
fassung, welche Skripte erfolgreich waren.

Optionale "Benachrichtige mich"-Anbindung (NOTIFY_WEBHOOK_URL)
------------------------------------------------------------------
Ist die Umgebungsvariable `NOTIFY_WEBHOOK_URL` gesetzt (z. B. als
GitHub-Actions-Secret, siehe `.github/workflows/update-events.yml`),
werden nach einem echten (nicht `--dry-run`) Lauf alle NEU hinzugekommenen
Events (Vorher-/Nachher-Vergleich über dieselbe Name+Datum+Distanz-
Identität wie beim Dedupe) per HTTPS-POST an diese URL gemeldet - gedacht
für die Cloud Function in `functions/index.js`, die sie gegen gespeicherte
Filterabos (siehe `auth.js`/events.html "Benachrichtige mich") prüft und
bei einem Treffer eine E-Mail auslöst. Optional zusätzlich
`NOTIFY_WEBHOOK_SECRET` (wird als Header `X-Notify-Secret` mitgeschickt).
Ohne gesetztes `NOTIFY_WEBHOOK_URL` passiert hier schlicht nichts - kein
Fehler, kein Effekt auf den restlichen Lauf.

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
import os
import subprocess
import sys
import urllib.error
import urllib.request
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
    #
    # Hinweis zur Laufzeit: laufkalender_scraper.py und
    # runninglife_scraper.py rufen zusätzlich die Detailseite jedes Events
    # ab - nur dort stehen die einzelnen Wettbewerbe, das Land und die
    # offizielle Veranstalter-Seite. Das sind rund 800 Requests mit der aus
    # robots.txt abgeleiteten Pause, also grob 30 Minuten. Mit
    # ["--no-details"] ließe sich das abschalten, dann fehlen aber genau
    # diese Angaben (siehe README, "Datenqualität").
    #
    # running.life: Kalendertiefe ausgeschöpft. Die Paginierung endet bei
    # Seite ~101 (rund 2000 deutsche Events); 110 ist der Puffer darüber,
    # die Schleife stoppt von selbst, sobald es keine nächste Seite mehr
    # gibt. Vorher standen hier nur die 10 Standardseiten, also ~200
    # Events - und für die restlichen fehlte damit auch die offizielle
    # Veranstalter-Seite, die running.life pro Event kennt.
    "runninglife_scraper.py": ["--max-pages", "110"],
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


def load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def event_identity(event: dict) -> tuple:
    """Identisch zu scraper_lib.dedupe_key(), aber ohne Import (dieses
    Skript startet die Scraper als eigene Subprozesse statt sie zu
    importieren) - Name + Startdatum + gerundete Distanz."""
    laenge_km = event.get("laenge_km")
    rounded_km = round(laenge_km, 1) if isinstance(laenge_km, (int, float)) else None
    return (str(event.get("name", "")).strip().casefold(), event.get("datum_start"), rounded_km)


def run_cleanup(events_json: Path) -> bool:
    """Führt scripts/clean_events.py aus: wendet manuelle Korrekturen an,
    entfernt zu kurze Laufevents und führt Duplikate zusammen, die
    verschiedene Quellen unter abweichenden Namen geliefert haben. Läuft
    NACH allen Scrapern, weil Duplikate erst durch das Zusammenspiel
    mehrerer Quellen entstehen. Ein Fehler hier bricht den Gesamtlauf
    nicht ab - events.json ist dann nur unbereinigt."""
    script = SCRIPTS_DIR / "clean_events.py"
    if not script.exists():
        return True
    cmd = [sys.executable, str(script), "--events-json", str(events_json), "--quiet"]
    print(f"\n{'=' * 70}\n→ Aufräumen: {script.name}\n{'=' * 70}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"⚠ {script.name} fehlgeschlagen (exit code {result.returncode}) – "
              "events.json bleibt unbereinigt, der Lauf gilt trotzdem als erfolgreich.")
        return False
    return True


def notify_webhook_of_new_events(new_events: list[dict]) -> None:
    """Meldet neu hinzugekommene Events (best-effort, siehe
    functions/index.js) an eine optionale Cloud Function, die sie gegen
    gespeicherte "Benachrichtige mich"-Filterabos prüft und passende
    E-Mails auslöst. Ohne gesetztes NOTIFY_WEBHOOK_URL passiert nichts;
    ein Fehler hier lässt den Gesamtlauf NICHT fehlschlagen - das
    Scrapen/Aktualisieren von events.json ist die Kernaufgabe, die
    Benachrichtigung ein optionales Extra."""
    webhook_url = os.environ.get("NOTIFY_WEBHOOK_URL")
    if not webhook_url or not new_events:
        return

    print(f"\n→ Melde {len(new_events)} neue(s) Event(s) an {webhook_url} ...")
    headers = {"Content-Type": "application/json"}
    secret = os.environ.get("NOTIFY_WEBHOOK_SECRET")
    if secret:
        headers["X-Notify-Secret"] = secret

    body = json.dumps({"events": new_events}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  ✓ Webhook antwortete mit HTTP {resp.status}.")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"  ⚠ Webhook-Aufruf fehlgeschlagen (ignoriert, events.json bleibt trotzdem gültig): {exc}")


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

    before_events = load_events(args.events_json)
    before = len(before_events)
    print(f"events.json vor dem Update: {before} Events.")
    print(
        f"Werde {len(scripts)} Scraper-Skript(e) nacheinander ausführen: "
        f"{', '.join(s.name for s in scripts)}"
    )

    results: dict[str, bool] = {}
    for script in scripts:
        extra_args = SCRIPT_EXTRA_ARGS.get(script.name, [])
        results[script.name] = run_script(script, args.events_json, args.dry_run, extra_args)

    if not args.dry_run:
        # Aufräumen VOR dem Vorher-/Nachher-Vergleich: sonst würden Events
        # gemeldet, die die Duplikat-Zusammenführung gleich wieder entfernt.
        run_cleanup(args.events_json)

    after_events = load_events(args.events_json)
    after = len(after_events)

    if not args.dry_run:
        before_identities = {event_identity(e) for e in before_events}
        new_events = [e for e in after_events if event_identity(e) not in before_identities]
        notify_webhook_of_new_events(new_events)

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
