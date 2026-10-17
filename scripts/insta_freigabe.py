#!/usr/bin/env python3
"""
scripts/insta_freigabe.py
=========================

Die Freigabe eines Instagram-Beitrags mit EINEM Klick im Dashboard
(admin.html, Karte „Instagram-Freigabe") - und die Frage des Abendlaufs,
ob er posten darf. Vom Nutzer am 14.10.2026 gewünscht: „die ersten Videos
alle gerne vorher mit einem Klick einfach freigeben".

Wie es zusammenhängt:

  1. Der Pages-Workflow schreibt marketing/instagram/plan.json (die
     Beiträge der nächsten 14 Tage: Datum, Format, Folien, Caption und
     eine Kennung des Inhalts, insta_inhalte.beitrag_hash). Das Dashboard
     zeigt sie und speichert je Tag ein Dokument
     insta_freigaben/<YYYY-MM-DD> in Firestore:
         status    "freigegeben" oder "gesperrt"
         hash      die Kennung des Inhalts, der freigegeben wurde
         format    das Format (nur zur Anzeige)
         geaendert Server-Zeitstempel
     Lesen dürfen alle (nur Datum + Status + Kennung, nichts Persönliches),
     schreiben nur Admins - firestore.rules.
  2. Der Abendlauf (instagram.yml, 17:47) ruft `entscheide()`: gepostet
     wird, wenn der Tag freigegeben ist UND die Kennung noch stimmt - oder
     wenn die Repository-Variable INSTAGRAM_AUTOPOST = ja ist. „gesperrt"
     sperrt immer, auch mit Autopost. Alles andere: nur rendern, der Grund
     steht im Log und in der Zusammenfassung des Laufs.

Warum die Kennung: Zwischen Freigabe und Abend kann ein Datenlauf neue
Events bringen oder ein Moment korrigiert werden - dann weicht der
Inhalt von dem ab, den der Nutzer gesehen hat, und die Freigabe verfällt
von selbst. Das Dashboard sieht die veraltete Kennung ebenfalls und
bittet um eine neue Freigabe.

Gelesen wird über die Firestore-REST-Schnittstelle ohne Anmeldung - wie
die Seiten den Wartungsschalter (config/wartung) abfragen.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PROJEKT = "endurance-5177a"
SAMMLUNG = "insta_freigaben"
STATUS_FREI = "freigegeben"
STATUS_GESPERRT = "gesperrt"
STATUS_WERTE = (STATUS_FREI, STATUS_GESPERRT)


def url_fuer(datum: str) -> str:
    return (f"https://firestore.googleapis.com/v1/projects/{PROJEKT}/databases/(default)"
            f"/documents/{SAMMLUNG}/{datum}")


def _abrufer(url: str) -> tuple[int, str]:
    """HTTP-Status und Antworttext; 404 ist kein Fehler (kein Dokument)."""
    req = urllib.request.Request(url, headers={"User-Agent": "endurance-events.de insta_freigabe"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace") if e.fp else ""


def lese_freigabe(datum: str, abrufer=None) -> dict | None:
    """Das Freigabe-Dokument eines Tages als {"status", "hash", "format"}
    - None, wenn es keines gibt. Ein Netz- oder Serverfehler wird als
    {"fehler": "..."} zurückgegeben, damit `entscheide()` ihn nennen kann,
    statt still nicht zu posten."""
    status, text = (abrufer or _abrufer)(url_fuer(datum))
    if status == 404:
        return None
    if status != 200:
        return {"fehler": f"Firestore antwortet {status}"}
    try:
        felder = json.loads(text).get("fields", {})
    except ValueError:
        return {"fehler": "Firestore-Antwort nicht lesbar"}
    wert = lambda name: (felder.get(name) or {}).get("stringValue")  # noqa: E731
    return {"status": wert("status"), "hash": wert("hash"), "format": wert("format")}


def autopost_aktiv(umgebung: dict | None = None) -> bool:
    env = os.environ if umgebung is None else umgebung
    return str(env.get("INSTAGRAM_AUTOPOST", "")).strip().lower() in ("ja", "yes", "true", "1")


def entscheide(beitrag_hash: str, freigabe: dict | None, autopost: bool) -> tuple[bool, str]:
    """Darf der Beitrag mit dieser Kennung raus? (ja/nein, Begründung).
    Reihenfolge: gesperrt schlägt alles; dann die Freigabe mit passender
    Kennung; dann Autopost; sonst nein."""
    if freigabe and freigabe.get("fehler"):
        if autopost:
            return True, f"INSTAGRAM_AUTOPOST=ja ({freigabe['fehler']} - Freigabe nicht prüfbar)"
        return False, f"{freigabe['fehler']} - ohne Autopost wird nur gerendert"
    status = (freigabe or {}).get("status")
    if status == STATUS_GESPERRT:
        return False, "im Dashboard gesperrt"
    if status == STATUS_FREI:
        if freigabe.get("hash") == beitrag_hash:
            return True, "im Dashboard freigegeben"
        if autopost:
            return True, "INSTAGRAM_AUTOPOST=ja (die Freigabe galt einem älteren Inhalt)"
        return False, ("Freigabe veraltet - der Inhalt hat sich seit der Freigabe geändert "
                       f"(freigegeben {freigabe.get('hash')}, jetzt {beitrag_hash}); "
                       "im Dashboard erneut freigeben")
    if autopost:
        return True, "INSTAGRAM_AUTOPOST=ja"
    return False, "nicht freigegeben - im Dashboard (admin.html, Karte 'Instagram-Freigabe') freigeben"


def darf_posten(datum: str, beitrag_hash: str, abrufer=None, umgebung: dict | None = None) -> tuple[bool, str]:
    """Alles in einem: Dokument lesen, Autopost prüfen, entscheiden."""
    return entscheide(beitrag_hash, lese_freigabe(datum, abrufer), autopost_aktiv(umgebung))


if __name__ == "__main__":
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else None
    if not tag:
        print("Aufruf: insta_freigabe.py YYYY-MM-DD [hash]", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(lese_freigabe(tag), ensure_ascii=False))
    if len(sys.argv) > 2:
        ok, grund = darf_posten(tag, sys.argv[2])
        print(("posten" if ok else "nicht posten") + ": " + grund)
