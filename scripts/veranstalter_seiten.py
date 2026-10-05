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
      "quelle": "override" | "quelle" | "zurueckgezogen",
                                     Einzelprüfung, vom Scraper geliefert, oder
                                     die Seite wurde für diese Ausgabe entfernt (url null)
      "konflikt": ["…", "…"],        statt url: zwei Seiten, keine entscheidbar
      "fest": true,                  von Hand gesetzt - lernen() fasst es nicht an
      "art1": "Laufen", "land": "Deutschland",
      "strecken": [ {"laenge_km": 10, "dauer_h": null, "wettbewerb": "10 km", "art2": "Straße"}, … ],
      "strecken_datum": "2026-12-06",  die Strecken der jüngsten Ausgabe und ihr Starttag (05.10.2026)
      "geprueft_am": "2027-03-02",   wann `pruefen` die Seite zuletzt abgerufen hat
      "uebernommen": "2027-06-13"    welche Ausgabe `pruefen --uebernehmen` angelegt hat
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
          "'quelle' = override (Einzelprüfung), quelle (vom Scraper geliefert) oder zurueckgezogen (die Ausgabe trägt die Seite nicht mehr, url leer); 'konflikt' statt 'url' = "
          "zwei Seiten, keine entscheidbar, nichts wird angewendet; 'fest': true = von Hand gesetzt, lernen() lässt den Eintrag in Ruhe. "
          "'strecken'/'art1'/'land' = die jüngste Ausgabe ('strecken_datum' ihr Starttag), gelernt auch ohne Seite; "
          "'geprueft_am'/'uebernommen' setzt `pruefen` (Suche nach der nächsten Ausgabe auf der Veranstalterseite). "
          "Die Einträge sind nach Schlüssel sortiert, damit der Diff je Lauf klein bleibt.")

# Monatsnamen für Datumsangaben im Seitentext (auch von seitenabgleich.py
# genutzt - EINE Tabelle für beide).
MONATE = {m: i + 1 for i, m in enumerate(
    ["januar", "februar", "marz", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "dezember"])}
MONATE.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
               "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12})


def daten_aus(txt: str) -> set[str]:
    """Alle Datumsangaben im (normalisierten) Seitentext als ISO-Daten:
    „12.10.2026", „12. Oktober 2026", „2026-10-12"."""
    out = set()
    for t, m, j in re.findall(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(20\d{2})\b", txt):
        if 1 <= int(m) <= 12 and 1 <= int(t) <= 31:
            out.add(f"{j}-{int(m):02d}-{int(t):02d}")
    for t, m, j in re.findall(r"\b(\d{1,2})\.\s?([a-z]{3,9})\.?\s?(20\d{2})\b", txt):
        if m in MONATE and 1 <= int(t) <= 31:
            out.add(f"{j}-{MONATE[m]:02d}-{int(t):02d}")
    for j, m, t in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", txt):
        if 1 <= int(m) <= 12 and 1 <= int(t) <= 31:
            out.add(f"{j}-{m}-{t}")
    return out


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


def generisch(kern: str) -> bool:
    """Ein Kern nur aus Allerweltswörtern („crosslauf", „silvesterlauf
    volkslauf") unterscheidet Veranstaltungen nicht - dann zählt der Ort
    wörtlich, nicht als Teilmenge (siehe Modulkopf)."""
    woerter = kern.split()
    return not woerter or all(w in ALLGEMEIN or len(w) < 4 for w in woerter)


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
            for k in self.daten:
                kern, _, ort = k.partition("|")
                idx.setdefault(kern, []).append((k, frozenset(ort.split())))
            self._index = idx
        return self._index

    def _kandidaten(self, event: dict) -> list[str]:
        """Die Schlüssel, die zu dieser Zeile passen (gleicher Kern,
        passender Ort oder Koordinaten ≤ 3 km)."""
        kern = kern_von(event)
        if not kern:
            return []
        ort = ort_von(event)
        streng = generisch(kern)
        treffer = []
        for k, ort_k in self._idx().get(kern, []):
            if _ort_passt(ort, ort_k, streng) or (not streng and _koordinaten_nah(event, self.daten[k])):
                treffer.append(k)
        return treffer

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
        gesammelt = {json.dumps(strecke_von(z), ensure_ascii=False, sort_keys=True): strecke_von(z)
                     for z in zeilen}
        if not neu and datum == alt.get("strecken_datum"):
            # Dieselbe Ausgabe noch einmal (zweiter Durchgang, Teilmenge der
            # Zeilen): Strecken VEREINIGEN, nicht ersetzen - sonst nähme ein
            # Aufruf mit einer Zeile der Veranstaltung alle anderen weg.
            # Verglichen wird mit `strecken_datum`, nicht mit `datum`: Das
            # hat lerne() für eine Zeile mit Seite schon auf die neue
            # Ausgabe gesetzt, die Strecken gehören aber noch zur alten.
            for st in alt.get("strecken") or []:
                gesammelt.setdefault(json.dumps(st, ensure_ascii=False, sort_keys=True), st)
        strecken = _strecken_sortiert(gesammelt.values())
        geaendert = neu or alt.get("strecken") != strecken or alt.get("art1") != zeilen[0].get("art1")
        alt["strecken_datum"] = datum
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
        k = schluessel_von(event)
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
        # Verschiedener Host (oder bisher Konflikt): Rang, dann Ausgabe.
        if (_rang(quelle), datum) > (_rang(alt_quelle), alt_datum):
            alt_host = host_von(alt_url) if alt_url else "Konflikt"
            self.daten[k] = neu
            return f"{event.get('name')}: Seite ersetzt ({alt_host} -> {host_von(url)})"
        if (_rang(quelle), datum) < (_rang(alt_quelle), alt_datum):
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
        k = schluessel_von(event)
        alt = self.daten.get(k) if k else None
        if alt is None or alt.get("fest") or not (alt.get("url") or alt.get("konflikt")):
            return None
        alt["url"] = None
        alt.pop("konflikt", None)
        alt["quelle"] = "override"
        return f"{event.get('name')} ({event.get('standort')}): Seite vergessen (Override: kein Link)"
        return None


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
        marke = (schluessel_von(e), url)
        if marke in gesehen:
            continue  # die Schwesterstrecken derselben Veranstaltung
        gesehen.add(marke)
        quelle = "override" if gesetzt and wert == url else "quelle"
        z = ged.lerne(e, quelle)
        if z:
            bericht.append(z)
    # Dann die Ausgabe selbst: Strecken, Sportart, Ort - für JEDE
    # Veranstaltung, auch ohne Seite.
    for k, zeilen in _ausgaben(events).items():
        z = ged.ziehe_zurueck(k, zeilen, overrides)
        if z:
            bericht.append(z)
        z = ged.lerne_ausgabe(k, zeilen)
        if z:
            bericht.append(z)
    return bericht


def _ausgaben(events: list[dict]) -> dict[str, list[dict]]:
    """Je Schlüssel die Zeilen der JÜNGSTEN Ausgabe in `events`."""
    gruppen: dict[str, dict[str, list[dict]]] = {}
    for e in events:
        k = schluessel_von(e)
        if k:
            gruppen.setdefault(k, {}).setdefault(e.get("datum_start") or "", []).append(e)
    return {k: tage[max(tage)] for k, tage in gruppen.items()}


def abgleich_vorjahr(events: list[dict], ged: Gedaechtnis) -> list[str]:
    """Welche Strecken der vorigen Ausgabe fehlen in der neuen? Nur
    Bericht - Strecken ändern sich, und eine Zeile wird nie geraten.
    VOR lernen() aufrufen."""
    bericht: list[str] = []
    for k, zeilen in _ausgaben(events).items():
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


def name_ohne_jahr(name: str) -> str:
    """„Munich Triathlon 2027" -> „Munich Triathlon", „Winterlaufserie 2026/2027"
    -> „Winterlaufserie". Die Auflage („49.") bleibt - ob sie im nächsten
    Jahr „50." heißt, weiß niemand; `unify_event_names` räumt das auf."""
    return re.sub(r"\s{2,}", " ", _JAHR_IM_NAMEN.sub("", name or "")).strip(" -–")


def manual_events_aus(eintrag: dict, start: str, ende: str, heute: str) -> list[OrderedDict]:
    """Die Zeilen der neuen Ausgabe für manual_events.json: je gemerkter
    Strecke eine, ohne Strecken eine Zeile ohne Maßzahl."""
    strecken = eintrag.get("strecken") or [OrderedDict((f, None) for f in STRECKEN_FELDER)]
    zeilen = []
    for st in strecken:
        z = OrderedDict([("land", eintrag.get("land")), ("name", name_ohne_jahr(eintrag.get("name"))),
                         ("standort", eintrag.get("standort")), ("lat", eintrag.get("lat")), ("lon", eintrag.get("lon")),
                         ("art1", eintrag.get("art1")), ("art2", st.get("art2")),
                         ("datum_start", start), ("datum_ende", ende),
                         ("laenge_km", st.get("laenge_km")), ("dauer_h", st.get("dauer_h")),
                         ("wettbewerb", st.get("wettbewerb")), ("veranstalter_url", eintrag.get("url")),
                         ("_quelle", eintrag.get("url")),
                         ("_note", f"Gedächtnis je Veranstaltung ({heute}): Die Veranstalterseite nennt den Termin "
                                   f"{start}" + (f" bis {ende}" if ende != start else "") +
                                   f"; Strecken aus der Ausgabe {eintrag.get('datum')} übernommen "
                                   "(veranstalter_seiten.py pruefen --uebernehmen). Bei der nächsten Prüfung: "
                                   "stimmen die Strecken noch?")])
        zeilen.append(OrderedDict((k, v) for k, v in z.items() if v is not None or k in ("laenge_km", "dauer_h")))
    return zeilen


def uebernehmen(eintraege: list[tuple[str, dict, str, str]], heute: str, pfad: Path = MANUAL_EVENTS) -> list[str]:
    """Schreibt die gefundenen Ausgaben nach manual_events.json (an das
    Ende der Liste; was dort schon unter Name und Datum steht, bleibt)."""
    roh = json.loads(pfad.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict) if pfad.exists() \
        else OrderedDict([("events", [])])
    liste = roh.setdefault("events", []) if isinstance(roh, OrderedDict) else roh
    vorhanden = {(normalize_event_name(e.get("name")), e.get("datum_start")) for e in liste}
    bericht = []
    for k, eintrag, start, ende in eintraege:
        zeilen = manual_events_aus(eintrag, start, ende, heute)
        if (normalize_event_name(zeilen[0]["name"]), start) in vorhanden:
            continue
        liste.extend(zeilen)
        vorhanden.add((normalize_event_name(zeilen[0]["name"]), start))
        bericht.append(f"{zeilen[0]['name']} ({eintrag.get('standort')}): Ausgabe {start} mit "
                       f"{len(zeilen)} Strecke(n) nach manual_events.json - {eintrag.get('url')}")
    if bericht:
        pfad.write_text(json.dumps(roh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bericht


def cmd_pruefen(args) -> None:
    """Vergangene Veranstaltungen: Nennt die gemerkte Seite schon den
    nächsten Termin? Bericht - und mit --uebernehmen die eindeutigen
    Funde nach manual_events.json."""
    from datetime import date, timedelta
    from veranstalter_links import Abrufer, text_von, nennt_den_lauf

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
    funde: list[tuple[str, dict, str, str]] = []
    for i, (k, v) in enumerate(offen, 1):
        status, body = ab.hole(v["url"])
        r = OrderedDict(name=v.get("name"), ort=v.get("standort"), url=v["url"],
                        letzte_ausgabe=v.get("datum"), geprueft_am=heute,
                        status=status if status is not None else body)
        v["geprueft_am"] = heute
        if status == 200:
            txt = text_von(body)
            kand = kandidaten_termine(daten_aus(txt), v.get("datum"), heute)
            r["kuenftige_termine"] = sorted(d for d in daten_aus(txt) if d > heute)[:10]
            r["kandidaten"] = kand
            r["textlaenge"] = len(txt)
            belegt = nennt_den_lauf(body, v["url"], [v.get("name") or ""], [], [v.get("standort") or ""])
            r["nennt_den_lauf"] = belegt
            sp = spanne(kand)
            if kand and sp and belegt:
                r["flag"] = "NEU"
                funde.append((k, v, sp[0], sp[1]))
            elif kand:
                r["flag"] = "NEU?"
            elif len(txt) < 300:
                r["flag"] = "LEER"
            else:
                r["flag"] = "NICHTS"
        else:
            r["flag"] = "FEHLER"
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
    if args.uebernehmen and funde:
        z = uebernehmen(funde, heute)
        for k, v, start, _ in funde:
            v["uebernommen"] = start
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
    args = p.parse_args()
    {"aufbauen": cmd_aufbauen, "zeigen": cmd_zeigen, "pruefen": cmd_pruefen}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
