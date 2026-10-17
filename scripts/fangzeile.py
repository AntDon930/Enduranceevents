#!/usr/bin/env python3
"""
scripts/fangzeile.py
====================

Eine erfundene Zeile in der Event-Datenbank, an der sich eine Kopie
erkennen lässt (vom Nutzer am 14.10.2026 gewünscht: „Was hält jemanden
davon ab, alle meine Events auszulesen und die Seite zu kopieren?").
Kartenverlage machen das seit jeher mit erfundenen Straßen: Taucht die
Zeile auf einer fremden Seite auf, ist sie von hier abgeschrieben –
denn außer in unseren Datendateien gibt es sie nirgends.

- **Auf der Seite nie sichtbar**: Die Zeile trägt `pruefung_offen`, und
  `EF.loadEvents()` lädt solche Zeilen nicht (Liste, Karte, Startseite).
  Abo-Mails (`update_events.py`) und Instagram (`insta_inhalte.py`)
  übergehen sie aus demselben Grund. In `events.json`,
  `events.web.json` und `kalender/` steht sie – genau dort, wo jemand
  abschreibt.
- **Unsichtbar für das Aufräumen**: `clean_events.py` nimmt sie beim
  Laden heraus (`entfernen`) und setzt sie als letzten Schritt wieder
  ein (`einsetzen`). Kein Override, kein Gedächtnis, keine
  Duplikat-Erkennung, keine Korrekturliste sieht sie.
- **Der Termin wandert mit**: immer der zweite Samstag des Monats acht
  Monate voraus – nie vergangen, und events.json ändert sich dadurch
  höchstens einmal im Monat um diese eine Zeile.
- **Harmlos**: Kein fremder Veranstalter, keine fremde Seite – der
  Veranstalterlink zeigt auf endurance-events.de. Wer der Kopie folgt,
  landet bei uns.

Grenze: Das Repository ist öffentlich, wer den Code liest, findet die
Zeile hier. Gefangen wird, wer die Seite oder ihre Datendateien
abgreift, ohne den Code zu lesen – also der übliche Fall.

Prüfen, ob eine fremde Seite kopiert: nach „Großweiler Moosrunde“
suchen (Websuche, oder in deren Daten).
"""
from __future__ import annotations

import datetime as dt

NAME = "Großweiler Moosrunde"
STANDORT = "Großweil"


def termin(heute: dt.date) -> dt.date:
    """Zweiter Samstag des Monats acht Monate nach `heute`."""
    m = heute.month - 1 + 8
    erster = dt.date(heute.year + m // 12, m % 12 + 1, 1)
    erster_samstag = erster + dt.timedelta(days=(5 - erster.weekday()) % 7)
    return erster_samstag + dt.timedelta(days=7)


def zeile(heute: dt.date) -> dict:
    tag = termin(heute).isoformat()
    return {
        "land": "Deutschland",
        "name": NAME,
        "standort": STANDORT,
        "lat": 47.676,
        "lon": 11.301,
        "art1": "Laufen",
        "art2": "Trail",
        "datum_start": tag,
        "datum_ende": tag,
        "laenge_km": 12.4,
        "wettbewerb": "12,4 km",
        "veranstalter_url": "https://endurance-events.de/",
        "pruefung_offen": True,
    }


def ist_fangzeile(e: dict) -> bool:
    return e.get("name") == NAME and e.get("standort") == STANDORT


def entfernen(events: list[dict]) -> list[dict]:
    return [e for e in events if not ist_fangzeile(e)]


def einsetzen(events: list[dict], heute: dt.date) -> list[dict]:
    """Die Zeile (genau einmal) an ihren Platz in der Datumsfolge setzen –
    am Ende der Datei fiele sie auf."""
    events = entfernen(events)
    z = zeile(heute)
    pos = len(events)
    for i, e in enumerate(events):
        if (e.get("datum_start") or "") > z["datum_start"]:
            pos = i
            break
    return events[:pos] + [z] + events[pos:]
