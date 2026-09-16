#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_ics.py
============

Schreibt für jedes Event in `events.json` eine fertige `.ics`-Datei nach
`kalender/`. Aufruf:

    python3 scripts/build_ics.py            # erzeugen und Altes aufräumen
    python3 scripts/build_ics.py --dry-run  # nur berichten

Warum feste Dateien und nicht im Browser erzeugt: Auf iPhone und iPad
übergibt Safari einen Termin nur dann an den Kalender, wenn die Datei
wirklich vom Server kommt - mit `Content-Type: text/calendar`. Alles, was
die Seite selbst baut (Blob, data-URI, sogar eine vom Service Worker
erfundene Antwort), behandelt iOS als Download: die Datei landete als
"Unknown.ics" in den Dateien, und die Teilen-Liste bot keinen Kalender
an. GitHub Pages liefert eine echte `.ics` dagegen mit dem richtigen Typ
aus.

Der Preis sind viele kleine Dateien (eine je Event, ~500 Byte). Das ist
eine bewusste Entscheidung des Nutzers vom 16.09.2026.

Alle Termine sind **ganztägig**: eine verlässliche Startzeit liefert
keine Quelle, und ein ganztägiger Eintrag behauptet keine Uhrzeit, die
wir nicht kennen. `DTEND` ist im iCalendar-Format (RFC 5545) exklusiv,
steht also einen Tag nach dem letzten Veranstaltungstag - ohne dieses
+1 fehlt der letzte Tag.

**Der Dateiname muss mit `icsFileName()` in `events.html` überein-
stimmen**, sonst zeigt der Knopf auf eine Datei, die es nicht gibt.
`scripts/test_scraper_lib.py` prüft beide Umsetzungen gegeneinander
(ruft dafür node auf).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON = REPO_ROOT / "events.json"
ICS_DIR = REPO_ROOT / "kalender"

MAX_SLUG_LEN = 48


def slugify(text: str) -> str:
    """Nur Kleinbuchstaben, Ziffern und Bindestriche.

    Umlaute werden zerlegt und ihre Zeichen verworfen (ä -> a), damit der
    Dateiname in jeder Umgebung gleich heißt. Dieselbe Regel steht in
    `events.html` (`icsFileName`) - beide werden gegeneinander getestet.
    """
    zerlegt = unicodedata.normalize("NFD", text or "")
    ohne_akzente = "".join(c for c in zerlegt if not unicodedata.combining(c))
    klein = ohne_akzente.lower()
    # ß wird von NFD nicht zerlegt und hat kein Basiszeichen - explizit.
    klein = klein.replace("ß", "ss")
    nur_erlaubt = re.sub(r"[^a-z0-9]+", "-", klein)
    return nur_erlaubt.strip("-")[:MAX_SLUG_LEN].strip("-")


def masszahl(event: dict) -> str:
    """Der Teil des Dateinamens, der die Strecken einer Veranstaltung
    auseinanderhält: die Distanz, sonst die Dauer, sonst "x"."""
    km = event.get("laenge_km")
    if isinstance(km, (int, float)):
        return f"{round(float(km), 1):g}km".replace(".", "-")
    dauer = event.get("dauer_h")
    if isinstance(dauer, (int, float)):
        return f"{round(float(dauer), 1):g}h".replace(".", "-")
    return "x"


def ics_dateiname(event: dict) -> str:
    """`<datum>-<name>-<distanz>-<ort>.ics`, z. B.
    `2027-06-26-hofer-backyard-ultra-x-hof.ics`.

    Der Ort gehört dazu, weil Name + Datum + Distanz nicht eindeutig sind:
    Der "Königsforst-Marathon" am 14.03.2027 steht mit 42,2 km zweimal in
    den Daten, einmal für Bensberg und einmal für Bergisch Gladbach
    (dasselbe Rennen aus zwei Quellen, das die Duplikat-Erkennung nicht
    zusammengeführt hat). Ohne den Ort hätte eine der beiden Zeilen keine
    Datei - und ihr Kalender-Knopf zeigte ins Leere.

    Der Name wird NUR aus Feldern des Events gebildet, damit
    `icsFileName()` in events.html ihn ohne Zusatzwissen ausrechnen kann."""
    datum = event.get("datum_start") or "ohne-datum"
    teile = [datum, slugify(event.get("name") or "event"), masszahl(event)]
    ort = slugify(event.get("standort") or "")
    if ort:
        teile.append(ort)
    return "-".join(teile) + ".ics"


# --------------------------------------------------------------------------
# iCalendar
# --------------------------------------------------------------------------

def ics_escape(text) -> str:
    """RFC 5545, 3.3.11: Backslash, Semikolon, Komma und Umbrüche maskieren."""
    return (str(text or "")
            .replace("\\", "\\\\")
            .replace(";", "\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n"))


def ics_fold(zeile: str) -> str:
    """Zeilen über 75 Oktette faltet das Format mit einem Leerzeichen am
    Anfang der Folgezeile. Manche Kalender stolpern über lange Zeilen."""
    if len(zeile) <= 74:
        return zeile
    teile = [zeile[:74]]
    rest = zeile[74:]
    while len(rest) > 73:
        teile.append(" " + rest[:73])
        rest = rest[73:]
    if rest:
        teile.append(" " + rest)
    return "\r\n".join(teile)


def plus_ein_tag(iso: str) -> str:
    j, m, d = (int(x) for x in iso.split("-"))
    return (date(j, m, d) + timedelta(days=1)).isoformat()


def laenge_text(event: dict) -> str:
    km = event.get("laenge_km")
    if isinstance(km, (int, float)):
        gerundet = round(float(km), 1)
        return f"{gerundet:g} km"
    dauer = event.get("dauer_h")
    if isinstance(dauer, (int, float)):
        return f"{round(float(dauer), 1):g} h"
    return "-"


# Wettbewerbs-Label, das nur die Distanz oder die Dauer wiederholt
# ("6 km", "24h", "42,2 km"). Es gehört nicht in den Titel: Die Länge
# steht ohnehin in der Beschreibung, und die Quellen runden dabei
# unterschiedlich - ein Titel "16. AOK Firmenlauf Waiblingen – 6 km" bei
# 5,5 km Streckenlänge sieht nach einem Widerspruch aus. events.html
# blendet solche Label aus demselben Grund aus (displayWettbewerb).
_NUR_MASSZAHL = re.compile(r"^\s*\d+([.,]\d+)?\s*(km|k|h|std\.?|stunden|meilen|mi)\s*$", re.I)


def build_ics(event: dict, stempel: str) -> str:
    start = event["datum_start"]
    ende = event.get("datum_ende") or start
    if ende < start:
        ende = start
    wb = (event.get("wettbewerb") or "").strip()
    if wb and _NUR_MASSZAHL.match(wb):
        wb = ""
    titel = f"{event['name']} – {wb}" if wb else event["name"]
    beschreibung = [
        f"Sportart: {event.get('art1') or '-'}"
        + (f" / {event['art2']}" if event.get("art2") else ""),
        f"Länge: {laenge_text(event)}",
    ]
    if event.get("veranstalter_url"):
        beschreibung.append(event["veranstalter_url"])

    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Ausdauersport-Events//kalender//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{ics_dateiname(event)[:-4]}@antdon930.github.io",
        f"DTSTAMP:{stempel}",
        f"DTSTART;VALUE=DATE:{start.replace('-', '')}",
        f"DTEND;VALUE=DATE:{plus_ein_tag(ende).replace('-', '')}",
        f"SUMMARY:{ics_escape(titel)}",
        f"LOCATION:{ics_escape(event.get('standort') or '')}"
        + (f"\\, {ics_escape(event['land'])}" if event.get("land") else ""),
        f"DESCRIPTION:{ics_escape(chr(10).join(beschreibung))}",
        "TRANSP:TRANSPARENT",
    ]
    if event.get("veranstalter_url"):
        zeilen.append(f"URL:{ics_escape(event['veranstalter_url'])}")
    zeilen += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(ics_fold(z) for z in zeilen) + "\r\n"


# --------------------------------------------------------------------------
# Hauptlauf
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument("--events-json", type=Path, default=EVENTS_JSON)
    parser.add_argument("--out-dir", type=Path, default=ICS_DIR)
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur berichten, nichts schreiben oder löschen.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    events = json.loads(args.events_json.read_text(encoding="utf-8"))
    # Ein Zeitstempel für den ganzen Lauf: sonst änderte sich JEDE Datei
    # bei jedem Aufruf, und der wöchentliche Commit wäre ein Diff über
    # tausende Dateien ohne inhaltliche Änderung.
    stempel = "20260101T000000Z"

    geplant: dict[str, str] = {}
    kollisionen: list[str] = []
    for event in events:
        if not event.get("datum_start") or not event.get("name"):
            continue
        name = ics_dateiname(event)
        if name in geplant:
            kollisionen.append(name)
            continue
        geplant[name] = build_ics(event, stempel)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    vorhanden = {p.name for p in args.out_dir.glob("*.ics")}

    neu = sorted(set(geplant) - vorhanden)
    weg = sorted(vorhanden - set(geplant))
    geaendert = []
    for name in sorted(set(geplant) & vorhanden):
        # newline="" beim LESEN ist wichtig: Die Dateien tragen CRLF (so
        # verlangt es RFC 5545). Ohne das übersetzt Python beim Lesen
        # jedes CRLF zu \n, der Vergleich schlug also IMMER fehl - jeder
        # Lauf schrieb alle 4.154 Dateien neu und meldete sie als
        # "geändert", obwohl sich nichts geändert hatte.
        with open(args.out_dir / name, encoding="utf-8", newline="") as fh:
            if fh.read() != geplant[name]:
                geaendert.append(name)

    if not args.dry_run:
        for name in neu + geaendert:
            (args.out_dir / name).write_text(geplant[name], encoding="utf-8", newline="")
        for name in weg:
            (args.out_dir / name).unlink()

    print(f"kalender/: {len(geplant)} Dateien "
          f"(+{len(neu)} neu, {len(geaendert)} geändert, -{len(weg)} entfernt)")
    if kollisionen:
        print(f"⚠ {len(kollisionen)} Event(s) mit gleichem Dateinamen übersprungen "
              f"(gleicher Name, Tag und Distanz):")
        for name in kollisionen[:10] if args.quiet else kollisionen:
            print(f"  - {name}")
    if args.dry_run:
        print("--dry-run aktiv: nichts geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
