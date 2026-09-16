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

Acht Schritte, in dieser Reihenfolge:

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
    guess_art2,
    guess_land,
    is_portal_link,
    is_same_event,
    is_same_race,
    find_override,
    load_manual_overrides,
    round_km,
)

# Für die Neubestimmung von art2 wird die Standard-Stichwortliste für
# Laufen genutzt (siehe ART2_KEYWORDS_LAUFEN in scraper_lib.py).
ART2_CONFIG = SiteConfig(base_url="", calendar_url="")


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
            for field in ("laenge_km", "art2", "art1", "land", "standort", "veranstalter_url"):
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


def refresh_art2(events: list[dict]) -> list[str]:
    """Bestimmt art2 aus dem Event-Namen neu, wenn dabei eine spezifischere
    Kategorie als die gespeicherte herauskommt (Trail/Berg/Cross/Hindernis/
    Bahn statt des generischen "Straße")."""
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
    parser.add_argument("--no-geocoding", action="store_true",
                        help="Kein Reverse-Geocoding für fehlende/falsche Länder "
                             "(dann wird `land` nur aus dem Ortsnamen abgeleitet).")
    args = parser.parse_args()

    events = json.loads(args.events_json.read_text(encoding="utf-8"))
    before = len(events)

    geocoder = None if args.no_geocoding else Geocoder(GEOCODE_CACHE_PATH)

    events, excluded, override_changes = apply_overrides(events)
    art2_changes = refresh_art2(events)
    distance_fixes = fix_halbmarathon_distance(events)
    rounding_fixes = round_distances(events)
    label_fixes = drop_contradicting_wettbewerb(events)
    land_fixes = fix_land(events, geocoder)
    events, too_short = drop_too_short(events)
    suspicious = report_suspicious_distances(events)
    events, dup_report = merge_duplicates(events)

    events.sort(key=lambda e: (e.get("datum_start") or "", (e.get("name") or "").casefold()))

    def section(title: str, lines: list[str]) -> None:
        print(f"\n{title}: {len(lines)}")
        if lines and not args.quiet:
            for line in lines:
                print(f"  - {line}")

    section("Manuelle Korrekturen angewendet", override_changes)
    section("Per Override ausgeschlossen", excluded)
    section("Kategorie (art2) korrigiert", art2_changes)
    section("Distanz korrigiert (Halbmarathon-Bugfix)", distance_fixes)
    section("Distanz auf eine Dezimalstelle gerundet", rounding_fixes)
    section("Widersprüchliches Wettbewerbs-Label entfernt", label_fixes)
    section("Land ergänzt/korrigiert", land_fixes)
    section(f"Unter {MIN_DISTANCE_KM:g} km entfernt ({MIN_DISTANCE_ART1})", too_short)
    section("⚠ Verdächtige Distanz (nur Hinweis, nichts gelöscht)", suspicious)
    section("Duplikat-Gruppen zusammengeführt", dup_report)

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
