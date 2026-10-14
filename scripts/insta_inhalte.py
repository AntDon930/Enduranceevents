#!/usr/bin/env python3
"""
scripts/insta_inhalte.py
========================

Was der Instagram-Account „AusdauerMaschine" an einem Tag postet - und
mit welcher Caption. Ohne Netz, ohne Video: nur die Planung. Das Video
baut scripts/insta_video.py, das Posten scripts/insta_posten.py, alles
zusammen scripts/insta_lauf.py (siehe README, Abschnitt „Instagram").

Der Wochenplan (Europe/Berlin, vom Datum bestimmt - kein Gedächtnis
nötig, derselbe Tag ergibt immer denselben Beitrag):

    Mo  wochenvorschau   die Events der Woche Mo-So, fünf Höhepunkte
    Di  moment           ein großer Moment des Ausdauersports
    Mi  spotlight        eine Sportart in einem Land, die nächsten 30 Tage
    Do  clip             ein lizenzierter Clip aus clips.json (sonst moment)
    Fr  wochenende       Sa + So: wie viele Events wo, fünf Höhepunkte
    Sa  region           rund um eine Großstadt (50 km), nächste 4 Wochen
    So  moment

Jahrestag: Hat ein Moment aus momente.json HEUTE Jahrestag, ersetzt er
an Di/Mi/Do/Sa/So den geplanten Beitrag („Heute vor 7 Jahren …").
Montag und Freitag bleiben bei den Terminen - die bringen Besucher.

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

WOCHENPLAN = {0: "wochenvorschau", 1: "moment", 2: "spotlight", 3: "clip",
              4: "wochenende", 5: "region", 6: "moment"}
JAHRESTAG_ERLAUBT = {1, 2, 3, 5, 6}
FORMATE = ("wochenvorschau", "moment", "spotlight", "clip", "wochenende", "region")

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
        ergebnis.append({
            "name": name, "ort": ort, "datum": datum, "land": zeilen[0].get("land", ""),
            "sport": zeilen[0].get("art1", ""), "art2": zeilen[0].get("art2", ""),
            "lat": zeilen[0].get("lat"), "lon": zeilen[0].get("lon"),
            "km": km, "strecken": len(zeilen),
            "vorlaeufig": any(z.get("datum_vorlaeufig") for z in zeilen),
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
    samstag = datum + dt.timedelta(days=(5 - datum.weekday()) % 7)
    sonntag = samstag + dt.timedelta(days=1)
    liste = veranstaltungen(events, samstag, sonntag)
    if len(liste) < 3:
        return None
    n_land = Counter(v["land"] for v in liste)
    top = hoehepunkte(liste, 5, rng)
    folien = [
        {"typ": "titel", "ueber": f"Wochenende {fmt_datum(samstag.isoformat(), False)} – {fmt_datum(sonntag.isoformat(), False)}",
         "titel": f"{len(liste)} Rennen\nam Wochenende",
         "zeilen": [f"{LAND_FLAGGE.get(l, '')} {n} {LAND_IN.get(l, l)}" for l, n in n_land.most_common()]},
        {"typ": "liste", "titel": "Unsere Tipps", "events": [event_folie(v) for v in top]},
        {"typ": "cta", "titel": "Noch spontan starten?", "zeilen": [SEITE, "Link in der Bio"]},
    ]
    haupt = Counter(v["sport"] for v in liste).most_common(1)[0][0]
    zeilen = "\n".join(f"{SPORT_EMOJI.get(v['sport'], '•')} {fmt_datum(v['datum'])} {v['name']} ({v['ort']})" for v in top)
    caption = caption_bauen([
        wahl(rng, ["Das Wochenende gehört den Ausdauersportlern! 🏁", "Startklar fürs Wochenende? 🔥",
                   "Wer läuft, radelt oder schwimmt am Wochenende? 👇"]),
        f"{len(liste)} Events am Samstag und Sonntag. Unsere Tipps:\n{zeilen}",
        "Schreib uns in die Kommentare, wo du startest! 💬",
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
          momente: list[dict] | None = None, clips: list[dict] | None = None) -> dict:
    """Der Beitrag für `datum`. `format_` erzwingt ein Format (Test,
    Handlauf); fehlen dafür die Daten (zu wenige Events, keine Clips),
    fällt der Plan auf einen Moment zurück - es gibt immer einen Beitrag."""
    events = events if events is not None else lade_events()
    momente = momente if momente is not None else lade_momente()
    rng = random.Random(datum.toordinal())
    wunsch = format_ or WOCHENPLAN[datum.weekday()]
    if format_ is None and datum.weekday() in JAHRESTAG_ERLAUBT:
        m = jahrestag(datum, momente)
        if m:
            return format_moment(datum, events, rng, momente, m)
    bauer = {
        "wochenvorschau": format_wochenvorschau, "wochenende": format_wochenende,
        "spotlight": format_spotlight, "region": format_region,
    }
    beitrag = None
    if wunsch in bauer:
        beitrag = bauer[wunsch](datum, events, rng)
    elif wunsch == "clip":
        beitrag = format_clip(datum, events, rng, clips)
    if beitrag is None:
        beitrag = format_moment(datum, events, rng, momente)
    return beitrag


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
    roh = json.dumps(kern, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def plan_liste(start: dt.date, tage: int, events: list[dict] | None = None,
               momente: list[dict] | None = None, clips: list[dict] | None = None) -> list[dict]:
    """Die Beiträge der nächsten `tage` Tage ab `start` - was das Dashboard
    zur Freigabe zeigt (marketing/instagram/plan.json, im Pages-Workflow
    erzeugt, nie committet). Je Tag Datum, Wochentag, Format, Kennung,
    Folien und Caption; Moment-/Clip-Id, wenn vorhanden."""
    events = events if events is not None else lade_events()
    momente = momente if momente is not None else lade_momente()
    aus = []
    for i in range(tage):
        tag = start + dt.timedelta(days=i)
        b = plane(tag, events, momente=momente, clips=clips)
        eintrag = {"datum": b["datum"], "wochentag": WOCHENTAGE[tag.weekday()],
                   "format": b["format"], "hash": beitrag_hash(b),
                   "folien": b["folien"], "caption": b["caption"]}
        if b.get("moment_id"):
            eintrag["moment_id"] = b["moment_id"]
        if b.get("clip"):
            eintrag["clip_id"] = b["clip"].get("id")
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
