#!/usr/bin/env python3
"""Neue Instagram-Beiträge der Clubs abholen (Business Discovery).

Vom Nutzer am 26.10.2026 gewünscht: „Wir müssen unbedingt die Sachen auf
Instagram auch automatisch auslesen! Ich hab die Zeit nicht, dir immer
Screenshots zu schicken." Viele Run Clubs stellen ihre Termine nur als
Monatsplan-Bild oder Beitragstext auf Instagram.

Wie: Metas offizielle Schnittstelle „Business Discovery“ liest die
ÖFFENTLICHEN Beiträge anderer Business- und Creator-Konten über das eigene
Profi-Konto (ausdauermaschine). Private Konten liefern nichts, ebenso
altersbeschränkte. Dafür braucht es die Anmeldung über Facebook (Seite mit
verknüpftem Instagram-Konto) – eingerichtet mit
scripts/instagram_fb_einrichten.sh; der Schlüssel liegt im Google-Tresor
(Secret „instagram-fb-token“), nie im Repository.

Dieses Skript wertet NICHTS aus. Es schreibt je Club die Beiträge der
letzten Tage (Text, Datum, Link, Bilder) in einen Ordner; die wöchentliche
Claude-Aufgabe liest Texte und Bilder und trägt Termine in clubs.json ein –
dieselbe Prüfung wie bei einem Bildschirmfoto des Betreibers.

    python3 scripts/clubs_instagram.py --aus ausgabe/ [--tage 21] [--max 300]

Umgebung: IG_FB_TOKEN (Seiten- oder Nutzerschlüssel mit instagram_basic,
instagram_manage_insights, pages_read_engagement), IG_FB_USER_ID (die
Instagram-Konto-Id von ausdauermaschine, nicht der Name), optional
IG_GRAPH_VERSION (Vorgabe v25.0).

Ausgabe: <aus>/bericht.json und <aus>/bilder/<handle>/<beitrag>-<n>.jpg.
Höflich: höchstens eine Anfrage alle --pause Sekunden, bei Rate-Limit-
Meldung (Code 4/17/32/613 oder Auslastung > 80 %) Pause, dann weiter.
Der Schlüssel erscheint nie im Log.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CLUBS_JSON = WURZEL / "clubs.json"
VORGABE_VERSION = "v25.0"
FELDER = ("username,name,biography,website,"
          "media.limit({n}){{caption,timestamp,media_type,media_url,permalink,"
          "children{{media_type,media_url}}}}")
RATE_CODES = {4, 17, 32, 613}
MAX_BILD = 4 * 1024 * 1024


def handle_aus(url: str | None) -> str | None:
    """'https://www.instagram.com/cozy.runclub/' -> 'cozy.runclub'."""
    m = re.match(r"https://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?", url or "")
    if not m or m[1].lower() in ("p", "reel", "explore", "stories"):
        return None
    return m[1].lower()


def handles(clubs: list[dict]) -> dict[str, list[str]]:
    """Handle -> ids der Clubs, die ihn tragen (ein Profil, mehrere Treffs)."""
    aus: dict[str, list[str]] = {}
    for c in clubs:
        h = handle_aus(c.get("instagram"))
        if h:
            aus.setdefault(h, []).append(c["id"])
    return aus


def maskiere(geheim: str | None) -> None:
    if geheim and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{geheim}")


def neu_genug(zeit: str | None, grenze: dt.datetime) -> bool:
    if not zeit:
        return False
    try:
        t = dt.datetime.strptime(zeit, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return False
    return t >= grenze


def auslastung(antwort) -> int:
    """Höchster Prozentwert aus den Nutzungs-Kopfzeilen (0, wenn keine)."""
    hoechst = 0
    for kopf in ("x-app-usage", "x-business-use-case-usage"):
        roh = antwort.headers.get(kopf)
        if not roh:
            continue
        for z in re.findall(r'"(?:call_count|total_cputime|total_time)"\s*:\s*(\d+)', roh):
            hoechst = max(hoechst, int(z))
    return hoechst


def hole(session, version: str, ig_id: str, token: str, handle: str, n: int):
    url = f"https://graph.facebook.com/{version}/{ig_id}"
    params = {"fields": f"business_discovery.username({handle}){{{FELDER.format(n=n)}}}"}
    try:
        r = session.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=40)
    except Exception as ex:  # requests-Fehlertexte enthalten die Adresse
        return None, {"fehler": f"Netzfehler {type(ex).__name__}"}, 0
    last = auslastung(r)
    try:
        daten = r.json()
    except ValueError:
        return None, {"fehler": f"HTTP {r.status_code} ohne JSON"}, last
    if "error" in daten:
        e = daten["error"]
        return None, {"fehler": e.get("message", "")[:200], "code": e.get("code"),
                      "subcode": e.get("error_subcode")}, last
    return daten.get("business_discovery"), None, last


def lade_bild(session, url: str, ziel: Path) -> bool:
    try:
        r = session.get(url, timeout=40, stream=True)
        if r.status_code != 200:
            return False
        daten = b""
        for stueck in r.iter_content(65536):
            daten += stueck
            if len(daten) > MAX_BILD:
                return False
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(daten)
        return True
    except Exception:
        return False


def lauf(args, session=None, schlafen=time.sleep, jetzt: dt.datetime | None = None) -> dict:
    import requests  # erst hier: der Regressionstest läuft mit einer Attrappe

    token = os.environ.get("IG_FB_TOKEN", "").strip()
    ig_id = os.environ.get("IG_FB_USER_ID", "").strip()
    version = (os.environ.get("IG_GRAPH_VERSION") or VORGABE_VERSION).strip()
    if not token or not ig_id:
        raise SystemExit("IG_FB_TOKEN und IG_FB_USER_ID fehlen (scripts/instagram_fb_einrichten.sh)")
    maskiere(token)
    s = session or requests.Session()
    s.headers["User-Agent"] = "endurance-events.de clubs-instagram"
    jetzt = jetzt or dt.datetime.now(dt.timezone.utc)
    grenze = jetzt - dt.timedelta(days=args.tage)
    clubs = json.loads(Path(args.clubs).read_text(encoding="utf-8"))
    liste = handles(clubs)
    aus = Path(args.aus)
    aus.mkdir(parents=True, exist_ok=True)
    bericht = {"abgerufen": jetzt.isoformat(timespec="seconds"), "tage": args.tage,
               "profile": {}, "fehler": {}}
    for nr, (handle, ids) in enumerate(sorted(liste.items())):
        if nr >= args.max:
            bericht["fehler"][handle] = {"fehler": "nicht abgerufen (--max erreicht)"}
            continue
        if nr:
            schlafen(args.pause)
        bd, fehler, last = hole(s, version, ig_id, token, handle, args.beitraege)
        if fehler and fehler.get("code") in RATE_CODES:
            print(f"Rate-Limit bei {handle} – 30 Minuten Pause", flush=True)
            schlafen(1800)
            bd, fehler, last = hole(s, version, ig_id, token, handle, args.beitraege)
        if last > 80:
            print(f"Auslastung {last} % – 10 Minuten Pause", flush=True)
            schlafen(600)
        if fehler:
            bericht["fehler"][handle] = dict(fehler, clubs=ids)
            continue
        beitraege = []
        for m in (bd.get("media") or {}).get("data", []):
            if not neu_genug(m.get("timestamp"), grenze):
                continue
            bilder = []
            quellen = [m] + [k for k in (m.get("children") or {}).get("data", [])]
            for i, q in enumerate(quellen):
                if q.get("media_type") not in ("IMAGE", "CAROUSEL_ALBUM") or not q.get("media_url"):
                    continue
                if q is m and m.get("media_type") == "CAROUSEL_ALBUM":
                    continue  # das Album selbst hat kein eigenes Bild
                ziel = aus / "bilder" / handle / f"{m.get('id', 'x')}-{i}.jpg"
                if lade_bild(s, q["media_url"], ziel):
                    bilder.append(str(ziel.relative_to(aus)))
            beitraege.append({"zeit": m.get("timestamp"), "text": m.get("caption") or "",
                              "link": m.get("permalink"), "art": m.get("media_type"), "bilder": bilder})
        bericht["profile"][handle] = {"clubs": ids, "name": bd.get("name"), "bio": bd.get("biography"),
                                      "webseite": bd.get("website"), "beitraege": beitraege}
    (aus / "bericht.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    mit = sum(1 for p in bericht["profile"].values() if p["beitraege"])
    print(f"{len(bericht['profile'])} Profile gelesen, {mit} mit neuen Beiträgen, "
          f"{len(bericht['fehler'])} ohne Ergebnis", flush=True)
    return bericht


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--aus", required=True)
    ap.add_argument("--clubs", default=str(CLUBS_JSON))
    ap.add_argument("--tage", type=int, default=21)
    ap.add_argument("--beitraege", type=int, default=8, help="je Profil höchstens so viele jüngste Beiträge")
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--pause", type=float, default=15.0)
    lauf(ap.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())
