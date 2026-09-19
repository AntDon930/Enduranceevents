#!/usr/bin/env python3
"""Sucht für Zeilen mit Zeitnehmer-, Anmelde- oder Portallink die offizielle
Veranstalterseite - und prüft sie, bevor sie vorgeschlagen wird.

Hintergrund (CLAUDE.md, Datenregel 2 und Punkt 10 der offenen Punkte):
`veranstalter_url` soll die offizielle Seite des Laufs sein, nie ein
Kalenderportal, eine Anmeldeplattform oder ein Zeitnehmer. Die Quellen
liefern aber oft genau das. Vom Nutzer am 19.09.2026 freigegeben („zieh
die anderen Zeitnehmer genauso nach", „check ob es ein Link zu der
offiziellen Webseite gibt").

Zwei Schritte, bewusst getrennt:

    python3 scripts/veranstalter_links.py sammeln  --bericht /tmp/bericht.json
    python3 scripts/veranstalter_links.py anwenden --bericht /tmp/bericht.json

`sammeln` ruft ab (mit Pause je Host, robots.txt wird geachtet) und
schreibt NUR einen Bericht. `anwenden` trägt daraus Overrides in
manual_overrides.json und das Protokoll in links_geprueft.json ein -
und zwar nur die Fälle, deren Zielseite den Lauf erkennbar nennt.

Woher die Kandidaten kommen:

- my.raceresult.com: die Kontaktseite `/<nr>/contact` nennt im JSON-LD
  die Organizer-URL (vom Nutzer am Backyardman Würzburg gezeigt).
- alle anderen Portal-/Anmeldeseiten: jeder externe Link auf der Seite,
  der nicht selbst Portal, Anmeldung, Zeitnehmer oder soziales Netz ist.

Was „geprüft" heißt (dieselbe Regel wie beim Auflösen der
laufen.de-Weiterleitungen): Die Zielseite wird abgerufen, und ihr Text
oder ihr Hostname muss ein unverwechselbares Wort des Veranstaltungs-
namens enthalten (mindestens fünf Buchstaben; „lauf", „marathon",
„Sparkasse" und ähnliche Allerweltswörter zählen nicht) oder das Datum.
Nennt keine Kandidatenseite den Lauf, bleibt der alte Link stehen und
der Fall wird als `unklar` protokolliert - geraten wird nie.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import unicodedata
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from scraper_lib import PORTAL_DOMAINS, is_portal_link  # noqa: E402

EVENTS = REPO / "events.json"
OVERRIDES = REPO / "scripts" / "manual_overrides.json"
LINKS = REPO / "scripts" / "links_geprueft.json"
UA = "EnduranceEventsBot/1.0 (+https://github.com/antdon930/enduranceevents)"
HEUTE = time.strftime("%Y-%m-%d")

# Hosts, deren Link nie die Veranstalterseite ist, die aber selbst (noch)
# nicht in PORTAL_DOMAINS stehen: soziale Netze und Kartendienste.
KEIN_VERANSTALTER = (
    "facebook.com", "fb.me", "fb.com", "instagram.com", "youtube.com", "youtu.be",
    "twitter.com", "x.com", "tiktok.com", "whatsapp.com", "linkedin.com",
    "google.com", "goo.gl", "maps.app.goo.gl", "apple.com", "paypal.com",
    "strava.com", "komoot.com", "komoot.de", "outdooractive.com", "flow.polar.com",
    "wikipedia.org", "openstreetmap.org", "t.me", "spotify.com", "amazon.de",
    # Zeitnahme- und Meldedienste, die (noch) nicht in PORTAL_DOMAINS
    # stehen, und Seiten, die beim ersten Lauf als Fehlgriff auffielen
    # (Ergebnisdienst, Meldeportal, Shop, Werbeagentur).
    "live-results.de", "ddmess.de", "sportstiming.se", "sportstiming.dk", "maximalpuls.com",
    "coderesearch.com", "yumpu.com", "out.ac", "stay22.com", "excentos.com",
)
# Seiten, die nie die Veranstalterseite sind, egal auf welchem Host.
KEIN_VERANSTALTER_PFAD = re.compile(r"datenschutz|privacy|impressum|imprint|/agb\b|cookie", re.I)
# Wörter, die in fast jedem Veranstaltungsnamen stehen und deshalb nichts
# beweisen.
ALLGEMEIN = {
    "lauf", "laeufe", "laufe", "marathon", "halbmarathon", "volkslauf", "stadtlauf",
    "strassenlauf", "crosslauf", "waldlauf", "trail", "trailrun", "ultra", "ultralauf",
    "silvesterlauf", "herbstlauf", "fruehlingslauf", "winterlauf", "berglauf", "citylauf",
    "firmenlauf", "nachtlauf", "abendlauf", "sparkassen", "sparkasse", "stadtwerke",
    "volksbank", "raiffeisen", "international", "internationaler", "meisterschaft",
    "meisterschaften", "offene", "offener", "landesmeisterschaft", "kreismeisterschaft",
    "deutsche", "bayerische", "sport", "sportfest", "sportverein", "turnverein",
    "laufserie", "serie", "cup", "challenge", "festival", "event", "events", "run", "runs",
    "running", "walking", "nordic", "staffel", "staffellauf", "staffelmarathon", "triathlon",
    "duathlon", "swimrun", "backyard", "jedermann", "jedermannlauf", "benefizlauf",
    "charity", "spendenlauf", "kinderlauf", "schuelerlauf", "adventslauf", "nikolauslauf",
    "weihnachtslauf", "osterlauf", "sommerlauf", "seelauf", "panoramalauf", "gedaechtnislauf",
    "winterlaufserie", "crosslaufserie", "wintercross", "herbstcross", "cross", "martin",
    "martins", "leben", "bruch", "family", "night", "gegen", "krebs", "ultramarathon",
    "stadion", "rahmen", "sankt", "lauftag", "laufen", "lauftreff", "volks", "power",
}


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower().replace("ß", "ss")).encode("ascii", "ignore").decode()


def namens_woerter(name: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{5,}", norm(name)) if w not in ALLGEMEIN]


def host_von(url: str) -> str:
    try:
        h = urlparse(url if "://" in url else "http://" + url).netloc.lower()
    except ValueError:
        return ""
    return h.split("@")[-1].split(":")[0].removeprefix("www.")


def ist_fremd(host: str, liste=KEIN_VERANSTALTER) -> bool:
    return any(host == d or host.endswith("." + d) for d in liste)


def kein_veranstalter(url: str) -> bool:
    h = host_von(url)
    if not h or "." not in h or ist_fremd(h) or is_portal_link(url):
        return True
    if h.endswith(".google") or h.startswith("shop."):
        return True
    return bool(KEIN_VERANSTALTER_PFAD.search(urlparse(url).path or ""))


# Hosts, die dieses Projekt nie abruft - ironman.com verbietet ClaudeBot in
# der robots.txt, und der Ironman-Scraper bricht deshalb ab (CLAUDE.md,
# „Quellen"). Diese Linie gilt auch für die Linkprüfung.
NIE_ABRUFEN = ("ironman.com",)


class Abrufer:
    """GET mit Pause je Host und robots.txt-Prüfung; merkt sich Antworten."""

    def __init__(self, pause: float = 2.0):
        self.pause = pause
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.zuletzt: dict[str, float] = {}
        self.robots: dict[str, RobotFileParser | None] = {}
        self.cache: dict[str, tuple[int | None, str]] = {}

    def erlaubt(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        if host not in self.robots:
            rp = RobotFileParser()
            try:
                r = self.session.get(f"{urlparse(url).scheme}://{host}/robots.txt", timeout=15)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self.robots[host] = rp
        rp = self.robots[host]
        try:
            return rp.can_fetch(UA, url) and rp.can_fetch("*", url)
        except Exception:
            return True

    def hole(self, url: str) -> tuple[int | None, str]:
        if url in self.cache:
            return self.cache[url]
        if ist_fremd(host_von(url), NIE_ABRUFEN) or not self.erlaubt(url):
            self.cache[url] = (None, "robots")
            return self.cache[url]
        host = urlparse(url).netloc.lower()
        warte = self.zuletzt.get(host, 0) + self.pause - time.time()
        if warte > 0:
            time.sleep(warte)
        try:
            # Harte Zeitgrenze über den ganzen Abruf: `timeout` gilt in
            # requests nur zwischen zwei Datenpaketen - ein Server, der
            # tröpfelt, hielt den ersten Lauf 20 Minuten fest. Deshalb
            # stückweise lesen, höchstens 30 s und 2 MB.
            r = self.session.get(url, timeout=(10, 15), allow_redirects=True, stream=True)
            start, teile, groesse = time.time(), [], 0
            for chunk in r.iter_content(chunk_size=65536):
                teile.append(chunk)
                groesse += len(chunk)
                if time.time() - start > 30 or groesse > 2_000_000:
                    break
            r.close()
            r._content = b"".join(teile)
            ergebnis = (r.status_code, r.text if r.status_code < 400 else "")
        except requests.RequestException as exc:
            ergebnis = (None, f"fehler:{type(exc).__name__}")
        self.zuletzt[host] = time.time()
        self.cache[url] = ergebnis
        return ergebnis


def text_von(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = html_mod.unescape(re.sub(r"<[^>]+>", " ", t))
    return norm(re.sub(r"\s+", " ", t))


def nennt_den_lauf(html: str, ziel: str, namen: list[str], daten: list[str],
                   orte: list[str] = ()) -> list[str]:
    """Die Wörter, an denen die Zielseite den Lauf erkennen lässt.

    Ein Ortsname (der `standort` der Zeile) zählt nur im HOSTNAMEN: Im
    Text steht er auf jeder Sponsoren-, Shop- und Vereinsseite der
    Stadt - „Leipzig Run" fand so einen Laufshop. Treffer im Hostnamen
    stehen vorn, `sammeln()` bevorzugt sie bei mehreren Kandidaten."""
    txt = text_von(html)
    hostn = norm(host_von(ziel))
    ortswoerter = {w for o in orte for w in re.findall(r"[a-z]{4,}", norm(o))}
    treffer = []
    for nm in namen:
        for w in namens_woerter(nm):
            if w in hostn:
                treffer.insert(0, "host:" + w)
                break
            if w in txt and w not in ortswoerter:
                treffer.append(w)
                break
    for d in daten:
        tag, monat, jahr = int(d[8:10]), int(d[5:7]), d[:4]
        if re.search(r"\b%02d\.\s?%02d\.\s?%s\b" % (tag, monat, jahr), txt) or \
           re.search(r"\b%d\.\s?%d\.\s?%s\b" % (tag, monat, jahr), txt):
            treffer.append("datum")
            break
    return treffer


def organizer_url_aus_jsonld(html: str) -> str | None:
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            daten = json.loads(block.strip())
        except json.JSONDecodeError:
            m = re.search(r'"organizer"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]*)"', block)
            return m.group(1).strip() if m else None
        eintraege = daten if isinstance(daten, list) else [daten]
        for d in eintraege:
            org = d.get("organizer") if isinstance(d, dict) else None
            if isinstance(org, dict) and org.get("url"):
                return str(org["url"]).strip()
    return None


def externe_links(html: str, seite: str) -> list[str]:
    seiten_host = host_von(seite)
    gefunden: list[str] = []
    for href in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
        href = html_mod.unescape(href.strip())
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolut = urljoin(seite, href)
        if not absolut.startswith(("http://", "https://")):
            continue
        h = host_von(absolut)
        if not h or h == seiten_host or h.endswith("." + seiten_host) or seiten_host.endswith("." + h):
            continue
        if kein_veranstalter(absolut):
            continue
        if re.search(r"\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?)(\?|$)", absolut, re.I):
            continue
        if absolut not in gefunden:
            gefunden.append(absolut)
    return gefunden


def kandidaten_url_normalisieren(u: str) -> str | None:
    u = u.strip()
    if not u:
        return None
    if not re.match(r"https?://", u, re.I):
        if "." not in u or " " in u:
            return None
        u = "https://" + u
    if kein_veranstalter(u):
        return None
    return u


def sammeln(args) -> None:
    events = json.loads(EVENTS.read_text())
    links = json.loads(LINKS.read_text())
    abrufer = Abrufer(pause=args.pause)
    # Veranstaltungen (Name|Datum) mit Portal-/Zeitnehmer-Link, noch ohne Linkprüfung
    gruppen: "OrderedDict[str, dict]" = OrderedDict()
    for e in sorted(events, key=lambda e: (e.get("datum_start") or "", e.get("name") or "")):
        url = e.get("veranstalter_url") or ""
        if not is_portal_link(url):
            continue
        schluessel = f"{e.get('name')}|{e.get('datum_start')}"
        if schluessel in links and not args.auch_geprueft:
            continue
        if args.nur_host and host_von(url) != args.nur_host:
            continue
        g = gruppen.setdefault(schluessel, {"name": e.get("name"), "datum": e.get("datum_start"),
                                            "urls": [], "namen": set(), "daten": set(), "orte": set()})
        if url not in g["urls"]:
            g["urls"].append(url)
        g["namen"].add(e.get("name") or "")
        g["daten"].add(e.get("datum_start") or "")
        g["orte"].add(e.get("standort") or "")
    if args.max:
        gruppen = OrderedDict(list(gruppen.items())[: args.max])
    print(f"{len(gruppen)} Veranstaltungen mit Portal-/Zeitnehmer-Link ohne Linkprüfung")

    bericht: "OrderedDict[str, dict]" = OrderedDict()
    if args.fortsetzen and Path(args.bericht).exists():
        bericht = json.loads(Path(args.bericht).read_text(), object_pairs_hook=OrderedDict)
        print(f"  setze fort: {len(bericht)} Veranstaltungen schon im Bericht")
    for i, (schluessel, g) in enumerate(gruppen.items(), 1):
        if schluessel in bericht:
            continue
        namen, daten = sorted(g["namen"]), sorted(g["daten"])
        eintrag = {"name": g["name"], "datum": g["datum"], "alt": g["urls"][0],
                   "kandidaten": [], "ergebnis": "unklar", "ziel": None, "treffer": [], "notiz": ""}
        kandidaten: list[str] = []
        for url in g["urls"]:
            host = host_von(url)
            if host == "my.raceresult.com":
                m = re.search(r"raceresult\.com/(\d+)", url)
                if not m:
                    continue
                status, body = abrufer.hole(f"https://my.raceresult.com/{m.group(1)}/contact")
                if status != 200:
                    eintrag["notiz"] = f"Kontaktseite nicht ladbar ({status or body})"
                    continue
                org = organizer_url_aus_jsonld(body)
                if not org or "Geben Sie hier" in org:
                    eintrag["notiz"] = "Kontaktseite: Organizer-URL leer oder Platzhalter"
                    continue
                k = kandidaten_url_normalisieren(org)
                if not k:
                    eintrag["notiz"] = f"Kontaktseite nennt {org} - Portal/Anmeldung/soziales Netz"
                    continue
                kandidaten.append(k)
            else:
                status, body = abrufer.hole(url)
                if status != 200:
                    eintrag["notiz"] = f"Seite nicht ladbar ({status or body})"
                    continue
                kandidaten.extend(externe_links(body, url))
        # Kandidaten einzeln prüfen - höchstens acht, sonst ist die Seite ein Linkverzeichnis
        gesehen = set()
        for k in kandidaten[:8]:
            hk = host_von(k)
            if hk in gesehen:
                continue
            gesehen.add(hk)
            status, body = abrufer.hole(k)
            if status != 200:
                eintrag["kandidaten"].append({"url": k, "status": status or body, "treffer": []})
                continue
            treffer = nennt_den_lauf(body, k, namen, daten, sorted(g["orte"]))
            eintrag["kandidaten"].append({"url": k, "status": status, "treffer": treffer})
        passend = [c for c in eintrag["kandidaten"] if c["treffer"]]
        # Nennt genau EIN Kandidat den Lauf schon im Hostnamen, ist das
        # die Veranstalterseite - auch wenn andere ihn im Text erwähnen.
        im_host = [c for c in passend if any(w.startswith("host:") for w in c["treffer"])]
        if len(im_host) == 1:
            passend = im_host
        if len(passend) == 1 or (passend and len({host_von(c["url"]) for c in passend}) == 1):
            eintrag["ergebnis"] = "gefunden"
            eintrag["ziel"] = passend[0]["url"]
            eintrag["treffer"] = passend[0]["treffer"]
        elif len(passend) > 1:
            eintrag["ergebnis"] = "mehrdeutig"
        bericht[schluessel] = eintrag
        if i % 10 == 0 or i == len(gruppen):
            print(f"  … {i}/{len(gruppen)}: {sum(1 for b in bericht.values() if b['ergebnis'] == 'gefunden')} gefunden")
            Path(args.bericht).write_text(json.dumps(bericht, ensure_ascii=False, indent=1))
    Path(args.bericht).write_text(json.dumps(bericht, ensure_ascii=False, indent=1))
    from collections import Counter
    print("fertig:", dict(Counter(b["ergebnis"] for b in bericht.values())))


def anwenden(args) -> None:
    bericht = json.loads(Path(args.bericht).read_text())
    overrides = json.loads(OVERRIDES.read_text(), object_pairs_hook=OrderedDict)
    links = json.loads(LINKS.read_text(), object_pairs_hook=OrderedDict)
    neu_ov = neu_ok = neu_unklar = 0
    for schluessel, b in bericht.items():
        if schluessel in links and not args.auch_geprueft:
            continue
        alt_host = host_von(b["alt"])
        if b["ergebnis"] == "gefunden":
            eintrag = overrides.get(schluessel, OrderedDict())
            note = (f"Veranstalterseite statt {alt_host}: {b['ziel']} - "
                    + ("von der raceresult-Kontaktseite (Organizer-URL)" if alt_host == "my.raceresult.com"
                       else f"auf der {alt_host}-Seite verlinkt")
                    + f", Zielseite nennt den Lauf ({', '.join(b['treffer'][:2])}). Linkprüfung {HEUTE}.")
            eintrag["veranstalter_url"] = b["ziel"]
            eintrag["_note"] = (eintrag["_note"] + " | " + note) if eintrag.get("_note") else note
            overrides[schluessel] = eintrag
            links[schluessel] = OrderedDict([("am", HEUTE), ("ergebnis", "korrigiert"),
                                             ("quelle", host_von(b["ziel"])), ("alt", b["alt"]), ("notiz", note)])
            neu_ov += 1
        elif b["ergebnis"] == "mehrdeutig":
            kand = ", ".join(c["url"] for c in b["kandidaten"] if c["treffer"])
            links[schluessel] = OrderedDict([("am", HEUTE), ("ergebnis", "unklar"), ("quelle", alt_host), ("alt", b["alt"]),
                                             ("notiz", f"Mehrere Seiten nennen den Lauf, keine eindeutig: {kand} - {alt_host} bleibt.")])
            neu_unklar += 1
        else:
            kand = [c["url"] for c in b["kandidaten"]]
            if b["notiz"] and ("leer" in b["notiz"] or "Platzhalter" in b["notiz"] or "Portal" in b["notiz"]):
                erg, notiz = "link_ok", b["notiz"] + f" - {alt_host} bleibt."
                neu_ok += 1
            else:
                erg = "unklar"
                notiz = (b["notiz"] or ("Keine verlinkte Seite nennt den Lauf" + (f" (geprüft: {', '.join(kand[:4])})" if kand else " (keine externen Links)"))) + f" - {alt_host} bleibt."
                neu_unklar += 1
            links[schluessel] = OrderedDict([("am", HEUTE), ("ergebnis", erg), ("quelle", alt_host), ("alt", b["alt"]), ("notiz", notiz)])
    OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n")
    LINKS.write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n")
    print(f"angewendet: {neu_ov} Overrides, {neu_ok} link_ok, {neu_unklar} unklar")


def pruefen(args) -> None:
    """Eigene Veranstalterseiten (kein Portal) abrufen: erreichbar, und
    nennt die Seite den Lauf? Schreibt nur einen Bericht; `anwenden`
    kennt ihn nicht - tote Links brauchen eine Websuche, keine Regel."""
    events = json.loads(EVENTS.read_text())
    links = json.loads(LINKS.read_text())
    abrufer = Abrufer(pause=args.pause)
    gruppen: "OrderedDict[str, dict]" = OrderedDict()
    for e in sorted(events, key=lambda e: (e.get("datum_start") or "", e.get("name") or "")):
        url = e.get("veranstalter_url") or ""
        if not url or is_portal_link(url) or kein_veranstalter(url):
            continue
        schluessel = f"{e.get('name')}|{e.get('datum_start')}"
        if schluessel in links and not args.auch_geprueft:
            continue
        g = gruppen.setdefault(schluessel, {"name": e.get("name"), "datum": e.get("datum_start"),
                                            "url": url, "namen": set(), "daten": set(), "orte": set()})
        g["namen"].add(e.get("name") or "")
        g["daten"].add(e.get("datum_start") or "")
        g["orte"].add(e.get("standort") or "")
    if args.max:
        gruppen = OrderedDict(list(gruppen.items())[: args.max])
    print(f"{len(gruppen)} Veranstaltungen mit eigener Seite ohne Linkprüfung")
    bericht: "OrderedDict[str, dict]" = OrderedDict()
    for i, (schluessel, g) in enumerate(gruppen.items(), 1):
        status, body = abrufer.hole(g["url"])
        if status == 200:
            treffer = nennt_den_lauf(body, g["url"], sorted(g["namen"]), sorted(g["daten"]), sorted(g["orte"]))
            erg = "nennt" if treffer else ("leer" if len(text_von(body)) < 200 else "nennt_nicht")
        elif status is None:
            erg, treffer = ("robots" if body == "robots" else "fehler"), []
        else:
            erg, treffer = ("tot" if status in (404, 410) else f"http{status}"), []
        bericht[schluessel] = {"name": g["name"], "datum": g["datum"], "url": g["url"],
                               "status": status if status is not None else body, "ergebnis": erg, "treffer": treffer}
        if i % 25 == 0 or i == len(gruppen):
            from collections import Counter
            print(f"  … {i}/{len(gruppen)}: {dict(Counter(b['ergebnis'] for b in bericht.values()))}")
            Path(args.bericht).write_text(json.dumps(bericht, ensure_ascii=False, indent=1))
    Path(args.bericht).write_text(json.dumps(bericht, ensure_ascii=False, indent=1))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sammeln", help="abrufen und prüfen, Bericht schreiben")
    s.add_argument("--bericht", required=True)
    s.add_argument("--pause", type=float, default=2.0, help="Sekunden zwischen zwei Abrufen desselben Hosts")
    s.add_argument("--max", type=int, default=0, help="nur die ersten N Veranstaltungen")
    s.add_argument("--nur-host", default=None, help="nur Links dieses Hosts (z. B. my.raceresult.com)")
    s.add_argument("--auch-geprueft", action="store_true", help="auch Veranstaltungen, die schon in links_geprueft.json stehen")
    s.add_argument("--fortsetzen", action="store_true", help="vorhandenen Bericht weiterführen statt neu beginnen")
    s.set_defaults(fn=sammeln)
    q = sub.add_parser("pruefen", help="eigene Veranstalterseiten abrufen (tot? nennt den Lauf?), nur Bericht")
    q.add_argument("--bericht", required=True)
    q.add_argument("--pause", type=float, default=1.0)
    q.add_argument("--max", type=int, default=0)
    q.add_argument("--auch-geprueft", action="store_true")
    q.set_defaults(fn=pruefen)
    a = sub.add_parser("anwenden", help="Bericht in Overrides und Linkprotokoll übernehmen")
    a.add_argument("--bericht", required=True)
    a.add_argument("--auch-geprueft", action="store_true")
    a.set_defaults(fn=anwenden)
    args = p.parse_args()
    args.fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
