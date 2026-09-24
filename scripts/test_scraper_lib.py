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

import requests
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
    # Andere Sprachen (22.09.2026): "Half marathon" traf nur das Teilwort
    # "marathon", der Grand Prix Winterthur stand mit 42,2 km in der Liste.
    check("Half marathon (EN)",
          guess_distance_km("Half marathon (anspruchsvolle Strecke)", CONFIG), 21.1)
    check("Semi-marathon (FR)", guess_distance_km("Semi-marathon de Lausanne", CONFIG), 21.1)
    check("mezza maratona (IT)", guess_distance_km("Mezza Maratona di Merano", CONFIG), 21.1)
    check("½ Marathon", guess_distance_km("½ Marathon", CONFIG), 21.1)
    check("maratona (IT)", guess_distance_km("Maratona dles Dolomites", CONFIG), 42.2)
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
    # Trail, Cross und Berglauf sind EINE Kategorie ("Trail"): Geländelauf,
    # von den Quellen mal so, mal so benannt (vom Nutzer am 19.09.2026 so
    # entschieden - vorher "Trail/Cross" und daneben "Berg").
    check("Höhenmeter -> Trail",
          guess_art2("Panoramalauf (989 Höhenmeter)", CONFIG), "Trail")
    check("Crosslauf", guess_art2("29. Mausebergecrosslauf", CONFIG), "Trail")
    check("Berglauf", guess_art2("47. Gaißacher Berglauf", CONFIG), "Trail")
    check("Alpiner Crosslauf", guess_art2("Alpiner Crosslauf Oberstdorf", CONFIG), "Trail")
    # Die alten Werte dürfen nirgends mehr entstehen.
    from scraper_lib import ART2_KEYWORDS_LAUFEN
    check("kein 'Berg' mehr in der Stichwortliste",
          sorted({k for _, k in ART2_KEYWORDS_LAUFEN}),
          ["Backyard Ultra", "Bahn", "Hindernis", "Straße", "Trail"])
    check("Stadtlauf -> Straße", guess_art2("40. Wolfenbütteler Stadtlauf", CONFIG), "Straße")
    check("Hindernislauf", guess_art2("Spartan Race Hindernislauf", CONFIG), "Hindernis")

    # ---- Hindernisläufe: Marken und der PLURAL ----
    #
    # Vom Nutzer am 21.09.2026 an der "Xletix Challenge - Berlin"
    # gemeldet ("ist ein Hindernis lauf und kein Lauf auf der Straße").
    # Die Nachzählung machte daraus 58 Zeilen. Erkannt wird die Marke
    # oder die PLURALFORM "Hindernisse(n)" - ein Hindernislauf wirbt mit
    # ihrer Zahl.
    for name in ("Xletix Challenge - Berlin", "XLETIX Challenge NRW",
                 "Muddy Angel Run - Dresden", "Mud Masters - Airport Weeze",
                 "CrossDeLuxe Erzgebirge", "Rats-Run - Kupferzell",
                 "Hotfoot Run Warstein Hot-20 (40 Hindernisse)",
                 "Puls 300 Cross- und Hindernis-Lauf",
                 "Bären Run 6 km Strongman Bären, etwa 20 Hindernissen"):
        check(f"{name!r} -> Hindernis", guess_art2(name, CONFIG), "Hindernis")
    # Die Gegenprobe, an der die naheliegende Fassung gescheitert wäre:
    # Ein gewöhnlicher Silvesterlauf nennt im SINGULAR ein Hindernis -
    # und zwar einmal, um es ausdrücklich zu VERNEINEN. Ein Muster auf
    # "hindernis" ohne Plural hätte beide Zeilen zu Hindernisläufen
    # gemacht.
    check("'kein Wasserhindernis' ist kein Hindernislauf",
          guess_art2("TIME2RUN Silvesterlauf in Schwabmünchen "
                     "6,7 km Strecke, kein Wasserhindernis", CONFIG), "Straße")
    check("'mögliches Wasserhindernis' ebenso",
          guess_art2("TIME2RUN Silvesterlauf in Schwabmünchen "
                     "12 km Strecke, mögliches Wasserhindernis", CONFIG), "Straße")

    # ---- Charity ist eine MARKIERUNG, keine Kategorie ----
    #
    # Vom 21.09.2026 an war "Charity" eine Kategorie (art2) und stand in
    # der Stichwortliste ganz vorn - ein Benefiz-Crosslauf war damit
    # Charity STATT Trail. Am selben Tag hat der Nutzer das
    # zurückgenommen ("Aber da bitte wieder die Kategorie einfügen"):
    # Die Kategorie war gerade die Auskunft, die dabei verloren ging.
    # Seitdem trägt das Event ein eigenes Merkmal (ist_charity), und die
    # Kategorie bleibt die Kategorie.
    from scraper_lib import ist_charity
    for name in ("19. Benin Benefiz-Lauf", "Sterntaler Spendenlauf",
                 "Bietlauf für einen Wohltätigen Zweck 9,2 km Crosslauf",
                 "ADAC Charity Treppenlauf", "Sponsorenlauf Brustkrebshilfe Dorsten",
                 "Borne to Run 48-Stunden-Spenden-Lauf",
                 # Vom Nutzer am 21.09.2026 gemeldet - trug keines der
                 # alten Stichwörter und stand deshalb unmarkiert da.
                 "Lauf für einen guten Zweck - Rastenberg"):
        check(f"{name!r} -> charity", ist_charity(name), True)
    check("Lauf ohne Charity-Wort ist nicht markiert",
          ist_charity("Lauf gegen Krebs"), False)
    # Die Kategorie bleibt jetzt erhalten - genau das war der Wunsch.
    check("Benefiz-Crosslauf behält seine Kategorie",
          guess_art2("Bietlauf für einen Wohltätigen Zweck 9,2 km Crosslauf", CONFIG), "Trail")
    check("Charity-Treppenlauf behält seine Kategorie",
          guess_art2("ADAC Charity Treppenlauf", CONFIG), "Trail")
    check("Spendenlauf auf der Straße bleibt Straße",
          guess_art2("Sterntaler Spendenlauf", CONFIG), "Straße")
    check("Benefiz-Seeschwimmen behält Freiwasser",
          guess_art2("Benefiz-Seeschwimmen im Freiwasser", CONFIG, "Schwimmen"), "Freiwasser")
    # Treppenläufe sind Trail (Nutzer, 21.09.2026: "als Trail aufnehmen").
    for name in ("Lotto Thüringen Treppenlauf", "TK Elevator Towerrun",
                 "Bad Wildbader Stäffeleslauf", "Neuwoges-Treppenhauslauf",
                 "Mt. Everest Treppenmarathon"):
        check(f"{name!r} -> Trail", guess_art2(name, CONFIG), "Trail")
    # Die Schwimm-Liste kennt Freiwasser/Becken, ohne Voreinstellung.
    check("Freiwasser", guess_art2("Bodensee Openwater Konstanz", CONFIG, "Schwimmen"), "Freiwasser")
    check("Becken", guess_art2("Hallenbad-Cup 1500 m", CONFIG, "Schwimmen"), "Becken")
    check("Schwimmen ohne Hinweis: keine Kategorie",
          guess_art2("Sommer-Cup", CONFIG, "Schwimmen"), None)
    check("Charity beim Radrennen ist eine Markierung, keine Kategorie",
          (ist_charity("Benefiz-Radrennen"), guess_art2("Benefiz-Radrennen", CONFIG, "Fahrrad")),
          (True, None))

    # Bestehende Daten werden auf die zusammengefasste Kategorie
    # nachgezogen - je Sportart: Beim Laufen wird "Cross" zu "Trail",
    # beim Triathlon bleibt "Cross" eine eigene Kategorie, und beim
    # Fahrrad ist "Cyclecross" eine dritte Sache.
    from clean_events import merge_art2, ART2_MERGED  # lokaler Import, nur hier
    rows = [
        {"name": "Waldtrail", "art1": "Laufen", "art2": "Trail/Cross"},
        {"name": "Mausebergecrosslauf", "art1": "Laufen", "art2": "Cross"},
        {"name": "Gaißacher Berglauf", "art1": "Laufen", "art2": "Berg"},
        {"name": "Tippfehler-Override", "art1": "Laufen", "art2": "Berglauf"},
        {"name": "Hofer Backyard Ultra", "art1": "Laufen", "art2": "Backcountry Ultra"},
        {"name": "Backyardman Würzburg", "art1": "Triathlon", "art2": "Backyard"},
        {"name": "Crosstriathlon", "art1": "Triathlon", "art2": "Cross"},
        {"name": "Stadtlauf", "art1": "Laufen", "art2": "Straße"},
        {"name": "Querfeldein-Rennen", "art1": "Fahrrad", "art2": "Cyclecross"},
    ]
    check("sechs Einträge zusammengefasst", len(merge_art2(rows)), 6)
    check("neue Kategorie steht", [r["art2"] for r in rows],
          ["Trail", "Trail", "Trail", "Trail", "Backyard Ultra", "Backyard Ultra",
           "Cross", "Straße", "Cyclecross"])
    check("idempotent", len(merge_art2(rows)), 0)
    check("kein Zielwert ist zugleich ein Schlüssel",
          [z for m in ART2_MERGED.values() for z in m.values() if z in m], [])

    # Die Kategorie-Liste der Filter (filter-ui.js) muss dieselben Werte
    # anbieten, die die Stichwortliste erzeugt - sonst filtert die Seite
    # einen Wert heraus, den es gibt (genau das wäre beim Umbenennen
    # passiert, wenn man nur eine der beiden Dateien anfasst).
    ui_js = (Path(__file__).resolve().parent.parent / "filter-ui.js").read_text(encoding="utf-8")
    zeile = next(l for l in ui_js.splitlines() if "'Laufen': [" in l)
    from scraper_lib import ART2_KEYWORDS_LAUFEN, DEFAULT_ART2_LAUFEN
    erzeugbar = {kat for _, kat in ART2_KEYWORDS_LAUFEN} | {DEFAULT_ART2_LAUFEN}
    fehlend = sorted(k for k in erzeugbar if f"'{k}'" not in zeile)
    check("Filter kennt alle Laufen-Kategorien", fehlend, [])

    # ---- Mehrsport: Ein Ironman ist kein Lauf ----
    #
    # Alle Quellen sind Laufkalender (default_art1 = "Laufen"), also stand
    # jeder Triathlon als Laufveranstaltung in der Liste - vom Nutzer an
    # "Ironman 70.3 Kraichgau · Laufen · Straße" gemeldet. Bei einem
    # Ironman kann man sich nicht für den Lauf allein anmelden.
    from scraper_lib import (ART2_KEYWORDS_TRIATHLON, DEFAULT_ART2_TRIATHLON,
                             guess_art1)
    print("\nSportart-Erkennung (guess_art1):")
    for name, erwartet in (
            ("Ironman 70.3 Kraichgau", "Triathlon"),
            ("Ironman 5150 Erkner Berlin-Brandenburg", "Triathlon"),
            ("Challenge Roth", "Triathlon"),
            ("Kornwestheimer Triathlon", "Triathlon"),
            ("Baltic X Cross Duathlon", "Triathlon"),
            ("SwimRun Rheinsberg", "Triathlon"),
            # Gegenprobe: Läufe bleiben Läufe. "Marathon" und "Ultra"
            # dürfen nichts umstellen.
            ("Königsforst-Marathon", "Laufen"),
            ("Hofer Backyard Ultra", "Laufen"),
            ("Spartan Race Hindernislauf", "Laufen")):
        check(name, guess_art1(name, CONFIG), erwartet)

    print("\nKategorie beim Mehrsport (guess_art2 mit art1):")
    # Das Format steht VOR dem Gelände: Ein "Cross Duathlon" ist ein
    # Duathlon, der im Gelände stattfindet - "Duathlon" ist die Auskunft,
    # nach der jemand filtert.
    check("Cross Duathlon -> Duathlon",
          guess_art2("Baltic X Cross Duathlon", CONFIG, "Triathlon"), "Duathlon")
    check("Crosstriathlon -> Cross",
          guess_art2("Wuppertaler Sparkassen Crosstriathlon", CONFIG, "Triathlon"), "Cross")
    check("SwimRun", guess_art2("SwimRun Rheinsberg", CONFIG, "Triathlon"), "Swimrun")
    check("Indoor-Triathlon",
          guess_art2("Indoor-Triathlon Aschersleben", CONFIG, "Triathlon"), "Indoor")
    check("Ironman -> Straße",
          guess_art2("Ironman 70.3 Kraichgau", CONFIG, "Triathlon"), "Straße")
    # Ohne art1 bleibt es bei der Lauf-Liste (ältere Aufrufe).
    check("ohne art1 unverändert", guess_art2("Mausebergecrosslauf", CONFIG), "Trail")
    # Eine Kategorie für beide Sportarten: Das Last-Man-Standing-Format
    # heißt beim Laufen und beim Triathlon gleich (Nutzer, 19.09.2026).
    check("Backyard-Triathlon", guess_art2("Backyardman Würzburg", CONFIG, "Triathlon"),
          "Backyard Ultra")

    # Über den ganzen Block statt über eine Zeile: Die Triathlon-Liste
    # ist länger als 80 Zeichen und daher umbrochen.
    start = ui_js.index("'Triathlon': [")
    zeile_tri = ui_js[start:ui_js.index("]", start)]
    erzeugbar_tri = {kat for _, kat in ART2_KEYWORDS_TRIATHLON} | {DEFAULT_ART2_TRIATHLON}
    fehlend_tri = sorted(k for k in erzeugbar_tri if f"'{k}'" not in zeile_tri)
    check("Filter kennt alle Triathlon-Kategorien", fehlend_tri, [])

    # Und die Übersetzung muss jeden Wert kennen - sonst steht im Filter
    # der rohe Schlüssel.
    filters_js = (Path(__file__).resolve().parent.parent / "filters.js").read_text(encoding="utf-8")
    ohne_text = sorted(k for k in erzeugbar_tri if f"'{k}': {{" not in filters_js)
    check("jede Triathlon-Kategorie ist übersetzt", ohne_text, [])

    # Der Bestand wird nachgezogen (clean_events.fix_multisport_art1).
    from clean_events import fix_multisport_art1
    bestand = [
        {"name": "Ironman 70.3 Kraichgau", "art1": "Laufen", "art2": "Straße"},
        {"name": "Cross-Duathlon in Hünsborn", "art1": "Laufen", "art2": "Trail"},
        {"name": "Königsforst-Marathon", "art1": "Laufen", "art2": "Straße"},
    ]
    check("zwei Einträge umgestellt", len(fix_multisport_art1(bestand)), 2)
    check("Sportart und Kategorie stimmen",
          [(r["art1"], r["art2"]) for r in bestand],
          [("Triathlon", "Straße"), ("Triathlon", "Duathlon"), ("Laufen", "Straße")])
    check("idempotent", len(fix_multisport_art1(bestand)), 0)


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
    # Südtirol (21.09.2026): "Italien" gilt nur mit Südtiroler PLZ oder
    # Koordinaten in der Provinz Bozen - sonst bleibt der Zwischenstand
    # "Italien" stehen und fällt später heraus.
    from scraper_lib import in_suedtirol, LAENDER as _regionen
    check("(Italien) mit Südtiroler PLZ", guess_land("39012 Meran (Italien)"), "Italien (Südtirol)")
    check("(ITA) ohne Südtiroler PLZ bleibt Italien", guess_land("20121 Milano (ITA)"), "Italien")
    check("Südtirol im Text", guess_land("Bozen, Südtirol"), "Italien (Südtirol)")
    check("Bozen liegt in Südtirol", in_suedtirol(46.4983, 11.3548), True)
    check("Sterzing liegt in Südtirol", in_suedtirol(46.8967, 11.4300), True)
    check("Innsbruck nicht", in_suedtirol(47.2692, 11.4041), False)
    check("Trient nicht (gleiche Region, andere Provinz)", in_suedtirol(46.0667, 11.1167), False)
    check("Südtirol zählt zu den Regionen", "Italien (Südtirol)" in _regionen, True)
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
    check("400 hm / 14,6 km -> Trail",
          art2_from_elevation("VR Bank – BraunenBerg-Lauf: 14,6 km, ca. 400 Hm", 14.6, "Straße"),
          "Trail")
    check("248 hm / 8,2 km -> Trail",
          art2_from_elevation("BergBau-Lauf: 8,2 km, ca. 248 Hm", 8.2, "Straße"), "Trail")
    # Flacher Stadtmarathon mit ein paar Brücken bleibt Straße (2,4 m/km).
    check("100 hm / 42,2 km bleibt Straße",
          art2_from_elevation("Stadtmarathon, 100 hm", 42.2, "Straße"), "Straße")
    # Eine spezifischere Kategorie aus dem Namen wird nie überschrieben.
    check("Hindernis bleibt Hindernis",
          art2_from_elevation("Spartan Beast: 21 km, ca. 1100 Hm", 21.0, "Hindernis"),
          "Hindernis")
    check("ohne Distanz keine Aussage",
          art2_from_elevation("ca. 400 Hm", None, "Straße"), "Straße")


def test_offizieller_link() -> None:
    print("\nPortal- vs. offizieller Link (update_existing_event):")
    check("running.life ist Portal", is_portal_link("https://running.life/de/termine/x"), True)
    check("laufen.de ist Portal", is_portal_link("https://laufen.de/laufkalender/details/1"), True)
    check("Veranstalter ist kein Portal", is_portal_link("https://www.braunenberg-lauf.de/"), False)
    # Ein Zeitnehmer ist kein Veranstalter (Kallinchen Triathlon, 19.09.2026).
    check("Zeitnehmer ist Portal",
          is_portal_link("https://www.berlin-timing.de/Kallinchen-Triathlon"), True)
    # Die übrigen Zeitnehmer und Anmeldeplattformen ebenso (19.09.2026,
    # "zieh die anderen Zeitnehmer genauso nach"): Ein Link dorthin ist
    # nie die Veranstalterseite - er wird ersetzt, sobald eine bekannt ist.
    for url in ("https://my.raceresult.com/354931/", "https://runtix.com/sts/10021/3221",
                "https://www.davengo.com/event/overview/x", "https://ladv.de/ausschreibung/detail/1/x.htm",
                "https://www.datasport.de/anmeldeservice/x", "https://rennmeldung.de/cgi-bin/bewerb.cgi?bewerb=1",
                "https://laufen-os.de/", "https://www.sas-online.net/eventportal_bs/837/",
                "https://www.sportprogramme.org/cakespg/events/menue/5037",
                "https://baer-service.de/veranstaltung/AAL/"):
        check(f"Zeitnehmer/Anmeldung ist Portal: {url.split('/')[2]}", is_portal_link(url), True)
    check("Veranstalter mit Zeitnehmer im Namen bleibt", is_portal_link("https://timing-team-lauf.de/"), False)
    # Hostname statt Teilzeichenkette: "tsv-weeze-leichtathletik.de" ist
    # kein Portal, obwohl "leichtathletik.de" darin steckt (Linkprüfung
    # 19.09.2026); Subdomains des Portals zählen dagegen mit.
    check("Vereinsdomain mit Portal-Endung ist kein Portal",
          is_portal_link("https://www.tsv-weeze-leichtathletik.de/staffel.html"), False)
    check("Subdomain des Portals ist Portal",
          is_portal_link("https://www.leichtathletik.de/wettkaempfe/x"), True)

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

    # Zeitrennen: Stundenlauf und Halbstundenlauf derselben Veranstaltung
    # sind zwei Wettbewerbe (Döbelner Fackellauf); dieselbe Dauer bleibt
    # ein Duplikat, und eine fehlende Dauer schließt nichts aus.
    st = {"name": "Döbelner Fackellauf", "datum_start": "2026-10-28",
          "standort": "Döbeln", "laenge_km": None, "dauer_h": 1.0}
    check("Stundenlauf vs. Halbstundenlauf getrennt",
          is_same_event(st, dict(st, dauer_h=0.5)), False)
    check("gleiche Dauer bleibt Duplikat", is_same_event(st, dict(st)), True)
    check("ohne Dauer weiter Duplikat", is_same_event(st, dict(st, dauer_h=None)), True)
    # Distanz gegen Dauer (seit 21.09.2026): zwei Wettbewerbe. Der
    # 24-h-Lauf des Rokathon ist nicht sein Marathon - vorher verschmolz
    # ein nachgetragenes Zeitrennen mit der Distanz-Zeile und ließ sich
    # gar nicht anlegen. Ohne JEDE Angabe bleibt es ein Duplikat.
    m = dict(st, laenge_km=42.2, dauer_h=None)
    check("Marathon vs. 24-h-Lauf getrennt", is_same_event(m, dict(st, dauer_h=24.0)), False)
    check("Marathon vs. Zeile ohne jede Angabe: Duplikat",
          is_same_event(m, dict(st, dauer_h=None)), True)

    # Vom Nutzer gemeldet: Marathon und Halbmarathon München standen je
    # DOPPELT in der Liste. Ursache war die Wortstellung - als Zeichenfolge
    # nur 0,69 Ähnlichkeit, als Wortmenge identisch.
    D, S = "2026-10-11", "München"
    m1 = {"name": "40. München Marathon by Brooks", "datum_start": D, "standort": S,
          "laenge_km": 42.2, "veranstalter_url": "https://marathonmuenchen.org"}
    m2 = {"name": "MARATHON MÜNCHEN", "wettbewerb": "Marathon", "datum_start": D,
          "standort": S, "laenge_km": 42.2, "veranstalter_url": "https://marathonmuenchen.org/"}
    check("Wortstellung vertauscht", is_same_event(m1, m2), True)

    # Sechster Weg (22.09.2026): zwei Quellen, zwei Labels für dieselbe
    # Strecke - "Marathon" (running.life) neben "Splatterthon" bzw.
    # "42.2 km" (lauftermine.ch). Der Halloween Run Bremen stand fünffach
    # in der Liste. Die Gegenproben sind der wichtigere Teil: Gattung
    # (Walking, Sprint/Volks) und eine halbe Kilometer Unterschied halten
    # zwei Wettbewerbe auseinander.
    hb = {"name": "Halloween Run Bremen", "wettbewerb": "Marathon", "datum_start": "2026-10-31",
          "standort": "Bremen", "laenge_km": 42.2, "art1": "Laufen"}
    check("zwei Labels ohne Gattung: Duplikat",
          is_same_event(hb, dict(hb, name="Halloween-Run-Bremen", wettbewerb="Splatterthon")), True)
    check("Label nur Maßzahl gegen Namen: Duplikat",
          is_same_event(dict(hb, wettbewerb="42.2 km"), hb), True)
    check("Runde in zwei Schreibweisen: Duplikat",
          is_same_event(dict(hb, wettbewerb="Kürbislauf 13,333 K", laenge_km=13.3),
                        dict(hb, wettbewerb="13 km", laenge_km=13.0)), True)
    check("Walking gegen Lauf: getrennt",
          is_same_event(dict(hb, wettbewerb="10 km Walking", laenge_km=10.0),
                        dict(hb, wettbewerb="Stadtwerke 10-km-Lauf", laenge_km=10.0)), False)
    check("Halbmarathon gegen Nordic Walking: getrennt",
          is_same_event(dict(hb, wettbewerb="Halbmarathon", laenge_km=21.1),
                        dict(hb, wettbewerb="Peri Power Nordic Walking", laenge_km=21.1)), False)
    check("Sprint gegen Volksdistanz: getrennt",
          is_same_event(dict(hb, wettbewerb="Sprintdistanz 28,8 km", laenge_km=28.8, art1="Triathlon"),
                        dict(hb, wettbewerb="Volksdistanz 28,5 km", laenge_km=28.5, art1="Triathlon")), False)
    check("halber Kilometer Unterschied: getrennt",
          is_same_event(dict(hb, wettbewerb="12 km Seen-Lauf", laenge_km=12.0),
                        dict(hb, wettbewerb="12,5 km Trailrun", laenge_km=12.5)), False)
    # Gravel neben Straße über dieselbe Länge sind zwei Wettbewerbe (Erkelenzer RTF, 24.09.2026).
    check("'RTF 110 km' und 'Gravel Ride 110 km' bleiben zwei Zeilen",
          is_same_event(dict(hb, art1="Fahrrad", wettbewerb="RTF 110 km", laenge_km=110.0),
                        dict(hb, art1="Fahrrad", wettbewerb="Gravel Ride 110 km", laenge_km=110.0)), False)
    check("Kinderlauf gegen Hauptlauf: getrennt",
          is_same_event(dict(hb, wettbewerb="Mini Marathon", laenge_km=21.1),
                        dict(hb, wettbewerb="21,097 km Generali Halbmarathon", laenge_km=21.1)), False)

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

    # Einwortiger Veranstaltungsname, eine Zeile ohne Wettbewerb: so stand
    # der SAARathon zweimal mit 42,2 km in den Daten (einmal mit
    # Wettbewerbs-Bezeichnung und offizieller Seite, einmal ohne und mit
    # Portallink). "SAARathon" ist ein Wort - zu kurz für die
    # Teilmengen-Regel -, und gegen die lange Bezeichnung reicht die
    # Ähnlichkeit nicht.
    SD, SS = "2026-10-11", "Saarbrücken"
    sa1 = {"name": "SAARathon", "wettbewerb": "42,195 km Weltkulturerbe-Marathon",
           "datum_start": SD, "standort": SS, "laenge_km": 42.2, "art1": "Laufen",
           "veranstalter_url": "https://www.westspangenlauf.de"}
    sa2 = {"name": "SAARathon", "datum_start": SD, "standort": SS, "laenge_km": 42.2,
           "art1": "Laufen",
           "veranstalter_url": "https://laufen.de/laufkalender/details/26V14000009060002"}
    check("gleicher Name, eine Zeile ohne Wettbewerb", is_same_event(sa1, sa2), True)
    # Nennen BEIDE einen Wettbewerb, ist das Label das Unterscheidende -
    # ein 10-km-Lauf und ein 10-km-Walking sind zwei Einträge.
    sa3 = dict(sa2, wettbewerb="42,2 km Nordic Walking")
    check("beide mit Wettbewerb bleiben getrennt", is_same_event(sa1, sa3), False)
    # Dieselbe Strecke, andere Sportart: auch kein Duplikat (Datenregel 1).
    sa4 = dict(sa2, art1="Wandern")
    check("andere Sportart bleibt getrennt", is_same_event(sa1, sa4), False)

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
    print("\nZeitrennen (parse_duration_h) und Backyard Ultra:")
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

    # Der Mad Chicken Run (vom Nutzer gemeldet): Die Quelle schreibt
    # "24h Solo auf einer 2km MotoCross-Strecke mit je 60HM (2km)". Die
    # 2 km sind eine RUNDE, keine Renndistanz - als Distanz gespeichert
    # hätte die 5-km-Mindestdistanz den Eintrag anschließend verworfen,
    # und genau deshalb fehlten die vier 24h-Wettbewerbe in der Liste.
    chicken = parse_competitions([
        "24h Solo auf einer 2km MotoCross-Strecke mit je 60HM (2km)",
        "24h Solo auf einer entspannten 2km Runde mit je 15HM (2km)",
        "24h im 5er Team auf der 2km Cross Runde - Einzelergebnisse (2km)",
        "Marathon in schönen 21 flachen Runden (42km)",
        "Halbmarathon in 11 flachen Runden (22km)",
        "10km Einstiegsdroge in 5 flachen Runden (10km)",
    ], CONFIG)
    check("Rundenlänge wird nicht zur Distanz",
          [(c.laenge_km, c.dauer_h) for c in chicken],
          [(None, 24.0), (42.0, None), (22.0, None), (10.0, None)])

    # Ein Umrechnungssatz begrenzt nichts: "24 Stunden ergeben 100 Meilen"
    # beschreibt die Rundenlänge eines Backyard, der läuft aber weiter,
    # bis nur noch eine Person übrig ist.
    check("Umrechnungssatz ist keine Zeitvorgabe",
          parse_duration_h("6,708 km pro Runde beim SWUB; 24 Stunden ergeben 100 Meilen."),
          None)

    # Rundenlänge aus bestehenden Backyard-Einträgen herausnehmen; große
    # Angaben bleiben stehen und werden nur gemeldet.
    from clean_events import clear_backyard_lap_km  # lokaler Import
    rows = [
        {"name": "Hofer Backyard Ultra", "art2": "Backyard Ultra", "laenge_km": 7.0},
        {"name": "Backyard SWUB", "art2": "Backyard Ultra", "laenge_km": 6.7},
        {"name": "RET-Team Backyard", "art2": "Backyard Ultra", "laenge_km": 80.0},
        {"name": "Stadtlauf", "art2": "Straße", "laenge_km": 7.0},
    ]
    cleared, to_check = clear_backyard_lap_km(rows)
    check("zwei Runden entfernt", len(cleared), 2)
    check("Runde ist weg", [r["laenge_km"] for r in rows], [None, None, 80.0, 7.0])
    check("große Angabe nur gemeldet", len(to_check), 1)

    # Die Laufen-Kategorie "Backyard Ultra" (bis 19.09.2026 "Backcountry
    # Ultra") ist das Last-Man-Standing-Format.
    check("Backyard Ultra", guess_art2("Backyard Ultra Berlin", CONFIG),
          "Backyard Ultra")
    check("Schreibweise egal", guess_art2("Murr BackYard 12h", CONFIG),
          "Backyard Ultra")
    check("Last Man Standing", guess_art2("Last Man Standing Hamburg", CONFIG),
          "Backyard Ultra")
    # Höhenmeter machen aus einem Backyard keinen Trail: Das
    # backyard-Stichwort steht VOR der Berg-/Höhenmeter-Zeile.
    check("Backyard mit Höhenmetern bleibt Backyard",
          guess_art2("Backyard Ultra Harz (120 Höhenmeter pro Runde)", CONFIG),
          "Backyard Ultra")
    # ABER: Steht "Trail" im Namen, ist es ein Trailrun, der das Wort nur
    # mitträgt. Deshalb steht das backyard-Stichwort NACH der Trail-Regel.
    check("Backyard Ultra Trail ist ein Trail",
          guess_art2("Backyard Ultra Trail Harz", CONFIG), "Trail")
    # Ein "Backcountry Ultra" ist ein langer Trailrun, kein Rundenformat -
    # seit die Kategorie das Format nennt, ist das Stichwort weg.
    check("Backcountry Ultra Trail ist ein Trail",
          guess_art2("Backcountry Ultra Trail 80 km", CONFIG), "Trail")


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


def test_kalenderdateien() -> None:
    """Die Dateinamen der .ics-Dateien werden ZWEIMAL berechnet: in
    scripts/build_ics.py (erzeugt die Dateien) und in events.html
    (verlinkt sie). Weichen die beiden ab, zeigt der Kalender-Knopf ins
    Leere - deshalb prüft dieser Test die JS-Umsetzung gegen die
    Python-Umsetzung, indem er node mit den gleichen Fällen aufruft."""
    import json as _json
    import re as _re
    import shutil
    import subprocess

    from build_ics import build_ics, ics_dateiname, slugify

    print("\nKalenderdateien (build_ics + events.html):")
    check("Umlaute werden zerlegt", slugify("Königsforst-Marathon"), "konigsforst-marathon")
    check("ß wird ss", slugify("Straßenlauf Groß-Gerau"), "strassenlauf-gross-gerau")
    check("Sonderzeichen werden Bindestrich",
          slugify("B2Run: Berlin (Firmenlauf!)"), "b2run-berlin-firmenlauf")

    faelle = [
        {"name": "Hofer Backyard Ultra", "datum_start": "2027-06-26",
         "datum_ende": "2027-06-28", "standort": "Hof", "land": "Deutschland",
         "art1": "Laufen", "art2": "Backyard Ultra", "dauer_h": None,
         "laenge_km": None, "wettbewerb": None, "veranstalter_url": None},
        {"name": "Königsforst-Marathon", "datum_start": "2027-03-14",
         "standort": "Bergisch Gladbach", "land": "Deutschland", "art1": "Laufen",
         "art2": "Trail", "laenge_km": 42.2, "wettbewerb": "Marathon 42.2 km",
         "veranstalter_url": "https://example.org/lauf"},
        {"name": "24h Mad Chicken Run", "datum_start": "2026-09-19",
         "datum_ende": "2026-09-20", "standort": "Kolkwitz", "land": "Deutschland",
         "art1": "Laufen", "art2": "Straße", "dauer_h": 24.0, "laenge_km": None,
         "wettbewerb": "24h Solo", "veranstalter_url": None},
        {"name": "Bodensee Openwater", "datum_start": "2027-08-28",
         "standort": "Wallhausen", "land": "Deutschland", "art1": "Schwimmen",
         "art2": "Freiwasser", "laenge_km": 2.5, "wettbewerb": "2,5 km",
         "veranstalter_url": None},
    ]

    check("Dateiname mit Dauer statt Distanz",
          ics_dateiname(faelle[2]),
          "2026-09-19-24h-mad-chicken-run-24h-kolkwitz.ics")
    check("Dateiname ohne beides",
          ics_dateiname(faelle[0]),
          "2027-06-26-hofer-backyard-ultra-x-hof.ics")

    # Mehrtägig: DTEND ist exklusiv, also der Tag NACH dem letzten.
    ics = build_ics(faelle[0], "20260101T000000Z")
    check("DTSTART", "DTSTART;VALUE=DATE:20270626" in ics, True)
    check("DTEND ist Enddatum + 1", "DTEND;VALUE=DATE:20270629" in ics, True)
    check("CRLF-Zeilenenden", ics.count("\r\n") >= 15, True)
    # Ein Label, das nur die Distanz wiederholt, gehört nicht in den Titel.
    ics2 = build_ics(faelle[3], "20260101T000000Z")
    check("Masszahl-Label nicht im Titel",
          "SUMMARY:Bodensee Openwater\r\n" in ics2, True)
    check("Komma maskiert (RFC 5545)",
          "LOCATION:Wallhausen\\, Deutschland" in ics2, True)

    # --- Gegenprobe in JavaScript ---
    node = shutil.which("node")
    if not node:
        print("  (node nicht vorhanden - JS-Gegenprobe übersprungen)")
        return
    quelle = (Path(__file__).resolve().parent.parent / "event-detail.js").read_text(encoding="utf-8")
    # Die vier Funktionen aus event-detail.js (die Detail-Box, von Liste
    # UND Karte genutzt) herausschneiden und in node laufen lassen. Kein
    # Nachbau: es läuft genau der Code, den die Seiten nutzen.
    stuecke = []
    for name in ("function icsSlug(", "function icsMasszahl(", "function eventSlug(",
                 "function icsFileName("):
        i = quelle.index(name)
        j = quelle.index("\n  }\n", i) + len("\n  }\n")
        stuecke.append(quelle[i:j])
    skript = "\n".join(stuecke) + (
        "\nconst faelle = " + _json.dumps(faelle, ensure_ascii=False) + ";"
        "\nconsole.log(JSON.stringify(faelle.map(icsFileName)));"
    )
    ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    if ergebnis.returncode != 0:
        check("JS-Gegenprobe lief", ergebnis.stderr.strip()[:200], "")
        return
    js_namen = _json.loads(ergebnis.stdout)
    py_namen = [ics_dateiname(f) for f in faelle]
    check("event-detail.js und build_ics.py erzeugen dieselben Dateinamen",
          js_namen, py_namen)

    # Und: passt der Ordner kalender/ überhaupt zu events.json?
    #
    # Das prüft die CI ohnehin (Schritt "kalender/ passt zu events.json",
    # dort inklusive Dateiinhalt) - aber erst NACH dem Push. Genau daran
    # ist die CI viermal hintereinander rot geworden: Der wöchentliche
    # Datenlauf hatte eine neue events.json committet, ohne die .ics-
    # Dateien mitzunehmen. Lokal fiel das nicht auf, weil kein Test
    # danach gesehen hat. Hier ist der Vergleich billig (nur die
    # Dateinamen, keine Inhalte) und schlägt vor dem Commit an.
    wurzel = Path(__file__).resolve().parent.parent
    events_json = wurzel / "events.json"
    kalender = wurzel / "kalender"
    if events_json.exists() and kalender.is_dir():
        events = _json.loads(events_json.read_text(encoding="utf-8"))
        erwartet = set()
        for e in events:
            if e.get("datum_start") and e.get("name"):
                erwartet.add(ics_dateiname(e))
        vorhanden = {pfad.name for pfad in kalender.glob("*.ics")}
        fehlend = sorted(erwartet - vorhanden)
        ueberzaehlig = sorted(vorhanden - erwartet)
        check("kalender/ hat eine Datei je Event (%d fehlen, %d zu viel)"
              % (len(fehlend), len(ueberzaehlig)),
              (fehlend[:3], ueberzaehlig[:3]), ([], []))
        if fehlend or ueberzaehlig:
            print("  -> python3 scripts/build_ics.py ausführen und mit committen")


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


# Alle HTML-Seiten des Projekts. Zwei Tests laufen darüber (JS-Syntax
# und "keine fremden Dateien"); eine neue Seite hier eintragen, nicht an
# zwei Stellen.
SEITEN = ("index.html", "events.html", "karte.html", "impressum.html", "datenschutz.html")


def test_js_syntax() -> None:
    """`node --check` über die Inline-Skripte und die geteilten Dateien.

    Die drei Seiten tragen ihr Skript im HTML - ein Tippfehler darin fällt
    weder Python noch einem Linter auf, die Seite bleibt einfach leer
    (genau das ist beim Umbau mehrfach passiert). Bisher stand
    "node --check nicht vergessen" nur in CLAUDE.md; jetzt prüft es der
    Test - und damit auch die CI.

    Ohne node wird übersprungen (wie die JS-Gegenprobe oben): Wer nur die
    Daten anfasst, soll nicht an einem fehlenden node hängen.
    """
    import shutil
    import subprocess

    def fehlerzeile(erg) -> str:
        """Die eine Zeile, die den Fehler benennt.

        node schreibt Datei, Codezeile, Pfeil, SyntaxError und zuletzt
        seine eigene Version - `splitlines()[-1]` wäre also "Node.js
        v22" und damit nutzlos.
        """
        if erg.returncode == 0:
            return ""
        zeilen = [z.strip() for z in erg.stderr.splitlines() if z.strip()]
        for z in zeilen:
            if "Error" in z:
                return z
        return zeilen[0] if zeilen else "node --check fehlgeschlagen"

    print("\nJavaScript-Syntax (node --check):")
    node = shutil.which("node")
    if not node:
        print("  (node nicht vorhanden - übersprungen)")
        return
    wurzel = Path(__file__).resolve().parent.parent
    import re as _re
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        for name in SEITEN:
            quelle = (wurzel / name).read_text(encoding="utf-8")
            # Nur Skripte OHNE src: die geladenen Dateien werden unten
            # einzeln geprüft.
            bloecke = _re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                                  quelle, _re.S)
            check(f"{name}: Inline-Skript vorhanden", len(bloecke) >= 1, True)
            for nr, block in enumerate(bloecke):
                datei = Path(tmp) / f"{name}.{nr}.js"
                datei.write_text(block, encoding="utf-8")
                erg = subprocess.run([node, "--check", str(datei)],
                                     capture_output=True, text=True)
                check(f"{name}: Inline-Skript {nr} ist gültiges JS",
                      fehlerzeile(erg), "")
        for name in ("filters.js", "filter-ui.js", "event-detail.js", "auth.js",
                     "firebase-config.js", "functions/index.js"):
            pfad = wurzel / name
            if not pfad.exists():
                continue
            erg = subprocess.run([node, "--check", str(pfad)],
                                 capture_output=True, text=True)
            check(f"{name} ist gültiges JS", fehlerzeile(erg), "")


def test_abo_rhythmen() -> None:
    """Die Abo-Rhythmen stehen an vier Stellen - alle müssen gleich sein.

    `auth.js` legt sie an, `functions/index.js` wertet sie aus,
    `firestore.rules` lässt nur sie durch, und `events.html` hat je
    Rhythmus zwei Texte. Läuft eine Stelle weg, entsteht der leise
    Fehler: Ein Abo wird gespeichert, aber die Function schickt nie eine
    E-Mail (oder die Regel weist es ab, und niemand weiß warum).
    """
    import re as _re

    wurzel = Path(__file__).resolve().parent.parent
    print("\nAbo-Rhythmen (auth.js / functions / rules / events.html):")

    def liste(pfad: str, muster: str) -> list[str]:
        text = (wurzel / pfad).read_text(encoding="utf-8")
        treffer = _re.search(muster, text, _re.S)
        if not treffer:
            return []
        return _re.findall(r"['\"]([a-z]+)['\"]", treffer.group(1))

    aus_auth = liste("auth.js", r"const ABO_RHYTHMEN = \[([^\]]*)\]")
    aus_function = liste("functions/index.js", r"const ABO_RHYTHMEN = \[([^\]]*)\]")
    aus_rules = liste("firestore.rules", r"rhythmus in\s*\n?\s*\[([^\]]*)\]")
    check("auth.js kennt drei Rhythmen", aus_auth, ["sofort", "woechentlich", "monatlich"])
    check("functions/index.js hat dieselben", aus_function, aus_auth)
    check("firestore.rules lässt dieselben durch", sorted(aus_rules), sorted(aus_auth))

    # Je Rhythmus ein Titel und eine Erklärung, in DE und EN.
    seite = (wurzel / "events.html").read_text(encoding="utf-8")
    fehlend = []
    for key in aus_auth:
        for schluessel in (f"abo_r_{key}:", f"abo_r_{key}_note:"):
            if seite.count(schluessel) != 2:      # einmal DE, einmal EN
                fehlend.append(f"{schluessel} ({seite.count(schluessel)}x)")
    check("events.html hat je Rhythmus Titel und Erklärung in DE und EN", fehlend, [])

    # Die Wartezeiten der Function müssen zu den Rhythmen passen.
    fn = (wurzel / "functions/index.js").read_text(encoding="utf-8")
    tage = _re.search(r"const RHYTHMUS_TAGE = \{([^}]*)\}", fn, _re.S)
    check("functions/index.js hat je Rhythmus eine Wartezeit",
          sorted(_re.findall(r"(\w+):", tage.group(1))) if tage else [],
          sorted(aus_auth))


def test_override_schluessel() -> None:
    """Die Schlüssel in manual_overrides.json müssen zu override_keys() passen.

    Die Distanz wird dort mit `:g` formatiert - also "21", nicht "21.0".
    Ein Schlüssel in der falschen Schreibweise wird **stillschweigend nie
    gefunden**: Der Override steht in der Datei, sieht richtig aus und
    tut nichts. Genau das ist beim Eintragen des Fichtel-Duplikats
    passiert (Schlüssel "…|21.0", Wirkung null). Dieser Test macht daraus
    einen roten Test statt einer stillen Lücke.
    """
    import json as _json

    print("\nSchlüssel in manual_overrides.json:")
    wurzel = Path(__file__).resolve().parent.parent
    pfad = wurzel / "scripts" / "manual_overrides.json"
    daten = _json.loads(pfad.read_text(encoding="utf-8"))

    from scraper_lib import override_keys

    falsch = []
    for key in daten:
        if key == "_readme":
            continue
        teile = key.split("|")
        if len(teile) not in (2, 3):
            falsch.append(f"{key}: weder '<Name>|<Datum>' noch '<Name>|<Datum>|<km>'")
            continue
        if len(teile) == 3:
            try:
                km = float(teile[2])
            except ValueError:
                falsch.append(f"{key}: dritter Teil ist keine Zahl")
                continue
            # Genau so baut override_keys() den Schlüssel.
            erwartet = override_keys(teile[0], teile[1], km)[0]
            if key != erwartet:
                falsch.append(f"{key}: müsste {erwartet!r} heißen")
    check("alle Schlüssel in der Form, die find_override sucht", falsch, [])

    # Allgemeiner und distanzgenauer Eintrag liegen ÜBEREINANDER - der
    # allgemeine (z. B. veranstalter_url für alle Strecken) darf nicht
    # unsichtbar werden, nur weil EINE Strecke einen eigenen Eintrag hat.
    # Sechs Veranstalter-Links aus der Linkprüfung griffen genau deshalb
    # nie (Taubertal 100, Steverlauf, ...), siehe find_override().
    from scraper_lib import find_override

    ov = {
        "_readme": "…",
        "Testlauf|2026-10-03": {"veranstalter_url": "https://testlauf.de/", "art2": "Straße"},
        "Testlauf|2026-10-03|21": {"wettbewerb": "Halbmarathon", "art2": "Trail"},
    }
    beides = find_override(ov, "Testlauf", "2026-10-03", 21.0)
    check("allgemeiner Eintrag scheint durch den distanzgenauen durch",
          beides.get("veranstalter_url"), "https://testlauf.de/")
    check("distanzgenauer Eintrag bringt seine Felder mit", beides.get("wettbewerb"), "Halbmarathon")
    check("bei Widerspruch gewinnt der distanzgenaue Eintrag", beides.get("art2"), "Trail")
    nur_allgemein = find_override(ov, "Testlauf", "2026-10-03", 10.0)
    check("andere Strecke bekommt nur den allgemeinen Eintrag",
          nur_allgemein, {"veranstalter_url": "https://testlauf.de/", "art2": "Straße"})
    check("kein Eintrag -> None", find_override(ov, "Anderer Lauf", "2026-10-03", 10.0), None)
    check("die Datei selbst bleibt unverändert", "wettbewerb" in ov["Testlauf|2026-10-03"], False)


def test_suche_uebersetzungen() -> None:
    """Die Mastersuche sucht in BEIDEN Sprachen - und zwar an zwei Stellen.

    „Germany" muss auch auf der deutschen Seite alle Events in
    Deutschland finden (so vom Nutzer gewünscht). Dafür durchsucht
    `sucheHeuhaufen()` in filters.js die Übersetzungen von Land,
    Sportart, Kategorie und Ort mit. Dieselbe Regel steht ein zweites Mal
    in functions/index.js, damit ein ABO genau das trifft, was die Suche
    gezeigt hat - sonst kämen E-Mails über Events, die man nie gesehen
    hat, oder gar keine.

    Dieser Test vergleicht die beiden Listen Wert für Wert. Läuft eine
    weg, fällt es hier auf und nicht erst beim Empfänger.
    """
    import json as _json
    import re as _re
    import shutil
    import subprocess

    print("\nÜbersetzungen für die Mastersuche (filters.js == functions/index.js):")
    node = shutil.which("node")
    if not node:
        print("  – übersprungen: node nicht gefunden")
        return
    wurzel = Path(__file__).resolve().parent.parent

    # filters.js lässt sich in node laden: Die Datei hängt ihr Objekt an
    # `window` ODER `globalThis` (siehe letzte Zeile dort).
    skript = (f"require({_json.dumps(str(wurzel / 'filters.js'))});"
              "const T = globalThis.EnduranceFilters.VALUE_TRANSLATIONS;"
              "const raus = {};"
              "['land','art1','art2','standort'].forEach(f => {"
              "  raus[f] = {};"
              "  Object.keys(T[f] || {}).forEach(k => { raus[f][k] = [T[f][k].de, T[f][k].en]; });"
              "});"
              "console.log(JSON.stringify(raus));")
    ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    if ergebnis.returncode != 0:
        check("filters.js ließ sich laden", ergebnis.stderr.strip()[:200], "")
        return
    aus_filters = _json.loads(ergebnis.stdout)

    # Und die Kopie in der Cloud Function.
    fn = (wurzel / "functions" / "index.js").read_text(encoding="utf-8")
    start = fn.index("const SUCH_UEBERSETZUNGEN")
    ende = fn.index("\n};", start) + 3
    skript2 = (fn[start:ende].replace("const SUCH_UEBERSETZUNGEN", "const S")
               + "console.log(JSON.stringify(S));")
    ergebnis2 = subprocess.run([node, "-e", skript2], capture_output=True, text=True)
    if ergebnis2.returncode != 0:
        check("functions/index.js ließ sich lesen", ergebnis2.stderr.strip()[:200], "")
        return
    aus_function = _json.loads(ergebnis2.stdout)

    for feld in ("land", "art1", "art2", "standort"):
        check(f"{feld}: dieselben Schlüssel",
              sorted(aus_filters.get(feld, {})), sorted(aus_function.get(feld, {})))
        abweichend = sorted(k for k in aus_filters.get(feld, {})
                            if aus_filters[feld][k] != aus_function.get(feld, {}).get(k))
        check(f"{feld}: dieselben Übersetzungen", abweichend, [])

    # Und die Suche selbst: ein deutsches Event muss auf englische
    # Eingaben antworten und umgekehrt.
    probe = _json.dumps({"name": "Marathon München by Brooks", "wettbewerb": "42,2 km",
                         "standort": "München", "land": "Deutschland",
                         "art1": "Laufen", "art2": "Straße"}, ensure_ascii=False)
    skript3 = (f"require({_json.dumps(str(wurzel / 'filters.js'))});"
               "const EF = globalThis.EnduranceFilters;"
               f"const e = {probe};"
               "const st = EF.createState(); const raus = {};"
               "['germany','munich','münchen','running','road','zzznix'].forEach(q => {"
               "  st.suche = q; raus[q] = EF.matchEvent(st, e); });"
               "console.log(JSON.stringify(raus));")
    ergebnis3 = subprocess.run([node, "-e", skript3], capture_output=True, text=True)
    treffer = _json.loads(ergebnis3.stdout) if ergebnis3.returncode == 0 else {}
    check("englische Eingaben treffen deutsche Daten",
          [treffer.get(q) for q in ("germany", "munich", "running", "road")],
          [True, True, True, True])
    check("deutsche Eingaben treffen weiterhin", treffer.get("münchen"), True)
    check("ein Unsinnswort trifft nicht", treffer.get("zzznix"), False)


def test_keine_fremden_dateien() -> None:
    """Keine Skripte und Stylesheets von fremden Servern.

    Leaflet, markercluster und die Firebase-SDKs liegen in `vendor/`.
    Ein CDN-Abruf überträgt die IP-Adresse jedes Besuchers an Dritte -
    bei JEDEM Aufruf, auch wenn niemand sich anmeldet. Rutscht wieder
    ein CDN-Verweis in eine Seite, fällt es hier auf, nicht erst in der
    Datenschutzerklärung.

    Die OpenStreetMap-Kacheln sind die eine bewusste Ausnahme: Eine
    Karte ohne Kartenbilder gibt es nicht. Sie stehen deshalb in der
    Datenschutzerklärung (und nur die Kartenseite lädt sie).
    """
    import re as _re

    wurzel = Path(__file__).resolve().parent.parent
    print("\nKeine fremden Dateien (Selbst-Hosten):")
    erlaubt = ("tile.openstreetmap.org", "www.openstreetmap.org")
    for name in SEITEN:
        quelle = (wurzel / name).read_text(encoding="utf-8")
        # Kommentare weg, sonst zählt die Begründung als Treffer.
        ohne = _re.sub(r"<!--.*?-->", "", quelle, flags=_re.S)
        # Nur GELADENE Dateien zählen: src an beliebigen Tags und href
        # an <link>. Ein <a href> auf geonames.org ist ein Link, den
        # jemand anklicken KANN - dabei werden keine Daten übertragen,
        # solange niemand klickt. (Genau daran ist diese Prüfung beim
        # ersten Versuch gescheitert: die GeoNames-Namensnennung in der
        # Fußzeile galt als Treffer.)
        treffer = [u for u in _re.findall(r'\ssrc="(https?://[^"]+)"', ohne)
                   + _re.findall(r'<link\b[^>]*\shref="(https?://[^"]+)"', ohne)
                   if not any(ok in u for ok in erlaubt)]
        check(f"{name} lädt nichts von fremden Servern", treffer, [])
    for name in ("auth.js", "filters.js", "filter-ui.js", "event-detail.js"):
        quelle = (wurzel / name).read_text(encoding="utf-8")
        ohne = _re.sub(r"//[^\n]*", "", quelle)
        treffer = [u for u in _re.findall(r"['\"](https?://[^'\"]+\.js)['\"]", ohne)
                   if not any(ok in u for ok in erlaubt)]
        check(f"{name} lädt kein fremdes Skript nach", treffer, [])
    # Und die Dateien, auf die verwiesen wird, müssen wirklich da sein.
    fehlend = []
    for name in SEITEN:
        quelle = (wurzel / name).read_text(encoding="utf-8")
        ohne = _re.sub(r"<!--.*?-->", "", quelle, flags=_re.S)
        for pfad in _re.findall(r'(?:src|href)="(vendor/[^"?]+)"', ohne):
            if not (wurzel / pfad).exists():
                fehlend.append(f"{name} -> {pfad}")
    check("alle vendor-Dateien liegen im Repo", fehlend, [])


def test_laender_maske() -> None:
    """laender.json - die Umrisse für die graue Maske auf karte.html.

    Der Prüfstein sind die SCHLÜSSEL: Sie müssen genau die Länder heißen,
    die filters.js in LAENDER führt (und events.json im Feld `land`).
    Wird dort eines umbenannt oder ergänzt, ohne die Maske neu zu bauen,
    liegt das Land stillschweigend unter dem grauen Schleier - sichtbar
    nur, wenn man genau hinschaut.
    """
    import json as _json
    import re as _re

    print("\nLändermaske (build_laender):")
    wurzel = Path(__file__).resolve().parent.parent
    pfad = wurzel / "laender.json"
    check("laender.json liegt im Repo", pfad.exists(), True)
    if not pfad.exists():
        print("  -> python3 scripts/build_laender.py ausführen")
        return
    daten = _json.loads(pfad.read_text(encoding="utf-8"))
    laender = daten.get("laender") or {}

    # Die Namen aus filters.js (LAENDER = [...]) - dieselbe Quelle, aus
    # der die Filterliste entsteht.
    quelle = (wurzel / "filters.js").read_text(encoding="utf-8")
    treffer = _re.search(r"const LAENDER = \[([^\]]*)\]", quelle)
    aus_filters = _re.findall(r"'([^']+)'", treffer.group(1)) if treffer else []
    check("dieselben Länder wie in filters.js",
          sorted(laender), sorted(aus_filters))

    # Jeder Ring ist eine Fläche: mindestens vier Punkte und geschlossen.
    offen = [name for name, ringe in laender.items()
             for ring in ringe if len(ring) < 4 or ring[0] != ring[-1]]
    check("alle Ringe sind geschlossene Flächen", offen, [])

    # Die Koordinaten stehen als [lon, lat] (GeoJSON-Reihenfolge) - karte.html
    # dreht sie für Leaflet. Verdrehte Werte fielen sonst erst am Bild auf.
    verdreht = []
    for name, ringe in laender.items():
        for ring in ringe:
            for lon, lat in ring[:50]:
                if not (-30 <= lon <= 60 and 35 <= lat <= 72):
                    verdreht.append((name, lon, lat))
                    break
    check("Koordinaten liegen in Europa und in der Reihenfolge lon, lat",
          verdreht[:3], [])

    # Größe: Die Datei lädt die Karte bei jedem Aufruf nach. 200 KB wären
    # keine Maske mehr, sondern ein zweites events.json.
    kb = pfad.stat().st_size // 1024
    check("laender.json bleibt klein (%d KB)" % kb, kb < 200, True)


def test_web_data() -> None:
    """Die kompakte Datenfassung (scripts/build_web_data.py → events.web.json)
    muss verlustfrei sein - in Python UND mit dem echten Dekodierer aus
    filters.js (node). Ein Format, das beim Rückweg etwas verliert, fiele
    sonst erst im Browser auf, und dort still: eine fehlende Distanz ist
    nur eine leere Zelle."""
    import json as _json
    import shutil
    import subprocess

    from build_web_data import FORMAT, dekodieren, kodieren

    print("\nKompakte Datenfassung (build_web_data + EF.decodeWebData):")
    # Feld fehlt (Index -1) ist etwas anderes als Feld = null.
    faelle = [
        {"name": "A", "laenge_km": 10.0, "dauer_h": None, "charity": True},
        {"name": "B", "laenge_km": 10.0},
        {"name": "A", "wettbewerb": "10 km", "lat": 48.1, "lon": 11.5},
    ]
    kodiert = kodieren(faelle, stand="2026-09-22")
    check("Format", kodiert["format"], FORMAT)
    check("Wörterbuch fasst gleiche Werte zusammen", kodiert["werte"]["name"], ["A", "B"])
    check("fehlendes Feld ist -1", kodiert["zeilen"]["charity"], [0, -1, -1])
    check("null bleibt ein Wert", kodiert["werte"]["dauer_h"], [None])
    check("Rückweg in Python", dekodieren(kodiert), faelle)

    wurzel = Path(__file__).resolve().parent.parent
    events = _json.loads((wurzel / "events.json").read_text(encoding="utf-8"))
    daten = kodieren(events, stand="2026-09-22")
    check("Rückweg über den ganzen Bestand (Python)", dekodieren(daten) == events, True)
    roh = len(_json.dumps(events, ensure_ascii=False, separators=(",", ":")))
    kompakt = len(_json.dumps(daten, ensure_ascii=False, separators=(",", ":")))
    check("kompakte Fassung ist kleiner als events.json ohne Einrückung", kompakt < roh, True)

    node = shutil.which("node")
    if not node:
        print("  (node fehlt - Dekodierer aus filters.js nicht geprüft)")
        return
    tmp = wurzel / "scripts" / ".web_data_test.json"
    tmp.write_text(_json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    try:
        skript = (
            "global.window = global;"
            f"require({_json.dumps(str(wurzel / 'filters.js'))});"
            f"const d = JSON.parse(require('fs').readFileSync({_json.dumps(str(tmp))}, 'utf8'));"
            "process.stdout.write(JSON.stringify(global.EnduranceFilters.decodeWebData(d)));"
        )
        ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    finally:
        tmp.unlink(missing_ok=True)
    if ergebnis.returncode != 0:
        check("filters.js dekodiert in node", ergebnis.stderr.strip()[:300], "")
        return
    zurueck = _json.loads(ergebnis.stdout)
    check("Rückweg mit EF.decodeWebData (node) über den ganzen Bestand", zurueck == events, True)
    print("  ✓ %d Events, %d KB → %d KB (ohne gzip)" % (len(events), roh // 1024, kompakt // 1024))


def test_asset_stempel() -> None:
    """Die ?v=-Stempel an den geteilten Skripten (stamp_assets.py).

    GitHub Pages liefert jede Datei mit max-age=600. Ohne Stempel kann ein
    Browser die neue events.html mit einer zehn Minuten alten filters.js
    kombinieren - dann fehlt eine Funktion, das Inline-Skript bricht in
    seiner ersten Zeile ab und die Seite bleibt LEER. Genau das ist
    einmal passiert. Der Stempel folgt dem Inhalt, dieser Test merkt
    also, wenn ein Modul geändert und der Stempel vergessen wurde.
    """
    from stamp_assets import ASSETS, pruefe, stempel_aller_assets

    print("\nStempel der geteilten Dateien (stamp_assets.py):")
    werte = stempel_aller_assets()
    check("alle geteilten Dateien vorhanden", sorted(werte), sorted(ASSETS))
    probleme = pruefe()
    check("Stempel passen zum Inhalt der Dateien", probleme, [])
    if probleme:
        print("  -> python3 scripts/stamp_assets.py ausführen")


def test_farbschema_skript() -> None:
    """Hell und Dunkel: das Skript im <head>, das `data-theme` setzt, steht
    in allen drei Seiten WORTGLEICH.

    Es muss im Kopf jeder Seite stehen (sonst blitzt die Seite im falschen
    Schema auf), und es ist deshalb dreimal kopiert statt als Datei
    eingebunden. Drei Kopien laufen auseinander, wenn niemand hinsieht -
    dieser Test sieht hin. Dazu: der Knopf in jeder Kopfzeile und site.css
    mit beiden Schemata über `data-theme` (nicht über
    prefers-color-scheme - dann hätte der Knopf keine Wirkung).
    """
    import os
    import re

    print("\nFarbschema-Skript (hell/dunkel) in den Seiten:")
    wurzel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    fassungen: dict[str, str | None] = {}
    for name in ("index.html", "events.html", "karte.html"):
        with open(os.path.join(wurzel, name), encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"<script>\n\(function \(\) \{\n  var wahl = null;.*?</script>", html, re.S)
        fassungen[name] = m.group(0) if m else None
        check(f"{name}: Skript im Kopf vorhanden", m is not None, True)
        check(f"{name}: Knopf .theme-btn in der Kopfzeile", 'class="icon-btn theme-btn"' in html, True)
        check(f"{name}: Skript steht VOR den Stylesheets",
              m is not None and m.start() < html.index("<link rel=\"stylesheet\""), True)
    check("alle drei Kopien sind wortgleich", len(set(v for v in fassungen.values() if v)), 1)
    with open(os.path.join(wurzel, "site.css"), encoding="utf-8") as f:
        css = f.read()
    check("site.css: helles Schema über :root[data-theme=\"light\"]", ':root[data-theme="light"]' in css, True)
    check("site.css: kein prefers-color-scheme", "prefers-color-scheme" in css, False)


def test_lauf_im_triathlonkalender() -> None:
    """Ein Lauf im Triathlon-Kalender bleibt ein Lauf.

    running.life führt im Triathlon-Kalender auch die Läufe der
    Triathlon-Veranstalter; der "O-SEE Ultra Trail" stand deshalb als
    Triathlon in der Liste - mit Kinderläufen unter 5 km, die der
    5-km-Regel entgingen (Nutzer 21.09.2026: "hat nichts mit Triathlon
    zu tun", und ein Triathlon kann keine Kategorie Trail haben).
    Die Regel greift NUR bei Triathlon als Voreinstellung und nie gegen
    ein Mehrsport-Stichwort.
    """
    from scraper_lib import SiteConfig, guess_art1
    print("\nLauf im Triathlon-Kalender (guess_art1):")
    tri = SiteConfig(base_url="", calendar_url="", default_art1="Triathlon")
    lauf = SiteConfig(base_url="", calendar_url="", default_art1="Laufen")
    rad = SiteConfig(base_url="", calendar_url="", default_art1="Fahrrad")
    check("O-SEE Ultra Trail im Triathlon-Kalender -> Laufen", guess_art1("O-SEE Ultra Trail", tri), "Laufen")
    check("Zittauer Gebirgslauf im Triathlon-Kalender -> Laufen", guess_art1("Zittauer Gebirgslauf", tri), "Laufen")
    check("XTERRA Germany bleibt Triathlon", guess_art1("XTERRA Germany", tri), "Triathlon")
    check("Cross Triathlon Trail Edition bleibt Triathlon", guess_art1("Cross Triathlon Trail Edition", tri), "Triathlon")
    check("Swimrun bleibt Triathlon", guess_art1("Rheinsberger SwimRun", tri), "Triathlon")
    check("Ohne Laufwort bleibt die Voreinstellung", guess_art1("O-SEE Challenge", tri), "Triathlon")
    check("Im Laufkalender wie bisher", guess_art1("O-SEE Ultra Trail", lauf), "Laufen")
    check("MTB Trail Marathon im Radkalender bleibt Fahrrad", guess_art1("MTB Trail Marathon", rad), "Fahrrad")


def test_fremde_sportart() -> None:
    """Ein Radrennen bei einer Laufveranstaltung ist ein Radrennen - eine
    Triathlon-Teilstrecke dagegen nicht.

    Die Unterscheidung kostet Mühe und ist genau die, an der die erste
    Fassung dieser Regel gescheitert ist: Sie hätte aus dem "21,5 km
    Radfahren" des Aluman (einem Triathlon) ein eigenständiges
    Radrennen gemacht. Erkennungszeichen ist die VERBFORM im Label -
    "Radfahren"/"Laufen"/"Run 1" beschreibt eine Etappe, "Rad 100 km"
    ein Rennen, das man einzeln bucht.
    """
    print("\nSportart aus dem Wettbewerbs-Label:")
    from clean_events import fix_fremde_sportart_im_wettbewerb

    def lauf(name, wb, km, art1="Laufen"):
        return {"name": name, "datum_start": "2026-09-19", "wettbewerb": wb,
                "laenge_km": km, "art1": art1, "art2": "Straße"}

    # Laufveranstaltung mit eigenem Radrennen (Drei Talsperren Marathon)
    talsperren = [lauf("Drei Talsperren Marathon", "Marathon", 42.2),
                  lauf("Drei Talsperren Marathon", "Halbmarathon", 21.1),
                  lauf("Drei Talsperren Marathon", "Rad 100 km", 100.0)]
    fix_fremde_sportart_im_wettbewerb(talsperren)
    check("'Rad 100 km' bei einem Marathon -> Fahrrad",
          [e["art1"] for e in talsperren], ["Laufen", "Laufen", "Fahrrad"])
    check("Fahrrad bekommt KEINE Laufen-Kategorie",
          talsperren[2]["art2"], None)

    # Triathlon: beide Zeilen sind Teilstrecken
    roemer = [lauf("RömerMan", "42 km Radfahren mit dem Rennrad", 42.0),
              lauf("RömerMan", "10 km Laufen durch das Grünprojekt", 10.0)]
    fix_fremde_sportart_im_wettbewerb(roemer)
    check("Triathlon-Teilstrecke bleibt unangetastet",
          [e["art1"] for e in roemer], ["Laufen", "Laufen"])

    # Eine einzelne Zeile, die schon als Triathlon geführt wird
    tri = [lauf("Lauchringer Triathlon-Nacht", "ca. 18,6 km Radfahren", 18.6,
                art1="Triathlon")]
    fix_fremde_sportart_im_wettbewerb(tri)
    check("art1 'Triathlon' wird nie überschrieben", tri[0]["art1"], "Triathlon")

    # "Mountainbike" darf nicht über \bbike\b als Teilstrecke gelten
    apfel = [lauf("Frickinger Apfellauf", "Lauf", 10.0),
             lauf("Frickinger Apfellauf", "Mountainbike", 20.0)]
    fix_fremde_sportart_im_wettbewerb(apfel)
    check("'Mountainbike' neben 'Lauf' -> Fahrrad",
          [e["art1"] for e in apfel], ["Laufen", "Fahrrad"])

    # Der Name allein reicht nicht - "Rad" steckt in vielen Laufnamen
    radweg = [lauf("Lauf am Radweg", None, 10.0)]
    fix_fremde_sportart_im_wettbewerb(radweg)
    check("'Rad' im NAMEN ändert nichts", radweg[0]["art1"], "Laufen")


def test_zwei_rennen_in_einer_zeile() -> None:
    """"15 km / 21 km Crosslauf" sind zwei Rennen, nicht eines über 21 km.

    Vor diesem Fix nahm guess_distance_km() die größere Zahl - der
    15-km-Lauf des Limberglaufs Ranis fehlte dadurch komplett in der
    Liste. Ein fehlendes Event ist die unangenehmere Sorte Fehler: eine
    falsche Zahl sieht man, eine fehlende Zeile nicht.
    """
    print("\nZwei Rennen in einer Zeile:")
    from scraper_lib import parse_competitions, SiteConfig
    config = SiteConfig(base_url="", calendar_url="")

    geteilt = parse_competitions(["15 km / 21 km Crosslauf (ab Jahrgang 2008)"], config)
    check("wird in zwei Wettbewerbe geteilt",
          sorted(k.laenge_km for k in geteilt), [15.0, 21.0])
    check("der Zusatz gehört beiden",
          all("Crosslauf" in (k.label or "") for k in geteilt), True)

    # Aufteilungen DERSELBEN Strecke bleiben ein Wettbewerb
    for text, erwartet in (("19 km (14 + 5 km)", [19.0]),
                           ("100 km (10 x 10 km)", [100.0]),
                           ("42,195 km Marathon (Rundkurs 8,33 km, fünfmal)", [42.2]),
                           ("46,5 km, 3 Runden je 15,5 km", [46.5])):
        check(f"{text!r} bleibt ein Wettbewerb",
              [k.laenge_km for k in parse_competitions([text], config)], erwartet)


def test_koordinaten_widerspruch() -> None:
    """Dieselbe Veranstaltung darf nicht an zwei Orten liegen.

    Der Bodensee Marathon stand mit seiner Marathon-Strecke auf
    49.07/10.14 - das ist Franken, 168 km vom Bodensee. Ursache war der
    abgeschnittene Ortsname "Kressbronn" statt "Kressbronn am Bodensee".
    Für die Umkreissuche und die Karte ist das kein Schönheitsfehler:
    Wer im Umkreis von Friedrichshafen sucht, sah den Marathon nicht.
    """
    print("\nWidersprüchliche Koordinaten:")
    from clean_events import report_widerspruechliche_koordinaten

    falsch = [
        {"name": "Bodensee Marathon", "datum_start": "2026-09-19",
         "standort": "Kressbronn", "lat": 49.0656, "lon": 10.1379},
        {"name": "Bodensee Marathon", "datum_start": "2026-09-19",
         "standort": "Kressbronn am Bodensee", "lat": 47.5969, "lon": 9.5982},
    ]
    check("168 km auseinander wird gemeldet",
          len(report_widerspruechliche_koordinaten(falsch)), 1)

    # Nachbarorte derselben Veranstaltung sind normal (Start/Ziel getrennt)
    nah = [
        {"name": "Drei Talsperren Marathon", "datum_start": "2026-09-19",
         "standort": "Eibenstock", "lat": 50.4727, "lon": 12.6115},
        {"name": "Drei Talsperren Marathon", "datum_start": "2026-09-19",
         "standort": "Eibenstock", "lat": 50.4950, "lon": 12.5996},
    ]
    check("3 km auseinander ist kein Fall",
          report_widerspruechliche_koordinaten(nah), [])


def test_override_koordinaten() -> None:
    """Ein Override muss auch lat/lon setzen können - und beide Wege
    (Einsammeln und rückwirkendes Aufräumen) müssen dieselben Felder
    kennen. Zwei getrennte Listen wären ein Fehler, der sich erst Wochen
    später zeigt: Das Feld wirkt je nach Weg oder nicht."""
    print("\nOverride-Felder:")
    from scraper_lib import OVERRIDE_FIELDS
    import clean_events
    import inspect

    check("lat und lon sind erlaubte Override-Felder",
          {"lat", "lon"} <= set(OVERRIDE_FIELDS), True)
    quelle = inspect.getsource(clean_events.apply_overrides)
    check("apply_overrides nutzt die gemeinsame Liste",
          "OVERRIDE_FIELDS" in quelle, True)

    events = [{"name": "Bodensee Marathon", "datum_start": "2026-09-19",
               "laenge_km": 42.2, "standort": "Kressbronn",
               "lat": 49.0656, "lon": 10.1379}]
    behalten, _, geaendert = clean_events.apply_overrides(events)
    check("die Koordinaten werden wirklich verschoben",
          round(behalten[0]["lat"], 3), 47.597)
    check("und die Änderung wird berichtet",
          any("lat" in zeile for zeile in geaendert), True)


def test_zwei_sportarten_im_namen() -> None:
    """"Swim&Run" und "Bike+Run" sind Mehrsport - "Decathlon" ist ein Laden.

    Das Trennzeichen war die Lücke: `swim ?run` erlaubte nur ein
    optionales LEERZEICHEN, und damit blieben elf Veranstaltungen
    Laufveranstaltungen, die keine sind ("Wunnebad Swim&Run", "DSW
    Swim & Run", "Kronberger Bike+Run", "Run and Bike Berlin").

    Die Gegenprobe ist der wichtigere Teil dieses Tests: "athlon" als
    Stichwort wäre naheliegend gewesen und hätte die "Decathlon Hybrid
    Series" (den Sporthändler), den "Weinathlon" und den "Eschathlon
    Halbmarathon" zu Triathlons gemacht - alles Wortspiele auf einen
    Laufnamen.
    """
    print("\nZwei Sportarten im Namen:")
    from scraper_lib import guess_art1, guess_art2, SiteConfig
    config = SiteConfig(base_url="", calendar_url="")

    for name, art2 in (("Wunnebad Swim&Run", "Swimrun"),
                       ("DSW Swim & Run", "Swimrun"),
                       ("Swim+Run Winnweiler", "Swimrun"),
                       ("Run and Bike Berlin", "Duathlon"),
                       ("Kronberger Bike+Run", "Duathlon")):
        gefunden = guess_art1(name, config)
        check(f"{name!r} ist Mehrsport", gefunden, "Triathlon")
        check(f"{name!r} bekommt die Kategorie {art2}",
              guess_art2(name, config, gefunden), art2)

    # Gegenprobe: Laufveranstaltungen, die nur so KLINGEN
    for name in ("Decathlon Hybrid Series - Plochingen", "Weinathlon",
                 "Eschathlon Halbmarathon", "Rundlauf am Bikepark",
                 "24. Bordesholmer Seelauf SEE +RUN", "Sunrun Berlin"):
        check(f"{name!r} bleibt ein Lauf", guess_art1(name, config), "Laufen")


def test_stundenlauf() -> None:
    """Ein „Stundenlauf" ist eine Stunde - ein „Halbstundenlauf" eine halbe.

    Das Muster für Zeitrennen verlangte eine ZAHL vor dem Wort, und der
    klassische Ein-Stunden-Lauf heißt einfach „Stundenlauf". 13
    Veranstaltungen standen deshalb ganz ohne Maßzahl in der Liste
    („LCM Stundenlauf", „Warburger Stundenlauf", „Stundenlauf mit
    Musik"). Gefunden bei der Einzelprüfung der ersten 400 Events, die
    Definition gegen Wikipedia/Brockhaus geprüft.

    Die Falle steckt im Wort: „Halb·stundenlauf" enthält „stundenlauf"
    als Teilzeichenkette. Ohne die Sonderzeile davor wäre er doppelt so
    lang wie in Wirklichkeit - deshalb steht sie ZUERST, und dieser Test
    hält die Reihenfolge fest.
    """
    print("\nStundenlauf:")
    from scraper_lib import parse_duration_h

    for text, erwartet in (
            ("LCM Stundenlauf", 1.0),
            ("50. LCM Stundenlauf", 1.0),
            ("Stundenlaufserie - Halle (Saale)", 1.0),
            ("Zwickauer Halb- und Stundenlauf", 1.0),
            ("Halbstundenlauf des TSV Zeulenroda", 0.5),
            # Mit Zahl greift weiterhin das allgemeine Muster.
            ("15. Bokeler 6 Stundenlauf", 6.0),
            ("24-Stunden-Lauf", 24.0),
            ("12h Lauf", 12.0),
            # Gegenproben: kein Zeitrennen.
            ("Halbmarathon", None),
            ("Stundenplan der Wettkämpfe", None),
            ("Zeitlimit 6 Stunden", None)):
        check(f"{text!r} -> {erwartet!r}", parse_duration_h(text), erwartet)


def test_audit_pruefungen() -> None:
    """Die Einzelprüfung meldet echte Fehler - und schweigt bei den
    Fällen, die sie früher fälschlich gemeldet hat.

    Der zweite Teil ist der wichtigere. Von den vier größten
    Fundgruppen der ersten Prüfung waren drei Fehler der REGEL und
    nicht der Daten (siehe CLAUDE.md). Jede dieser Korrekturen steht
    hier als Gegenprobe, damit sie nicht beim nächsten Umbau
    zurückrutscht.
    """
    print("\nEinzelprüfung (audit_events):")
    from audit_events import pruefe_event

    def kategorien(**felder):
        basis = {"name": "Testlauf", "datum_start": "2026-09-19",
                 "datum_ende": "2026-09-19", "standort": "Musterstadt",
                 "land": "Deutschland", "lat": 50.0, "lon": 10.0,
                 "art1": "Laufen", "art2": "Straße", "laenge_km": 10.0,
                 "wettbewerb": "10 km",
                 "veranstalter_url": "https://beispiel-lauf.de/"}
        basis.update(felder)
        return {k for k, _ in pruefe_event(basis)}

    # --- Fälle, die gemeldet werden MÜSSEN ---------------------------
    check("Kinderlauf mit 21,1 km wird gemeldet",
          "Kinderlauf-Label mit Erwachsenendistanz"
          in kategorien(wettbewerb="Kinderlauf", laenge_km=21.1), True)
    check("Label '9 km' bei 8,5 km wird gemeldet",
          "Zahl im Label weicht von laenge_km ab"
          in kategorien(wettbewerb="9 km", laenge_km=8.5), True)
    check("Jahreszahl 2025 an einem Termin 2026 wird gemeldet",
          "Jahreszahl im Namen passt nicht zum Datum"
          in kategorien(name="ONW-Lauf Dannenberg 2025"), True)
    check("Name in Großbuchstaben wird gemeldet",
          "Name komplett in Großbuchstaben"
          in kategorien(name="BFUTR EXTREME UNTERWEGS"), True)
    check("Portallink wird gemeldet",
          "Portallink statt offizieller Seite"
          in kategorien(veranstalter_url="https://my.raceresult.com/123/"), True)
    check("Koordinate außerhalb Deutschlands wird gemeldet",
          "Koordinaten passen nicht zum Land"
          in kategorien(lat=41.9, lon=12.5), True)

    check("ein Probe-Eintrag des Kalenders wird gemeldet",
          "Testeintrag der Quelle?"
          in kategorien(name="TESTVERANSTALTUNG Neujahrslauf"), True)
    # Der Basisname dieser Prüfungen ist „Testlauf" - und genau der darf
    # NICHT anschlagen: Ein Lauf kann so heißen. Gemeldet wird nur das
    # eindeutige „TESTVERANSTALTUNG" (gefunden am 02.01.2030, Dolgesheim).
    check("ein Lauf namens „Testlauf“ ist KEIN Fall",
          "Testeintrag der Quelle?" in kategorien(), False)
    check("und „Härtetest-Lauf“ auch nicht",
          "Testeintrag der Quelle?"
          in kategorien(name="12. Härtetest-Lauf Sauerland"), False)

    # --- Gegenproben: die drei Fehlalarme der ersten Fassung ----------
    check("ein Jugendlauf über 5,6 km ist KEIN Fall",
          "Kinderlauf-Label mit Erwachsenendistanz"
          in kategorien(wettbewerb="Jugendlauf, 5,6 km", laenge_km=5.6), False)
    check("'Bernburger Halbmarathon' mit 12-km-Label ist KEIN Fall",
          "„Halbmarathon\u201c, aber Distanz passt nicht"
          in kategorien(name="Bernburger Halbmarathon",
                        wettbewerb="12 km – ab Altersklasse U16",
                        laenge_km=12.0), False)
    check("'Winterlaufserie 2026/2027' ist KEIN Fall",
          "Jahreszahl im Namen passt nicht zum Datum"
          in kategorien(name="51. Winterlaufserie 2026/2027, 1. Wertungslauf"), False)
    check("ein Freitagslauf ist KEIN Fall",
          "Wochentag Mo-Do" in kategorien(datum_start="2026-09-18",
                                          datum_ende="2026-09-18"), False)
    check("'(L)auf zur Venus' ist KEIN unsauberer Name",
          "Name sieht unsauber aus" in kategorien(name="(L)auf zur Venus"), False)
    check("ein Hindernislauf mit 'Cross' im Namen ist KEIN Fall",
          "Trail/Cross im Namen, andere Kategorie"
          in kategorien(name="Family-CrossDeLuxe Leipzig", art2="Hindernis"), False)
    check("'3 Runden je 15,5 km' ist kein Label-Widerspruch",
          "Zahl im Label weicht von laenge_km ab"
          in kategorien(wettbewerb="46,5 km, 3 Runden je 15,5 km",
                        laenge_km=46.5), False)
    # --- Label, das seine Distanz selbst nennt -------------------------
    check("„Halbmarathon 22,8 km\u201c bei 22,8 km ist KEIN Fall (Trail-Rundkurs)",
          "„Halbmarathon\u201c, aber Distanz passt nicht"
          in kategorien(name="Dörenther Klippen UltraTrail",
                        wettbewerb="Halbmarathon 22,8 km und ca. 560 Hm",
                        laenge_km=22.8), False)
    check("„Halbmarathon\u201c ohne km-Angabe bei 23 km wird gemeldet",
          "„Halbmarathon\u201c, aber Distanz passt nicht"
          in kategorien(wettbewerb="Halbmarathon", laenge_km=23.0), True)

    # --- Rundenlänge gegen Staffel -------------------------------------
    # Die vierte Begegnung mit der Rundenlängen-Falle. Der Unterschied
    # zur Staffel ist der ganze Aufwand: Bei „2x5 km Staffel" läuft man
    # wirklich 5 km (eigener Wettbewerb), bei „4 Runden à 5,27 km"
    # läuft dieselbe Person alle vier.
    check("„4 Runden à ca. 5,27 km\u201c bei 5,3 km wird gemeldet",
          "Rundenlänge statt Renndistanz"
          in kategorien(wettbewerb="Halbmarathon (4 Runden à ca. 5,27 km)",
                        laenge_km=5.3), True)
    check("eine STAFFEL wird nicht gemeldet („2x5 km Staffel\u201c bei 5 km)",
          "Rundenlänge statt Renndistanz"
          in kategorien(wettbewerb="2x5 km Staffel", laenge_km=5.0), False)
    check("ein DUO wird nicht gemeldet",
          "Rundenlänge statt Renndistanz"
          in kategorien(wettbewerb="DUO Marathon 2 x 21,1 km", laenge_km=21.1), False)
    check("stimmt die Summe, ist es kein Fall („3 Runden je 15,5 km\u201c bei 46,5)",
          "Rundenlänge statt Renndistanz"
          in kategorien(wettbewerb="46,5 km, 3 Runden je 15,5 km", laenge_km=46.5), False)

    check("eine saubere Zeile meldet gar nichts", kategorien(), set())


def test_such_vorschlaege() -> None:
    """„Iron" muss „Ironman" anbieten - und nichts Sinnloses.

    Die Vorschläge entstehen AUS DEN DATEN (`EF.buildSuggestions`), nicht
    aus einer gepflegten Markenliste: Eine Liste im Code würde veralten,
    sobald eine Serie dazukommt, und beim großen Datenlauf kommen 16.000
    Events dazu.

    Die Gegenproben sind hier das Eigentliche. Beim Bauen dieser Funktion
    standen in der Liste: „Wings for Life -" (ein Bindestrich als Wort),
    „2026" und „Silvesterlauf 2026" (Jahreszahlen), „München" doppelt
    (einmal als Ort, einmal aus den Namen) und drei Schreibweisen von
    „UltraTrail". Jede dieser Schwächen steht unten als Test.
    """
    print("\nVorschläge der Mastersuche:")
    import json, shutil, subprocess
    node = shutil.which("node")
    if not node:
        print("  (node nicht vorhanden - übersprungen)")
        return
    wurzel = Path(__file__).resolve().parent.parent
    skript = f"""
      global.window = global;
      require({str(wurzel / 'filters.js')!r});
      const EF = global.EnduranceFilters;
      const mach = (name, ort, tag) => ({{ name, standort: ort, datum_start: tag }});
      const daten = [
        mach('Ironman Frankfurt', 'Frankfurt', '2027-06-27'),
        mach('Ironman Hamburg', 'Hamburg', '2027-06-06'),
        mach('Ironman 70.3 Erkner', 'Erkner', '2027-09-12'),
        mach('Ironman 70.3 Leipzig', 'Leipzig', '2027-08-08'),
        // Serie, die NICHT am Namensanfang steht
        mach('Kulmbach Spartan Trifecta Weekend', 'Kulmbach', '2027-06-11'),
        mach('Spartan Berlin', 'Berlin', '2027-05-01'),
        mach('Spartan Muenchen', 'Muenchen', '2027-05-02'),
        // Serie mit Bindestrich-Ort dahinter
        mach('Wings for Life - Frankfurt am Main', 'Frankfurt', '2027-05-09'),
        mach('Wings for Life - Gangelt', 'Gangelt', '2027-05-09'),
        mach('Wings for Life - Bamberg', 'Bamberg', '2027-05-09'),
        // Jahreszahlen im Namen
        mach('Silvesterlauf 2026 Nord', 'Kiel', '2026-12-31'),
        mach('Silvesterlauf 2026 Sued', 'Ulm', '2026-12-31'),
        mach('Silvesterlauf 2026 West', 'Aachen', '2026-12-31'),
        // Schreibvarianten
        mach('Grosser UltraTrail', 'Bonn', '2027-07-01'),
        mach('Kleiner Ultratrail', 'Bonn', '2027-07-02'),
        mach('Dritter ULTRATRAIL', 'Bonn', '2027-07-03')
      ];
      const idx = EF.buildSuggestions(daten);
      const texte = idx.map(v => v.text);
      const treffer = (q) => EF.matchSuggestions(idx, q, 8).map(v => v.text + ':' + v.anzahl);
      console.log(JSON.stringify({{
        iron: treffer('iron'),
        sparta: treffer('sparta'),
        wings: treffer('wings'),
        silv: treffer('silvest'),
        ultra: treffer('ultratr'),
        bonn: treffer('bon'),
        mitBindestrich: texte.filter(t => t.trim().endsWith('-')),
        mitJahr: texte.filter(t => /\\b20\\d\\d/.test(t)),
        // Die Vier-Zeichen-Regel gilt nur für SERIEN. Ein Ort darf
        // kurz sein - "Ulm" hat drei Buchstaben und muss vorkommen.
        kurzeSerie: idx.filter(v => v.art === 'serie' && v.text.length < 4).map(v => v.text),
        kurzerOrt: idx.filter(v => v.art === 'ort' && v.text === 'Ulm').length
      }}));
    """
    ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    if ergebnis.returncode != 0:
        check("node konnte filters.js laden", ergebnis.stderr.strip()[-200:], "")
        return
    d = json.loads(ergebnis.stdout)

    check("„iron\u201c schlägt „Ironman\u201c vor (4 Veranstaltungen)",
          "Ironman:4" in d["iron"], True)
    # Der Kernfall: eine Serie, die MITTEN im Namen steht.
    check("„sparta\u201c schlägt „Spartan\u201c vor, auch wenn der Name "
          "mit dem Ort beginnt", "Spartan:3" in d["sparta"], True)
    check("„wings\u201c schlägt „Wings for Life\u201c vor (3)",
          "Wings for Life:3" in d["wings"], True)
    # Der längere Begriff verdrängt den kürzeren bei gleicher Trefferzahl.
    check("„Wings\u201c allein steht NICHT daneben",
          any(x.startswith("Wings:") for x in d["wings"]), False)

    # --- Gegenproben ---------------------------------------------------
    check("kein Vorschlag endet auf einem Bindestrich", d["mitBindestrich"], [])
    check("keine Jahreszahl in einem Vorschlag", d["mitJahr"], [])
    check("keine Serie aus einem Wort unter vier Zeichen", d["kurzeSerie"], [])
    check("ein kurzer ORTSNAME bleibt trotzdem („Ulm\u201c)", d["kurzerOrt"], 1)
    check("„silvest\u201c findet die Serie ohne die Jahreszahl",
          "Silvesterlauf:3" in d["silv"], True)
    check("Schreibvarianten sind EIN Vorschlag mit drei Treffern",
          [x for x in d["ultra"] if x.endswith(":3")] != [], True)
    check("ein Ort steht genau EINMAL in der Liste",
          len([x for x in d["bonn"] if x.startswith("Bonn:")]), 1)


def test_laufen_weiterleitung() -> None:
    """Die laufen.de-Detailseite leitet auf den Veranstalter weiter - und
    genau dieses Ziel ist der Veranstalter-Link (Entscheidungspunkt 15,
    vom Nutzer am 19.09.2026 freigegeben).

    Gegenproben: Ziele auf Anmeldeportalen (lanet3, raceresult, datasport,
    racepedia), sozialen Netzen, Kalenderportalen (PORTAL_DOMAINS) und
    innerhalb von laufen.de (www-Variante) sind KEIN Veranstalter-Link.
    """
    print("\nlaufen.de-Weiterleitung (veranstalter_link_aus_weiterleitung):")
    from laufkalender_scraper import veranstalter_link_aus_weiterleitung as vl
    detail = "https://laufen.de/laufkalender/details/26V09000621060001"
    check("Veranstalter-Host", vl(detail, "https://www.sv-molbergen-leichtathletik.de/"),
          "https://www.sv-molbergen-leichtathletik.de/")
    check("http ohne www", vl(detail, "http://www.svg-poenitz.de"), "http://www.svg-poenitz.de")
    check("Leerzeichen am Rand", vl(detail, "  https://www.taubertal100.de/ "), "https://www.taubertal100.de/")
    for ziel in ("https://lanet3.de/external/dlv/register/13425",
                 "https://my.raceresult.com/354931/",
                 "https://www.datasport.de/anmeldeservice/x",
                 "https://schwabacher-citylauf-2026.racepedia.de",
                 "https://www.facebook.com/events/123", "https://fb.me/e/abc",
                 "https://www.laufen.de/laufkalender/details/26V09000621060001",
                 "https://running.life/de/termine/x",
                 "/laufkalender/details/26V09000621060001",
                 "mailto:ch.olbrich@gmx.de", "", None):
        check(f"kein Veranstalter: {ziel!r}", vl(detail, ziel), None)

    # Der Abruf selbst: eine Weiterleitung setzt den Link und parst nichts,
    # eine echte Detailseite (200) läuft wie bisher durch parse_detail_page.
    import laufkalender_scraper as lk

    class _Resp:
        def __init__(self, status, headers=None, text=""):
            self.status_code, self.headers, self.text = status, headers or {}, text
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(str(self.status_code))

    class _Session:
        def __init__(self, antworten): self.antworten, self.aufrufe = antworten, []
        def get(self, url, timeout=20, allow_redirects=True):
            self.aufrufe.append((url, allow_redirects))
            return self.antworten[url]

    e1 = lk.Event(name="A", detail_url="https://laufen.de/laufkalender/details/1",
                  veranstalter_url="https://laufen.de/laufkalender/details/1")
    e2 = lk.Event(name="B", detail_url="https://laufen.de/laufkalender/details/2",
                  veranstalter_url="https://laufen.de/laufkalender/details/2")
    e3 = lk.Event(name="C", detail_url="https://laufen.de/laufkalender/details/3",
                  veranstalter_url="https://laufen.de/laufkalender/details/3")
    sess = _Session({
        e1.detail_url: _Resp(302, {"Location": "https://www.wellen-marathon.de"}),
        e2.detail_url: _Resp(302, {"Location": "https://lanet3.de/external/dlv/register/1"}),
        e3.detail_url: _Resp(200, text="<html><body></body></html>"),
    })
    out = lk.enrich_from_details(sess, [e1, e2, e3], delay=0, max_details=0)
    check("Weiterleitung setzt den Veranstalter-Link", out[0].veranstalter_url, "https://www.wellen-marathon.de")
    check("Portal-Ziel lässt den Portallink stehen", out[1].veranstalter_url, e2.detail_url)
    check("Detailseite ohne Weiterleitung bleibt unverändert", out[2].veranstalter_url, e3.detail_url)
    check("kein Event geht verloren", len(out), 3)
    check("ohne allow_redirects abgerufen", all(not ar for _, ar in sess.aufrufe), True)


def test_nicht_ausdauer() -> None:
    """HYROX gehört nicht in die Liste - ein Hindernislauf schon.

    HYROX ist achtmal ein Kilometer Laufen im Wechsel mit acht
    Kraftstationen; man kann sich dafür nicht als Läufer anmelden. Vom
    Nutzer am 18.09.2026 entschieden.

    Die Gegenprobe ist der wichtigere Teil: Ein Hindernislauf (Spartan,
    XLETIX, CrossDeLuxe, Muddy Angel) IST ein Laufformat und bleibt.
    Ein Stichwort wie „Fitness" oder „Hindernis" in NICHT_AUSDAUER
    hätte die alle mitgenommen.
    """
    print("\nKein Ausdauer-Format (NICHT_AUSDAUER):")
    from scraper_lib import ist_nicht_ausdauer
    from clean_events import drop_nicht_ausdauer

    for name in ("HYROX Karlsruhe", "Intersport HYROX Hamburg", "hyrox cologne",
                 "Gymrace Airport Weeze", "Decathlon Hybrid Series - Plochingen",
                 # Nachzügler, vom Nutzer am 21.09.2026 bestätigt
                 "Runworx", "Black Forest Team Battle",
                 # Gehen und Skilanglauf (Nutzer, 21.09.2026)
                 "Lusatian Race Walking", "Internationaler Kammlauf (Skilanglauf)",
                 "König-Ludwig-Langlauf", "Gehermeeting: Gehertag Naumburg",
                 # virtuelle Läufe (Nutzer, 21.09.2026)
                 "Virtueller Silvesterlauf", "Virtual Run Berlin"):
        check(f"{name!r} fliegt heraus", bool(ist_nicht_ausdauer(name)), True)
    for name in ("Kulmbach Spartan Trifecta Weekend", "XLETIX Challenge - Nürburgring",
                 "Family-CrossDeLuxe Leipzig", "Muddy Angel Run - Berlin",
                 "Tough Mudder Hamburg", "Fitnesslauf Bochum", "Hindernislauf Kiel",
                 "Decathlon Stadtlauf Plochingen", "Hybrid Trail Harz",
                 # Walking-Strecken bleiben (offene Frage an den Nutzer),
                 # "Langläufer" ist kein Langlauf, ein Bergläufer kein Geher.
                 "21. Trochtelfinger Nordic Walking Stöckles-Cup", "Ahmadiyya Charity Walk",
                 "5 km Walking", "Langläufer-Cup Oberstdorf", "Marathon der Bergläufer"):
        check(f"{name!r} bleibt", ist_nicht_ausdauer(name), None)
    # Der Ort zählt mit: Die XMAS-Challenge trug "virtuell" nur dort.
    from scraper_lib import nicht_ausdauer_text
    check("Ort 'virtuell' reicht",
          bool(ist_nicht_ausdauer(nicht_ausdauer_text("Blaues Land läuft – XMAS-Challenge",
                                                      "10 km", "virtuell"))), True)
    check("normaler Ort ändert nichts",
          ist_nicht_ausdauer(nicht_ausdauer_text("Stadtlauf", "10 km", "Murnau")), None)

    behalten, entfernt = drop_nicht_ausdauer([
        {"name": "HYROX Berlin", "datum_start": "2027-01-01"},
        {"name": "Spartan Berlin", "datum_start": "2027-01-01"},
        {"name": "XMAS-Challenge", "datum_start": "2027-01-01", "standort": "virtuell"},
    ])
    check("drop_nicht_ausdauer behält den Hindernislauf",
          [e["name"] for e in behalten], ["Spartan Berlin"])
    check("und meldet die Ausschlüsse mit Grund", len(entfernt), 2)


def test_datum_vorlaeufig() -> None:
    """Ein vorläufiger Termin (Kalenderprognose) trägt `datum_vorlaeufig`.

    Vom Nutzer am 21.09.2026 entschieden: Wo kein Tag veröffentlicht ist,
    zeigt die Liste nur "Juni 2027*" mit Fußnote. Das Feld kommt allein
    per Override (OVERRIDE_FIELDS), die Kalenderdatei sagt es im Titel,
    und ein Event ohne das Feld trägt es auch nicht als false in
    events.json (to_dict lässt None weg).
    """
    print("\nVorläufige Termine (datum_vorlaeufig):")
    from scraper_lib import OVERRIDE_FIELDS, Event
    import build_ics
    check("Override-Feld bekannt", "datum_vorlaeufig" in OVERRIDE_FIELDS, True)
    e = Event(name="Borkener Citylauf", datum_start="2027-06-07", datum_ende="2027-06-07",
              standort="Borken", laenge_km=10.0)
    check("ohne Markierung fehlt das Feld in events.json",
          "datum_vorlaeufig" in e.to_dict(), False)
    e.datum_vorlaeufig = True
    check("markiert steht es drin", e.to_dict().get("datum_vorlaeufig"), True)
    ics = build_ics.build_ics(e.to_dict(), "20260101T000000Z")
    check("Kalenderdatei nennt den vorläufigen Termin im Titel",
          "SUMMARY:Borkener Citylauf (Termin vorläufig)" in ics, True)
    check("und in der Beschreibung", "Termin noch nicht veröffentlicht" in ics, True)
    ics_ohne = build_ics.build_ics(Event(name="Stadtlauf", datum_start="2027-06-07",
                                         datum_ende="2027-06-07", standort="X").to_dict(),
                                   "20260101T000000Z")
    check("ein normaler Termin bleibt unverändert", "vorläufig" in ics_ohne, False)


def test_staffeln() -> None:
    """Erst einmal keine Staffeln (Nutzer, 21.09.2026).

    Zwei Stufen (siehe ist_staffel): Ein Label, das NUR die Staffel
    beschreibt, nimmt diese eine Zeile; ein Name, der eine
    Staffelveranstaltung nennt, nimmt alle Zeilen. Die Gegenproben sind
    der wichtigere Teil - alle am Bestand gezählt: ein Einzelrennen mit
    Staffel-Option bleibt, eine Laufserie namens "Winterstaffel" bleibt,
    ein Ort namens Staffelsee bleibt.
    """
    print("\nStaffeln (ist_staffel):")
    from scraper_lib import ist_staffel, filter_staffeln, Event
    from clean_events import drop_staffeln

    for name, wb in (("22. Einstein-Marathon", "ZEISS Marathon Staffel"),
                     ("Uni-Lauf Bamberg", "2x5 km Staffel, Wechsel an der Buger Spitze"),
                     ("Lübeck Marathon", "DUO Marathon 2 x 21,1 km"),
                     ("H/21 Halbmarathon Hannover", "H/21 for Two (Staffel)"),
                     ("Landkreislauf Schwandorf", "Läufer-Staffel (10 Läufer, Gesamtstrecke ca. 49,5 km)"),
                     ("Firmenstaffel Sachsen-Anhalt", "5er-Staffel (5 × 3 km = 15 km)"),
                     ("Ostsee Staffel Marathon", "5 km"),
                     ("40. Weezer Staffellauf", None),
                     ("Rasteder Ellernteichstaffellauf", None),
                     ("Stadtpark-Staffel-Marathon", "Marathon"),
                     ("Marathonstaffel Mörfelden", "Marathon"),
                     ("Staffel-Mix-Marathon", None),
                     ("Stralsunder Firmenstaffellauf", "12 km")):
        check(f"{name!r} / {wb!r} fällt", bool(ist_staffel(name, wb)), True)
    for name, wb in (("#ZeroHungerRun Bonn", "10 km Lauf und Staffel"),
                     ("Butterkuchenlauf", "12 km (Einzel oder Staffel)"),
                     ("GaPa Everesting-Festival", "Everesting Solo oder Staffel"),
                     ("Grünwalder Burglauf", "5 km Strecke, ebenfalls als Einzel- oder Duo-Staffel möglich"),
                     ("Inzeller Falkensteinlauf", "Halbmarathon 21,095 km, Einzel und Staffel"),
                     ("GVG-Winterstaffel Pulheim", "Halbmarathon"),
                     ("Meckenheimer Apfelstaffel", None),
                     ("4. Zülpicher Seepark Nikolauslauf mit Fun/Firmenstaffel", None),
                     ("Volks- und Staffeltriathlon TuS Wasserstraße", None),
                     ("Staffelsee Panoramalauf", "5 km"),
                     ("21. Obermain-Marathon Bad Staffelstein", "Sparkassen-Marathon"),
                     ("Rund um den Kellerskopf", "21 km Halbmarathon (2 x 10,5 km Runde)")):
        check(f"{name!r} / {wb!r} bleibt", ist_staffel(name, wb), None)

    zeilen = [Event(name="Lübeck Marathon", wettbewerb="Marathon", laenge_km=42.2),
              Event(name="Lübeck Marathon", wettbewerb="DUO Marathon 2 x 21,1 km", laenge_km=21.1)]
    behalten, n = filter_staffeln(zeilen)
    check("filter_staffeln nimmt nur die Staffel-Zeile", [e.wettbewerb for e in behalten], ["Marathon"])
    check("und zählt sie", n, 1)
    behalten, entfernt = drop_staffeln([
        {"name": "Weezer Staffellauf", "datum_start": "2027-01-01"},
        {"name": "Stadtlauf", "datum_start": "2027-01-01", "wettbewerb": "10 km"},
    ])
    check("drop_staffeln behält den Stadtlauf", [e["name"] for e in behalten], ["Stadtlauf"])
    check("und meldet den Ausschluss", len(entfernt), 1)


def test_serientermin_im_label() -> None:
    """Ein Serientermin, der MITTEN im Wettbewerbs-Label steht.

    Die Hammer Winterlaufserie hat drei Termine (31.01. = 10 km,
    14.02. = 15 km, 28.02. = Halbmarathon), und `expand_competitions()`
    hatte jede Distanz an jeden Termin gehängt - neun Zeilen statt drei.
    Zwei davon trugen ihren Termin im Label: „15,0 km (am 14.02.2027 für
    M/W ab 18 bis M/W85)". `_DATE_LABEL` sah das nicht, weil es ein Label
    verlangt, das MIT dem Datum beginnt.

    Die Gegenproben sind der wichtigere Teil - gezählt wurde vorher: Im
    ganzen Bestand tragen genau zwei Zeilen ein „am <Datum>" im Label,
    beide echte Serientermine. Damit die Regel nicht mehr fängt als das,
    gelten zwei Bedingungen:

    - Das Wort „am" muss davorstehen. Ein blankes Datum irgendwo im Text
      kann alles sein.
    - Der Termin muss IM Zeitraum der Veranstaltung liegen, und Wörter
      wie „Anmeldeschluss" schließen ihn aus. Sonst schöbe
      „(Anmeldeschluss am 14.02.2027)" den Lauf auf die Meldefrist.
    """
    print("\nSerientermin im Wettbewerbs-Label (_datum_aus_label):")
    from clean_events import _datum_aus_label, fix_series_dates

    def zeile(wb, start="2027-01-31", ende="2027-02-28"):
        return {"name": "Hammer Winterlaufserie", "datum_start": start,
                "datum_ende": ende, "laenge_km": 15.0, "wettbewerb": wb}

    check("Klammerzusatz wird zum Termin",
          _datum_aus_label(zeile("15,0 km (am 14.02.2027 für M/W ab 18 bis M/W85)")),
          ("2027-02-14", "15,0 km"))
    check("und das Label behält seinen Rest",
          _datum_aus_label(zeile("Halbmarathon (am 28.02.2027 für M/W ab 18)")),
          ("2027-02-28", "Halbmarathon"))
    check("auch ohne Klammern", _datum_aus_label(zeile("10 km am 14.02.2027")),
          ("2027-02-14", "10 km"))

    check("Anmeldeschluss ist kein Termin",
          _datum_aus_label(zeile("10 km (Anmeldeschluss am 14.02.2027)")), None)
    check("ein Datum außerhalb des Zeitraums auch nicht",
          _datum_aus_label(zeile("Lauf am 14.03.2027")), None)
    check("ein blankes Datum ohne „am“ ebenfalls nicht",
          _datum_aus_label(zeile("10 km 14.02.2027 Start 11 Uhr")), None)
    check("ein gewöhnliches Label bleibt unangetastet",
          _datum_aus_label(zeile("15,0 km")), None)

    events = [zeile("15,0 km (am 14.02.2027 für M/W ab 18 bis M/W85)"),
              zeile("10,0 km")]
    meldungen = fix_series_dates(events)
    check("fix_series_dates setzt Start UND Ende",
          (events[0]["datum_start"], events[0]["datum_ende"]),
          ("2027-02-14", "2027-02-14"))
    check("und lässt die Zeile ohne Termin in Ruhe",
          (events[1]["datum_start"], events[1]["datum_ende"]),
          ("2027-01-31", "2027-02-28"))
    check("eine Meldung je verschobener Zeile", len(meldungen), 1)


def test_manuelle_events() -> None:
    """Einzeln recherchierte Strecken nachtragen (manual_events.json).

    Gebraucht wird das, weil ein Override eine Zeile ÄNDERN, aber keine
    ANLEGEN kann - und beim Durchgehen der Streckenlisten fehlten immer
    wieder einzelne Wettbewerbe einer vorhandenen Veranstaltung (die
    Bühlauer Winterlaufserie hat fünf Termine, wir hatten einen).

    Geprüft wird vor allem, dass dabei nichts DOPPELT entsteht:
    Übersprungen wird jeder Eintrag, zu dem `is_same_event()` schon eine
    Zeile findet. Damit ist der Schritt idempotent und verträgt sich mit
    einem späteren Scraper-Lauf, der dieselbe Strecke selbst einsammelt.
    """
    print("\nEinzeln recherchierte Events (manual_events.json):")
    from clean_events import add_manual_events, load_manual_events

    eintraege = load_manual_events()
    check("die Datei ist lesbar und nicht leer", len(eintraege) > 0, True)
    check("Dokumentations-Felder landen nicht in events.json",
          [k for e in eintraege for k in e if k.startswith("_")], [])
    for feld in ("name", "datum_start", "standort", "art1", "veranstalter_url"):
        fehlend = [e.get("name") for e in eintraege if not e.get(feld)]
        check(f"jeder Eintrag hat {feld}", fehlend, [])
    ohne_koordinaten = [e.get("name") for e in eintraege
                        if e.get("lat") is None or e.get("lon") is None]
    check("jeder Eintrag hat Koordinaten", ohne_koordinaten, [])

    beispiel = dict(eintraege[0])
    ergaenzt, meldungen = add_manual_events([beispiel])
    schluessel = (beispiel["name"], beispiel["datum_start"], beispiel.get("laenge_km"))
    check("eine schon vorhandene Strecke wird nicht doppelt angelegt",
          sum(1 for e in ergaenzt
              if (e["name"], e["datum_start"], e.get("laenge_km")) == schluessel), 1)
    check("und alle anderen kommen dazu", len(meldungen), len(eintraege) - 1)

    ergaenzt, meldungen = add_manual_events([])
    check("in eine leere Liste wird alles nachgetragen",
          (len(ergaenzt), len(meldungen)), (len(eintraege), len(eintraege)))
    nochmal, meldungen = add_manual_events(ergaenzt)
    check("ein zweiter Durchlauf trägt nichts mehr nach", meldungen, [])
    check("idempotent, also gleich viele Zeilen", len(nochmal), len(eintraege))


def test_mehrsport_teilstrecken() -> None:
    """Die Länge eines Triathlons ist die SUMME seiner Teilstrecken.

    `guess_distance_km()` nimmt bei mehreren Zahlen die größte - bei
    einem Triathlon ist das die Radstrecke. Deshalb stand die
    Kurzdistanz des Triathlon Höchstadt mit „40 km" in der Liste statt
    mit 51,5 km, und dasselbe bei jedem zweiten Triathlon im Bestand:
    Niederrhein N3T 38 statt 49,5; Frankfurt City 80 statt 102;
    Indeland 88 statt 109,9. Eine Radstrecke als Länge des Rennens ist
    doppelt falsch - die Zahl stimmt nicht, und sie sieht aus wie ein
    Radrennen.

    Die Gegenproben sind hier der wichtigere Teil: Die Regel darf NUR
    dort zuschlagen, wo wirklich Teilstrecken aufgezählt sind.
    """
    print("\nMehrsport: Teilstrecken summieren (summiere_teilstrecken):")
    from scraper_lib import summiere_teilstrecken as summe

    check("1,5 km Schwimmen + 40 km Rad + 10 km Laufen",
          summe("1,5 km Schwimmen, 40 km Radfahren, 10 km Laufen"), 51.5)
    check("englisch und ohne Leerzeichen", summe("400m Swim 20km Bike 5km Run"), 25.4)
    check("Meter mit Tausenderpunkt", summe("1.500m Swim 40km Bike 10km Run"), 51.5)
    check("Wort vor der Zahl", summe("Schwimmen 1,5 km / Rad 40 km / Laufen 10 km"), 51.5)
    check("Langdistanz", summe("3,8 km Schwimmen, 180 km Rad, 42,2 km Laufen"), 226.0)
    check("Duathlon ohne Schwimmen", summe("10 km Laufen und 40 km Radfahren"), 50.0)

    # --- Gegenproben ---------------------------------------------------
    check("ein reiner Lauftext bleibt unberührt",
          summe("5 km Lauf, 10 km Lauf, 21,1 km Lauf"), None)
    check("ein Halbmarathon auch", summe("21,1 km Halbmarathon"), None)
    check("ein Radrennen allein reicht nicht", summe("Rad 100 km"), None)
    check("eine einzelne Teilstrecke auch nicht", summe("ca. 18,6 km Radfahren"), None)
    check("'Mountainbike Rennen 42 km' ist kein Mehrsport",
          summe("Mountainbike Rennen 42 km"), None)
    # Der wichtigste Schutz: Zählt ein Text MEHRERE Wettbewerbe auf,
    # lässt sich nicht sagen, welche Zahlen zusammengehören. Dann lieber
    # nichts - der Aufrufer macht weiter wie bisher.
    check("zwei Wettbewerbe in einem Text ergeben nichts",
          summe("Jedermann 400m Swim 20km Bike 5km Run "
                "Kurzdistanz 1.500m Swim 40km Bike 10km Run"), None)
    check("leerer Text", summe(""), None)

    from scraper_lib import guess_distance_km
    check("guess_distance_km nutzt die Summe",
          guess_distance_km("1,5 km Schwimmen, 40 km Radfahren, 10 km Laufen", CONFIG), 51.5)
    check("und bleibt sonst wie bisher",
          guess_distance_km("5 km, 10 km, 42,195 km", CONFIG), 42.2)


def test_kalender_staging() -> None:
    """`stage_kalender()` fasst den Git-Index nur in GitHub Actions an.

    Der Umweg gibt es, weil GitHub den `schedule`-Trigger nur aus dem
    Standard-Branch liest und die `update-events.yml` auf `main` ein
    älterer Stand ist: Sie committet `git add events.json` OHNE
    `kalender`. `git commit` committet aber den INDEX - was hier gestaget
    ist, geht also mit.

    Geprüft wird vor allem die Gegenprobe: **Lokal darf das Skript den
    Index NIE anfassen.** Ein Werkzeug, das ungefragt `git add` ausführt,
    wäre eine böse Überraschung.
    """
    print("\nKalenderdateien für den Commit vormerken (stage_kalender):")
    import os
    import subprocess
    from update_events import stage_kalender

    skripte = Path(__file__).resolve().parent
    wurzel = skripte.parent

    alt = os.environ.pop("GITHUB_ACTIONS", None)
    try:
        vorher = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                cwd=wurzel, capture_output=True, text=True).stdout
        stage_kalender()
        nachher = subprocess.run(["git", "diff", "--cached", "--name-only"],
                                 cwd=wurzel, capture_output=True, text=True).stdout
        check("ohne GITHUB_ACTIONS bleibt der Index unberührt", nachher, vorher)
    finally:
        if alt is not None:
            os.environ["GITHUB_ACTIONS"] = alt

    quelle = (skripte / "update_events.py").read_text(encoding="utf-8")
    check("der Aufruf steht in run_build_ics()",
          "    stage_kalender()\n    return True" in quelle, True)
    check("und ist an GITHUB_ACTIONS gebunden",
          'os.environ.get("GITHUB_ACTIONS")' in quelle, True)


def _node_event_detail(ausdruck: str):
    """Lässt event-detail.js komplett in node laufen (mit einem Stummel
    für EnduranceFilters) und gibt das JSON des Ausdrucks zurück - kein
    Nachbau, es läuft der Code der Seiten (`EED` ist das Modul)."""
    import json as _json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        return None
    wurzel = Path(__file__).resolve().parent.parent
    # Erst das echte filters.js (EF), dann event-detail.js - kein
    # Stummel: triathlonFormat() wohnt in filters.js.
    skript = (
        "global.window = global;"
        f"require({_json.dumps(str(wurzel / 'filters.js'))});"
        "global.EnduranceFilters.relativeDays = () => '';"
        f"require({_json.dumps(str(wurzel / 'event-detail.js'))});"
        "const EED = global.EnduranceDetail;"
        f"console.log(JSON.stringify({ausdruck}));"
    )
    ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    if ergebnis.returncode != 0:
        check("event-detail.js läuft in node", ergebnis.stderr.strip()[:300], "")
        return None
    return _json.loads(ergebnis.stdout)


def test_wettbewerb_zusatz() -> None:
    """Der Zusatz unter dem Namen (displayWettbewerb): keine Maßzahl mehr.

    Vom Nutzer am 21.09.2026 entschieden: "Wir haben die Länge in der
    Liste schon und in der Detailansicht dann auch. Man muss es nicht 3x
    sehen." Hier die Fälle aus seiner Meldung und die Gegenproben, an
    denen die erste Fassung gescheitert war (leere Klammern, "ca. ,",
    ein führendes "mit", "400-m-Runde" mit Bindestrich)."""
    print("\nZusatz unter dem Namen (displayWettbewerb):")
    faelle = [
        ("Brian Trail (15,5 km, 500 hm)", 15.5, "Brian Trail"),
        ("5.555 m (Berglauf auf den Lousberg)", 5.6, "Berglauf auf den Lousberg"),
        ("10 km Fuchsburg Lauf (ab Jahrgang 2015)", 10, "Fuchsburg Lauf (ab Jahrgang 2015)"),
        ("Marathon", 42.2, None),
        ("21,1 km", 21.1, None),
        ("18 km", 18, None),
        ("Marathon (6 Runden à 7,5 km)", 42.2, None),
        ("Kurzdistanz 51,5 km (1,5 km Schwimmen / 40 km Rad / 10 km Laufen)", 51.5, "Kurzdistanz"),
        ("2x5 km Staffel", 5, "Staffel"),
        ("4-Stunden-Lauf (400-m-Runde)", None, None),
        ("6 km mit 15 Hindernissen (Fun Distanz)", 6, "15 Hindernissen (Fun Distanz)"),
        ("ca. 10.700 m, 25+ Hindernisse", 10.7, "25+ Hindernisse"),
        ("Nordic Walking", 8, "Nordic Walking"),
        ("5 km Walking - Startgebühr 7 Euro", 5, "Walking - Startgebühr 7 Euro"),
        ("Moslig 8000", None, "Moslig 8000"),
        ("Cross lang (10.060 m)", 10.1, "Cross lang"),
        # Wiederholt nur Sportart oder Kategorie: kein Zusatz.
        ("Laufen", 10, None),
        ("Trail", 12, None),
    ]
    import json as _json
    events = [{"wettbewerb": w, "laenge_km": km, "art1": "Laufen", "art2": "Trail"} for w, km, _ in faelle]
    got = _node_event_detail(_json.dumps(events, ensure_ascii=False) + ".map(e => EED.displayWettbewerb(e))")
    if got is None:
        print("  (node nicht vorhanden - übersprungen)")
        return
    for (w, km, erwartet), ist in zip(faelle, got):
        check(f"{w!r} -> {erwartet!r}", ist, erwartet)


def test_triathlon_format() -> None:
    """triathlonFormat(): erst das Label, dann das SCHWIMMEN, dann die Summe.

    Datenregel 21 (21.09.2026): Weinstadt hat 23,6 km Gesamtlänge, aber
    nur 300 m Schwimmen - Super-Sprint, nicht Sprint. Die Regel greift
    nur nach unten, nur mit Teilstrecke im Label und nur ohne
    Format-Stichwort."""
    print("\nTriathlon-Format (triathlonFormat):")
    T = "Triathlon"
    faelle = [
        ({"art1": T, "laenge_km": 23.6, "wettbewerb": "Jedermann-Triathlon 23,6 km (0,3 km Schwimmen / 18,7 km Rad / 4,6 km Laufen)"}, "supersprint"),
        ({"art1": T, "laenge_km": 23.7, "wettbewerb": "Volkstriathlon 23,7 km (0,7 km Schwimmen / 18 km Rad / 5 km Laufen)"}, "sprint"),
        ({"art1": T, "laenge_km": 25.4, "wettbewerb": "Volksdistanz 25,4 km (400 m Schwimmen / 20 km Rad / 5 km Laufen)"}, "supersprint"),
        ({"art1": T, "laenge_km": 25.4, "wettbewerb": "Jedermann Sprint 25,4 km (400 m Schwimmen / 20 km Rad / 5 km Laufen)"}, "sprint"),
        ({"art1": T, "laenge_km": 23.6, "wettbewerb": "Jedermann-Triathlon"}, "sprint"),
        ({"art1": T, "laenge_km": 51.5, "wettbewerb": ""}, "olympisch"),
        ({"art1": T, "laenge_km": 113, "wettbewerb": ""}, "mittel"),
        ({"art1": T, "laenge_km": 226, "wettbewerb": ""}, "lang"),
        ({"art1": T, "laenge_km": 452, "wettbewerb": ""}, "ultra"),
        ({"art1": T, "laenge_km": 25.5, "wettbewerb": "Volksdistanz 25,5 km (500 m Schwimmen / 20 km Rad / 5 km Laufen)"}, "sprint"),
        ({"art1": T, "art2": "Swimrun", "laenge_km": 40, "wettbewerb": ""}, None),
        ({"art1": "Laufen", "laenge_km": 42.2, "wettbewerb": ""}, None),
    ]
    import json as _json
    got = _node_event_detail(_json.dumps([f for f, _ in faelle], ensure_ascii=False)
                             + ".map(e => EED.triathlonFormat(e))")
    if got is None:
        print("  (node nicht vorhanden - übersprungen)")
        return
    for (f, erwartet), ist in zip(faelle, got):
        check(f"{(f.get('wettbewerb') or f['laenge_km'])!r} -> {erwartet!r}", ist, erwartet)


def test_triathlon_format_kopie() -> None:
    """triathlonFormat() steht zweimal - filters.js (Liste, Karte) und
    functions/index.js (Abo-Filter). Beide Fassungen müssen wortgleich
    sein (bis auf Einrückung und Anführungszeichen), und der Längen-
    Filter muss bei JEDEM Triathlon im Bestand dieselbe Kategorie
    treffen, die die Spalte anzeigt (Datenregel 21)."""
    print("\nTriathlon-Format: Kopie in functions/index.js und Filter == Anzeige:")
    wurzel = Path(__file__).resolve().parent.parent
    def block(text: str) -> str:
        a = text.index("TRIATHLON_FORMAT_IM_LABEL = [")
        b = text.index("TRIATHLON_FORMAT_KATEGORIE = {")
        zeilen = []
        for z in text[a:b].splitlines():
            z = z.strip().replace('"', "'")
            if z and not z.startswith("//"):
                zeilen.append(z)
        return "\n".join(zeilen)
    web = block((wurzel / "filters.js").read_text(encoding="utf-8"))
    fn = block((wurzel / "functions" / "index.js").read_text(encoding="utf-8"))
    check("filters.js und functions/index.js: dieselbe Regel", fn == web, True)
    if fn != web:
        import difflib
        for d in list(difflib.unified_diff(web.splitlines(), fn.splitlines(), lineterm=""))[:12]:
            print("    " + d)

    import json as _json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        print("  (node nicht vorhanden - übersprungen)")
        return
    skript = (
        "global.window = global;"
        f"require({_json.dumps(str(wurzel / 'filters.js'))});"
        "const EF = global.EnduranceFilters;"
        f"const events = require({_json.dumps(str(wurzel / 'events.json'))}).filter(e => e.art1 === 'Triathlon' && e.laenge_km != null);"
        "const KAT = { supersprint: 'supersprint', sprint: 'sprint', olympisch: 'olympic', mittel: 'middle', lang: 'long', ultra: 'tultra' };"
        "const keys = Object.values(KAT);"
        "let falsch = [];"
        "for (const e of events) {"
        "  const f = EF.triathlonFormat(e); if (!f) continue;"
        "  const st = EF.createState();"
        "  const getroffen = keys.filter(k => { st.distanceCategories = new Set(['Triathlon:' + k]); return EF.matchEvent(st, e); });"
        "  if (getroffen.length !== 1 || getroffen[0] !== KAT[f]) falsch.push([e.name, e.laenge_km, f, getroffen]);"
        "}"
        "console.log(JSON.stringify({ n: events.length, falsch: falsch.slice(0, 5) }));"
    )
    ergebnis = subprocess.run([node, "-e", skript], capture_output=True, text=True)
    if ergebnis.returncode != 0:
        check("filters.js läuft in node", ergebnis.stderr.strip()[:300], "")
        return
    out = _json.loads(ergebnis.stdout)
    check(f"Filterkategorie == angezeigtes Format bei {out['n']} Triathlon-Zeilen", out["falsch"], [])


def test_charity_merkmal() -> None:
    """fix_charity(): das Merkmal aus dem Namen, die alte Kategorie geleert,
    refresh_art2() holt die echte zurück (Datenregel 17)."""
    print("\nCharity-Merkmal (fix_charity):")
    from clean_events import fix_charity, refresh_art2  # lokaler Import
    rows = [
        {"name": "Bietlauf für einen Wohltätigen Zweck", "datum_start": "2026-10-03", "art1": "Laufen", "art2": "Charity", "wettbewerb": "9,2 km Crosslauf"},
        {"name": "Lauf für einen guten Zweck - Rastenberg", "datum_start": "2026-09-22", "art1": "Laufen", "art2": "Straße"},
        {"name": "Stadtlauf Erding", "datum_start": "2026-09-27", "art1": "Laufen", "art2": "Straße"},
        {"name": "Ahmadiyya Charity Walk Neuwied", "datum_start": "2026-10-11", "art1": "Laufen", "art2": "Charity"},
    ]
    fix_charity(rows)
    check("Benefiz-Crosslauf: charity gesetzt", rows[0].get("charity"), True)
    check("... und die alte Kategorie geleert", rows[0].get("art2"), None)
    check("'guten Zweck' -> charity", rows[1].get("charity"), True)
    check("Stadtlauf bleibt ohne Merkmal", rows[2].get("charity"), None)
    refresh_art2(rows)
    check("refresh_art2 holt die Kategorie aus dem Label zurück", rows[0].get("art2"), "Trail")
    check("Charity Walk ohne Gelände-Stichwort wird Straße", rows[3].get("art2"), "Straße")
    vorher = [dict(r) for r in rows]
    fix_charity(rows); refresh_art2(rows)
    check("fix_charity ist idempotent", rows, vorher)


def test_veranstalter_links() -> None:
    """Die Prüfregel von scripts/veranstalter_links.py: Eine Kandidatenseite
    gilt nur, wenn sie den Lauf am Namen nennt (neunter Durchgang,
    19.09.2026). Festgehalten werden die Gegenproben, die beim Bau
    aufgetreten sind."""
    import veranstalter_links as vl
    # Umlaute im Hostnamen: „Dülmen" heißt im Netz tsg-duelmen.de.
    assert "duelmen" in vl.host_woerter("Nikolauslauf der TSG Dülmen")
    assert vl.nennt_den_lauf("<p>Termine</p>", "https://www.tsg-duelmen.de/de/sport/",
                             ["Nikolauslauf der TSG Dülmen"], ["2026-12-05"], ["Dülmen"]) == ["host:duelmen"]
    assert vl.nennt_den_lauf("<p>x</p>", "http://www.kyffhaeuser-berglauf.de/",
                             ["Kyffhäuser Berglauf"], ["2027-04-10"], ["Bad Frankenhausen"]) == ["host:kyffhaeuser"]
    # Der Ortsname zählt im TEXT nicht - sonst wäre jeder Laufshop der Stadt ein Treffer.
    assert vl.nennt_den_lauf("<p>Laufschuhe in Leipzig kaufen</p>", "https://shop.example.de/",
                             ["Leipzig Run"], ["2026-10-11"], ["Leipzig"]) == []
    # Allgemeine Wörter („Herbstlauf", „Sparkasse") belegen nichts, ein unverwechselbares schon.
    assert vl.nennt_den_lauf("<p>Herbstlauf der Sparkasse</p>", "https://example.de/",
                             ["Sparkassen Herbstlauf"], ["2026-10-11"], ["Bayreuth"]) == []
    assert vl.nennt_den_lauf("<p>Der Ingelheimer Polderlauf startet</p>", "https://www.polderlauf.de/",
                             ["Ingelheimer Polderlauf"], ["2026-10-03"], ["Ingelheim am Rhein"])[0] == "host:polderlauf"
    # Das Datum allein reicht als Beleg.
    assert "datum" in vl.nennt_den_lauf("<p>Start am 03.10.2026</p>", "https://example.de/",
                                        ["Lauf"], ["2026-10-03"], ["Ort"])
    # Umlaut-Domains stehen in der Adresse als Punycode - dekodiert steckt der Name darin
    # (Silvesterlauf Mörschied auf tus-mörschied.de, zehnter Durchgang 20.09.2026).
    assert vl.host_von("https://www.xn--tus-mrschied-8ib.de/index.php/laufen") == "tus-mörschied.de"
    assert vl.nennt_den_lauf("<p>x</p>", "https://www.xn--tus-mrschied-8ib.de/silvesterlauf",
                             ["Silvesterlauf Mörschied"], ["2026-12-31"], ["Mörschied"]) == ["host:morschied"]
    # Der ORT im Hostnamen zählt nur für handverlesene Kandidaten (verifizieren):
    # djk-herzogenrath.de belegt den Volkslauf Herzogenrath - herzogenrath.de wäre die Stadt.
    assert vl.nennt_den_lauf("<p>Ausschreibung</p>", "http://www.djk-herzogenrath.de/seite/ausschreibung.html",
                             ["46. Internationaler Halbmarathon, 56. Internationaler Volkslauf"],
                             ["2026-10-24"], ["Herzogenrath"]) == []
    # Seit dem 22.09.2026 heißt der Treffer „ort:", nicht „host:": `verifizieren` nimmt
    # einen reinen Orts-Treffer nur noch als `unklar` (falkensteinlauf.de war ein anderer
    # Falkenstein-Lauf, tsg-leutkirch.de der Juli-Volkslauf statt der Stadtmeisterschaft).
    assert vl.nennt_den_lauf("<p>Ausschreibung</p>", "http://www.djk-herzogenrath.de/seite/ausschreibung.html",
                             ["46. Internationaler Halbmarathon, 56. Internationaler Volkslauf"],
                             ["2026-10-24"], ["Herzogenrath"], ort_im_host=True) == ["ort:herzogenrath"]
    # Ort im Host PLUS Datum auf der Seite bleibt ein voller Beleg.
    assert vl.nennt_den_lauf("<p>Start am 24.10.2026</p>", "http://www.djk-herzogenrath.de/",
                             ["46. Internationaler Volkslauf"], ["2026-10-24"], ["Herzogenrath"],
                             ort_im_host=True) == ["ort:herzogenrath", "datum"]
    # Ergebnisdienste, Karten und Datenschutzseiten sind keine Veranstalter.
    assert vl.kandidaten_url_normalisieren("https://www.sportstiming.dk/event/17605") is None
    assert vl.kandidaten_url_normalisieren("https://example.de/datenschutz") is None
    print("✓ Veranstalterseiten-Prüfung (Umlaut-Hosts, Ortswort, ort:-Treffer, Allgemeinwörter, Datum, Fremd-Hosts)")


def test_schwimmen_regeln() -> None:
    """Reine Schwimm-Events erst ab 500 m, und keine Meisterschaften
    (vom Nutzer am 24.09.2026 entschieden: "Schwimm events sollten erst
    ab 500m aufgenommen werden. Also reine Schwimmevents. Bei einem
    Triathlon kann es auch weniger sein als 500m. Ich möchte keine
    Schwimm Events aufnehmen, die nicht für jeden sind, also 50m
    deutsche Meisterschaft etc.").

    Die Gegenproben sind der wichtigere Teil: Der 300-m-Schwimmteil
    eines Super-Sprint-Triathlons bleibt, ein 3,5-km-Lauf fällt weiter,
    ein Zeitrennen ist nie zu kurz, und eine LAUF-Meisterschaft bleibt
    (Datenregel 18 - dort entscheidet der Einzelfall)."""
    print("\nSchwimmen: 500-m-Grenze und Meisterschaften:")
    from scraper_lib import (Event, MIN_DISTANCE_BY_ART1, filter_min_distance,
                             filter_nicht_offen_schwimmen, ist_nicht_offen_schwimmen,
                             ist_zu_kurz)
    from clean_events import drop_nicht_offen_schwimmen, drop_too_short

    check("Schwimmen hat 0,5 km", MIN_DISTANCE_BY_ART1.get("Schwimmen"), 0.5)
    check("Laufen hat 5 km", MIN_DISTANCE_BY_ART1.get("Laufen"), 5.0)
    check("400 m Schwimmen ist zu kurz", ist_zu_kurz("Schwimmen", 0.4), True)
    check("500 m Schwimmen bleibt", ist_zu_kurz("Schwimmen", 0.5), False)
    check("3,5 km Lauf ist zu kurz", ist_zu_kurz("Laufen", 3.5), True)
    check("Triathlon kennt keine Grenze", ist_zu_kurz("Triathlon", 0.3), False)
    check("Fahrrad kennt keine Grenze", ist_zu_kurz("Fahrrad", 3.0), False)
    check("unbekannte Distanz ist nie zu kurz", ist_zu_kurz("Schwimmen", None), False)
    check("Zeitrennen ist nie zu kurz", ist_zu_kurz("Schwimmen", 0.1, 24.0), False)

    ev = [Event(art1="Schwimmen", name="Seeschwimmen", laenge_km=0.25),
          Event(art1="Schwimmen", name="Seeschwimmen", laenge_km=0.5),
          Event(art1="Triathlon", name="Weinstadt Triathlon", laenge_km=23.6),
          Event(art1="Laufen", name="Kinderlauf", laenge_km=2.0),
          Event(art1="Schwimmen", name="24h Schwimmen", laenge_km=0.05, dauer_h=24.0)]
    kept, skipped = filter_min_distance(ev)
    check("filter_min_distance wirft 250 m Schwimmen und 2-km-Lauf", skipped, 2)
    check("… und behält 500 m, Triathlon und Zeitrennen", len(kept), 3)
    # Ältere Aufrufer mit ausdrücklicher Grenze: nur Laufen, wie vorher.
    kept, skipped = filter_min_distance(ev, 5.0)
    check("filter_min_distance(min_km) bleibt eine Lauf-Regel", skipped, 1)
    kept, dropped = drop_too_short([
        {"name": "Seeschwimmen", "art1": "Schwimmen", "laenge_km": 0.4},
        {"name": "Seeschwimmen", "art1": "Schwimmen", "laenge_km": 1.0},
        {"name": "Triathlon", "art1": "Triathlon", "laenge_km": 0.3},
        {"name": "24h Halle", "art1": "Schwimmen", "laenge_km": 0.05, "dauer_h": 24}])
    check("clean_events.drop_too_short ebenso", (len(kept), len(dropped)), (3, 1))

    for name in ("Deutsche Meisterschaften Freiwasser", "Bayerische Freiwassermeisterschaft",
                 "DM Kurzbahn Wuppertal", "Landesmeisterschaften Schwimmen",
                 "Open Water Championships Zürich", "Offene Sächsische Freiwassermeisterschaften"):
        check(f"{name!r} ist nicht offen", bool(ist_nicht_offen_schwimmen("Schwimmen", name)), True)
    for name in ("Bodensee Openwater Konstanz", "Alpen Open Water Cup Simssee",
                 "Hafenschwimmen Wilhelmshaven", "24h Friedberg", "Wörthersee Swim",
                 "Jedermann-Schwimmen am Pöhl-Cup"):
        check(f"{name!r} bleibt", ist_nicht_offen_schwimmen("Schwimmen", name), None)
    check("Lauf-Meisterschaft ist nicht betroffen",
          ist_nicht_offen_schwimmen("Laufen", "Bayerische Halbmarathon-Meisterschaften"), None)
    check("Label zählt mit",
          bool(ist_nicht_offen_schwimmen("Schwimmen", "Seefest Wörthsee", "Meisterschaft 1500 m")), True)
    kept, skipped = filter_nicht_offen_schwimmen([
        Event(art1="Schwimmen", name="DM Freiwasser"), Event(art1="Schwimmen", name="Seeschwimmen"),
        Event(art1="Laufen", name="Deutsche Meisterschaft 10 km")])
    check("filter_nicht_offen_schwimmen", (len(kept), skipped), (2, 1))
    kept, entfernt = drop_nicht_offen_schwimmen([
        {"name": "DM Freiwasser", "art1": "Schwimmen", "datum_start": "2027-06-01"},
        {"name": "Seeschwimmen", "art1": "Schwimmen"}])
    check("clean_events.drop_nicht_offen_schwimmen", (len(kept), len(entfernt)), (1, 1))
    # Am Bestand: Keine Schwimm-Zeile darf dadurch fallen, ohne dass
    # es gemeldet wird - hier zählen wir nur, was gemeldet würde.
    import json as _json
    from scraper_lib import EVENTS_JSON_PATH
    bestand = _json.loads(EVENTS_JSON_PATH.read_text(encoding="utf-8"))
    schwimmen = [e for e in bestand if e.get("art1") == "Schwimmen"]
    zu_kurz = [e for e in schwimmen if ist_zu_kurz("Schwimmen", e.get("laenge_km"), e.get("dauer_h"))]
    check("Bestand: keine Schwimm-Zeile unter 500 m", len(zu_kurz), 0)


def test_schwimmkalender() -> None:
    """Der Scraper für schwimmkalender.de (24.09.2026): Listenzeile,
    Detailseite, Distanz/Dauer/Ort aus der Bezeichnung - ohne Netz."""
    print("\nschwimmkalender.de:")
    import schwimmkalender_scraper as sk
    liste = ("<table id='example'><tr><td width='15%' Title='25.09.2026 '>25.09.2026</td>"
             "<td width='60%'><a href='../main/main.php?d=0&Action=views/lstuserevents.php"
             "&fOK=update|userevents|7275&id=185021732606602137475479552159275218493' class='kat64'"
             "   onclick=\"DoScroll2QueryString(event)\" target='_blank'>24h Friedberg</a></td>"
             "<td width='20%'>Hessen</td></tr><tr><td width='15%' Title='03.10.2026 '>03.10.2026</td>"
             "<td width='60%'><a href='../main/main.php?d=0&Action=views/lstuserevents.php"
             "&fOK=update|userevents|7055&id=1' class='kat63' target='_blank'>"
             "Hafenschwimmen, Wilhelmshaven (3k)</a></td><td width='20%'>Niedersachsen</td></tr>"
             "</table>Freiwasser: 2 Einträge gefunden<input type='hidden' name='id' "
             "value='12339903260660213953077955215927521849352' id = 'id'>")
    zeilen = sk.parse_liste(liste)
    check("zwei Listenzeilen", len(zeilen), 2)
    check("Zeile: Nummer, Kategorie, Name, Land",
          (zeilen[1]["nr"], zeilen[1]["kategorie"], zeilen[1]["name"], zeilen[1]["land"]),
          (7055, 63, "Hafenschwimmen, Wilhelmshaven (3k)", "Niedersachsen"))
    check("Sitzungsnummer", sk.sitzungs_id(liste), "12339903260660213953077955215927521849352")
    check("Liste erkannt", sk.ist_liste(liste), True)
    check("Startseite ist keine Liste", sk.ist_liste("<p>Liebe Schwimmerinnen</p>"), False)
    detail = ("<div id='iKategorieNr'>Freiwasser</div><div class='showastext' id='iBezeichnung' >"
              "Hafenschwimmen, Wilhelmshaven (3k)</div><div id='iDatum' >03.10.2026</div>"
              "<div id='iEndDatum' >-</div><div id='iLandNr' >Niedersachsen</div>"
              "<div id='textarea' ><p><a href=\"http://www.hafenschwimmen.de/\" target=\"_blank\">"
              "Hafenschwimmen</a></p></div><div id='simpletextarea' ></div>")
    d = sk.parse_detail(detail)
    check("Detail: Felder", (d["name"], d["datum_start"], d["datum_ende"], d["land"], d["links"]),
          ("Hafenschwimmen, Wilhelmshaven (3k)", "2026-10-03", None, "Niedersachsen",
           ["http://www.hafenschwimmen.de/"]))
    ev = sk.build_events(d, 63, sk.CONFIG)
    check("eine Zeile mit 3 km, Schwimmen/Freiwasser, Ort und Link",
          [(e.name, e.standort, e.land, e.art1, e.art2, e.laenge_km, e.veranstalter_url) for e in ev],
          [("Hafenschwimmen Wilhelmshaven", "Wilhelmshaven", "Deutschland", "Schwimmen", "Freiwasser",
            3.0, "http://www.hafenschwimmen.de/")])
    check("Distanzen aus der Klammer", sk.distanzen_aus_name("Seeschwimmen, Waging am See (2k/5k)"), [2.0, 5.0])
    check("Komma-Dezimale", sk.distanzen_aus_name("Hechtsee X-Treme, Kufstein (3,8k)"), [3.8])
    check("Meter in der Klammer", sk.distanzen_aus_name("Spreeschwimmen (750m)"), [0.75])
    check("Zahl im Namen ist keine Distanz", sk.distanzen_aus_name("100 x 100 Hamburg"), [])
    check("Dauer aus dem Namen", (sk.dauer_aus_name("24h Friedberg"), sk.dauer_aus_name("25h Handorf"),
                                  sk.dauer_aus_name("Hafenschwimmen (3k)")), (24.0, 25.0, None))
    for name, land, ort in (("Hafenschwimmen, Wilhelmshaven (3k)", "Niedersachsen", "Wilhelmshaven"),
                            ("24h Spaichingen-Aldingen", "Baden-Württemberg", "Spaichingen-Aldingen"),
                            ("25h Schwarzenbach a. Wald", "Bayern", "Schwarzenbach a. Wald"),
                            ("Seeschwimmen Waging am See (5k)", "Bayern", "Waging am See"),
                            ("Urban Challenge Berlin", "Berlin", "Berlin"),
                            ("100 x 100 Hamburg", "Hamburg", "Hamburg"),
                            ("Rotary Charity-Schwimmen (24h Freising)", "Bayern", "Freising"),
                            ("Berliner Spreeschwimmen (1k)", "Berlin", "Berlin"),
                            ("Seeschwimmen (2k)", "Bayern", None),
                            ("Vollmondschwimmen (2k)", "Bayern", None)):
        check(f"Ort aus {name!r}", sk.ort_aus_name(name, land), ort)
    check("Name ohne Distanz und Komma", sk.name_ohne_zusatz("Hafenschwimmen, Wilhelmshaven (3k)"),
          "Hafenschwimmen Wilhelmshaven")
    check("Klammer ohne Distanz bleibt", sk.name_ohne_zusatz("Rotary Charity-Schwimmen (24h Freising)"),
          "Rotary Charity-Schwimmen (24h Freising)")
    check("Bundesland → Deutschland", sk.land_aus_feld("Hessen"), "Deutschland")
    check("Staat bleibt", (sk.land_aus_feld("Österreich"), sk.land_aus_feld("Italien")), ("Österreich", "Italien"))
    d24 = {"name": "24h Friedberg", "datum_start": "2026-09-25", "datum_ende": "2026-09-26",
           "land": "Hessen", "links": []}
    ev = sk.build_events(d24, 64, sk.CONFIG)
    check("24h Halle ist ein Zeitrennen im Becken",
          [(e.name, e.standort, e.art1, e.art2, e.dauer_h, e.laenge_km, e.datum_ende) for e in ev],
          [("24h Friedberg", "Friedberg", "Schwimmen", "Becken", 24.0, None, "2026-09-26")])
    dsr = {"name": "Urban Challenge Berlin", "datum_start": "2026-09-27", "datum_ende": None,
           "land": "Berlin", "links": ["https://www.urban-challenge.de/"]}
    ev = sk.build_events(dsr, 69, sk.CONFIG)
    check("SwimRun ist Triathlon/Swimrun", [(e.art1, e.art2, e.standort) for e in ev],
          [("Triathlon", "Swimrun", "Berlin")])
    ev = sk.build_events({"name": "Seeschwimmen (2k)", "datum_start": "2027-06-01", "datum_ende": None,
                          "land": "Bayern", "links": []}, 63, sk.CONFIG)
    check("ohne erkennbaren Ort keine Zeile", ev, [])
    check("Kategorie-URL", sk.kategorie_url(63, "1"),
          "https://www.schwimmkalender.de/sk_kalender/main/main.php?d=0&Action=views/start.php&fOK=userevents|63|63|63|63&id=1")


def test_neue_quellen() -> None:
    """Die Scraper vom 22.09.2026 (endure-cycling, ÖLV, Sparkasse Running,
    Laufkalender NWS, lauftermine.ch): die Parser, die am Bestand der
    Live-Seiten kalibriert wurden, ohne Netz - und die Regeln, die beim
    Bau aufgetreten sind."""
    from scraper_lib import ort_aus_veranstaltungsort as ort
    # Veranstaltungsorte -> Ort (ÖLV- und Sparkassen-Kalender).
    assert ort("OÖ - 4020 Linz, PHDL Linz (Pädagogische Hochschule)") == "Linz"
    assert ort("Heideparkplatz am Ende der Berggasse 2380 Perchtoldsdorf") == "Perchtoldsdorf"
    assert ort("ASKÖ-Stadion Graz-Eggenberg, Schloßstraße 20, 8020 Graz") == "Graz"
    assert ort('Hotel "Fischer am See", Heiterwang 6611') == "Heiterwang"
    assert ort("Wien-Donauinsel") == "Wien"
    assert ort("Sportplatz Weißenbach am Lech") == "Weißenbach am Lech"
    assert ort("Bad Ischl") == "Bad Ischl"
    import endure_scraper as en
    assert en.parse_zeitraum("5. April 2026") == ("2026-04-05", "2026-04-05")
    assert en.parse_zeitraum("18.–20. Juni 2026") == ("2026-06-18", "2026-06-20")
    assert en.parse_zeitraum("30. Mai – 1. Juni 2026") == ("2026-05-30", "2026-06-01")
    # Nur km mit Streckenwort davor sind weitere Strecken - "5 km vom Bahnhof" nicht.
    assert en.strecken_aus_text("Langstrecke 297 km / 2.500 Hm; Light-Variante 145 km. Start 5 km vom Bahnhof") == [297.0, 145.0]
    import oelv_scraper as oe
    assert oe.parse_ort("Ames (ESP)") == ("Ames", "ESP")
    assert oe.parse_ort("Pergine Valsugana (ITA)") == ("Pergine Valsugana", "Italien")
    assert oe.parse_ort("Ebreichsdorf") == ("Ebreichsdorf", "Österreich")
    import nws_scraper as nws
    assert nws.parse_ort("D-Schönau") == ("Schönau", "Deutschland")
    assert nws.parse_ort("Liestal BL") == ("Liestal", "Schweiz")
    assert nws.parse_ort("Basel (Staffellauf)") == ("Basel", "Schweiz")
    assert nws.schoener_name("20. BELCHEN-BERGLAUF") == "20. Belchen-Berglauf"
    assert nws.schoener_name("16. Muttenz Marathon") == "16. Muttenz Marathon"
    import lauftermine_scraper as lt
    kal = ('id=2;mo("Januar 2026","janvier 2026","gennaio 2026","january 2026")\n'
           'v(1,"www.neujahrsmarathon.ch","Neujahrsmarathon Schlieren","42.2 / 18 / 12 / 6","","ZH","")\n'
           '//v(7,"www.x.ch","Abgesagt Irgendwo","10","","ZH","")\n'
           'mo("Dezember","d","d","d")\n'
           'v(31,"www.stauseelauf.ch","Gippinger Stauseelauf","7.53","","AG","")\n'
           'mo("Januar","j","j","j")\n'
           'v(1,"www.neujahrsmarathon.ch","Neujahrsmarathon Schlieren","42.2","","ZH","")\n')
    e = lt.parse_kalender(kal)
    assert [x["datum"] for x in e] == ["2026-01-01", "2026-12-31", "2027-01-01"], e
    assert e[0]["distanzen"] == ["42.2", "18", "12", "6"] and e[0]["kanton"] == "ZH"
    # Der Ort steht im Namen - oder gar nicht (dann kein Eintrag, kein Raten).
    assert lt.ort_aus_name("Neujahrsmarathon Schlieren") == "Schlieren"
    assert lt.ort_aus_name("La Trotteuse-Tissot La Chaux-de-Fonds") == "La Chaux-de-Fonds"
    assert lt.ort_aus_name("Coupe du Vignoble Cortaillod 3/4") == "Cortaillod"
    assert lt.ort_aus_name("Zürcher Silvesterlauf") is None
    assert lt.ort_aus_name("Corrida Bulloise") is None
    assert lt.ort_aus_name("Bierathlon") is None
    # Die neuen Kalender gelten als Portal, bis eine Veranstalterseite bekannt ist.
    from scraper_lib import is_portal_link
    assert is_portal_link("https://events.endure-cycling.com/events/x/")
    assert is_portal_link("https://oelv.athmin.at/event-details.aspx?event=1")
    assert is_portal_link("https://radsport-events.de/x")
    assert not is_portal_link("https://rundumdenharz.com")
    print("  ✓ neue Quellen: Orte, Zeiträume, Kalender-Skript, Portallinks")


def test_turbosport() -> None:
    """Der Scraper für turbo-sport.eu / BRV Timing (24.09.2026): Navigation,
    Rennseite mit Ausschreibungstabelle, nur offene Klassen, Ort aus Name,
    Pfad oder Hostname - ohne Netz."""
    print("\nturbo-sport.eu (BRV Timing):")
    import turbosport_scraper as ts
    nav = ('<nav><ul class="subnav-nav"><li><a href="/veranstaltungen/donnerstagsrennen" class="subnav-link" '
           'title="2026 Donnerstagsrennen Serie">x</a></li><li><a href="/events/augsburg" class="subnav-link" '
           'title="26.09.26 Obergünzburger RR">x</a></li><li><a href="/events/augsburg" class="subnav-link" '
           'title="26.09.26 Obergünzburger RR">x</a></li></ul></nav>')
    liste = ts.parse_events_liste(nav)
    assert [e["datum"] for e in liste] == [None, "2026-09-26"], liste
    assert liste[1]["url"] == "https://turbo-sport.eu/events/augsburg"
    seite_html = (
        '<main><h2 class="element-header"><span>Großer Fritz Neuser Preis am Samstag, 3. Oktober 2026</span></h2>'
        '<p><a href="https://www.rad-net.de/x">Link zur Ausschreibung auf rad-net.de</a></p>'
        '<p><a href="https://rcherpersdorf.de/veranstaltungen/stadtparkrennen-schwabach/">Link zur Event Website</a></p>'
        '<p><a href="https://www.datasport.de/anmeldeservice/x">Link zur Anmeldung bei Datasport Germany</a></p>'
        '<table><tr><th>Kategorie:</th><th>JG von:</th><th>JG bis:</th><th>Wettbewerb:</th><th>Runden:</th>'
        '<th>Distanz:</th><th>Nenngeld:</th><th>Startzeit:</th></tr>'
        '<tr><td>R.4.1 | 4.5 Amateure</td><td>1987</td><td>2007</td><td>Lizenzklasse</td><td>40</td><td>60 km</td><td>21,00 EUR</td><td>12:45:00</td></tr>'
        '<tr><td>R.6.1 | Jedermann (männlich)</td><td>vor</td><td>2008</td><td>Jedermann</td><td>20</td><td>30 km</td><td>25,00 EUR</td><td>9:00:00</td></tr>'
        '<tr><td>R.6.2 | Jedermann (weiblich)</td><td>vor</td><td>2008</td><td>Jedermann</td><td>20</td><td>30 km</td><td>25,00 EUR</td><td>9:00:00</td></tr>'
        '<tr><td>R.1.1 | 4.27 Hobby Männer</td><td>vor</td><td>2009</td><td>Hobbyklasse</td><td>15</td><td>20.2 km</td><td>18,00 EUR</td><td>18:02:55</td></tr>'
        '</table></main>')
    seite = ts.parse_rennseite(seite_html)
    assert seite["name"] == "Großer Fritz Neuser Preis" and seite["datum"] == "2026-10-03", seite
    assert seite["veranstalter_url"] == "https://rcherpersdorf.de/veranstaltungen/stadtparkrennen-schwabach/"
    # Seit dem 24.09.2026 kommen die Lizenzklassen mit ("Bitte auch die mit BDR Lizenz aufnehmen").
    assert seite["lizenzklassen"] == 1 and [k["km"] for k in seite["klassen"]] == [60.0, 30.0, 30.0, 20.2]
    orte = {"schwabach": [("Schwabach", 49.331, 11.024)], "prien am chiemsee": [("Prien am Chiemsee", 47.856, 12.346)],
            "obergünzburg": [("Obergünzburg", 47.846, 10.418)], "burggen": [("Burggen", 47.777, 10.817)],
            "schönberg": [("Schönberg", 1.0, 1.0), ("Schönberg", 2.0, 2.0)], "landshut": [("Landshut", 48.538, 12.146)]}
    # Der Name nennt keinen Ort - der Pfad der Rennseite tut es.
    evs, grund = ts.events_aus_rennseite(seite, "https://turbo-sport.eu/events/schwabacher-stadtparkrennen", None, ts.CONFIG, orte)
    assert grund is None and len(evs) == 3, (grund, evs)
    assert {(e.standort, e.laenge_km, e.wettbewerb, e.art2) for e in evs} == {
        ("Schwabach", 60.0, "Lizenzklasse 60 km", "Straße"),
        ("Schwabach", 30.0, "Jedermann 30 km", "Straße"), ("Schwabach", 20.2, "Hobbyklasse 20.2 km", "Straße")}, evs
    assert evs[0].lat == 49.331 and evs[0].datum_start == "2026-10-03"
    # Lizenz und Jedermann über DIESELBE Distanz: eine Zeile, das Label nennt beide
    # (dedupe_key und ICS-Dateiname kennen kein Label).
    seite_gleich = dict(seite, klassen=[{"klasse": "Lizenzklasse", "kategorie": "U17", "km": 30.0},
                                        {"klasse": "Jedermann", "kategorie": "Jedermann", "km": 30.0},
                                        {"klasse": "Hobbyklasse", "kategorie": "Hobby", "km": 30.0}])
    evs_gleich, _ = ts.events_aus_rennseite(seite_gleich, "https://turbo-sport.eu/events/schwabacher-stadtparkrennen", None, ts.CONFIG, orte)
    assert [e.wettbewerb for e in evs_gleich] == ["Lizenzklasse / Jedermann / Hobbyklasse 30 km"], evs_gleich
    # Mit KLASSEN_FILTER = OFFENE_KLASSEN bleibt es beim alten Verhalten (umkehrbar).
    ts.KLASSEN_FILTER = ts.OFFENE_KLASSEN
    try:
        nur_offen = ts.parse_rennseite(seite_html)
        assert [k["km"] for k in nur_offen["klassen"]] == [30.0, 30.0, 20.2] and nur_offen["lizenzklassen"] == 1
        seite2 = dict(seite, klassen=[], lizenzklassen=3)
        assert ts.events_aus_rennseite(seite2, "https://turbo-sport.eu/events/x", None, ts.CONFIG, orte) == ([], "nur Lizenzklassen (ausgefiltert)")
    finally:
        ts.KLASSEN_FILTER = None
    # Ergebnisseite (keine Tabelle) liefert nichts.
    seite3 = dict(seite, klassen=[], lizenzklassen=0)
    assert ts.events_aus_rennseite(seite3, "https://turbo-sport.eu/events/x", None, ts.CONFIG, orte)[1].startswith("keine Ausschreibungstabelle")
    # Ort aus dem Namen: Adjektivendung, laufende Nummer, Mehrdeutigkeit, Hostname.
    assert ts.ort_aus_name("1.Obergünzburger Rundstreckenrennen", orte)[0] == "Obergünzburg"
    assert ts.ort_aus_name("37. Burggener Straßenpreis", orte)[0] == "Burggen"
    assert ts.ort_aus_name("11. Inklusiver Landshuter Straßenpreis", orte)[0] == "Landshut"
    assert ts.ort_aus_name("5. Schönberger Pfingstradrennen", orte) is None   # zwei Schönberg in Bayern
    assert ts.ort_aus_name("Kampenkönig", orte) is None
    assert ts.ort_aus_host("https://rfv-prien.de/aktivitaeten/kampenkoenig/", orte)[0] == "Prien am Chiemsee"
    assert ts.ort_aus_host("https://www.rad-net.de/x", orte) is None
    assert ts.ort_aus_slug("https://turbo-sport.eu/events/schwabacher-stadtparkrennen", orte)[0] == "Schwabach"
    # Ohne Ort kein Eintrag - geraten wird nie.
    seite4 = dict(seite, name="Kampenkönig", veranstalter_url=None)
    assert ts.events_aus_rennseite(seite4, "https://turbo-sport.eu/events/kampenkoenig", None, ts.CONFIG, orte) == ([], "Ort nicht erkennbar")
    from scraper_lib import is_portal_link
    assert is_portal_link("https://turbo-sport.eu/events/augsburg")
    print("  ✓ turbo-sport.eu: Navigation, Ausschreibungstabelle, alle Klassen (Lizenz eigene Zeile), Ort aus Name/Pfad/Host")


def test_radsportevents() -> None:
    """Der Scraper für die JSON-API von radsport-events.de (24.09.2026):
    Strecken, Rundenlängen, Dauern, Mehrsport-Summen, Ausschlüsse."""
    print("\nradsport-events.de:")
    import radsportevents_scraper as rs
    basis = {"id": 48, "title": "Spreewaldmarathon", "eventDate": "2027-04-24", "endDate": None,
             "city": "Lübbenau", "country": "DE", "latitude": 51.868, "longitude": 13.969,
             "category": "ROAD", "eventType": "RADMARATHON", "organizerUrl": "http://www.spreewaldmarathon.de/",
             "tentative": False, "cancelled": False, "status": "PUBLISHED",
             "distances": [{"distanceKm": 70.0, "durationMinutes": None, "label": None},
                           {"distanceKm": 200.0, "durationMinutes": None, "label": None}]}
    evs = rs.parse_item(basis, rs.CONFIG)
    assert [(e.laenge_km, e.wettbewerb, e.art1, e.art2, e.land, e.standort) for e in evs] == [
        (70.0, "Radmarathon 70 km", "Fahrrad", "Straße", "Deutschland", "Lübbenau"),
        (200.0, "Radmarathon 200 km", "Fahrrad", "Straße", "Deutschland", "Lübbenau")], evs
    assert evs[0].lat == 51.868 and evs[0].veranstalter_url == "http://www.spreewaldmarathon.de/"
    # Rundenlänge fällt weg, 24h-Rennen bekommt 24 h; Dauer in Minuten -> Stunden.
    e24 = rs.parse_item(dict(basis, eventType="RENNEN_24H", distances=[{"distanceKm": 17.0, "label": "Runde"}]), rs.CONFIG)
    assert len(e24) == 1 and e24[0].laenge_km is None and e24[0].dauer_h == 24.0 and e24[0].wettbewerb == "24-Stunden-Rennen 24 h", e24
    ecx = rs.parse_item(dict(basis, category="MTB", eventType="CYCLOCROSS", distances=[{"distanceKm": 0.0, "durationMinutes": 40}]), rs.CONFIG)
    assert ecx[0].art2 == "Cyclecross" and ecx[0].dauer_h == 0.7 and ecx[0].laenge_km is None, ecx
    # Zeitfahren, Gravel, vorläufiger Termin, Portallink ohne organizerUrl.
    ezf = rs.parse_item(dict(basis, eventType="BERGZEITFAHREN", tentative=True, organizerUrl=None,
                             distances=[{"distanceKm": 10.0}]), rs.CONFIG)
    assert ezf[0].art2 == "Zeitfahren" and ezf[0].datum_vorlaeufig is True
    assert ezf[0].veranstalter_url == "https://radsport-events.de/events/48"
    assert rs.parse_item(dict(basis, category="GRAVEL", eventType="GRAVEL_RACE"), rs.CONFIG)[0].art2 == "Gravel"
    # Mehrsport: Summe nur bei beschrifteten Teilstrecken, sonst ohne Länge.
    edu = rs.parse_item(dict(basis, category="MTB", eventType="DUATHLON_CROSS", distances=[
        {"distanceKm": 4.6, "label": "Lauf"}, {"distanceKm": 20.0, "label": "Rad"}, {"distanceKm": 5.0, "label": "Lauf"}]), rs.CONFIG)
    assert len(edu) == 1 and edu[0].art1 == "Triathlon" and edu[0].art2 == "Duathlon" and edu[0].laenge_km == 29.6, edu
    assert edu[0].wettbewerb.startswith("Cross-Duathlon 29.6 km (")
    edu2 = rs.parse_item(dict(basis, eventType="DUATHLON", distances=[{"distanceKm": 3.0}, {"distanceKm": 14.0}]), rs.CONFIG)
    assert len(edu2) == 1 and edu2[0].laenge_km is None and edu2[0].wettbewerb == "Duathlon", edu2
    # Ausschlüsse: abgesagt, virtuell, Camp, Mannschaftszeitfahren, Italien außerhalb Südtirols.
    assert rs.parse_item(dict(basis, cancelled=True), rs.CONFIG) == []
    for typ in ("VIRTUELLE_RTF", "GRAVEL_CAMP", "MANNSCHAFTSZEITFAHREN", "ETAPPENTOUR"):
        assert rs.parse_item(dict(basis, eventType=typ), rs.CONFIG) == [], typ
    assert rs.parse_item(dict(basis, country="IT", latitude=45.69, longitude=9.67), rs.CONFIG) == []   # Bergamo
    bozen = rs.parse_item(dict(basis, country="IT", latitude=46.498, longitude=11.354), rs.CONFIG)   # Bozen
    assert bozen and bozen[0].land == "Italien", bozen  # Südtirol setzt filter_dach() über die Koordinaten
    from scraper_lib import is_portal_link
    assert is_portal_link("https://radsport-events.de/events/48")
    print("  ✓ radsport-events.de: Strecken, Runde/Dauer, Zeitfahren/Gravel/Cyclocross, Mehrsport-Summe, Ausschlüsse")


def main() -> int:
    for test in (test_distanz, test_rundung, test_kategorie, test_land,
                 test_wettbewerbe, test_hoehenprofil, test_offizieller_link,
                 test_duplikate, test_namensvereinheitlichung,
                 test_vergangene_events, test_zeitrennen, test_kalenderdateien, test_web_data,
                 test_meldungen,
                 test_ortsverzeichnis, test_js_syntax, test_abo_rhythmen,
                 test_override_schluessel, test_suche_uebersetzungen,
                 test_fremde_sportart, test_zwei_rennen_in_einer_zeile,
                 test_koordinaten_widerspruch, test_override_koordinaten,
                 test_zwei_sportarten_im_namen, test_audit_pruefungen,
                 test_stundenlauf, test_such_vorschlaege,
                 test_nicht_ausdauer, test_staffeln, test_datum_vorlaeufig, test_laufen_weiterleitung, test_veranstalter_links, test_neue_quellen, test_serientermin_im_label,
                 test_schwimmen_regeln, test_schwimmkalender, test_turbosport, test_radsportevents,
                 test_kalender_staging,
                 test_mehrsport_teilstrecken,
                 test_manuelle_events,
                 test_keine_fremden_dateien, test_laender_maske,
                 test_asset_stempel, test_farbschema_skript,
                 test_lauf_im_triathlonkalender,
                 test_wettbewerb_zusatz, test_triathlon_format, test_charity_merkmal,
                 test_triathlon_format_kopie):
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
