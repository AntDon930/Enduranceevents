#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_laender.py
================

Baut `laender.json` - die Umrisse der Länder, die die Seite abdeckt.
Gebraucht wird die Datei von `karte.html`: Alles AUSSERHALB dieser Länder
liegt dort unter einer grauen Maske, damit der Blick auf der Region
bleibt (so vom Nutzer am 18.09.2026 gewünscht).

Warum eine eigene Datei und kein Kartendienst: Ein Kachel-Anbieter mit
label-armem Stil wäre ein zweiter fremder Server, an den die IP-Adresse
jedes Besuchers geht - die OpenStreetMap-Kacheln sind die EINZIGE
Ausnahme, die dieses Projekt sich erlaubt (siehe README "Nichts von
fremden Servern"). Eine Maske aus eigenen Daten kostet ~60 KB und
überträgt nichts.

Quelle: Natural Earth (`ne_10m_admin_0_countries` für die Staaten,
`ne_10m_admin_1_states_provinces` für Südtirol - die Provinz Bozen ist
keine Staatsgrenze), **Public Domain**
(keine Namensnennung verlangt; sie steht trotzdem im Impressum, weil
dort alle Datenquellen stehen). 1:10 Mio ist die genaueste der drei
Natural-Earth-Stufen - bei 1:50 Mio lägen die Grenzen an Orten wie Basel
oder Konstanz sichtbar daneben.

Aufruf (läuft NICHT im Workflow mit, wie build_places.py):

    python3 scripts/build_laender.py                  # lädt und baut
    python3 scripts/build_laender.py --quelle ne10.json   # aus Datei
    python3 scripts/build_laender.py --toleranz 0.002     # gröber

Die Datei wird committet: Sie ändert sich praktisch nie (Ländergrenzen),
und der Pages-Workflow soll nichts herunterladen müssen.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "laender.json"

QUELLE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
              "master/geojson/ne_10m_admin_0_countries.geojson")
# Provinzen und Bundesländer (~40 MB) - nur geladen, wenn ein Eintrag in
# LAENDER sie braucht.
QUELLE_ADMIN1_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
                     "master/geojson/ne_10m_admin_1_states_provinces.geojson")

# Welche Länder die Seite abdeckt. Der Schlüssel ist GENAU der Wert, der
# in events.json im Feld `land` steht (und in filters.js in LAENDER) -
# so lässt sich die Maske später um ein Land erweitern, ohne hier etwas
# umzubauen: Zeile eintragen, Skript laufen lassen, fertig.
# Der Wert nennt die Eigenschaft und ihren Wert in der Quelle: Staaten
# über ADM0_A3 in ne_10m_admin_0_countries, Provinzen über iso_3166_2 in
# ne_10m_admin_1_states_provinces.
#
# Südtirol (vom Nutzer am 21.09.2026 aufgenommen: "sehr viele Radrennen,
# ein sehr sportliches Land - damit sind es alle Ausdauer-Events im
# deutschsprachigen Raum") ist die Provinz Bozen (IT-BZ), nicht ganz
# Italien; im Filter heißt sie "Italien (Südtirol)", damit niemand ganz
# Italien erwartet.
LAENDER = {
    "Deutschland": ("ADM0_A3", "DEU"),
    "Österreich": ("ADM0_A3", "AUT"),
    "Schweiz": ("ADM0_A3", "CHE"),
    "Italien (Südtirol)": ("iso_3166_2", "IT-BZ"),
}

# Vereinfachung in Grad. 0.001° ≈ 110 m in der Höhe; in der Breite wird
# mit cos(Breitengrad) gerechnet, sonst wäre die Toleranz in Ost-West-
# Richtung fast doppelt so groß wie in Nord-Süd-Richtung.
#
# ~100 m ist fein genug, dass die Maskenkante auch beim Hineinzoomen auf
# der Grenze liegt, und grob genug, dass die Datei klein bleibt.
TOLERANZ_GRAD = 0.001

# Nachkommastellen der Koordinaten: 4 ≈ 11 m. Mehr wäre bei 100 m
# Vereinfachung sinnlos und macht die Datei nur größer.
STELLEN = 4


def lade_quelle(pfad: str | None, url: str = QUELLE_URL) -> dict:
    if pfad:
        with open(pfad, encoding="utf-8") as fh:
            return json.load(fh)
    print(f"Lade {url} …")
    with urllib.request.urlopen(url, timeout=600) as antwort:
        return json.loads(antwort.read().decode("utf-8"))


def _abstand_zur_linie(p, a, b, kx: float) -> float:
    """Senkrechter Abstand von p zur Strecke a-b (Grad, ost-west skaliert)."""
    px, py = p[0] * kx, p[1]
    ax, ay = a[0] * kx, a[1]
    bx, by = b[0] * kx, b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def vereinfache(ring: list, toleranz: float) -> list:
    """Douglas-Peucker. Iterativ statt rekursiv - ein Ring hat bis zu
    3.000 Punkte, und Pythons Rekursionsgrenze soll hier keine Rolle
    spielen."""
    if len(ring) < 4:
        return ring
    # Ost-West-Skalierung am mittleren Breitengrad des Rings.
    mitte = sum(p[1] for p in ring) / len(ring)
    kx = math.cos(math.radians(mitte))

    behalten = [False] * len(ring)
    behalten[0] = behalten[-1] = True
    stapel = [(0, len(ring) - 1)]
    while stapel:
        start, ende = stapel.pop()
        if ende <= start + 1:
            continue
        groesster, index = 0.0, start
        for i in range(start + 1, ende):
            d = _abstand_zur_linie(ring[i], ring[start], ring[ende], kx)
            if d > groesster:
                groesster, index = d, i
        if groesster > toleranz:
            behalten[index] = True
            stapel.append((start, index))
            stapel.append((index, ende))
    return [p for p, ja in zip(ring, behalten) if ja]


def ringe_von(geometrie: dict) -> list:
    """Alle Ringe einer (Multi-)Polygon-Geometrie, äußere und Löcher.

    Die Reihenfolge bleibt wie in der Quelle: äußerer Ring, dann seine
    Löcher. Die Karte legt sie als Aussparungen in die graue Fläche;
    `fill-rule: evenodd` (Leaflet-Voreinstellung) sorgt dabei von selbst
    dafür, dass ein Loch IM Land wieder grau wird - etwa Büsingen am
    Hochrhein, das deutsch ist und mitten in der Schweiz liegt.
    """
    if geometrie["type"] == "Polygon":
        polygone = [geometrie["coordinates"]]
    elif geometrie["type"] == "MultiPolygon":
        polygone = geometrie["coordinates"]
    else:
        raise SystemExit("Unerwartete Geometrie: " + geometrie["type"])
    return [ring for polygon in polygone for ring in polygon]


def runde(ring: list) -> list:
    """Koordinaten kürzen - und dabei aufeinanderfolgende Doppelpunkte
    wegwerfen, die durchs Runden entstehen können."""
    raus = []
    for lon, lat in ring:
        punkt = [round(lon, STELLEN), round(lat, STELLEN)]
        if not raus or raus[-1] != punkt:
            raus.append(punkt)
    # Ring wieder schließen (das Runden kann den letzten Punkt schlucken).
    if len(raus) > 2 and raus[0] != raus[-1]:
        raus.append(list(raus[0]))
    return raus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quelle", help="lokale ne_10m_admin_0_countries.geojson")
    ap.add_argument("--quelle-admin1", help="lokale ne_10m_admin_1_states_provinces.geojson")
    ap.add_argument("--toleranz", type=float, default=TOLERANZ_GRAD,
                    help="Vereinfachung in Grad (Standard %(default)s ≈ 110 m)")
    ap.add_argument("--ziel", default=str(ZIEL))
    args = ap.parse_args(argv)

    nach_code = {}
    gesucht = set(LAENDER.values())
    quellen = [("ADM0_A3", args.quelle, QUELLE_URL)]
    if any(eig != "ADM0_A3" for eig, _ in gesucht):
        quellen.append(("iso_3166_2", args.quelle_admin1, QUELLE_ADMIN1_URL))
    for eigenschaft, pfad, url in quellen:
        rohdaten = lade_quelle(pfad, url)
        for feat in rohdaten.get("features", []):
            wert = (feat.get("properties") or {}).get(eigenschaft)
            if (eigenschaft, wert) in gesucht:
                nach_code[(eigenschaft, wert)] = feat
        del rohdaten

    fehlend = [name for name, code in LAENDER.items() if code not in nach_code]
    if fehlend:
        sys.exit("Nicht in der Quelle gefunden: " + ", ".join(fehlend))

    ausgabe = {}
    for name, code in LAENDER.items():
        vorher = 0
        ringe = []
        for ring in ringe_von(nach_code[code]["geometry"]):
            vorher += len(ring)
            einfach = runde(vereinfache(ring, args.toleranz))
            # Ein Ring mit weniger als vier Punkten ist keine Fläche mehr
            # (winzige Inseln fallen so weg - bei 100 m Toleranz sind das
            # Felsen, keine Veranstaltungsorte).
            if len(einfach) >= 4:
                ringe.append(einfach)
        ausgabe[name] = ringe
        print(f"  {name}: {len(ringe)} Ringe, "
              f"{sum(len(r) for r in ringe)} von {vorher} Punkten")

    datei = {
        "_readme": (
            "Umrisse der abgedeckten Länder für die graue Maske auf karte.html. "
            "Erzeugt von scripts/build_laender.py aus Natural Earth "
            "(ne_10m_admin_0_countries; Südtirol = Provinz Bozen aus "
            "ne_10m_admin_1_states_provinces; Public Domain), vereinfacht auf "
            f"{args.toleranz}° (~{round(args.toleranz * 111)} m). Schlüssel = Wert des "
            "Feldes `land` in events.json. Jeder Eintrag ist eine Liste von "
            "Ringen ([[lon, lat], …]); äußere Ringe und Löcher stehen in der "
            "Reihenfolge der Quelle, die Karte zeichnet sie mit "
            "fill-rule: evenodd."
        ),
        "quelle": "Natural Earth, ne_10m_admin_0_countries + ne_10m_admin_1_states_provinces (Public Domain)",
        "laender": ausgabe,
    }
    ziel = Path(args.ziel)
    # separators: keine Leerzeichen - das sind bei ~5.000 Punkten einige KB.
    ziel.write_text(json.dumps(datei, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")
    print(f"{ziel.name}: {ziel.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
