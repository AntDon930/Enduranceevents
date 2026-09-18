#!/usr/bin/env python3
"""Einzelprüfung von events.json - meldet Verdachtsfälle, ändert nichts.

Warum es dieses Skript gibt
---------------------------
Die Einzelprüfung von 400 Events am 18.09.2026 hat 13 echte Fehler
zutage gefördert (siehe CLAUDE.md). Drei davon verhindert seitdem eine
Regel in `scraper_lib.py`, drei weitere meldet `clean_events.py`. Die
restlichen **fünf** fand nur ein Wegwerf-Skript, das niemand
aufgehoben hätte - beim nächsten großen Datenlauf hätte es sie nicht
mehr gegeben:

  - „BFUTR EXTREME" mit 18 km/Straße statt 105 km Trail
  - der Kinderlauf des Karlsfelder Seelaufs mit 21,1 km
  - „17. Gau-Algesheimer Alagastaluf" (Tippfehler) doppelt
  - „9 km" im Label bei 8,5 km echter Strecke
  - „ONW-Lauf Dannenberg 2025" an einem Termin im Jahr 2026

Deshalb stehen die Prüfungen jetzt hier. Sie sind bewusst
**Hinweise**, keine Korrekturen - dieselbe Linie wie bei
`clean_events.py` (siehe „Die wichtigste Lektion" im README): Zu viel
automatisch geändert ist schlimmer als eine Meldung, weil es niemand
sieht.

Abgrenzung zu clean_events.py
-----------------------------
`clean_events.py` räumt auf und prüft die Beziehungen ZWISCHEN Events
(Duplikate, widersprüchliche Koordinaten, gleiche Veranstalter-Seite).
Hier steht, was sich an einer EINZELNEN Zeile prüfen lässt: Passt die
Distanz zum Label, das Label zum Namen, der Name zum Datum, die
Koordinate zum Land.

Aufruf
------
    python3 scripts/audit_events.py                # alles
    python3 scripts/audit_events.py --ab 0 --anzahl 200
    python3 scripts/audit_events.py --quiet        # nur die Zahlen

Der Rückgabewert ist immer 0: Das hier ist ein Bericht, kein Test.
Verdachtsfälle sind normal, jeder gehört einzeln gegen die offizielle
Ausschreibung geprüft.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import EVENTS_JSON_PATH, is_portal_link  # noqa: E402

# Protokoll der Einzelprüfungen. Die Prüfung von 2.369 Veranstaltungen
# geht über mehrere Sitzungen - ohne dieses Protokoll fängt jede von
# vorn an. `--offen` blendet aus, was schon geprüft ist.
GEPRUEFT_PATH = Path(__file__).resolve().parent / "geprueft.json"


def lade_geprueft() -> dict:
    if not GEPRUEFT_PATH.exists():
        return {}
    daten = json.loads(GEPRUEFT_PATH.read_text(encoding="utf-8"))
    return {k.casefold(): v for k, v in daten.items() if k != "_readme"}


def ist_geprueft(protokoll: dict, event: dict) -> bool:
    return f"{(event.get('name') or '').strip()}|{event.get('datum_start')}".casefold() in protokoll


def zaehle_unklar(protokoll: dict) -> int:
    """Wie viele Veranstaltungen im Protokoll als 'unklar' stehen.

    'unklar' heisst: angesehen, aber an der Quelle nicht zu entscheiden.
    `--offen` blendet sie aus (sonst werden sie jede Sitzung neu
    recherchiert), deshalb nennt der Kopf ihre Zahl - sonst verschwaenden
    sie stillschweigend."""
    return sum(1 for v in protokoll.values() if v.get("ergebnis") == "unklar")

# Anmelde- und Zeitnahme-Portale, die is_portal_link() (noch) nicht
# kennt. Dort steht keine Ausschreibung, sondern ein Anmeldeformular -
# als `veranstalter_url` ist das die zweite Wahl (Datenregel 2).
WEITERE_PORTALE = ("raceresult.com", "davengo.com", "sportstiming",
                   "anmeldung", "eventfrog", "runtix", "lanet3",
                   "run-timing", "berlin-timing", "baer-service",
                   "racepedia", "mika-timing", "sportident")

# Grobe Umrisse der abgedeckten Länder (lat_min, lat_max, lon_min, lon_max).
# Absichtlich großzügig: Hier soll auffallen, wenn eine Koordinate im
# falschen LAND liegt, nicht wenn sie ein paar Kilometer danebenliegt.
LAND_BOX = {
    "Deutschland": (47.2, 55.1, 5.8, 15.1),
    "Österreich": (46.3, 49.1, 9.5, 17.2),
    "Schweiz": (45.8, 47.9, 5.9, 10.5),
}

# Ein Kinderlauf über zehn Kilometer gibt es nicht. Gemessen: Bei einer
# Schwelle von 5 km trifft die Regel vier ECHTE Jugendläufe (5,0 und
# 5,6 km), bei 10 km keinen einzigen - und der Auslöser, der Kinderlauf
# des Karlsfelder Seelaufs, stand mit 21,1 km da (er ist 999 m lang).
KINDERLAUF_RE = re.compile(
    r"kinder|bambini|bambino|schüler|knirps|zwerg|mini.?lauf|jugendlauf", re.I)
KINDERLAUF_MAX_KM = 10.0

# „3 Runden je 15,5 km", „100 km (10 x 10 km)": Die zweite Zahl ist die
# Aufteilung derselben Strecke, kein Widerspruch.
RUNDEN_RE = re.compile(r"runde|round|\bà\b|\bje\b|\bx\b|mal\b|rundkurs", re.I)

# Ein Zeitrennen hat eine Dauer, keine Strecke (Datenregel 8). Steht bei
# einem "Stundenlauf" trotzdem eine Distanz, ist das meist die Runde
# oder die Siegerleistung des Vorjahres - der "Emder Stundenlauf" und
# der "15. Bokeler 6 Stundenlauf" stehen beide mit 10,0 km da.
# `fill_duration()` trägt bei diesen Zeilen bewusst KEINE Dauer nach
# (es füllt nur, wo gar nichts steht), also fällt es sonst niemandem auf.
ZEITRENNEN_IM_NAMEN_RE = re.compile(
    r"stunden(?:lauf|rennen)|\d+\s*h[-\s]?lauf|backyard", re.I)

KM_IM_LABEL_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*km", re.I)

# "4 Runden à ca. 5,27 km", "3 x 7,03 km", "2 x 21,1 km" - die Zahl der
# Runden und die Länge EINER Runde.
# Staffel, Team, DUO: Die Einzelstrecke ist das, was man läuft.
STAFFEL_RE = re.compile(r"staffel|\bteam\b|\bduo\b|\bpaar|relay", re.I)

RUNDEN_MAL_RE = re.compile(
    r"(\d{1,2})\s*(?:runden?|x|×)\s*(?:à|a|je)?\s*(?:ca\.?\s*)?"
    r"(\d{1,3}(?:[.,]\d+)?)\s*km", re.I)

# Ein Freitagabend-Stadtlauf ist völlig normal, ein Rennen am Dienstag
# nicht. Die erste Fassung meldete Mo-FR und produzierte 45 Fehlalarme
# (siehe CLAUDE.md, „Die Prüfregel irrt öfter als die Daten").
WERKTAG_AUSNAHMEN = re.compile(
    r"firmenlauf|abendlauf|nacht|silvester|neujahr|feiertag|etappe|"
    r"wandertage|mai\b|pfingst|oster", re.I)


def _label(event: dict) -> str:
    """Das Wettbewerbs-Label - ersatzweise der Veranstaltungsname.

    Der Rückfall auf den Namen ist kein Schönheitsfehler, sondern hat
    den „Running Paule Marathon" mit 6,4 km gefunden: Die Zeile trug
    gar kein Label, und 6,4 km waren die Rundenlänge.

    Umgekehrt darf für „Halbmarathon" NICHT der Name gelesen werden,
    wenn ein Label da ist: Der „Bernburger Halbmarathon" bietet auch
    12 km an, und die Regel meldete das als Fehler (er war keiner).
    """
    return ((event.get("wettbewerb") or "") or (event.get("name") or "")).lower()


# Probe-Einträge der Kalenderportale. Nur dieses eine, eindeutige Wort -
# "Testlauf" oder "Test-Run" kann ein echter Veranstaltungsname sein.
TESTEINTRAG_RE = re.compile(r"testveranstaltung|\btest[- ]?event\b", re.I)


def pruefe_event(event: dict) -> list[tuple[str, str]]:
    """Alle Prüfungen für EINE Zeile. Gibt (Kategorie, Meldung) zurück."""
    funde: list[tuple[str, str]] = []
    name = event.get("name") or ""
    wb = event.get("wettbewerb") or ""
    km = event.get("laenge_km")
    label = _label(event)
    datum = event.get("datum_start") or ""

    def melde(kategorie: str, zusatz: str = "") -> None:
        funde.append((kategorie, f"{datum} {name!r} [{wb or '-'}]"
                      + (f" -> {zusatz}" if zusatz else "")))

    # --- Testeintrag der Quelle ---------------------------------------
    # Kalenderportale legen Probe-Einträge an, die im öffentlichen
    # Kalender stehen bleiben. Gefunden wurde eine "TESTVERANSTALTUNG
    # Neujahrslauf" am 02.01.2030 in Dolgesheim (laufen.de). Bewusst nur
    # dieses eine Wort und nur als MELDUNG: "Testlauf" kann ein echter
    # Veranstaltungsname sein, gelöscht wird nach Einzelprüfung über
    # manual_overrides.json.
    if TESTEINTRAG_RE.search(name):
        melde("Testeintrag der Quelle?")

    # --- Name gegen Datum ---------------------------------------------
    # „ONW-Lauf Dannenberg 2025" an einem Termin im Jahr 2026. Ein
    # Saison-Bereich („Winterlaufserie 2026/2027") ist dagegen richtig,
    # deshalb der Schrägstrich als Ausnahme.
    if "/" not in name:
        for jahr in re.findall(r"\b(20\d\d)\b", name):
            if jahr != datum[:4]:
                melde("Jahreszahl im Namen passt nicht zum Datum", jahr)
                break

    # --- Link ---------------------------------------------------------
    url = event.get("veranstalter_url") or ""
    host = urllib.parse.urlparse(url).netloc.lower()
    if not url:
        melde("kein Veranstalter-Link")
    elif is_portal_link(url) or any(p in host for p in WEITERE_PORTALE):
        melde("Portallink statt offizieller Seite", host)

    # --- Distanz gegen das Label --------------------------------------
    if isinstance(km, (int, float)):
        # Nennt das Label seine eigene Kilometerzahl UND stimmt die mit dem
        # Feld überein, ist die Zeile in sich schlüssig - dann ist der
        # Name "Marathon" die Auskunft des Veranstalters und kein Fehler.
        # Trailveranstalter nennen einen 22,8-km-Rundkurs regelmäßig
        # "Halbmarathon" ("Dörenther Klippen UltraTrail · Halbmarathon
        # 22,8 km und ca. 560 Hm"), und der "29. Rursee Marathon" hat
        # neben dem Marathon einen Ultra über 52 km. Ohne diese Bedingung
        # meldete die Regel 19 Fälle, von denen 17 richtig waren.
        selbst_erklaert = any(
            abs(float(z.replace(",", ".")) - km) <= max(0.3, 0.05 * km)
            for z in KM_IM_LABEL_RE.findall(wb))

        # Die RUNDENLÄNGE statt der Renndistanz - inzwischen die vierte
        # Begegnung mit dieser Fehlerklasse (Backyard-Runde, "Running
        # Paule Marathon" 6,4 km, "Warendorfer Weihnachtslauf" 6 km,
        # "Borsig Halbmarathon" 5,3 km). Das Label verrät sie selbst:
        # Nennt es "N Runden à X km" und steht im Feld das X statt N*X,
        # ist die Runde gespeichert.
        # Eine STAFFEL ist etwas anderes als Runden derselben Strecke.
        # Bei "2x5 km Staffel" läuft man wirklich 5 km, und die Staffel
        # ist ein eigener Wettbewerb - die gespeicherten 5 km sind
        # richtig. Bei "Halbmarathon (4 Runden à ca. 5,27 km)" läuft
        # dieselbe Person alle vier Runden, die Renndistanz sind 21,1 km.
        # Ohne diese Unterscheidung meldete die Regel sechs Staffeln als
        # Fehler, die keine waren.
        runden = None if STAFFEL_RE.search(wb) else RUNDEN_MAL_RE.search(wb)
        if runden:
            try:
                n = int(runden.group(1))
                eine = float(runden.group(2).replace(",", "."))
            except ValueError:
                n, eine = 0, 0.0
            if n > 1 and eine > 0 and abs(km - eine) <= 0.3 and abs(km - n * eine) > 0.5:
                melde("Rundenlänge statt Renndistanz",
                      f"{km:g} km gespeichert, {n} x {eine:g} = {n * eine:g} km")

        if selbst_erklaert:
            pass
        elif re.search(r"halbmarathon|half marathon", label) and abs(km - 21.1) > 1.5:
            melde("„Halbmarathon“, aber Distanz passt nicht", f"{km:g} km")
        elif (re.search(r"\bmarathon\b", label)
              and not re.search(r"halb|half|viertel|drittel|mini|staffel|team", label)
              and abs(km - 42.2) > 2.5 and km < 60):
            melde("„Marathon“, aber Distanz passt nicht", f"{km:g} km")

        if KINDERLAUF_RE.search(wb) and km >= KINDERLAUF_MAX_KM:
            melde("Kinderlauf-Label mit Erwachsenendistanz", f"{km:g} km")

        # Zahl im Label gegen das Feld. Runden-Angaben sind ausgenommen.
        if wb and not RUNDEN_RE.search(wb):
            zahlen = KM_IM_LABEL_RE.findall(wb.lower())
            if zahlen:
                label_km = float(zahlen[0].replace(",", "."))
                if abs(label_km - km) > max(0.3, 0.05 * max(label_km, km)):
                    melde("Zahl im Label weicht von laenge_km ab",
                          f"Label {label_km:g}, Feld {km:g}")

        if km > 130 or (0 < km < 4.9 and event.get("art1") == "Laufen"):
            melde("auffällige Distanz", f"{km:g} km")

        if ZEITRENNEN_IM_NAMEN_RE.search(f"{name} {wb}"):
            melde("Zeitrennen im Namen, aber eine Distanz gesetzt", f"{km:g} km")

    # --- Kategorie gegen den Namen ------------------------------------
    text = f"{name} {wb}".lower()
    if event.get("art1") == "Laufen":
        # „\btrail" mit Wortanfang, „crosslauf" ausgeschrieben: Ein
        # Hindernislauf heißt oft „Cross…" und ist richtig eingeordnet
        # (der „Family-CrossDeLuxe" hat die erste Fassung dieser Regel
        # als Fehlalarm entlarvt).
        if (re.search(r"\btrail|crosslauf|geländelauf", text)
                and event.get("art2") not in ("Trail/Cross", "Berg",
                                              "Backcountry Ultra")):
            melde("Trail/Cross im Namen, andere Kategorie", repr(event.get("art2")))
        if re.search(r"berglauf|bergrennen|gipfel", text) and event.get("art2") != "Berg":
            melde("Berglauf im Namen, andere Kategorie", repr(event.get("art2")))

    # --- Vollständigkeit ----------------------------------------------
    lat, lon = event.get("lat"), event.get("lon")
    if lat is None or lon is None:
        melde("keine Koordinaten")
    else:
        box = LAND_BOX.get(event.get("land"))
        if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
            melde("Koordinaten passen nicht zum Land",
                  f"{event.get('land')} {lat:.3f},{lon:.3f}")
    if not (event.get("standort") or "").strip():
        melde("kein Ort")
    if not event.get("land"):
        melde("kein Land")
    if km is None and event.get("dauer_h") is None:
        melde("weder Distanz noch Dauer")
    if km is not None and event.get("dauer_h") is not None:
        melde("Distanz UND Dauer gesetzt", f"{km:g} km / {event['dauer_h']:g} h")

    # --- Datum ---------------------------------------------------------
    ende = event.get("datum_ende")
    try:
        start_d = datetime.date.fromisoformat(datum)
        if ende:
            tage = (datetime.date.fromisoformat(ende) - start_d).days
            if tage < 0:
                melde("Ende liegt vor dem Start")
            elif tage > 6:
                melde("Veranstaltung dauert über eine Woche", f"{tage + 1} Tage")
        if start_d.weekday() < 4 and not WERKTAG_AUSNAHMEN.search(text):
            melde("Wochentag Mo-Do", ["Mo", "Di", "Mi", "Do"][start_d.weekday()])
    except ValueError:
        melde("Datum unlesbar")

    # --- Name -----------------------------------------------------------
    # Führende Klammern sind erlaubt: „(L)auf zur Venus" ist ein
    # Wortspiel, kein Rest aus dem Parser.
    if re.search(r"\s{2,}|\|\s*$|&amp;|&#|&nbsp;|<[a-z]", name):
        melde("Name sieht unsauber aus")
    if name.isupper() and len(name) > 12:
        melde("Name komplett in Großbuchstaben")
    if len(name) > 70:
        melde("Name sehr lang (Beschreibung statt Name?)")

    return funde


def pruefe_bestand(events: list[dict]) -> dict[str, list[str]]:
    funde: dict[str, list[str]] = collections.defaultdict(list)
    for event in events:
        for kategorie, meldung in pruefe_event(event):
            funde[kategorie].append(meldung)

    # Exakt gleiche Zeilen (Name + Datum + Distanz + Label) - das ist
    # immer ein Fehler, egal aus welcher Quelle.
    zaehler = collections.Counter(
        ((e.get("name") or "").casefold(), e.get("datum_start"),
         e.get("laenge_km"), (e.get("wettbewerb") or "").casefold())
        for e in events)
    for (n, d, k, _), anzahl in zaehler.items():
        if anzahl > 1:
            funde["exakt identische Zeilen"].append(
                f"{d} {n!r} {k} km ({anzahl}x)")
    return funde


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--events-json", type=Path, default=EVENTS_JSON_PATH)
    parser.add_argument("--ab", type=int, default=0,
                        help="Ab welchem Event (nach Datum sortiert).")
    parser.add_argument("--anzahl", type=int,
                        help="Wie viele Events (Standard: alle).")
    parser.add_argument("--quiet", action="store_true",
                        help="Nur die Zahlen, keine Einzelmeldungen.")
    parser.add_argument("--offen", action="store_true",
                        help="Nur Events, die noch NICHT in geprueft.json stehen.")
    parser.add_argument("--max-je-gruppe", type=int, default=25,
                        help="Wie viele Beispiele je Kategorie (Standard 25).")
    args = parser.parse_args()

    events = json.loads(args.events_json.read_text(encoding="utf-8"))
    events.sort(key=lambda e: (e.get("datum_start") or "",
                               (e.get("name") or "").casefold()))
    teil = events[args.ab:args.ab + args.anzahl] if args.anzahl else events[args.ab:]
    if args.offen:
        protokoll = lade_geprueft()
        vorher = len(teil)
        teil = [e for e in teil if not ist_geprueft(protokoll, e)]
        unklar = zaehle_unklar(protokoll)
        print(f"(--offen: {vorher - len(teil)} von {vorher} Zeilen sind bereits "
              f"geprüft, {len(protokoll)} Veranstaltungen im Protokoll.)")
        if unklar:
            print(f"(davon {unklar} als 'unklar' abgelegt - an der Quelle nicht "
                  f"zu entscheiden, Begründung steht in geprueft.json.)")
    if not teil:
        print("Keine Events in diesem Ausschnitt.")
        return 0

    print(f"Geprüft: Events {args.ab + 1}-{args.ab + len(teil)} von {len(events)}, "
          f"{teil[0].get('datum_start')} bis {teil[-1].get('datum_start')}")

    funde = pruefe_bestand(teil)
    for titel in sorted(funde, key=lambda t: -len(funde[t])):
        print(f"\n### {titel}: {len(funde[titel])}")
        if args.quiet:
            continue
        for zeile in funde[titel][:args.max_je_gruppe]:
            print(f"    {zeile}")
        if len(funde[titel]) > args.max_je_gruppe:
            print(f"    … und {len(funde[titel]) - args.max_je_gruppe} weitere")

    gesamt = sum(len(v) for v in funde.values())
    print(f"\nSUMME Verdachtsfälle: {gesamt} "
          f"({gesamt / len(teil):.2f} je Event)")
    print("Nichts davon ist automatisch ein Fehler - jeder Fall gehört "
          "einzeln\ngegen die offizielle Ausschreibung geprüft "
          "(siehe CLAUDE.md, „Die wichtigste Lektion“).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
