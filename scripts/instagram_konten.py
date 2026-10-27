#!/usr/bin/env python3
"""
scripts/instagram_konten.py
===========================

Das eigene Instagram-Konto großer Veranstaltungen – als kleines Symbol in
der Detail-Box (seit 27.10.2026, vom Nutzer gewünscht: „die größeren
Events mit einem Instagram Account verknüpfen … das Instagram Logo
irgendwo klein hin auf dem Profil von dem Event … Das muss nicht für
jedes Event gemacht werden, aber für die großen wär das schon gut, die
auch einen eigenen Instagram Account haben.“).

Zwei Teile, bewusst getrennt:

1. **Sammeln** (`pruefen`): Die EIGENE Veranstalterseite eines Events
   (`veranstalter_url`, nie ein Portal) wird abgerufen, und jedes
   Instagram-Konto, auf das sie verlinkt, kommt in
   `scripts/instagram_konten.json` – je Adresse die nackte Liste, ohne
   Urteil. Nennt die Unterseite keines, wird einmal die Startseite des
   Hosts gelesen (der Instagram-Link steht meist im Fuß). robots.txt,
   2 s Pause je Host, 15 s Frist und 2 MB wie in insta_veranstalter.py,
   dessen Abrufer hier mitläuft. Jede Adresse höchstens alle
   PRUEF_ABSTAND_TAGE, nach einem Fehler früher. instagram.com selbst
   wird NIE abgerufen – ein Link ist kein Abruf.

2. **Entscheiden** (`event_konto`): Welches der Konten gehört dem Event
   selbst? Nur eines, dessen Name aus dem Namen der Veranstaltung (oder
   ihrem Ort) besteht – `leipzigmarathon` für den Leipzig Marathon,
   `oetztalerradmarathon`, `viking.triathlon`. So fallen genau die Konten
   weg, die der Nutzer nicht meint: der Verein (`lsvham`, `tsvpenzberg`,
   `tuswasserstrasse` – auch wenn er im Namen des Laufs steht), die
   Agentur (`alohasport.at`), der Sponsor (`brooksrunning`), der
   Tourismusverband (`pitztal`), ein Schwesterrennen desselben
   Veranstalters (`erlentriathlon` auf der Seite des Einsiedeln
   Triathlons) und die Ausgabe derselben Serie in einer anderen Stadt
   (`halloweenrunbremen` beim Halloween-Run in Rotenburg). Die Regel steht unten bei `event_konto`; am 27.10.2026
   an 41 Seiten gezählt, bevor sie gebaut war. Geraten wird nie
   (Datenregel 2): kein Treffer, kein Symbol.

`clean_events.fix_instagram()` setzt das Feld `instagram` (der Name ohne
@) an jede Zeile, deren Seite ein Event-Konto nennt, und nimmt es weg,
wenn nicht mehr. Ein Override `"instagram": "<name>"` setzt es von Hand,
`"instagram": null` schaltet es ab – für die Fälle, die die Regel nicht
sieht (Abkürzungen: `trailvsb`, `wtcshamburg`).

    python3 scripts/instagram_konten.py pruefen [--max N] [--zeitlimit S]
    python3 scripts/instagram_konten.py zeigen <Suchwort>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import insta_veranstalter as iv  # noqa: E402  (Abrufer, Instagram-Links, Portalliste)

WURZEL = SCRIPTS.parent
DATEI = SCRIPTS / "instagram_konten.json"
EVENTS_JSON = WURZEL / "events.json"
PRUEF_ABSTAND_TAGE = 90     # eine gelesene Seite erst nach einem Vierteljahr wieder
FEHLER_ABSTAND_TAGE = 21    # eine nicht lesbare früher
PARALLEL = 8                # so viele Hosts gleichzeitig (je Host weiter einer nach dem anderen)
NAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")

# --- die Regel --------------------------------------------------------------

# Wörter, die jede zweite Veranstaltung trägt: Sie zählen zur Abdeckung
# des Kontonamens, belegen aber allein nichts – sonst wäre `erlentriathlon`
# das Konto des Einsiedeln Triathlons.
GENERISCH = {
    "marathon", "halbmarathon", "halfmarathon", "ultramarathon", "radmarathon", "bikemarathon",
    "lauf", "laufen", "lauftag", "laufnacht", "run", "running", "runners", "trail", "trails",
    "trailrun", "trailrunning", "ultratrail", "ultra", "triathlon", "duathlon", "aquathlon",
    "swimrun", "swim", "schwimmen", "bike", "rad", "radrennen", "gravel", "rennen", "race",
    "racing", "cup", "festival", "challenge", "tour", "classic", "city", "citylauf", "stadtlauf",
    "volkslauf", "nachtlauf", "nightrun", "night", "silvesterlauf", "firmenlauf", "frauenlauf",
    "berglauf", "crosslauf", "cross", "backyard", "sport", "sports", "event", "events",
    "marsch", "walk", "open", "series", "serie", "mtb", "xco", "tri", "sprint", "winter",
    "sommer", "summer", "trophy", "grand", "prix", "gran", "fondo", "granfondo",
}
# Vereinskürzel und Vereinswörter: `tsvpenzberg` ist der Verein, nicht
# sein Volkslauf. Die Durchsicht der ersten 128 Treffer am 27.10.2026 fand
# genau diese Fehlerklasse: Steht der Verein im Namen des Laufs („Oktoberlauf
# … TUS Wasserstraße“, „Nikolauslauf des ALV Mainz“, „SCC Cross Country“),
# besteht das Vereinskonto aus Namenswörtern und sah wie ein Event-Konto aus.
# Kürzel, die vorn im Kontonamen allein schon den Verein verraten:
VEREIN_VORN = ("tsv", "tus", "tsg", "vfl", "vfb", "djk", "asv", "ssv", "esv", "psv", "mtv",
               "ltv", "lsv", "rsv", "ttv", "sgv")
# Kürzel, die nur zählen, wenn sie als eigenes Wort im Namen der
# Veranstaltung stehen oder als erstes Glied des Kontonamens („llg_…“) –
# vorn im Kontonamen allein wären sie zu kurz („schwebebahnlauf“, „lac“ =
# See auf Französisch):
VEREIN_KUERZEL = VEREIN_VORN + ("sv", "tv", "sc", "lg", "lc", "rc", "rv", "fc", "cs", "llg", "lac",
                                "alv", "ast", "osc", "scc", "lsg", "usc", "ssc", "ac", "tri")
# Wörter, die im Kontonamen den Verein verraten („athletik_waldniel“,
# „laufclub_geinberg“, „jeunesse_de_fey“):
VEREIN_WORT = ("athletik", "laufclub", "runclub", "runningclub", "triclub", "radsport", "jeunesse",
               "turnverein", "sportverein", "sportclub", "laufgemeinschaft", "lauftreff", "skiclub",
               "verein")
VEREIN = set(VEREIN_KUERZEL) | set(VEREIN_WORT) | {
    "sg", "lt", "ski", "team", "club", "ev", "ltf", "triteam", "laufteam"}
# Füllwörter: decken Buchstaben des Kontonamens ab („cityundtrail“),
# zählen aber nicht als Wort.
FUELL = {"und", "and", "the", "des", "der", "die", "das", "von", "vom"}
STOP = FUELL | {"zum", "zur", "den", "dem", "bei", "mit", "auf", "am", "im", "in", "an",
                "by", "powered", "presented", "de", "la", "le", "du", "di", "et",
                "int", "internationaler", "internationale", "internationales"}
# Endungen im Kontonamen, die nichts über das Event sagen
# („rennsteiglauf.official“, „neujahrsmarathon.ch“).
ENDUNG = {"official", "offiziell", "officiel", "ufficiale", "oficial", "de", "at", "ch", "it",
          "eu", "com", "info", "org", "net", "live", "hq"}
MIN_ABDECKUNG = 0.6         # Anteil der Buchstaben des Kontonamens aus Namenswörtern
MIN_ABDECKUNG_GENERISCH = 0.9
GROSSE_ORTE_AB = 10_000     # Einwohner: ab hier zählt ein Ort im Rest des Kontonamens als fremder Ort
_GROSSE_ORTE: set[str] | None = None


def grosse_orte() -> set[str]:
    """Die Namen der Orte ab GROSSE_ORTE_AB Einwohnern (places.json), in
    beiden Umlaut-Schreibweisen. Ein solcher Ort im NICHT abgedeckten Rest
    des Kontonamens ist ein anderer Ort: `halloweenrunbremen` auf der Seite
    des Halloween-Runs in Rotenburg ist die Bremer Ausgabe der Serie."""
    global _GROSSE_ORTE
    if _GROSSE_ORTE is None:
        _GROSSE_ORTE = set()
        try:
            orte = json.loads((WURZEL / "places.json").read_text(encoding="utf-8"))["orte"]
        except (OSError, ValueError, KeyError):
            orte = []
        for o in orte:
            if len(o) > 5 and isinstance(o[5], int) and o[5] >= GROSSE_ORTE_AB:
                _GROSSE_ORTE |= {v for v in _varianten(o[0]) if len(v) >= 4}
    return _GROSSE_ORTE


def _vereinskonto(konto: str, h: str, name: str) -> bool:
    glieder = [t for t in re.split(r"[._]+", konto.lower()) if t]
    if len(glieder) > 1 and glieder[0] in VEREIN_KUERZEL:
        return True
    if h.startswith(VEREIN_VORN):
        return True
    namens_glieder = {t.lower() for t in re.split(r"[^\w]+", name or "") if t}
    if any(k in namens_glieder and h.startswith(k) for k in VEREIN_KUERZEL):
        return True
    return any(w in h for w in VEREIN_WORT)


def _varianten(wort: str) -> set[str]:
    """„Ötztaler“ → {oetztaler, otztaler}: Kontonamen schreiben Umlaute
    mal mit e, mal ohne."""
    w = wort.lower().replace("ß", "ss")
    mit_e = w.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    ohne = "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c))
    return {re.sub(r"[^a-z0-9]", "", v) for v in (mit_e, ohne)} - {""}


def _woerter(text: str) -> set[str]:
    aus: set[str] = set()
    for teil in re.split(r"[^\wäöüÄÖÜß]+", text or ""):
        teil = re.sub(r"(?:19|20)\d\d$", "", teil)            # „Marathon2027“
        if len(teil) < 3 or teil.isdigit() or teil.lower() in STOP:
            continue
        aus |= {v for v in _varianten(teil) if len(v) >= 3 and not v.isdigit()}
    return aus


def _kontoname(konto: str) -> str:
    teile = [t for t in re.split(r"[._]+", konto.lower()) if t and t not in ENDUNG]
    roh = "".join(teile)
    roh = re.sub(r"(?:19|20)\d\d$", "", roh)                  # „berlinmarathon2027“
    return re.sub(r"[^a-z0-9]", "", roh)


def _bewertung(konto: str, name: str, standort: str) -> tuple[float, bool]:
    """(Abdeckung, belegt): Welcher Anteil des Kontonamens besteht aus
    Wörtern der Veranstaltung, und ist das genug Beleg?"""
    h = _kontoname(konto)
    if len(h) < 4 or _vereinskonto(konto, h, name):
        return 0.0, False
    namen = _woerter(name)
    orte = _woerter(standort)
    kandidaten = sorted((namen | orte | FUELL), key=len, reverse=True)
    belegt_von = [False] * len(h)
    treffer: list[str] = []
    for w in kandidaten:
        start = h.find(w)
        while start != -1:
            if not any(belegt_von[start:start + len(w)]):
                for i in range(start, start + len(w)):
                    belegt_von[i] = True
                treffer.append(w)
            start = h.find(w, start + 1)
    abdeckung = sum(belegt_von) / len(h)
    # Ein großer Ort im Rest, der nicht der eigene ist: ein anderes Rennen.
    rest = re.findall(r"[a-z0-9]+", "".join(c if not b else " " for c, b in zip(h, belegt_von)))
    if any(len(r) >= 4 and r in grosse_orte() and r not in orte for r in rest):
        return abdeckung, False
    worte = [w for w in treffer if w not in FUELL]
    eigen = [w for w in worte if w in namen and w not in orte and w not in GENERISCH and w not in VEREIN]
    ort = [w for w in worte if w in orte and w not in VEREIN]
    generisch = [w for w in worte if w in GENERISCH]
    belegt = (
        (eigen and abdeckung >= MIN_ABDECKUNG)                     # „rennsteiglauf“, „evl.halbmarathon“
        or (ort and generisch and abdeckung >= MIN_ABDECKUNG)      # „leipzigmarathon“
        or (len(set(worte) - VEREIN) >= 2 and abdeckung >= MIN_ABDECKUNG_GENERISCH)  # „cityundtrail“
    )
    return abdeckung, bool(belegt)


def event_konto(konten: list[str] | None, name: str, standort: str = "") -> str | None:
    """Das eigene Konto der Veranstaltung unter den Konten ihrer Seite –
    oder keines. Belegt ist ein Konto, wenn sein Name zu mindestens 60 %
    aus Wörtern der Veranstaltung besteht UND eines davon sie
    unterscheidet (ein Wort ihres Namens, das kein Allerweltswort, kein
    Vereinskürzel und nicht der Ort ist) – oder der Ort zusammen mit einem
    Veranstaltungswort („leipzigmarathon“), oder der Name ganz aus
    mindestens zwei Wörtern der Veranstaltung („cityundtrail“). Mehrere
    belegte: das mit der höchsten Abdeckung; Gleichstand heißt keines."""
    belegte = []
    for konto in konten or []:
        if not NAME_RE.match(konto or ""):
            continue
        abdeckung, belegt = _bewertung(konto, name, standort)
        if belegt:
            belegte.append((abdeckung, konto))
    if not belegte:
        return None
    belegte.sort(reverse=True)
    if len(belegte) > 1 and abs(belegte[0][0] - belegte[1][0]) < 1e-9:
        return None
    return belegte[0][1]


# --- die Datei --------------------------------------------------------------

def lade(pfad: Path = DATEI) -> dict:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichere(daten: dict, pfad: Path = DATEI) -> None:
    """Eine Zeile je Adresse, nach Adresse sortiert – kleine Diffs im
    wöchentlichen Commit."""
    zeilen = [f"  {json.dumps(url, ensure_ascii=False)}: {json.dumps(daten[url], ensure_ascii=False, sort_keys=True)}"
              for url in sorted(daten)]
    pfad.write_text("{\n" + ",\n".join(zeilen) + "\n}\n", encoding="utf-8")


def eigene_seite(url: str | None, domains: tuple[str, ...]) -> bool:
    return bool(url) and bool(re.match(r"https?://", url)) and not iv.ist_portal(url, domains)


# --- Sammeln ---------------------------------------------------------------

def konten_von(url: str, abrufer) -> tuple[list[str] | None, str]:
    """Die Konten, auf die die Seite verlinkt (None = nicht lesbar), und
    woher sie stammen."""
    if not abrufer._darf(url):
        return [], "robots"
    html = abrufer.holen(url)
    konten = iv.namen_im_html(html) if html is not None else None
    quelle = "seite"
    if not konten:
        teile = urlparse(url)
        start = f"{teile.scheme}://{teile.netloc}/"
        if start.rstrip("/") != url.rstrip("/"):
            html2 = abrufer.holen(start)
            if html2 is not None:
                konten, quelle = iv.namen_im_html(html2), "startseite"
    return konten, quelle


def faellig(eintrag: dict | None, heute: dt.date) -> bool:
    if not eintrag:
        return True
    try:
        alter = (heute - dt.date.fromisoformat(eintrag["geprueft"])).days
    except (KeyError, ValueError, TypeError):
        return True
    return alter >= (FEHLER_ABSTAND_TAGE if eintrag.get("fehler") else PRUEF_ABSTAND_TAGE)


def adressen(events: list[dict], heute: dt.date) -> list[str]:
    """Die eigenen Seiten künftiger Events, früheste zuerst."""
    domains = iv.portal_domains()
    erste: dict[str, str] = {}
    for e in events:
        url = e.get("veranstalter_url")
        ende = e.get("datum_ende") or e.get("datum_start") or ""
        if not eigene_seite(url, domains) or ende < heute.isoformat():
            continue
        if any(h in urlparse(url).netloc for h in ("instagram.com", "facebook.com", "ironman.com")):
            continue
        tag = e.get("datum_start") or ""
        if url not in erste or tag < erste[url]:
            erste[url] = tag
    return sorted(erste, key=lambda u: (erste[u], u))


def pruefen(events: list[dict], daten: dict, heute: dt.date, max_seiten: int, zeitlimit: float,
            abrufer_fabrik=None, uhr=time.monotonic, speichern=None, parallel: int = PARALLEL) -> dict:
    """Ruft die fälligen Seiten ab (ungeprüfte zuerst, dann die ältesten
    Prüfungen) und schreibt ihre Konten in `daten`. Gibt eine Zählung
    zurück.

    Mehrere HOSTS gleichzeitig (`parallel` Fäden, je mit eigenem Abrufer),
    alle Seiten eines Hosts nacheinander im selben Faden - die Pause je
    Host bleibt also, wie sie ist. Nacheinander kostete eine Seite rund
    7 s (robots.txt, Seite, notfalls die Startseite mit 2 s Pause), der
    ganze Bestand 7 Stunden; am 27.10.2026 so gemessen und umgebaut."""
    import threading
    fabrik = abrufer_fabrik or iv.Abrufer
    alle = adressen(events, heute)
    neu = [u for u in alle if u not in daten]
    alt = sorted((u for u in alle if u in daten and faellig(daten[u], heute)),
                 key=lambda u: daten[u].get("geprueft", ""))
    reihe = (neu + alt)[:max_seiten]
    je_host: dict[str, list[str]] = {}
    for url in reihe:
        je_host.setdefault(urlparse(url).netloc.lower(), []).append(url)
    gruppen = list(je_host.values())
    beginn = uhr()
    zaehlung = {"geprueft": 0, "mit_konto": 0, "fehler": 0, "offen": len(neu) + len(alt)}
    sperre = threading.Lock()

    def eintragen(url: str, konten: list[str] | None, quelle: str) -> None:
        with sperre:
            vorher = daten.get(url) or {}
            if konten is None:
                daten[url] = {"geprueft": heute.isoformat(), "konten": vorher.get("konten", []), "fehler": True}
                zaehlung["fehler"] += 1
            else:
                daten[url] = {"geprueft": heute.isoformat(), "konten": konten}
                if quelle != "seite":
                    daten[url]["quelle"] = quelle
                if konten:
                    zaehlung["mit_konto"] += 1
            zaehlung["geprueft"] += 1
            if speichern and zaehlung["geprueft"] % 100 == 0:
                speichern(dict(daten))

    def arbeiter() -> None:
        abrufer = fabrik()
        while True:
            with sperre:
                if not gruppen or uhr() - beginn > zeitlimit:
                    return
                gruppe = gruppen.pop(0)
            for url in gruppe:
                if uhr() - beginn > zeitlimit:
                    return
                eintragen(url, *konten_von(url, abrufer))

    faeden = [threading.Thread(target=arbeiter, daemon=True) for _ in range(max(1, parallel))]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    zaehlung["offen"] -= zaehlung["geprueft"]
    return zaehlung


def main() -> int:
    ap = argparse.ArgumentParser(description="Instagram-Konten der Veranstaltungen (eigene Seite).")
    ap.add_argument("--events-json", type=Path, default=EVENTS_JSON)
    ap.add_argument("--datei", type=Path, default=DATEI)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pruefen", help="fällige Veranstalterseiten nach Instagram-Links fragen")
    p.add_argument("--max", type=int, default=400)
    p.add_argument("--zeitlimit", type=float, default=15 * 60, help="Sekunden")
    z = sub.add_parser("zeigen", help="Event-Konten zu einem Suchwort zeigen")
    z.add_argument("suchwort")
    a = ap.parse_args()

    import fangzeile
    events = fangzeile.entfernen(json.loads(a.events_json.read_text(encoding="utf-8")))
    daten = lade(a.datei)
    heute = dt.date.today()
    if a.cmd == "pruefen":
        z = pruefen(events, daten, heute, a.max, a.zeitlimit, speichern=lambda d: speichere(d, a.datei))
        speichere(daten, a.datei)
        konten = sum(1 for e in events if event_konto((daten.get(e.get("veranstalter_url")) or {}).get("konten"),
                                                       e.get("name", ""), e.get("standort", "")))
        print(f"Instagram-Konten: {z['geprueft']} Seiten geprüft, {z['mit_konto']} mit Instagram-Link, "
              f"{z['fehler']} nicht lesbar, {z['offen']} noch fällig; {konten} Zeilen mit Event-Konto.")
        return 0
    wort = a.suchwort.lower()
    for e in events:
        if wort not in (e.get("name", "") + " " + e.get("standort", "")).lower():
            continue
        eintrag = daten.get(e.get("veranstalter_url")) or {}
        print(f"{e.get('datum_start')} {e.get('name')} ({e.get('standort')}): "
              f"Seite {e.get('veranstalter_url')} → Konten {eintrag.get('konten')} → "
              f"{event_konto(eintrag.get('konten'), e.get('name', ''), e.get('standort', '')) or 'keines'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
