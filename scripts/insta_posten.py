#!/usr/bin/env python3
"""
scripts/insta_posten.py
=======================

Veröffentlicht ein fertiges Reel (reel.mp4 + Caption) über die
Instagram-API mit **Anmeldung über Instagram**. Den Weg hat der Nutzer am
16.10.2026 gewählt: keine Facebook-Seite, kein Business-Portfolio, keine
gemeinsame Kontenübersicht – „Ich würde meinen privaten Facebook Account
und die Webseite gerne trennen. Da soll nichts zusammenhängen." Ohne
Zugang tut das Skript nichts außer es zu sagen; der Workflow rendert dann
nur und legt das Video als Artefakt ab.

Zwei Dinge braucht dieser Weg, die die Anmeldung über Facebook nicht
brauchte. Beide liegen im Google-Projekt hinter Firebase
(endurance-5177a), erreicht OHNE Schlüsseldatei über Workload Identity:
Der Workflow-Schritt `google-github-actions/auth` tauscht das
GitHub-Kennzeichen des Laufs gegen einen Google-Zugang für eine Stunde
(Umgebungsvariable GCP_ACCESS_TOKEN).

  * **Das Video braucht eine öffentliche Adresse.** Meta holt es selbst
    ab (`video_url`); die Bytes direkt hochladen (Resumable Upload) geht
    laut Meta nur mit Facebook Login. Also: nach gs://<bucket>/<name>.mp4
    (Objekte öffentlich lesbar, der Bucket nicht auflistbar), nach dem
    Veröffentlichen gelöscht; eine Lebenszyklus-Regel räumt Reste nach
    einem Tag weg. Der Name trägt eine Zufallszahl.
  * **Der Instagram-Schlüssel läuft nach 60 Tagen ab**, wenn er nicht
    erneuert wird (`refresh_access_token`, frühestens 24 h nach dem
    Erzeugen). Er liegt im Secret Manager („instagram-token"), nie in
    GitHub. Jeder Lauf – auch die Vorschau am Morgen – erneuert ihn, wenn
    die jüngste Fassung ERNEUERN_NACH_TAGEN alt ist, legt die neue Fassung
    an und vernichtet die alten. Solange der Workflow mindestens alle 60
    Tage läuft, läuft der Schlüssel nie ab.

Der Weg auf Instagram (Meta-Doku „Content Publishing", Instagram Login,
Host graph.instagram.com, Schlüssel als „Authorization: Bearer"):

  0. GET  /me?fields=user_id,username     → die Konto-Id (<IG_ID>)
  1. POST /<IG_ID>/media  media_type=REELS, video_url, caption,
          share_to_feed, thumb_offset     → Container-Id
  2. GET  /<container>?fields=status_code bis FINISHED (Instagram lädt
          und verarbeitet das Video, meist 20–90 s)
  3. POST /<IG_ID>/media_publish creation_id
  4. GET  /<media-id>?fields=permalink    → die Adresse des Reels

**Kein Schlüssel ins Log.** Das Repository ist öffentlich, also auch die
Protokolle der Läufe. Beide Schlüssel werden in GitHub Actions mit
`::add-mask::` geschwärzt, sobald sie bekannt sind, und ein Netzfehler
von requests (dessen Text die Adresse samt Parametern enthält) wird nur
mit seinem Typ gemeldet.

Einmal einrichten: `bash scripts/instagram_google_einrichten.sh` in der
Google Cloud Shell, README „Instagram", Einrichtung.

Umgebung (alles optional außer GCP_ACCESS_TOKEN):

  GCP_ACCESS_TOKEN  Google-Zugang aus dem Workflow (fehlt er: nur rendern)
  GCP_PROJEKT       Vorgabe endurance-5177a
  IG_BUCKET         Vorgabe endurance-5177a-instagram
  IG_API_VERSION    Vorgabe v25.0
  IG_USER_ID        überspringt Schritt 0
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import secrets as _zufall
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

IG_HOST = "graph.instagram.com"
VORGABE_VERSION = "v25.0"
VORGABE_PROJEKT = "endurance-5177a"
VORGABE_BUCKET = "endurance-5177a-instagram"
SECRET = "instagram-token"
ERNEUERN_NACH_TAGEN = 7
WARTEN_MAX_S = 600
WARTEN_SCHRITT_S = 15
EINRICHTEN = "scripts/instagram_google_einrichten.sh"


class PostenFehler(RuntimeError):
    pass


def zugang() -> dict | None:
    """Der Google-Zugang des Laufs – ohne ihn wird nur gerendert."""
    gcp = (os.environ.get("GCP_ACCESS_TOKEN") or "").strip()
    if not gcp:
        return None
    maskiere(gcp)
    return {"gcp_token": gcp,
            "projekt": (os.environ.get("GCP_PROJEKT") or VORGABE_PROJEKT).strip(),
            "bucket": (os.environ.get("IG_BUCKET") or VORGABE_BUCKET).strip(),
            "version": (os.environ.get("IG_API_VERSION") or VORGABE_VERSION).strip(),
            "uid": (os.environ.get("IG_USER_ID") or "").strip() or None}


def maskiere(geheim: str | None) -> None:
    """In GitHub Actions: den Wert in allen weiteren Zeilen des Logs schwärzen."""
    if geheim and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{geheim}", flush=True)


def _anfrage(s, methode: str, url: str, schritt: str, **kw) -> requests.Response:
    try:
        return getattr(s, methode)(url, **kw)
    except requests.RequestException as e:
        # Der Text der Ausnahme enthält die Adresse mit allen Parametern -
        # beim Erneuern also den Schlüssel. Nur der Typ geht ins Log.
        raise PostenFehler(f"{schritt}: Netzfehler ({type(e).__name__})") from None


def _antwort(r, schritt: str) -> dict:
    try:
        daten = r.json() if r.content else {}
    except ValueError:
        daten = {"roh": r.text[:300]}
    if r.status_code >= 400 or (isinstance(daten, dict) and "error" in daten):
        fehler = daten.get("error", daten) if isinstance(daten, dict) else daten
        raise PostenFehler(f"{schritt}: HTTP {r.status_code} – {json.dumps(fehler, ensure_ascii=False)[:500]}")
    return daten


def _zeit(text: str) -> dt.datetime:
    """createTime des Secret Manager („2026-10-16T08:00:00.123456789Z")."""
    return dt.datetime.strptime(text[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


class Google:
    """Die zwei Google-Dienste, die der Weg braucht – nur REST, kein SDK."""

    SM = "https://secretmanager.googleapis.com/v1"
    GCS = "https://storage.googleapis.com"

    def __init__(self, z: dict, session=None):
        self.z, self.s = z, session or requests.Session()
        self.h = {"Authorization": f"Bearer {z['gcp_token']}"}
        self.secret = f"{self.SM}/projects/{z['projekt']}/secrets/{SECRET}"

    # --- Secret Manager: der Instagram-Schlüssel -----------------------
    def schluessel_lesen(self) -> tuple[str, dt.datetime, str]:
        r = _anfrage(self.s, "get", f"{self.secret}/versions/latest", "Tresor lesen", headers=self.h, timeout=30)
        if r.status_code == 404:
            raise PostenFehler(f"Im Tresor liegt noch kein Instagram-Schlüssel – in der Cloud Shell "
                               f"`bash {EINRICHTEN} --schluessel` ausführen.")
        meta = _antwort(r, "Tresor lesen")
        inhalt = _antwort(_anfrage(self.s, "get", f"{self.SM}/{meta['name']}:access", "Tresor lesen",
                                   headers=self.h, timeout=30), "Tresor lesen")
        token = base64.b64decode(inhalt["payload"]["data"]).decode("utf-8").strip()
        maskiere(token)
        return token, _zeit(meta["createTime"]), meta["name"]

    def schluessel_speichern(self, token: str) -> str:
        daten = {"payload": {"data": base64.b64encode(token.encode("utf-8")).decode("ascii")}}
        return _antwort(_anfrage(self.s, "post", f"{self.secret}:addVersion", "Tresor schreiben",
                                 headers=self.h, json=daten, timeout=30), "Tresor schreiben")["name"]

    def alte_vernichten(self, behalten: str) -> int:
        liste = _antwort(_anfrage(self.s, "get", f"{self.secret}/versions", "Tresor aufräumen", headers=self.h,
                                  params={"filter": "state:ENABLED"}, timeout=30), "Tresor aufräumen")
        weg = 0
        for v in liste.get("versions", []):
            if v.get("name") and v["name"] != behalten:
                _antwort(_anfrage(self.s, "post", f"{self.SM}/{v['name']}:destroy", "Tresor aufräumen",
                                  headers=self.h, json={}, timeout=30), "Tresor aufräumen")
                weg += 1
        return weg

    # --- Cloud Storage: Video oder Bild, solange Meta es abholt --------
    def video_hochladen(self, pfad: Path, name: str, art: str = "video/mp4") -> str:
        url = f"{self.GCS}/upload/storage/v1/b/{self.z['bucket']}/o"
        _antwort(_anfrage(self.s, "post", url, "Datei ablegen", params={"uploadType": "media", "name": name},
                          headers={**self.h, "Content-Type": art}, data=pfad.read_bytes(), timeout=300),
                 "Datei ablegen")
        return f"{self.GCS}/{self.z['bucket']}/{quote(name)}"

    def video_loeschen(self, name: str) -> None:
        r = _anfrage(self.s, "delete", f"{self.GCS}/storage/v1/b/{self.z['bucket']}/o/{quote(name, safe='')}",
                     "Video löschen", headers=self.h, timeout=30)
        if r.status_code != 404:
            _antwort(r, "Video löschen")


def _ig(z: dict) -> str:
    return f"https://{IG_HOST}/{z['version']}"


def erneuere(token: str, session=None) -> tuple[str, int]:
    """Neuer Schlüssel mit 60 Tagen Laufzeit (die Antwort kann derselbe Text sein)."""
    s = session or requests.Session()
    r = _anfrage(s, "get", f"https://{IG_HOST}/refresh_access_token", "Schlüssel erneuern",
                 params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    daten = _antwort(r, "Schlüssel erneuern")
    neu = (daten.get("access_token") or "").strip()
    if not neu:
        raise PostenFehler("Schlüssel erneuern: Antwort ohne access_token")
    maskiere(neu)
    return neu, int(daten.get("expires_in") or 0)


def pflege_schluessel(z: dict, session=None, jetzt: dt.datetime | None = None) -> dict:
    """Schlüssel aus dem Tresor holen und bei Bedarf erneuern.

    Rückgabe: {"token", "alter_tage", "erneuert", "gueltig_tage"}."""
    s = session or requests.Session()
    g = Google(z, s)
    token, erstellt, name = g.schluessel_lesen()
    jetzt = jetzt or dt.datetime.now(dt.timezone.utc)
    alter = (jetzt - erstellt).days
    info = {"token": token, "alter_tage": alter, "erneuert": False, "gueltig_tage": None}
    if alter < ERNEUERN_NACH_TAGEN:
        return info
    try:
        neu, laeuft = erneuere(token, s)
    except PostenFehler as e:
        hinweis = (f" Der Schlüssel ist {alter} Tage alt – nach 60 Tagen ohne Erneuerung ist er abgelaufen: "
                   f"in der App einen neuen erzeugen und `bash {EINRICHTEN} --schluessel` ausführen."
                   if alter >= 55 else "")
        raise PostenFehler(f"{e}.{hinweis}") from None
    neuer_name = g.schluessel_speichern(neu)
    g.alte_vernichten(neuer_name)
    info.update(token=neu, erneuert=True, gueltig_tage=laeuft // 86400 if laeuft else None)
    return info


def konto(z: dict, ig_token: str, session=None) -> dict:
    s = session or requests.Session()
    return _antwort(_anfrage(s, "get", f"{_ig(z)}/me", "Konto", params={"fields": "user_id,username"},
                             headers={"Authorization": f"Bearer {ig_token}"}, timeout=30), "Konto")


def _veroeffentliche(s, basis: str, uid: str, auth: dict, felder: dict, warten, was: str) -> tuple[str, str]:
    """Container anlegen, warten bis FINISHED, veröffentlichen → (Container, Medium)."""
    cid = _antwort(_anfrage(s, "post", f"{basis}/{uid}/media", f"{was}: Container anlegen", headers=auth,
                            json=felder, timeout=60), f"{was}: Container anlegen")["id"]
    print(f"  {was}: Container {cid}")
    gewartet = 0
    while True:
        st = _antwort(_anfrage(s, "get", f"{basis}/{cid}", f"{was}: Status", headers=auth,
                               params={"fields": "status_code,status"}, timeout=30), f"{was}: Status")
        code = st.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            break
        if code in ("ERROR", "EXPIRED"):
            raise PostenFehler(f"{was}: Verarbeitung {code} – {st.get('status')}")
        if gewartet >= WARTEN_MAX_S:
            raise PostenFehler(f"{was}: Verarbeitung dauert über {WARTEN_MAX_S} s (zuletzt {code})")
        warten(WARTEN_SCHRITT_S if was == "Reel" else 3)
        gewartet += WARTEN_SCHRITT_S if was == "Reel" else 3
    mid = _antwort(_anfrage(s, "post", f"{basis}/{uid}/media_publish", f"{was}: Veröffentlichen", headers=auth,
                            json={"creation_id": cid}, timeout=60), f"{was}: Veröffentlichen")["id"]
    return cid, mid


def poste_reel(video: Path, caption: str, thumb_offset_ms: int | None, z: dict, ig_token: str,
               session=None, warten=time.sleep, kennung: str = "reel") -> dict:
    s = session or requests.Session()
    g = Google(z, s)
    basis = _ig(z)
    auth = {"Authorization": f"Bearer {ig_token}"}
    uid = z.get("uid") or str(konto(z, ig_token, s)["user_id"])
    z["uid"] = uid

    try:
        limit = s.get(f"{basis}/{uid}/content_publishing_limit", headers=auth,
                      params={"fields": "quota_usage,config"}, timeout=30).json()
        print(f"  Veröffentlichungslimit: {json.dumps(limit.get('data', limit), ensure_ascii=False)[:200]}")
    except Exception:                                        # noqa: BLE001 - nur Auskunft
        pass

    name = f"{kennung}-{_zufall.token_hex(8)}.mp4"
    adresse = g.video_hochladen(video, name)
    print(f"  Video abgelegt ({video.stat().st_size / 1e6:.1f} MB), Instagram holt es ab …")
    try:
        felder = {"media_type": "REELS", "video_url": adresse, "caption": caption, "share_to_feed": True}
        if thumb_offset_ms is not None:
            felder["thumb_offset"] = int(thumb_offset_ms)
        cid, mid = _veroeffentliche(s, basis, uid, auth, felder, warten, "Reel")
    finally:
        try:
            g.video_loeschen(name)
        except PostenFehler as e:
            print(f"  Hinweis: Video nicht gelöscht ({e}) – die Lebenszyklus-Regel räumt es nach einem Tag weg.")

    link = None
    try:
        link = _antwort(_anfrage(s, "get", f"{basis}/{mid}", "Permalink", headers=auth,
                                 params={"fields": "permalink"}, timeout=30), "Permalink").get("permalink")
    except PostenFehler:
        pass
    return {"media_id": mid, "container_id": cid, "permalink": link}


def poste_story(bild: Path, z: dict, ig_token: str, session=None, warten=time.sleep,
                kennung: str = "story") -> dict:
    """Eine Story als Bild (media_type STORIES, image_url). Link-Sticker,
    Umfragen und Musik gibt es über die Schnittstelle nicht - die bleiben
    Handarbeit in der App."""
    s = session or requests.Session()
    g = Google(z, s)
    basis = _ig(z)
    auth = {"Authorization": f"Bearer {ig_token}"}
    uid = z.get("uid") or str(konto(z, ig_token, s)["user_id"])
    z["uid"] = uid
    name = f"{kennung}-{_zufall.token_hex(8)}.jpg"
    adresse = g.video_hochladen(bild, name, "image/jpeg")
    try:
        cid, mid = _veroeffentliche(s, basis, uid, auth, {"media_type": "STORIES", "image_url": adresse},
                                    warten, "Story")
    finally:
        try:
            g.video_loeschen(name)
        except PostenFehler as e:
            print(f"  Hinweis: Bild nicht gelöscht ({e}) – die Lebenszyklus-Regel räumt es nach einem Tag weg.")
    return {"media_id": mid, "container_id": cid}


INSIGHTS_VOLL = "reach,saved,shares,views,total_interactions"
INSIGHTS_KNAPP = "reach,saved,shares"


def auswertung(z: dict, ig_token: str, session=None, anzahl: int = 30) -> dict:
    """Kennzahlen der letzten `anzahl` Beiträge: Likes und Kommentare
    (instagram_business_basic), dazu Reichweite, Gespeichert, Geteilt und
    Aufrufe, wenn der Schlüssel instagram_business_manage_insights trägt -
    sonst `insights` False und ein Hinweis, wie man sie freischaltet."""
    s = session or requests.Session()
    basis = _ig(z)
    auth = {"Authorization": f"Bearer {ig_token}"}
    ich = _antwort(_anfrage(s, "get", f"{basis}/me", "Auswertung", headers=auth,
                            params={"fields": "user_id,username,followers_count,media_count"}, timeout=30),
                   "Auswertung")
    uid = str(ich.get("user_id") or z.get("uid"))
    liste = _antwort(_anfrage(s, "get", f"{basis}/{uid}/media", "Auswertung", headers=auth,
                              params={"fields": "id,timestamp,media_product_type,permalink,like_count,comments_count",
                                      "limit": anzahl}, timeout=30), "Auswertung").get("data", [])
    insights, hinweis, metriken = True, None, INSIGHTS_VOLL
    beitraege = []
    for m in liste:
        eintrag = {"id": m.get("id"), "zeit": m.get("timestamp"), "typ": m.get("media_product_type"),
                   "link": m.get("permalink"), "likes": m.get("like_count"), "kommentare": m.get("comments_count")}
        while insights:
            r = _anfrage(s, "get", f"{basis}/{m['id']}/insights", "Auswertung", headers=auth,
                         params={"metric": metriken}, timeout=30)
            daten = r.json() if r.content else {}
            if r.status_code < 400 and "data" in daten:
                for w in daten["data"]:
                    werte = w.get("values") or [{}]
                    eintrag[w.get("name")] = werte[0].get("value", w.get("total_value", {}).get("value"))
                break
            meldung = json.dumps(daten.get("error", daten), ensure_ascii=False)[:300]
            if metriken == INSIGHTS_VOLL:
                metriken = INSIGHTS_KNAPP           # ältere Fassung kennt nicht alle Metriken
                continue
            insights = False
            hinweis = ("Reichweite, Gespeichert und Geteilt fehlen – in der Meta-App unter "
                       "„Berechtigungen und Features“ instagram_business_manage_insights hinzufügen und "
                       f"`bash {EINRICHTEN} --anmelden` erneut ausführen. (Instagram: {meldung})")
        beitraege.append(eintrag)
    return {"follower": ich.get("followers_count"), "beitraege_gesamt": ich.get("media_count"),
            "beitraege": beitraege, "insights": insights, "hinweis": hinweis}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ein gerendertes Reel auf Instagram veröffentlichen.")
    ap.add_argument("ordner", help="Ordner mit reel.mp4, caption.txt, beitrag.json")
    a = ap.parse_args()
    ordner = Path(a.ordner)
    meta = json.loads((ordner / "beitrag.json").read_text(encoding="utf-8"))
    z = zugang()
    if not z:
        print("GCP_ACCESS_TOKEN nicht gesetzt (nur im Workflow) – nichts veröffentlicht.")
        sys.exit(0)
    pflege = pflege_schluessel(z)
    erg = poste_reel(ordner / "reel.mp4", (ordner / "caption.txt").read_text(encoding="utf-8"),
                     meta.get("video", {}).get("thumb_offset_ms"), z, pflege["token"],
                     kennung=f"reel-{meta.get('datum', 'x')}")
    print(json.dumps(erg, ensure_ascii=False))
