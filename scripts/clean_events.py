#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_events.py
==================

Wartungsskript, das eine bestehende `events.json` nach denselben Regeln
aufräumt, die die Scraper beim Einfügen anwenden. Nötig, weil die Scraper
vorhandene Einträge nie verändern (sie fügen nur neue an) - Regeln, die
später dazukommen oder Bugfixes an der Distanz-/Kategorie-Erkennung
wirken deshalb nicht rückwirkend. Genau dafür ist dieses Skript da.

Neun Schritte, in dieser Reihenfolge:

1. **Manuelle Korrekturen** aus `scripts/manual_overrides.json` anwenden
   (Distanz/Kategorie/Link überschreiben, `exclude: true` entfernt das
   Event). Wichtig für Events aus inzwischen deaktivierten Quellen wie
   blv-sport.de, die kein Scraper mehr neu erzeugt.
2. **Kategorie (art2) neu bestimmen**, wo der Name ein klareres Signal
   gibt als der gespeicherte Wert - fängt die frühere Fehleinstufung von
   Trail-/Bergläufen als "Straße" rückwirkend auf (ein Name wie
   "... Bergtrail 42k Trail-Marathon" traf zuerst auf die generische
   Marathon-Regel). Ein per Override gesetztes art2 bleibt unangetastet.
3. **Längenangaben auf eine Dezimalstelle runden**: Quellen geben
   dieselbe Strecke unterschiedlich genau an ("42,195 km" vs. "42,2 km"),
   gespeichert wird einheitlich 42.2.
4. **Land ergänzen/korrigieren** über Reverse-Geocoding der Koordinaten.
   Eine vierstellige Postleitzahl unterscheidet Österreich nicht von der
   Schweiz - Events wie Mosnang (CH) oder Innsbruck (AT) blieben deshalb
   ohne Land; umgekehrt stand beim "Fränkische-Schweiz-Marathon" in Bayern
   fälschlich "Schweiz".
5. **5-km-Mindestdistanz**: Events mit BEKANNTER Distanz unter
   `scraper_lib.MIN_DISTANCE_KM` entfernen (Events ohne Distanzangabe
   bleiben, siehe README "Datenqualität").
5b. **Vergangene Events entfernen**: Maßgeblich ist `datum_ende` (sonst
   `datum_start`); der heutige Tag bleibt drin, ein mehrtägiges Rennen
   bleibt bis zu seinem letzten Tag. Die Kalender der Quellen führen
   abgelaufene Termine teils monatelang weiter - ohne diesen Schritt
   sammelt sich Vergangenheit in der Liste an.
6. **Verdächtige Distanzen melden** (nur Hinweis, es wird nichts
   gelöscht): Widerspricht eine Einzelangabe der Streckenaufzählung einer
   anderen Quelle für dieselbe Veranstaltung, wird sie zur Prüfung
   ausgegeben - siehe `report_suspicious_distances()` samt Begründung,
   warum hier bewusst NICHT automatisch gelöscht wird.
7. **Duplikate zusammenführen** über `scraper_lib.is_same_event()`
   (gleiches Datum + ähnlicher Name + gleicher Ort + kompatible Distanz).
   Dieselbe Veranstaltung steht oft in mehreren Kalendern unter
   abweichendem Namen ("52. Int. Bodensee-Marathon" / "Bodensee
   Marathon"). Behalten wird der vollständigste Eintrag, fehlende Felder
   werden aus den Duplikaten ergänzt und ein direkter Veranstalter-Link
   einem Kalender-Portal-Link vorgezogen.

Zum Schluss wird nach Datum (dann Name) sortiert - das hält die Datei
übersichtlich und die Git-Diffs klein. Die Webseite sortiert ohnehin
selbst (nächstes Datum zuerst, vergangene Events ans Ende).

Das Skript ist idempotent: ein zweiter Lauf direkt danach ändert nichts.

Nutzung
-------
    python3 scripts/clean_events.py --dry-run   # nur Bericht, nichts ändern
    python3 scripts/clean_events.py             # events.json aufräumen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import (  # noqa: E402
    ENRICHABLE_FIELDS,
    EVENTS_JSON_PATH,
    GEOCODE_CACHE_PATH,
    MIN_DISTANCE_BY_ART1,
    MIN_DISTANCE_KM,
    Geocoder,
    SiteConfig,
    guess_art1,
    guess_art2,
    ist_charity,
    ist_nicht_offen_schwimmen,
    ist_zu_kurz,
    guess_land,
    is_portal_link,
    is_same_event,
    meter_km,
    is_same_race,
    find_override,
    ist_nicht_ausdauer, ist_staffel, nicht_ausdauer_text,
    ART2_LISTEN,
    _haversine_km,
    OVERRIDE_FIELDS,
    parse_duration_h,
    load_manual_overrides,
    round_km,
)

# Für die Neubestimmung von art2 wird die Standard-Stichwortliste für
# Laufen genutzt (siehe ART2_KEYWORDS_LAUFEN in scraper_lib.py).
ART2_CONFIG = SiteConfig(base_url="", calendar_url="")

# Nur ein sauberes YYYY-MM-DD gilt als vergleichbares Datum; alles andere
# wird beim Aufräumen nicht angefasst (siehe drop_past_events()).
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def completeness(event: dict) -> int:
    return sum(1 for value in event.values() if value is not None)


# Einzeln recherchierte Events, die KEINE Quelle liefert. Gegenstück zu
# manual_overrides.json: Das korrigiert vorhandene Zeilen, dies trägt
# fehlende nach.
MANUAL_EVENTS_PATH = Path(__file__).resolve().parent / "manual_events.json"


def load_manual_events() -> list[dict]:
    """Liest scripts/manual_events.json (Liste von Event-Dicts).

    Schlüssel, die mit "_" beginnen, sind Dokumentation (`_note`,
    `_quelle`) und landen NICHT in events.json - dort gehört nur hin,
    was die Seite anzeigt.
    """
    if not MANUAL_EVENTS_PATH.exists():
        return []
    roh = json.loads(MANUAL_EVENTS_PATH.read_text(encoding="utf-8"))
    eintraege = roh.get("events", roh) if isinstance(roh, dict) else roh
    return [{k: v for k, v in e.items() if not k.startswith("_")} for e in eintraege]


def add_manual_events(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Trägt einzeln recherchierte Strecken nach, die keine Quelle liefert.

    Warum es das gibt: Beim Durchgehen der Streckenlisten tauchte immer
    wieder derselbe Fall auf - eine Veranstaltung steht in der Liste,
    aber nicht alle ihre Wettbewerbe. Die Bühlauer Winterlaufserie hat
    fünf Termine, wir hatten einen; der proWissen-Lauf hat 5 km UND
    10 km, wir hatten die 10 km. Ein Override kann das nicht heilen: Er
    ändert eine vorhandene Zeile, er legt keine an. Und ein fehlendes
    Event ist die unangenehmere Sorte Fehler - eine falsche Zahl sieht
    man, eine fehlende Zeile nicht.

    Nachgetragen wird nur, was einzeln an der offiziellen Ausschreibung
    geprüft ist; die Belegstelle steht als `_quelle`/`_note` in der
    Datei (dieselbe Linie wie bei manual_overrides.json).

    Doppelt kann dabei nichts entstehen: Übersprungen wird jeder
    Eintrag, zu dem `is_same_event()` bereits eine Zeile findet - also
    genau die Duplikat-Definition des Projekts. Damit ist der Schritt
    idempotent und verträgt sich mit einem späteren Scraper-Lauf, der
    dieselbe Strecke von selbst einsammelt: Dann greift er nicht mehr.

    Die nachgetragenen Zeilen laufen danach durch DIESELBEN Regeln wie
    alles andere (Kategorie, Rundung, Mindestdistanz, vergangene Events,
    Zusammenführen) - deshalb steht dieser Schritt ganz am Anfang.
    """
    manuell = load_manual_events()
    if not manuell:
        return events, []
    hinzu: list[str] = []
    for kandidat in manuell:
        if any(is_same_event(vorhanden, kandidat) for vorhanden in events):
            continue
        events = events + [dict(kandidat)]
        hinzu.append(
            f"{kandidat.get('name')} ({kandidat.get('datum_start')}"
            + (f", {kandidat['laenge_km']:g} km"
               if isinstance(kandidat.get("laenge_km"), (int, float)) else "")
            + f") - {kandidat.get('standort')}"
        )
    return events, hinzu


def apply_overrides(events: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    overrides = load_manual_overrides()
    kept: list[dict] = []
    excluded: list[str] = []
    changed: list[str] = []
    for event in events:
        override = find_override(overrides, event.get("name"), event.get("datum_start"),
                                 event.get("laenge_km"))
        if override:
            if override.get("exclude"):
                excluded.append(
                    f"{event.get('name')} ({event.get('datum_start')}"
                    + (f", {event['laenge_km']:g} km" if isinstance(event.get('laenge_km'), (int, float)) else "")
                    + ")"
                )
                continue
            for field in OVERRIDE_FIELDS:
                if field not in override or event.get(field) == override[field]:
                    continue
                # Ein Override darf einen direkten Veranstalter-Link NIE durch
                # einen Portallink ersetzen (siehe scraper_lib).
                if (field == "veranstalter_url"
                        and is_portal_link(override[field])
                        and event.get("veranstalter_url")
                        and not is_portal_link(event["veranstalter_url"])):
                    continue
                changed.append(
                    f"{event.get('name')}: {field} {event.get(field)!r} -> {override[field]!r}"
                )
                event[field] = override[field]
        kept.append(event)
    return kept, excluded, changed


# Alte Kategorien, die heute eine einzige sind - je Sportart, denn "Cross"
# ist beim Laufen ein Geländelauf (heute "Trail"), beim Triathlon aber
# weiterhin eine eigene Kategorie, und beim Fahrrad ist "Cyclecross" eine
# dritte Sache.
#
# Laufen: "Trail", "Cross" und "Berg" beschreiben alle einen Geländelauf;
# die Quellen benennen dieselbe Strecke mal so, mal so, und wer sie
# trennen will, rät. Erst zu "Trail/Cross" zusammengefasst, am 19.09.2026
# auf Wunsch des Nutzers um "Berg" erweitert und in "Trail" umbenannt
# ("die beste Bezeichnung einfach für die ganzen Events"). "Berglauf"
# stand daneben einmal als Tippfehler-Wert im Override und damit in den
# Daten - der geht denselben Weg.
#
# "Backcountry Ultra" (Laufen) und "Backyard" (Triathlon) sind beide das
# Last-Man-Standing-Format und heißen seit dem 19.09.2026 in beiden
# Sportarten gleich: "Backyard Ultra" (so vom Nutzer entschieden).
ART2_MERGED = {
    "Laufen": {
        "Trail/Cross": "Trail", "Cross": "Trail", "Berg": "Trail",
        "Berglauf": "Trail", "Backcountry Ultra": "Backyard Ultra",
    },
    "Triathlon": {"Backyard": "Backyard Ultra"},
}


def merge_art2(events: list[dict]) -> list[str]:
    """Zieht bereits gespeicherte alte Kategorie-Werte (`ART2_MERGED`) auf
    die heutigen nach.

    Die Stichwortlisten (`ART2_KEYWORDS_*`) liefern den neuen Wert schon
    bei jedem Scraper-Lauf; dieser Schritt holt den Bestand nach - und
    fängt Overrides ab, die noch den alten Wert nennen. Idempotent: Ein
    zweiter Durchlauf findet nichts mehr, weil kein Zielwert zugleich ein
    Schlüssel ist.
    """
    changed: list[str] = []
    for event in events:
        zuordnung = ART2_MERGED.get(event.get("art1") or "")
        if not zuordnung:
            continue
        neu = zuordnung.get(event.get("art2"))
        if neu:
            changed.append(f"{event.get('name')}: art2 {event['art2']!r} -> {neu!r}")
            event["art2"] = neu
    return changed


# Alter Name, damit ältere Aufrufe weiter funktionieren.
merge_trail_cross = merge_art2


def fix_charity(events: list[dict]) -> list[str]:
    """Setzt das Merkmal `charity` aus dem Namen - und holt die Zeilen ab,
    die die alte Kategorie "Charity" tragen.

    Vorgeschichte in einem Satz: Am 21.09.2026 kam "Charity" auf Wunsch
    des Nutzers als KATEGORIE (art2) dazu und verdrängte dort die echte
    Kategorie; am selben Tag hat er das zurückgenommen ("Aber da bitte
    wieder die Kategorie einfügen"). Seitdem ist Charity ein Merkmal
    NEBEN der Kategorie.

    Zwei Dinge tut die Funktion, beide idempotent:

    1. `charity: True`, wo ist_charity() den Namen erkennt.
    2. Wo noch `art2 == "Charity"` steht, wird das Feld geleert - die
       echte Kategorie holt refresh_art2() unmittelbar danach aus der
       Stichwortliste zurück (deshalb läuft fix_charity DAVOR).

    Ein Override mit ausdrücklichem `charity` wird nicht angefasst:
    Der Wings for Life World Run trägt das Wort nicht im Namen, ist aber
    einer - solche Zeilen markiert der Nutzer von Hand, und eine Regel
    darf ihm das nicht wieder wegnehmen. Umgekehrt kann er mit
    `"charity": false` eine Fehlmarkierung abschalten.
    """
    overrides = load_manual_overrides()
    changed: list[str] = []
    for event in events:
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        war_kategorie = event.get("art2") == "Charity"
        if war_kategorie:
            event["art2"] = None
        if own and "charity" in own:
            continue  # von Hand entschieden
        if ist_charity(event.get("name") or ""):
            if not event.get("charity"):
                changed.append(f"{event.get('name')}: charity -> True")
                event["charity"] = True
        elif war_kategorie:
            # Stand nur über die alte Kategorie als Charity da, der Name
            # sagt es aber nicht - dann ist es auch keine Markierung.
            changed.append(f"{event.get('name')}: Kategorie 'Charity' -> echte Kategorie")
    return changed


def refresh_art2(events: list[dict]) -> list[str]:
    """Bestimmt art2 aus dem Event-Namen neu, wenn dabei eine spezifischere
    Kategorie als die gespeicherte herauskommt (Trail, Hindernis, Bahn,
    Backyard Ultra statt des generischen "Straße")."""
    overrides = load_manual_overrides()
    changed: list[str] = []
    for event in events:
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        if own and "art2" in own:
            continue  # manuell gesetzte Kategorie nicht überschreiben
        if event.get("art1") != "Laufen":
            continue  # Stichwortliste gilt nur für Laufen
        # Name UND Wettbewerbs-Label: Die Gattung steht oft nur im Label
        # ("Hot-20 (40 Hindernisse)" beim Hotfoot Run, "9,2 km Crosslauf"
        # beim Bietlauf) - der Veranstaltungsname nennt sie nicht. Beim
        # Einsammeln liest expand_competitions() das Label längst mit;
        # hier fehlte es. Nachgezählt am Bestand vom 21.09.2026: vier
        # Zeilen ändern sich, alle vier zu Recht (Crossläufe, die als
        # Straße standen).
        guessed = guess_art2(f"{event.get('name') or ''} {event.get('wettbewerb') or ''}",
                             ART2_CONFIG)
        current = event.get("art2")
        # "Charity" war bis zum 21.09.2026 eine Kategorie und gewann hier
        # sogar gegen eine schon gesetzte spezifische - der Zweck vor dem
        # Untergrund. Am selben Tag zurückgenommen: Charity ist jetzt ein
        # eigenes Merkmal (fix_charity), die Kategorie bleibt die
        # Kategorie. "Charity" als Altwert holt fix_charity() ab.
        # Ein Hindernislauf schlägt auch eine schon gesetzte Trail-Kategorie.
        # Grund ist die Reihenfolge der Stichwortliste selbst: Dort steht
        # "Hindernis" VOR "Trail", weil ein Hindernislauf durchs Gelände
        # immer noch ein Hindernislauf ist. Fünf Zeilen standen nur
        # deshalb als Trail, weil "Cross" in ihrem Namen steht
        # (CrossDeLuxe Erzgebirge, "Puls 300 Cross- und Hindernis-Lauf",
        # der Berserker des Legend of Cross) - und die gleichnamigen
        # Schwesterveranstaltungen wären danach Hindernis gewesen, sie
        # nicht. Sonst bleibt es bei der Regel, nur Generisches zu
        # ersetzen: Eine Kategorie, die spezifischer ist als die
        # geratene, wird nicht angefasst.
        if guessed == "Hindernis" and current == "Trail":
            changed.append(f"{event.get('name')}: art2 'Trail' -> 'Hindernis'")
            event["art2"] = "Hindernis"
            continue
        if guessed and guessed != current and current in (None, "Straße", "Charity"):
            changed.append(f"{event.get('name')}: art2 {current!r} -> {guessed!r}")
            event["art2"] = guessed
    return changed


def drop_nicht_ausdauer(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Entfernt Formate, die kein Ausdauer-Event sind (NICHT_AUSDAUER).

    Das Gegenstück zu `scraper_lib.filter_nicht_ausdauer()` für den
    bestehenden Bestand - dieselbe Aufteilung wie bei den vergangenen
    Events (`filter_past` beim Einsammeln, `drop_past_events` hier).

    Die einzige Zeile in der Liste ist HYROX: achtmal ein Kilometer
    Laufen im Wechsel mit acht Kraftstationen. Vom Nutzer am 18.09.2026
    entschieden, und ausdrücklich „erst einmal" - eine Zeile aus
    NICHT_AUSDAUER heraus, und die Events kommen beim nächsten
    Datenlauf zurück.

    Anders als die Distanz- und Datumsregeln ist das KEINE Heuristik:
    Ein eindeutiger Markenname ist eine Tatsache, keine Vermutung. Die
    Warnung der „wichtigsten Lektion" gilt trotzdem - deshalb steht in
    der Liste nur, was der Nutzer einzeln entschieden hat, und jeder
    Ausschluss wird gemeldet.
    """
    kept: list[dict] = []
    entfernt: list[str] = []
    for event in events:
        grund = ist_nicht_ausdauer(nicht_ausdauer_text(
            event.get("name"), event.get("wettbewerb"), event.get("standort")))
        if grund:
            entfernt.append(f"{event.get('name')} ({event.get('datum_start')}) - {grund}")
        else:
            kept.append(event)
    return kept, entfernt


def drop_ausserhalb(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Wirft Zeilen heraus, deren `land` keine abgedeckte Region ist.

    Praktisch trifft das nur "Italien": den Zwischenstand, den die
    Scraper für italienische Events stehen lassen, bis Koordinaten
    entscheiden, ob es Südtirol ist (scraper_lib.in_suedtirol). Läuft
    NACH fix_land(): Erst dort werden Koordinaten zu "Italien (Südtirol)"
    - was danach noch "Italien" heißt, liegt außerhalb (Trentino, Mailand)
    und gehört nicht in die Liste. Zeilen ohne `land` bleiben, wie
    überall (unbekannt schließt nichts aus).
    """
    from scraper_lib import LAENDER, in_suedtirol, SUEDTIROL
    kept, removed = [], []
    for e in events:
        land = e.get("land")
        if land == "Italien" and in_suedtirol(e.get("lat"), e.get("lon")):
            e["land"] = SUEDTIROL
            land = SUEDTIROL
        if land and land not in LAENDER:
            removed.append(f"{e.get('name')} ({e.get('standort')}, {land})")
            continue
        kept.append(e)
    return kept, removed


def drop_staffeln(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Entfernt Staffeln - das Gegenstück zu `scraper_lib.filter_staffeln()`
    für den Bestand. Vom Nutzer am 21.09.2026 entschieden ("Erst einmal
    keine Staffeln aufnehmen"); die Regel samt Gegenproben steht bei
    `ist_staffel()` in scraper_lib.py. Jeder Ausschluss wird gemeldet.
    """
    kept: list[dict] = []
    entfernt: list[str] = []
    for event in events:
        grund = ist_staffel(event.get("name"), event.get("wettbewerb"))
        if grund:
            entfernt.append(f"{event.get('name')} ({event.get('datum_start')}) - {grund}")
        else:
            kept.append(event)
    return kept, entfernt


def fill_art2_andere_sportarten(events: list[dict]) -> list[str]:
    """Trägt die Kategorie bei Nicht-Lauf-Sportarten nach, wo die Quelle
    sie ausdrücklich nennt.

    `refresh_art2()` daneben gilt nur für Laufen und liest nur den
    NAMEN. Für ein Radrennen steht die Auskunft aber im
    Wettbewerbs-Label ("Mountainbike Rennen 42 km"), nicht im Namen der
    Laufveranstaltung, an der es hängt ("Possenlauf").

    Gefüllt wird nur, was leer ist, und nur für Sportarten mit einer
    EIGENEN Stichwortliste (ART2_LISTEN). Ohne diese Bedingung fiele
    guess_art2() still auf die Laufen-Liste zurück - ein
    Mountainbike-Rennen bekäme "Straße".
    """
    overrides = load_manual_overrides()
    changed: list[str] = []
    for event in events:
        art1 = event.get("art1")
        if art1 in (None, "Laufen") or art1 not in ART2_LISTEN:
            continue
        if event.get("art2") is not None:
            continue
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        if own and "art2" in own:
            continue
        text = f"{event.get('wettbewerb') or ''} {event.get('name') or ''}"
        geraten = guess_art2(text, ART2_CONFIG, art1)
        if geraten:
            changed.append(f"{event.get('name')} [{event.get('wettbewerb')}]: "
                           f"art2 None -> {geraten!r}")
            event["art2"] = geraten
    return changed


def fix_multisport_art1(events: list[dict]) -> list[str]:
    """Zieht Triathlons (und andere Mehrsport-Wettkämpfe) nach, die als
    Laufveranstaltung gespeichert sind.

    Alle vier Quellen sind Laufkalender; ihre SiteConfig trägt
    `default_art1 = "Laufen"`, und damit stand jeder Triathlon als
    Laufveranstaltung in der Liste. Der Nutzer hat es an einer Zeile
    gemerkt, die es nicht geben darf: „Ironman 70.3 Kraichgau · Laufen ·
    Straße" - bei einem Ironman kann man sich nicht für den Lauf allein
    anmelden. `guess_art1()` erkennt das inzwischen beim Einsammeln,
    dieser Schritt holt den Bestand nach.

    Umgestellt wird NUR von "Laufen" aus und nur bei einem eindeutigen
    Stichwort im Namen (ART1_KEYWORDS). Eine von Hand gesetzte Sportart
    (Override) bleibt unangetastet, und die Kategorie wird gleich
    mitgezogen - ein Triathlon mit der Laufkategorie "Trail" wäre
    nur halb korrigiert.
    """
    overrides = load_manual_overrides()
    changed: list[str] = []
    for event in events:
        if event.get("art1") != "Laufen":
            continue
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        if own and "art1" in own:
            continue
        name = event.get("name") or ""
        neu = guess_art1(name, ART2_CONFIG)
        if neu == "Laufen":
            continue
        alt_art2 = event.get("art2")
        # Die Kategorie kommt aus der Liste der NEUEN Sportart (siehe
        # ART2_LISTEN in scraper_lib.py). Ein manuell gesetztes art2
        # bleibt auch hier stehen.
        if not (own and "art2" in own):
            event["art2"] = guess_art2(f"{name} {event.get('wettbewerb') or ''}",
                                       ART2_CONFIG, neu)
        changed.append(f"{name}: art1 {event['art1']!r} -> {neu!r}, "
                       f"art2 {alt_art2!r} -> {event.get('art2')!r}")
        event["art1"] = neu
    return changed


# Ein Wettbewerbs-Label, das AUSDRÜCKLICH eine andere Sportart nennt.
# Das ist keine Vermutung aus dem Namen, sondern die Angabe der Quelle
# selbst: Der "Drei Talsperren Marathon" in Eibenstock trägt neben
# Marathon, Halbmarathon und 8 km auch "Rad 100 km", "Rad 50 km" und
# "Rad 30 km" - laut Ausschreibung eigenständige Wettbewerbe, für die
# man sich einzeln anmeldet. Bei uns standen sie als LAUF in der Liste,
# also als 100-km-Lauf.
#
# Die Wortgrenzen sind der ganze Trick: "rad" ohne sie trifft
# "Konrad", "Radeberg", "Stadtradeln"; "bike" trifft "Bikepark-Lauf".
FREMDE_SPORTART_IM_LABEL = (
    (re.compile(r"(?:^|[\s(\[/|–-])(?:rad|radrennen|radmarathon|radtour|radstrecke|"
                r"radfahren|mtb|mountainbike|bike|velo)(?:$|[\s):\]/|,.–-])", re.I),
     "Fahrrad"),
    (re.compile(r"(?:^|[\s(\[/|–-])(?:schwimmen|schwimmstrecke|"
                r"freiwasserschwimmen|open ?water)(?:$|[\s):\]/|,.–-])", re.I),
     "Schwimmen"),
)

# Nennt das Label MEHRERE Disziplinen, ist es keine eigene Sportart,
# sondern eine Teilstrecke oder eine Aufzählung ("500 m Schwimmen +
# 5 km Laufen", "10 km Radfahren bis zur 1. Wechselzone", "6,5 km:
# Rad, Lauf, Skiroller, Walking"). Solche Zeilen werden NICHT
# umgestellt, sondern von report_multisport_teilstrecken() gemeldet.
MEHRERE_DISZIPLINEN_RE = re.compile(
    r"wechselzone|\+|skiroller", re.I)

# VERBFORMEN einer Disziplin - das Erkennungszeichen einer Teilstrecke.
# Der Unterschied, um den sich alles dreht, steht in den Daten selbst:
#
#   "Rad 100 km", "Mountainbike Rennen 42 km"   -> ein Rennen, das man bucht
#   "21,5 km Radfahren", "7,3 km Laufen"        -> eine Etappe, die man absolviert
#   "Run 1", "ca. 20 km Radstrecke"             -> ebenso
#
# Ein Veranstalter, der seine Wettbewerbe so benennt, beschreibt einen
# Mehrsport-Wettkampf. Deshalb wird nicht die einzelne ZEILE geprüft,
# sondern die ganze VERANSTALTUNG: Trägt IRGENDEINE ihrer Zeilen eine
# solche Verbform, bleibt die Sportart unangetastet.
#
# Gemessen an den zwölf Veranstaltungen, die die Regel sonst getroffen
# hätte, trennt das sauber: Aluman, RömerMan, Trifun Pellworm,
# Mainathlon, Dirty Race und Speck Race sind Triathlons und bleiben
# stehen; beim Drei Talsperren Marathon, Possenlauf, Elsterlauf,
# Frickinger Apfellauf, Pfettrachtaler Lauf und Schneeglöckchen-Lauf
# heißen die Laufstrecken "Marathon", "10 km Lauf", "8,0 km Lauf" -
# dort ist das Radrennen wirklich ein eigener Wettbewerb.
#
# Die Wortgrenzen sind wieder entscheidend: `\bbike\b` darf NICHT in
# "Mountainbike" treffen, sonst fällt der Frickinger Apfellauf durch.
TEILSTRECKEN_VERB_RE = re.compile(
    r"\b(laufen|laufstrecke|run|running|schwimmen|schwimmstrecke|swim|"
    r"radfahren|radstrecke|bike|biken)\b", re.I)


def _ist_mehrsport_veranstaltung(gruppe: list[dict]) -> bool:
    """True, wenn IRGENDEINE Zeile dieser Veranstaltung ihre Strecke als
    Disziplin-Etappe benennt (siehe TEILSTRECKEN_VERB_RE)."""
    return any(TEILSTRECKEN_VERB_RE.search(e.get("wettbewerb") or "")
               for e in gruppe)


def fix_fremde_sportart_im_wettbewerb(events: list[dict]) -> list[str]:
    """Stellt Zeilen um, deren Wettbewerbs-Label ausdrücklich eine andere
    Sportart nennt als `art1`.

    Gefunden bei der Einzelprüfung von 200 Events: Der "Drei Talsperren
    Marathon" hatte drei Radrennen (30/50/100 km) als LAUF in der Liste.
    Das ist keine Randnotiz - ein 100-km-Lauf ist eine Ultradistanz, ein
    100-km-Radrennen ein Vormittag.

    Bewusst eng gehalten, weil eine falsche Umstellung unsichtbar ist
    (siehe „die wichtigste Lektion" im README):

    - Es zählt nur das **Wettbewerbs-Label**, nicht der Name. Im Namen
      steht „Rad" auch bei „Radrennbahn-Lauf".
    - Das Label muss **genau eine** fremde Sportart nennen. Steht
      daneben noch Laufen, Walking oder eine Wechselzone, ist es eine
      Teilstrecke eines Mehrsport-Wettkampfs - die wird nur gemeldet.
    - Ein von Hand gesetztes `art1` (Override) bleibt unangetastet.
    """
    overrides = load_manual_overrides()
    veranstaltungen: dict[tuple, list[dict]] = {}
    for event in events:
        veranstaltungen.setdefault(((event.get("name") or "").casefold(),
                                    event.get("datum_start")), []).append(event)
    changed: list[str] = []
    for event in events:
        label = event.get("wettbewerb") or ""
        if not label:
            continue
        # Ein Triathlon ist schon richtig eingeordnet; sein "Radfahren"
        # ist eine Etappe, kein eigenes Rennen.
        if event.get("art1") == "Triathlon":
            continue
        treffer = [sport for muster, sport in FREMDE_SPORTART_IM_LABEL
                   if muster.search(label)]
        if len(treffer) != 1 or treffer[0] == event.get("art1"):
            continue
        if MEHRERE_DISZIPLINEN_RE.search(label):
            continue
        gruppe = veranstaltungen[((event.get("name") or "").casefold(),
                                  event.get("datum_start"))]
        if _ist_mehrsport_veranstaltung(gruppe):
            continue
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        if own and "art1" in own:
            continue
        neu = treffer[0]
        alt_art2 = event.get("art2")
        if not (own and "art2" in own):
            # Für Fahrrad und Schwimmen gibt es noch KEINE eigene
            # Stichwortliste (Fahrplan Punkt 1). guess_art2() fiele sonst
            # still auf die LAUFEN-Liste zurück und machte aus einem
            # Mountainbike-Rennen einen "Straße"-Eintrag. Keine Kategorie
            # ist ehrlicher als eine falsche.
            event["art2"] = (guess_art2(label, ART2_CONFIG, neu)
                             if neu in ART2_LISTEN else None)
        changed.append(
            f"{event.get('name')} [{label}]: art1 {event.get('art1')!r} -> {neu!r}, "
            f"art2 {alt_art2!r} -> {event.get('art2')!r}")
        event["art1"] = neu
    return changed


def report_widerspruechliche_koordinaten(events: list[dict],
                                         grenze_km: float = 30.0) -> list[str]:
    """Meldet Veranstaltungen, die am selben Tag an zwei weit
    auseinanderliegenden Punkten liegen.

    Der Fund, der diese Prüfung ausgelöst hat: Der "Bodensee Marathon"
    stand mit seiner Marathon-Strecke auf 49.07/10.14 - mitten in
    Franken, 168 km vom Bodensee. Ursache ist der Geocoder: Die eine
    Quelle nannte als Ort "Kressbronn", die andere "Kressbronn am
    Bodensee", und für das kurze "Kressbronn" fand sich ein
    gleichnamiger Ort anderswo.

    Das ist kein Schönheitsfehler: Die Umkreissuche und die Karte
    bauen ausschließlich auf diesen Koordinaten auf. Wer im Umkreis
    von 25 km um Friedrichshafen sucht, bekommt den Marathon nicht zu
    sehen - obwohl er dort stattfindet.

    Warum nur ein Hinweis und keine Korrektur: Welcher der beiden
    Punkte der richtige ist, steht in den Daten nicht. Die Mehrheit zu
    nehmen wäre geraten - und zu viel automatisch verschoben ist
    schlimmer als eine Meldung, weil es niemand sieht.
    """
    gruppen: dict[tuple, list[dict]] = {}
    for event in events:
        lat, lon = event.get("lat"), event.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        gruppen.setdefault(((event.get("name") or "").casefold(),
                            event.get("datum_start")), []).append(event)
    meldungen: list[str] = []
    for (_, datum), gruppe in gruppen.items():
        if len(gruppe) < 2:
            continue
        weiteste, paar = 0.0, None
        for i, a in enumerate(gruppe):
            for b in gruppe[i + 1:]:
                km = _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
                if km > weiteste:
                    weiteste, paar = km, (a, b)
        if paar and weiteste > grenze_km:
            a, b = paar
            meldungen.append(
                f"{datum} {a.get('name')}: {weiteste:.0f} km auseinander - "
                f"{a.get('standort')} ({a['lat']:.3f},{a['lon']:.3f}) vs. "
                f"{b.get('standort')} ({b['lat']:.3f},{b['lon']:.3f})")
    return sorted(meldungen)


def report_gleiche_seite_gleiche_distanz(events: list[dict]) -> list[str]:
    """Meldet Einträge mit DERSELBEN Veranstalter-Seite, demselben Datum
    und derselben Distanz, die aber unter verschiedenen Namen laufen.

    Der Auslöser: "45. Hörnle Berglauf Bad Kohlgrub" und "Hörnlelauf
    Bad Kohlgrub" - beide am 19.09.2026, beide 7 km, beide mit derselben
    vollständigen Adresse (…/veranstaltungen.php?id=94). Laut Quelle ist
    das ein einziges Rennen. Der Namensvergleich in `is_same_event()`
    kommt hier nicht heran: als Wortmengen haben „hornle/berglauf" und
    „hornlelauf" zu wenig gemeinsam.

    Warum das NICHT automatisch zusammengeführt wird: Die Regel wurde
    über den ganzen Bestand durchgerechnet und hätte 48 Paare
    verschmolzen - darunter echte, verschiedene Wettbewerbe derselben
    Veranstaltung: den Marathon des "24h Mad Chicken Run" mit dem
    24-Stunden-Rennen, den "Kolberger Berglauf" mit der Wanderung über
    dieselbe Strecke, und bei der "Heidi-Challenge" die "Tour Werder
    61,8 km" mit der "Tour City Berlin 63,0 km". Genau davor warnt die
    wichtigste Lektion im README. Also: melden, einzeln prüfen,
    bestätigte Fälle nach manual_overrides.json.

    Die VOLLSTÄNDIGE Adresse ist Bedingung, nicht die Domain: Unter
    einer Domain liegen mehrere Rennen eines Veranstalters (deshalb ist
    die Domain auch in `_same_name()` ausdrücklich kein Kriterium).
    """
    gruppen: dict[tuple, list[dict]] = {}
    for event in events:
        url = (event.get("veranstalter_url") or "").strip().rstrip("/")
        if not url or is_portal_link(url) or not event.get("datum_start"):
            continue
        gruppen.setdefault((url, event["datum_start"]), []).append(event)
    meldungen: list[str] = []
    for (url, datum), gruppe in gruppen.items():
        for i, a in enumerate(gruppe):
            for b in gruppe[i + 1:]:
                # Beide Distanzen müssen BEKANNT sein: Ist eine davon
                # None, hält _compatible_distance() alles für kompatibel -
                # so wurde aus dem 42-km-Lauf und dem 24-Stunden-Rennen
                # desselben Veranstalters ein Paar.
                if not isinstance(a.get("laenge_km"), (int, float)):
                    continue
                if not isinstance(b.get("laenge_km"), (int, float)):
                    continue
                if a.get("art1") != b.get("art1"):
                    continue
                if abs(a["laenge_km"] - b["laenge_km"]) > 0.5:
                    continue
                if is_same_event(a, b):
                    continue  # greift ohnehin schon
                meldungen.append(
                    f"{datum} {a['laenge_km']:g} km: {a.get('name')!r} "
                    f"[{a.get('wettbewerb') or '-'}] vs. {b.get('name')!r} "
                    f"[{b.get('wettbewerb') or '-'}] - {url}")
    return sorted(meldungen)


# Zwei km-Angaben in einem Label. "3 Runden je 15,5 km" o. Ä. ist keine
# zweite Strecke, sondern die Aufteilung derselben.
_RUNDEN_RE = re.compile(r"runde|round|\bà\b|\bje\b|\bx\b|mal\b|Rundkurs", re.I)


def report_mehrere_distanzen_im_label(events: list[dict]) -> list[str]:
    """Meldet Wettbewerbs-Label mit ZWEI verschiedenen Streckenlängen.

    Gefunden an "15 km / 21 km Crosslauf" beim Limberglauf Ranis: Die
    Quelle hatte zwei getrennte Wettbewerbe in eine Zeile geschrieben,
    `parse_competitions()` machte daraus einen einzigen Eintrag mit
    21 km - der 15-km-Lauf fehlte in der Liste komplett. Laut
    Ausschreibung gibt es ihn (Start 10:10 Uhr, 15 EUR).

    Das ist die unangenehmere Sorte Fehler: Ein FEHLENDES Event sieht
    niemand. Deshalb die Meldung - was daraus wird (Override oder ein
    genauerer Parser für diese Quelle), entscheidet die Einzelprüfung.

    Nur ein Hinweis, weil die Muster auseinandergehen: "10 km
    (10,50 km)" ist dieselbe Strecke zweimal genannt, "19 km
    (14 + 5 km)" ihre Aufteilung, "100 km (10 x 10 km)" das
    Rundenformat - und "3 000 m, 5 km, 10 km" wirklich drei Rennen.
    """
    meldungen: list[str] = []
    for event in events:
        label = event.get("wettbewerb") or ""
        if not label or _RUNDEN_RE.search(label):
            continue
        werte = {float(z.replace(",", "."))
                 for z in re.findall(r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*km\b", label, re.I)}
        if len(werte) > 1:
            meldungen.append(
                f"{event.get('datum_start')} {event.get('name')} "
                f"[{label}] -> gespeichert: {event.get('laenge_km')} km")
    return sorted(meldungen)


# Wortbestandteile, die bei einem Mehrsport-Wettkampf eine EINZELNE
# Disziplin bezeichnen. Steht so etwas im Wettbewerbs-Label, ist die
# Zeile keine Anmeldemöglichkeit, sondern eine Teilstrecke.
TEILSTRECKE_RE = re.compile(
    r"^(ca\.\s*)?(\d+([.,]\d+)?\s*km\s+)?"
    r"(laufen|lauf|radfahren|rad(strecke)?|schwimmen|schwimmstrecke|run|bike|swim)\b",
    re.I)


def report_multisport_teilstrecken(events: list[dict]) -> list[str]:
    """Meldet Zeilen, die bei einem Mehrsport-Wettkampf nur eine
    TEILSTRECKE beschreiben - und deshalb keine Anmeldemöglichkeit sind.

    Beispiele aus den echten Daten: „Ironman Hamburg · 42,2 km Laufen
    entlang der Alster" (der Laufteil eines Triathlons), „Volks- und
    Staffeltriathlon · 22,5 km Radfahren", „Triathlon Stralsund ·
    Laufen · 10 km". Die Quellen listen bei Triathlons oft die drei
    Disziplinen einzeln auf; `parse_competitions()` hat daraus je eine
    eigene Zeile gemacht.

    **Nur gemeldet, nichts gelöscht** - dieselbe Regel wie bei den
    verdächtigen Distanzen (siehe README, „Datenqualität"): Ob eine
    solche Zeile eine echte Teilstrecke ist oder doch ein eigener
    Wettbewerb (es gibt Staffeln und Einzelstarts über eine Disziplin),
    entscheidet die Ausschreibung, nicht ein Muster. Bestätigte Fälle
    gehören mit `"exclude": true` in manual_overrides.json.
    """
    treffer: list[str] = []
    for event in events:
        if event.get("art1") != "Triathlon":
            continue
        label = (event.get("wettbewerb") or "").strip()
        if not label or not TEILSTRECKE_RE.match(label):
            continue
        treffer.append(f"{event.get('name')} ({event.get('datum_start')}): "
                       f"Label {label!r}, {event.get('laenge_km')} km - "
                       f"sieht nach einer Teilstrecke aus")
    return treffer


# Die Gesamtdistanzen der geläufigen Triathlon-Formate in km (Schwimmen +
# Rad + Laufen zusammen). Nur zum PRÜFEN, nie zum Überschreiben.
TRIATHLON_DISTANZEN_KM = (
    25.75,   # Super-Sprint / Jedermann (halbe Sprintdistanz, grob)
    51.5,    # Sprint 25,75 / Olympisch 51,5 (Ironman-Marke: 5150)
    113.0,   # Mitteldistanz / Ironman 70.3
    226.0,   # Langdistanz / Ironman
)


# Kategorien, die es NUR beim Laufen gibt. Ein Triathlon im Gelände heißt
# "Cross"; trägt eine Triathlon-Zeile "Trail", "Bahn" oder "Hindernis",
# stammt die Kategorie aus der Lauf-Liste - und meist ist die Zeile ein
# Lauf, der als Triathlon einsortiert wurde.
LAUF_KATEGORIEN_NUR_LAUFEN = {"Trail", "Bahn", "Hindernis"}


def report_triathlon_mit_laufkategorie(events: list[dict]) -> list[str]:
    """Meldet Triathlon-Zeilen mit einer Kategorie, die es nur beim Laufen
    gibt.

    Gefunden am "O-SEE Ultra Trail" (Nutzer 21.09.2026: "hat nichts mit
    Triathlon zu tun - Triathlons können auch nicht wirklich ein Trail
    Event sein"): Die Kinderläufe und der Canicross standen als
    Triathlon/Trail in der Liste und entgingen so der 5-km-Regel, die
    nur für Laufen gilt. Nur Meldung, keine Umstellung - ob die Zeile
    ein Lauf ist (dann Override `art1: Laufen`) oder ein Cross-Triathlon
    (dann `art2: Cross`), entscheidet die Ausschreibung.
    """
    return [
        f"{e.get('name')} ({e.get('datum_start')}, {e.get('wettbewerb') or '–'}, "
        f"{e.get('art2')}): wahrscheinlich ein Lauf – Override art1 prüfen"
        for e in events
        if e.get("art1") == "Triathlon" and e.get("art2") in LAUF_KATEGORIEN_NUR_LAUFEN
    ]


def report_triathlon_distanzen(events: list[dict]) -> list[str]:
    """Meldet Triathlon-Zeilen, deren Distanz zu keinem gängigen Format
    passt.

    Ein Triathlon ist die SUMME aus Schwimmen, Rad und Laufen; die
    üblichen Formate liegen bei ~26, ~52, 113 und 226 km. Steht dort
    etwas ganz anderes (im Bestand z. B. „Ironman Hamburg · 178 km" -
    das ist die Radstrecke, oder „Ironman 70.3 Kraichgau · 52 km" - das
    ist die olympische Distanz, nicht die 113 km einer 70.3), stimmt
    entweder die Zahl nicht oder die Zeile gehört zu einem anderen
    Wettbewerb derselben Veranstaltung.

    **Nur gemeldet.** Die Marke sagt zwar die Solldistanz („70.3" sind
    113 km), aber viele Ironman-Veranstaltungen tragen an einem
    Wochenende mehrere Wettbewerbe aus - die 52 km könnten also der
    5150-Wettbewerb sein, der nur falsch zugeordnet ist. Automatisch
    überschreiben würde hier echte Daten verfälschen; die Lehre dazu
    steht im README.
    """
    treffer: list[str] = []
    for event in events:
        if event.get("art1") != "Triathlon":
            continue
        # Nur der klassische Triathlon (Schwimmen-Rad-Laufen) hat diese
        # Formate. Ein Duathlon, ein Aquathlon oder ein SwimRun hat ganz
        # andere Gesamtlängen - ein 15-km-SwimRun ist völlig normal und
        # gehört nicht in diese Meldung.
        if event.get("art2") not in ("Straße", "Cross"):
            continue
        km = event.get("laenge_km")
        if km is None:
            continue
        # 15 % Toleranz: Die Strecken weichen von Ort zu Ort ab (ein
        # "Olympischer" Triathlon kann 48 oder 52 km lang sein).
        if any(abs(km - soll) <= soll * 0.15 for soll in TRIATHLON_DISTANZEN_KM):
            continue
        treffer.append(f"{event.get('name')} ({event.get('datum_start')}): "
                       f"{km} km passt zu keinem Triathlon-Format"
                       + (f", Label {event.get('wettbewerb')!r}" if event.get("wettbewerb") else ""))
    return treffer


def report_moegliche_duplikate(events: list[dict]) -> list[str]:
    """Meldet Paare, die WAHRSCHEINLICH dieselbe Veranstaltung sind: gleicher
    Tag, gleicher Ort, gleiche Distanz - aber Namen, die das automatische
    Dedupe nicht als ähnlich erkennt.

    Beispiel aus den echten Daten (vom Nutzer gemeldet): Am 19.09.2026
    standen in Gefrees „13. Fichtelgebirgstrailrun" (21 km) und
    „Fichtellauf · Halbmarathon" (21 km) nebeneinander - dasselbe Rennen,
    einmal unter dem Namen der Trail-Unterseite des Veranstalters. Die
    Namensvergleiche in `is_same_event()` haben keine Chance: Die beiden
    Namen teilen kein einziges Wort.

    **Nur gemeldet, nichts zusammengeführt** - und das ist hier besonders
    wichtig: Ein Straßenlauf und ein Trailrun desselben Veranstalters am
    selben Tag über dieselbe Distanz sind ein häufiger, ECHTER Fall. Die
    Regel „gleicher Tag + Ort + Distanz = Duplikat" würde solche Paare
    verschmelzen und ein echtes Rennen unsichtbar machen. Genau davor
    warnt die wichtigste Lektion im README. Bestätigte Fälle gehören
    einzeln mit `"exclude": true` in manual_overrides.json.
    """
    from collections import defaultdict

    gruppen: dict[tuple, list[dict]] = defaultdict(list)
    for event in events:
        km = event.get("laenge_km")
        if km is None or not event.get("datum_start") or not event.get("standort"):
            continue
        gruppen[(event["datum_start"], event["standort"].casefold(), round(float(km), 1))].append(event)

    treffer: list[str] = []
    for (datum, _ort, km), gruppe in sorted(gruppen.items()):
        namen = {(e.get("name") or "").casefold() for e in gruppe}
        if len(namen) < 2:
            continue
        beschreibung = " || ".join(
            f"{e.get('name')} [{e.get('art2')}]" for e in gruppe)
        treffer.append(f"{datum}, {gruppe[0].get('standort')}, {km:g} km: {beschreibung}")
    return treffer


def fix_halbmarathon_distance(events: list[dict]) -> list[str]:
    """Einmalige Datenkorrektur zu einem behobenen Bug: Der Stichwort-
    Fallback in `guess_distance_km()` prüfte "marathon" vor "halbmarathon"
    und trug für Events wie "35. Halbmarathon Altötting" 42,2 km statt
    21,1 km ein. Der Code ist gefixt (Stichwörter werden nach Länge
    absteigend geprüft), die bereits gespeicherten Werte muss dieses
    Skript nachziehen.

    Bewusst sehr eng gefasst: nur Einträge, deren Name "halbmarathon"
    enthält, deren gespeicherte Distanz genau dem Marathon-Fallback
    42,2 km entspricht und in deren Namen kein eigenständiges "Marathon"
    steht (sonst könnten 42,2 km korrekt sein, weil das Event beide
    Distanzen anbietet). Nach der Korrektur trifft die Bedingung auf
    keinen Eintrag mehr zu - das Skript bleibt idempotent."""
    changed: list[str] = []
    for event in events:
        name = (event.get("name") or "").lower()
        if "halbmarathon" not in name or event.get("laenge_km") != 42.2:
            continue
        if re.search(r"(?<!halb)marathon", name.replace("halbmarathon", "hm")):
            continue  # eigenständiges "Marathon" im Namen -> 42,2 km evtl. korrekt
        event["laenge_km"] = 21.1
        changed.append(f"{event.get('name')}: laenge_km 42.2 -> 21.1")
    return changed


def fix_meter_labels(events: list[dict]) -> list[str]:
    """Nennt das Wettbewerbs-Label die Strecke nur in METERN ("Mini
    Marathon mit 150 m, 300 m, 550 m und 900 m", "Hauptlauf 7.900 m"),
    ist die größte Meterangabe die Distanz - `scraper_lib.meter_km()`
    liest sie seit dem 22.09.2026 beim Einsammeln. Dieser Schritt zieht
    den Bestand nach: Der "Mini Marathon" des Traunsee Halbmarathons (ein
    Kinderlauf bis 900 m, ÖLV-Kalender) stand mit 21,1 km in der Liste,
    weil das Label auf das Stichwort "Marathon" zurückfiel und der
    Halbmarathon-Bugfix daraus 21,1 machte. Mit 0,9 km fällt er dann über
    die Mindestdistanz heraus. Am Bestand nachgezählt (5.643 Zeilen):
    genau diese eine Zeile; Rundungsunterschiede bis 0,1 km ("9.350 m"
    neben 9,4 km) bleiben unangetastet. Idempotent."""
    changed: list[str] = []
    for event in events:
        label = event.get("wettbewerb") or ""
        km = event.get("laenge_km")
        if not label or km is None:
            continue
        mk = meter_km(label)
        if mk is None or abs(mk - km) <= 0.1:
            continue
        changed.append(f"{event.get('name')} ({label[:40]}): laenge_km {km:g} -> {mk:g}")
        event["laenge_km"] = mk
    return changed


def round_distances(events: list[dict]) -> list[str]:
    """Rundet alle Längenangaben auf eine Nachkommastelle.

    Die Quellen geben dieselbe Strecke unterschiedlich genau an: Marathon
    mal als "42,195 km", mal als "42,2 km", Halbmarathon als "21,0975 km".
    In der Liste soll einheitlich 42.2 bzw. 21.1 stehen (Wunsch aus dem
    Chat). Die Scraper runden inzwischen selbst (siehe
    scraper_lib.round_km()), die bereits gespeicherten Werte zieht dieses
    Skript nach.
    """
    changed: list[str] = []
    for event in events:
        km = event.get("laenge_km")
        rounded = round_km(km)
        if rounded is not None and rounded != km:
            changed.append(f"{event.get('name')}: laenge_km {km} -> {rounded}")
            event["laenge_km"] = rounded
    return changed


# Ein Wettbewerbs-Label, das mit einem deutschen Datum BEGINNT. Zwei in
# den Daten vorkommende Formen: nur das Datum ("07.02.2027") und Datum
# plus Streckenbeschreibung ("14.11.2026 - 10 km Hauptlauf"). Der Rest
# hinter dem Trennzeichen bleibt als Label erhalten, falls er etwas sagt.
_DATE_LABEL = re.compile(
    r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\s*(?:[-–—|,:]\s*(?P<rest>.*))?$"
)

# Zweite Form: das Datum steht MITTEN im Label, eingeleitet von "am" -
# "15,0 km (am 14.02.2027 für M/W ab 18 bis M/W85)" (Hammer
# Winterlaufserie). Dasselbe Signal wie oben, nur anders gesetzt: Das
# Label sagt, an welchem Termin der Serie diese Strecke gelaufen wird.
# Bewusst eng: "am" muss davorstehen (ein blankes Datum irgendwo im Text
# kann alles Mögliche sein, etwa eine Anmeldefrist), und der Termin muss
# innerhalb des gespeicherten Zeitraums der Veranstaltung liegen - siehe
# `_datum_aus_label()`.
_DATE_IM_LABEL = re.compile(r"\bam\s+(\d{1,2})\.(\d{1,2})\.(\d{4})")

# Wörter, nach denen ein Datum KEIN Wettkampftermin ist. Ohne das würde
# "10 km (Anmeldeschluss am 14.02.2027)" den Lauf auf den Meldeschluss
# schieben - der kann durchaus im Zeitraum der Serie liegen.
_KEIN_TERMIN = re.compile(r"meldeschluss|anmeld|nachmeld|meldefrist|ummeld", re.I)


def _datum_aus_label(event: dict) -> tuple[str, str] | None:
    """Termin aus einem Label der Form "... (am TT.MM.JJJJ ...)".

    Gibt `(iso_datum, neues_label)` zurück oder `None`. Der Termin wird
    nur angenommen, wenn er im Zeitraum der Veranstaltung liegt: Eine
    Serie vom 31.01. bis 28.02. kann keine Strecke am 14.03. haben, ein
    Datum ausserhalb ist also etwas anderes (Anmeldeschluss, Ausweich-
    termin, Vorjahr) und wird nicht angefasst.
    """
    label = (event.get("wettbewerb") or "").strip()
    match = _DATE_IM_LABEL.search(label)
    if not match or _KEIN_TERMIN.search(label):
        return None
    day, month, year = (int(match.group(i)) for i in (1, 2, 3))
    try:
        termin = date(year, month, day).isoformat()
    except ValueError:
        return None
    start = event.get("datum_start") or ""
    ende = event.get("datum_ende") or start
    if not start or not (start <= termin <= ende):
        return None
    # Den Klammerzusatz mit dem Datum entfernen, den Rest behalten.
    rest = re.sub(r"\s*\((?:[^()]*\bam\s+\d{1,2}\.\d{1,2}\.\d{4}[^()]*)\)", "", label)
    rest = _DATE_IM_LABEL.sub("", rest)      # auch ohne Klammern ("10 km am 14.02.2027")
    rest = re.sub(r"\s{2,}", " ", rest).strip(" -–—|,:")
    return termin, rest


def fix_series_dates(events: list[dict]) -> list[str]:
    """Korrigiert Laufserien, bei denen die Quelle als "Wettbewerbe" die
    TERMINE der einzelnen Läufe auflistet.

    Beispiel Winterlaufserie Drelsdorf: Die Serie besteht aus drei Läufen
    in 14-tägigem Abstand, und jeder Termin hat seine eigene Hauptdistanz
    (laut Veranstalter 10.01. = 10 km, 24.01. = 15 km, 07.02. = 21,1 km).
    Die Streckenliste der Quelle nennt aber die Datumsangaben, nicht
    Streckennamen. `expand_competitions()` hat daraus je Termin ALLE drei
    Distanzen gemacht - neun Einträge statt drei, sechs davon frei
    erfunden.

    Ein Label, das nur ein Datum ist, benennt also den Termin, zu dem
    diese Strecke gehört. Deshalb wird das Datum des Eintrags darauf
    gesetzt und das Label geleert. Die dadurch entstehenden echten
    Duplikate führt der nachfolgende Merge-Schritt zusammen - daher läuft
    diese Korrektur VOR ihm.

    Bewusst kein Löschen: bei der "Alten-Busecker Winterlaufserie" lagen
    alle drei Einträge auf dem ersten Termin. Hätte man die
    nicht-passenden verworfen, wären zwei reale Läufe verloren gegangen -
    so bekommen sie ihr richtiges Datum.
    """
    changed: list[str] = []
    for event in events:
        label = (event.get("wettbewerb") or "").strip()
        aus_klammer = _datum_aus_label(event)
        if aus_klammer:
            termin, rest = aus_klammer
            if termin != event.get("datum_start") or termin != event.get("datum_ende"):
                changed.append(
                    f"{event.get('name')} ({event.get('laenge_km')} km): "
                    f"Datum {event.get('datum_start')} -> {termin} (laut Label {label!r})"
                )
            event["datum_start"] = termin
            event["datum_ende"] = termin
            if rest:
                event["wettbewerb"] = rest
            else:
                event.pop("wettbewerb", None)
            continue
        match = _DATE_LABEL.match(label)
        if not match:
            continue
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            real_date = date(year, month, day).isoformat()
        except ValueError:
            continue  # unmögliches Datum - Label lieber unangetastet lassen
        if real_date != event.get("datum_start"):
            changed.append(
                f"{event.get('name')} ({event.get('laenge_km')} km): "
                f"Datum {event.get('datum_start')} -> {real_date} (laut Label {label!r})"
            )
            event["datum_start"] = real_date
            event["datum_ende"] = real_date
        rest = (match.group("rest") or "").strip(" -–—|,:")
        if rest:
            event["wettbewerb"] = rest
        else:
            event.pop("wettbewerb", None)
    return changed


def drop_contradicting_wettbewerb(events: list[dict]) -> list[str]:
    """Entfernt eine Wettbewerbs-Bezeichnung, die ihrer eigenen Distanz
    widerspricht.

    Die Bezeichnung nennt oft selbst eine Distanz ("0,7 km", "2,5km
    Kreismeisterschaft"). Steht dort eine ANDERE Zahl als in `laenge_km`,
    ist das Label an den falschen Eintrag geraten - real vorgekommen, weil
    `wettbewerb` früher Teil von ENRICHABLE_FIELDS war und damit aus einem
    fremden Eintrag ergänzt wurde (dort inzwischen entfernt). Betroffen
    waren z. B. Label "0,7 km" an einem 7,5-km-Eintrag und "2,5km
    Kreismeisterschaft" an einem mit 25 km.

    Entfernt wird nur das LABEL, nie die Distanz: welche der beiden
    Angaben stimmt, lässt sich ohne Blick in die Quelle nicht sagen, und
    die Distanz ist das Feld, auf das die Liste filtert.

    Kleine Abweichungen bleiben unangetastet: Quellen runden ihre Labels
    ("6 km" für exakt 5,7 km), das ist kein Widerspruch. Ebenso Labels mit
    MEHREREN Distanzen ("15 km / 21 km"), bei denen die gespeicherte die
    größte davon ist - das ist das dokumentierte Verhalten von
    guess_distance_km().
    """
    changed: list[str] = []
    for event in events:
        label = event.get("wettbewerb")
        km = event.get("laenge_km")
        if not label or not isinstance(km, (int, float)):
            continue
        found = [round(float(m.replace(",", ".")), 1)
                 for m in re.findall(r"(\d{1,3}(?:[.,]\d+)?)\s*km", label, re.I)]
        if not found:
            continue
        # Passt eine der genannten Zahlen (mit Rundungstoleranz), ist alles gut.
        if any(abs(value - km) <= max(0.5, km * 0.05) for value in found):
            continue
        changed.append(
            f"{event.get('name')} ({km:g} km): Label {label!r} nennt "
            f"{', '.join(f'{v:g}' for v in found)} km - entfernt"
        )
        event.pop("wettbewerb", None)
    return changed


def needs_land_check(event: dict) -> bool:
    """Entscheidet, ob für dieses Event eine Reverse-Geocoding-Anfrage
    lohnt. Bewusst nicht für alle Events: Nominatim erlaubt etwa eine
    Anfrage pro Sekunde, ein Komplettdurchlauf über alle Events dauert
    über eine Stunde - und wäre zum größten Teil verschwendet, weil eine
    FÜNFSTELLIGE Postleitzahl eindeutig Deutschland bedeutet und die
    daraus abgeleiteten Länder damit bereits belastbar sind.

    Geprüft werden daher genau die beiden Fälle, in denen der gespeicherte
    Wert nachweislich falsch sein kann:

    1. `land` fehlt ganz - fast immer eine vierstellige PLZ, die
       Österreich und Schweiz nicht unterscheidet (Mosnang, Innsbruck,
       Schwaz).
    2. `land` ist NICHT Deutschland, oder der Event-NAME enthält ein
       Länder-Stichwort. Nicht-deutsche Länder sind die Minderheit und
       genau die, die aus unsicheren Signalen entstanden sind; und ein
       Länderwort im Namen ist die bekannte Fehlerquelle („25.
       Fränkische-Schweiz-Marathon" in Bayern stand als `land: "Schweiz"`
       in events.json, weil ein Scraper das Land aus dem Namen geraten
       hat).
    """
    land = event.get("land")
    if not land:
        return True
    if land != "Deutschland":
        return True
    return bool(guess_land(event.get("name") or ""))


def fix_land(events: list[dict], geocoder: Geocoder | None) -> list[str]:
    """Ergänzt fehlendes und korrigiert falsches `land`.

    Maßgeblich sind die Koordinaten (Reverse-Geocoding) - die einzige
    Quelle, die Österreich und Schweiz zuverlässig unterscheidet. Welche
    Events überhaupt geprüft werden, entscheidet `needs_land_check()`.
    Ergebnisse landen im gemeinsamen Geocode-Cache, ein zweiter Lauf
    fragt also nichts erneut ab. Ohne `geocoder` (--no-geocoding) bleibt
    nur der Ortsname als schwaches Signal für Events ohne `land`.
    """
    changed: list[str] = []
    for event in events:
        if not needs_land_check(event):
            continue

        lat, lon = event.get("lat"), event.get("lon")
        current = event.get("land")

        land = None
        if geocoder and lat is not None and lon is not None:
            land = geocoder.reverse_land(lat, lon)
        if not land and not current:
            land = guess_land(event.get("standort") or "")

        if land and land != current:
            changed.append(
                f"{event.get('name')} ({event.get('standort')}): "
                f"land {current!r} -> {land!r}"
            )
            event["land"] = land
    return changed


def drop_past_events(events: list[dict],
                     today: str | None = None) -> tuple[list[dict], list[str]]:
    """Entfernt Events, die vorbei sind. Eine Liste, in der ein Lauf vom
    letzten März steht, ist für niemanden nützlich - und die Scraper
    holen vergangene Termine aus den Kalendern immer wieder mit herein,
    solange die Quelle sie dort stehen lässt.

    Maßgeblich ist das ENDE der Veranstaltung: ein dreitägiges Etappen-
    rennen, das gestern begonnen hat, läuft noch und bleibt. Der heutige
    Tag selbst bleibt immer drin.

    Ein Event mit unlesbarem oder fehlendem Datum wird NICHT gelöscht,
    sondern behalten (und im Bericht als Hinweis geführt) - dieselbe
    Linie wie bei den Distanzen: nicht auf Unsicherheit hin löschen,
    denn zu viel gelöscht ist unsichtbar."""
    heute = today or date.today().isoformat()
    kept, dropped = [], []
    for event in events:
        ende = event.get("datum_ende") or event.get("datum_start")
        if not isinstance(ende, str) or not ISO_DATE_PATTERN.match(ende):
            kept.append(event)
            continue
        if ende < heute:
            dropped.append(f"{event.get('name')} ({ende})")
        else:
            kept.append(event)
    return kept, dropped


def fill_duration(events: list[dict]) -> list[str]:
    """Trägt `dauer_h` bei zeitlich begrenzten Rennen nach.

    Nötig, weil das Feld erst später dazugekommen ist: Ein
    "24-Stunden-Lauf" aus einem früheren Lauf hat es noch nicht, und die
    Scraper ändern bestehende Einträge nie. Quelle ist der
    Veranstaltungsname plus das Wettbewerbs-Label - dieselbe Erkennung
    wie beim Einsammeln (`scraper_lib.parse_duration_h()`, inklusive der
    Absicherung gegen Zielschlusszeiten wie "Zeitlimit 6 Stunden").

    Ein vorhandener Wert wird nicht angetastet, auch nicht, wenn die
    Erkennung nichts findet - ein per Override gesetztes `dauer_h` ist
    die bessere Auskunft."""
    changed: list[str] = []
    for event in events:
        if event.get("dauer_h") is not None:
            continue
        # Nur Einträge OHNE Distanz. Sonst wird aus dem "24h Mad Chicken
        # Run | Marathon, 42 km" ein Zeitrennen, obwohl die Zeile eine
        # feste 42-km-Strecke innerhalb einer 24-Stunden-Veranstaltung
        # beschreibt: Das "24h" steht im Namen des Festivals, nicht in
        # dieser Strecke.
        if event.get("laenge_km") is not None:
            continue
        text = f"{event.get('name') or ''} {event.get('wettbewerb') or ''}"
        dauer = parse_duration_h(text)
        if dauer is None:
            continue
        event["dauer_h"] = dauer
        changed.append(f"{event.get('name')} ({event.get('wettbewerb') or '-'}): "
                       f"dauer_h = {dauer:g} h")
    return changed


# Die klassische Backyard-Runde ist 4,167 Meilen = 6,706 km lang (so
# gesetzt, dass 24 Runden 100 Meilen ergeben); die Quellen schreiben
# 6,7 oder gerundet 7 km. Alles bis zu dieser Grenze ist auf einer
# Backyard-Zeile die RUNDE, nicht die Renndistanz.
BACKYARD_LAP_MAX_KM = 10.0


def clear_backyard_lap_km(events: list[dict]) -> tuple[list[str], list[str]]:
    """Nimmt die Rundenlänge aus `laenge_km` von Backyard-Events heraus.

    Ein Backyard Ultra läuft dieselbe Runde zur gleichen Stunde, bis nur
    noch eine Person weiterläuft - die Runde ist keine Wettkampfdistanz.
    In den Daten standen 18 solcher Events mit "7 km" bzw. "6,7 km" in
    der Länge-Spalte; wer nach "5-10 km" filterte, fand dadurch Rennen,
    bei denen man 200 km läuft. Die Länge zeigt danach "-" (oder die
    Dauer, falls das Rennen auf z. B. 24 Stunden begrenzt ist).

    Größere Angaben werden NICHT angetastet, sondern nur gemeldet: bei
    "RET-Team Backyard | 80 km" oder "Murr BackYard 12h | 67 km" ist
    unklar, ob das eine Zielvorgabe, eine Teamwertung oder doch eine
    Runde ist - solche Fälle gehören einzeln geprüft (siehe README,
    "Die wichtigste Lektion"). Gibt (geleert, zu prüfen) zurück."""
    cleared: list[str] = []
    to_check: list[str] = []
    for event in events:
        if event.get("art2") != "Backyard Ultra":
            continue
        km = event.get("laenge_km")
        if not isinstance(km, (int, float)):
            continue
        if km <= BACKYARD_LAP_MAX_KM:
            event["laenge_km"] = None
            cleared.append(f"{event.get('name')}: {km:g} km (Runde) entfernt")
        else:
            to_check.append(f"{event.get('name')}: {km:g} km - Runde, "
                            f"Zielvorgabe oder Teamwertung? bitte prüfen")
    return cleared, to_check


def drop_too_short(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Entfernt Zeilen unter der Mindestdistanz ihrer Sportart
    (MIN_DISTANCE_BY_ART1: Laufen 5 km, seit dem 24.09.2026 Schwimmen
    500 m). Fahrrad und Triathlon haben keine: 3,5 km Freiwasserschwimmen
    sind eine ernsthafte Distanz, und der 300-m-Schwimmteil eines
    Super-Sprints ist keine Schwimmveranstaltung. Ein Zeitrennen ist nie
    "zu kurz": beim 24-Stunden-Lauf auf einer 1-km-Runde ist die
    Rundenlänge keine Wettkampfdistanz (`scraper_lib.ist_zu_kurz`)."""
    kept, dropped = [], []
    for event in events:
        km = event.get("laenge_km")
        too_short = (
            isinstance(km, (int, float))
            and ist_zu_kurz(event.get("art1"), km, event.get("dauer_h"))
        )
        if too_short:
            dropped.append(f"{event.get('name')} ({km} km, {event.get('art1')})")
        else:
            kept.append(event)
    return kept, dropped


def drop_nicht_offen_schwimmen(events: list[dict]) -> tuple[list[dict], list[str]]:
    """Entfernt Schwimm-Meisterschaften - das Gegenstück zu
    `scraper_lib.filter_nicht_offen_schwimmen()` für den Bestand (vom
    Nutzer am 24.09.2026 entschieden: nur Schwimm-Events, für die sich
    jeder anmelden kann). Nur `art1 == "Schwimmen"`, jede Zeile wird
    gemeldet."""
    kept: list[dict] = []
    entfernt: list[str] = []
    for event in events:
        grund = ist_nicht_offen_schwimmen(event.get("art1"), event.get("name"),
                                          event.get("wettbewerb"))
        if grund:
            entfernt.append(f"{event.get('name')} ({event.get('datum_start')}) - {grund}")
        else:
            kept.append(event)
    return kept, entfernt


# Distanzen, die ein Veranstaltungsname selbst ankündigt. Steht das Wort im
# Namen, ist die Distanz belegt - egal, was die Aufzählung einer anderen
# Quelle enthält.
NAME_DISTANCE_CLAIMS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"(?<!halb)marathon", re.I), 42.2),
    (re.compile(r"halbmarathon|half ?marathon", re.I), 21.1),
    (re.compile(r"ultra|100 ?km|24 ?(?:h|stunden)|backyard", re.I), 100.0),
]


def name_announces_distance(name: str | None, km: float) -> bool:
    """True, wenn der Veranstaltungsname die Distanz `km` selbst nennt.

    "Marathon" im Namen belegt eine 42,2-km-Strecke, "Ultra"/"24h" eine
    beliebig lange. Schützt echte Distanzen davor, wegen einer
    unvollständigen Streckenliste einer anderen Quelle gelöscht zu werden.
    """
    if not name:
        return False
    # "Halbmarathon" enthält "marathon" - der Negative-Lookbehind im ersten
    # Muster verhindert, dass ein Halbmarathon-Name 42,2 km belegt.
    for pattern, claimed in NAME_DISTANCE_CLAIMS:
        if pattern.search(name) and km >= claimed - max(0.5, claimed * 0.05):
            return True
    return False


# Erkennt eine schlecht formatierte Auflagen-Nummer ohne Leerzeichen
# dahinter ("37.Bessunger Merck-Lauf").
_ORDINAL_NO_SPACE = re.compile(r"^\d+\.\S")


def tidy_name(name: str) -> str:
    """Repariert reine Formatierungsmängel eines Namens: mehrfache
    Leerzeichen zusammenziehen, Rand trimmen, fehlendes Leerzeichen nach
    der Auflagen-Nummer ergänzen.

    Das ist eine reine Schreibweisen-Korrektur ("17.  Preungesheimer
    Dorflauf" -> "17. Preungesheimer Dorflauf", "37.Bessunger Merck-Lauf"
    -> "37. Bessunger Merck-Lauf") und macht Kandidaten vergleichbar, die
    sich NUR in der Formatierung unterscheiden.
    """
    cleaned = re.sub(r"\s+", " ", (name or "")).strip()
    return re.sub(r"^(\d+\.)(?=\S)", r"\1 ", cleaned)


_UMLAUT_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def fold_umlauts(name: str) -> str:
    """Schlüssel, unter dem Umschrift und echte Schreibweise zusammenfallen:
    "Baedleslauf" und "Bädleslauf" ergeben beide "baedleslauf"."""
    return name.casefold().translate(_UMLAUT_FOLD)


_LEADING_ORDINAL = re.compile(r"^(\d+\.\s*)")


def has_umlauts(name: str) -> bool:
    return any(c in name for c in "äöüÄÖÜß")


def repair_umlaut_spelling(winner: str, candidates: list[str]) -> str:
    """Setzt im Gewinner-Namen die korrekte deutsche Schreibweise, wenn ein
    anderer Kandidat sie liefert.

    Die Umlaut-Frage ist keine Auswahl-, sondern eine Reparaturfrage:
    "Bädleslauf" ist objektiv richtig und "Baedleslauf" objektiv falsch,
    unabhängig davon, welche Variante häufiger vorkommt oder ob eine
    Auflagen-Nummer davorsteht. Zwei Versuche vorher gingen daneben:

    * "enthält Umlaut" als allgemeines Qualitätsmerkmal - dadurch verlor
      "Wiesent Challenge" gegen einen 108 Zeichen langen Namen, nur weil
      darin das Wort "Straßenlauf" vorkam.
    * Zusammenführen anhand der gefalteten Form - das griff nicht, sobald
      sich die Varianten ZUSÄTZLICH in der Auflagen-Nummer unterschieden
      ("22. Baedleslauf" gegen "Bädleslauf").

    Deshalb wird hier nur der TEXT NACH der Auflagen-Nummer ersetzt, und
    nur wenn er sich vom Gewinner ausschließlich in der Umschrift
    unterscheidet. Die Nummer selbst bleibt, wie die Mehrheit sie
    entschieden hat.
    """
    if has_umlauts(winner):
        return winner
    prefix_match = _LEADING_ORDINAL.match(winner)
    prefix = prefix_match.group(1) if prefix_match else ""
    body = winner[len(prefix):]
    for candidate in candidates:
        other_body = _LEADING_ORDINAL.sub("", candidate)
        if has_umlauts(other_body) and fold_umlauts(other_body) == fold_umlauts(body):
            return prefix + other_body
    return winner


def name_quality_hard(name: str) -> tuple:
    """Schreibweisen-Mangel, den die Mehrheit NICHT durchsetzen darf:
    durchgehende GROSSSCHREIBUNG ("MARATHON MÜNCHEN" gegen "Marathon
    München by Brooks"). Die Umlaut-Frage klärt vorher
    `prefer_umlaut_spelling()`."""
    letters = [c for c in name if c.isalpha()]
    return (not (len(letters) >= 4 and name == name.upper()),)


# Ab dieser Länge ist ein "Name" in Wahrheit eine Beschreibung und taugt
# nicht für die Namensspalte der Liste. Echter Fall: "5. Wiesent-Challenge
# 10 km Straßenlauf und 12 km Panoramatrail mit Oberfränkischen
# Meisterschaften im Trail-Lauf" (108 Zeichen) hätte über die Regel
# "länger ist besser" gegen "Wiesent Challenge" gewonnen.
MAX_SENSIBLE_NAME_LENGTH = 60

# Obergrenze für die Iteration aus Zusammenführen und
# Namen-Vereinheitlichen (siehe main()). In der Praxis ist nach zwei
# bis drei Durchläufen Ruhe.
MAX_MERGE_PASSES = 8


def name_quality_soft(name: str) -> tuple:
    """Nachrangige Kriterien, erst wenn Schreibweise UND Häufigkeit
    gleichstehen.

    Längere Namen tragen meist mehr Information ("Wehringer Wertachlauf
    mit schwäbischen Meisterschaften") - aber nur bis zu einer sinnvollen
    Grenze, jenseits derer der "Name" die komplette Ausschreibung
    wiedergibt. Alphabetisch als letzter Anker, damit das Ergebnis
    reproduzierbar ist und der Lauf idempotent bleibt."""
    return (
        len(name) <= MAX_SENSIBLE_NAME_LENGTH,
        len(name),
        tuple(-ord(c) for c in name.casefold()),
    )


def tidy_all_names(events: list[dict]) -> list[str]:
    """Repariert Formatierungsmängel in JEDEM Event-Namen.

    `unify_event_names()` ruft `tidy_name()` nur für Veranstaltungen auf,
    die mehr als einen Namen tragen. Ein Einzel-Event mit doppeltem
    Leerzeichen ("19. Parforceheide  Crosslauf") oder fehlendem
    Leerzeichen nach der Nummer ("41.  Memmelsdorfer Schlosslauf") bliebe
    dadurch unangetastet, obwohl der Mangel derselbe ist.

    Nur Leerraum und das Leerzeichen nach der Auflagen-Nummer - die
    Groß-/Kleinschreibung bleibt unberührt, weil sich Namen wie "REWE",
    "DJK" oder "AOK" nicht zuverlässig umschreiben lassen.
    """
    changed: list[str] = []
    for event in events:
        name = event.get("name")
        if not name:
            continue
        tidied = tidy_name(name)
        if tidied != name:
            changed.append(f"{name!r} -> {tidied!r}")
            event["name"] = tidied
    return changed


def unify_event_names(events: list[dict]) -> list[str]:
    """Gibt allen Einträgen derselben Veranstaltung denselben Namen.

    Eine Veranstaltung steht mit je einem Eintrag pro Strecke in der Liste.
    Kommen diese Einträge aus verschiedenen Quellen, tragen sie
    unterschiedliche Schreibweisen desselben Namens - beim Münchner
    Marathon etwa "MARATHON MÜNCHEN" (42,2 km) neben "Marathon München by
    Brooks" (21,1 und 10 km). In der Liste sieht das nach drei
    verschiedenen Veranstaltungen aus.

    Auswahl in drei Stufen: erst `name_quality_hard()` (Schreibweisen-
    Mängel, die eine Mehrheit nicht durchsetzen darf), dann die
    Häufigkeit in der Gruppe, dann `name_quality_soft()`. Vorher
    repariert `tidy_name()` reine Formatierungsmängel.

    Beim häufigsten Einzelfall - Auflagen-Nummer vorhanden oder nicht -
    entscheidet damit die Quellenmehrheit. Es wird bewusst NICHT
    versucht, die Nummer generell zu entfernen oder zu ergänzen: das wäre
    eine inhaltliche Änderung, keine Vereinheitlichung.

    Events mit einem Eintrag in `manual_overrides.json` werden
    ÜBERSPRUNGEN: die Schlüssel dort beginnen mit dem Namen, ein
    Umbenennen würde den Override unwirksam machen.
    """
    overrides = load_manual_overrides()
    by_date: dict[str | None, list[dict]] = {}
    for event in events:
        by_date.setdefault(event.get("datum_start"), []).append(event)

    changed: list[str] = []
    for group in by_date.values():
        clusters: list[list[dict]] = []
        for event in group:
            for cluster in clusters:
                if any(is_same_race(member, event) for member in cluster):
                    cluster.append(event)
                    break
            else:
                clusters.append([event])

        for cluster in clusters:
            names = [e.get("name") for e in cluster if e.get("name")]
            if len(set(names)) < 2:
                continue
            if any(find_override(overrides, e.get("name"), e.get("datum_start"),
                                 e.get("laenge_km")) for e in cluster):
                continue  # Override-Schlüssel nicht zerstören
            # Zuerst Formatierung reparieren - dadurch fallen Kandidaten
            # zusammen, die sich nur darin unterschieden.
            tidied = [tidy_name(n) for n in names]
            counts = Counter(tidied)
            canonical = max(
                counts,
                key=lambda n: (name_quality_hard(n), counts[n], name_quality_soft(n)),
            )
            canonical = repair_umlaut_spelling(canonical, tidied)
            for event in cluster:
                if event.get("name") != canonical:
                    changed.append(
                        f"{event.get('datum_start')} {event.get('name')!r} -> {canonical!r}"
                    )
                    event["name"] = canonical
    return changed


def report_suspicious_distances(events: list[dict]) -> list[str]:
    """MELDET (löscht nicht!) Distanzen, die der Streckenaufzählung einer
    anderen Quelle für dieselbe Veranstaltung widersprechen.

    Konkreter Fall aus den Daten: Der BraunenBerg-Lauf in Aalen steht bei
    running.life mit seinen drei Strecken (32 km, 14,6 km, 8,2 km, jeweils
    mit Streckennamen) - und bei laufen.de zusätzlich als eine einzige
    Zeile "5. BraunenBerg-Lauf, 35 km" ohne Streckenangabe. Die 35 km sind
    keine vierte Strecke, sondern die ungenaue Obergrenze aus der
    Ergebnisliste. `merge_events()` kann das nicht erkennen, weil es
    Distanzen vergleicht und 35 zu keiner der drei passt - genau die
    Toleranz, die echte Distanz-Varianten absichtlich getrennt hält.

    Die Regel greift bewusst eng:

    * Nur innerhalb derselben Veranstaltung (`is_same_race()`: gleiches
      Datum, ähnlicher Name, derselbe Ort).
    * Nur, wenn dort MEHRERE Einträge mit Streckennamen (`wettbewerb`)
      stehen - ein einzelner wäre kein Beweis für eine vollständige
      Aufzählung.
    * Nur Einträge OHNE `wettbewerb`, deren Distanz LÄNGER ist als die
      längste aufgezählte Strecke - sie behaupten ein Rennen, das es laut
      der anderen Quelle nicht gibt.
    * Nur, wenn der NAME die Distanz nicht selbst ankündigt (ein
      "3-Länder-Marathon" hat einen Marathon, egal was eine
      unvollständige Aufzählung sagt).

    WARUM NUR MELDEN, NICHT LÖSCHEN: Diese Funktion hat als automatische
    Löschregel begonnen. Von ihren sieben Treffern waren nach
    Einzelrecherche ZWEI echte Rennen - der Halbmarathon des NRZ
    Klosterlaufs und die 42-km-Strecke der Mud Masters Airport Weeze; in
    beiden Fällen war die Aufzählung der anderen Quelle unvollständig.
    Eine Regel, die jedes siebte Mal echte Daten wegwirft, ist für diesen
    Datensatz nicht gut genug - und "zu viel gelöscht" ist schlimmer als
    "eine Zahl zu großzügig", weil es unsichtbar ist.

    Die Meldung ist trotzdem wertvoll: sie zeigt genau die Handvoll
    Einträge, die eine Websuche wert sind. Bestätigte Fehler kommen dann
    mit `"exclude": true` in `scripts/manual_overrides.json` - mit dem
    dreiteiligen Schlüssel "<Name>|<Datum>|<km>", damit nur die eine
    falsche Strecke entfernt wird und nicht die ganze Veranstaltung.
    """
    clusters: list[list[dict]] = []
    for event in events:
        for cluster in clusters:
            if any(is_same_race(member, event) for member in cluster):
                cluster.append(event)
                break
        else:
            clusters.append([event])

    report: list[str] = []
    for cluster in clusters:
        listed = [e for e in cluster if e.get("wettbewerb")]
        unlisted = [e for e in cluster if not e.get("wettbewerb")]
        if len(listed) < 2 or not unlisted:
            continue
        known = [e["laenge_km"] for e in listed if isinstance(e.get("laenge_km"), (int, float))]
        if not known:
            continue
        longest = max(known)
        for event in unlisted:
            km = event.get("laenge_km")
            if not isinstance(km, (int, float)):
                continue
            if km <= longest + max(0.5, longest * 0.05):
                continue  # passt zur Aufzählung oder ist plausibel kürzer
            if name_announces_distance(event.get("name"), km):
                continue  # der Name nennt diese Distanz selbst
            report.append(
                f"{event.get('name')} ({event.get('datum_start')}, {km:g} km): "
                f"länger als die längste aufgezählte Strecke "
                f"({', '.join(f'{k:g}' for k in sorted(known))} km) - bitte prüfen"
            )

    return report


# Ab dieser Distanz ist ein Laufevent an EINEM Tag unplausibel. Der
# längste Einzeltag-Lauf der Welt liegt bei rund 300 km; alles darüber ist
# ein Etappenrennen (dann läuft datum_ende später) oder ein Parse-Fehler.
IMPLAUSIBLE_RUN_KM = 300.0


def report_implausible_distances(events: list[dict]) -> list[str]:
    """MELDET (löscht nicht) Laufdistanzen, die an einem Tag nicht laufbar
    sind.

    Zwei echte Fehlerquellen, die so sichtbar werden:

    * Ein Regex-Fehler - der "Transeuropalauf" über 2067 km stand mit
      67 km in events.json, weil der Vorkommateil des Distanz-Regex auf
      drei Stellen begrenzt war. Inzwischen gefixt.
    * Eine Einheiten-Eigenheit von laufen.de: Dort stehen in der
      Wettbewerbsliste METER, sind aber als "km" ausgezeichnet, mit Punkt
      als Tausendertrennzeichen ("400 km", "600 km", "1.200 km" für
      400 m, 600 m und 1200 m). Bei den Werten MIT Trennzeichen liest
      unser Parser zufällig das Richtige, bei denen ohne wird aus 400 m
      eine 400-km-Strecke.

    Etappenrennen sind ausgenommen: wenn `datum_ende` nach `datum_start`
    liegt, ist eine Gesamtdistanz über 300 km normal (Transeuropalauf:
    2067 km über 37 Tage).

    Bewusst nur melden - welcher der beiden Fälle vorliegt, entscheidet
    ein Blick in die Quelle, und automatisch zu korrigieren hieße raten.
    Bestätigte Fälle kommen nach `manual_overrides.json`.
    """
    report: list[str] = []
    for event in events:
        km = event.get("laenge_km")
        if event.get("art1") != "Laufen" or not isinstance(km, (int, float)):
            continue
        if km <= IMPLAUSIBLE_RUN_KM:
            continue
        if event.get("datum_ende") and event["datum_ende"] > (event.get("datum_start") or ""):
            continue  # Etappenrennen über mehrere Tage
        report.append(
            f"{event.get('name')} ({event.get('datum_start')}): {km:g} km an einem Tag "
            f"- Meter als km? Label {event.get('wettbewerb')!r} - bitte prüfen"
        )
    return report


def merge_duplicates(events: list[dict]) -> tuple[list[dict], list[str]]:
    by_date: dict[str | None, list[dict]] = {}
    for event in events:
        by_date.setdefault(event.get("datum_start"), []).append(event)

    result: list[dict] = []
    report: list[str] = []
    for _date, group in by_date.items():
        clusters: list[list[dict]] = []
        for event in group:
            for cluster in clusters:
                if any(is_same_event(member, event) for member in cluster):
                    cluster.append(event)
                    break
            else:
                clusters.append([event])

        for cluster in clusters:
            if len(cluster) == 1:
                result.append(cluster[0])
                continue
            # Primär = vollständigster Eintrag; bei Gleichstand der mit
            # bekannter Distanz, dann der mit dem längeren (aussagekräftigeren) Namen.
            primary = max(
                cluster,
                key=lambda e: (
                    completeness(e),
                    e.get("laenge_km") is not None,
                    len(e.get("name") or ""),
                ),
            )
            for other in cluster:
                if other is primary:
                    continue
                for field in ENRICHABLE_FIELDS:
                    if primary.get(field) is None and other.get(field) is not None:
                        primary[field] = other[field]
                # Direkter Veranstalter-Link schlägt Kalender-Portal-Link.
                if is_portal_link(primary.get("veranstalter_url")) and other.get("veranstalter_url") \
                        and not is_portal_link(other["veranstalter_url"]):
                    primary["veranstalter_url"] = other["veranstalter_url"]
            names = " ||| ".join(e.get("name") or "" for e in cluster)
            report.append(f"{_date}: {names}  ->  behalten: {primary.get('name')}")
            result.append(primary)
    return result, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument("--events-json", type=Path, default=EVENTS_JSON_PATH)
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur Bericht ausgeben, events.json NICHT verändern.")
    parser.add_argument("--quiet", action="store_true",
                        help="Nur die Zusammenfassung, keine Einzelmeldungen.")
    parser.add_argument("--today", metavar="YYYY-MM-DD",
                        help="Stichtag für das Entfernen vergangener Events "
                             "(Standard: heute). Nur für Tests/Nachrechnen.")
    parser.add_argument("--no-geocoding", action="store_true",
                        help="Kein Reverse-Geocoding für fehlende/falsche Länder "
                             "(dann wird `land` nur aus dem Ortsnamen abgeleitet).")
    args = parser.parse_args()

    events = json.loads(args.events_json.read_text(encoding="utf-8"))
    before = len(events)

    geocoder = None if args.no_geocoding else Geocoder(GEOCODE_CACHE_PATH)

    events, excluded, override_changes = apply_overrides(events)
    # NACH apply_overrides: Ein Override mit dem Schlüssel "<Name>|<Datum>"
    # trifft JEDE Strecke dieser Veranstaltung an diesem Tag - auch eine
    # gerade nachgetragene. Beim ASV Duisburg hat genau das die neue
    # 5-km-Zeile auf 10 km gesetzt und damit zum Duplikat gemacht.
    # Nachgetragene Zeilen sind ohnehin schon einzeln geprüft und
    # brauchen keinen Override.
    events, manuell_ergaenzt = add_manual_events(events)
    # VOR refresh_art2: Das holt die Kategorie aus der Lauf-Liste und
    # würde einem noch als "Laufen" geführten Triathlon "Trail"
    # verpassen.
    events, nicht_ausdauer = drop_nicht_ausdauer(events)
    events, staffeln = drop_staffeln(events)
    events, nicht_offen = drop_nicht_offen_schwimmen(events)
    multisport_fixes = fix_multisport_art1(events)
    # Nach fix_multisport_art1: Ein Triathlon ist zuerst ein Triathlon;
    # erst danach ist ein "Rad 50 km" bei einer LAUFveranstaltung ein
    # eigenständiges Radrennen.
    fremde_sportart = fix_fremde_sportart_im_wettbewerb(events)
    art2_andere = fill_art2_andere_sportarten(events)
    art2_merges = merge_art2(events)
    # VOR refresh_art2: fix_charity leert die alte Kategorie "Charity",
    # refresh_art2 holt die echte danach aus der Stichwortliste.
    charity_changes = fix_charity(events)
    art2_changes = refresh_art2(events)
    distance_fixes = fix_halbmarathon_distance(events)
    meter_fixes = fix_meter_labels(events)
    rounding_fixes = round_distances(events)
    label_fixes = drop_contradicting_wettbewerb(events)
    land_fixes = fix_land(events, geocoder)
    # Danach: Was außerhalb der abgedeckten Regionen liegt ("Italien" ohne
    # Südtirol), fliegt - siehe drop_ausserhalb().
    events, ausserhalb = drop_ausserhalb(events)
    if ausserhalb:
        print(f"\nAußerhalb der abgedeckten Regionen entfernt ({len(ausserhalb)}):")
        for zeile in ausserhalb:
            print(f"  - {zeile}")
    backyard_cleared, backyard_check = clear_backyard_lap_km(events)
    duration_fills = fill_duration(events)
    events, too_short = drop_too_short(events)
    events, past = drop_past_events(events, args.today)
    suspicious = report_suspicious_distances(events)
    implausible = report_implausible_distances(events)
    moegliche_dups = report_moegliche_duplikate(events)
    tri_teilstrecken = report_multisport_teilstrecken(events)
    tri_distanzen = report_triathlon_distanzen(events)
    tri_laufkategorie = report_triathlon_mit_laufkategorie(events)
    koord_wider = report_widerspruechliche_koordinaten(events)
    gleiche_seite = report_gleiche_seite_gleiche_distanz(events)
    mehrfach_km = report_mehrere_distanzen_im_label(events)
    # Zusammenführen und Namen-Vereinheitlichen bedingen sich GEGENSEITIG:
    # Nach dem Zusammenführen ändern sich die Mehrheiten innerhalb einer
    # Veranstaltung, und umgekehrt lässt ein vereinheitlichter Name zwei
    # Einträge erst als Duplikat erkennbar werden (der Namensvergleich ist
    # Teil von is_same_event). Ein einzelner Durchlauf ist deshalb NICHT
    # idempotent - ein zweiter Aufruf des Skripts fand sonst erneut
    # Änderungen. Also bis zum Fixpunkt iterieren, mit Obergrenze gegen
    # ein Hin- und Herpendeln.
    series_fixes = fix_series_dates(events)
    tidy_fixes = tidy_all_names(events)

    dup_report: list[str] = []
    name_fixes: list[str] = []
    for _ in range(MAX_MERGE_PASSES):
        events, pass_dups = merge_duplicates(events)
        pass_names = unify_event_names(events)
        dup_report += pass_dups
        name_fixes += pass_names
        if not pass_dups and not pass_names:
            break
    else:
        print(f"\n⚠ Zusammenführen/Vereinheitlichen war nach "
              f"{MAX_MERGE_PASSES} Durchläufen noch nicht stabil.")

    events.sort(key=lambda e: (e.get("datum_start") or "", (e.get("name") or "").casefold()))

    def section(title: str, lines: list[str]) -> None:
        print(f"\n{title}: {len(lines)}")
        if lines and not args.quiet:
            for line in lines:
                print(f"  - {line}")

    section("Manuelle Korrekturen angewendet", override_changes)
    section("Einzeln recherchiert nachgetragen (manual_events.json)", manuell_ergaenzt)
    section("Per Override ausgeschlossen", excluded)
    section("Kein Ausdauer-Format, entfernt (NICHT_AUSDAUER)", nicht_ausdauer)
    section("Staffeln entfernt (erst einmal keine Staffeln)", staffeln)
    section("Schwimm-Meisterschaften entfernt (nicht für jeden offen)", nicht_offen)
    section("Sportart korrigiert (Mehrsport statt Laufen)", multisport_fixes)
    section("Sportart korrigiert (Label nennt eine andere Sportart)",
            fremde_sportart)
    section("Kategorie bei Nicht-Lauf-Sportarten nachgetragen", art2_andere)
    section("Alte Kategorie-Werte zusammengefasst (Trail, Backyard Ultra)", art2_merges)
    section("Charity-Merkmal gesetzt", charity_changes)
    section("Kategorie (art2) korrigiert", art2_changes)
    section("Distanz korrigiert (Halbmarathon-Bugfix)", distance_fixes)
    section("Distanz aus dem Meter-Label (Kinderläufe, Meterangaben)", meter_fixes)
    section("Distanz auf eine Dezimalstelle gerundet", rounding_fixes)
    section("Widersprüchliches Wettbewerbs-Label entfernt", label_fixes)
    section("Land ergänzt/korrigiert", land_fixes)
    section("Backyard: Rundenlänge aus der Distanz entfernt", backyard_cleared)
    section("⚠ Backyard mit großer Distanzangabe (nur Hinweis)", backyard_check)
    section("Dauer nachgetragen (Zeitrennen)", duration_fills)
    section("Unter der Mindestdistanz entfernt (Laufen "
            f"{MIN_DISTANCE_KM:g} km, Schwimmen {MIN_DISTANCE_BY_ART1['Schwimmen']:g} km)",
            too_short)
    section("Vergangene Events entfernt", past)
    section("⚠ Verdächtige Distanz (nur Hinweis, nichts gelöscht)", suspicious)
    section("⚠ Gleicher Tag, Ort und Distanz unter anderem Namen (nur Hinweis)",
            moegliche_dups)
    section("⚠ Mehrsport: Zeile sieht nach einer Teilstrecke aus (nur Hinweis)",
            tri_teilstrecken)
    section("⚠ Triathlon-Distanz passt zu keinem Format (nur Hinweis)", tri_distanzen)
    section("⚠ Triathlon mit Laufkategorie – wahrscheinlich ein Lauf (nur Hinweis)", tri_laufkategorie)
    section("⚠ Unplausible Laufdistanz an einem Tag (nur Hinweis)", implausible)
    section("⚠ Dieselbe Veranstaltung an zwei weit entfernten Punkten (nur Hinweis)",
            koord_wider)
    section("⚠ Gleiche Veranstalter-Seite, gleiche Distanz, anderer Name (nur Hinweis)",
            gleiche_seite)
    section("⚠ Zwei Streckenlängen in einem Wettbewerbs-Label (nur Hinweis)",
            mehrfach_km)
    section("Duplikat-Gruppen zusammengeführt", dup_report)
    section("Laufserie: Datum aus dem Termin-Label übernommen", series_fixes)
    section("Namens-Formatierung bereinigt", tidy_fixes)
    section("Namen innerhalb einer Veranstaltung vereinheitlicht", name_fixes)

    print(f"\nevents.json: {before} -> {len(events)} Events "
          f"({len(events) - before:+d}).")

    if args.dry_run:
        print("--dry-run aktiv: events.json wurde NICHT verändert.")
        return

    args.events_json.write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✅ {args.events_json} aufgeräumt.")


if __name__ == "__main__":
    main()
