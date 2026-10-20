#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/abo_meldung.py
======================

Meldet der Cloud Function `checkNewEvents` (functions/index.js), welche
Events seit dem letzten Deploy NEU AUF DER SEITE stehen – sie prüft sie
gegen die E-Mail-Abos und schickt die fälligen Mails.

Seit dem 20.10.2026 (vom Nutzer: „Ja, bitte beide Punkte ändern") läuft
das im Pages-Workflow statt im Datenlauf. Zwei Lücken waren der Grund:

1. **Mails vor dem Deploy.** `update_events.py` meldete die neuen Events
   noch im Datenlauf, also bevor sie committet und deployt waren. Am
   19.10.2026 war das Deploy-Gate rot – die Mail kam um 17:02 Uhr, die
   Events standen erst nach der Reparatur auf der Seite.
2. **Freigegebene Zeilen kamen nie.** Als „neu" galt nur, was der
   Datenlauf neu brachte. Eine Zeile, die vorher ausgeblendet war
   (`pruefung_offen`) und über die Korrekturseite sichtbar wird, löste
   nie eine Mail aus.

Deshalb vergleicht dieses Skript, was die Besucher SEHEN: Neu ist eine
Zeile, die jetzt sichtbar ist und beim letzten Melden nicht
(`neue_sichtbare`) – neue Zeilen aus dem Datenlauf, frisch freigegebene
Zeilen, nachgetragene Strecken.

**Gemeldet wird einmal je Datenlauf**, beim ersten grünen Deploy, der
einen neuen Commit des Datenlaufs (github-actions[bot]) enthält – also
montags, nach einem roten Gate am Tag der Reparatur. Ein Korrektur-Deploy
unter der Woche meldet nichts; seine freigegebenen Zeilen gehen mit der
nächsten Meldung raus. Würde jeder Deploy melden, wanderte die
wöchentliche Mail mit jedem Korrektur-Deploy auf einen anderen Wochentag
(die Function verschickt „wöchentlich", sobald sechs Tage um sind).

Den Stand merkt sich die Seite selbst: `deploy.json` (von pages.yml mit
hochgeladen, das Repo ist öffentlich) trägt den Commit des Deploys
(`commit`) und den Commit, bis zu dem gemeldet ist (`gemeldet`). Fehlt
die Datei (der erste Deploy damit), gilt der letzte Datenlauf-Commit als
gemeldet.

Zwei Schritte in `.github/workflows/pages.yml`:

    abo_meldung.py vergleichen --seite <Live-Adresse> --aus <datei>
        vor dem Upload: liest die deploy.json der Live-Seite, vergleicht
        die events.json von `gemeldet` (aus Git) mit der neuen, schreibt
        die neue deploy.json und die Liste – AUSSERHALB der hochgeladenen
        Seite (Workflow-Artefakt).

    abo_meldung.py senden --datei <datei>
        im Job NACH dem Deploy – nur, wenn der Deploy grün war. Liest
        NOTIFY_WEBHOOK_URL und NOTIFY_WEBHOOK_SECRET aus der Umgebung.

Ein RÜCKFALL meldet nichts: Ist der Live-Commit kein Vorfahr des neuen
(„Re-run all jobs" an einem älteren Lauf, siehe pages.yml), wären die
Zeilen des alten Stands sonst „neu".

Sicher statt viel: Lässt sich die deploy.json der Live-Seite nicht lesen
oder sieht der gemeldete Stand kaputt aus (weniger als `MIN_VORHER`
Zeilen), wird nichts gemeldet – sonst bekäme jedes Abo alle Events als
„neu". Dasselbe ab
`MAX_MELDUNG` neuen Zeilen (das wäre ein Fehler, keine Woche). In beiden
Fällen wird der Lauf rot und sagt, warum.

Die Kennung einer Zeile ist dieselbe wie beim Einsammeln (Name +
Startdatum + gerundete Distanz, `scraper_lib.dedupe_key()`). Eine
Korrektur der Distanz macht eine sichtbare Zeile deshalb zu einer neuen –
so war es auch vorher im Datenlauf.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fangzeile  # noqa: E402

# Ein echter Stand hat Tausende Zeilen; darunter ist der Abruf kaputt.
MIN_VORHER = 1000
# Mehr neue Zeilen auf einmal sind ein Fehler (eine Regel, die plötzlich
# nichts mehr ausblendet), keine Woche – dann lieber gar keine Mail.
MAX_MELDUNG = 3000
USER_AGENT = "EnduranceEvents-AboMeldung/1.0 (+https://endurance-events.de)"


def kennung(e: dict) -> tuple:
    """Name + Startdatum + gerundete Distanz – wie scraper_lib.dedupe_key()."""
    km = e.get("laenge_km")
    km = round(km, 1) if isinstance(km, (int, float)) else None
    return (str(e.get("name", "")).strip().casefold(), e.get("datum_start"), km)


def sichtbar(e: dict, heute: str) -> bool:
    """Was die Seite zeigt: nicht ausgeblendet (`pruefung_offen`, siehe
    clean_events.mark_pruefung_offen), nicht die Fangzeile und nicht
    vergangen (Datenregel 10: `datum_ende`, sonst `datum_start`; ein
    unlesbares Datum bleibt, wie in EF.dropPastEvents)."""
    if e.get("pruefung_offen") or fangzeile.ist_fangzeile(e):
        return False
    ende = str(e.get("datum_ende") or e.get("datum_start") or "")
    if len(ende) >= 10 and ende[:4].isdigit():
        return ende[:10] >= heute
    return True


def neue_sichtbare(vorher: list[dict], nachher: list[dict], heute: str) -> list[dict]:
    """Die Zeilen, die jetzt sichtbar sind und vorher nicht (je Kennung
    höchstens einmal)."""
    alt = {kennung(e) for e in vorher if sichtbar(e, heute)}
    neu, gesehen = [], set()
    for e in nachher:
        k = kennung(e)
        if sichtbar(e, heute) and k not in alt and k not in gesehen:
            gesehen.add(k)
            neu.append(e)
    return neu


def schreibe(pfad: Path, events: list[dict], grund: str | None = None) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = {"anzahl": len(events), "events": events}
    if grund:
        daten["grund"] = grund
    pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")


def git(*args: str) -> str | None:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def live_stand(seite: str, cache: str) -> tuple[str, dict]:
    """Die deploy.json der Live-Seite: ("ok", Inhalt), ("fehlt", {}) bei
    404 (vor dem ersten Deploy damit) oder ("fehler", {})."""
    url = f"{seite}/deploy.json?abo={cache}"
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                daten = json.loads(resp.read().decode("utf-8"))
            return ("ok", daten) if isinstance(daten, dict) else ("fehler", {})
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return "fehlt", {}
        except (urllib.error.URLError, socket.timeout, ValueError):
            pass
        if i < 2:
            time.sleep(10 * (i + 1))
    return "fehler", {}


def ist_commit(sha) -> bool:
    return isinstance(sha, str) and len(sha) == 40 and git("cat-file", "-e", f"{sha}^{{commit}}") is not None


def letzter_datenlauf(bis: str) -> str | None:
    """Der jüngste Commit des Datenlaufs (github-actions[bot]) bis `bis`."""
    out = git("log", "-1", "--format=%H", "--author=github-actions", bis, "--", "events.json")
    return out.strip() or None if out is not None else None


def datenlauf_seit(von: str, bis: str) -> bool:
    out = git("log", "--format=%H", "--author=github-actions", f"{von}..{bis}", "--", "events.json")
    return bool(out and out.strip())


def schreibe_deploy(pfad: str | None, commit: str, gemeldet: str | None) -> None:
    if not pfad:
        return
    daten = {"commit": commit}
    if gemeldet:
        daten["gemeldet"] = gemeldet
    Path(pfad).write_text(json.dumps(daten) + "\n", encoding="utf-8")


def cmd_vergleichen(args) -> int:
    heute = args.heute or dt.date.today().isoformat()
    nachher = json.loads(Path(args.nachher).read_text(encoding="utf-8"))
    aus = Path(args.aus)
    seite = args.seite.rstrip("/")
    commit = args.commit or (git("rev-parse", "HEAD") or "").strip()

    status, live = live_stand(seite, args.cache)
    if status == "fehler":
        grund = "deploy.json der Live-Seite nicht lesbar – nichts gemeldet"
        print(f"::warning::{grund}")
        schreibe_deploy(args.deploy_json, commit, None)
        schreibe(aus, [], grund)
        return 0
    live_commit, gemeldet = live.get("commit"), live.get("gemeldet")
    if ist_commit(live_commit) and git("merge-base", "--is-ancestor", live_commit, commit) is None:
        print(f"Rückfall: die Live-Seite ({live_commit[:8]}) ist neuer als dieser Stand ({commit[:8]}) – keine Abo-Meldung.")
        schreibe_deploy(args.deploy_json, commit, gemeldet if ist_commit(gemeldet) else None)
        schreibe(aus, [])
        return 0
    if not ist_commit(gemeldet):
        gemeldet = letzter_datenlauf(commit)
        print(f"Noch kein Meldestand auf der Seite – als gemeldet gilt der letzte Datenlauf {str(gemeldet)[:8]}.")
    if not ist_commit(gemeldet):
        grund = "kein Datenlauf-Commit in der Geschichte – nichts gemeldet"
        print(f"::warning::{grund}")
        schreibe_deploy(args.deploy_json, commit, None)
        schreibe(aus, [], grund)
        return 0
    if not datenlauf_seit(gemeldet, commit):
        print(f"Kein neuer Datenlauf seit der letzten Meldung ({gemeldet[:8]}) – die Abos bekommen "
              "die neuen und freigegebenen Zeilen mit dem nächsten Datenlauf.")
        schreibe_deploy(args.deploy_json, commit, gemeldet)
        schreibe(aus, [])
        return 0

    text = git("show", f"{gemeldet}:events.json")
    try:
        vorher = json.loads(text) if text is not None else None
    except ValueError:
        vorher = None
    if not isinstance(vorher, list) or len(vorher) < MIN_VORHER:
        grund = (f"gemeldeter Stand {gemeldet[:8]} sieht kaputt aus "
                 f"({len(vorher) if isinstance(vorher, list) else 'nicht lesbar'}, erwartet ≥ {MIN_VORHER} Zeilen) – nichts gemeldet")
        print(f"::warning::{grund}")
        schreibe_deploy(args.deploy_json, commit, gemeldet)
        schreibe(aus, [], grund)
        return 0
    neu = neue_sichtbare(vorher, nachher, heute)
    if len(neu) > MAX_MELDUNG:
        grund = f"{len(neu)} neue Zeilen auf einmal (Grenze {MAX_MELDUNG}) – nichts gemeldet, bitte prüfen"
        print(f"::warning::{grund}")
        schreibe_deploy(args.deploy_json, commit, gemeldet)
        schreibe(aus, [], grund)
        return 0
    # Ab hier gilt dieser Stand als gemeldet – schlägt das Senden nach dem
    # Deploy fehl, wird der Job rot (das Log nennt die Zeilen).
    schreibe_deploy(args.deploy_json, commit, commit)
    schreibe(aus, neu)
    print(f"Neuer Datenlauf seit der letzten Meldung ({gemeldet[:8]} → {commit[:8]}).")
    print(f"Neu sichtbar: {len(neu)} Zeile(n)")
    for e in neu[:15]:
        print(f"  {e.get('datum_start')}  {e.get('name')}  ({e.get('standort')})")
    if len(neu) > 15:
        print(f"  … und {len(neu) - 15} weitere")
    return 0


def melde(url: str, secret: str | None, events: list[dict], versuche: int = 3) -> dict:
    """POST an checkNewEvents. Wiederholt wird nur, wo sicher nichts
    verschickt wurde: keine Verbindung oder 502/503/504 (die Function lief
    nicht). Eine Zeitüberschreitung NICHT – die Function könnte die Mails
    schon in die Warteschlange gelegt haben, ein zweiter Aufruf
    verschickte sie doppelt."""
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if secret:
        headers["X-Notify-Secret"] = secret
    body = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
    for i in range(versuche):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8", "replace")
                try:
                    return json.loads(text)
                except ValueError:
                    return {"antwort": text[:200]}
        except urllib.error.HTTPError as exc:
            if exc.code in (502, 503, 504) and i + 1 < versuche:
                time.sleep(20 * (i + 1))
                continue
            raise RuntimeError(f"Webhook antwortete mit HTTP {exc.code}") from None
        except (socket.timeout, TimeoutError):
            raise RuntimeError("Zeitüberschreitung – nicht wiederholt (Mails könnten schon unterwegs sein)") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise RuntimeError("Zeitüberschreitung – nicht wiederholt (Mails könnten schon unterwegs sein)") from None
            if i + 1 < versuche:
                time.sleep(20 * (i + 1))
                continue
            # Nur den Typ nennen: der Text kann die Adresse enthalten.
            raise RuntimeError(f"Webhook nicht erreichbar ({type(exc.reason).__name__})") from None
    raise RuntimeError("Webhook nicht erreichbar")


def cmd_senden(args) -> int:
    pfad = Path(args.datei)
    if not pfad.exists():
        print(f"::error::{pfad} fehlt – der Vergleich vor dem Deploy ist nicht gelaufen, nichts gemeldet")
        return 1
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    if daten.get("grund"):
        print(f"::error::Nicht gemeldet: {daten['grund']}")
        return 1
    events = daten.get("events") or []
    if not events:
        print("Keine neuen sichtbaren Events – keine Meldung an die Abos.")
        return 0
    url = os.environ.get("NOTIFY_WEBHOOK_URL")
    if not url:
        print(f"NOTIFY_WEBHOOK_URL ist nicht gesetzt – {len(events)} neue Event(s) nicht gemeldet.")
        return 0
    print(f"→ Melde {len(events)} neu sichtbare(s) Event(s) an die Abo-Funktion …")
    try:
        antwort = melde(url, os.environ.get("NOTIFY_WEBHOOK_SECRET"), events)
    except RuntimeError as exc:
        print(f"::error::{exc}")
        return 1
    print(f"  ✓ Abos geprüft: {antwort.get('checkedSubscriptions', '?')}, "
          f"E-Mails verschickt: {antwort.get('mailsQueued', '?')}, "
          f"für später gesammelt: {antwort.get('collectedForLater', '?')} Event(s)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("vergleichen", help="Live-Stand gegen den neuen vergleichen")
    v.add_argument("--seite", required=True, help="Adresse der Live-Seite")
    v.add_argument("--nachher", default="events.json")
    v.add_argument("--commit", help="Commit dieses Deploys (Vorgabe: HEAD)")
    v.add_argument("--cache", default="0", help="Zusatz gegen den CDN-Cache (Lauf-Nummer)")
    v.add_argument("--deploy-json", help="hier die neue deploy.json ablegen (in der Seite)")
    v.add_argument("--aus", required=True)
    v.add_argument("--heute", help="YYYY-MM-DD (für Tests)")
    s = sub.add_parser("senden", help="die neuen Events an checkNewEvents melden")
    s.add_argument("--datei", required=True)
    args = p.parse_args(argv)
    return cmd_vergleichen(args) if args.cmd == "vergleichen" else cmd_senden(args)


if __name__ == "__main__":
    sys.exit(main())
