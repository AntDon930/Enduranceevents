#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_scraper_lib.py
======================

Regressionstests für die Textauswertung der Scraper - ohne Netzwerk, ohne
zusätzliche Test-Bibliothek. Aufruf:

    python3 scripts/test_scraper_lib.py

Warum es diese Datei gibt: Die Fehler in diesem Projekt saßen bisher fast
alle in derselben Ecke - im Erkennen von Distanz, Kategorie und Land aus
Freitext. Mehrere davon sind erst aufgefallen, als jemand einzelne Events
in der fertigen Liste stichprobenartig nachgeschlagen hat. Jeder dieser
echten Fehler steht unten als Testfall mit Kommentar, damit er nicht ein
zweites Mal hereinkommt.

Der Exit-Code ist 0 bei Erfolg und 1 bei mindestens einem Fehlschlag,
lässt sich also direkt in CI einhängen.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    clean_competition_label,
    expand_competitions,
    guess_art2,
    guess_distance_km,
    guess_land,
    is_same_event,
    parse_competitions,
    round_km,
)

CONFIG = SiteConfig(base_url="", calendar_url="")

_failures: list[str] = []


def check(label: str, got, want) -> None:
    if got != want:
        _failures.append(f"{label}: erwartet {want!r}, bekommen {got!r}")
        print(f"  ✗ {label}: erwartet {want!r}, bekommen {got!r}")
    else:
        print(f"  ✓ {label}")


def test_distanz() -> None:
    print("\nDistanz-Erkennung (guess_distance_km):")
    # Echter Bug: Der Nachkommateil war auf zwei Stellen begrenzt, dadurch
    # matchte der Regex bei "42,195" nur "195" als eigenständige km-Angabe.
    check("42,195 km -> 42.2", guess_distance_km("42,195 km", CONFIG), 42.2)
    check("21,0975 km -> 21.1", guess_distance_km("über 21,0975 km", CONFIG), 21.1)
    # Echter Bug: "Strecken: 1 bis 42,195 Kilometer" ergab 195 km.
    check("Spanne mit Kilometer",
          guess_distance_km("Strecken: 0,4 bis 21,1 Kilometer", CONFIG), 21.1)
    # Echter Bug: Das Stichwort "marathon" wurde vor "halbmarathon" geprüft,
    # ein "35. Halbmarathon Altötting" bekam dadurch 42,2 statt 21,1 km.
    check("Halbmarathon-Stichwort",
          guess_distance_km("35. Halbmarathon Altötting", CONFIG), 21.1)
    check("Marathon-Stichwort",
          guess_distance_km("20. Kassel Marathon", CONFIG), 42.2)
    check("ohne Angabe", guess_distance_km("Volkslauf", CONFIG), None)


def test_rundung() -> None:
    print("\nRundung (round_km) - immer eine Dezimalstelle:")
    for value, want in [(42.195, 42.2), (21.0975, 21.1), (6.66, 6.7),
                        (9.999, 10.0), (10, 10.0), (None, None), (True, None)]:
        check(f"{value!r}", round_km(value), want)


def test_kategorie() -> None:
    print("\nKategorie-Erkennung (guess_art2) - spezifisch vor generisch:")
    # Echter, vom Nutzer gemeldeter Bug: Das Wort "Marathon" im Namen führte
    # zu "Straße", obwohl "Bergtrail"/"Trail-Marathon" einen Trail beschreibt.
    check("Bergtrail Trail-Marathon",
          guess_art2("5. Beck HochRhön Bergtrail 42k Trail-Marathon", CONFIG), "Trail")
    check("Höhenmeter -> Berg",
          guess_art2("Panoramalauf (989 Höhenmeter)", CONFIG), "Berg")
    check("Crosslauf", guess_art2("29. Mausebergecrosslauf", CONFIG), "Cross")
    check("Stadtlauf -> Straße", guess_art2("40. Wolfenbütteler Stadtlauf", CONFIG), "Straße")
    check("Hindernislauf", guess_art2("Spartan Race Hindernislauf", CONFIG), "Hindernis")


def test_land() -> None:
    print("\nLand-Erkennung (guess_land):")
    # Echter, vom Nutzer gemeldeter Fall: Die Detailseite nennt
    # "9607 Mosnang (Schweiz)", in events.json fehlte das Land trotzdem.
    check("(Schweiz)", guess_land("9607 Mosnang (Schweiz)"), "Schweiz")
    # Dieselbe Seite nutzt teils dreibuchstabige Kürzel.
    check("(AUT)", guess_land("6020 Innsbruck (AUT)"), "Österreich")
    check("(GER)", guess_land("10115 Berlin (GER)"), "Deutschland")
    check("fünfstellige PLZ", guess_land("83242 Reit im Winkl"), "Deutschland")
    # Vierstellige PLZ trennt AT und CH nicht -> bewusst kein Rateversuch.
    check("vierstellige PLZ bleibt offen", guess_land("6130 Schwaz"), None)
    # Echter Bug: land="Schweiz" für Ebermannstadt (Bayern), weil das Land
    # aus dem EVENT-NAMEN geraten wurde.
    check("Fränkische Schweiz ist Deutschland",
          guess_land("25. Fränkische-Schweiz-Marathon"), None)
    check("Sächsische Schweiz", guess_land("Sächsische Schweiz Trail"), None)
    # Zweibuchstabige Codes dürfen in Freitext NICHT anschlagen.
    check("'de' in Freitext", guess_land("Tour de France"), None)


def test_wettbewerbe() -> None:
    print("\nWettbewerbe (parse_competitions / expand_competitions):")
    check("hm-Klammer entfernt",
          clean_competition_label("Moslig 8000 (229 hm) | 8,5 km"), "Moslig 8000")
    check("races-Layout",
          clean_competition_label("TST 86K | 86 km | + 3500 hm"), "TST 86K")

    # Der vom Nutzer genannte Fall: die Seite listet sieben Wettbewerbe,
    # vorher landete nur der längste in events.json.
    mosnang = [
        "Kids Fun Race | 0,4 km",
        "Plausch-Stafette | 2 km",
        "Moslig 8000 (229 hm) | 8,5 km",
        "Halbmarathon (989 hm) | 21,1 km",
    ]
    comps = parse_competitions(mosnang, CONFIG)
    check("alle vier Strecken", [c.laenge_km for c in comps], [0.4, 2.0, 8.5, 21.1])
    check("Labels", [c.label for c in comps],
          ["Kids Fun Race", "Plausch-Stafette", "Moslig 8000", "Halbmarathon"])

    # Gleiche Distanz mehrfach (Einzel/Staffel/Walking) = ein Eintrag.
    check("Duplikat-Distanz zusammengefasst",
          [c.laenge_km for c in parse_competitions(["10 km", "10 km Staffel"], CONFIG)],
          [10.0])

    base = Event(name="Schnebelhorn Panoramatrail", standort="Mosnang",
                 land="Schweiz", datum_start="2026-09-18")
    variants = expand_competitions(base, comps, CONFIG)
    check("ein Eintrag pro Strecke", len(variants), 4)
    check("Name bleibt unverändert",
          {v.name for v in variants}, {"Schnebelhorn Panoramatrail"})
    check("Wettbewerb gesetzt", variants[2].wettbewerb, "Moslig 8000")

    # art2 pro Strecke: der "hint" der Quelle ("Trailrun") schlägt durch.
    hinted = parse_competitions([("TST 42K | 42 km", "Trailrun")], CONFIG)
    check("art2 aus Streckenart",
          [v.art2 for v in expand_competitions(Event(name="Trophy"), hinted, CONFIG)],
          ["Trail"])

    # Ohne erkannte Wettbewerbe darf nichts verloren gehen.
    check("keine Wettbewerbe -> Basis-Event",
          len(expand_competitions(base, [], CONFIG)), 1)


def test_duplikate() -> None:
    print("\nDuplikat-Erkennung (is_same_event):")
    a = {"name": "52. Int. Bodensee-Marathon", "datum_start": "2026-09-20",
         "standort": "Konstanz", "laenge_km": 42.195}
    b = {"name": "Bodensee Marathon", "datum_start": "2026-09-20",
         "standort": "Konstanz", "laenge_km": 42.2}
    check("gleicher Lauf, anderer Name", is_same_event(a, b), True)

    # Unterschiedliche Distanzen desselben Events bleiben getrennte Einträge
    # (ausdrücklicher Wunsch aus dem Chat).
    hm = dict(a, laenge_km=21.1)
    check("Marathon vs. Halbmarathon getrennt", is_same_event(a, hm), False)

    # Generische Namen am selben Tag in verschiedenen Städten.
    s1 = {"name": "Silvesterlauf", "datum_start": "2026-12-31",
          "standort": "Salzburg", "lat": 47.80, "lon": 13.04, "laenge_km": 10.0}
    s2 = {"name": "Silvesterlauf", "datum_start": "2026-12-31",
          "standort": "München", "lat": 48.14, "lon": 11.58, "laenge_km": 10.0}
    check("gleicher Name, andere Stadt", is_same_event(s1, s2), False)


def main() -> int:
    for test in (test_distanz, test_rundung, test_kategorie, test_land,
                 test_wettbewerbe, test_duplikate):
        test()

    print()
    if _failures:
        print(f"❌ {len(_failures)} Test(s) fehlgeschlagen:")
        for line in _failures:
            print(f"  - {line}")
        return 1
    print("✅ Alle Tests bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
