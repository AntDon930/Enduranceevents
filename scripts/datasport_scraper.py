#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datasport_scraper.py
====================

Liest die Veranstaltungsseiten von https://datasport.com (Datasport AG,
Gerlafingen - Zeitnahme und Anmeldeplattform für die Schweiz, dazu einige
Veranstaltungen in Deutschland, Österreich und Südtirol) und ergänzt sie in
`events.json` (siehe `scraper_lib.py`): Läufe, Radrennen (Rennrad, MTB,
Gravel), Triathlons und Schwimmen.

Rechtslage (geprüft am 30.09.2026)
----------------------------------
Der Nutzer hatte datasport am 21.09.2026 als Zeitnehmer ausgeschlossen und
am 30.09.2026 ausdrücklich freigegeben („du hast meine Erlaubnis für
Punkt 3, datasport.com"). robots.txt: `User-agent: *` → `Allow: /`,
`Disallow: /api/`; die Gruppe der KI-Crawler (GPTBot, ClaudeBot, CCBot, …)
bekommt dasselbe plus `Crawl-delay: 10`. **Wir halten die 10 Sekunden
ein** (`MINDEST_PAUSE`), auch wenn unser User-Agent formal unter `*`
fällt - der Wunsch der Seite an automatische Abrufe ist eindeutig. Das
Impressum nennt kein Verbot, Nutzungsbedingungen gibt es nur für die
Anmeldung (onreg). Die `/api/`-Pfade werden nie aufgerufen.

Struktur (am 30.09.2026 kalibriert)
-----------------------------------
Die Seite ist eine Next.js-Anwendung. Die Listenseite `/de/events` liefert
serverseitig nur 20 Einträge und ignoriert URL-Parameter; weitere Seiten
holt sie über `/api/` - gesperrt. **Die Liste ist deshalb die
`sitemap.xml`** (von robots.txt genannt, ~1.450 Adressen
`/de/events/<slug>`), und die ist sortiert: erst die KOMMENDEN
Veranstaltungen chronologisch aufsteigend, danach die vergangenen
absteigend. Der Scraper geht die Liste in dieser Reihenfolge durch und
hört auf, sobald `ABBRUCH_NACH_VERGANGENEN` Seiten hintereinander in der
Vergangenheit liegen - so sind es rund 100 statt 1.450 Abrufe (bei 10 s
Pause ~17 Minuten). Slugs mit einer Jahreszahl vor dem laufenden Jahr
werden gar nicht erst abgerufen.

Jede Veranstaltungsseite trägt in den Next.js-Flight-Daten
(`self.__next_f.push([1,"…"])`) ein vollständiges JSON-Objekt der
Ausgabe (`_event_objekt()` schneidet es heraus):

* `name`, `slug`, `editionFrom`/`editionTo`, `cancelled`, `visible`;
* `organizerLink` = die Veranstalterseite (Datenregel 2; oft ohne
  Schema, „www.inferno.ch/"), sonst bleibt die datasport-Seite als
  Portallink (`PORTAL_DOMAINS`);
* `town.de` (der Ort), `regions[].countryCode` (CHE/DEU/AUT/ITA) und
  `preciseLocation` (Koordinaten - Nominatim entfällt; bei ITA entscheidet
  `filter_dach()` über die Koordinaten, ob es Südtirol ist);
* `contests[]`: je Wettbewerb `name`, `discipline.name.de` (Volkslauf,
  Trail Run, Berglauf, Walking / Nordic Walking, Strassenrennen, Cross
  Country, Bike Marathon, Bergrennen, Andere …), `discipline.sportType
  .name.de` (Lauf, Rennrad, MTB, Triathlon, Langlauf, …), `from`/`to`
  (der Tag des Wettbewerbs bei mehrtägigen Veranstaltungen), `categories`
  (Altersklassen mit `ageFrom`/`ageTo`) und `sections` (Teilstrecken in
  METERN - bei einem Triathlon Swim/Bike/Run, bei einem Lauf meist eine).

Was daraus wird
---------------
* **Sportart aus `sportType`** (`SPORTART`), nicht aus dem Namen: Lauf →
  Laufen, Rennrad/MTB/Bike → Fahrrad, Triathlon und Duathlon → Triathlon
  (Kategorie Duathlon), Schwimmen → Schwimmen. Andere Sportarten
  (Langlauf, Ski & Snowboard, Hyathlon) werden übersprungen und gezählt.
* **Je Wettbewerb ein Eintrag** (Datenregel 1), Länge = Summe der
  Teilstrecken (bei Mehrsport Datenregel 15; das Label nennt die
  Aufteilung: „Short Distance 22,9 km (0,5 km Schwimmen / 17 km Rad /
  5,4 km Laufen)"). Nennt der Wettbewerbsname eine Dauer, ist es ein
  Zeitrennen (`dauer_h`, Datenregel 8).
* **Übersprungen** werden abgesagte und unsichtbare Ausgaben, Nachwuchs-
  Wettbewerbe (alle Altersklassen bis 17 Jahre oder ein Nachwuchswort im
  Namen: Kids, U12, Junior, Pfüderi …), Team-Formate (Staffel, Team
  Trophy, Couples, Gruppen, Firmen-Challenge - Datenregel 16), E-Bike-
  Klassen, Wettbewerbe ohne Strecke, die nur eine Anmeldeart sind
  („Voranmeldung", „Warteliste"), Serien mit mehreren Orten im Ortsfeld
  („Andorra / Selva Val Gardena / Riva del Garda" - eine Koordinate für
  vier Länder), Länder außerhalb der vier Regionen (Liechtenstein,
  Luxemburg) sowie Italien außerhalb Südtirols (über die Koordinaten).
* **Walking-Wettbewerbe bleiben als Laufen** mit dem Zusatz im Label -
  dieselbe (offene) Linie wie bei den 145 Walking-Zeilen der Laufkalender
  (CLAUDE.md, offene Punkte 19).
* **Kategorie**: `guess_art2()` über Wettbewerbsname und Disziplin
  (Trail Run/Berglauf → Trail, Strassenrennen → Straße, …); fällt nichts
  heraus, gilt die Sportart: Rennrad → Straße, MTB → Mountainbike.
* **Die Jahreszahl im Namen fällt** („gurtenCLASSIC 2026" → „gurtenCLASSIC"):
  datasport legt je Ausgabe eine Seite an, die anderen Quellen nennen die
  Veranstaltung ohne Jahr, und `is_same_event()` soll sie zusammenführen.
* **Ein Lauf in einer Veranstaltung mit Mehrsport-Namen** („Inferno
  Triathlon + Halbmarathon") bekommt den Namen seines Wettbewerbs, wenn
  der ein Wort des Veranstaltungsnamens trägt („Inferno Halbmarathon") -
  sonst machte `clean_events.fix_multisport_art1()` aus dem Halbmarathon
  beim nächsten Aufräumen wieder einen Triathlon (es liest nur den Namen).

Stand 30.09.2026 (erster Lauf): siehe README, „Quellen für den großen
Datenlauf".

Nutzung: `python3 scripts/datasport_scraper.py --help`
(Testlauf: `--dry-run --max-details 5`).
"""

from datetime import date
from pathlib import Path
import json
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper_lib import (  # noqa: E402
    Event,
    SiteConfig,
    fetch_page,
    guess_art1,
    guess_art2,
    in_suedtirol,
    parse_duration_h,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://datasport.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
EVENT_URL = f"{BASE_URL}/de/events/{{slug}}"
# Crawl-delay der KI-Crawler-Gruppe in robots.txt - siehe Rechtslage oben.
MINDEST_PAUSE = 10.0
# So viele vergangene Ausgaben hintereinander beenden den Durchlauf
# (die sitemap kippt nach den kommenden Ausgaben in die Vergangenheit).
ABBRUCH_NACH_VERGANGENEN = 5

# `sportType.name.de` → unsere Sportart. Duathlon ist die Mehrsport-Schublade
# (Datenregel 11): Powerman Zofingen führt ihn als eigene Sportart.
SPORTART = {"lauf": "Laufen", "rennrad": "Fahrrad", "mtb": "Fahrrad", "bike": "Fahrrad",
            "triathlon": "Triathlon", "duathlon": "Triathlon", "schwimmen": "Schwimmen"}
# Rückfall für die Kategorie, wenn Name und Disziplin nichts hergeben.
SPORTTYP_ART2 = {"rennrad": "Straße", "mtb": "Mountainbike", "bike": "Mountainbike"}
# Bezeichnungen der Teilstrecken (sections[].name) → Disziplin im Label.
TEILSTRECKE = [
    (re.compile(r"swim|schwimm|natation|nuoto", re.I), "Schwimmen"),
    (re.compile(r"mountain\s*bike|\bmtb\b", re.I), "MTB"),
    (re.compile(r"bike|velo|rad|cycl|vélo|bici", re.I), "Rad"),
    (re.compile(r"run|lauf|course|corsa|trail", re.I), "Laufen"),
]
_NACHWUCHS_NAME = re.compile(
    r"\bkids?\b|\bkind\b|kinder|jugend|schüler|scolar|pfüderi|junior|\bu\s?(?:[6-9]|1[0-8])\b|"
    r"mini\b|bambini|enfants|ragazzi", re.I)
_TEAM_NAME = re.compile(
    r"staffel|stafette|relay|relais|team|couples?|\bduo\b|gruppen|group|inter-?entreprises?|inter-?clubs?|"
    r"entreprises?|firmen|betrieb|"
    r"famigros|family|familie|famille|\d\s*(?:personnes|personen|persone)", re.I)
_EBIKE = re.compile(r"e-?bike|e-?mtb|ebike", re.I)
# Ein „Wettbewerb", der nur eine Anmeldeart ist (Voranmeldung, Warteliste) -
# zählt nur, wenn er keine Strecke nennt.
_KEIN_WETTBEWERB = re.compile(r"anmeldung|iscrizion|registration|inscription|warte\s*liste|waiting|ticket", re.I)
# Serien an mehreren Orten („Andorra / Selva Val Gardena / Riva del Garda")
# tragen EINE Koordinate für alle Rennen - nicht verortbar.
_MEHRERE_ORTE = re.compile(r"\s/\s")
_PROVINZ = re.compile(r"\s*\((?:[A-Z]{2}|[A-Z]{1,3}-\d+)\)\s*$")
LAND_CODE = {"CHE": "Schweiz", "DEU": "Deutschland", "AUT": "Österreich", "ITA": "Italien"}
_TESTSEITE = re.compile(r"test-flag", re.I)
_JAHR = re.compile(r"\b(20\d\d)\b")
_SLUG_JAHR = re.compile(r"(?<!\d)(20\d\d)(?!\d)")
_KM_IM_NAMEN = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*km", re.I)
_FLIGHT = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*</script>', re.S)
_MEHRSPORT_WORT = re.compile(r"triathlon|duathlon|aquathlon|swimrun|gigathlon|ironman", re.I)
_ALLGEMEIN = {"run", "lauf", "trail", "marathon", "halbmarathon", "triathlon", "bike",
              "race", "challenge", "cup", "classic", "tour", "the", "und", "and"}


# --------------------------------------------------------------------------
# sitemap.xml und Flight-Daten
# --------------------------------------------------------------------------

def slugs_aus_sitemap(xml: str) -> list[str]:
    """Die Slugs aller `/de/events/<slug>`-Adressen in der Reihenfolge
    der sitemap (kommende Ausgaben zuerst, siehe Modul-Doku)."""
    out: list[str] = []
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", xml, re.S):
        m = re.search(r"/de/events/([^/<\s]+)$", loc.strip())
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def slug_jahr(slug: str) -> int | None:
    """Die Jahreszahl im Slug („gurtenclassic-2026" → 2026), sonst None."""
    m = _SLUG_JAHR.search(slug)
    return int(m.group(1)) if m else None


def _flight_text(html: str) -> str:
    """Der Inhalt aller Next.js-Flight-Chunks als ein Text (die Chunks
    sind JavaScript-Strings; json.loads löst ihre Escapes auf)."""
    teile = []
    for chunk in _FLIGHT.findall(html):
        try:
            teile.append(json.loads('"' + chunk + '"'))
        except ValueError:
            continue
    return "".join(teile)


def _json_objekt_ab(text: str, start: int) -> str | None:
    """Das balancierte {…}-Objekt, das bei `start` beginnt (Strings mit
    Escapes werden übersprungen)."""
    tiefe = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif ch == "{":
            tiefe += 1
        elif ch == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start:i + 1]
        i += 1
    return None


def event_objekt(html: str, slug: str | None = None) -> dict | None:
    """Das Ausgabe-Objekt einer Veranstaltungsseite (das JSON mit
    `organizerLink`, `contests`, `town` …) - None, wenn die Seite keines
    trägt (404-Seite, Testseite)."""
    text = _flight_text(html)
    treffer = []
    pos = 0
    while True:
        i = text.find('"organizerLink"', pos)
        if i < 0:
            break
        start = text.rfind('{"id":', 0, i)
        roh = _json_objekt_ab(text, start) if start >= 0 else None
        pos = i + 1
        if not roh:
            continue
        try:
            obj = json.loads(roh)
        except ValueError:
            continue
        if isinstance(obj, dict) and "contests" in obj:
            treffer.append(obj)
    if not treffer:
        return None
    if slug:
        for obj in treffer:
            if obj.get("slug") == slug:
                return obj
    return treffer[0]


# --------------------------------------------------------------------------
# Aus dem Objekt werden Events
# --------------------------------------------------------------------------

def _datum(text) -> str | None:
    if not text or not isinstance(text, str):
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else None


def _de(d) -> str:
    if isinstance(d, dict):
        return (d.get("de") or d.get("en") or next(iter(d.values()), "") or "").strip()
    return (d or "").strip() if isinstance(d, str) else ""


def name_ohne_jahr(name: str) -> str:
    """„gurtenCLASSIC 2026" → „gurtenCLASSIC", „Claro Pizzo 2026 - 13°
    Edizione" → „Claro Pizzo - 13° Edizione"."""
    text = _JAHR.sub("", name or "")
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"^\s*[-–|·]\s*|\s*[-–|·]\s*$", "", text)
    return text.strip() or (name or "").strip()


def veranstalter_link(link, slug: str) -> str:
    """organizerLink mit Schema - oder die datasport-Seite als Portallink."""
    text = (link or "").strip() if isinstance(link, str) else ""
    if not text or text in ("-", "/") or "datasport.com" in text or "onreg." in text:
        return EVENT_URL.format(slug=slug)
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text.lstrip("/")
    if not re.match(r"^https?://[^/\s]+\.[^/\s]+", text):
        return EVENT_URL.format(slug=slug)
    return text


def ist_nachwuchs(contest: dict) -> bool:
    """Nachwuchs-Wettbewerb: Nachwuchswort im Namen, oder ALLE
    Altersklassen enden vor 18 (ein leeres `ageTo` gilt als offen)."""
    if _NACHWUCHS_NAME.search(contest.get("name") or ""):
        return True
    klassen = [k for k in (contest.get("categories") or []) if isinstance(k, dict)]
    if not klassen:
        return False
    return all(isinstance(k.get("ageTo"), (int, float)) and k["ageTo"] <= 17 for k in klassen)


def _teilstrecken(contest: dict) -> list[tuple[str, float | None]]:
    """(Bezeichnung, km) je Teilstrecke; km None, wenn die Quelle keine
    Meter nennt."""
    out = []
    for s in contest.get("sections") or []:
        if not isinstance(s, dict):
            continue
        m = s.get("distance")
        km = round_km(m / 1000) if isinstance(m, (int, float)) and m > 0 else None
        out.append(((s.get("name") or "").strip(), km))
    return out


def _disziplin(bezeichnung: str) -> str | None:
    for muster, wort in TEILSTRECKE:
        if muster.search(bezeichnung):
            return wort
    return None


def _label(name: str, km: float | None, stunden: float | None,
           teile: list[tuple[str, float | None]], mehrsport: bool) -> str:
    text = name.strip()
    if stunden is not None:
        return text
    if km is None:
        return text
    if not _KM_IM_NAMEN.search(text) or mehrsport:
        text = f"{text} {km:g} km"
    if mehrsport and len(teile) >= 2 and all(k for _, k in teile):
        text += " (" + " / ".join(
            f"{k:g} km {_disziplin(b) or b}".strip() for b, k in teile) + ")"
    return text


def _mehrsport_art2(name: str, teile: list[tuple[str, float | None]], config: SiteConfig) -> str:
    art2 = guess_art2(name, config, "Triathlon")
    if art2 and art2 != config.default_art2 and art2 != "Straße":
        return art2
    disziplinen = {_disziplin(b) for b, _ in teile}
    disziplinen.discard(None)
    if disziplinen == {"Rad", "Laufen"}:
        return "Duathlon"
    if disziplinen == {"Schwimmen", "Laufen"}:
        return "Aquathlon"
    return art2 or "Straße"


def _lauf_name(event_name: str, contest_name: str) -> str:
    """Der Name für eine Lauf-/Rad-Zeile in einer Veranstaltung, deren
    NAME eine andere Sportart nennt (siehe Modul-Doku): der Wettbewerbs-
    name, wenn er ein unverwechselbares Wort des Veranstaltungsnamens
    trägt - sonst der Veranstaltungsname."""
    woerter = {w.lower() for w in re.findall(r"[\wäöüÄÖÜß]{4,}", event_name)} - _ALLGEMEIN
    contest_woerter = {w.lower() for w in re.findall(r"[\wäöüÄÖÜß]{4,}", contest_name)}
    if woerter & contest_woerter and len(contest_name.split()) >= 2:
        return contest_name.strip()
    # Sonst der Kern des Veranstaltungsnamens (alles vor dem ersten
    # Mehrsport-Wort) plus der Wettbewerb: „Inferno" + „Trail".
    m = _MEHRSPORT_WORT.search(event_name)
    kern = event_name[:m.start()].strip(" -–+/&|") if m else ""
    if kern and contest_name.strip():
        return f"{kern} {contest_name.strip()}"
    return event_name


def events_aus_objekt(obj: dict, config: SiteConfig,
                      bericht: dict | None = None) -> list[Event]:
    """Das Ausgabe-Objekt einer Seite → null, ein oder mehrere Events.
    `bericht` zählt, was übersprungen wurde (Schlüssel = Grund)."""
    z = bericht if bericht is not None else {}

    def zaehle(grund: str) -> None:
        z[grund] = z.get(grund, 0) + 1

    if not obj or obj.get("cancelled") or obj.get("visible") is False:
        zaehle("abgesagt/unsichtbar")
        return []
    slug = obj.get("slug") or ""
    name = name_ohne_jahr(_de(obj.get("name")))
    start_ausgabe = _datum(obj.get("editionFrom"))
    ende_ausgabe = _datum(obj.get("editionTo")) or start_ausgabe
    ort = _PROVINZ.sub("", _de(obj.get("town")))   # „Badia (BZ)" → „Badia"
    if not name or not start_ausgabe or not ort:
        zaehle("ohne Name/Datum/Ort")
        return []
    if _MEHRERE_ORTE.search(ort):
        zaehle("Serie an mehreren Orten")
        return []
    regionen = [r for r in (obj.get("regions") or []) if isinstance(r, dict)]
    code = (regionen[0].get("countryCode") or "").upper() if regionen else ""
    land = LAND_CODE.get(code)
    if code and land is None:
        # Liechtenstein, Luxemburg, Norwegen: die Seite kennt das Land,
        # es gehört nur nicht zu unseren vier Regionen.
        zaehle(f"Land {code}")
        return []
    lage = obj.get("preciseLocation") or {}
    lat = lage.get("latitude") if isinstance(lage, dict) else None
    lon = lage.get("longitude") if isinstance(lage, dict) else None
    if land == "Italien" and lat is not None and lon is not None and not in_suedtirol(lat, lon):
        # Trentino, Gardasee, Dolomiti di Brenta: Italien, aber nicht
        # Südtirol (Datenregel 4) - sonst räumt clean_events.py die Zeilen
        # jede Woche wieder heraus (zehn im ersten Lauf).
        zaehle("Italien außerhalb Südtirols")
        return []
    url = veranstalter_link(obj.get("organizerLink"), slug)
    name_sagt = guess_art1(name, config)   # nennt der NAME eine andere Sportart?

    events: list[Event] = []
    gesehen: set = set()
    for contest in obj.get("contests") or []:
        if not isinstance(contest, dict):
            continue
        cname = _de(contest.get("name"))
        disziplin = contest.get("discipline") or {}
        sporttyp = _de((disziplin.get("sportType") or {}).get("name")).lower()
        disz_name = _de(disziplin.get("name"))
        art1 = SPORTART.get(sporttyp)
        if art1 is None:
            zaehle(f"Sportart {sporttyp or '?'}")
            continue
        if _EBIKE.search(cname):
            zaehle("E-Bike")
            continue
        if ist_nachwuchs(contest):
            zaehle("Nachwuchs")
            continue
        if _TEAM_NAME.search(cname):
            zaehle("Team/Staffel")
            continue
        teile = _teilstrecken(contest)
        stunden = parse_duration_h(cname)
        km = None
        if stunden is None:
            bekannt = [k for _, k in teile if k]
            if bekannt and len(bekannt) == len(teile):
                km = round_km(sum(bekannt))
            elif len(bekannt) == 1 and len(teile) == 1:
                km = bekannt[0]
            if km is None and not bekannt:
                # Keine Meter in den Teilstrecken („12 km Nordic Walking und
                # Walking" nennt sie nur im Namen) - genau EINE Zahl zählt.
                zahlen = _KM_IM_NAMEN.findall(cname)
                if len(zahlen) == 1:
                    km = round_km(float(zahlen[0].replace(",", ".")))
        if km is None and stunden is None and (not cname or _KEIN_WETTBEWERB.search(cname)):
            zaehle("ohne Strecke (Anmeldeart oder ohne Namen)")
            continue
        mehrsport = art1 == "Triathlon"
        if mehrsport:
            art2 = ("Duathlon" if sporttyp == "duathlon"
                    else _mehrsport_art2(f"{cname} {name}", teile, config))
        else:
            art2 = (guess_art2(f"{cname} {disz_name}", config, art1)
                    or guess_art2(name, config, art1)
                    or SPORTTYP_ART2.get(sporttyp))
        zeilen_name = name
        if not mehrsport and name_sagt != "Laufen" and name_sagt != art1:
            zeilen_name = _lauf_name(name, cname)
            if zeilen_name != name:
                zaehle("Name aus Wettbewerb")
        start = _datum(contest.get("from")) or start_ausgabe
        ende = _datum(contest.get("to")) or ende_ausgabe or start
        if ende < start:
            ende = start
        # Dieselbe Strecke am selben Tag nur einmal (Lizenz- und Hobbyklasse
        # über dieselbe Distanz; `dedupe_key()` und der Kalender-Dateiname
        # kennen kein Label). Ohne Maßzahl entscheidet der Wettbewerbsname.
        schluessel = ((art1, km, stunden, zeilen_name, start) if (km is not None or stunden is not None)
                      else (art1, zeilen_name, start, cname.lower()))
        if schluessel in gesehen:
            zaehle("gleiche Strecke doppelt")
            continue
        gesehen.add(schluessel)
        events.append(Event(
            land=land, name=zeilen_name, standort=ort,
            lat=lat if isinstance(lat, (int, float)) else None,
            lon=lon if isinstance(lon, (int, float)) else None,
            art1=art1, art2=art2, datum_start=start, datum_ende=ende,
            laenge_km=km, dauer_h=stunden,
            wettbewerb=_label(cname or disz_name, km, stunden, teile, mehrsport) or None,
            veranstalter_url=url,
        ))
    return events


# --------------------------------------------------------------------------
# Abruf
# --------------------------------------------------------------------------

def _lade_sitemap(session, pause: float) -> str | None:
    """Die sitemap.xml (8 MB) - mit längerer Frist als fetch_page() und
    einem zweiten Versuch: Am 30.09.2026 brach ein Lauf am Lesetimeout
    des Proxys ab, bevor er eine einzige Seite gesehen hatte."""
    for versuch in (1, 2):
        try:
            resp = session.get(SITEMAP_URL, timeout=90)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 - jeder Fehler wird gemeldet
            print(f"  ⚠ sitemap.xml, Versuch {versuch}: {exc}")
            time.sleep(pause)
    return None


def fetch_datasport(session, config, delay, max_pages, render_js) -> list[Event]:
    pause = max(float(delay or 0), MINDEST_PAUSE)
    heute = date.today().isoformat()
    print(f"→ Lade {SITEMAP_URL} ...")
    xml = _lade_sitemap(session, pause)
    if not xml:
        return []
    slugs = slugs_aus_sitemap(xml)
    print(f"  {len(slugs)} Veranstaltungsseiten in der sitemap; Pause {pause:.0f} s je Seite.")
    events: list[Event] = []
    bericht: dict = {}
    abgerufen = 0
    vergangen_folge = 0
    uebersprungen_jahr = 0
    ausgaben = 0
    fehler = 0
    for slug in slugs:
        if _TESTSEITE.search(slug):
            continue
        jahr = slug_jahr(slug)
        if jahr is not None and jahr < date.today().year:
            uebersprungen_jahr += 1
            continue
        if config.max_details and abgerufen >= config.max_details:
            print(f"  --max-details {config.max_details} erreicht.")
            break
        time.sleep(pause)
        abgerufen += 1
        html = fetch_page(session, EVENT_URL.format(slug=slug), render_js)
        if not html:
            # Ein Lesefehler (Timeout am Proxy, kurzer Aussetzer) darf keine
            # Ausgabe kosten - einmal nach der Pause erneut versuchen.
            time.sleep(pause)
            html = fetch_page(session, EVENT_URL.format(slug=slug), render_js)
        if not html:
            fehler += 1
            continue
        obj = event_objekt(html, slug)
        if not obj:
            print(f"  ⚠ {slug}: kein Ausgabe-Objekt auf der Seite")
            continue
        ende = _datum(obj.get("editionTo")) or _datum(obj.get("editionFrom"))
        if ende and ende < heute:
            vergangen_folge += 1
            if vergangen_folge >= ABBRUCH_NACH_VERGANGENEN:
                print(f"  {ABBRUCH_NACH_VERGANGENEN} vergangene Ausgaben hintereinander "
                      f"(zuletzt {slug}, {ende}) - die sitemap ist hier in der Vergangenheit.")
                break
            continue
        vergangen_folge = 0
        ausgaben += 1
        neu = events_aus_objekt(obj, config, bericht)
        print(f"  {slug}: {len(neu)} Strecke(n)")
        events.extend(neu)
    print(f"\n→ {abgerufen} Seiten abgerufen ({uebersprungen_jahr} Slugs mit altem Jahr "
          f"übersprungen, {fehler} nicht ladbar), {ausgaben} kommende Ausgaben, "
          f"{len(events)} Strecken-Einträge.")
    if bericht:
        print("  Übersprungen/Hinweise: " + ", ".join(f"{k}: {v}" for k, v in sorted(bericht.items())))
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=f"{BASE_URL}/de/events",
    default_art1="Laufen",
    custom_fetch=fetch_datasport,
    note="datasport_scraper.py: sitemap.xml als Liste, je Ausgabe eine Seite (Next.js-Flight-"
         "Daten), 10 s Pause laut robots.txt-Gruppe der KI-Crawler; freigegeben am 30.09.2026.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
