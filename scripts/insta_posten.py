#!/usr/bin/env python3
"""
scripts/insta_posten.py
=======================

Lädt ein fertiges Reel (reel.mp4 + Caption) über die Instagram-API hoch
und veröffentlicht es. Ohne Zugangsdaten tut es nichts außer es zu sagen
- der Workflow rendert dann nur und legt das Video als Artefakt ab.

Der Weg (Meta-Doku „Content Publishing“, „Resumable Uploads“):

  1. POST /{ig-user-id}/media  media_type=REELS, upload_type=resumable,
     caption, share_to_feed, thumb_offset  → Container-Id + Upload-Adresse
  2. POST rupload.facebook.com/ig-api-upload/{version}/{container}
     mit den Bytes (Kopfzeilen offset, file_size)  → kein Hosting nötig
  3. GET  /{container}?fields=status_code  bis FINISHED (Instagram
     verarbeitet das Video, meist 20-90 s)
  4. POST /{ig-user-id}/media_publish  creation_id={container}
  5. GET  /{media-id}?fields=permalink  → die Adresse des Reels

Zugangsdaten (GitHub-Secrets, Einrichtung im README „Instagram"):

  IG_USER_ID        die Instagram-Business-Konto-Id (nicht der Name)
  IG_ACCESS_TOKEN   Token mit instagram_basic + instagram_content_publish;
                    am besten ein Systemnutzer-Token aus dem Meta Business
                    Manager - das läuft nicht ab.
  IG_API_HOST       optional, Vorgabe graph.facebook.com (der Upload in
                    Schritt 2 ist laut Meta nur mit „Facebook Login for
                    Business" freigegeben)
  IG_API_VERSION    optional, Vorgabe v23.0

Das Veröffentlichungslimit (100 API-Beiträge je 24 h) ist für einen
Beitrag am Tag ohne Belang; es wird trotzdem abgefragt und gemeldet.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

VORGABE_HOST = "graph.facebook.com"
VORGABE_VERSION = "v23.0"
WARTEN_MAX_S = 600


class PostenFehler(RuntimeError):
    pass


def zugang() -> dict | None:
    uid, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    if not uid or not token:
        return None
    return {"uid": uid.strip(), "token": token.strip(),
            "host": (os.environ.get("IG_API_HOST") or VORGABE_HOST).strip(),
            "version": (os.environ.get("IG_API_VERSION") or VORGABE_VERSION).strip()}


def _antwort(r: requests.Response, schritt: str) -> dict:
    try:
        daten = r.json()
    except ValueError:
        daten = {"roh": r.text[:300]}
    if r.status_code >= 400 or "error" in daten:
        fehler = daten.get("error", daten)
        raise PostenFehler(f"{schritt}: HTTP {r.status_code} – {json.dumps(fehler, ensure_ascii=False)[:500]}")
    return daten


def poste_reel(video: Path, caption: str, thumb_offset_ms: int | None = None,
               z: dict | None = None, session: requests.Session | None = None,
               warten=time.sleep) -> dict:
    z = z or zugang()
    if not z:
        raise PostenFehler("IG_USER_ID / IG_ACCESS_TOKEN fehlen")
    s = session or requests.Session()
    basis = f"https://{z['host']}/{z['version']}"
    auth = {"Authorization": f"OAuth {z['token']}"}

    try:
        limit = s.get(f"{basis}/{z['uid']}/content_publishing_limit", headers=auth,
                      params={"fields": "quota_usage,config"}, timeout=30).json()
        print(f"  Veröffentlichungslimit: {json.dumps(limit.get('data', limit), ensure_ascii=False)[:200]}")
    except Exception:                                        # noqa: BLE001 - nur Auskunft
        pass

    felder = {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
              "share_to_feed": "true"}
    if thumb_offset_ms is not None:
        felder["thumb_offset"] = str(int(thumb_offset_ms))
    container = _antwort(s.post(f"{basis}/{z['uid']}/media", headers=auth, data=felder, timeout=60),
                         "Container anlegen")
    cid = container["id"]
    uri = container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{z['version']}/{cid}"
    print(f"  Container {cid}")

    daten = video.read_bytes()
    _antwort(s.post(uri, headers={**auth, "offset": "0", "file_size": str(len(daten))},
                    data=daten, timeout=600), "Video hochladen")
    print(f"  hochgeladen ({len(daten) / 1e6:.1f} MB), Instagram verarbeitet …")

    gewartet = 0
    while True:
        st = _antwort(s.get(f"{basis}/{cid}", headers=auth,
                            params={"fields": "status_code,status"}, timeout=30), "Status")
        code = st.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            break
        if code in ("ERROR", "EXPIRED"):
            raise PostenFehler(f"Verarbeitung: {code} – {st.get('status')}")
        if gewartet >= WARTEN_MAX_S:
            raise PostenFehler(f"Verarbeitung dauert über {WARTEN_MAX_S} s (zuletzt {code})")
        warten(10)
        gewartet += 10

    veroeff = _antwort(s.post(f"{basis}/{z['uid']}/media_publish", headers=auth,
                              data={"creation_id": cid}, timeout=60), "Veröffentlichen")
    mid = veroeff["id"]
    link = None
    try:
        link = _antwort(s.get(f"{basis}/{mid}", headers=auth, params={"fields": "permalink"}, timeout=30),
                        "Permalink").get("permalink")
    except PostenFehler:
        pass
    return {"media_id": mid, "container_id": cid, "permalink": link}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ein gerendertes Reel auf Instagram veröffentlichen.")
    ap.add_argument("ordner", help="Ordner mit reel.mp4, caption.txt, beitrag.json")
    a = ap.parse_args()
    ordner = Path(a.ordner)
    meta = json.loads((ordner / "beitrag.json").read_text(encoding="utf-8"))
    if not zugang():
        print("IG_USER_ID / IG_ACCESS_TOKEN nicht gesetzt – nichts veröffentlicht.")
        sys.exit(0)
    erg = poste_reel(ordner / "reel.mp4", (ordner / "caption.txt").read_text(encoding="utf-8"),
                     meta.get("video", {}).get("thumb_offset_ms"))
    print(json.dumps(erg, ensure_ascii=False))
