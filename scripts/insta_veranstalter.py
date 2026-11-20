#!/usr/bin/env python3
"""
scripts/insta_veranstalter.py
=============================

Findet den Instagram-Namen des Veranstalters eines Rennens - auf dessen
EIGENER Seite (veranstalter_url in events.json), und nur dort. Damit
nennt die Caption eines Reels den Veranstalter mit @-Erwähnung: Er wird
benachrichtigt und teilt den Beitrag oft in seiner Story, weil er Werbung
für sein Rennen ist - der stärkste Hebel für einen neuen Account (vom
Nutzer am 16.10.2026 freigegeben, Content-Strategie Punkt 3).

Die Regeln, alle wie bei der Linkprüfung (veranstalter_links.py):

  * Nur die Veranstalterseite selbst, nie ein Kalenderportal oder ein
    Zeitnehmer (PORTAL_DOMAINS aus scraper_lib.py - gelesen aus dem
    Quelltext, weil scraper_lib bs4 braucht und der Instagram-Workflow es
    nicht installiert).
  * robots.txt wird beachtet, je Host höchstens ein Abruf alle 2 s, 15 s
    Frist, höchstens 2 MB.
  * Gesucht werden Links auf instagram.com/<name>. Steht genau EIN Name
    auf der Seite, gilt er. Stehen mehrere da (Sponsoren, Partner), gilt
    nur der, dessen Name ein Wort des Rennens oder des Hosts trägt - sonst
    keiner. Geraten wird nie (Datenregel 2).
  * Nennt die Unterseite keinen, wird einmal die Startseite des Hosts
    gelesen (der Instagram-Link steht meist im Fuß jeder Seite).
  * Ergebnisse (auch „keiner") liegen 30 Tage im Cache
    marketing/instagram/.cache/instagram_namen.json - der Workflow hebt
    den Ordner mit actions/cache auf.

Die Erwähnung kommt NACH der Kennung des Beitrags in die Caption
(insta_lauf.py), wie die Namensnennung des Hintergrunds: Das Dashboard
zeigt die Caption ohne sie, die Freigabe bleibt gültig.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

WURZEL = Path(__file__).resolve().parent.parent
CACHE = WURZEL / "marketing" / "instagram" / ".cache" / "instagram_namen.json"
UA = "AusdauerMaschine/1.0 (+https://endurance-events.de)"
GUELTIG_TAGE = 30
MAX_BYTES = 2_000_000
PAUSE_S = 2.0

# Pfade auf instagram.com, die kein Konto sind.
KEIN_KONTO = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "direct", "about", "developer",
              "legal", "web", "sharer", "share", "embed", "oauth", "static", "instagram", "privacy", "help",
              "challenge", "emails", "session", "ar", "lite", "download", "press", "api", "graphql"}
EIGENES_KONTO = "ausdauermaschine"
INSTA_RE = re.compile(r"""(?:https?:)?//(?:www\.|m\.)?instagram\.com/([A-Za-z0-9._]{1,30})(?=[/"'?#\s<>]|$)""", re.I)


def portal_domains() -> tuple[str, ...]:
    """PORTAL_DOMAINS aus scraper_lib.py - ohne den Import (bs4)."""
    quelle = (WURZEL / "scripts" / "scraper_lib.py").read_text(encoding="utf-8")
    start = quelle.index("PORTAL_DOMAINS = (")
    ende = quelle.index("\n)", start)
    return tuple(re.findall(r'"([a-z0-9.-]+\.[a-z]{2,})"', quelle[start:ende]))


def ist_portal(url: str, domains: tuple[str, ...]) -> bool:
    host = urlparse(url if "://" in url else "http://" + url).netloc.lower().split("@")[-1].split(":")[0]
    return any(host == d or host.endswith("." + d) for d in domains)


def namen_im_html(html: str) -> list[str]:
    """Alle Instagram-Konten, auf die eine Seite verlinkt (klein, eindeutig)."""
    gesehen: list[str] = []
    for m in INSTA_RE.finditer(html or ""):
        name = m.group(1).lower().rstrip(".")
        if name in KEIN_KONTO or name == EIGENES_KONTO or not re.search(r"[a-z]", name):
            continue
        if name not in gesehen:
            gesehen.append(name)
    return gesehen


def _woerter(text: str) -> set[str]:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return {w for w in re.split(r"[^a-z0-9]+", text) if len(w) >= 4}


def waehle(namen: list[str], rennen: str, host: str) -> str | None:
    """Genau ein Name → der. Mehrere → nur der eine, der ein Wort des
    Rennens oder des Hosts trägt; sonst keiner."""
    if len(namen) == 1:
        return namen[0]
    woerter = _woerter(rennen) | _woerter(host.replace("www.", "").rsplit(".", 1)[0])
    passend = [n for n in namen if any(w in n.replace(".", "").replace("_", "") for w in woerter)]
    return passend[0] if len(passend) == 1 else None


class Abrufer:
    """Höflich lesen: robots.txt, Pause je Host, Frist, Größe."""

    def __init__(self, session=None, schlafen=time.sleep, uhr=time.monotonic):
        import requests
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": UA})
        self.robots: dict[str, RobotFileParser | None] = {}
        self.letzter: dict[str, float] = {}
        self.schlafen, self.uhr = schlafen, uhr

    def _darf(self, url: str) -> bool:
        teile = urlparse(url)
        basis = f"{teile.scheme}://{teile.netloc}"
        if basis not in self.robots:
            rp = RobotFileParser()
            try:
                r = self.s.get(basis + "/robots.txt", timeout=15)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except Exception:                                # noqa: BLE001
                rp.parse([])
            self.robots[basis] = rp
        return self.robots[basis].can_fetch(UA, url)

    def holen(self, url: str) -> str | None:
        if not self._darf(url):
            return None
        host = urlparse(url).netloc
        warten = PAUSE_S - (self.uhr() - self.letzter.get(host, -1e9))
        if warten > 0:
            self.schlafen(warten)
        self.letzter[host] = self.uhr()
        try:
            with self.s.get(url, timeout=15, stream=True) as r:
                if r.status_code != 200 or "html" not in r.headers.get("Content-Type", "html"):
                    return None
                daten = b""
                for block in r.iter_content(65536):
                    daten += block
                    if len(daten) > MAX_BYTES:
                        break
                return daten.decode(r.encoding or "utf-8", "replace")
        except Exception:                                    # noqa: BLE001 - kein Name ist kein Fehler
            return None


def lade_cache(pfad: Path = CACHE) -> dict:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichere_cache(cache: dict, pfad: Path = CACHE) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def name_fuer(url: str, rennen: str, abrufer: Abrufer, cache: dict, heute: dt.date,
              domains: tuple[str, ...]) -> str | None:
    if not url or not re.match(r"https?://", url) or ist_portal(url, domains):
        return None
    eintrag = cache.get(url)
    if eintrag:
        try:
            if (heute - dt.date.fromisoformat(eintrag["geprueft"])).days < GUELTIG_TAGE:
                return eintrag.get("name")
        except (KeyError, ValueError):
            pass
    host = urlparse(url).netloc
    name = None
    html = abrufer.holen(url)
    if html is not None:
        name = waehle(namen_im_html(html), rennen, host)
    if name is None:
        start = f"{urlparse(url).scheme}://{host}/"
        if start.rstrip("/") != url.rstrip("/"):
            html = abrufer.holen(start)
            if html is not None:
                name = waehle(namen_im_html(html), rennen, host)
    cache[url] = {"name": name, "geprueft": heute.isoformat()}
    return name


def rennen_im_beitrag(beitrag: dict) -> list[tuple[str, str]]:
    """(Name, Veranstalterseite) der Rennen, die Folien und Stories zeigen."""
    folien = list(beitrag.get("folien") or []) + [st.get("folie") or {} for st in beitrag.get("stories") or []]
    aus, gesehen = [], set()
    for f in folien:
        for ev in [f] + list(f.get("events") or []):
            name, url = ev.get("name") or ev.get("titel"), ev.get("url")
            if url and name and url not in gesehen:
                gesehen.add(url)
                aus.append((name, url))
    return aus


def erwaehnungen(beitrag: dict, abrufer: Abrufer | None = None, cache_pfad: Path = CACHE,
                 heute: dt.date | None = None, max_namen: int = 6) -> list[str]:
    """Die @-Namen der Veranstalter eines Beitrags (höchstens `max_namen`)."""
    heute = heute or dt.date.today()
    domains = portal_domains()
    cache = lade_cache(cache_pfad)
    abrufer = abrufer or Abrufer()
    namen: list[str] = []
    for rennen, url in rennen_im_beitrag(beitrag):
        n = name_fuer(url, rennen, abrufer, cache, heute, domains)
        if n and n not in namen:
            namen.append(n)
        if len(namen) >= max_namen:
            break
    speichere_cache(cache, cache_pfad)
    return namen


def caption_mit_erwaehnung(caption: str, namen: list[str]) -> str:
    """„Veranstalter: @a @b" vor die Hashtags."""
    if not namen:
        return caption
    zeile = ("📣 Veranstalter: " if len(namen) == 1 else "📣 Mit dabei: ") + " ".join("@" + n for n in namen)
    if zeile in caption:
        return caption
    teile = caption.rsplit("\n\n", 1)
    if len(teile) == 2 and teile[1].startswith("#"):
        return f"{teile[0]}\n\n{zeile}\n\n{teile[1]}"[:2200]
    return f"{caption}\n\n{zeile}"[:2200]


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Instagram-Namen der Veranstalter einer Seite finden.")
    ap.add_argument("url")
    ap.add_argument("--rennen", default="")
    a = ap.parse_args()
    n = name_fuer(a.url, a.rennen, Abrufer(), {}, dt.date.today(), portal_domains())
    print(n or "kein eindeutiger Instagram-Name")
    sys.exit(0)
