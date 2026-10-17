#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
turbosport_scraper.py
=====================

Liest die Rennseiten von https://turbo-sport.eu (BRV Timing, die
Transponder-Zeitnahme des Bayerischen Radsportverbands e.V.) und
ergänzt die **offenen** Wettbewerbe (Jedermann- und Hobbyklassen) der
bayerischen Straßenrennen in `events.json` (siehe `scraper_lib.py`).

Rechtslage (geprüft am 24.09.2026, vom Nutzer verlinkt: „turbo-sport
ist sehr gut für lokale Rennen")
------------------------------------------------------------------------
robots.txt: 404 (= keine Einschränkung). Impressum (Herausgeber
Bayerischer Radsportverband e.V.): nur der allgemeine Urheberrechts-
hinweis auf „Dokumente (Text, Bild und Ton)", kein Verbot des
Auslesens; die Datenschutzerklärung sagt nichts dazu. 2 s Pause je
Abruf, wie bei den anderen Quellen.

Struktur (am 24.09.2026 an der Live-Seite kalibriert)
-------------------------------------------------------
TYPO3-Seiten, alles server-seitig gerendert. `/events` trägt in der
Unternavigation (`.subnav-link`) EINEN Eintrag je Rennen der Saison,
beschriftet „26.09.26 Obergünzburger RR" (Datum dd.mm.yy + Kurzname);
die Serie („2026 Donnerstagsrennen Serie") ohne Datum. Die Rennseite
(`/events/<slug>` oder `/veranstaltungen/<slug>`):

* `<h2>` mit dem vollen Namen und dem Datum: „Großer Fritz Neuser Preis
  am Samstag, 3. Oktober 2026".
* **Vor dem Rennen** eine Tabelle „Rennen und Altersklassen" mit den
  Spalten Kategorie | JG von | JG bis | Wettbewerb | Runden | Distanz |
  Nenngeld | Startzeit. Die Spalte *Wettbewerb* sagt, wer starten darf:
  „Lizenzklasse" (BDR-Lizenz nötig), „Jedermann" oder „Hobbyklasse".
  **Nach dem Rennen** stehen dort stattdessen Ergebnislisten (Spalten
  StNr./Name/Verein) - solche Seiten liefern nichts, und das ist
  richtig so: vergangene Rennen gehören nicht in die Liste.
* Links „Link zur Event Website" / „Link zur Veranstalter Website" /
  „Link zur Website vom Veranstalter" → `veranstalter_url` (Datenregel
  2). Die rad-net-Ausschreibung und die Datasport-Anmeldung sind
  Portallinks und werden nicht übernommen; ohne Veranstalterlink bleibt
  die turbo-sport-Seite stehen (in `PORTAL_DOMAINS`).

Was daraus wird
---------------
* **Alle Klassen, auch die Lizenzklassen** (vom Nutzer am 24.09.2026
  entschieden: „Bitte auch die mit BDR Lizenz aufnehmen"). Die erste
  Fassung nahm nur Jedermann- und Hobbyklassen, weil ein Lizenzrennen
  die BDR-Lizenz verlangt; der Nutzer will sie trotzdem in der Liste -
  wer eine Lizenz hat, sucht sein Rennen genauso. Die Klasse steht im
  Label („Lizenzklasse 60 km"), damit man es sieht. Wer das umdrehen
  will: `KLASSEN_FILTER` auf `OFFENE_KLASSEN` setzen.
* Je verschiedener Distanz EIN Eintrag (Datenregel 1); das Label nennt
  die Klassen, die über diese Distanz fahren, samt Distanz („Lizenzklasse
  / Jedermann 30 km"). Zwei Zeilen für Lizenz und Jedermann über dieselbe
  Distanz gehen nicht: `dedupe_key()` (Name + Datum + Distanz) und der
  Kalender-Dateiname kennen kein Label, die zweite Zeile fiele beim
  Einsammeln weg bzw. hätte dieselbe `.ics`-Datei.
* **Der Ort steht nicht auf der Seite.** Er kommt aus dem NAMEN
  („Obergünzburger", „Schwabacher Stadtparkrennen", „Dachau") - ein
  Wort des Namens, notfalls ohne die Adjektivendung (-er, -ener), muss
  ein Ort in **Bayern** laut `places.json` sein; die Koordinaten kommen
  gleich mit, Nominatim ist nicht nötig. Zweite Quelle ist der Hostname
  der Veranstalterseite (`rfv-prien.de` → Prien am Chiemsee,
  `rsv-passau.de` → Passau), dieselbe Regel wie in
  `veranstalter_links.py` (Ort im Host). Ohne erkennbaren Ort **kein
  Eintrag**, nur eine Meldung - geraten wird nie (Datenregel 4).
  Ein Wort, das auf MEHRERE bayerische Orte passt, zählt nicht.
* Kategorie: BRV Timing misst Straßenrennen (Straßenpreise, Rundstrecken-
  rennen, Kriterien, Bergsprints, Zeitfahren); Voreinstellung deshalb
  „Straße", ein Zeitfahren erkennt `ART2_KEYWORDS_FAHRRAD`.
* Die Serie „Donnerstagsrennen" (fünf Termine, Hobbyklasse) wird
  übersprungen: Die Seite nennt weder Ort noch je Termin eine eigene
  Tabelle; die Termine stehen nur als Linktexte der rad-net-
  Ausschreibungen. Gemeldet, nicht geraten.

Die Saison steht ab dem Frühjahr auf der Seite; im September 2026
lieferte sie noch zwei Rennen mit Jedermann-Klassen (Schwabach am
03./04.10.). Der Wert der Quelle kommt mit der Saison 2027.

Nutzung: `python3 scripts/turbosport_scraper.py --help`
(Testlauf: `--dry-run`).
"""

from pathlib import Path
import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from scraper_lib import (  # noqa: E402
    GERMAN_MONTHS,
    Event,
    SiteConfig,
    fetch_page,
    guess_art2,
    parse_flexible_date,
    round_km,
    run_scraper_cli,
)

BASE_URL = "https://turbo-sport.eu"
EVENTS_URL = f"{BASE_URL}/events"
PLACES_PATH = Path(__file__).resolve().parent.parent / "places.json"
REGION = "Bayern"

# Spalte "Wettbewerb": wer starten darf. Lizenzklassen brauchen die
# BDR-Lizenz; seit dem 24.09.2026 kommen sie trotzdem mit (Entscheidung
# des Nutzers). KLASSEN_FILTER = OFFENE_KLASSEN liefert wieder nur
# Jedermann und Hobby.
OFFENE_KLASSEN = re.compile(r"jedermann|hobby", re.I)
KLASSEN_FILTER: "re.Pattern | None" = None

# Linktexte, hinter denen die Veranstalterseite steht (nicht rad-net,
# nicht Datasport, nicht Komoot).
_VERANSTALTER_LINK = re.compile(r"event[- ]?website|veranstalter[- ]?website|website vom veranstalter", re.I)
_KEIN_VERANSTALTER = ("rad-net.de", "datasport", "komoot", "turbo-sport.eu", "brv-timing")

# "Großer Fritz Neuser Preis am Samstag, 3. Oktober 2026"
_H2_DATUM = re.compile(
    r"^(?P<name>.+?)\s+am\s+(?:[A-Za-zäöü]+(?:sonntag|montag|tag)?,?\s*)?(?P<tag>\d{1,2})\.\s*"
    r"(?P<monat>[A-Za-zäöüÄÖÜ]+)\s+(?P<jahr>\d{4})\s*$",
    re.I,
)
# "26.09.26 Obergünzburger RR" (Unternavigation)
_NAV_DATUM = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})\s+(.+)$")

# Wörter, die im Namen wie ein Ort aussehen könnten, aber keiner sind.
_KEIN_ORT = {"preis", "rennen", "kriterium", "cup", "sturm", "veste", "giro", "crit",
             "stadtmeisterschaft", "einzelzeitfahren", "bergsprint", "bergkriterium",
             "rundstreckenrennen", "pfingstradrennen", "straßenpreis", "gedächtnisrennen",
             "vierer", "mannschaftszeitfahren", "inklusiver", "offene", "großer", "grosser",
             "tour", "allgäu", "allgäuer", "bergzeitfahren", "sparkasse", "brauerei"}

_orte_cache: dict | None = None


def lade_orte(pfad: Path = PLACES_PATH) -> dict[str, list[tuple[str, float, float]]]:
    """Alle bayerischen Orte aus places.json: Name (klein) -> [(Name, lat, lon), …].
    Mehrere Treffer je Name bleiben erhalten - dann ist der Name mehrdeutig."""
    global _orte_cache
    if _orte_cache is not None:
        return _orte_cache
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    region = daten["regionen"].index(REGION)
    orte: dict[str, list[tuple[str, float, float]]] = {}
    for eintrag in daten["orte"]:
        if eintrag[2] == region:
            orte.setdefault(eintrag[0].lower(), []).append((eintrag[0], eintrag[3], eintrag[4]))
    _orte_cache = orte
    return orte


def _ortskandidaten(wort: str) -> list[str]:
    """"Obergünzburger" -> ["obergünzburger", "obergünzburg"], "Burggener" ->
    [.., "burggen"], "Landshuter" -> [.., "landshut"], "Patrichinger" ->
    [.., "patriching"]. Die Endungen, mit denen ein bayerischer Ortsname
    zum Adjektiv wird."""
    w = wort.lower().strip(",.:;'\"()")
    kandidaten = [w]
    for endung in ("ener", "er"):
        if w.endswith(endung) and len(w) - len(endung) >= 4:
            kandidaten.append(w[: -len(endung)])
    return kandidaten


def ort_aus_name(name: str, orte: dict | None = None) -> tuple[str, float, float] | None:
    """Der Ort im Rennnamen, mit Koordinaten aus places.json - oder None.
    Ein Wort, das auf MEHRERE bayerische Orte passt, zählt nicht."""
    orte = orte if orte is not None else lade_orte()
    for wort in re.split(r"[\s/–-]+", name):
        wort = re.sub(r"^[\d.]+", "", wort)  # "1.Obergünzburger" -> "Obergünzburger"
        if len(wort) < 4 or not wort[:1].isupper() or wort.lower() in _KEIN_ORT:
            continue
        for kandidat in _ortskandidaten(wort):
            treffer = orte.get(kandidat)
            if treffer and len(treffer) == 1:
                return treffer[0]
    return None


def ort_aus_slug(url: str | None, orte: dict | None = None) -> tuple[str, float, float] | None:
    """`/events/schwabacher-stadtparkrennen` -> Schwabach: Der Pfad der
    turbo-sport-Seite trägt oft den Ort, den der Rennname nicht nennt
    („Großer Fritz Neuser Preis")."""
    if not url:
        return None
    slug = urlparse(url).path.rsplit("/", 1)[-1]
    woerter = " ".join(t.capitalize() for t in re.split(r"[-_]+", slug) if t)
    return ort_aus_name(woerter, orte)


def ort_aus_host(url: str | None, orte: dict | None = None) -> tuple[str, float, float] | None:
    """`https://rfv-prien.de/...` -> Prien am Chiemsee: ein Wortteil des
    Hostnamens ist ein eindeutiger bayerischer Ort (Umlaute als ae/oe/ue)."""
    if not url:
        return None
    orte = orte if orte is not None else lade_orte()
    host = urlparse(url).netloc.lower().removeprefix("www.")
    teile = [t for t in re.split(r"[.\-_0-9]+", host) if len(t) >= 5]
    for teil in teile:
        # Voller Ortsname als Teil (prien) oder der Ort beginnt mit dem Teil
        # (prien -> "prien am chiemsee").
        passend = [k for k in orte if k == teil or k.startswith(teil + " ")
                   or k.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss") == teil]
        if len(passend) == 1 and len(orte[passend[0]]) == 1:
            return orte[passend[0]][0]
    return None


def parse_events_liste(html: str) -> list[dict]:
    """Die Unternavigation von /events: je Rennen URL, Datum (aus
    'dd.mm.yy'), Kurzname. Einträge ohne Datum (die Serie) tragen None."""
    soup = BeautifulSoup(html, "html.parser")
    eintraege = []
    gesehen = set()
    for a in soup.select("a.subnav-link[href], nav a[href]"):
        href = a.get("href") or ""
        if not re.match(r"^/(events|veranstaltungen)/[^/#?]+$", href) or href in gesehen:
            continue
        gesehen.add(href)
        titel = (a.get("title") or a.get_text(" ", strip=True)).strip()
        m = _NAV_DATUM.match(titel)
        datum = None
        kurz = titel
        if m:
            datum = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"
            kurz = m.group(4).strip()
        eintraege.append({"url": urljoin(BASE_URL, href), "datum": datum, "kurzname": kurz})
    return eintraege


def parse_rennseite(html: str) -> dict:
    """Name, Datum, Veranstalterlink und die offenen Klassen einer Rennseite."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup
    name = datum = None
    for h2 in main.select("h2"):
        text = h2.get_text(" ", strip=True)
        m = _H2_DATUM.match(text)
        if m and GERMAN_MONTHS.get(m.group("monat").lower()):
            name = m.group("name").strip()
            datum = parse_flexible_date(
                f"{int(m.group('tag')):02d}.{GERMAN_MONTHS[m.group('monat').lower()]:02d}.{m.group('jahr')}")
            break
        if not name and text and not text.endswith(":") and len(text) > 8:
            name = text  # erster Titel ohne Datum (Serie)
    veranstalter_url = None
    for a in main.select("a[href^='http']"):
        if _VERANSTALTER_LINK.search(a.get_text(" ", strip=True)):
            href = a["href"]
            if not any(k in href for k in _KEIN_VERANSTALTER):
                veranstalter_url = href
                break
    klassen: list[dict] = []
    lizenz = 0
    for table in main.select("table"):
        kopf = [th.get_text(" ", strip=True).rstrip(":").lower() for th in table.select("tr:first-child th, tr:first-child td")]
        if "wettbewerb" not in kopf or "distanz" not in kopf:
            continue
        iw, idist, ikat = kopf.index("wettbewerb"), kopf.index("distanz"), kopf.index("kategorie") if "kategorie" in kopf else 0
        for tr in table.select("tr")[1:]:
            zellen = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(zellen) <= max(iw, idist):
                continue
            mk = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*km", zellen[idist], re.I)
            km = round_km(float(mk.group(1).replace(",", "."))) if mk else None
            if not OFFENE_KLASSEN.search(zellen[iw]):
                lizenz += 1
                if KLASSEN_FILTER is not None and not KLASSEN_FILTER.search(zellen[iw]):
                    continue
            klassen.append({"klasse": zellen[iw], "kategorie": zellen[ikat], "km": km})
    return {"name": name, "datum": datum, "veranstalter_url": veranstalter_url,
            "klassen": klassen, "lizenzklassen": lizenz}


KLASSEN_REIHENFOLGE = ["Lizenzklasse", "Jedermann", "Hobbyklasse"]


def klassen_name(wettbewerb: str) -> str:
    """Die Spalte „Wettbewerb" auf drei Werte gebracht: Hobbyklasse, Jedermann, sonst Lizenzklasse."""
    if re.search(r"hobby", wettbewerb, re.I):
        return "Hobbyklasse"
    if re.search(r"jedermann", wettbewerb, re.I):
        return "Jedermann"
    return "Lizenzklasse"


def events_aus_rennseite(seite: dict, url: str, datum_nav: str | None,
                         config: SiteConfig, orte: dict | None = None) -> tuple[list[Event], str | None]:
    """Ein Event je Klasse und Distanz - oder ([], Grund)."""
    name = seite.get("name")
    datum = seite.get("datum") or datum_nav
    if not name or not datum:
        return [], "kein Name/Datum"
    if not seite["klassen"]:
        return [], ("nur Lizenzklassen (ausgefiltert)" if seite["lizenzklassen"] else "keine Ausschreibungstabelle (vorbei?)")
    ort = (ort_aus_name(name, orte) or ort_aus_slug(url, orte)
           or ort_aus_host(seite.get("veranstalter_url"), orte))
    if not ort:
        return [], "Ort nicht erkennbar"
    standort, lat, lon = ort
    events: list[Event] = []
    je_km: dict = {}
    for k in seite["klassen"]:
        eintrag = je_km.setdefault(k["km"], {"klassen": [], "kategorien": []})
        klasse = klassen_name(k["klasse"])
        if klasse not in eintrag["klassen"]:
            eintrag["klassen"].append(klasse)
        eintrag["kategorien"].append(k["kategorie"])
    for km, eintrag in je_km.items():
        klassen = " / ".join(sorted(eintrag["klassen"], key=KLASSEN_REIHENFOLGE.index))
        label = f"{klassen} {km:g} km" if km else klassen
        ev = Event(land="Deutschland", name=name, standort=standort, lat=lat, lon=lon,
                   art1="Fahrrad", datum_start=datum, datum_ende=datum,
                   laenge_km=km, wettbewerb=label,
                   veranstalter_url=seite.get("veranstalter_url") or url)
        ev.art2 = guess_art2(f"{name} {' '.join(eintrag['kategorien'])}", config, "Fahrrad") or "Straße"
        events.append(ev)
    return events, None


def fetch_turbosport_events(session, config, delay, max_pages, render_js) -> list[Event]:
    print(f"→ Lade {EVENTS_URL} ...")
    html = fetch_page(session, EVENTS_URL, render_js=False)
    if not html:
        print("  ⚠ Übersicht nicht abrufbar.")
        return []
    liste = parse_events_liste(html)
    print(f"  ✓ {len(liste)} Rennseite(n) in der Navigation.")
    orte = lade_orte()
    events: list[Event] = []
    uebersprungen: list[str] = []
    for i, e in enumerate(liste):
        if config.max_details and i >= config.max_details:
            break
        time.sleep(delay)
        seite_html = fetch_page(session, e["url"], render_js=False)
        if not seite_html:
            uebersprungen.append(f"{e['kurzname']}: nicht abrufbar")
            continue
        seite = parse_rennseite(seite_html)
        neue, grund = events_aus_rennseite(seite, e["url"], e["datum"], config, orte)
        if grund:
            uebersprungen.append(f"{seite.get('name') or e['kurzname']} ({e['datum'] or 'ohne Datum'}): {grund}")
        events.extend(neue)
    if uebersprungen:
        print(f"\n  Übersprungen ({len(uebersprungen)}):")
        for zeile in uebersprungen:
            print(f"   - {zeile}")
    print(f"\n→ {len(events)} Wettbewerbe aus {len(liste)} Rennseiten.")
    return events


CONFIG = SiteConfig(
    base_url=BASE_URL,
    calendar_url=EVENTS_URL,
    default_art1="Fahrrad",
    default_art2="Straße",
    custom_fetch=fetch_turbosport_events,
    note="turbosport_scraper.py: BRV Timing (Bayerischer Radsportverband), robots.txt 404, "
         "Impressum ohne Verbot (24.09.2026); nur Jedermann-/Hobbyklassen, Ort aus dem Namen.",
)

if __name__ == "__main__":
    run_scraper_cli(CONFIG)
