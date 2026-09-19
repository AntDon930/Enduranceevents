#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_places.py
===============

Baut `places.json` - das Ortsverzeichnis für die Umkreissuche auf
`events.html`.

Warum das nötig ist: Die Stadt/Ort-Auswahl kannte früher nur die Orte,
an denen ein Event stattfindet (~2000 Stück aus `events.json`). Wer in
Fürth wohnt und wissen will, was im Umkreis von 40 km läuft, fand
"Fürth" dort aber nur, wenn dort selbst ein Rennen stattfindet. Für die
Umkreissuche braucht es deshalb *alle* Orte und Postleitzahlen von
Deutschland, Österreich und der Schweiz - unabhängig davon, ob dort ein
Event liegt.

Datenquelle: GeoNames (CC BY 4.0, Namensnennung steht im Filter-Panel
und im README).

* `https://download.geonames.org/export/zip/<CC>.zip` - Postleitzahlen
  mit Ortsname und Koordinaten. Das ist die Grundlage: nur hier steht
  die PLZ.
* `https://download.geonames.org/export/dump/<CC>.zip` - der große
  Gazetteer. Daraus kommt nur die **Einwohnerzahl**, und die dient
  einzig der Sortierung der Trefferliste: wer "Mün" tippt, will
  München sehen und nicht Münchendorf.

Ergebnis ist eine kompakte JSON-Datei (Arrays statt Objekte, damit sie
klein bleibt - sie wird im Browser nachgeladen, sobald der Nutzer den
Stadt/Ort-Filter öffnet):

    {
      "quelle": "...", "erstellt": "2026-09-16",
      "laender": ["DE", "AT", "CH"],
      "regionen": ["Bayern", ...],
      "orte": [[name, landIdx, regionIdx, lat, lon, einwohner, "plz plz"], ...]
    }

Aufruf:

    python3 scripts/build_places.py                 # lädt und schreibt places.json
    python3 scripts/build_places.py --cache-dir /tmp/geonames
    python3 scripts/build_places.py --out places.json

Das Skript läuft **nicht** im Wochen-Workflow mit: Ortsnamen und
Postleitzahlen ändern sich praktisch nie, ein Lauf pro Jahr genügt.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple

LAENDER = ["DE", "AT", "CH"]

ZIP_URL = "https://download.geonames.org/export/zip/{cc}.zip"
DUMP_URL = "https://download.geonames.org/export/dump/{cc}.zip"

# Deutschland vergibt eigene Postleitzahlen an Großempfänger (Behörden,
# Konzerne). In der GeoNames-Datei steht dann der Firmenname im Feld
# "Ortsname" - "Mercedes-Benz Vertrieb NFZ GmbH" ist kein Ort und hat in
# einer Ortsauswahl nichts verloren.
#
# Bewusst nur eindeutige Rechtsformen und immer als ganzes Wort: ein
# schlichtes "AG" oder "KG" als Zeichenkette träfe auch Ortsnamen ("Baden
# AG" trägt in der Schweizer PLZ-Datei das Kantonskürzel, "Bad
# Aglasterhausen" hat die Buchstabenfolge mitten im Namen). Der Rest -
# "Finanzamt Fürth", "Sparkasse Wetzlar" - fällt ohnehin über den
# Gazetteer-Abgleich weg, siehe `_hat_ortsbezug`.
FIRMEN_MUSTER = re.compile(
    r"\b(gmbh|mbh|kgaa|ohg|gbr|aktiengesellschaft)\b"
    r"|\be\.?\s*v\.?(\s|$)"
    r"|&\s*co\b",
    re.IGNORECASE,
)


# Rechtsform am Ende des Namens - greift nur in Ländern ohne
# Kantonskürzel im Ortsnamen (siehe ORTSBEZUG_PRUEFEN). "Deutz AG" und
# "Eppendorf SE" sind Firmen, die Schweizer "Wohlen AG" und "Reinach AG"
# dagegen Gemeinden mit angehängtem Kantonskürzel - deshalb diese Regel
# nicht für die Schweiz.
RECHTSFORM_ENDE = re.compile(r"\b(ag|se|kg|eg|ug|mbh|ohg|gbr|ev)\.?$", re.IGNORECASE)


def _ist_firma(name: str, streng: bool = False) -> bool:
    """True, wenn der "Ortsname" in Wahrheit ein Großempfänger ist."""
    if FIRMEN_MUSTER.search(name):
        return True
    return bool(streng and RECHTSFORM_ENDE.search(name))


def normalisiere(text: str) -> str:
    """Suchschlüssel: klein, ohne Umlaute/Akzente, ohne Sonderzeichen.

    Muss zur gleichnamigen Funktion in `events.html` passen - dort wird
    die Nutzereingabe genauso behandelt, damit "muenchen", "München" und
    "munchen" dasselbe finden. "Sankt" und "St." werden vereinheitlicht,
    sonst findet "Sankt Anton am Arlberg" den Ort nicht, der in den
    Daten "St. Anton am Arlberg" heißt.
    """
    t = text.lower()
    t = (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
          .replace("ß", "ss"))
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = "".join(c if c.isalnum() else " " for c in t)
    t = " ".join(t.split())
    t = re.sub(r"\b(sankt|saint|ste)\b", "st", t)
    return t


def _lade(url: str, cache_dir: str) -> bytes:
    """Lädt eine Datei, legt sie im Cache ab und nutzt sie beim nächsten Mal."""
    os.makedirs(cache_dir, exist_ok=True)
    pfad = os.path.join(cache_dir, url.rsplit("/", 2)[-2] + "_" + url.rsplit("/", 1)[-1])
    if os.path.exists(pfad) and os.path.getsize(pfad) > 0:
        with open(pfad, "rb") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": "endurance-events-places/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        daten = resp.read()
    with open(pfad, "wb") as fh:
        fh.write(daten)
    return daten


def _entpacke(daten: bytes, name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(daten)) as zf:
        return zf.read(name).decode("utf-8")


def _entfernung_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Luftlinie in Kilometern (Haversine) - grob genügt hier völlig."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def gazetteer(cc: str, cache_dir: str) -> Dict[str, List[Tuple[float, float, int, bool]]]:
    """Normalisierter Name -> [(lat, lon, Einwohner, ist_Ort), ...].

    Ein Index über den GeoNames-Gazetteer, der zwei Fragen beantwortet:

    * **Wie groß ist der Ort?** Nur zur Sortierung der Trefferliste - wer
      "Mün" tippt, will München sehen und nicht Münchendorf. Über die
      Verwaltungscodes ließe sich das nicht zuordnen: die PLZ-Datei führt
      für Deutschland mal "01", mal "BY" als admin1, je nach Zeile.
      Zugeordnet wird deshalb über Name + Nähe.
    * **Gibt es diesen Ort überhaupt?** Die deutsche Post vergibt eigene
      Postleitzahlen an Großempfänger; in der PLZ-Datei steht dann
      "Finanzamt Fürth" oder "Amtsgericht Schweinfurt" im Ortsfeld. Was
      im Gazetteer keine Entsprechung in der Nähe hat, ist kein Ort
      (siehe `_hat_ortsbezug`).

    Enthalten sind besiedelte Orte (Klasse P) und Verwaltungseinheiten
    (Klasse A) samt ihrer alternativen Namen - München heißt im
    Gazetteer "Munich", "München" steht in der Liste der
    fremdsprachigen Namen, und Wien steht als Stadt unter "Vienna".
    """
    text = _entpacke(_lade(DUMP_URL.format(cc=cc), cache_dir), f"{cc}.txt")
    index: Dict[str, List[Tuple[float, float, int, bool]]] = defaultdict(list)
    for zeile in text.splitlines():
        f = zeile.split("\t")
        if len(f) < 15:
            continue
        klasse = f[6]
        if klasse not in ("P", "A"):
            continue
        try:
            lat, lon = float(f[4]), float(f[5])
            pop = int(f[14] or 0)
        except ValueError:
            continue
        # Einwohnerzahlen nur von Orten und Bundesländern/Kantonen (ADM1).
        # Regierungsbezirke (ADM2) bleiben draußen, sonst erbt Arnsberg die
        # 3,5 Millionen seines Bezirks und steht in der Trefferliste über
        # Berlin.
        if klasse == "A" and f[7] != "ADM1":
            pop = 0
        eintrag = (lat, lon, pop, klasse == "P")
        namen = {f[1], f[2]}
        if f[3]:
            namen.update(f[3].split(","))
        for name in namen:
            name = name.strip()
            if name:
                index[normalisiere(name)].append(eintrag)
    return index


def _in_der_naehe(index, name: str, lat: float, lon: float, max_km: float) -> List[Tuple[float, float, int, bool]]:
    return [k for k in index.get(normalisiere(name), ())
            if _entfernung_km(lat, lon, k[0], k[1]) <= max_km]


# Wie weit ein Gazetteer-Eintrag vom Mittelpunkt der Postleitzahlbezirke
# entfernt sein darf, um noch als derselbe Ort zu gelten.
GAZETTEER_MAX_KM = 30.0

# Nur für Deutschland wird verworfen, was im Gazetteer keine Entsprechung
# hat. Großempfänger-Postleitzahlen ("Finanzamt Fürth") gibt es nur dort.
# Österreich und die Schweiz führen in ihren PLZ-Dateien echte Ortschaften,
# und viele kleine Weiler ("Kohlergraben", "Abländschen", "Jungfraujoch")
# fehlen schlicht im Gazetteer - die Prüfung hätte dort über 1000 richtige
# Orte gelöscht.
ORTSBEZUG_PRUEFEN = ("DE",)


def _hat_ortsbezug(index, name: str, lat: float, lon: float) -> bool:
    """Steht hinter dem Namen ein echter Ort - oder ein Großempfänger?

    Geprüft wird der ganze Name und zusätzlich sein Anfang: viele
    PLZ-Einträge heißen "Gemeinde Ortsteil" ("Hamburg Stellingen",
    "Wittstock/Dosse Freyenstein"), und der Ortsteil steht nicht immer
    im Gazetteer - die Gemeinde davor aber schon. Umgekehrt beginnt
    "Finanzamt Fürth" mit einem Wort, das nirgends ein Ort ist, und
    fliegt damit raus. Nur der Anfang zählt, nicht das Ende: sonst
    würde "Fürth" das Finanzamt wieder hereinholen.
    """
    woerter = normalisiere(name).split()
    if not woerter:
        return False
    kandidaten = [name]
    kandidaten.extend(" ".join(woerter[:i]) for i in (1, 2) if i < len(woerter))
    # Verwaltungseinheiten zählen hier bewusst mit. Sie nicht zu zählen
    # würde zwar "Kreis Borken" (nur als Kreis eingetragen) loswerden,
    # aber auch 663 echte Gemeinden mitreißen, die im Gazetteer allein
    # als Gemeinde stehen, weil die Ortschaft darin anders heißt -
    # Crinitzberg, Nuthe-Urstromtal, Ammersbek. Ein Kreisname zu viel in
    # der Auswahl ist harmlos (seine Koordinaten stimmen), ein fehlender
    # Wohnort nicht.
    return any(_in_der_naehe(index, k, lat, lon, GAZETTEER_MAX_KM) for k in kandidaten)


# Wie nah zwei gleichnamige Ortsgruppen beieinander liegen müssen, um
# als ein Ort zu gelten (siehe _verschmelze_nachbarn).
NACHBAR_MAX_KM = 20.0


def _mittelpunkt(eintrag: dict) -> Tuple[float, float]:
    n = len(eintrag["lats"])
    return sum(eintrag["lats"]) / n, sum(eintrag["lons"]) / n


def _verschmelze_nachbarn(gruppen: Dict[Tuple[str, str], dict]) -> None:
    """Fasst gleichnamige Gruppen zusammen, die nebeneinander liegen.

    Gruppiert wird nach Name + Bundesland, weil zwei "Neustadt" in
    verschiedenen Ländern verschiedene Orte sind. Postleitzahlbezirke
    halten sich aber nicht an Landesgrenzen: die PLZ 22113 liegt teils
    in Hamburg, teils in Schleswig-Holstein - "Hamburg" stand deshalb
    zweimal in der Auswahl, 4 km auseinander. Was näher als
    NACHBAR_MAX_KM beieinander liegt, wird zu einem Eintrag; den Namen
    und die Region gibt die Gruppe mit den meisten Postleitzahlen vor.
    """
    nach_namen: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for schluessel in gruppen:
        nach_namen[schluessel[0]].append(schluessel)

    for schluessel_liste in nach_namen.values():
        if len(schluessel_liste) < 2:
            continue
        # Größte Gruppe zuerst, damit sie Name und Region vorgibt.
        schluessel_liste.sort(key=lambda k: -len(gruppen[k]["plz"]))
        behalten: List[Tuple[str, str]] = []
        for schluessel in schluessel_liste:
            eintrag = gruppen[schluessel]
            lat, lon = _mittelpunkt(eintrag)
            ziel = next(
                (k for k in behalten
                 if _entfernung_km(lat, lon, *_mittelpunkt(gruppen[k])) <= NACHBAR_MAX_KM),
                None,
            )
            if ziel is None:
                behalten.append(schluessel)
                continue
            gruppen[ziel]["lats"].extend(eintrag["lats"])
            gruppen[ziel]["lons"].extend(eintrag["lons"])
            gruppen[ziel]["plz"].update(eintrag["plz"])
            del gruppen[schluessel]


def sammle_orte(cc: str, cache_dir: str) -> List[dict]:
    """Ein Eintrag je (Ortsname, Bundesland/Kanton) mit allen PLZ dazu.

    Dieselbe Stadt taucht in der PLZ-Datei einmal pro Postleitzahl auf
    (Berlin ~190-mal). Zusammengefasst wird auf Name + admin1: ein
    "Neustadt" in Bayern und eines in Sachsen bleiben getrennt, sonst
    läge der Ausgangspunkt der Umkreissuche irgendwo dazwischen.
    """
    text = _entpacke(_lade(ZIP_URL.format(cc=cc), cache_dir), f"{cc}.txt")
    index = gazetteer(cc, cache_dir)

    gruppen: Dict[Tuple[str, str], dict] = {}
    for zeile in text.splitlines():
        f = zeile.split("\t")
        if len(f) < 12:
            continue
        plz, name, region, admin1 = f[1].strip(), f[2].strip(), f[3].strip(), f[4].strip()
        if not plz or not name or _ist_firma(name, streng=cc in ORTSBEZUG_PRUEFEN):
            continue
        try:
            lat, lon = float(f[9]), float(f[10])
        except ValueError:
            continue
        schluessel = (normalisiere(name), admin1)
        eintrag = gruppen.get(schluessel)
        if eintrag is None:
            eintrag = gruppen[schluessel] = {
                "name": name, "land": cc, "region": region,
                "lats": [], "lons": [], "plz": set(),
            }
        eintrag["lats"].append(lat)
        eintrag["lons"].append(lon)
        eintrag["plz"].add(plz)

    _verschmelze_nachbarn(gruppen)

    orte = []
    for eintrag in gruppen.values():
        n = len(eintrag["lats"])
        # Mittelpunkt aller Postleitzahlbezirke des Ortes. Für eine
        # Umkreissuche ab 1 km ist das genau genug; auf drei
        # Nachkommastellen gerundet sind das ~100 m.
        lat = round(sum(eintrag["lats"]) / n, 3)
        lon = round(sum(eintrag["lons"]) / n, 3)
        if cc in ORTSBEZUG_PRUEFEN and not _hat_ortsbezug(index, eintrag["name"], lat, lon):
            continue
        # Einwohnerzahl: erst unter den echten Orten suchen; nur wenn dort
        # nichts in der Nähe liegt, zählt die gleichnamige
        # Verwaltungseinheit (so bekommt Wien seine Einwohnerzahl).
        treffer = _in_der_naehe(index, eintrag["name"], lat, lon, GAZETTEER_MAX_KM)
        orte_treffer = [k for k in treffer if k[3]]
        einwohner = max((k[2] for k in (orte_treffer or treffer)), default=0)
        orte.append({
            "name": eintrag["name"],
            "land": eintrag["land"],
            "region": eintrag["region"],
            "lat": lat,
            "lon": lon,
            "einwohner": einwohner,
            "plz": sorted(eintrag["plz"]),
        })
    return orte


def baue(cache_dir: str) -> dict:
    alle: List[dict] = []
    for cc in LAENDER:
        orte = sammle_orte(cc, cache_dir)
        print(f"  {cc}: {len(orte)} Orte, {sum(len(o['plz']) for o in orte)} PLZ-Zuordnungen")
        alle.extend(orte)

    # Größte Orte zuerst: Die Trefferliste im Browser übernimmt diese
    # Reihenfolge bei gleichwertigen Treffern, ohne selbst sortieren zu
    # müssen.
    alle.sort(key=lambda o: (-o["einwohner"], normalisiere(o["name"])))

    regionen: List[str] = []
    region_idx: Dict[str, int] = {}
    zeilen = []
    for o in alle:
        if o["region"] not in region_idx:
            region_idx[o["region"]] = len(regionen)
            regionen.append(o["region"])
        zeilen.append([
            o["name"],
            LAENDER.index(o["land"]),
            region_idx[o["region"]],
            o["lat"],
            o["lon"],
            o["einwohner"],
            " ".join(o["plz"]),
        ])

    return {
        "quelle": "GeoNames (https://www.geonames.org), CC BY 4.0",
        "erstellt": date.today().isoformat(),
        "laender": LAENDER,
        "regionen": regionen,
        "orte": zeilen,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Ortsverzeichnis (places.json) aus GeoNames bauen")
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "places.json"))
    p.add_argument("--cache-dir", default=os.path.join(os.path.dirname(__file__), "..", ".geonames-cache"))
    args = p.parse_args()

    print("Baue Ortsverzeichnis aus GeoNames-Daten …")
    daten = baue(args.cache_dir)
    ziel = os.path.abspath(args.out)
    with open(ziel, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, ensure_ascii=False, separators=(",", ":"))
    groesse = os.path.getsize(ziel) / 1024
    print(f"{len(daten['orte'])} Orte → {ziel} ({groesse:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
