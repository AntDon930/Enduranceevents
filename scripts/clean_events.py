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
    MIN_DISTANCE_ART1,
    MIN_DISTANCE_KM,
    Geocoder,
    SiteConfig,
    guess_art1,
    guess_art2,
    guess_land,
    is_portal_link,
    is_same_event,
    is_same_race,
    find_override,
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
            for field in ("laenge_km", "dauer_h", "wettbewerb", "art2", "art1",
                          "land", "standort", "veranstalter_url"):
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


# Alte Kategorien, die heute eine einzige sind. "Trail" und "Cross"
# beschreiben beide einen Geländelauf; die Quellen benennen dieselbe
# Strecke mal so, mal so, und wer sie trennen will, rät. Auf Wunsch des
# Nutzers zusammengefasst zu "Trail/Cross".
ART2_MERGED_LAUFEN = {"Trail": "Trail/Cross", "Cross": "Trail/Cross"}


def merge_trail_cross(events: list[dict]) -> list[str]:
    """Zieht bereits gespeicherte "Trail"- und "Cross"-Einträge auf die
    gemeinsame Kategorie "Trail/Cross" nach.

    Die Stichwortliste (`ART2_KEYWORDS_LAUFEN`) liefert den neuen Wert
    schon bei jedem Scraper-Lauf; dieser Schritt holt den Bestand nach.
    Idempotent: Ein zweiter Durchlauf findet nichts mehr, weil
    "Trail/Cross" in der Zuordnung nicht mehr vorkommt.

    Nur für `art1 == "Laufen"` - beim Fahrrad ist "Cyclecross" eine eigene
    Kategorie und bleibt unangetastet.
    """
    changed: list[str] = []
    for event in events:
        if event.get("art1") != "Laufen":
            continue
        neu = ART2_MERGED_LAUFEN.get(event.get("art2"))
        if neu:
            changed.append(f"{event.get('name')}: art2 {event['art2']!r} -> {neu!r}")
            event["art2"] = neu
    return changed


def refresh_art2(events: list[dict]) -> list[str]:
    """Bestimmt art2 aus dem Event-Namen neu, wenn dabei eine spezifischere
    Kategorie als die gespeicherte herauskommt (Trail/Cross, Berg,
    Hindernis, Bahn statt des generischen "Straße")."""
    overrides = load_manual_overrides()
    changed: list[str] = []
    for event in events:
        own = find_override(overrides, event.get("name"), event.get("datum_start"),
                            event.get("laenge_km"))
        if own and "art2" in own:
            continue  # manuell gesetzte Kategorie nicht überschreiben
        if event.get("art1") != "Laufen":
            continue  # Stichwortliste gilt nur für Laufen
        guessed = guess_art2(event.get("name") or "", ART2_CONFIG)
        current = event.get("art2")
        if guessed and guessed != current and current in (None, "Straße"):
            changed.append(f"{event.get('name')}: art2 {current!r} -> {guessed!r}")
            event["art2"] = guessed
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
    mitgezogen - ein Triathlon mit der Laufkategorie "Trail/Cross" wäre
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
        if event.get("art2") != "Backcountry Ultra":
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
    """Entfernt zu kurze LAUF-Events. Andere Sportarten sind bewusst
    ausgenommen: 3,5 km Freiwasserschwimmen sind eine ernsthafte Distanz,
    ein 3,5-km-Lauf nicht (siehe MIN_DISTANCE_ART1 in scraper_lib.py)."""
    kept, dropped = [], []
    for event in events:
        km = event.get("laenge_km")
        too_short = (
            isinstance(km, (int, float))
            and km < MIN_DISTANCE_KM
            and event.get("art1") == MIN_DISTANCE_ART1
            # Ein Zeitrennen ist nie "zu kurz": beim 24-Stunden-Lauf auf
            # einer 1-km-Runde ist die Rundenlänge keine Wettkampfdistanz.
            and event.get("dauer_h") is None
        )
        if too_short:
            dropped.append(f"{event.get('name')} ({km} km)")
        else:
            kept.append(event)
    return kept, dropped


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
    # VOR refresh_art2: Das holt die Kategorie aus der Lauf-Liste und
    # würde einem noch als "Laufen" geführten Triathlon "Trail/Cross"
    # verpassen.
    multisport_fixes = fix_multisport_art1(events)
    art2_merges = merge_trail_cross(events)
    art2_changes = refresh_art2(events)
    distance_fixes = fix_halbmarathon_distance(events)
    rounding_fixes = round_distances(events)
    label_fixes = drop_contradicting_wettbewerb(events)
    land_fixes = fix_land(events, geocoder)
    backyard_cleared, backyard_check = clear_backyard_lap_km(events)
    duration_fills = fill_duration(events)
    events, too_short = drop_too_short(events)
    events, past = drop_past_events(events, args.today)
    suspicious = report_suspicious_distances(events)
    implausible = report_implausible_distances(events)
    tri_teilstrecken = report_multisport_teilstrecken(events)
    tri_distanzen = report_triathlon_distanzen(events)
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
    section("Per Override ausgeschlossen", excluded)
    section("Sportart korrigiert (Mehrsport statt Laufen)", multisport_fixes)
    section("Kategorie Trail/Cross zusammengefasst", art2_merges)
    section("Kategorie (art2) korrigiert", art2_changes)
    section("Distanz korrigiert (Halbmarathon-Bugfix)", distance_fixes)
    section("Distanz auf eine Dezimalstelle gerundet", rounding_fixes)
    section("Widersprüchliches Wettbewerbs-Label entfernt", label_fixes)
    section("Land ergänzt/korrigiert", land_fixes)
    section("Backyard: Rundenlänge aus der Distanz entfernt", backyard_cleared)
    section("⚠ Backyard mit großer Distanzangabe (nur Hinweis)", backyard_check)
    section("Dauer nachgetragen (Zeitrennen)", duration_fills)
    section(f"Unter {MIN_DISTANCE_KM:g} km entfernt ({MIN_DISTANCE_ART1})", too_short)
    section("Vergangene Events entfernt", past)
    section("⚠ Verdächtige Distanz (nur Hinweis, nichts gelöscht)", suspicious)
    section("⚠ Mehrsport: Zeile sieht nach einer Teilstrecke aus (nur Hinweis)",
            tri_teilstrecken)
    section("⚠ Triathlon-Distanz passt zu keinem Format (nur Hinweis)", tri_distanzen)
    section("⚠ Unplausible Laufdistanz an einem Tag (nur Hinweis)", implausible)
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
