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
    art2_from_elevation,
    clean_competition_label,
    expand_competitions,
    guess_art2,
    guess_distance_km,
    guess_land,
    is_portal_link,
    is_same_event,
    parse_competitions,
    parse_duration_h,
    parse_elevation_m,
    round_km,
    update_existing_event,
)

from build_places import (  # noqa: E402
    _hat_ortsbezug,
    _ist_firma,
    _verschmelze_nachbarn,
    normalisiere,
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
    # Echter Bug, derselbe Fehlertyp wie oben, nur vor dem Komma: Der
    # Vorkommateil war auf drei Stellen begrenzt, dadurch matchte aus
    # "2067 km" nur "067" - der Transeuropalauf (2067 km) stand mit 67 km
    # in events.json. "1000 km" ergab sogar 0.
    check("2067 km", guess_distance_km("2067 km", CONFIG), 2067.0)
    check("1000 km", guess_distance_km("1000 km", CONFIG), 1000.0)
    check("kein Start mitten in der Zahl",
          guess_distance_km("Etappe 12345 km", CONFIG), 12345.0)


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
    # running.life schreibt die Strecken als Satz; alles ab dem Doppelpunkt
    # ist Beschreibung und gehört nicht ins Label.
    check("Satz mit Doppelpunkt",
          clean_competition_label(
              "VR Bank – BraunenBerg-Lauf: 14,6 km , ca. 400 Hm, Strecke endet in Oberalfingen."),
          "VR Bank – BraunenBerg-Lauf")
    check("Label ohne Doppelpunkt bleibt", clean_competition_label("Halbmarathon"), "Halbmarathon")

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


def test_hoehenprofil() -> None:
    print("\nHöhenprofil (art2_from_elevation):")
    check("Hm lesen", parse_elevation_m("ca. 1100 Hm, Start im Bergwerk"), 1100.0)
    check("Hm mit Tausenderpunkt", parse_elevation_m("+ 3.500 hm"), 3500.0)
    check("Höhenmeter ausgeschrieben", parse_elevation_m("229 Höhenmeter"), 229.0)
    check("keine Angabe", parse_elevation_m("8,2 km"), None)

    # Der vom Nutzer beanstandete Fall: 400 Hm auf 14,6 km ist kein
    # Straßenlauf (27 m/km).
    check("400 hm / 14,6 km -> Berg",
          art2_from_elevation("VR Bank – BraunenBerg-Lauf: 14,6 km, ca. 400 Hm", 14.6, "Straße"),
          "Berg")
    check("248 hm / 8,2 km -> Berg",
          art2_from_elevation("BergBau-Lauf: 8,2 km, ca. 248 Hm", 8.2, "Straße"), "Berg")
    # Flacher Stadtmarathon mit ein paar Brücken bleibt Straße (2,4 m/km).
    check("100 hm / 42,2 km bleibt Straße",
          art2_from_elevation("Stadtmarathon, 100 hm", 42.2, "Straße"), "Straße")
    # Eine spezifischere Kategorie aus dem Namen wird nie überschrieben.
    check("Trail bleibt Trail",
          art2_from_elevation("BraunenBerg-Trail: 32 km, ca. 1100 Hm", 32.0, "Trail"), "Trail")
    check("ohne Distanz keine Aussage",
          art2_from_elevation("ca. 400 Hm", None, "Straße"), "Straße")


def test_offizieller_link() -> None:
    print("\nPortal- vs. offizieller Link (update_existing_event):")
    check("running.life ist Portal", is_portal_link("https://running.life/de/termine/x"), True)
    check("laufen.de ist Portal", is_portal_link("https://laufen.de/laufkalender/details/1"), True)
    check("Veranstalter ist kein Portal", is_portal_link("https://www.braunenberg-lauf.de/"), False)

    # Kernfall: Ein gespeicherter Portallink wird durch die offizielle Seite
    # ersetzt - ohne das behalten Altbestände den Portallink für immer.
    target = {"name": "BraunenBerg-Lauf",
              "veranstalter_url": "https://running.life/de/termine/braunenberg-lauf"}
    update_existing_event(target, {"veranstalter_url": "https://www.braunenberg-lauf.de/",
                                   "land": "Deutschland"})
    check("Portallink ersetzt", target["veranstalter_url"], "https://www.braunenberg-lauf.de/")
    check("fehlendes Feld ergänzt", target["land"], "Deutschland")

    # Umgekehrt NICHT: ein bereits direkter Link wird nie durch ein Portal
    # überschrieben.
    target2 = {"veranstalter_url": "https://www.braunenberg-lauf.de/"}
    update_existing_event(target2, {"veranstalter_url": "https://running.life/de/termine/x"})
    check("direkter Link bleibt", target2["veranstalter_url"], "https://www.braunenberg-lauf.de/")


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

    # Vom Nutzer gemeldet: Marathon und Halbmarathon München standen je
    # DOPPELT in der Liste. Ursache war die Wortstellung - als Zeichenfolge
    # nur 0,69 Ähnlichkeit, als Wortmenge identisch.
    D, S = "2026-10-11", "München"
    m1 = {"name": "40. München Marathon by Brooks", "datum_start": D, "standort": S,
          "laenge_km": 42.2, "veranstalter_url": "https://marathonmuenchen.org"}
    m2 = {"name": "MARATHON MÜNCHEN", "wettbewerb": "Marathon", "datum_start": D,
          "standort": S, "laenge_km": 42.2, "veranstalter_url": "https://marathonmuenchen.org/"}
    check("Wortstellung vertauscht", is_same_event(m1, m2), True)

    # Hier trägt der Wettbewerbs-Name das unterscheidende Wort, und die
    # kürzere Wortmenge steckt komplett in der längeren.
    h1 = {"name": "Marathon München by Brooks", "wettbewerb": "Halbmarathon",
          "datum_start": D, "standort": S, "laenge_km": 21.1}
    h2 = {"name": "München Halbmarathon", "datum_start": D, "standort": S, "laenge_km": 21.1}
    check("Teilmenge mit Wettbewerbs-Name", is_same_event(h1, h2), True)
    check("Marathon bleibt vom Halbmarathon getrennt", is_same_event(m1, h1), False)

    # Ein einzelnes gemeinsames Wort darf NICHT reichen (Teilmengen-Regel
    # verlangt mindestens zwei Wörter).
    check("ein Wort ist zu generisch",
          is_same_event({"name": "Stadtlauf", "datum_start": D, "standort": S, "laenge_km": 10.0},
                        {"name": "Marathon", "datum_start": D, "standort": S, "laenge_km": 10.0}),
          False)

    # Ausprobiert und verworfen: gleiche Veranstalter-Domain als Kriterium.
    # Diese beiden sind verschiedene Veranstaltungen (Alfhausen und
    # Ibbenbüren, 20 km auseinander), verbunden nur durch das
    # Regionalportal laufen-os.de.
    a1 = {"name": "Alfhausener Volkslauf", "datum_start": "2026-09-19", "standort": "Alfhausen",
          "lat": 52.51, "lon": 7.95, "laenge_km": 10.0,
          "veranstalter_url": "https://www.laufen-os.de/wettkaempfe/13-alfhausener-volkslauf"}
    a2 = {"name": "MBH Benefizlauf", "datum_start": "2026-09-19", "standort": "Ibbenbüren",
          "lat": 52.28, "lon": 7.72, "laenge_km": 10.0,
          "veranstalter_url": "https://www.laufen-os.de/wettkaempfe/mbh-benefizlauf"}
    check("gleiche Domain, andere Veranstaltung", is_same_event(a1, a2), False)

    # Generische Namen am selben Tag in verschiedenen Städten.
    s1 = {"name": "Silvesterlauf", "datum_start": "2026-12-31",
          "standort": "Salzburg", "lat": 47.80, "lon": 13.04, "laenge_km": 10.0}
    s2 = {"name": "Silvesterlauf", "datum_start": "2026-12-31",
          "standort": "München", "lat": 48.14, "lon": 11.58, "laenge_km": 10.0}
    check("gleicher Name, andere Stadt", is_same_event(s1, s2), False)


def test_namensvereinheitlichung() -> None:
    """Die Namens-Vereinheitlichung lebt in clean_events.py, die Regeln
    lassen sich aber ohne Netzwerk und ohne events.json prüfen."""
    print("\nNamen vereinheitlichen (clean_events):")
    from clean_events import (  # lokaler Import, nur für diesen Test
        name_quality_hard, name_quality_soft, repair_umlaut_spelling, tidy_name,
    )

    check("doppeltes Leerzeichen", tidy_name("17.  Preungesheimer Dorflauf"),
          "17. Preungesheimer Dorflauf")
    check("fehlendes Leerzeichen nach Nummer", tidy_name("37.Bessunger Merck-Lauf"),
          "37. Bessunger Merck-Lauf")

    # GROSSSCHREIBUNG darf die Mehrheit nicht durchsetzen.
    check("GROSSGESCHRIEBEN verliert",
          name_quality_hard("MARATHON MÜNCHEN") < name_quality_hard("Marathon München by Brooks"),
          True)

    # Umlaute sind eine Reparatur, keine Auswahl: die Auflagen-Nummer der
    # Mehrheit bleibt, die Schreibweise wird korrigiert.
    check("Umschrift wird repariert",
          repair_umlaut_spelling("22. Baedleslauf", ["22. Baedleslauf", "Bädleslauf"]),
          "22. Bädleslauf")
    check("ß wird repariert",
          repair_umlaut_spelling("Int. Pronsfelder Volks- und Strassenlauf",
                                 ["Int. Pronsfelder Volks- und Strassenlauf",
                                  "39. Int. Pronsfelder Volks- und Straßenlauf"]),
          "Int. Pronsfelder Volks- und Straßenlauf")
    # Kein Umlaut-Transfer zwischen verschiedenen Namen - daran ist ein
    # früherer Versuch gescheitert ("Wiesent Challenge" verlor gegen einen
    # 108 Zeichen langen Namen, nur weil darin "Straßenlauf" vorkam).
    check("kein Transfer zwischen verschiedenen Namen",
          repair_umlaut_spelling("Wiesent Challenge",
                                 ["Wiesent Challenge", "5. Wiesent-Challenge 10 km Straßenlauf"]),
          "Wiesent Challenge")

    # Ein 108-Zeichen-"Name" ist eine Beschreibung und verliert.
    lang = "5. Wiesent-Challenge 10 km Straßenlauf und 12 km Panoramatrail mit Oberfränkischen Meisterschaften im Trail-Lauf"
    check("überlanger Name verliert",
          name_quality_soft(lang) < name_quality_soft("Wiesent Challenge"), True)


def test_zeitrennen() -> None:
    """Zeitlich begrenzte Rennen (24-Stunden-Lauf, 6h, 12h) haben keine
    Distanz - die Dauer steht in `dauer_h` und erscheint in derselben
    Spalte wie die Distanz. Die beiden Fehlerquellen der Erkennung stehen
    hier als Testfall, weil beide in echten Daten vorkommen: "229 hm"
    sind Höhenmeter, und ein "Zeitlimit: 6 Stunden" ist eine
    Zielschlusszeit - die macht aus einem Marathon kein 6-Stunden-Rennen."""
    print("\nZeitrennen (parse_duration_h) und Backcountry Ultra:")
    check("24-Stunden-Lauf", parse_duration_h("24-Stunden-Lauf Hamburg"), 24.0)
    check("6h mit Anhang", parse_duration_h("6h Lauf im Stadtpark"), 6.0)
    check("ausgeschrieben", parse_duration_h("12 Stunden von Aachen"), 12.0)
    check("englisch", parse_duration_h("24 hours of Zurich"), 24.0)
    check("Bindestrich-Form", parse_duration_h("6-Stunden-Lauf"), 6.0)

    # Höhenmeter sind keine Stunden.
    check("229 hm ist keine Dauer", parse_duration_h("Berglauf 8,5 km | 229 hm"), None)
    # Zielschlusszeiten dürfen nicht zur Renndauer werden.
    check("Zeitlimit zählt nicht",
          parse_duration_h("Marathon (Zeitlimit: 6 Stunden)"), None)
    check("Karenzzeit zählt nicht",
          parse_duration_h("Halbmarathon, Karenzzeit 3 h"), None)
    check("Startzeit zählt nicht", parse_duration_h("Start 10 Uhr, 10 km"), None)
    check("100 Stunden unplausibel", parse_duration_h("100-Stunden-Rennen"), None)

    # Ein Zeitrennen ist ein eigener Eintrag, obwohl es keine Distanz hat -
    # ohne diese Ausnahme fiel es in expand_competitions() heraus. Und zwei
    # Zeitrennen derselben Veranstaltung sind zwei Einträge, nicht eines
    # (der Dedupe-Schlüssel enthält deshalb die Dauer).
    comps = parse_competitions(
        ["24-Stunden-Lauf", "6h Lauf", "Halbmarathon | 21,1 km", "12 Stunden"], CONFIG)
    check("vier Wettbewerbe erkannt", len(comps), 4)
    check("Dauer am Wettbewerb", [c.dauer_h for c in comps], [24.0, 6.0, None, 12.0])
    base = Event(name="Zeitlauf Testheim", datum_start="2027-05-01", standort="Testheim")
    evs = expand_competitions(base, comps, CONFIG)
    check("vier Einträge", len(evs), 4)
    check("Zeitrennen ohne Distanz", [e.laenge_km for e in evs], [None, None, 21.1, None])
    check("Dauer am Eintrag", [e.dauer_h for e in evs], [24.0, 6.0, None, 12.0])

    # Neue Laufen-Kategorie. Sie steht VOR "Trail" in der Stichwortliste,
    # sonst würde ein "Backcountry Ultra Trail" zum gewöhnlichen Trail.
    check("Backcountry Ultra erkannt",
          guess_art2("Alpiner Backcountry Ultra", CONFIG), "Backcountry Ultra")
    check("Backcountry gewinnt gegen Trail",
          guess_art2("Backcountry Ultra Trail 80 km", CONFIG), "Backcountry Ultra")
    # Ein Backyard Ultra ist ein anderes Format (Rundenlauf nach Big's
    # Backyard) und wird NICHT automatisch als Backcountry Ultra eingestuft.
    check("Backyard bleibt unberührt",
          guess_art2("Backyard Ultra Berlin", CONFIG) != "Backcountry Ultra", True)


def test_vergangene_events() -> None:
    """Vergangene Events gehören nicht in die Liste - weder neu
    hereingeholt (scraper_lib.filter_past) noch in der bestehenden Datei
    (clean_events.drop_past_events). Beide Seiten müssen sich gleich
    verhalten, sonst holt der Scraper heraus, was das Aufräumen entfernt
    hat, oder umgekehrt."""
    from clean_events import drop_past_events  # lokaler Import, nur hier
    from scraper_lib import filter_past

    HEUTE = "2026-09-16"
    roh = [
        Event(name="vorbei", datum_start="2026-09-01", standort="X"),
        Event(name="heute", datum_start=HEUTE, standort="X"),
        # Etappenrennen, das gestern begonnen hat: läuft noch.
        Event(name="mehrtägig läuft", datum_start="2026-09-14",
              datum_ende="2026-09-18", standort="X"),
        Event(name="mehrtägig vorbei", datum_start="2026-09-01",
              datum_ende="2026-09-03", standort="X"),
        # Unlesbares Datum: nicht löschen, nur behalten (dieselbe Linie
        # wie bei den Distanzen - zu viel gelöscht ist unsichtbar).
        Event(name="kaputtes Datum", datum_start="irgendwann", standort="X"),
        Event(name="zukunft", datum_start="2027-01-01", standort="X"),
    ]
    kept, skipped = filter_past(roh, HEUTE)
    check("filter_past verwirft nur Vergangenes", skipped, 2)
    check("filter_past behält heute, laufend, kaputt, künftig",
          [e.name for e in kept],
          ["heute", "mehrtägig läuft", "kaputtes Datum", "zukunft"])

    # Dieselben Fälle als Dicts durch das Aufräumskript.
    dicts = [{"name": e.name, "datum_start": e.datum_start,
              "datum_ende": e.datum_ende} for e in roh]
    kept2, dropped2 = drop_past_events(dicts, HEUTE)
    check("drop_past_events entfernt dieselben zwei", len(dropped2), 2)
    check("drop_past_events behält denselben Rest",
          [e["name"] for e in kept2],
          ["heute", "mehrtägig läuft", "kaputtes Datum", "zukunft"])


def test_meldungen() -> None:
    """Nutzer-Fehlermeldungen (scripts/review_reports.py): bündeln pro
    Strecke, nicht pro Veranstaltung. Der Bündel-Schlüssel ist genau der
    distanzgenaue Override-Schlüssel - sonst würde eine Meldung zur
    10-km-Strecke am Ende die Marathonzeile derselben Veranstaltung
    korrigieren."""
    from review_reports import (  # lokaler Import, nur für diesen Test
        bundle_key, bundle_reports, parse_set,
    )

    ev = {"name": "48. Hochgratlauf", "datum_start": "2026-09-06", "laenge_km": 12.8}
    check("Bündel-Schlüssel distanzgenau",
          bundle_key(ev), "48. Hochgratlauf|2026-09-06|12.8")
    # 42,195 km und 42.2 km müssen im selben Bündel landen - die Anzeige
    # rundet auf eine Dezimalstelle, der Schlüssel muss das auch tun.
    check("Schlüssel rundet auf eine Dezimalstelle",
          bundle_key({"name": "M", "datum_start": "2026-10-11", "laenge_km": 42.195}),
          "M|2026-10-11|42.2")
    check("ohne Distanz kein Distanzteil",
          bundle_key({"name": "M", "datum_start": "2026-10-11", "laenge_km": None}),
          "M|2026-10-11")

    reports = [
        {"id": "a", "kategorie": "laenge", "beschreibung": "zu lang", "event": ev},
        {"id": "b", "kategorie": "laenge", "beschreibung": "12,4 km", "event": ev},
        {"id": "c", "kategorie": "url", "beschreibung": "Link tot",
         "event": {"name": "48. Hochgratlauf", "datum_start": "2026-09-06",
                   "laenge_km": 21.1}},
    ]
    bundles = bundle_reports(reports)["buendel"]
    check("zwei Strecken = zwei Bündel", len(bundles), 2)
    # Am häufigsten gemeldetes Bündel zuerst: zwei unabhängige Meldungen
    # sind ein stärkerer Hinweis als eine.
    check("häufigstes Bündel zuerst", bundles[0]["anzahl"], 2)
    check("Kategorien gezählt", bundles[0]["kategorien"], {"laenge": 2})

    # Komma-Distanzen aus dem Melde-Text dürfen nicht als Text landen.
    check("--set laenge_km=12,4 wird zur Zahl",
          parse_set(["laenge_km=12,4"]), {"laenge_km": 12.4})
    check("--set exclude=true wird bool",
          parse_set(["exclude=true"]), {"exclude": True})


def test_ortsverzeichnis() -> None:
    """Aufbereitung von places.json (scripts/build_places.py).

    Das Ortsverzeichnis füttert die Umkreissuche in events.html. Getestet
    wird, was dort schiefgehen kann: Großempfänger-Postleitzahlen, die
    als Ort durchgehen, und Schreibweisen, unter denen ein Ort nicht mehr
    gefunden wird.
    """
    print("\nOrtsverzeichnis (build_places):")

    # Der Suchschlüssel muss zu normalizePlaceText() in events.html
    # passen - beide Seiten müssen dasselbe aus einer Eingabe machen.
    check("Umlaute", normalisiere("München"), "muenchen")
    check("ß", normalisiere("Weißenburg"), "weissenburg")
    check("Akzent", normalisiere("Genève"), "geneve")
    # "Sankt Anton am Arlberg" heißt in den Daten "St. Anton am Arlberg" -
    # ohne Vereinheitlichung findet die Suche den Ort nicht.
    check("Sankt = St.", normalisiere("Sankt Anton"), normalisiere("St. Anton"))
    check("Bindestrich", normalisiere("Baden-Württemberg"), "baden wuerttemberg")

    # Großempfänger: In der deutschen PLZ-Datei steht bei diesen
    # Postleitzahlen ein Firmenname im Ortsfeld.
    check("Firma erkannt", _ist_firma("Mercedes-Benz Vertrieb NFZ GmbH"), True)
    check("Verein erkannt", _ist_firma("ADAC e. V."), True)
    check("echter Ort", _ist_firma("Aachen"), False)
    # Aalen endet auf "ag"+"en"; die Prüfung darf nur auf ganze Wörter
    # anschlagen, sonst verschwindet der Ort aus der Auswahl.
    check("Ort mit AG im Namen", _ist_firma("Aalen"), False)
    # Eine Rechtsform am Ende zählt nur dort, wo Ortsnamen kein
    # Kantonskürzel tragen: "Deutz AG" ist eine Firma, "Wohlen AG" die
    # Aargauer Gemeinde.
    check("Firma mit Rechtsform am Ende", _ist_firma("Deutz AG", streng=True), True)
    check("Gemeinde mit Kantonskürzel", _ist_firma("Wohlen AG"), False)

    # Was der Firmenfilter nicht erwischt ("Finanzamt Fürth"), fängt der
    # Abgleich mit dem Gazetteer: kein Ort dieses Namens in der Nähe.
    index = {
        "fuerth": [(49.48, 10.97, 132036, True)],
        "hamburg": [(53.55, 9.99, 1973896, True)],
    }
    check("Ort mit Entsprechung", _hat_ortsbezug(index, "Fürth", 49.48, 10.97), True)
    check("Finanzamt ohne Ort", _hat_ortsbezug(index, "Finanzamt Fürth", 49.48, 10.97), False)
    # "Gemeinde Ortsteil": der Ortsteil fehlt oft im Gazetteer, die
    # Gemeinde davor nicht - der Eintrag muss bleiben.
    check("Gemeinde + Ortsteil", _hat_ortsbezug(index, "Hamburg Stellingen", 53.57, 10.01), True)
    # Gleicher Name, aber 600 km entfernt: das ist ein anderer Ort.
    check("zu weit weg", _hat_ortsbezug(index, "Fürth", 53.55, 9.99), False)

    # Postleitzahlbezirke halten sich nicht an Landesgrenzen: die PLZ
    # 22113 liegt teils in Hamburg, teils in Schleswig-Holstein. Ohne
    # Zusammenfassung stand "Hamburg" zweimal in der Trefferliste.
    gruppen = {
        ("hamburg", "HH"): {"name": "Hamburg", "land": "DE", "region": "Hamburg",
                            "lats": [53.57], "lons": [10.01], "plz": {"20095"}},
        ("hamburg", "SH"): {"name": "Hamburg", "land": "DE", "region": "Schleswig-Holstein",
                            "lats": [53.53], "lons": [10.12], "plz": {"22113"}},
        ("neustadt", "BY"): {"name": "Neustadt", "land": "DE", "region": "Bayern",
                             "lats": [49.73], "lons": [11.13], "plz": {"91413"}},
        ("neustadt", "SN"): {"name": "Neustadt", "land": "DE", "region": "Sachsen",
                             "lats": [51.02], "lons": [14.21], "plz": {"01844"}},
    }
    _verschmelze_nachbarn(gruppen)
    check("Hamburg zusammengefasst", sorted(gruppen[("hamburg", "HH")]["plz"]), ["20095", "22113"])
    check("Hamburg nur noch einmal", ("hamburg", "SH") in gruppen, False)
    # Zwei echte "Neustadt" 200 km auseinander bleiben getrennt.
    check("Neustadt bleibt doppelt", ("neustadt", "SN") in gruppen, True)


def main() -> int:
    for test in (test_distanz, test_rundung, test_kategorie, test_land,
                 test_wettbewerbe, test_hoehenprofil, test_offizieller_link,
                 test_duplikate, test_namensvereinheitlichung,
                 test_vergangene_events, test_zeitrennen, test_meldungen,
                 test_ortsverzeichnis):
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
