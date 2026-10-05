#!/usr/bin/env python3
"""Gedächtnis je Veranstaltung, OHNE Datum: welche Veranstalterseite gehört
zu welchem Lauf - über den Jahreswechsel hinweg.

Warum es das gibt (vom Nutzer am 05.10.2026 gefragt: „Wie merkst du dir
alle Webseiten? Wenn der Lauf rausgenommen wird, weil er vorbei ist …"):
Jeder geprüfte Link stand bis dahin nur in `manual_overrides.json`, und
dort hängt er am Schlüssel `<Name>|<Datum>`. Kommt die Ausgabe 2027
derselben Veranstaltung über einen Scraper mit Portallink herein, greift
der Override nicht mehr (anderes Datum), die alte Zeile ist längst als
vergangen gelöscht (Datenregel 10), und die Linkarbeit vom Vorjahr ist
für diesen Lauf verloren. Am 05.10.2026 zeigten von 894 Link-Overrides
schon 194 auf vergangene Termine.

Was die Datei `scripts/veranstalter_seiten.json` enthält:

    "<kern>|<ort>": {
      "url": "https://…",            die Veranstalterseite (nie ein Portal)
      "name": "49. Nat. Nikolaus Volkslauf",   der zuletzt gesehene Name
      "standort": "Bad Schönborn", "lat": …, "lon": …,
      "datum": "2026-12-06",         die jüngste Ausgabe, von der gelernt wurde
      "quelle": "override" | "quelle" | "zurueckgezogen" | "tot",
                                     Einzelprüfung, vom Scraper geliefert, die Seite wurde
                                     für diese Ausgabe entfernt (url null), oder `pruefen`
                                     hat sie zweimal als tot vorgefunden (url null, url_tot)
      "konflikt": ["…", "…"],        statt url: zwei Seiten, keine entscheidbar
      "fest": true,                  von Hand gesetzt - lernen() fasst es nicht an
      "art1": "Laufen", "land": "Deutschland",
      "strecken": [ {"laenge_km": 10, "dauer_h": null, "wettbewerb": "10 km", "art2": "Straße"}, … ],
      "strecken_datum": "2026-12-06",  die Strecken der jüngsten Ausgabe und ihr Starttag (05.10.2026)
      "geprueft_am": "2027-03-02",   wann `pruefen` die Seite zuletzt abgerufen hat
      "uebernommen": "2027-06-13",   welche Ausgabe `pruefen --uebernehmen` angelegt hat
      "strecken_uebernommen": true,  die Strecken sind die eigene Vorjahreskopie (keine Quelle)
      "tot_zaehler": 1,              so oft in Folge war die Seite weg (404/410, Host weg)
      "url_tot": "https://…"         bei `quelle` tot: die Adresse, die es nicht mehr gibt
    }

Seit dem 05.10.2026 steht JEDE Veranstaltung im Gedächtnis, auch eine
ohne eigene Seite (`url` null, kein `konflikt`) - der Nutzer will „eine
Liste mit allen Events": Was einmal drin war, bleibt bekannt, mit seinen
Strecken, seinem Ort und seiner Sportart. Vom Nutzer so entschieden
(„bau ein Gedächtnis je Veranstaltung, aber ohne das Datum … damit
werden dann die alten Daten mit den neuen abgeglichen"):

Der SCHLÜSSEL ist der Kern des Namens ohne Auflage, Jahr, Ort und
Ortsadjektiv (`scraper_lib._kern_tokens()`, dieselbe Rechnung wie beim
siebten Weg der Duplikat-Erkennung) plus der Ort als Wortmenge. „49. Nat.
Nikolaus Volkslauf 2026" und „50. Nat. Nikolaus Volkslauf 2027" in Bad
Schönborn sind damit EIN Eintrag. Beim Nachschlagen genügt es, wenn die
Ortswörter der einen Seite in denen der anderen stecken („Kressbronn" in
„Kressbronn am Bodensee") oder die Koordinaten höchstens 3 km auseinander
liegen - AUSSER der Kern besteht nur aus Allerweltswörtern („Crosslauf",
„Silvesterlauf"): Dann muss der Ort wörtlich derselbe sein, sonst bekäme
der Gillrather Crosslauf (Geilenkirchen-Gillrath) die Seite des
Geilenkirchener Crosslaufs.

Drei Schritte, alle in `clean_events.py` eingehängt (nach den Overrides,
VOR dem Entfernen vergangener Events - die vergangene Zeile bringt dem
Gedächtnis ihre Seite bei, bevor sie geht):

  lernen()    jede Zeile mit eigener Seite schreibt sie ins Gedächtnis.
              Vorrang: ein per Override belegter Link vor einem vom
              Scraper gelieferten; bei gleichem Rang gewinnt die jüngere
              Ausgabe (ein Sponsorwechsel wechselt die Domain:
              brooks-ruhr-trail-run.de -> altra-ruhr-trail-run.de).
              Gleicher Rang, gleiche Ausgabe, verschiedene Hosts (36 Fälle
              am Bestand, fast alle dieselbe Veranstaltung unter zwei
              Namen) -> `konflikt`, es wird nichts angewendet. Setzt ein
              Override `veranstalter_url: null` (der Link war FALSCH, wie
              pfingstlauf.de beim Langeneicker Pfingstlauf), verliert der
              Eintrag seine SEITE - nicht seine Strecken (`quelle`
              override, url null). Und trägt die Ausgabe, die der
              Eintrag kennt, auf KEINER Zeile mehr eine eigene Seite,
              gilt sie als ZURÜCKGEZOGEN (`quelle` zurueckgezogen, url
              null): Jemand hat sie bewusst entfernt (tv-albig.de war
              der Verein, nicht der Doppelzwölfer), das Gedächtnis gibt
              sie nicht an die nächste Ausgabe weiter. Am 05.10.2026
              traf das 7 Einträge aus den alten Ständen.
  anwenden()  jede Zeile OHNE eigene Seite (kein Link, Portallink,
              soziales Netz) bekommt die gemerkte Seite - aber nur von
              einer FRÜHEREN Ausgabe, nie von derselben (siehe oben) und
              nie von einer späteren (Serie mit mehreren Terminen unter
              einem Namen). Deshalb läuft es in clean_events.py VOR
              lernen(). Eine vorhandene eigene Seite wird nie
              überschrieben (dieselbe Sperre wie in `apply_overrides()`),
              und ein Override mit `veranstalter_url: null` sperrt die
              Zeile. Fehlen der Zeile die Koordinaten, kommen auch die
              der vorigen Ausgabe (derselbe Ort).
  abgleich_vorjahr()  meldet je Veranstaltung, welche Strecken der
              vorigen Ausgabe in der neuen fehlen („Vorjahr hatte 5, 10
              und 21,1 km, jetzt nur 10 km") - nur Bericht, Strecken
              ändern sich von Jahr zu Jahr. Läuft VOR lernen(), sonst
              hätte das Gedächtnis die neue Ausgabe schon gelernt.
  pruefen     ruft die Seiten der Veranstaltungen ab, die im Gedächtnis
              stehen, aber KEINE Zeile mehr in events.json haben - also
              vorbei sind und deren nächste Ausgabe noch in keiner Quelle
              steht - und sucht einen künftigen Termin, der zur vorigen
              Ausgabe passt (10 bis 14 Monate später, siehe
              `kandidaten_termine()`), auf einer Seite, die den Lauf am
              Namen nennt (`nennt_den_lauf()`). Jede Seite höchstens alle
              `PRUEF_ABSTAND_TAGE` Tage (`geprueft_am`), die ältesten
              zuerst; `--max` begrenzt den Lauf.
              Mit `--uebernehmen` wird ein EINDEUTIGER Fund (genau ein
              Termin bzw. eine zusammenhängende Spanne bis 3 Tage) als
              neue Ausgabe in `manual_events.json` eingetragen - mit den
              Strecken der vorigen Ausgabe, der Seite als `_quelle` und
              einer Notiz; `clean_events.py` nimmt sie beim nächsten Lauf
              auf. Mehrdeutige Funde („NEU?") bleiben im Bericht für die
              Handprüfung. So läuft es wöchentlich in `update_events.py`
              (vom Nutzer am 05.10.2026 gewünscht: „auf den Webseiten in
              der Vergangenheit soll auch ab und zu gecheckt werden, ob
              denn das neue Event schon rausgekommen ist").

    python3 scripts/veranstalter_seiten.py aufbauen [--alt alter-stand.json …]
    python3 scripts/veranstalter_seiten.py pruefen --bericht bericht.json [--fortsetzen] [--max N] [--uebernehmen]
    python3 scripts/veranstalter_seiten.py zeigen <Suchwort>

`aufbauen` lernt aus events.json und zusätzlich aus älteren Ständen der
Datei (`git show <commit>:events.json > alt.json`) - so kamen am
05.10.2026 die 171 Veranstaltungen zurück, deren Link-Override schon ins
Leere lief. Danach schreibt `clean_events.py` die Datei bei jedem Lauf
fort; `update_events.py` legt sie in GitHub Actions mit in den Commit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from scraper_lib import (  # noqa: E402
    _haversine_km, _kern_tokens, find_override, is_portal_link,
    load_manual_overrides, normalize_event_name,
)
from veranstalter_links import ALLGEMEIN, host_von, kein_veranstalter  # noqa: E402

PFAD = REPO / "scripts" / "veranstalter_seiten.json"
EVENTS = REPO / "events.json"
MANUAL_EVENTS = REPO / "scripts" / "manual_events.json"
PRUEFUNG = REPO / "scripts" / "veranstalter_seiten_pruefung.json"
# Eine Seite wird höchstens alle drei Wochen abgerufen - Veranstalter
# schreiben den nächsten Termin nicht über Nacht, und der wöchentliche
# Lauf soll nicht jede Woche dieselben 4.000 Seiten holen.
PRUEF_ABSTAND_TAGE = 21
# Die nächste Ausgabe liegt erfahrungsgemäß ein Jahr nach der vorigen:
# 10 bis 14 Monate danach ist ein Termin plausibel, alles andere auf der
# Seite (Trainingstermine, Vereinsfeste, Folgejahre) nicht.
FENSTER_TAGE = (300, 430)
README = ("Gedächtnis je Veranstaltung OHNE Datum (scripts/veranstalter_seiten.py): "
          "Schlüssel '<Kern des Namens>|<Ort als Wortmenge>', Wert die Veranstalterseite. "
          "Geschrieben von clean_events.py (lernen), gelesen von clean_events.py (anwenden): "
          "Eine neue Ausgabe mit Portallink bekommt die Seite der vorigen. "
          "'quelle' = override (Einzelprüfung), quelle (vom Scraper geliefert), zurueckgezogen (die Ausgabe trägt die Seite nicht mehr, url leer) oder tot (pruefen fand sie zweimal nicht, url leer, alte Adresse in url_tot); 'konflikt' statt 'url' = "
          "zwei Seiten, keine entscheidbar, nichts wird angewendet; 'fest': true = von Hand gesetzt, lernen() lässt den Eintrag in Ruhe. "
          "'strecken'/'art1'/'land' = die jüngste Ausgabe ('strecken_datum' ihr Starttag), gelernt auch ohne Seite; "
          "'geprueft_am'/'uebernommen' setzt `pruefen` (Suche nach der nächsten Ausgabe auf der Veranstalterseite). "
          "Die Einträge sind nach Schlüssel sortiert, damit der Diff je Lauf klein bleibt.")

# Monatsnamen für Datumsangaben im Seitentext (auch von seitenabgleich.py
# genutzt - EINE Tabelle für beide). Deutsch, Englisch, Französisch und
# Italienisch: Die Schweizer Seiten (Romandie, Tessin) und die Südtiroler
# schreiben „12 octobre 2027" bzw. „12 ottobre 2027" - bis zum
# 05.10.2026 las die Prüfung dort kein einziges Datum (NICHTS statt NEU).
MONATE = {m: i + 1 for i, m in enumerate(
    ["januar", "februar", "marz", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "dezember"])}
MONATE.update({m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"])})
MONATE.update({m: i + 1 for i, m in enumerate(
    ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
     "septembre", "octobre", "novembre", "decembre"])})
MONATE.update({m: i + 1 for i, m in enumerate(
    ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
     "settembre", "ottobre", "novembre", "dicembre"])})
MONATE.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
               "sep": 9, "sept": 9, "okt": 10, "oct": 10, "nov": 11, "dez": 12, "dec": 12,
               "maerz": 3, "fevr": 2, "juil": 7, "dic": 12, "gen": 1, "mag": 5, "giu": 6,
               "lug": 7, "ago": 8, "set": 9, "ott": 10, "dic.": 12})


def _datum(j: str, m: int, t: str) -> str | None:
    if 1 <= m <= 12 and 1 <= int(t) <= 31:
        return f"{j}-{m:02d}-{int(t):02d}"
    return None


def daten_aus(txt: str) -> set[str]:
    """Alle Datumsangaben im (normalisierten) Seitentext als ISO-Daten:
    „12.10.2026", „12.10.26", „12/10/2026", „12. Oktober 2026",
    „12 octobre 2026", „12 ottobre 2026", „October 12, 2026", „2026-10-12".

    Das zweistellige Jahr („12.10.26") zählt nur ohne weitere Ziffer oder
    Punkt dahinter - „12.10.26.“ und „1.2.26 Uhr“ wären sonst Daten; und
    nur 2020–2039, damit „1.2.03" keine Jahresangabe wird."""
    out = set()
    for t, m, j in re.findall(r"\b(\d{1,2})[./]\s?(\d{1,2})[./]\s?(20\d{2})\b", txt):
        d = _datum(j, int(m), t)
        if d:
            out.add(d)
    for t, m, j in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.([23]\d)\b(?![.:\d])", txt):
        d = _datum("20" + j, int(m), t)
        if d:
            out.add(d)
    for t, m, j in re.findall(r"\b(\d{1,2})\.?\s?([a-z]{3,9})\.?\s?(20\d{2})\b", txt):
        if m in MONATE:
            d = _datum(j, MONATE[m], t)
            if d:
                out.add(d)
    for m, t, j in re.findall(r"\b([a-z]{3,9})\.?\s(\d{1,2})(?:st|nd|rd|th)?,?\s(20\d{2})\b", txt):
        if m in MONATE:
            d = _datum(j, MONATE[m], t)
            if d:
                out.add(d)
    for j, m, t in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", txt):
        d = _datum(j, int(m), t)
        if d:
            out.add(d)
    return out


def distanzen_aus(txt: str) -> set[float]:
    """Alle Kilometerangaben im (normalisierten) Seitentext, gerundet auf
    eine Stelle: „10 km", „21,1 km", „1500 m" (300–5000 m als Kilometer),
    dazu 21,1 für „Halbmarathon" und 42,2 für „Marathon" (nicht hinter
    „Halb"). Seit dem 05.10.2026 hier und nicht mehr in seitenabgleich.py -
    das Gedächtnis prüft damit, ob die Strecken des Vorjahrs auf der Seite
    noch stehen (ein 10-km-Lauf kann ein Halbmarathon geworden sein)."""
    out: set[float] = set()
    for z in re.findall(r"\b(\d{1,3}(?:[.,]\d{1,3})?)\s?(?:km|kilometer)\b", txt):
        try:
            out.add(round(float(z.replace(",", ".")), 1))
        except ValueError:
            pass
    for z in re.findall(r"\b(\d{1,2}\.\d{3}|\d{3,5})\s?(?:m|meter)\b", txt):
        v = int(z.replace(".", ""))
        if 300 <= v <= 5000:
            out.add(round(v / 1000, 1))
    if re.search(r"\bhalbmarathon|\bhalf marathon|\bsemi-?marathon|\bmezza maratona|\b21[.,]1\b|\b21[.,]0975", txt):
        out.add(21.1)
    if re.search(r"(?<!halb)(?<!half )(?<!semi-)(?<!semi )marathon|(?<!mezza )\bmaratona\b", txt):
        out.add(42.2)
    return out


def km_passt(km: float, gefunden) -> bool:
    """Steht `km` unter den gefundenen Angaben? ±0,15 km, oder gleiche
    gerundete Zahl bei weniger als 0,6 km Abstand („10,5" zu „10")."""
    return any(abs(km - g) <= 0.15 or (abs(km - g) < 0.6 and abs(round(km) - round(g)) == 0) for g in gefunden)


# --------------------------------------------------------------------------
# Schlüssel
# --------------------------------------------------------------------------

def eigene_seite(url: str | None) -> bool:
    """True, wenn `url` als Veranstalterseite zählt: vorhanden, kein
    Portal/Zeitnehmer/Kalender (PORTAL_DOMAINS), kein soziales Netz."""
    return bool(url) and not is_portal_link(url) and not kein_veranstalter(url)


def kern_von(event: dict) -> str:
    """Der Kern des Namens als sortierte Wortfolge - leer, wenn vom Namen
    nach Auflage, Jahr und Ort nichts bleibt („Lauf in Dorf")."""
    return " ".join(sorted(_kern_tokens(event)))


def ort_von(event: dict) -> frozenset:
    return frozenset(normalize_event_name(event.get("standort") or "").split())


# Wörter, die eine andere VERANSTALTUNG anzeigen, wenn sie nur auf einer
# Seite stehen - ein Sponsor heißt nie so. Für die unscharfe Suche nach
# dem Schlüssel (`Gedaechtnis._kandidaten`).
_FORMATWOERTER = {
    "triathlon", "duathlon", "aquathlon", "swimrun", "quadrathlon", "marathon",
    "halbmarathon", "ultra", "ultralauf", "ultramarathon", "ultratrail", "trail",
    "trailrun", "cross", "crosslauf", "berglauf", "staffel", "staffellauf", "walking",
    "nordic", "wandern", "wanderung", "kinderlauf", "schuelerlauf", "jugendlauf",
    "backyard", "gravel", "mtb", "mountainbike", "rennrad", "rtf", "ctf", "radmarathon",
    "schwimmen", "freiwasser", "winterloop", "probelauf", "nachtlauf", "sprint",
    "kids", "junior", "mini", "bambini", "firmenlauf", "frauenlauf",
}


def _unterscheidend(wort: str) -> bool:
    """Ein Wort, das eine Veranstaltung von anderen am selben Ort
    unterscheidet: kein Allerweltswort (`ALLGEMEIN`), mindestens vier
    Buchstaben, keine Zahl."""
    return len(wort) >= 4 and wort not in ALLGEMEIN and not wort.isdigit()


def generisch(kern: str) -> bool:
    """Ein Kern nur aus Allerweltswörtern („crosslauf", „silvesterlauf
    volkslauf") unterscheidet Veranstaltungen nicht - dann zählt der Ort
    wörtlich, nicht als Teilmenge (siehe Modulkopf)."""
    woerter = kern.split()
    return not woerter or not any(_unterscheidend(w) for w in woerter)


def schluessel_von(event: dict) -> str | None:
    kern, ort = kern_von(event), ort_von(event)
    if not kern or not ort:
        return None
    return f"{kern}|{' '.join(sorted(ort))}"


def _ort_passt(a: frozenset, b: frozenset, streng: bool) -> bool:
    if streng:
        return a == b
    return bool(a and b and (a <= b or b <= a))


def _koordinaten_nah(event: dict, eintrag: dict) -> bool:
    c = (event.get("lat"), event.get("lon"), eintrag.get("lat"), eintrag.get("lon"))
    return all(isinstance(x, (int, float)) for x in c) and _haversine_km(*c) <= 3


def _jahresabstand(a: str | None, b: str | None) -> bool:
    """Liegen die beiden Tage etwa ganze Jahre auseinander (mindestens
    eines, je ±65 Tage um das Vielfache von 365)?"""
    from datetime import date
    try:
        d = abs((date.fromisoformat(a or "") - date.fromisoformat(b or "")).days)
    except ValueError:
        return False
    return d >= FENSTER_TAGE[0] and (d % 365 <= 65 or d % 365 >= 300)


def _rang(quelle: str) -> int:
    return 1 if quelle == "override" else 0


STRECKEN_FELDER = ("laenge_km", "dauer_h", "wettbewerb", "art2")


def strecke_von(event: dict) -> OrderedDict:
    return OrderedDict((f, event.get(f)) for f in STRECKEN_FELDER)


def _strecken_sortiert(strecken) -> list:
    def key(s):
        km, h = s.get("laenge_km"), s.get("dauer_h")
        return (0, km) if isinstance(km, (int, float)) else (1, h) if isinstance(h, (int, float)) else (2, 0)
    return sorted(strecken, key=lambda s: (key(s), s.get("wettbewerb") or ""))


def masszahl(strecke: dict) -> str:
    km, h = strecke.get("laenge_km"), strecke.get("dauer_h")
    if isinstance(km, (int, float)):
        return f"{km:g} km"
    if isinstance(h, (int, float)):
        return f"{h:g} h"
    return strecke.get("wettbewerb") or "ohne Maßzahl"


def _masszahl_schluessel(strecke: dict):
    km, h = strecke.get("laenge_km"), strecke.get("dauer_h")
    if isinstance(km, (int, float)):
        return ("km", round(float(km), 1))
    if isinstance(h, (int, float)):
        return ("h", round(float(h), 2))
    return None


# --------------------------------------------------------------------------
# Das Gedächtnis
# --------------------------------------------------------------------------

class Gedaechtnis:
    def __init__(self, daten: dict | None = None):
        self.daten: dict[str, dict] = {k: v for k, v in (daten or {}).items() if k != "_readme"}
        self._index: dict[str, list[tuple[str, frozenset]]] | None = None
        self._wort_index: dict[str, list[str]] = {}

    # -- Datei ------------------------------------------------------------
    @classmethod
    def laden(cls, pfad: Path = PFAD) -> "Gedaechtnis":
        if not pfad.exists():
            return cls({})
        return cls(json.loads(pfad.read_text(encoding="utf-8")))

    def speichern(self, pfad: Path = PFAD) -> None:
        # Je Veranstaltung EINE Zeile: Ein Datenlauf ändert ein paar
        # hundert Einträge, und der Diff soll je Veranstaltung eine Zeile
        # zeigen, nicht je Feld eine (die Datei hat ~4.400 Einträge, ~2 MB).
        zeilen = [' "_readme": ' + json.dumps(README, ensure_ascii=False)]
        for k in sorted(self.daten, key=str.casefold):
            zeilen.append(f' {json.dumps(k, ensure_ascii=False)}: {json.dumps(self.daten[k], ensure_ascii=False)}')
        pfad.write_text("{\n" + ",\n".join(zeilen) + "\n}\n", encoding="utf-8")

    def __len__(self) -> int:
        return len(self.daten)

    # -- Nachschlagen -----------------------------------------------------
    def _idx(self) -> dict[str, list[tuple[str, frozenset]]]:
        if self._index is None:
            idx: dict[str, list[tuple[str, frozenset]]] = {}
            woerter: dict[str, list[str]] = {}
            for k in self.daten:
                kern, _, ort = k.partition("|")
                idx.setdefault(kern, []).append((k, frozenset(ort.split())))
                for w in kern.split():
                    if _unterscheidend(w):
                        woerter.setdefault(w, []).append(k)
            self._index = idx
            self._wort_index = woerter
        return self._index

    def _kandidaten(self, event: dict) -> list[str]:
        """Die Schlüssel, die zu dieser Zeile passen: gleicher Kern und
        passender Ort (oder Koordinaten ≤ 3 km). Findet das nichts, zählt
        auch ein Kern, der im anderen ENTHALTEN ist - derselbe Gedanke wie
        der siebte Weg der Duplikat-Erkennung (Datenregel 7): „SAARathon"
        in „Sparkassen-SAARathon", „Frauenlauf" in „Vitamin Well
        Frauenlauf". Ein Sponsorwechsel oder ein neu aufgesetzter Kalender
        ändert den Namen, nicht die Veranstaltung; bis zum 05.10.2026 war
        das ein zweiter Eintrag ohne Seite und ohne Vorjahr. Drei
        Bedingungen: die kleinere Wortmenge enthält mindestens ein
        unterscheidendes Wort (kein Allerweltswort, `_unterscheidend`), der
        Ort passt wie sonst auch, und die Zeile liegt etwa GANZE JAHRE von
        der gemerkten Ausgabe entfernt (`_jahresabstand`). Ohne die dritte
        Bedingung hätte die Regel am Bestand den „Ironman 5150 Erkner" mit
        dem „Ironman 70.3 Erkner" am Folgetag, die „Crossmania Series #3"
        mit „#5" und den „itdesign-Nikolauslauf" mit seinem Probelauf
        verschmolzen - Geschwister einer Serie liegen Tage auseinander, die
        nächste Ausgabe ein Jahr."""
        kern = kern_von(event)
        if not kern:
            return []
        ort = ort_von(event)
        streng = generisch(kern)
        treffer = []
        for k, ort_k in self._idx().get(kern, []):
            if _ort_passt(ort, ort_k, streng) or (not streng and _koordinaten_nah(event, self.daten[k])):
                treffer.append(k)
        if treffer:
            return treffer
        woerter = frozenset(kern.split())
        gesehen: set[str] = set()
        for w in woerter:
            for k in self._wort_index.get(w, []):
                if k in gesehen:
                    continue
                gesehen.add(k)
                kern_k, _, ort_k = k.partition("|")
                menge_k = frozenset(kern_k.split())
                kleiner = menge_k if menge_k < woerter else woerter if woerter < menge_k else None
                if kleiner is None or not any(_unterscheidend(x) for x in kleiner):
                    continue
                unterschied = menge_k ^ woerter
                if any(x.isdigit() or x in _FORMATWOERTER for x in unterschied):
                    # Eine Zahl oder ein Sportwort im Unterschied ist eine
                    # Serie oder ein anderes Format („Ironman 5150", „Vienna
                    # Triathlon" neben „Run Vienna"), kein Sponsor.
                    continue
                art1_k = self.daten[k].get("art1")
                if art1_k and event.get("art1") and art1_k != event.get("art1"):
                    continue
                if not _jahresabstand(event.get("datum_start"), self.daten[k].get("datum")):
                    continue
                if _ort_passt(ort, frozenset(ort_k.split()), False) or _koordinaten_nah(event, self.daten[k]):
                    treffer.append(k)
        return treffer

    def schluessel_fuer(self, event: dict) -> str | None:
        """Der Schlüssel, unter dem diese Zeile GELERNT wird: der eigene,
        wenn er schon dasteht oder nichts anderes passt; sonst der eine
        Eintrag, dessen Kern im Namen steckt (oder umgekehrt). Ist der
        Kern der Zeile der KLEINERE, wandert der Eintrag auf ihn um:
        „saarathon" bleibt stabil, „sparkassen saarathon" nicht - der
        nächste Sponsor hieße sonst wieder anders."""
        k = schluessel_von(event)
        if not k:
            return None
        if k in self.daten:
            return k
        kand = self._kandidaten(event)
        if len(kand) != 1:
            return k
        alt = kand[0]
        kern, _, _ = k.partition("|")
        kern_alt, _, _ = alt.partition("|")
        if frozenset(kern.split()) < frozenset(kern_alt.split()):
            self.daten[k] = self.daten.pop(alt)
            self._index = None
            return k
        return alt

    def finde(self, event: dict) -> dict | None:
        """Der Eintrag zu dieser Zeile - oder None, wenn keiner passt oder
        mehr als einer passt. Ob er eine Seite kennt, sagt `url`."""
        kand = self._kandidaten(event)
        if len(kand) != 1:
            return None
        return self.daten[kand[0]]

    # -- Die Daten einer Ausgabe: Strecken, Sportart, Ort ----------------
    def lerne_ausgabe(self, k: str, zeilen: list[dict]) -> str | None:
        """Merkt sich die Strecken, Sportart und Lage der jüngsten Ausgabe
        unter dem Schlüssel `k` (alle `zeilen` tragen denselben Starttag).
        Eine ältere Ausgabe überschreibt nie eine jüngere."""
        datum = zeilen[0].get("datum_start") or ""
        alt = self.daten.get(k)
        if alt is None:
            alt = self.daten[k] = OrderedDict([("url", None), ("name", zeilen[0].get("name")),
                                               ("standort", zeilen[0].get("standort")),
                                               ("lat", zeilen[0].get("lat")), ("lon", zeilen[0].get("lon")),
                                               ("datum", datum), ("quelle", "quelle")])
            self._index = None
            neu = True
        else:
            neu = False
            if datum < (alt.get("datum") or ""):
                return None
        # Zeilen, die das Gedächtnis selbst angelegt hat (`gedaechtnis`,
        # Strecken des Vorjahrs), zählen nur, solange keine Quelle die
        # Ausgabe liefert - sonst lernte es seine eigene Kopie zurück.
        echte = [z for z in zeilen if not z.get("gedaechtnis")]
        uebernommen = not echte
        zeilen = echte or zeilen
        # Schlüssel ist die STRECKE (Länge, Dauer, Label), nicht der ganze
        # Eintrag: Korrigiert ein Override nur die Kategorie einer Strecke,
        # ersetzt die neue Angabe die alte, statt neben ihr zu stehen (am
        # XTERRA Trail de la Vallée de Joux, 05.10.2026: jede Strecke
        # zweimal, einmal "Cross", einmal "Trail").
        def strecken_key(st):
            return json.dumps([st.get("laenge_km"), st.get("dauer_h"), st.get("wettbewerb")],
                              ensure_ascii=False)
        gesammelt = {strecken_key(strecke_von(z)): strecke_von(z) for z in zeilen}
        if (not neu and datum == alt.get("strecken_datum")
                and alt.get("art1") == zeilen[0].get("art1")
                and not (alt.get("strecken_uebernommen") and not uebernommen)):
            # Dieselbe Ausgabe noch einmal (zweiter Durchgang, Teilmenge der
            # Zeilen): Strecken VEREINIGEN, nicht ersetzen - sonst nähme ein
            # Aufruf mit einer Zeile der Veranstaltung alle anderen weg.
            # Verglichen wird mit `strecken_datum`, nicht mit `datum`: Das
            # hat lerne() für eine Zeile mit Seite schon auf die neue
            # Ausgabe gesetzt, die Strecken gehören aber noch zur alten.
            # AUSSER die gemerkten Strecken waren die eigene Vorjahreskopie
            # und jetzt liefert eine Quelle die Ausgabe: dann ersetzen.
            for st in alt.get("strecken") or []:
                gesammelt.setdefault(strecken_key(st), st)
        strecken = _strecken_sortiert(gesammelt.values())
        geaendert = neu or alt.get("strecken") != strecken or alt.get("art1") != zeilen[0].get("art1")
        alt["strecken_datum"] = datum
        if uebernommen:
            alt["strecken_uebernommen"] = True
        else:
            alt.pop("strecken_uebernommen", None)
        alt["art1"] = zeilen[0].get("art1")
        alt["land"] = zeilen[0].get("land")
        alt["strecken"] = strecken
        if datum > (alt.get("datum") or "") or not alt.get("url"):
            # Name, Ort und Lage der jüngsten Ausgabe - bei einer Zeile mit
            # Seite hat lerne() das schon getan, dann nur nachziehen.
            alt["name"] = zeilen[0].get("name")
            alt["standort"] = zeilen[0].get("standort")
            if isinstance(zeilen[0].get("lat"), (int, float)):
                alt["lat"], alt["lon"] = zeilen[0].get("lat"), zeilen[0].get("lon")
            alt["datum"] = datum
        if neu:
            return f"{zeilen[0].get('name')} ({zeilen[0].get('standort')}): Veranstaltung gemerkt ({len(strecken)} Strecken, ohne Seite)"
        return f"{zeilen[0].get('name')}: Strecken der Ausgabe {datum} gemerkt ({len(strecken)})" if geaendert else None

    # -- Lernen -----------------------------------------------------------
    def lerne(self, event: dict, quelle: str) -> str | None:
        """Trägt die Seite dieser Zeile ein. Gibt eine Zeile für den Bericht
        zurück, wenn sich etwas geändert hat."""
        url = (event.get("veranstalter_url") or "").strip()
        if not eigene_seite(url):
            return None
        k = self.schluessel_fuer(event)
        if not k:
            return None
        datum = event.get("datum_start") or ""
        neu = OrderedDict([("url", url), ("name", event.get("name")), ("standort", event.get("standort")),
                           ("lat", event.get("lat")), ("lon", event.get("lon")),
                           ("datum", datum), ("quelle", quelle)])
        alt = self.daten.get(k)
        if alt is None:
            self.daten[k] = neu
            self._index = None
            return f"{event.get('name')} ({event.get('standort')}): Seite gemerkt ({host_von(url)})"
        if alt.get("fest"):
            return None
        alt_datum, alt_quelle = alt.get("datum") or "", alt.get("quelle") or "quelle"
        alt_url = alt.get("url")
        if alt.get("quelle") == "tot" and alt.get("url_tot") and host_von(alt["url_tot"]) == host_von(url):
            # Die tote Seite ist wieder da (eine Quelle liefert sie für die
            # jüngste Ausgabe): dann gilt sie wieder.
            self.daten[k] = neu
            return f"{event.get('name')}: Seite wieder da ({host_von(url)})"
        if alt_url and host_von(alt_url) == host_von(url):
            # Gleicher Host: Adresse, Name, Ausgabe und Rang nachziehen -
            # bei GLEICHER Ausgabe und gleichem Rang aber nur, wenn die
            # neue Schreibweise besser ist (https statt http). Sonst
            # schrieben zwei Zeilen derselben Veranstaltung mit
            # „teamoptimum.de/" und „www.teamoptimum.de" die Adresse bei
            # jedem Lauf hin und her (05.10.2026).
            if (datum, _rang(quelle)) > (alt_datum, _rang(alt_quelle)) or (
                    (datum, _rang(quelle)) == (alt_datum, _rang(alt_quelle))
                    and alt_url.startswith("http://") and url.startswith("https://")):
                geaendert = alt_url != url
                alt.update(neu)
                return (f"{event.get('name')}: Adresse aktualisiert ({url})" if geaendert else None)
            return None
        # Verschiedener Host (oder bisher Konflikt, oder tot): die JÜNGERE
        # Ausgabe gewinnt, bei derselben Ausgabe der Override. Bis zum
        # 05.10.2026 stand der Rang vorn - ein per Override belegter Link
        # der Ausgabe 2026 hätte dann die neu aufgesetzte Seite, die der
        # Scraper für 2027 liefert, nie zur Kenntnis genommen, und 2028
        # bekäme die tote Adresse. Was events.json für die jüngste Ausgabe
        # zeigt, zeigt auch das Gedächtnis; wer die Seite 2027 per Override
        # korrigiert, überschreibt sie damit wieder.
        if (datum, _rang(quelle)) > (alt_datum, _rang(alt_quelle)) or alt_quelle == "tot":
            alt_host = host_von(alt_url) if alt_url else ("Konflikt" if alt.get("konflikt") else
                                                          host_von(alt.get("url_tot") or "") or "keine")
            self.daten[k] = neu
            return f"{event.get('name')}: Seite ersetzt ({alt_host} -> {host_von(url)})"
        if (datum, _rang(quelle)) < (alt_datum, _rang(alt_quelle)):
            return None
        # Gleicher Rang, gleiche Ausgabe, anderer Host: nicht entscheidbar.
        konflikt = sorted(set((alt.get("konflikt") or []) + ([alt_url] if alt_url else []) + [url]))
        if alt.get("konflikt") == konflikt and not alt_url:
            return None
        self.daten[k] = OrderedDict([("url", None), ("konflikt", konflikt), ("name", event.get("name")),
                                     ("standort", event.get("standort")), ("lat", event.get("lat")),
                                     ("lon", event.get("lon")), ("datum", datum), ("quelle", quelle)])
        return f"{event.get('name')}: zwei Seiten, keine entscheidbar ({', '.join(host_von(u) for u in konflikt)})"

    def ziehe_zurueck(self, k: str, zeilen: list[dict], overrides: dict) -> str | None:
        """Die aktuelle Ausgabe trägt die gemerkte Seite nicht mehr - auf
        KEINER ihrer Zeilen, und kein Override setzt einen Link: Dann hat
        sie jemand bewusst entfernt (Einzelprüfung, Korrekturliste), und
        das Gedächtnis darf sie nicht an die nächste Ausgabe weitergeben.
        Nur für dieselbe Ausgabe, die der Eintrag kennt - eine ältere
        Zeile sagt nichts über den gemerkten Stand aus."""
        alt = self.daten.get(k)
        if alt is None or alt.get("fest") or not (alt.get("url") or alt.get("konflikt")):
            return None
        if (zeilen[0].get("datum_start") or "") != (alt.get("datum") or ""):
            return None
        if any(eigene_seite(z.get("veranstalter_url")) for z in zeilen):
            return None
        if any(_override_url(z, overrides)[1] for z in zeilen):
            return None
        host = host_von(alt["url"]) if alt.get("url") else "Konflikt"
        alt["url"] = None
        alt.pop("konflikt", None)
        alt["quelle"] = "zurueckgezogen"
        return f"{zeilen[0].get('name')} ({zeilen[0].get('standort')}): Seite zurückgezogen ({host} - die Ausgabe {alt.get('datum')} trägt sie nicht mehr)"

    def vergesse(self, event: dict) -> str | None:
        """Ein Override mit `veranstalter_url: null` nimmt dem Eintrag die
        SEITE - nicht den Eintrag: Strecken, Lage und Ausgabe bleiben
        (lerne_ausgabe legt ihn sonst gleich wieder an, und der Bericht
        meldete bei jedem Lauf „vergessen" und „gemerkt" im Wechsel)."""
        k = self.schluessel_fuer(event)
        alt = self.daten.get(k) if k else None
        if alt is None or alt.get("fest") or not (alt.get("url") or alt.get("konflikt")):
            return None
        alt["url"] = None
        alt.pop("konflikt", None)
        alt["quelle"] = "override"
        return f"{event.get('name')} ({event.get('standort')}): Seite vergessen (Override: kein Link)"


# --------------------------------------------------------------------------
# Die beiden Schritte für clean_events.py
# --------------------------------------------------------------------------

def _override_url(event: dict, overrides: dict) -> tuple[bool, str | None]:
    """(steht `veranstalter_url` im Override dieser Zeile?, der Wert)."""
    ov = find_override(overrides, event.get("name"), event.get("datum_start"),
                       event.get("laenge_km"), event.get("wettbewerb")) or {}
    return "veranstalter_url" in ov, ov.get("veranstalter_url")


def lernen(events: list[dict], ged: Gedaechtnis, overrides: dict | None = None) -> list[str]:
    """Jede Zeile mit eigener Seite bringt sie dem Gedächtnis bei; eine
    Zeile, deren Override den Link ausdrücklich löscht, lässt es vergessen."""
    overrides = load_manual_overrides() if overrides is None else overrides
    bericht: list[str] = []
    gesehen: set[tuple] = set()
    for e in events:
        gesetzt, wert = _override_url(e, overrides)
        if gesetzt and wert is None:
            z = ged.vergesse(e)
            if z:
                bericht.append(z)
            continue
        url = e.get("veranstalter_url")
        if not eigene_seite(url):
            continue
        marke = (ged.schluessel_fuer(e), url)
        if marke in gesehen:
            continue  # die Schwesterstrecken derselben Veranstaltung
        gesehen.add(marke)
        quelle = "override" if gesetzt and wert == url else "quelle"
        z = ged.lerne(e, quelle)
        if z:
            bericht.append(z)
    # Dann die Ausgabe selbst: Strecken, Sportart, Ort - für JEDE
    # Veranstaltung, auch ohne Seite.
    for k, zeilen in _ausgaben(events, ged).items():
        z = ged.ziehe_zurueck(k, zeilen, overrides)
        if z:
            bericht.append(z)
        z = ged.lerne_ausgabe(k, zeilen)
        if z:
            bericht.append(z)
    return bericht


def _ausgaben(events: list[dict], ged: "Gedaechtnis | None" = None) -> dict[str, list[dict]]:
    """Je Schlüssel die Zeilen der JÜNGSTEN Ausgabe in `events` - mit
    `ged` unter dem Schlüssel, unter dem das Gedächtnis die Zeile führt
    (auch nach einem Sponsorwechsel im Namen)."""
    gruppen: dict[str, dict[str, list[dict]]] = {}
    for e in events:
        k = ged.schluessel_fuer(e) if ged is not None else schluessel_von(e)
        if k:
            gruppen.setdefault(k, {}).setdefault(e.get("datum_start") or "", []).append(e)
    return {k: tage[max(tage)] for k, tage in gruppen.items()}


def abgleich_vorjahr(events: list[dict], ged: Gedaechtnis) -> list[str]:
    """Welche Strecken der vorigen Ausgabe fehlen in der neuen? Nur
    Bericht - Strecken ändern sich, und eine Zeile wird nie geraten.
    VOR lernen() aufrufen."""
    bericht: list[str] = []
    for k, zeilen in _ausgaben(events, ged).items():
        alt = ged.daten.get(k)
        if not alt or not alt.get("strecken"):
            continue
        datum = zeilen[0].get("datum_start") or ""
        if not alt.get("datum") or datum <= alt["datum"]:
            continue
        jetzt = {_masszahl_schluessel(z) for z in zeilen} - {None}
        fehlt = [s for s in alt["strecken"] if _masszahl_schluessel(s) and _masszahl_schluessel(s) not in jetzt]
        if fehlt and jetzt:
            bericht.append(f"{zeilen[0].get('name')} ({datum}, {zeilen[0].get('standort')}): "
                           f"Ausgabe {alt['datum']} hatte zusätzlich {', '.join(masszahl(s) for s in fehlt)}")
        elif fehlt:
            bericht.append(f"{zeilen[0].get('name')} ({datum}, {zeilen[0].get('standort')}): ohne Maßzahl - "
                           f"Ausgabe {alt['datum']} hatte {', '.join(masszahl(s) for s in alt['strecken'])}")
    return bericht


def anwenden(events: list[dict], ged: Gedaechtnis, overrides: dict | None = None) -> list[str]:
    """Jede Zeile ohne eigene Seite bekommt die gemerkte - nie eine, die
    schon eine eigene hat, und nie eine, deren Override den Link löscht."""
    overrides = load_manual_overrides() if overrides is None else overrides
    bericht: list[str] = []
    for e in events:
        eintrag = ged.finde(e)
        if not eintrag:
            continue
        # Nur eine FRÜHERE Ausgabe zählt. Liegt der gemerkte Stand NACH
        # dieser Zeile, ist es eine Serie mit mehreren Terminen unter einem
        # Namen (ZKB Zürilauf Cup, Rodgauer Winterlaufserie) - dann wäre die
        # gemerkte Seite die eines anderen Laufs der Serie. Und DIESELBE
        # Ausgabe zählt auch nicht: Trägt die Zeile die Seite nicht mehr,
        # die das Gedächtnis für genau diese Ausgabe kennt, hat sie jemand
        # bewusst entfernt (tv-albig.de war der Verein, nicht der
        # Doppelzwölfer; Fünfzehnter Durchgang) - das Gedächtnis darf sie
        # nicht zurückbringen. Deshalb läuft anwenden() in clean_events VOR
        # lernen(): Danach stünde die neue Ausgabe schon im Eintrag.
        if (eintrag.get("datum") or "") >= (e.get("datum_start") or ""):
            continue
        # Koordinaten der vorigen Ausgabe, wenn die Zeile keine hat (die
        # Quelle nennt nur den Ort): dieselbe Veranstaltung, derselbe Ort.
        if not isinstance(e.get("lat"), (int, float)) and isinstance(eintrag.get("lat"), (int, float)):
            e["lat"], e["lon"] = eintrag["lat"], eintrag["lon"]
            bericht.append(f"{e.get('name')} ({e.get('datum_start')}): Koordinaten der Ausgabe {eintrag.get('datum')} übernommen")
        alt = e.get("veranstalter_url")
        if eigene_seite(alt) or not eintrag.get("url"):
            continue
        gesetzt, wert = _override_url(e, overrides)
        if gesetzt and wert is None:
            continue
        e["veranstalter_url"] = eintrag["url"]
        bericht.append(f"{e.get('name')} ({e.get('datum_start')}): {host_von(alt) if alt else 'kein Link'}"
                       f" -> {eintrag['url']} (gemerkt von {eintrag.get('name')!r}, {eintrag.get('datum')})")
    return bericht


# --------------------------------------------------------------------------
# Kommandozeile
# --------------------------------------------------------------------------

def _lade_events(pfad: Path) -> list[dict]:
    return json.loads(pfad.read_text(encoding="utf-8"))


def cmd_aufbauen(args) -> None:
    ged = Gedaechtnis.laden()
    overrides = load_manual_overrides()
    vorher = len(ged)
    # Ältere Stände ZUERST, der aktuelle zuletzt - so gewinnt bei gleichem
    # Rang die jüngere Ausgabe, und ein Link-Override auf eine vergangene
    # Zeile zählt dort als Einzelprüfung.
    for alt in args.alt:
        zeilen = _lade_events(Path(alt))
        for e in zeilen:
            gesetzt, wert = _override_url(e, overrides)
            if gesetzt and wert:
                e["veranstalter_url"] = wert
        z = lernen(zeilen, ged, overrides)
        print(f"{alt}: {len(zeilen)} Zeilen, {len(z)} Änderungen am Gedächtnis")
    zeilen = _lade_events(args.events_json)
    z = lernen(zeilen, ged, overrides)
    print(f"{args.events_json}: {len(zeilen)} Zeilen, {len(z)} Änderungen am Gedächtnis")
    konflikte = [k for k, v in ged.daten.items() if v.get("konflikt")]
    mit_seite = sum(1 for v in ged.daten.values() if v.get("url"))
    print(f"Gedächtnis: {vorher} -> {len(ged)} Veranstaltungen, {mit_seite} mit Seite, {len(konflikte)} im Konflikt")
    if konflikte and not args.quiet:
        for k in konflikte:
            print(f"  ⚠ {ged.daten[k].get('name')} ({ged.daten[k].get('standort')}): "
                  f"{', '.join(host_von(u) for u in ged.daten[k]['konflikt'])}")
    ged.speichern()
    print(f"✅ {PFAD} geschrieben.")


def cmd_zeigen(args) -> None:
    ged = Gedaechtnis.laden()
    wort = normalize_event_name(args.suchwort)
    for k, v in ged.daten.items():
        if wort in k or wort in normalize_event_name(v.get("name")):
            print(f"{k}\n    {json.dumps(v, ensure_ascii=False)}")


def kandidaten_termine(daten: set[str] | list[str], letzte_ausgabe: str | None, heute: str) -> list[str]:
    """Die Termine auf der Seite, die als NÄCHSTE Ausgabe in Frage kommen:
    künftig, und 10 bis 14 Monate nach der vorigen (FENSTER_TAGE). Ohne
    bekannte vorige Ausgabe zählt jeder künftige Termin bis 14 Monate."""
    from datetime import date, timedelta
    kuenftig = sorted(d for d in daten if d > heute)
    if not kuenftig:
        return []
    try:
        if letzte_ausgabe:
            basis = date.fromisoformat(letzte_ausgabe)
            von, bis = basis + timedelta(days=FENSTER_TAGE[0]), basis + timedelta(days=FENSTER_TAGE[1])
        else:
            basis = date.fromisoformat(heute)
            von, bis = basis, basis + timedelta(days=FENSTER_TAGE[1])
    except ValueError:
        return []
    return [d for d in kuenftig if von.isoformat() <= d <= bis.isoformat()]


def spanne(termine: list[str]) -> tuple[str, str] | None:
    """Genau EIN Termin - oder eine zusammenhängende Spanne von höchstens
    vier Tagen (Etappen, Festival): (Start, Ende). Sonst None (mehrdeutig)."""
    from datetime import date
    if not termine:
        return None
    t = sorted(set(termine))
    if len(t) == 1:
        return t[0], t[0]
    erster, letzter = date.fromisoformat(t[0]), date.fromisoformat(t[-1])
    if (letzter - erster).days <= 3:
        return t[0], t[-1]
    return None


_JAHR_IM_NAMEN = re.compile(r"\s*\b(?:19|20)\d{2}(?:/(?:19|20)?\d{2})?\b")
_AUFLAGE_VORN = re.compile(r"^\s*\d{1,3}\.\s+")


def name_ohne_jahr(name: str) -> str:
    """„Munich Triathlon 2027" -> „Munich Triathlon", „Winterlaufserie 2026/2027"
    -> „Winterlaufserie", „6. Appelhülsener Landlauf" -> „Appelhülsener
    Landlauf". Die Auflage vorn fällt seit dem 05.10.2026 ebenfalls: Die
    nächste Ausgabe heißt „7.", und eine falsche Zahl ist schlechter als
    keine (im ersten vollen Lauf stand die „6." neben der „7." aus dem
    Kalender). Eine Auflage mitten im Namen bleibt."""
    ohne = _JAHR_IM_NAMEN.sub("", name or "")
    ohne = _AUFLAGE_VORN.sub("", ohne)
    return re.sub(r"\s{2,}", " ", ohne).strip(" -–")


def manual_events_aus(eintrag: dict, start: str, ende: str, heute: str,
                      seiten_km=None) -> list[OrderedDict]:
    """Die Zeilen der neuen Ausgabe für manual_events.json: je gemerkter
    Strecke eine, ohne Strecken eine Zeile ohne Maßzahl.

    `seiten_km` sind die Kilometerangaben, die die Veranstalterseite JETZT
    nennt (`distanzen_aus`). Nennt sie welche, kommt nur mit, was dort
    noch steht: Aus einem 10-km-Lauf kann ein Halbmarathon geworden sein,
    und eine 10-km-Zeile aus dem Vorjahr wäre dann eine erfundene Strecke
    - die unangenehmere Sorte Fehler, weil sie aussieht wie eine Angabe.
    Was die Seite zusätzlich nennt, wird NICHT angelegt (geraten wird
    nie), sondern steht in der Notiz und im Bericht. Bleibt keine Strecke
    übrig, trägt die Ausgabe eine Zeile ohne Maßzahl. Nennt die Seite gar
    keine Kilometer (die Strecken stehen oft nur auf einer Unterseite),
    gilt das Vorjahr unverändert. Zeitrennen (`dauer_h`) und Zeilen ohne
    Maßzahl bleiben immer.

    Jede Zeile trägt `gedaechtnis: true` - das Feld landet in events.json
    und sagt: Diese Strecke ist aus dem Vorjahr übernommen, keine Quelle
    hat sie für diese Ausgabe bestätigt. `clean_events.add_manual_events()`
    zieht solche Zeilen zurück, sobald eine Quelle die Ausgabe liefert, und
    `update_existing_event()`/`merge_duplicates()` nehmen die Markierung
    weg, sobald eine Quelle dieselbe Strecke bestätigt."""
    strecken = eintrag.get("strecken") or [OrderedDict((f, None) for f in STRECKEN_FELDER)]
    weggefallen: list[dict] = []
    if seiten_km:
        bleibt = []
        for st in strecken:
            km = st.get("laenge_km")
            if isinstance(km, (int, float)) and not km_passt(km, seiten_km):
                weggefallen.append(st)
            else:
                bleibt.append(st)
        strecken = bleibt or [OrderedDict((f, None) for f in STRECKEN_FELDER)]
    bekannt = {_masszahl_schluessel(st) for st in (eintrag.get("strecken") or [])}
    neu_auf_seite = sorted(g for g in (seiten_km or []) if g >= 1 and ("km", round(g, 1)) not in bekannt
                           and not km_passt(g, [st["laenge_km"] for st in (eintrag.get("strecken") or [])
                                                if isinstance(st.get("laenge_km"), (int, float))]))
    hinweis = ""
    if weggefallen:
        hinweis += (" Nicht übernommen, weil die Seite sie nicht mehr nennt: "
                    + ", ".join(masszahl(st) for st in weggefallen) + ".")
    if neu_auf_seite:
        hinweis += (" Die Seite nennt außerdem: " + ", ".join(f"{g:g} km" for g in neu_auf_seite[:8])
                    + " - prüfen, ob das neue Strecken sind.")
    zeilen = []
    for st in strecken:
        z = OrderedDict([("land", eintrag.get("land")), ("name", name_ohne_jahr(eintrag.get("name"))),
                         ("standort", eintrag.get("standort")), ("lat", eintrag.get("lat")), ("lon", eintrag.get("lon")),
                         ("art1", eintrag.get("art1")), ("art2", st.get("art2")),
                         ("datum_start", start), ("datum_ende", ende),
                         ("laenge_km", st.get("laenge_km")), ("dauer_h", st.get("dauer_h")),
                         ("wettbewerb", st.get("wettbewerb")), ("veranstalter_url", eintrag.get("url")),
                         ("gedaechtnis", True),
                         ("_quelle", eintrag.get("url")),
                         ("_note", f"Gedächtnis je Veranstaltung ({heute}): Die Veranstalterseite nennt den Termin "
                                   f"{start}" + (f" bis {ende}" if ende != start else "") +
                                   f"; Strecken aus der Ausgabe {eintrag.get('datum')} übernommen "
                                   "(veranstalter_seiten.py pruefen --uebernehmen)." + hinweis +
                                   " Die Zeile verschwindet von selbst, sobald eine Quelle die Ausgabe liefert.")])
        zeilen.append(OrderedDict((k, v) for k, v in z.items() if v is not None or k in ("laenge_km", "dauer_h")))
    return zeilen


def _vergangen(eintrag: dict, heute: str) -> bool:
    return (eintrag.get("datum_ende") or eintrag.get("datum_start") or "") < heute


def uebernehmen(eintraege: list[tuple], heute: str, pfad: Path = MANUAL_EVENTS) -> list[str]:
    """Schreibt die gefundenen Ausgaben nach manual_events.json (an das
    Ende der Liste; was dort schon unter Name und Datum steht, bleibt).
    Jeder Eintrag ist (Schlüssel, Gedächtnis-Eintrag, Start, Ende) und
    optional dahinter die Kilometer, die die Seite nennt (`seiten_km`).
    Räumt dabei die vergangenen Ausgaben weg, die das Gedächtnis selbst
    angelegt hat (`gedaechtnis: true`) - sonst wüchse die Datei mit jedem
    Jahr um Zeilen, die drop_past_events() ohnehin nie mehr aufnimmt."""
    roh = json.loads(pfad.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict) if pfad.exists() \
        else OrderedDict([("events", [])])
    liste = roh.setdefault("events", []) if isinstance(roh, OrderedDict) else roh
    geraeumt = [e for e in liste if e.get("gedaechtnis") and _vergangen(e, heute)]
    if geraeumt:
        liste[:] = [e for e in liste if not (e.get("gedaechtnis") and _vergangen(e, heute))]
    vorhanden = {(normalize_event_name(e.get("name")), e.get("datum_start")) for e in liste}
    bericht = []
    for tupel in eintraege:
        k, eintrag, start, ende = tupel[:4]
        seiten_km = tupel[4] if len(tupel) > 4 else None
        zeilen = manual_events_aus(eintrag, start, ende, heute, seiten_km)
        if (normalize_event_name(zeilen[0]["name"]), start) in vorhanden:
            continue
        liste.extend(zeilen)
        vorhanden.add((normalize_event_name(zeilen[0]["name"]), start))
        bericht.append(f"{zeilen[0]['name']} ({eintrag.get('standort')}): Ausgabe {start} mit "
                       f"{len(zeilen)} Strecke(n) nach manual_events.json - {eintrag.get('url')}"
                       + (" (Strecken gegen die Seite geprüft)" if seiten_km else ""))
    if bericht or geraeumt:
        pfad.write_text(json.dumps(roh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if geraeumt:
        bericht.append(f"{len(geraeumt)} vergangene Zeile(n) des Gedächtnisses aus manual_events.json entfernt")
    return bericht


# Was als „tot" zählt: Die Seite gibt es nicht mehr (404/410) oder den
# Host nicht mehr (DNS/Verbindung). 403, 429, 5xx und Zeitüberschreitungen
# sind Bot-Sperren oder Wackler, keine Beweise.
TOT_STATUS = {404, 410}
TOT_NACH_PRUEFUNGEN = 2


def _ist_tot(status: int | None, body: str) -> bool:
    return status in TOT_STATUS or (status is None and body.startswith("fehler:Connection"))


def _wurzel(url: str) -> str:
    from urllib.parse import urlparse
    u = urlparse(url)
    return f"{u.scheme}://{u.netloc}/"


def _gleiche_adresse(a: str, b: str) -> bool:
    return a.rstrip("/").lower().replace("http://", "https://") == b.rstrip("/").lower().replace("http://", "https://")


def pruefe_eintrag(k: str, v: dict, ab, heute: str) -> tuple[OrderedDict, tuple | None]:
    """Ruft die gemerkte Seite EINER vergangenen Veranstaltung ab und sucht
    den nächsten Termin. Gibt (Berichtszeile, Fund-oder-None) zurück und
    schreibt in `v`: `geprueft_am`, eine umgezogene Adresse, eine tote
    Seite (`quelle` tot, `url_tot`). Was die Prüfung aushält (seit dem
    05.10.2026, Frage des Nutzers: „auch wenn die Webseite leicht geändert
    oder neu aufgesetzt wurde"):

    - **Weiterleitung**: Kommt der Abruf auf einer anderen Adresse an (neue
      Domain nach Sponsorwechsel, neuer Pfad nach Umbau) und die Seite
      dort nennt den Lauf, merkt sich das Gedächtnis die neue Adresse.
    - **Tote Unterseite**: 1.520 der 4.154 gemerkten Adressen zeigen auf
      Unterseiten, 164 tragen eine Jahreszahl im Pfad - nach einem Umbau
      ist die Unterseite weg, die Startseite nicht. Dann wird die
      Startseite abgerufen; nennt sie den Lauf, tritt sie an die Stelle
      der toten Adresse (und liefert den Termin, wenn er dort steht).
    - **Tote Seite**: Antwortet auch die Startseite bei zwei Prüfungen
      hintereinander (mindestens drei Wochen auseinander) mit 404/410
      oder ist der Host weg, gilt die Seite als tot: `url` leer, die alte
      Adresse in `url_tot`, `quelle` tot. anwenden() gibt sie dann nicht
      mehr an die nächste Ausgabe weiter, und lerne() nimmt die erste
      eigene Seite, die eine Quelle für eine neue Ausgabe liefert. Eine
      lebende Antwort setzt den Zähler zurück.
    - **Startseite ohne Termin**: Nennt die gemerkte Unterseite den Lauf,
      aber keinen passenden Termin, wird zusätzlich die Startseite
      gelesen (nur wenn sie den Lauf nennt) - Veranstalter kündigen die
      nächste Ausgabe oft zuerst dort an.
    - **Strecken**: Nennt die Seite Kilometer, gehen in die neue Ausgabe
      nur die Strecken des Vorjahrs, die dort noch stehen
      (`manual_events_aus`)."""
    from veranstalter_links import text_von, nennt_den_lauf
    url = v["url"]
    status, body = ab.hole(url)
    r = OrderedDict(name=v.get("name"), ort=v.get("standort"), url=url,
                    letzte_ausgabe=v.get("datum"), geprueft_am=heute,
                    status=status if status is not None else body)
    v["geprueft_am"] = heute
    namen, orte = [v.get("name") or ""], [v.get("standort") or ""]
    belegt = nennt_den_lauf(body, url, namen, [], orte) if status == 200 else []
    txt = text_von(body) if status == 200 else ""
    wurzel = _wurzel(url)
    tot = _ist_tot(status, body)
    # Weiterleitung auf einen ANDEREN Host (und eine eigene Seite): Die
    # Seite ist umgezogen. Ein neuer Pfad auf demselben Host zählt nicht -
    # velosolingen.de leitet seine Startseite auf /adm_program/index.php,
    # das ist der Einstieg des CMS, keine neue Adresse (Probelauf 05.10.2026).
    ende = getattr(ab, "endadresse", {}).get(url)
    if status == 200 and ende and host_von(ende) != host_von(url) and eigene_seite(ende) and belegt:
        r["umgezogen"] = ende
        v["url"] = url = ende
        wurzel = _wurzel(url)
    # Tote Unterseite oder eine Seite, die den Lauf nicht (mehr) nennt:
    # die Startseite versuchen.
    von_startseite = False
    if not _gleiche_adresse(url, wurzel) and (tot or (status == 200 and not belegt)):
        st2, body2 = ab.hole(wurzel)
        belegt2 = nennt_den_lauf(body2, wurzel, namen, [], orte) if st2 == 200 else []
        r["startseite"] = st2 if st2 is not None else body2
        if st2 == 200 and belegt2:
            if tot:
                r["umgezogen"] = wurzel
                v["url"] = url = wurzel
            status, body, belegt, txt, tot = st2, body2, belegt2, text_von(body2), False
            von_startseite = True
    if tot:
        v["tot_zaehler"] = int(v.get("tot_zaehler") or 0) + 1
        if v["tot_zaehler"] >= TOT_NACH_PRUEFUNGEN:
            v["url_tot"], v["url"] = url, None
            v["quelle"] = "tot"
            v.pop("tot_zaehler", None)
            r["flag"] = "TOT"
            return r, None
        r["flag"] = "FEHLER"
        return r, None
    v.pop("tot_zaehler", None)
    if status != 200:
        r["flag"] = "FEHLER"
        return r, None
    daten = daten_aus(txt)
    kand = kandidaten_termine(daten, v.get("datum"), heute)
    if not kand and belegt and not _gleiche_adresse(url, wurzel):
        # Die Unterseite nennt den Lauf, aber keinen passenden Termin:
        # die Startseite dazulesen, wenn sie den Lauf ebenfalls nennt.
        st2, body2 = ab.hole(wurzel)
        if st2 == 200 and nennt_den_lauf(body2, wurzel, namen, [], orte):
            txt2 = text_von(body2)
            daten |= daten_aus(txt2)
            kand = kandidaten_termine(daten, v.get("datum"), heute)
            if kand:
                r["termin_von"] = wurzel
                txt = txt + " " + txt2
                von_startseite = True
    r["kuenftige_termine"] = sorted(d for d in daten if d > heute)[:10]
    r["kandidaten"] = kand
    r["textlaenge"] = len(txt)
    r["nennt_den_lauf"] = belegt
    seiten_km = sorted(g for g in distanzen_aus(txt) if g >= 1)
    if seiten_km:
        r["seiten_km"] = seiten_km[:40]
    sp = spanne(kand)
    if kand and sp and belegt and not von_startseite:
        r["flag"] = "NEU"
        return r, (k, v, sp[0], sp[1], set(seiten_km))
    if kand:
        r["flag"] = "NEU?"
        if sp and belegt and von_startseite:
            # Der Termin stammt von der STARTSEITE, nicht von der Seite des
            # Laufs: Die nennt auch die anderen Veranstaltungen desselben
            # Veranstalters. Beim ersten vollen Lauf (05.10.2026) hätte der
            # „GENERALI 5K" so den Termin des Berlin-Marathons bekommen
            # (Sonntag statt Samstag). Deshalb nur zur Handprüfung.
            r["grund"] = "Termin von der Startseite, nicht von der Seite des Laufs"
    elif len(txt) < 300:
        r["flag"] = "LEER"
    else:
        r["flag"] = "NICHTS"
    return r, None


def cmd_pruefen(args) -> None:
    """Vergangene Veranstaltungen: Nennt die gemerkte Seite schon den
    nächsten Termin? Bericht - und mit --uebernehmen die eindeutigen
    Funde nach manual_events.json."""
    from datetime import date, timedelta
    from veranstalter_links import Abrufer

    ged = Gedaechtnis.laden()
    events = _lade_events(args.events_json)
    aktuell: set[str] = set()
    for e in events:
        for k in ged._kandidaten(e):
            aktuell.add(k)
    heute = args.heute or time.strftime("%Y-%m-%d")
    grenze = (date.fromisoformat(heute) - timedelta(days=PRUEF_ABSTAND_TAGE)).isoformat()
    offen = [(k, v) for k, v in ged.daten.items()
             if k not in aktuell and v.get("url") and (v.get("geprueft_am") or "") < grenze
             and (v.get("uebernommen") or "") < heute]
    # Die ältesten Prüfungen zuerst, darunter die ältesten Ausgaben.
    offen.sort(key=lambda kv: (kv[1].get("geprueft_am") or "", kv[1].get("datum") or ""))
    bericht_pfad = Path(args.bericht)
    bericht: OrderedDict = OrderedDict()
    if args.fortsetzen and bericht_pfad.exists():
        bericht = json.loads(bericht_pfad.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    if args.max:
        offen = offen[:args.max]
    print(f"{len(ged)} Veranstaltungen im Gedächtnis, {len(offen)} vergangene mit Seite fällig "
          f"(nächste Ausgabe unbekannt, zuletzt vor mehr als {PRUEF_ABSTAND_TAGE} Tagen geprüft)", flush=True)
    ab = Abrufer(pause=args.pause)
    t0 = time.time()
    funde: list[tuple] = []
    abgebrochen = 0
    for i, (k, v) in enumerate(offen, 1):
        if args.zeitlimit and time.time() - t0 > args.zeitlimit:
            # Sauber aufhören, nicht von außen abgeschossen werden: Dann
            # gingen die Funde dieses Laufs und `geprueft_am` verloren, und
            # dieselben Seiten kämen nächste Woche als Erste wieder dran.
            abgebrochen = len(offen) - i + 1
            print(f"  Zeitlimit von {args.zeitlimit} s erreicht - {abgebrochen} Seiten bleiben für den nächsten Lauf.", flush=True)
            break
        r, fund = pruefe_eintrag(k, v, ab, heute)
        if fund:
            funde.append(fund)
        bericht[k] = r
        if i % 25 == 0 or i == len(offen):
            zaehler: dict[str, int] = {}
            for b in bericht.values():
                zaehler[b["flag"]] = zaehler.get(b["flag"], 0) + 1
            print(f"  … {i}/{len(offen)} ({int(time.time() - t0)} s): {zaehler}", flush=True)
            bericht_pfad.write_text(json.dumps(bericht, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bericht_pfad.write_text(json.dumps(bericht, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    neu = [b for b in bericht.values() if b.get("flag") in ("NEU", "NEU?")]
    print(f"\nNEU - die Seite nennt einen passenden künftigen Termin ({len(neu)}):")
    for b in neu:
        print(f"  - [{b['flag']}] {b['name']} ({b['ort']}, zuletzt {b['letzte_ausgabe']}): "
              f"{', '.join(b['kandidaten'][:4])} - {b['url']}")
    umgezogen = [b for b in bericht.values() if b.get("umgezogen")]
    tot = [b for b in bericht.values() if b.get("flag") == "TOT"]
    if umgezogen:
        print(f"\nAdresse umgezogen ({len(umgezogen)}):")
        for b in umgezogen:
            print(f"  - {b['name']} ({b['ort']}): {b['url']} -> {b['umgezogen']}")
    if tot:
        print(f"\nSeite tot - wird nicht mehr weitergegeben ({len(tot)}):")
        for b in tot:
            print(f"  - {b['name']} ({b['ort']}): {b['url']}")
    if args.uebernehmen and funde:
        z = uebernehmen(funde, heute)
        for fund in funde:
            fund[1]["uebernommen"] = fund[2]
        print(f"\nNach manual_events.json übernommen ({len(z)}):")
        for zeile in z:
            print("  -", zeile)
    elif funde:
        print("\nMit --uebernehmen landen die eindeutigen Funde (NEU) in manual_events.json.")
    ged.speichern()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--events-json", type=Path, default=EVENTS)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("aufbauen", help="aus events.json (und älteren Ständen) lernen")
    a.add_argument("--alt", action="append", default=[], metavar="DATEI",
                   help="älterer Stand von events.json (mehrfach möglich, älteste zuerst)")
    a.add_argument("--quiet", action="store_true")
    z = sub.add_parser("zeigen", help="Einträge zu einem Suchwort")
    z.add_argument("suchwort")
    pr = sub.add_parser("pruefen", help="Seiten vergangener Veranstaltungen auf den neuen Termin prüfen")
    pr.add_argument("--bericht", required=True)
    pr.add_argument("--fortsetzen", action="store_true")
    pr.add_argument("--max", type=int, default=0)
    pr.add_argument("--pause", type=float, default=2.0)
    pr.add_argument("--uebernehmen", action="store_true",
                    help="eindeutige Funde als neue Ausgabe nach manual_events.json schreiben")
    pr.add_argument("--heute", default=None, help="Stichtag (nur für Tests)")
    pr.add_argument("--zeitlimit", type=int, default=0,
                    help="nach so vielen Sekunden keine weitere Seite mehr abrufen, Funde trotzdem übernehmen und speichern")
    args = p.parse_args()
    {"aufbauen": cmd_aufbauen, "zeigen": cmd_zeigen, "pruefen": cmd_pruefen}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
