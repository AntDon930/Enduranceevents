#!/usr/bin/env python3
"""
scripts/insta_inhalte.py
========================

Was der Instagram-Account „AusdauerMaschine" an einem Tag postet - und
mit welcher Caption. Ohne Netz, ohne Video: nur die Planung. Das Video
baut scripts/insta_video.py, das Posten scripts/insta_posten.py, alles
zusammen scripts/insta_lauf.py (siehe README, Abschnitt „Instagram").

Der Wochenplan (Europe/Berlin, vom Datum bestimmt - kein Gedächtnis
nötig, derselbe Tag ergibt immer denselben Beitrag). Seit dem 16.10.2026
neu, vom Nutzer verlangt: „Die Leute wollen keine langweiligen
Zusammenfassungen sehen" - jedes Format beginnt in der ERSTEN Sekunde mit
einer großen Zahl oder Frage (Folie „hook", sofort sichtbar), zeigt die
Rennen einzeln und schnell (Folie „event", im Takt des Beats) und endet
mit einer Aufforderung, die Instagram belohnt (teilen, speichern,
kommentieren):

    Mo  krass        das längste Lauf-/Rad-/Schwimm-/Zeitrennen der
                     nächsten 2 Monate - „161 KM. AM STÜCK."
    Di  naehe        rund um eine Großstadt (50 km, 4 Wochen), Rotation
                     über STAEDTE - „Schick das deinem Laufpartner"
    Mi  wuerdest     ein ungewöhnliches Rennen (Backyard, 24 h, Ultra,
                     Hindernis, Freiwasser) - „Würdest du? Ja oder nein"
    Do  humor        Läuferhumor aus humor.json (mit Clips: clip)
    Fr  wochenende   „Was machst du am Wochenende?" + drei Tipps
    Sa  saison       „Speicher dir das": Marathons/Triathlons/… in einem
                     Monat 3-5 Monate voraus
    So  moment       ein großer Moment des Ausdauersports

Zwei Tage im Monat haben ein eigenes Format (seit 27.10.2026, vom Nutzer:
„Instagram konzentriert sich auf die großen Events" – und gleich danach:
„eine gesunde Anzahl … die 10-20 größten Events im Monat", die Schwelle
5.000 war nur ein Beispiel). Beide zeigen nur Events aus
marketing/instagram/grosse_events.json (recherchiert, mit Starterzahl und
Anmeldestart samt Quelle) und deren geprüfte LOGOS (insta_logos.py):

    letzter Fr  monat      „375 EVENTS IM NOVEMBER 2026" - dann die Logos der
                           bis zu 20 größten Events des nächsten Monats (nach
                           Starterzahl) im Takt (ein Schlag je Logo), Farbe
                           und Schwarzweiß im Wechsel
    1. des Monats  anmeldung  „Diese Rennen öffnen im November die Anmeldung"
                           - je Event Logo, Anmeldestart, Renntermin

Fehlen dafür Events (monat: unter 6, anmeldung: unter 3), gilt der
normale Wochenplan.

Jeden zweiten Montag (ungerade Kalenderwoche) statt „krass" das Format
**laengste**: eine animierte Balkengrafik der längsten Lauf- und
Radrennen, „Welches würdest du schaffen?".

Dazu jeden zweiten Samstag (gerade Kalenderwoche) statt „saison" das
Format **top**: die 3/5/7/10 größten Marathon-, Halbmarathon-, Ultra-,
Trail-Events, Radmarathons oder Triathlons der nächsten 12 Monate, nach
Datum, ohne Rangfolge; Kategorie, Anzahl und Design (Karte, einzeln,
Raster, Zeitleiste) wechseln (vom Nutzer am 27.10.2026: „Top 5 Marathons
im Jahr … auf einer Karte … die 5 Logos oben" und „es muss nicht immer
Top 5 sein … nicht bewertet werden wer der beste … unterschiedliche
Designs in der Darstellung").

Die alten Formate (wochenvorschau, spotlight, region) bleiben über
--format erreichbar, der Plan nutzt sie nicht mehr.

Dazu je Tag bis zu zwei STORIES (stories_fuer): das Rennen der nächsten
Tage und ein Countdown zu einem großen Rennen (100/60/30/14/7 Tage),
sonst ein Hinweis auf das neue Reel.

Jahrestag: Hat ein Moment aus momente.json HEUTE Jahrestag, ersetzt er
an Di/Mi/Do/So den geplanten Beitrag („Heute vor 7 Jahren …").

WARUM KEINE TV-AUSSCHNITTE: Fernseh- und Veranstalterbilder bekannter
Rennen (Olympia, Ironman, Tour de France, Marathon-Majors) gehören den
Rechteinhabern. Instagram erkennt sie automatisch (Rights Manager),
sperrt die Reels und löscht Accounts nach wiederholten Verstößen; in
Deutschland kommt die Abmahnung dazu - und das Impressum nennt den
Betreiber. Die „Momente" erzählen deshalb die FAKTEN (die sind frei)
über lizenzfreiem Hintergrundmaterial, und Clips kommen nur aus
clips.json mit eingetragener Lizenz (insta_video.py prüft sie).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
MARKETING = WURZEL / "marketing" / "instagram"
MOMENTE_DATEI = MARKETING / "momente.json"
CLIPS_DATEI = MARKETING / "clips.json"

ACCOUNT = "ausdauermaschine"
SEITE = "endurance-events.de"
# Der Link für die Profilbeschreibung. utm_source=instagram ordnet den
# Besuch im Dashboard dem Kanal Instagram zu (stats_aggregate.js, kanal()).
BIO_LINK = "https://endurance-events.de/?utm_source=instagram&utm_medium=bio"

HUMOR_DATEI = MARKETING / "humor.json"
GROSSE_EVENTS_DATEI = MARKETING / "grosse_events.json"

WOCHENPLAN = {0: "krass", 1: "naehe", 2: "wuerdest", 3: "humor",
              4: "wochenende", 5: "saison", 6: "moment"}
JAHRESTAG_ERLAUBT = {1, 2, 3, 6}
FORMATE = ("krass", "naehe", "wuerdest", "humor", "wochenende", "saison", "moment", "clip",
           "monat", "anmeldung", "top", "anlass", "laengste", "jahr", "duell", "wochenvorschau", "spotlight", "region")
MONAT_MIN_LOGOS = 6           # darunter gilt der Wochenplan
MONAT_MAX_LOGOS = 20          # „die 10-20 größten Events im Monat" (Nutzer, 27.10.2026)
ANMELDUNG_MIN = 3
ANMELDUNG_MAX = 8

SPORTARTEN = ("Laufen", "Fahrrad", "Triathlon", "Schwimmen")
SPORT_PLURAL = {"Laufen": "Läufe", "Fahrrad": "Radrennen", "Triathlon": "Triathlons",
                "Schwimmen": "Schwimm-Events"}
SPORT_SINGULAR = {"Laufen": "Lauf", "Fahrrad": "Radrennen", "Triathlon": "Triathlon",
                  "Schwimmen": "Schwimm-Event"}
SPORT_EMOJI = {"Laufen": "🏃", "Fahrrad": "🚴", "Triathlon": "🏊‍♂️🚴‍♀️🏃", "Schwimmen": "🏊"}
LAND_KURZ = {"Deutschland": "DE", "Österreich": "AT", "Schweiz": "CH", "Italien (Südtirol)": "IT"}
LAND_IN = {"Deutschland": "in Deutschland", "Österreich": "in Österreich",
           "Schweiz": "in der Schweiz", "Italien (Südtirol)": "in Südtirol"}
LAND_FLAGGE = {"Deutschland": "🇩🇪", "Österreich": "🇦🇹", "Schweiz": "🇨🇭", "Italien (Südtirol)": "🇮🇹"}

# Großstädte für das Format "region" - Reihenfolge = Rotation je Woche.
STAEDTE = [
    ("München", 48.137, 11.575), ("Berlin", 52.520, 13.405), ("Wien", 48.208, 16.373),
    ("Hamburg", 53.551, 9.994), ("Zürich", 47.377, 8.541), ("Köln", 50.938, 6.960),
    ("Stuttgart", 48.776, 9.183), ("Frankfurt", 50.111, 8.682), ("Graz", 47.071, 15.439),
    ("Leipzig", 51.340, 12.375), ("Nürnberg", 49.454, 11.077), ("Bern", 46.948, 7.447),
    ("Düsseldorf", 51.227, 6.773), ("Dresden", 51.050, 13.738), ("Salzburg", 47.809, 13.055),
    ("Hannover", 52.376, 9.732), ("Innsbruck", 47.269, 11.404), ("Basel", 47.560, 7.589),
    ("Freiburg", 47.999, 7.842), ("Bremen", 53.079, 8.802), ("Linz", 48.306, 14.286),
    ("Dortmund", 51.514, 7.465), ("Münster", 51.961, 7.626), ("Regensburg", 49.013, 12.102),
]
REGION_RADIUS_KM = 50

HASHTAGS_BASIS = ["#ausdauersport", "#laufevent", "#wettkampf", "#trainingsziel"]
HASHTAGS_SPORT = {
    "Laufen": ["#laufen", "#marathon", "#halbmarathon", "#laufenmachtglücklich", "#runnersofinstagram"],
    "Fahrrad": ["#radfahren", "#rennrad", "#radmarathon", "#gravel", "#cyclinglife"],
    "Triathlon": ["#triathlon", "#triathlontraining", "#ironman", "#swimbikerun"],
    "Schwimmen": ["#schwimmen", "#freiwasserschwimmen", "#openwaterswimming", "#swimming"],
}
HASHTAGS_LAND = {"Deutschland": "#deutschland", "Österreich": "#österreich",
                 "Schweiz": "#schweiz", "Italien (Südtirol)": "#südtirol"}

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]


# ---------------------------------------------------------------- Daten

def lade_events(pfad: Path | None = None) -> list[dict]:
    with open(pfad or WURZEL / "events.json", encoding="utf-8") as f:
        return json.load(f)


def lade_momente(pfad: Path | None = None) -> list[dict]:
    with open(pfad or MOMENTE_DATEI, encoding="utf-8") as f:
        return json.load(f)["momente"]


def lade_grosse(pfad: Path | None = None) -> list[dict]:
    """Die großen Events (grosse_events.json) - ohne Datei eine leere Liste."""
    try:
        return json.loads((pfad or GROSSE_EVENTS_DATEI).read_text(encoding="utf-8")).get("events", [])
    except (OSError, ValueError):
        return []


def lade_humor(pfad: Path | None = None) -> list[dict]:
    p = pfad or HUMOR_DATEI
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("witze", [])


def lade_clips(pfad: Path | None = None) -> list[dict]:
    p = pfad or CLIPS_DATEI
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return [c for c in json.load(f).get("clips", []) if c.get("aktiv", True)]


def veranstaltungen(events: list[dict], von: dt.date, bis: dt.date) -> list[dict]:
    """Die Zeilen von events.json (eine je STRECKE) zu Veranstaltungen
    zusammengefasst - nur sichtbare (`pruefung_offen` blendet die Seite
    aus, dann zeigt sie auch Instagram nicht) mit Start in [von, bis]."""
    gruppen: dict[tuple, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("pruefung_offen"):
            continue
        try:
            start = dt.date.fromisoformat(e["datum_start"])
        except (KeyError, ValueError):
            continue
        if not (von <= start <= bis):
            continue
        gruppen[(e.get("name", ""), e.get("standort", ""), e["datum_start"])].append(e)
    ergebnis = []
    for (name, ort, datum), zeilen in gruppen.items():
        km = sorted({z["laenge_km"] for z in zeilen if isinstance(z.get("laenge_km"), (int, float))})
        dauern = [z["dauer_h"] for z in zeilen if isinstance(z.get("dauer_h"), (int, float))]
        ergebnis.append({
            "name": name, "ort": ort, "datum": datum, "land": zeilen[0].get("land", ""),
            "sport": zeilen[0].get("art1", ""), "art2": zeilen[0].get("art2", ""),
            "lat": zeilen[0].get("lat"), "lon": zeilen[0].get("lon"),
            "km": km, "strecken": len(zeilen),
            "dauer_h": max(dauern) if dauern else None,
            "url": next((z["veranstalter_url"] for z in zeilen if z.get("veranstalter_url")), None),
            "vorlaeufig": any(z.get("datum_vorlaeufig") for z in zeilen),
            "kinder": bool(NICHT_HIGHLIGHT_RE.search(name)),
        })
    ergebnis.sort(key=lambda v: (v["datum"], v["name"]))
    return ergebnis


def sport_anzahl(n: int, sport: str) -> str:
    return f"{n} {(SPORT_SINGULAR if n == 1 else SPORT_PLURAL).get(sport, sport)}"


# Kinder-, Jugend- und Schülerläufe sind nie ein Highlight (Datenregel 24
# nimmt reine Kinderwettbewerbe heraus, ein „Junior-Marathon" kann
# trotzdem durchrutschen).
NICHT_HIGHLIGHT_RE = re.compile(r"junior|kids?\b|kinder|schüler|jugend|bambini|\bu\d{1,2}\b", re.I)


def hoehepunkt_wert(v: dict) -> float:
    """Wie sehr sich eine Veranstaltung als Höhepunkt eignet: viele
    Strecken (ein Maß für Größe), lange Distanzen, Triathlon; vorläufige
    Termine nie zuerst."""
    w = min(v["strecken"], 8) * 1.0
    if v["km"]:
        lang = max(v["km"])
        w += 3 if lang >= 42 else 2 if lang >= 21 else 1 if lang >= 10 else 0
    if v["sport"] == "Triathlon":
        w += 1.5
    if re.search(r"marathon|ironman|challenge|rundfahrt|classic", v["name"], re.I):
        w += 2
    if v["vorlaeufig"]:
        w -= 10
    if NICHT_HIGHLIGHT_RE.search(v["name"]):
        w -= 20
    return w


def hoehepunkte(liste: list[dict], n: int, rng: random.Random) -> list[dict]:
    """n Höhepunkte, nicht alle aus einem Land/einer Sportart: erst nach
    Wert sortiert, dann reihum je Land gezogen; bei Gleichstand würfelt
    rng (mit dem Datum gesät), damit die Liste nicht jede Woche gleich
    beginnt."""
    gemischt = sorted((v for v in liste if not NICHT_HIGHLIGHT_RE.search(v["name"])),
                      key=lambda v: (-hoehepunkt_wert(v), rng.random()))
    je_land: dict[str, list[dict]] = defaultdict(list)
    for v in gemischt:
        je_land[v["land"]].append(v)
    reihenfolge = sorted(je_land, key=lambda l: -len(je_land[l]))
    auswahl: list[dict] = []
    namen = set()
    while len(auswahl) < n and any(je_land.values()):
        for land in reihenfolge:
            while je_land[land]:
                v = je_land[land].pop(0)
                if v["name"] in namen:
                    continue
                namen.add(v["name"])
                auswahl.append(v)
                break
            if len(auswahl) >= n:
                break
    auswahl.sort(key=lambda v: (v["datum"], v["name"]))
    return auswahl


def entfernung_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- Texte

def dauer_wort(stunden: float) -> str:
    """„6 Stunden", unter einer Stunde „40 Minuten" (wie die Seite)."""
    if 0 < stunden < 1:
        return f"{round(stunden * 60)} Minuten"
    return f"{fmt_km(stunden)} Stunden"


def fmt_km(km: float) -> str:
    if abs(km - 42.195) < 0.01:
        return "42,2"
    if abs(km - 21.0975) < 0.01:
        return "21,1"
    s = f"{km:.1f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def strecken_text(v: dict) -> str:
    if not v["km"]:
        return ""
    km = v["km"]
    if len(km) > 4:
        return f"{fmt_km(km[0])} – {fmt_km(km[-1])} km"
    return " · ".join(fmt_km(k) for k in km) + " km"


def fmt_datum(iso: str, mit_tag: bool = True) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{WOCHENTAGE[d.weekday()]} {d.day:02d}.{d.month:02d}." if mit_tag else f"{d.day:02d}.{d.month:02d}."


def fmt_datum_lang(d: dt.date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def event_folie(v: dict) -> dict:
    return {"datum": fmt_datum(v["datum"]), "name": v["name"],
            "ort": f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
            "strecken": strecken_text(v), "sport": v["sport"]}


def event_karte(v: dict, ueber: str | None = None) -> dict:
    """Eine Folie für EIN Rennen - groß, schnell (insta_video, typ „event").
    `url` reist mit, damit insta_veranstalter.py den Instagram-Namen des
    Veranstalters finden kann; das Video zeigt ihn nicht."""
    karte = {"typ": "event", "datum": fmt_datum(v["datum"]), "name": v["name"],
             "ort": f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
             "strecken": strecken_text(v) or (dauer_wort(v["dauer_h"]) if v.get("dauer_h") else ""),
             "sport": v["sport"], "kategorie": v.get("art2") or ""}
    if ueber:
        karte["ueber"] = ueber
    if v.get("url"):
        karte["url"] = v["url"]
    return karte


def sicher(liste: list[dict]) -> list[dict]:
    """Nur Rennen, deren Angaben wir zeigen wollen: kein vorläufiger Termin,
    kein Kinder-/Jugendlauf (Datenregel 19 und 24 - „Weniger anzeigen ist
    eine Datenqualitäts-Entscheidung")."""
    return [v for v in liste if not v["vorlaeufig"] and not v.get("kinder")]


VERB = {"Laufen": "LAUFEN", "Fahrrad": "FAHREN", "Schwimmen": "SCHWIMMEN", "Triathlon": "MACHEN"}
PARTNER = {"Laufen": "deinem Laufpartner", "Fahrrad": "deiner Radgruppe",
           "Schwimmen": "deinem Schwimmpartner", "Triathlon": "deiner Trainingsgruppe"}


def frage_folie(sport: str | None) -> dict:
    return {"typ": "satz", "ueber": "Und du?", "titel": f"WÜRDEST DU DAS {VERB.get(sport, 'MACHEN')}?",
            "zeilen": ["Ja oder nein - schreib's in die Kommentare"]}


def cta_folie(titel: str = "Dein nächstes Rennen?", *zeilen: str) -> dict:
    return {"typ": "cta", "titel": titel, "zeilen": list(zeilen) or [SEITE, "Link in der Bio"]}


def hashtags(sport: str | None, land: str | None = None, extra: list[str] | None = None,
             rng: random.Random | None = None, n: int = 10) -> list[str]:
    tags: list[str] = []
    if sport in HASHTAGS_SPORT:
        tags += HASHTAGS_SPORT[sport]
    else:
        for s in SPORTARTEN[:3]:
            tags += HASHTAGS_SPORT[s][:2]
    if land in HASHTAGS_LAND:
        tags.append(HASHTAGS_LAND[land])
    tags += extra or []
    tags += HASHTAGS_BASIS
    gesehen, ergebnis = set(), []
    for t in tags:
        if t.lower() not in gesehen:
            gesehen.add(t.lower())
            ergebnis.append(t)
    return ergebnis[:n]


def wahl(rng: random.Random, varianten: list[str]) -> str:
    return varianten[rng.randrange(len(varianten))]


CTA = [
    "Alle Termine, Strecken und Filter: Link in der Bio 👉 {seite}",
    "Mehr als {anzahl} Events mit Umkreissuche und Kalender-Export: Link in der Bio 👉 {seite}",
    "Dein nächstes Rennen findest du über den Link in der Bio 👉 {seite}",
    "Alle Events in DE, AT, CH & Südtirol – kostenlos, ohne Anmeldung: Link in der Bio 👉 {seite}",
]


def caption_bauen(teile: list[str], tags: list[str], rng: random.Random, anzahl: int) -> str:
    cta = wahl(rng, CTA).format(seite=SEITE, anzahl=f"{(anzahl // 500) * 500:,}".replace(",", "."))
    text = "\n\n".join(t for t in teile if t) + "\n\n" + cta + "\n\n" + " ".join(tags)
    # Instagram: höchstens 2.200 Zeichen und 30 Hashtags.
    return text[:2200]


# ---------------------------------------------------------------- Formate

def _beitrag(format_: str, datum: dt.date, folien: list[dict], caption: str,
             sport: str | None, **extra) -> dict:
    b = {"format": format_, "datum": datum.isoformat(), "folien": folien,
         "caption": caption, "sport": sport, "kampagne": f"{format_}-{datum.isoformat()}"}
    b.update(extra)
    return b


def format_wochenvorschau(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    montag = datum - dt.timedelta(days=datum.weekday())
    sonntag = montag + dt.timedelta(days=6)
    liste = veranstaltungen(events, max(datum, montag), sonntag)
    if len(liste) < 3:
        return None
    n_sport = Counter(v["sport"] for v in liste)
    top = hoehepunkte(liste, 5, rng)
    kw = montag.isocalendar()[1]
    folien = [
        {"typ": "titel", "ueber": f"KW {kw} · {fmt_datum(montag.isoformat(), False)} – {fmt_datum(sonntag.isoformat(), False)}",
         "titel": f"{len(liste)} Events\ndiese Woche",
         "zeilen": [f"{SPORT_EMOJI.get(s, '')} {sport_anzahl(n, s)}" for s, n in n_sport.most_common()]},
        {"typ": "liste", "titel": "Unsere Highlights", "events": [event_folie(v) for v in top]},
        {"typ": "cta", "titel": "Alle Termine", "zeilen": [SEITE, "Link in der Bio"]},
    ]
    haupt = n_sport.most_common(1)[0][0]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    caption = caption_bauen([
        wahl(rng, ["Neue Woche, neue Startnummern! 🔥", "Die Woche der Wettkämpfe beginnt. 💪",
                   "Wo startest du diese Woche? 👇"]),
        f"{len(liste)} Ausdauer-Events zwischen {fmt_datum(montag.isoformat(), False)} und "
        f"{fmt_datum(sonntag.isoformat(), False)} – unsere Highlights:\n{zeilen}",
        "Markiere deine Trainingsgruppe! 👥",
    ], hashtags(haupt, rng=rng), rng, len(events))
    return _beitrag("wochenvorschau", datum, folien, caption, haupt)


def format_wochenende(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """„Was machst du am Wochenende?" - die Zahl der Rennen am Samstag und
    Sonntag, dann drei Tipps einzeln, dann die Frage in die Kommentare."""
    samstag = datum + dt.timedelta(days=(5 - datum.weekday()) % 7)
    sonntag = samstag + dt.timedelta(days=1)
    liste = veranstaltungen(events, samstag, sonntag)
    if len(liste) < 3:
        return None
    n_land = Counter(v["land"] for v in liste)
    top = hoehepunkte(sicher(liste) or liste, 3, rng)
    laender = " · ".join("Südtirol" if l == "Italien (Südtirol)" else LAND_KURZ.get(l, l) for l, _ in n_land.most_common())
    folien = [
        {"typ": "hook", "ueber": "Was machst du am Wochenende?", "zahl": str(len(liste)),
         "titel": "RENNEN AM SAMSTAG UND SONNTAG", "zeilen": [laender]},
        *[event_karte(v) for v in top],
        {"typ": "satz", "ueber": "Und du?", "titel": "WO STARTEST DU?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie("Noch spontan starten?"),
    ]
    haupt = Counter(v["sport"] for v in liste).most_common(1)[0][0]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    caption = caption_bauen([
        wahl(rng, [f"{len(liste)} Rennen am Wochenende - und du sitzt auf dem Sofa? 🛋️➡️🏁",
                   "Was machst du am Wochenende? 👀", f"Noch nichts vor? {len(liste)} Rennen warten. 🔥"]),
        f"Unsere Tipps für Samstag und Sonntag:\n{zeilen}",
        "Wo startest du? Schreib's in die Kommentare! 💬",
    ], hashtags(haupt, rng=rng, extra=["#wochenende"]), rng, len(events))
    return _beitrag("wochenende", datum, folien, caption, haupt)


def format_spotlight(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """Eine Sportart in einem Land, die nächsten 30 Tage. Rotation über
    alle Paare mit mindestens drei Veranstaltungen (nach Kalenderwoche)."""
    bis = datum + dt.timedelta(days=30)
    liste = veranstaltungen(events, datum, bis)
    paare = [(s, l) for s in SPORTARTEN for l in LAND_KURZ
             if sum(1 for v in liste if v["sport"] == s and v["land"] == l) >= 3]
    if not paare:
        return None
    sport, land = paare[datum.isocalendar()[1] % len(paare)]
    treffer = [v for v in liste if v["sport"] == sport and v["land"] == land]
    top = hoehepunkte(treffer, 5, rng)
    folien = [
        {"typ": "titel", "ueber": "Die nächsten 30 Tage",
         "titel": f"{len(treffer)} {SPORT_PLURAL.get(sport, sport)}\n{LAND_IN.get(land, land)}",
         "zeilen": [f"{SPORT_EMOJI.get(sport, '')} {fmt_datum(datum.isoformat(), False)} – {fmt_datum(bis.isoformat(), False)}"]},
        {"typ": "liste", "titel": "Nicht verpassen", "events": [event_folie(v) for v in top]},
        {"typ": "cta", "titel": f"Alle {SPORT_PLURAL.get(sport, sport)}", "zeilen": [SEITE, "Link in der Bio"]},
    ]
    zeilen = "\n".join(f"{fmt_datum(v['datum'])} {v['name']} ({v['ort']}) {strecken_text(v)}".rstrip() for v in top)
    caption = caption_bauen([
        f"{SPORT_EMOJI.get(sport, '')} {len(treffer)} {SPORT_PLURAL.get(sport, sport)} {LAND_IN.get(land, land)} in den nächsten 30 Tagen!",
        f"Unsere Auswahl:\n{zeilen}",
        "Speicher dir den Beitrag für deine Saisonplanung. 📌",
    ], hashtags(sport, land, rng=rng), rng, len(events))
    return _beitrag("spotlight", datum, folien, caption, sport)


def format_region(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    bis = datum + dt.timedelta(days=28)
    liste = veranstaltungen(events, datum, bis)
    woche = datum.isocalendar()[1] + 52 * datum.isocalendar()[0]
    for versuch in range(len(STAEDTE)):
        stadt, lat, lon = STAEDTE[(woche + versuch) % len(STAEDTE)]
        treffer = [v for v in liste if v["lat"] is not None and v["lon"] is not None
                   and entfernung_km(lat, lon, v["lat"], v["lon"]) <= REGION_RADIUS_KM]
        if len(treffer) >= 3:
            break
    else:
        return None
    n_sport = Counter(v["sport"] for v in treffer)
    top = hoehepunkte(treffer, 5, rng)
    folien = [
        {"typ": "titel", "ueber": f"Rund um {stadt} · {REGION_RADIUS_KM} km",
         "titel": f"{len(treffer)} Events\nin den nächsten 4 Wochen",
         "zeilen": [f"{SPORT_EMOJI.get(s, '')} {sport_anzahl(n, s)}" for s, n in n_sport.most_common()]},
        {"typ": "liste", "titel": f"Rund um {stadt}", "events": [event_folie(v) for v in top]},
        {"typ": "cta", "titel": "Deine Umgebung?", "zeilen": ["Umkreissuche auf", SEITE, "Link in der Bio"]},
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    land = treffer[0]["land"]
    tag_stadt = "#" + re.sub(r"[^a-zäöüß]", "", stadt.lower())
    caption = caption_bauen([
        f"📍 {stadt} und Umgebung: {len(treffer)} Ausdauer-Events in den nächsten vier Wochen.",
        f"Unsere Auswahl:\n{zeilen}",
        f"Nicht aus {stadt}? Auf {SEITE} findest du mit der Umkreissuche die Rennen in deiner Nähe.",
    ], hashtags(n_sport.most_common(1)[0][0], land, extra=[tag_stadt], rng=rng), rng, len(events))
    return _beitrag("region", datum, folien, caption, n_sport.most_common(1)[0][0], stadt=stadt)


# ------------------------------------------------- Formate seit 16.10.2026

# Superlative für „krass": Sportart (None = alle), Maß, Mindestwert,
# Überschrift, Einheit, Zusatz. Rotation nach Kalenderwoche; hat eine
# Kategorie keinen Treffer, die nächste.
KRASS_KATEGORIEN = (
    ("Laufen", "km", 50, "Das längste Laufrennen der nächsten zwei Monate", "KM", "ZU FUSS."),
    ("Fahrrad", "km", 150, "Das längste Radrennen der nächsten zwei Monate", "KM", "AUF DEM RAD."),
    (None, "h", 12, "Das längste Zeitrennen der nächsten zwei Monate", "STUNDEN", "OHNE ZIELLINIE."),
    ("Triathlon", "km", 100, "Der längste Triathlon der nächsten zwei Monate", "KM", "SCHWIMMEN, RAD, LAUFEN."),
    ("Schwimmen", "km", 5, "Das längste Schwimmrennen der nächsten zwei Monate", "KM", "IM WASSER."),
)


def _krass_wert(v: dict, art: str) -> float:
    if art == "h":
        return float(v.get("dauer_h") or 0)
    return float(max(v["km"]) if v["km"] else 0)


def zahl_text(zahl: str) -> str:
    """„161 KM" → „161 km", „24 STUNDEN" → „24 Stunden" (für die Caption)."""
    return zahl.replace(" KM", " km").replace(" STUNDEN", " Stunden").replace("NOCH ", "noch ").replace(" TAGE", " Tage")


def format_krass(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """Das Krasseste der nächsten zwei Monate - eine Zahl, die man kaum
    glaubt, in der ersten Sekunde."""
    liste = sicher(veranstaltungen(events, datum, datum + dt.timedelta(days=60)))
    woche = datum.isocalendar()[1]
    for versuch in range(len(KRASS_KATEGORIEN)):
        sport, art, minimum, ueber, einheit, zusatz = KRASS_KATEGORIEN[(woche + versuch) % len(KRASS_KATEGORIEN)]
        treffer = [v for v in liste if (sport is None or v["sport"] == sport) and _krass_wert(v, art) >= minimum]
        if treffer:
            break
    else:
        return None
    v = max(treffer, key=lambda x: (_krass_wert(x, art), hoehepunkt_wert(x), x["name"]))
    zahl = f"{fmt_km(_krass_wert(v, art))} {einheit}"
    folien = [
        {"typ": "hook", "ueber": ueber, "zahl": zahl, "titel": zusatz, "zeilen": []},
        event_karte(v),
        frage_folie(v["sport"]),
        cta_folie(),
    ]
    caption = caption_bauen([
        f"🤯 {zahl_text(zahl)}. {ueber}:",
        f"📅 {fmt_datum(v['datum'])} · {v['name']} ({v['ort']}, {LAND_KURZ.get(v['land'], v['land'])})"
        + (f"\nStrecken: {strecken_text(v)}" if strecken_text(v) else ""),
        "Würdest du dich trauen? Ja oder nein 👇\nMarkiere jemanden, der das schafft! 💪",
    ], hashtags(v["sport"], v["land"], extra=["#ultra", "#extrem"], rng=rng), rng, len(events))
    return _beitrag("krass", datum, folien, caption, v["sport"])


def format_naehe(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """Rennen rund um eine Großstadt - zum Weiterschicken an die
    Trainingsgruppe (Teilen zählt bei Instagram am meisten)."""
    liste = veranstaltungen(events, datum, datum + dt.timedelta(days=28))
    woche = datum.isocalendar()[1] + 52 * datum.isocalendar()[0]
    for versuch in range(len(STAEDTE)):
        stadt, lat, lon = STAEDTE[(woche + versuch) % len(STAEDTE)]
        treffer = [v for v in liste if v["lat"] is not None and v["lon"] is not None
                   and entfernung_km(lat, lon, v["lat"], v["lon"]) <= REGION_RADIUS_KM]
        if len(treffer) >= 4:
            break
    else:
        return None
    n_sport = Counter(v["sport"] for v in treffer)
    haupt = n_sport.most_common(1)[0][0]
    top = hoehepunkte(sicher(treffer) or treffer, 4, rng)
    folien = [
        {"typ": "hook", "ueber": f"Rund um {stadt}", "zahl": str(len(treffer)),
         "titel": "RENNEN IN DEN NÄCHSTEN 4 WOCHEN", "zeilen": []},
        *[event_karte(v) for v in top],
        {"typ": "satz", "ueber": "Nicht allein starten",
         "titel": f"SCHICK DAS {PARTNER.get(haupt, 'deiner Trainingsgruppe').upper()}", "zeilen": []},
        cta_folie(f"Nicht aus {stadt}?", "Umkreissuche auf", SEITE),
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    tag_stadt = "#" + re.sub(r"[^a-zäöüß]", "", stadt.lower())
    caption = caption_bauen([
        f"📍 {stadt}: {len(treffer)} Rennen in den nächsten vier Wochen!",
        f"Unsere Tipps:\n{zeilen}",
        f"Schick das jemandem aus {stadt} 📲 - allein trainieren ist halb so schön.",
    ], hashtags(haupt, top[0]["land"], extra=[tag_stadt], rng=rng), rng, len(events))
    return _beitrag("naehe", datum, folien, caption, haupt, stadt=stadt)


def _besonderheit(v: dict) -> tuple[int, str, str, str] | None:
    """(Rang, Art, große Zahl, Satz) - was ein Rennen ungewöhnlich macht.
    Nur aus den Daten, nichts dazuerfunden."""
    name = v["name"].lower()
    km = max(v["km"]) if v["km"] else 0
    verb = VERB.get(v["sport"], "MACHEN")
    if v.get("art2") == "Backyard Ultra":
        return 9, "backyard", "6,7 KM", "Jede Stunde. Bis nur noch einer läuft."
    if (v.get("dauer_h") or 0) >= 24:
        return 8, "zeit", f"{fmt_km(v['dauer_h'])} STUNDEN", f"{verb.capitalize()}. Ohne Ziellinie."
    if re.search(r"treppen|stairrun|towerrun|tower run|stäffele", name):
        return 7, "treppe", "TREPPEN", "Statt Kilometer."
    if v["sport"] == "Laufen" and km >= 100:
        return 6, "ultra", f"{fmt_km(km)} KM", "Zu Fuß. In einem Rennen."
    if v.get("art2") == "Hindernis":
        return 5, "hindernis", f"{fmt_km(km)} KM" if km else "HINDERNISSE", "Schlamm, Wände, Wasser."
    if v["sport"] == "Schwimmen" and km >= 3:
        return 5, "schwimmen", f"{fmt_km(km)} KM", ("Im offenen Wasser." if v.get("art2") == "Freiwasser"
                                                   else "Schwimmen. Am Stück.")
    if v["sport"] == "Triathlon" and km >= 200:
        return 5, "langdistanz", f"{fmt_km(km)} KM", "Schwimmen, Rad, Laufen. An einem Tag."
    if v["sport"] == "Fahrrad" and km >= 200:
        return 4, "rad", f"{fmt_km(km)} KM", "Auf dem Rad. In einem Rennen."
    if re.search(r"\bnacht|night|mitternacht|midnight", name):
        return 3, "nacht", "NACHTS", "Stirnlampe an und los."
    return None


def format_wuerdest(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """„Würdest du das laufen?" - ein ungewöhnliches Rennen der nächsten
    drei Monate. Bringt Kommentare (ja/nein), die Instagram belohnt."""
    liste = sicher(veranstaltungen(events, datum, datum + dt.timedelta(days=90)))
    kandidaten = [(b, v) for v in liste for b in [_besonderheit(v)] if b]
    if not kandidaten:
        return None
    arten = sorted({b[1] for b, _ in kandidaten},
                   key=lambda a: (-max(b[0] for b, _ in kandidaten if b[1] == a), a))
    art = arten[datum.isocalendar()[1] % len(arten)]
    (_, _, zahl, satz), v = max(((b, v) for b, v in kandidaten if b[1] == art),
                                key=lambda bv: (hoehepunkt_wert(bv[1]), bv[1]["name"]))
    verb = VERB.get(v["sport"], "MACHEN").lower()
    folien = [
        {"typ": "hook", "ueber": f"Würdest du das {verb}?", "zahl": zahl, "titel": satz.upper(), "zeilen": []},
        event_karte(v),
        {"typ": "satz", "ueber": "Ehrlich jetzt", "titel": "JA ODER NEIN?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie(),
    ]
    caption = caption_bauen([
        f"Würdest du das {verb}? 🤔 {zahl_text(zahl)} - {satz}",
        f"📅 {fmt_datum(v['datum'])} · {v['name']} ({v['ort']}, {LAND_KURZ.get(v['land'], v['land'])})"
        + (f"\nStrecken: {strecken_text(v)}" if strecken_text(v) else ""),
        "JA oder NEIN? Schreib's in die Kommentare 👇",
    ], hashtags(v["sport"], v["land"], rng=rng), rng, len(events))
    return _beitrag("wuerdest", datum, folien, caption, v["sport"])


def _mit_doppelpunkt(t: str) -> str:
    return t if t.endswith(("?", "!", "“", '"', ":")) else t + ":"


def format_humor(datum: dt.date, events: list[dict], rng: random.Random,
                 witze: list[dict] | None = None) -> dict | None:
    """Läuferhumor: Erwartung gegen Wirklichkeit, zwei Folien, dann die
    Bitte, jemanden zu markieren - das am häufigsten geteilte Format."""
    witze = witze if witze is not None else lade_humor()
    if not witze:
        return None
    w = witze[(datum.toordinal() // 7) % len(witze)]
    folien = [
        {"typ": "satz", "ueber": w["oben"], "titel": w["text_oben"].upper(), "zeilen": []},
        {"typ": "satz", "ueber": w["unten"], "titel": w["text_unten"].upper(), "zeilen": [], "pointe": True},
        {"typ": "satz", "ueber": "Kennst du?", "titel": "MARKIER JEMANDEN, DER DAS KENNT", "zeilen": []},
        cta_folie("Und dein nächstes Rennen?"),
    ]
    caption = caption_bauen([
        f"{_mit_doppelpunkt(w['oben'])} {w['text_oben']}\n{_mit_doppelpunkt(w['unten'])} {w['text_unten']} 😅",
        "Markiere jemanden, der das kennt! 👇",
    ], hashtags(w.get("sport"), rng=rng, extra=["#läuferhumor", "#sporthumor"]), rng, len(events))
    return _beitrag("humor", datum, folien, caption, w.get("sport"), witz_id=w["id"])


# Kategorien für „saison": Name (Mehrzahl), Sportart, Prüfung je Veranstaltung.
SAISON_KATEGORIEN = (
    ("Marathons", "Laufen", lambda v: any(42.0 <= k <= 42.3 for k in v["km"])),
    ("Triathlons", "Triathlon", lambda v: True),
    ("Trailläufe", "Laufen", lambda v: v.get("art2") == "Trail" and any(k >= 20 for k in v["km"])),
    ("Radmarathons", "Fahrrad", lambda v: any(k >= 100 for k in v["km"])),
    ("Halbmarathons", "Laufen", lambda v: any(21.0 <= k <= 21.2 for k in v["km"])),
    ("Ultraläufe", "Laufen", lambda v: any(k > 42.3 for k in v["km"])),
)


def format_saison(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """„Speicher dir das": eine Sorte Rennen in einem Monat drei bis fünf
    Monate voraus - für die Saisonplanung. Gespeicherte Beiträge zählen
    bei Instagram viel."""
    woche = datum.isocalendar()[1]
    treffer, name, sport, jahr, monat = [], "", None, datum.year, datum.month
    for voraus in (4, 3, 5):
        monat = (datum.month + voraus - 1) % 12 + 1
        jahr = datum.year + (datum.month + voraus - 1) // 12
        anfang = dt.date(jahr, monat, 1)
        ende = dt.date(jahr + (monat == 12), monat % 12 + 1, 1) - dt.timedelta(days=1)
        liste = sicher(veranstaltungen(events, anfang, ende))
        for versuch in range(len(SAISON_KATEGORIEN)):
            name, sport, pruefe = SAISON_KATEGORIEN[(woche + versuch) % len(SAISON_KATEGORIEN)]
            treffer = [v for v in liste if v["sport"] == sport and pruefe(v)]
            if len(treffer) >= 4:
                break
        if len(treffer) >= 4:
            break
    else:
        return None
    top = hoehepunkte(treffer, 6, rng)
    monat_text = f"{MONATE[monat - 1]} {jahr}"
    folien = [
        {"typ": "hook", "ueber": "Speicher dir das", "zahl": str(len(treffer)),
         "titel": f"{name.upper()} IM {MONATE[monat - 1].upper()}", "zeilen": [f"Saison {jahr}"]},
        *[dict(event_karte(v), schnell=True) for v in top],
        {"typ": "satz", "ueber": "Saisonplanung", "titel": "WELCHER WIRD DEIN HÖHEPUNKT?",
         "zeilen": ["Speichern nicht vergessen"]},
        cta_folie("Alle Termine + Kalender"),
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    caption = caption_bauen([
        f"📌 Speicher dir das: {len(treffer)} {name} im {monat_text}.",
        f"Unsere Auswahl:\n{zeilen}",
        "Welcher wird dein Saisonhöhepunkt? 👇 Mit Kalender-Export für jedes Rennen auf der Seite.",
    ], hashtags(sport, rng=rng, extra=["#saisonplanung", f"#saison{jahr}"]), rng, len(events))
    return _beitrag("saison", datum, folien, caption, sport, monat=monat_text)


# ------------------------------------------------- Große Events mit Logo

MONAT_KURZ = ["Jan", "Feb", "März", "Apr", "Mai", "Juni", "Juli", "Aug", "Sep", "Okt", "Nov", "Dez"]


def letzter_freitag(datum: dt.date) -> bool:
    return datum.weekday() == 4 and (datum + dt.timedelta(days=7)).month != datum.month


def naechster_monat(datum: dt.date) -> tuple[int, int]:
    return (datum.year + (datum.month == 12), datum.month % 12 + 1)


def monats_grenzen(jahr: int, monat: int) -> tuple[dt.date, dt.date]:
    anfang = dt.date(jahr, monat, 1)
    return anfang, dt.date(jahr + (monat == 12), monat % 12 + 1, 1) - dt.timedelta(days=1)


def gross_fuer(v: dict, grosse: list[dict]) -> dict | None:
    """Das große Event, zu dem eine Veranstaltung gehört: ein Suchwort aus
    `suche` steckt im Namen, Land und Sportart stimmen, und kein Wort aus
    `nicht` (L'Hivernale Sierre-Zinal ist ein anderer Lauf)."""
    name = v["name"].lower()
    for g in grosse:
        if g.get("land") and g["land"] != v["land"] or g.get("sport") and g["sport"] != v["sport"]:
            continue
        if any(s and s.lower() in name for s in g.get("nicht") or []):
            continue
        if any(s and s.lower() in name for s in g.get("suche") or []):
            return g
    return None


def logo_karte(g: dict, datum: str | None, ueber: str | None = None, blitz: bool = False,
               v: dict | None = None) -> dict:
    """Eine Folie „logo" (insta_video): `logo_id` zeigt in den Logo-Cache
    (insta_logos.slug), `url` reist für die @-Erwähnung mit."""
    import insta_logos
    ort = (v or {}).get("ort") or g.get("ort") or ""
    land = (v or {}).get("land") or g.get("land") or ""
    karte = {"typ": "logo", "logo_id": insta_logos.slug(g["name"]), "name": g["name"],
             "ort": f"{ort} {LAND_KURZ.get(land, '')}".strip(), "sport": g.get("sport")}
    if datum:
        karte["datum"] = datum
    if ueber:
        karte["ueber"] = ueber
    if blitz:
        karte["blitz"] = True
    url = g.get("webseite") or (v or {}).get("url")
    if url:
        karte["url"] = url
    return karte


def datum_kurz(d: dt.date, jahr: bool = False) -> str:
    return f"{d.day}. {MONAT_KURZ[d.month - 1]}" + (f" {d.year}" if jahr else "")


def format_monat(datum: dt.date, events: list[dict], rng: random.Random,
                 grosse: list[dict] | None = None) -> dict | None:
    """„375 EVENTS IM NOVEMBER 2026" - am letzten Freitag für den nächsten
    Monat: die Zahl aller Events, dann die Logos der großen Events im Takt
    (ein Schlag je Logo, harter Schnitt), am Ende „Check it out". Farbe und
    Schwarzweiß wechseln von Monat zu Monat."""
    grosse = grosse if grosse is not None else lade_grosse()
    jahr, monat = naechster_monat(datum) if datum.day > 7 else (datum.year, datum.month)
    anfang, ende = monats_grenzen(jahr, monat)
    alle = veranstaltungen(events, anfang, ende)
    treffer: dict[str, tuple[dict, dict]] = {}
    for v in sicher(alle):
        g = gross_fuer(v, grosse)
        if g and g["name"] not in treffer:
            treffer[g["name"]] = (g, v)
    if len(treffer) < MONAT_MIN_LOGOS:
        return None
    auswahl = sorted(treffer.values(), key=lambda gv: -(gv[0].get("starter") or 0))[:MONAT_MAX_LOGOS]
    auswahl.sort(key=lambda gv: (gv[1]["datum"], gv[0]["name"]))
    monat_name = MONATE[monat - 1]
    sportarten = [s for s in SPORTARTEN if any(v["sport"] == s for v in alle)]
    folien = [
        {"typ": "hook", "ueber": "Dein Rennkalender", "zahl": str(len(alle)),
         "titel": f"EVENTS IM {monat_name.upper()} {jahr}",
         "zeilen": [" · ".join({"Fahrrad": "Rad"}.get(s, s) for s in sportarten)]},
        *[logo_karte(g, datum_kurz(dt.date.fromisoformat(v["datum"])), blitz=True, v=v) for g, v in auswahl],
        cta_folie("Check it out!", f"Alle {len(alle)} Events im {monat_name}", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(g.get('sport'), '•')} {fmt_datum(v['datum'])} {g['name']} ({v['ort']})"
                       for g, v in auswahl)
    haupt = Counter(g.get("sport") for g, _ in auswahl).most_common(1)[0][0]
    caption = caption_bauen([
        f"🗓️ {len(alle)} Events im {monat_name} {jahr} – das sind die großen:",
        zeilen,
        "Wo stehst du am Start? 👇 Check it out – alle Termine mit Umkreissuche und Kalender-Export.",
    ], hashtags(haupt, rng=rng, extra=[f"#{monat_name.lower()}{jahr}", "#rennkalender"]), rng, len(events))
    return _beitrag("monat", datum, folien, caption, haupt, monat=f"{monat_name} {jahr}",
                    stil="sw" if monat % 2 else "farbe")


# Kategorien für „top": Schlüssel, Name (Mehrzahl), Sportart, Prüfung über
# die Zeilen einer großen Veranstaltung (km = alle Distanzen, art2, Name).
TOP_KATEGORIEN = (
    ("marathon", "Marathon-Events", "Laufen", lambda km, art2, n: any(42.0 <= k <= 42.3 for k in km)),
    ("trail", "Trail-Events", "Laufen", lambda km, art2, n: "Trail" in art2),
    ("radmarathon", "Radmarathons", "Fahrrad",
     lambda km, art2, n: (max(km, default=0) >= 100 or "radmarathon" in n) and "Mountainbike" not in art2),
    # nur Veranstaltungen ohne Marathon - sonst stand der Hamburg Marathon
    # unter den Halbmarathons, weil er auch einen anbietet
    ("halbmarathon", "Halbmarathon-Events", "Laufen",
     lambda km, art2, n: any(21.0 <= k <= 21.2 for k in km) and not any(42.0 <= k <= 42.3 for k in km)),
    ("ultra", "Ultra-Events", "Laufen", lambda km, art2, n: any(k > 42.3 for k in km) and "Marsch" not in art2),
    ("triathlon", "Triathlons", "Triathlon", lambda km, art2, n: True),
    ("gravel", "Gravel-Events", "Fahrrad", lambda km, art2, n: "Gravel" in art2 or "gravel" in n),
)
TOP_ANZAHLEN = (5, 3, 7, 10)    # „es muss nicht immer Top 5 sein … Top 10, Top 3" (Nutzer, 27.10.2026)
TOP_DESIGNS = ("karte", "einzeln", "raster", "zeitleiste")
TOP_DAUER = {3: 2.6, 5: 2.3, 7: 1.8, 10: 1.4}    # Sekunden je Event, mehr Events = schneller


def top_kandidaten(datum: dt.date, events: list[dict], grosse: list[dict], kategorie: tuple,
                   bis: dt.date | None = None) -> list[dict]:
    """Die großen Events einer Kategorie bis `bis` (Vorgabe: 12 Monate),
    größte zuerst: je großes Event die früheste Ausgabe, Distanzen und
    Kategorien aller seiner Zeilen zusammen."""
    _, _, sport, pruefe = kategorie
    je_name: dict[str, dict] = {}
    for v in sicher(veranstaltungen(events, datum, bis or datum + dt.timedelta(days=365))):
        if v["sport"] != sport:
            continue
        g = gross_fuer(v, grosse)
        if not g:
            continue
        e = je_name.setdefault(g["name"], {"g": g, "v": v, "km": set(), "art2": set()})
        if v["datum"] < e["v"]["datum"]:
            e["v"] = v
        e["km"].update(v["km"])
        if v.get("art2"):
            e["art2"].add(v["art2"])
    treffer = [e for e in je_name.values() if pruefe(sorted(e["km"]), e["art2"], e["g"]["name"].lower())]
    return sorted(treffer, key=lambda e: (-(e["g"].get("starter") or 0), e["g"]["name"]))


def top_eintraege(auswahl: list[dict]) -> list[dict]:
    """Die Einträge der Folien „top" (nach Datum): Logo, Name, Datum,
    Ort, Teilnehmende, Koordinaten, Seite."""
    import insta_logos
    aus = []
    for e in sorted(auswahl, key=lambda e: (e["v"]["datum"], e["g"]["name"])):
        v, g = e["v"], e["g"]
        tag = dt.date.fromisoformat(v["datum"])
        aus.append({"logo_id": insta_logos.slug(g["name"]), "name": g["name"],
                    "datum": datum_kurz(tag, jahr=True), "monat_iso": v["datum"][:7], "tag": tag.day,
                    "ort": f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
                    "starter": g.get("starter"), "lat": v.get("lat"), "lon": v.get("lon"),
                    "url": g.get("webseite") or v.get("url")})
    return aus


# ------------------------------------------------- Anlässe (große Rennen)

ANLAESSE_DATEI = MARKETING / "anlaesse.json"
# Wie die Kategorie im Satz heißt (Mehrzahl, ohne „-Events").
KATEGORIE_WORT = {"marathon": "Marathons", "halbmarathon": "Halbmarathons", "ultra": "Ultraläufe",
                  "trail": "Trailläufe", "radmarathon": "Radmarathons", "triathlon": "Triathlons",
                  "gravel": "Gravel-Rennen"}


def lade_anlaesse(pfad: Path | None = None) -> list[dict]:
    try:
        return json.loads((pfad or ANLAESSE_DATEI).read_text(encoding="utf-8")).get("anlaesse", [])
    except (OSError, ValueError):
        return []


def anlass_am(datum: dt.date, anlaesse: list[dict] | None = None) -> dict | None:
    anlaesse = anlaesse if anlaesse is not None else lade_anlaesse()
    return next((a for a in anlaesse if a.get("datum") == datum.isoformat()), None)


def format_anlass(datum: dt.date, events: list[dict], rng: random.Random, anlass: dict,
                  grosse: list[dict] | None = None) -> dict | None:
    """Am Tag eines großen internationalen Rennens (anlaesse.json): „Heute
    startet die Tour de France" – und dann die Radmarathons, die bei uns
    in diesem Jahr noch anstehen (vom Nutzer am 27.10.2026: „zu Ehren des
    Tour de France Starts … die noch anstehenden Radmarathons in diesem
    Jahr", „London Marathon … alle Marathons in unserer Region"). Das
    große Rennen steht nur als TEXT da – keine Bilder, keine Logos davon.
    Bleiben bis Silvester zu wenige, gelten die nächsten 12 Monate."""
    grosse = grosse if grosse is not None else lade_grosse()
    kat = next((k for k in TOP_KATEGORIEN if k[0] == anlass.get("kategorie")), None)
    if not kat:
        return None
    # Hat die Kategorie zu wenige große Events (Gravel), gilt die erste
    # Kategorie derselben Sportart (Radmarathons).
    kandidaten = [kat] + [k for k in TOP_KATEGORIEN if k[2] == kat[2] and k != kat][:1]
    jahresende = dt.date(datum.year, 12, 31)
    fenster = [(jahresende, f"bis Silvester {datum.year}"), (datum + dt.timedelta(days=365), "in den nächsten 12 Monaten")]
    for k in kandidaten:
        schluessel, name, sport, pruefe = k
        for bis, wann in fenster:
            liste = top_kandidaten(datum, events, grosse, k, bis)
            alle = [v for v in sicher(veranstaltungen(events, datum, bis))
                    if v["sport"] == sport and pruefe(v["km"], {v.get("art2") or ""}, v["name"].lower())]
            if len(liste) >= 3:
                break
        if len(liste) >= 3:
            break
    else:
        return None
    runde = datum.toordinal()
    anzahl = min(len(liste), (5, 7, 10)[runde % 3])
    design = TOP_DESIGNS[(runde // 7) % len(TOP_DESIGNS)]
    # Abwechslung: mal die größten, mal die nächsten (die als Erstes anstehen)
    naechste = runde % 2 == 1
    if naechste:
        auswahl = sorted(liste, key=lambda e: e["v"]["datum"])[:anzahl]
    else:
        auswahl = liste[:anzahl]
    eintraege = top_eintraege(auswahl)
    wort = KATEGORIE_WORT.get(schluessel, name)
    titel = f"Die nächsten {anzahl} großen {name}" if naechste else f"Die {anzahl} größten {name}"
    basis = {"typ": "top", "variante": design, "sport": sport, "titel": titel, "eintraege": eintraege,
             "start": datum.isoformat()[:7], "dauer": TOP_DAUER.get(anzahl, 2.0)}
    folien = [
        {"typ": "hook", "ueber": anlass["anlass_text"], "zahl": str(len(alle)),
         "titel": f"{wort.upper()} BEI UNS {wann.upper()}",
         "zeilen": ["Deutschland · Österreich · Schweiz · Südtirol"]},
        {"typ": "satz", "ueber": anlass["name"], "titel": "UND WO STARTEST DU?",
         "zeilen": [f"Die nächsten großen {wort} bei uns" if naechste else f"Die größten {wort} bei uns"]},
        *[dict(basis, aktiv=i) for i in range(anzahl)],
        dict(basis, aktiv=None, schluss="Wo bist du dabei?"),
        cta_folie("Check it out!", f"Alle {len(alle)} {wort} mit Termin", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(f"• {e['datum']}: {e['name']}, {e['ort']}" for e in eintraege)
    caption = caption_bauen([
        f"🏁 {anlass['anlass_text']}! Und bei uns? {len(alle)} {wort} {wann} in Deutschland, "
        "Österreich, der Schweiz und Südtirol. " + ("Die nächsten großen:" if naechste else "Die größten davon:"),
        zeilen,
        "Wo startest du? 👇",
    ], hashtags(sport, rng=rng, extra=[anlass.get("hashtag") or "", f"#{schluessel}"]), rng, len(events))
    return _beitrag("anlass", datum, folien, caption, sport, anlass=anlass.get("id"), kategorie=schluessel,
                    design=design, anzahl=anzahl)


# ---------------------------------------------- Die längsten (Balken)

LAENGSTE_VARIANTEN = ("gemischt", "Laufen", "Fahrrad")
# Am 27.10.2026 an der Quelle geprüft: auf der Seite richtig, aber KEIN Rennen
# bzw. Länge unbelegt – in der Grafik („die längsten Rennen") nicht zeigen.
# Echte Datenfehler stehen als Override in manual_overrides.json.
LAENGSTE_AUSNAHMEN = {
    "Chainreaction - Bikeconvoy for Ukraine",      # Hilfskonvoi nach Przemyśl, kein Wettkampf
    "Three Peaks Bike Race",                       # Route frei, Seite nennt keine Länge
    "Hackenpedder Bikepacking", "Hackenpedder Route",      # laut Veranstalter kein Rennen
    "Bayrisch-Böhmisches Biere und Bäder Brevet",  # Randonnée ohne Wertung
}


def laengste_kandidaten(datum: dt.date, events: list[dict], sport: str, n: int) -> list[dict]:
    """Die n längsten Veranstaltungen einer Sportart in den nächsten 12
    Monaten (je Veranstaltung die längste Strecke DIESER Sportart).
    Gerechnet über die Zeilen, nicht über `veranstaltungen()`: die fasst
    Lauf- und Radzeilen einer Veranstaltung zusammen, und der Lausitzer
    Seenland100 stand mit der Länge seines Radmarathons als 201-km-Lauf
    da. Märsche, Zeitrennen ohne Kilometer und Kinderläufe zählen nicht;
    dieselbe Strecke unter zwei Namen am selben Tag und Ort nur einmal."""
    bis = datum + dt.timedelta(days=365)
    je_name: dict[tuple, dict] = {}
    for e in events:
        if e.get("pruefung_offen") or e.get("art1") != sport or e.get("art2") == "Marsch":
            continue
        if e.get("datum_vorlaeufig") or NICHT_HIGHLIGHT_RE.search(e.get("name", "")):
            continue
        km = e.get("laenge_km")
        if not isinstance(km, (int, float)) or e.get("name") in LAENGSTE_AUSNAHMEN:
            continue
        try:
            tag = dt.date.fromisoformat(e["datum_start"])
        except (KeyError, ValueError):
            continue
        if not (datum <= tag <= bis):
            continue
        schluessel = (e["name"], e.get("standort", ""))
        if schluessel not in je_name or km > je_name[schluessel]["km"][-1]:
            je_name[schluessel] = {"name": e["name"], "ort": e.get("standort", ""), "land": e.get("land", ""),
                                   "sport": sport, "art2": e.get("art2"), "datum": e["datum_start"], "km": [km],
                                   "url": e.get("veranstalter_url")}
    gesehen, aus = set(), []
    for v in sorted(je_name.values(), key=lambda v: (-v["km"][-1], v["datum"])):
        doppel = (v["datum"], v["ort"].lower(), round(v["km"][-1]))
        if doppel in gesehen:
            continue
        gesehen.add(doppel)
        aus.append(v)
    return aus[:n]


def _balken_zeile(v: dict) -> dict:
    tag = dt.date.fromisoformat(v["datum"])
    km = v["km"][-1]
    km_text = f"{km:,.0f}".replace(",", ".") if km >= 1000 else fmt_km(km)
    return {"name": v["name"], "km": km, "km_text": f"{km_text} km",
            "datum": datum_kurz(tag, jahr=True), "ort": f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
            "sport": v["sport"], "url": v.get("url")}


def format_laengste(datum: dt.date, events: list[dict], rng: random.Random) -> dict | None:
    """„Welches würdest du schaffen?" – eine animierte Balkengrafik der
    längsten Rennen der nächsten 12 Monate: die Balken wachsen nacheinander
    vom kürzesten zum längsten, die Kilometer zählen hoch (vom Nutzer am
    27.10.2026: „eine animierte Grafik der 10 längsten Radevents oder der 10
    längsten Laufevents … welches Event würdest du schaffen? … Laufen und
    Radfahren in einen Post"). Varianten im Wechsel: gemischt (je 5 Lauf und
    Rad in zwei Feldern), nur Laufen, nur Rad (je 10)."""
    runde = datum.toordinal() // 14
    for versuch in range(len(LAENGSTE_VARIANTEN)):
        variante = LAENGSTE_VARIANTEN[(runde + versuch) % len(LAENGSTE_VARIANTEN)]
        if variante == "gemischt":
            gruppen = [("Laufen", laengste_kandidaten(datum, events, "Laufen", 5)),
                       ("Fahrrad", laengste_kandidaten(datum, events, "Fahrrad", 5))]
        else:
            gruppen = [(variante, laengste_kandidaten(datum, events, variante, 10))]
        if all(len(z) >= 5 for _, z in gruppen):
            break
    else:
        return None
    felder = [{"sport": sp, "titel": {"Laufen": "Laufen", "Fahrrad": "Rad"}[sp],
               "zeilen": [_balken_zeile(v) for v in zeilen]} for sp, zeilen in gruppen]
    laengste = max(z["km"] for f in felder for z in f["zeilen"])
    wort = {"gemischt": "RENNEN", "Laufen": "LÄUFE", "Fahrrad": "RADRENNEN"}[variante]
    anzahl = sum(len(f["zeilen"]) for f in felder)
    folien = [
        {"typ": "hook", "ueber": "Würdest du das schaffen?",
         "zahl": f"{laengste:,.0f} KM".replace(",", ".") if laengste >= 1000 else f"{fmt_km(laengste)} KM",
         "titel": f"DIE {anzahl} LÄNGSTEN {wort} BEI UNS", "zeilen": ["in den nächsten 12 Monaten"]},
        {"typ": "balken", "titel": f"Die längsten {wort.capitalize()}", "felder": felder,
         "dauer": 1.2 + 0.55 * anzahl},
        {"typ": "satz", "ueber": "Und du?", "titel": "WELCHES WÜRDEST DU SCHAFFEN?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie("Check it out!", "Alle Ultras mit Termin", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(f['sport'], '•')} {z['km_text']}: {z['name']} ({z['datum']}, {z['ort']})"
                       for f in felder for z in f["zeilen"])
    caption = caption_bauen([
        f"🤯 Bis zu {_balken_zeile({'name': '', 'km': [laengste], 'datum': '2000-01-01', 'ort': '', 'land': '', 'sport': ''})['km_text']}"
        " – die längsten Rennen in Deutschland, Österreich, der Schweiz "
        "und Südtirol in den nächsten 12 Monaten:",
        zeilen,
        "Welches würdest du schaffen? Schreib's in die Kommentare 👇",
    ], hashtags(None if variante == "gemischt" else variante, rng=rng, extra=["#ultra", "#ultracycling",
                                                                             "#ultrarunning"]),
        rng, len(events))
    sport = None if variante == "gemischt" else variante
    return _beitrag("laengste", datum, folien, caption, sport, variante=variante,
                    foto_sport=sport or ("Laufen", "Fahrrad")[datum.toordinal() % 2])


def format_top(datum: dt.date, events: list[dict], rng: random.Random,
               grosse: list[dict] | None = None, kategorie: str | None = None,
               anzahl: int | None = None, design: str | None = None) -> dict | None:
    """„Die 7 größten Trail-Events" – die größten Events einer Kategorie in
    den nächsten 12 Monaten, OHNE Rangfolge (vom Nutzer: „es muss auch
    nicht bewertet werden wer der beste … Einfach die 5 größten"), nach
    Datum vorgestellt, am Ende alle zusammen. Kategorie, Anzahl (3/5/7/10)
    und Design wechseln von Mal zu Mal."""
    grosse = grosse if grosse is not None else lade_grosse()
    kandidaten = [(k, top_kandidaten(datum, events, grosse, k)) for k in TOP_KATEGORIEN]
    # Nur Kategorien rotieren, die mindestens drei Events haben - sonst
    # sprang eine leere Kategorie auf die nächste, und die kam zweimal.
    moeglich = [(k, t) for k, t in kandidaten if len(t) >= min(TOP_ANZAHLEN)]
    if not moeglich:
        return None
    runde = datum.toordinal() // 14            # ein Top-Reel alle zwei Wochen
    kat, liste = moeglich[runde % len(moeglich)]
    if kategorie:                              # Sonderplan: fest vorgegeben
        kat, liste = next(((k, t) for k, t in moeglich if k[0] == kategorie), (kat, liste))
    # Design und Anzahl wechseln jedes Mal (nie zweimal dasselbe hintereinander)
    wunsch = anzahl or TOP_ANZAHLEN[(runde + runde // len(TOP_ANZAHLEN)) % len(TOP_ANZAHLEN)]
    anzahl = max(n for n in TOP_ANZAHLEN if n <= len(liste) and n <= max(wunsch, min(TOP_ANZAHLEN)))
    design = design if design in TOP_DESIGNS else TOP_DESIGNS[runde % len(TOP_DESIGNS)]
    schluessel, name, sport, _ = kat
    eintraege = top_eintraege(liste[:anzahl])
    titel = f"Die {anzahl} größten {name}"
    basis = {"typ": "top", "variante": design, "sport": sport, "titel": titel, "eintraege": eintraege,
             "start": datum.isoformat()[:7], "dauer": TOP_DAUER.get(anzahl, 2.0)}
    folien = [
        {"typ": "hook", "ueber": "Die nächsten 12 Monate", "zahl": str(anzahl),
         "titel": f"DIE GRÖSSTEN {name.upper()}", "zeilen": ["Deutschland · Österreich · Schweiz · Südtirol"]},
        *[dict(basis, aktiv=i) for i in range(anzahl)],
        dict(basis, aktiv=None, schluss="Wo bist du dabei?"),
        cta_folie("Check it out!", f"Alle {name} mit Termin", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(f"• {e['datum']}: {e['name']}, {e['ort']}"
                       + (f" ({_starter_kurz(e['starter'])})" if e.get("starter") else "")
                       for e in eintraege)
    caption = caption_bauen([
        f"🗓️ Die {anzahl} größten {name} der nächsten 12 Monate in Deutschland, Österreich, der Schweiz "
        "und Südtirol – nach Datum:",
        zeilen,
        "Gezählt nach allen Teilnehmenden der Veranstaltung, letzte Ausgabe (Angaben der Veranstalter, "
        "gerundet). Wo bist du dabei? 👇 Speichern nicht vergessen.",
    ], hashtags(sport, rng=rng, extra=[f"#{schluessel}", "#rennkalender"]), rng, len(events))
    return _beitrag("top", datum, folien, caption, sport, kategorie=schluessel, design=design, anzahl=anzahl)


def _starter_kurz(n: int) -> str:
    gerundet = round(n, -3) if n >= 10000 else round(n, -2)
    return f"ca. {gerundet:,} am Start".replace(",", ".")


def anmeldestart(g: dict) -> tuple[dt.date, bool] | None:
    """(Datum, genau?) aus `anmeldestart` - „YYYY-MM-DD" oder „YYYY-MM"."""
    wert = str(g.get("anmeldestart") or "")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", wert):
            return dt.date.fromisoformat(wert), True
        if re.fullmatch(r"\d{4}-\d{2}", wert):
            return dt.date.fromisoformat(wert + "-01"), False
    except ValueError:
        pass
    return None


def renntermin(g: dict, events: list[dict], ab: dt.date) -> tuple[dt.date, dict | None] | None:
    """Der nächste Termin eines großen Events ab `ab`: aus events.json
    (sichtbar, nicht vorläufig), sonst `termin` aus der Liste."""
    kandidaten = []
    for v in sicher(veranstaltungen(events, ab, ab + dt.timedelta(days=550))):
        if gross_fuer(v, [g]):
            kandidaten.append((dt.date.fromisoformat(v["datum"]), v))
    if kandidaten:
        return min(kandidaten, key=lambda x: x[0])
    try:
        t = dt.date.fromisoformat(str(g.get("termin") or ""))
        return (t, None) if t >= ab else None
    except ValueError:
        return None


def format_anmeldung(datum: dt.date, events: list[dict], rng: random.Random,
                     grosse: list[dict] | None = None, heute: dt.date | None = None) -> dict | None:
    """„Anmeldung startet": die großen Events, deren Anmeldung in diesem
    Monat öffnet - je Event Logo, Anmeldestart und Renntermin. Am 1. des
    Monats (vom Nutzer: „welche Events diesen Monat mit der Registrierung
    anfangen", Beispiel LLC Marathon Regensburg)."""
    grosse = grosse if grosse is not None else lade_grosse()
    liste = []
    for g in grosse:
        a = anmeldestart(g)
        if not a or (a[0].year, a[0].month) != (datum.year, datum.month):
            continue
        rt = renntermin(g, events, a[0])
        if not rt:
            continue
        liste.append((a, rt, g))
    if len(liste) < ANMELDUNG_MIN:
        return None
    liste.sort(key=lambda x: -(x[2].get("starter") or 0))
    liste = sorted(liste[:ANMELDUNG_MAX], key=lambda x: (x[0][0], x[2]["name"]))
    monat_name = MONATE[datum.month - 1]

    heute = heute or datum

    def ab_text(a: tuple[dt.date, bool]) -> str:
        # `heute` ist der Tag des Beitrags: was schon offen ist, heißt „seit"
        if a[1] and a[0] < heute:
            return f"Anmeldung offen seit {datum_kurz(a[0])}"
        return f"Anmeldung ab {datum_kurz(a[0])}" if a[1] else f"Anmeldung im {monat_name}"

    folien = [
        {"typ": "hook", "ueber": "Anmeldung startet", "zahl": str(len(liste)),
         "titel": f"TOP-RENNEN ÖFFNEN IM {monat_name.upper()} DIE ANMELDUNG",
         "zeilen": ["Startplatz sichern"]},
        *[logo_karte(g, datum_kurz(rt[0], jahr=True), ueber=ab_text(a), v=rt[1]) for a, rt, g in liste],
        {"typ": "satz", "ueber": "Und du?", "titel": "WO MELDEST DU DICH AN?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie("Check it out!", "Alle Termine und Anmeldelinks", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(
        f"{SPORT_EMOJI.get(g.get('sport'), '•')} {g['name']}: {ab_text(a).replace('Anmeldung ', '')} "
        f"(Rennen am {fmt_datum_lang(rt[0])})" for a, rt, g in liste)
    haupt = Counter(g.get("sport") for _, _, g in liste).most_common(1)[0][0]
    caption = caption_bauen([
        f"📝 Anmeldestart im {monat_name}: {len(liste)} große Rennen öffnen ihre Startplätze.",
        zeilen,
        "Angaben ohne Gewähr – die genauen Zeiten stehen beim Veranstalter. Wo meldest du dich an? 👇",
    ], hashtags(haupt, rng=rng, extra=["#anmeldung", "#startplatz"]), rng, len(events))
    return _beitrag("anmeldung", datum, folien, caption, haupt, monat=f"{monat_name} {datum.year}",
                    stil="farbe")


# ------------------------------------------------- Rennjahr und Duell

JAHR_MIN_MONATE = 10


def format_jahr(datum: dt.date, events: list[dict], rng: random.Random,
                grosse: list[dict] | None = None) -> dict | None:
    """„Dein Rennjahr": die nächsten zwölf Monate, je Monat das größte
    Event (mit geprüftem Logo vor ohne) - Monat für Monat im Takt, dann
    alle zwölf auf einen Blick. Nennt keine Rangfolge, nur „das größte"."""
    import insta_logos
    grosse = grosse if grosse is not None else lade_grosse()
    je_monat: dict[str, dict[str, tuple]] = defaultdict(dict)
    for v in sicher(veranstaltungen(events, datum.replace(day=1), datum + dt.timedelta(days=365))):
        g = gross_fuer(v, grosse)
        if g and g["name"] not in je_monat[v["datum"][:7]]:
            je_monat[v["datum"][:7]][g["name"]] = (g, v)
    eintraege, schon = [], set()
    jahr, monat = datum.year, datum.month
    for _ in range(12):
        kandidaten = [(g, v) for g, v in je_monat.get(f"{jahr:04d}-{monat:02d}", {}).values()
                      if g["name"] not in schon]
        if kandidaten:
            g, v = max(kandidaten, key=lambda x: (insta_logos.logo_bild(insta_logos.slug(x[0]["name"])) is not None,
                                                  x[0].get("starter") or 0))
            schon.add(g["name"])
            tag = dt.date.fromisoformat(v["datum"])
            eintraege.append({"monat": monat, "jahr": jahr, "logo_id": insta_logos.slug(g["name"]),
                              "name": g["name"], "datum": datum_kurz(tag),
                              "ort": f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
                              "starter": g.get("starter"), "sport": g.get("sport")})
        monat += 1
        if monat > 12:
            jahr, monat = jahr + 1, 1
    if len(eintraege) < JAHR_MIN_MONATE:
        return None
    n = len(eintraege)
    basis = {"typ": "jahr", "eintraege": eintraege, "sport": "Laufen",
             "titel": f"Dein Rennjahr {eintraege[0]['jahr']}/{str(eintraege[-1]['jahr'])[2:]}"}
    folien = [
        {"typ": "hook", "ueber": "Dein Rennjahr", "zahl": str(n),
         "titel": f"MONATE, {n} HIGHLIGHTS", "zeilen": ["Das größte Event jedes Monats"]},
        *[dict(basis, aktiv=i, blitz=True) for i in range(n)],
        dict(basis, aktiv=None),
        {"typ": "satz", "ueber": "Und du?", "titel": "WELCHER MONAT IST DEINER?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie("Check it out!", "Alle Events, jeden Monat", SEITE, "Link in der Bio"),
    ]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(e['sport'], '•')} {MONATE[e['monat'] - 1]}: {e['name']}, {e['ort']}"
                       for e in eintraege)
    caption = caption_bauen([
        f"📅 Dein Rennjahr: {n} Monate, {n} Highlights – das größte Event jedes Monats in Deutschland, "
        "Österreich, der Schweiz und Südtirol.",
        zeilen,
        "Gezählt nach Teilnehmenden der letzten Ausgabe (Angaben der Veranstalter). Welcher Monat ist "
        "deiner? 👇 Speichern nicht vergessen.",
    ], hashtags("Laufen", rng=rng, extra=["#rennkalender", "#saisonplanung"]), rng, len(events))
    return _beitrag("jahr", datum, folien, caption, "Laufen")


DUELL_KATEGORIEN = ("marathon", "halbmarathon", "radmarathon", "trail", "triathlon", "ultra")


def _strecken_kurz(km: list[float]) -> str:
    werte = sorted(km, reverse=True)[:2]
    if not werte:
        return "–"
    return " · ".join(fmt_km(k).replace(" km", "") for k in werte) + " km"


def duell_paare(datum: dt.date, events: list[dict], grosse: list[dict]) -> list[tuple[str, dict, dict]]:
    """Mögliche Duelle: zwei große Events derselben Kategorie, beide mit
    geprüftem Logo, die Größe höchstens Faktor 2 auseinander - in der
    Reihenfolge der Kategorien, je Kategorie die größten zuerst."""
    import insta_logos
    paare = []
    for kat in TOP_KATEGORIEN:
        if kat[0] not in DUELL_KATEGORIEN:
            continue
        liste = [e for e in top_kandidaten(datum, events, grosse, kat)
                 if insta_logos.logo_bild(insta_logos.slug(e["g"]["name"])) and e["g"].get("starter")]
        for a, b in zip(liste[0::2], liste[1::2]):
            if a["g"]["starter"] <= 2 * b["g"]["starter"]:
                paare.append((kat[0], a, b))
    return paare


def format_duell(datum: dt.date, events: list[dict], rng: random.Random,
                 grosse: list[dict] | None = None, paar: list[str] | None = None) -> dict | None:
    """„Duell": zwei große Events derselben Kategorie Seite an Seite -
    Termin, Ort, Teilnehmende, Strecken - und die Frage, welches man
    wählen würde (Kommentare). Das Paar wechselt mit dem Datum."""
    import insta_logos
    grosse = grosse if grosse is not None else lade_grosse()
    paare = duell_paare(datum, events, grosse)
    if not paare:
        return None
    kat, a, b = paare[(datum.toordinal() // 7) % len(paare)]
    if paar:                                   # Sonderplan: ein festes Paar
        kat, a, b = next((p for p in paare if {p[1]["g"]["name"], p[2]["g"]["name"]} == set(paar)), (kat, a, b))
    name_kat = next(k[1] for k in TOP_KATEGORIEN if k[0] == kat)
    sport = a["g"]["sport"]

    def seite(e: dict) -> dict:
        v, g = e["v"], e["g"]
        return {"logo_id": insta_logos.slug(g["name"]), "name": g["name"]}

    def wert(e: dict) -> tuple:
        v, g = e["v"], e["g"]
        return (datum_kurz(dt.date.fromisoformat(v["datum"]), jahr=True),
                f"{v['ort']} {LAND_KURZ.get(v['land'], '')}".strip(),
                g["starter"], _strecken_kurz(sorted(e["km"])))

    wa, wb = wert(a), wert(b)
    zeilen = [
        ["Termin", wa[0], wb[0], -1],
        ["Ort", wa[1], wb[1], -1],
        ["Am Start (ca.)", _starter_zahl(wa[2]), _starter_zahl(wb[2]), 0 if wa[2] >= wb[2] else 1],
        ["Strecken", wa[3], wb[3], -1],
    ]
    frage = "Welches würdest du wählen?"
    folien = [
        {"typ": "hook", "ueber": f"Duell · {name_kat}", "titel": f"{a['g']['name']} oder {b['g']['name']}?",
         "zeilen": ["Zwei Riesen im Vergleich"]},
        {"typ": "duell", "titel": f"Duell · {name_kat}", "sport": sport, "links": seite(a), "rechts": seite(b),
         "zeilen": zeilen, "frage": frage, "dauer": 7.0},
        {"typ": "satz", "ueber": "Du entscheidest", "titel": "LINKS ODER RECHTS?",
         "zeilen": ["Schreib's in die Kommentare"]},
        cta_folie("Check it out!", f"Alle {name_kat} mit Termin", SEITE, "Link in der Bio"),
    ]
    caption = caption_bauen([
        f"⚔️ Duell: {a['g']['name']} oder {b['g']['name']}?",
        f"🅰️ {a['g']['name']} – {wa[0]}, {wa[1]}, {_starter_kurz(wa[2])}\n"
        f"🅱️ {b['g']['name']} – {wb[0]}, {wb[1]}, {_starter_kurz(wb[2])}",
        "Teilnehmende der letzten Ausgabe laut Veranstalter (gerundet). Welches würdest du wählen? "
        "Schreib A oder B in die Kommentare 👇",
    ], hashtags(sport, rng=rng, extra=[f"#{kat}", "#duell"]), rng, len(events))
    return _beitrag("duell", datum, folien, caption, sport, kategorie=kat)


def _starter_zahl(n: int) -> str:
    gerundet = round(n, -3) if n >= 10000 else round(n, -2)
    return f"{gerundet:,}".replace(",", ".")


# ------------------------------------------------- Sonderplan (Startwoche)

SONDERPLAN_DATEI = MARKETING / "sonderplan.json"


def lade_sonderplan(pfad: Path | None = None) -> dict[str, dict]:
    """Feste Formate für einzelne Tage (marketing/instagram/sonderplan.json),
    z. B. die Startwoche ab 02.11.2026: {"tage": {"2026-11-02": {"format":
    "jahr"}, …}}. Optional mit `kategorie`, `anzahl`, `design` für „top"."""
    try:
        return json.loads((pfad or SONDERPLAN_DATEI).read_text(encoding="utf-8")).get("tage", {})
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ Stories

COUNTDOWN_TAGE = (100, 60, 30, 14, 7)
WOCHENTAG_LANG = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def stories_fuer(datum: dt.date, events: list[dict], beitrag: dict, rng: random.Random) -> list[dict]:
    """Bis zu zwei Stories zum Beitrag des Tages (eine Folie je Story, als
    Bild gerendert, insta_video.rendere_story):

      1. „rennen":    das spannendste Rennen der nächsten drei Tage
      2. „countdown": ein großes Rennen in genau 100/60/30/14/7 Tagen -
                      sonst „reel": Hinweis auf das neue Reel
    """
    aus = []
    nahe = sicher(veranstaltungen(events, datum + dt.timedelta(days=1), datum + dt.timedelta(days=3)))
    if nahe:
        v = hoehepunkte(nahe, 1, rng)[0]
        tag = dt.date.fromisoformat(v["datum"])
        wann = "Morgen" if (tag - datum).days == 1 else f"Am {WOCHENTAG_LANG[tag.weekday()]}"
        aus.append({"art": "rennen", "sport": v["sport"],
                    "folie": dict(event_karte(v, ueber=f"{wann}: Rennen des Tages"), hinweis=f"Alle Infos: {SEITE}")})
    gross = []
    for tage in COUNTDOWN_TAGE:
        tag = datum + dt.timedelta(days=tage)
        for v in sicher(veranstaltungen(events, tag, tag)):
            if hoehepunkt_wert(v) >= 9:
                gross.append((hoehepunkt_wert(v), tage, v))
    if gross:
        _, tage, v = max(gross, key=lambda g: (g[0], -g[1], g[2]["name"]))
        folie = {"typ": "hook", "ueber": "Countdown", "zahl": f"NOCH {tage} TAGE", "titel": v["name"].upper(),
                 "zeilen": [f"{fmt_datum(v['datum'])} · {v['ort']}"]}
        if v.get("url"):
            folie["url"] = v["url"]
        aus.append({"art": "countdown", "sport": v["sport"], "folie": folie})
    else:
        erste = (beitrag.get("folien") or [{}])[0]
        kern = " ".join(t for t in (erste.get("zahl"), erste.get("titel")) if t) or "Neues Reel"
        aus.append({"art": "reel", "sport": beitrag.get("sport"),
                    "folie": {"typ": "satz", "ueber": "Neues Reel", "titel": kern.upper()[:80],
                              "zeilen": ["Jetzt auf unserem Profil"]}})
    return aus


def jahrestag(datum: dt.date, momente: list[dict]) -> dict | None:
    for m in momente:
        d = dt.date.fromisoformat(m["datum"])
        if (d.month, d.day) == (datum.month, datum.day) and d.year < datum.year:
            return m
    return None


def moment_wahl(datum: dt.date, momente: list[dict]) -> tuple[dict, bool]:
    m = jahrestag(datum, momente)
    if m:
        return m, True
    # Sonst reihum - nach Tagen seit einem festen Anfang, je Moment-Tag
    # (Di/Do/So) ein anderer. Stabil, solange momente.json gleich bleibt.
    return momente[(datum.toordinal() // 2) % len(momente)], False


def format_moment(datum: dt.date, events: list[dict], rng: random.Random,
                  momente: list[dict] | None = None, moment: dict | None = None) -> dict:
    momente = momente if momente is not None else lade_momente()
    if moment is None:
        moment, ist_jahrestag = moment_wahl(datum, momente)
    else:
        ist_jahrestag = jahrestag(datum, [moment]) is not None
    d = dt.date.fromisoformat(moment["datum"])
    jahre = datum.year - d.year - ((datum.month, datum.day) < (d.month, d.day))
    ueber = f"Heute vor {jahre} Jahren" if ist_jahrestag else fmt_datum_lang(d)
    folien = [
        {"typ": "moment", "ueber": ueber, "zahl": moment.get("zahl", ""), "titel": moment["titel"],
         "zeilen": moment.get("zeilen", [])},
        {"typ": "moment_text", "titel": moment.get("ort", ""), "text": moment["text"]},
        {"typ": "cta", "titel": "Und dein nächstes Rennen?", "zeilen": [SEITE, "Link in der Bio"]},
    ]
    einstieg = (f"📅 Heute vor {jahre} Jahren: " if ist_jahrestag else f"📅 {fmt_datum_lang(d)}: ") + moment["titel"]
    caption = caption_bauen([
        einstieg,
        moment["text"],
        moment.get("frage") or "Welcher Moment hat dich am meisten motiviert? 👇",
        f"Quelle: {moment['quelle']}" if moment.get("quelle") else "",
    ], hashtags(moment.get("sport"), rng=rng, extra=moment.get("hashtags", [])), rng, len(events))
    return _beitrag("moment", datum, folien, caption, moment.get("sport"),
                    moment_id=moment["id"], jahrestag=ist_jahrestag)


def format_clip(datum: dt.date, events: list[dict], rng: random.Random,
                clips: list[dict] | None = None) -> dict | None:
    clips = clips if clips is not None else lade_clips()
    if not clips:
        return None
    clip = clips[(datum.toordinal() // 7) % len(clips)]
    folien = [
        {"typ": "clip_titel", "ueber": clip.get("ueber", ""), "titel": clip["titel"],
         "zeilen": clip.get("zeilen", [])},
        {"typ": "cta", "titel": clip.get("cta", "Selbst an den Start?"), "zeilen": [SEITE, "Link in der Bio"]},
    ]
    credit = f"🎥 {clip['urheber']} – {clip['lizenz']}" + (f" ({clip['quelle_url']})" if clip.get("quelle_url") else "")
    caption = caption_bauen([clip.get("caption") or clip["titel"], credit],
                            hashtags(clip.get("sport"), rng=rng, extra=clip.get("hashtags", [])), rng, len(events))
    return _beitrag("clip", datum, folien, caption, clip.get("sport"), clip=clip)


# ---------------------------------------------------------------- Plan

def plane(datum: dt.date, events: list[dict] | None = None, format_: str | None = None,
          momente: list[dict] | None = None, clips: list[dict] | None = None,
          witze: list[dict] | None = None, grosse: list[dict] | None = None,
          anlaesse: list[dict] | None = None, sonderplan: dict[str, dict] | None = None) -> dict:
    """Der Beitrag für `datum` samt Stories. `format_` erzwingt ein Format
    (Test, Handlauf); fehlen dafür die Daten (zu wenige Events, keine
    Clips), fällt der Plan auf einen Moment zurück - es gibt immer einen
    Beitrag."""
    events = events if events is not None else lade_events()
    momente = momente if momente is not None else lade_momente()
    rng = random.Random(datum.toordinal())
    wunsch = format_ or WOCHENPLAN[datum.weekday()]
    beitrag = None
    sonder = (sonderplan if sonderplan is not None else lade_sonderplan()).get(datum.isoformat()) \
        if format_ is None else None
    if sonder:
        # ein fester Tag (Startwoche) geht allem vor; fehlen die Daten, gilt der Plan
        wahl_ = sonder.get("format")
        if wahl_ == "top":
            beitrag = format_top(datum, events, rng, grosse, sonder.get("kategorie"), sonder.get("anzahl"),
                                 sonder.get("design"))
        elif wahl_ == "anmeldung":
            beitrag = format_anmeldung(datum.replace(day=1), events, rng, grosse, heute=datum)
            if beitrag:
                beitrag["datum"] = datum.isoformat()
                beitrag["kampagne"] = f"anmeldung-{datum.isoformat()}"
        elif wahl_ == "duell":
            beitrag = format_duell(datum, events, rng, grosse, sonder.get("paar"))
        elif wahl_ in ("jahr", "monat"):
            beitrag = {"jahr": format_jahr, "monat": format_monat}[wahl_](datum, events, rng, grosse)
        elif wahl_ == "laengste":
            beitrag = format_laengste(datum, events, rng)
        elif wahl_:
            wunsch = wahl_
    if beitrag is None and format_ is None and not sonder:
        # Ein großes internationales Rennen geht allem vor (seltener als
        # alles andere), dann die zwei Tage im Monat mit Logo-Reel.
        a = anlass_am(datum, anlaesse)
        if a:
            beitrag = format_anlass(datum, events, rng, a, grosse)
        # Belegt ein Anlass den 1. oder den letzten Freitag, rückt das
        # Monatsformat einen Tag weiter (NYC-Marathon am 01.11.2026).
        gestern = datum - dt.timedelta(days=1)
        gestern_anlass = anlass_am(gestern, anlaesse) is not None
        if beitrag is None and (datum.day == 1 or (datum.day == 2 and gestern_anlass)):
            beitrag = format_anmeldung(datum.replace(day=1), events, rng, grosse, heute=datum)
            if beitrag:
                beitrag["datum"] = datum.isoformat()
                beitrag["kampagne"] = f"anmeldung-{datum.isoformat()}"
        elif beitrag is None and (letzter_freitag(datum) or (letzter_freitag(gestern) and gestern_anlass)):
            beitrag = format_monat(datum, events, rng, grosse)
        elif beitrag is None and datum.weekday() == 5 and datum.isocalendar()[1] % 2 == 0:
            beitrag = format_top(datum, events, rng, grosse)
        elif beitrag is None and datum.weekday() == 0 and datum.isocalendar()[1] % 2 == 1:
            beitrag = format_laengste(datum, events, rng)
    if beitrag is None and format_ is None and not sonder and datum.weekday() in JAHRESTAG_ERLAUBT:
        m = jahrestag(datum, momente)
        if m:
            beitrag = format_moment(datum, events, rng, momente, m)
    if beitrag is None:
        if wunsch == "humor" and format_ is None:
            # Gibt es lizenzierte Clips, gehört der Donnerstag ihnen.
            beitrag = format_clip(datum, events, rng, clips) if (clips if clips is not None else lade_clips()) else None
        bauer = {
            "krass": format_krass, "naehe": format_naehe, "wuerdest": format_wuerdest,
            "wochenende": format_wochenende, "saison": format_saison,
            "wochenvorschau": format_wochenvorschau, "spotlight": format_spotlight, "region": format_region,
        }
        if beitrag is None:
            if wunsch in bauer:
                beitrag = bauer[wunsch](datum, events, rng)
            elif wunsch == "humor":
                beitrag = format_humor(datum, events, rng, witze)
            elif wunsch == "clip":
                beitrag = format_clip(datum, events, rng, clips)
            elif wunsch == "monat":
                beitrag = format_monat(datum, events, rng, grosse)
            elif wunsch == "anmeldung":
                beitrag = format_anmeldung(datum, events, rng, grosse)
            elif wunsch == "top":
                beitrag = format_top(datum, events, rng, grosse)
            elif wunsch == "laengste":
                beitrag = format_laengste(datum, events, rng)
            elif wunsch == "jahr":
                beitrag = format_jahr(datum, events, rng, grosse)
            elif wunsch == "duell":
                beitrag = format_duell(datum, events, rng, grosse)
            elif wunsch == "anlass":
                # von Hand: der nächste Anlass ab dem Datum
                naechster = sorted((a for a in (anlaesse if anlaesse is not None else lade_anlaesse())
                                    if a.get("datum") and a["datum"] >= datum.isoformat()),
                                   key=lambda a: a["datum"])
                if naechster:
                    beitrag = format_anlass(datum, events, rng, naechster[0], grosse)
        if beitrag is None:
            beitrag = format_moment(datum, events, rng, momente)
    beitrag["stories"] = stories_fuer(datum, events, beitrag, random.Random(datum.toordinal() + 1))
    return beitrag


def format_am(datum: dt.date, momente: list[dict] | None = None) -> str:
    """Das Format, das der Plan für `datum` vorsieht, ohne die Events zu
    lesen (für die Auswertung alter Beiträge): Jahrestag oder Wochenplan.
    Ein Rückfall auf „moment" mangels Events bleibt unsichtbar."""
    momente = momente if momente is not None else lade_momente()
    sonder = lade_sonderplan().get(datum.isoformat())
    if sonder and sonder.get("format"):
        return sonder["format"]
    if anlass_am(datum):
        return "anlass"
    if datum.day == 1 and any((a := anmeldestart(g)) and (a[0].year, a[0].month) == (datum.year, datum.month)
                              for g in lade_grosse()):
        return "anmeldung"
    if letzter_freitag(datum):
        return "monat"
    if datum.weekday() == 5 and datum.isocalendar()[1] % 2 == 0:
        return "top"
    if datum.weekday() == 0 and datum.isocalendar()[1] % 2 == 1:
        return "laengste"
    if datum.weekday() in JAHRESTAG_ERLAUBT and jahrestag(datum, momente):
        return "moment"
    return WOCHENPLAN[datum.weekday()]


# ---------------------------------------------------------- Freigabe-Plan

def beitrag_hash(beitrag: dict) -> str:
    """Kennung des INHALTS eines Beitrags (Format, Folien, Caption) - 16
    Hex-Stellen SHA-256. Die Freigabe im Dashboard (admin.html, Karte
    „Instagram-Freigabe") speichert diese Kennung; der Abendlauf postet
    nur, wenn sein eigener Plan dieselbe ergibt. Ändert sich der Inhalt
    zwischen Freigabe und Posten (ein Datenlauf bringt neue Events, ein
    Moment wird korrigiert), verfällt die Freigabe von selbst, statt dass
    etwas rausgeht, das niemand gesehen hat. Gerechnet VOR der
    Namensnennung, die insta_lauf.py beim Rendern anhängt - sonst
    stimmten plan.json und Abendlauf nie überein."""
    kern = {"format": beitrag.get("format"), "caption": beitrag.get("caption"),
            "folien": beitrag.get("folien")}
    if beitrag.get("stories"):
        kern["stories"] = [st.get("folie") for st in beitrag["stories"]]
    roh = json.dumps(kern, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def plan_liste(start: dt.date, tage: int, events: list[dict] | None = None,
               momente: list[dict] | None = None, clips: list[dict] | None = None,
               grosse: list[dict] | None = None) -> list[dict]:
    """Die Beiträge der nächsten `tage` Tage ab `start` - was das Dashboard
    zur Freigabe zeigt (marketing/instagram/plan.json, im Pages-Workflow
    erzeugt, nie committet). Je Tag Datum, Wochentag, Format, Kennung,
    Folien und Caption; Moment-/Clip-Id, wenn vorhanden."""
    events = events if events is not None else lade_events()
    momente = momente if momente is not None else lade_momente()
    aus = []
    for i in range(tage):
        tag = start + dt.timedelta(days=i)
        b = plane(tag, events, momente=momente, clips=clips, grosse=grosse)
        eintrag = {"datum": b["datum"], "wochentag": WOCHENTAGE[tag.weekday()],
                   "format": b["format"], "hash": beitrag_hash(b),
                   "folien": b["folien"], "caption": b["caption"]}
        if b.get("moment_id"):
            eintrag["moment_id"] = b["moment_id"]
        if b.get("clip"):
            eintrag["clip_id"] = b["clip"].get("id")
        if b.get("stories"):
            eintrag["stories"] = [{"art": st["art"], "folie": st["folie"]} for st in b["stories"]]
        aus.append(eintrag)
    return aus


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Instagram-Beitrag eines Tages planen (ohne Video).")
    ap.add_argument("--datum", default=None, help="YYYY-MM-DD, Vorgabe: heute (Europe/Berlin)")
    ap.add_argument("--format", choices=FORMATE, default=None)
    ap.add_argument("--tage", type=int, default=1, help="so viele Tage ab --datum zeigen")
    ap.add_argument("--plan", type=int, default=0, metavar="TAGE",
                    help="Freigabe-Plan für so viele Tage als JSON schreiben (--json)")
    ap.add_argument("--json", default=None, metavar="PFAD",
                    help="Zieldatei für --plan (Vorgabe: marketing/instagram/plan.json)")
    a = ap.parse_args()
    from zoneinfo import ZoneInfo
    start = dt.date.fromisoformat(a.datum) if a.datum else dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    ev = lade_events()
    if a.plan:
        ziel = Path(a.json) if a.json else MARKETING / "plan.json"
        plan = {"erzeugt": dt.datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="minutes"),
                "von": start.isoformat(), "tage": a.plan, "beitraege": plan_liste(start, a.plan, ev)}
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{ziel}: {len(plan['beitraege'])} Beiträge ab {start}")
        raise SystemExit(0)
    for i in range(a.tage):
        b = plane(start + dt.timedelta(days=i), ev, a.format)
        print(f"===== {b['datum']} ({WOCHENTAGE[dt.date.fromisoformat(b['datum']).weekday()]}) – {b['format']} =====")
        print(json.dumps(b["folien"], ensure_ascii=False, indent=1))
        print("--- Caption ---\n" + b["caption"] + "\n")
