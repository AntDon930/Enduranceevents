#!/usr/bin/env python3
"""
scripts/insta_lauf.py
=====================

Ein Tag des Instagram-Accounts „AusdauerMaschine" in einem Aufruf:
planen (insta_inhalte.py) → Video rendern (insta_video.py) → Caption
schreiben → auf Wunsch veröffentlichen (insta_posten.py).

    python3 scripts/insta_lauf.py                         # heute, nur rendern
    python3 scripts/insta_lauf.py --datum 2026-10-16      # ein bestimmter Tag
    python3 scripts/insta_lauf.py --format moment         # Format erzwingen
    python3 scripts/insta_lauf.py --vorschau              # nur PNGs der Folien
    python3 scripts/insta_lauf.py --posten                # und veröffentlichen

Ausgabe in marketing/instagram/ausgabe/<datum>/ (nicht im Repo):
reel.mp4, cover.jpg, caption.txt, beitrag.json. Der Workflow
`.github/workflows/instagram.yml` ruft genau das täglich auf.

Veröffentlicht wird nur mit `--posten` UND gesetzten Zugangsdaten
(IG_USER_ID, IG_ACCESS_TOKEN). Ein Fehler beim Veröffentlichen lässt
den Lauf fehlschlagen (rot in Actions, Mail an den Nutzer) - das Video
liegt trotzdem als Artefakt bereit und kann von Hand gepostet werden.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import insta_inhalte as inhalte  # noqa: E402
import insta_video as video  # noqa: E402

AUSGABE = inhalte.MARKETING / "ausgabe"


def caption_mit_nachweis(caption: str, nachweis: str | None) -> str:
    """Namensnennung (CC BY/BY-SA verlangt sie) vor die Hashtags."""
    if not nachweis or nachweis in caption:
        return caption
    teile = caption.rsplit("\n\n", 1)
    if len(teile) == 2 and teile[1].startswith("#"):
        return f"{teile[0]}\n\n📷 {nachweis}\n\n{teile[1]}"[:2200]
    return f"{caption}\n\n📷 {nachweis}"[:2200]


def zusammenfassung(text: str) -> None:
    pfad = os.environ.get("GITHUB_STEP_SUMMARY")
    if pfad:
        with open(pfad, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--datum", help="YYYY-MM-DD, Vorgabe: heute (Europe/Berlin)")
    ap.add_argument("--format", choices=inhalte.FORMATE)
    ap.add_argument("--ausgabe", type=Path, help="Zielordner, Vorgabe marketing/instagram/ausgabe/<datum>")
    ap.add_argument("--vorschau", action="store_true", help="nur die Folien als PNG, kein Video")
    ap.add_argument("--posten", action="store_true", help="nach dem Rendern veröffentlichen")
    ap.add_argument("--freigabe", action="store_true",
                    help="mit --posten: nur veröffentlichen, wenn der Tag im Dashboard freigegeben "
                         "ist oder INSTAGRAM_AUTOPOST=ja gilt (insta_freigabe.py)")
    a = ap.parse_args()

    datum = dt.date.fromisoformat(a.datum) if a.datum else dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    ziel = a.ausgabe or AUSGABE / datum.isoformat()
    beitrag = inhalte.plane(datum, format_=a.format)
    # Kennung des Inhalts VOR dem Rendern (die Namensnennung des
    # Hintergrunds kommt erst danach in die Caption) - dieselbe, die
    # plan.json trägt und die das Dashboard mit der Freigabe speichert.
    beitrag["hash"] = inhalte.beitrag_hash(beitrag)
    print(f"{datum} ({inhalte.WOCHENTAGE[datum.weekday()]}): Format {beitrag['format']}"
          + (f", Moment {beitrag['moment_id']}" if beitrag.get("moment_id") else "")
          + (f", Clip {beitrag['clip']['id']}" if beitrag.get("clip") else ""))

    if a.vorschau:
        for p in video.vorschau(beitrag, ziel):
            print(f"  {p}")
        (ziel / "caption.txt").write_text(beitrag["caption"], encoding="utf-8")
        return 0

    if not video.ffmpeg_vorhanden():
        print("ffmpeg/ffprobe fehlen – kein Video möglich.", file=sys.stderr)
        return 1
    meta = video.rendere(beitrag, ziel, seed=datum.toordinal())
    beitrag["video"] = meta
    beitrag["caption"] = caption_mit_nachweis(beitrag["caption"], meta.get("nachweis"))
    (ziel / "caption.txt").write_text(beitrag["caption"], encoding="utf-8")
    print(f"  Video: {ziel / 'reel.mp4'} ({meta['dauer_s']} s, Hintergrund {meta['hintergrund']['art']})")

    zusammenfassung(f"## Instagram {datum} – {beitrag['format']}\n\n"
                    f"Video {meta['dauer_s']} s, Hintergrund: {meta['hintergrund']}\n\n"
                    f"```\n{beitrag['caption']}\n```\n")

    darf, grund = True, ""
    if a.posten and a.freigabe:
        import insta_freigabe as freigabe
        darf, grund = freigabe.darf_posten(beitrag["datum"], beitrag["hash"])
        print(f"  Freigabe: {'posten' if darf else 'NICHT posten'} - {grund}")
        zusammenfassung(f"Freigabe: **{'posten' if darf else 'nicht posten'}** - {grund}\n")
        beitrag["freigabe"] = {"posten": darf, "grund": grund}
    if a.posten and not darf:
        beitrag["veroeffentlicht"] = None
    elif a.posten:
        import insta_posten as posten
        if not posten.zugang():
            print("  --posten: IG_USER_ID / IG_ACCESS_TOKEN fehlen – nur gerendert.")
            beitrag["veroeffentlicht"] = None
        else:
            erg = posten.poste_reel(ziel / "reel.mp4", beitrag["caption"], meta.get("thumb_offset_ms"))
            beitrag["veroeffentlicht"] = erg
            print(f"  veröffentlicht: {erg.get('permalink') or erg['media_id']}")
            zusammenfassung(f"Veröffentlicht: {erg.get('permalink') or erg['media_id']}\n")
    (ziel / "beitrag.json").write_text(json.dumps(beitrag, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
