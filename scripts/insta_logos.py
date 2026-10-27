#!/usr/bin/env python3
"""
scripts/insta_logos.py
======================

Die Logos der großen Events (marketing/instagram/grosse_events.json) für
die Logo-Reels „monat" und „anmeldung" (insta_inhalte.py). Vom Nutzer am
27.10.2026 so gewählt („Logos von den Webseiten"), nachdem er auf das
Restrisiko hingewiesen wurde: Ein Logo ist geschützt; die meisten
Veranstalter freuen sich über die Werbung, ein Anspruch darauf besteht
aber nicht. Widerspricht einer, fliegt seine Datei aus logos/ - dann
zeigt das Reel eine Namenskarte.

NUR GEPRÜFTE LOGOS. Der erste Durchgang über alle 127 Seiten traf bei
etwa jedem vierten ein Sponsorlogo (Garmin beim Ötztaler - vom Nutzer
bemerkt -, LBS, Mizuno, Intersport …) oder eine geparkte Domain. Deshalb
holt der tägliche Lauf NICHTS aus dem Netz: Das Reel zeigt nur Dateien aus
marketing/instagram/logos/<slug>.png, die jemand angesehen hat. Der Weg
dorthin:

    python3 scripts/insta_logos.py sammeln [--nur Name] [--neu]
        holt je Event den besten Kandidaten von der Startseite
        (`webseite`) in den Cache (.cache/logos/) und schreibt einen
        Kontaktbogen (--uebersicht bogen.png)
    python3 scripts/insta_logos.py uebernehmen <slug> [--url Bildadresse]
        legt das angesehene Logo (aus dem Cache oder von --url) als
        logos/<slug>.png ab und trägt Quelle und Datum in logos/logos.json ein
    python3 scripts/insta_logos.py bogen bogen.png
        Kontaktbogen der GEPRÜFTEN Logos, Lücken rot

Die Suche auf der Startseite (höflich wie insta_veranstalter.py:
robots.txt, 2 s Pause je Host, 15 s Frist): <img>, deren class/id/alt/src
oder das umschließende Element „logo"/„brand" tragen - ein Bild im Link
auf die Startseite zählt am meisten, Sponsoren, Partner, Fuß, soziale
Netze und Unterveranstaltungen fliegen raus oder zählen weniger; zuletzt
das apple-touch-icon. Seiten, die ihr Logo per JavaScript einsetzen
(Ötztaler: SVG-Symbol), findet sie nicht - dann `--url` oder die Datei von
Hand.

Aufbereitet wird jedes Logo gleich: SVG gerastert (Chromium über
Playwright für Node, wenn vorhanden - versteht CSS in SVGs -, sonst ffmpeg/librsvg),
Rand (transparent oder einfarbig) abgeschnitten, auf höchstens 900 px
verkleinert, PNG mit Alpha. Helle Logos auf transparentem Grund (für
dunkle Kopfzeilen gemacht) legt das Reel auf eine Navy- statt auf eine
weiße Karte (`ist_hell`).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

WURZEL = Path(__file__).resolve().parent.parent
MARKETING = WURZEL / "marketing" / "instagram"
GROSSE_EVENTS = MARKETING / "grosse_events.json"
LOGO_ORDNER = MARKETING / ".cache" / "logos"       # Kandidaten (sammeln), nicht im Repo
GEPRUEFT = MARKETING / "logos"                     # angesehene Logos, im Repo
GUELTIG_TAGE = 30
MAX_BILD_BYTES = 4_000_000
MAX_KANTE = 900
MIN_KANTE = 110             # längere Seite nach dem Zuschneiden
MAX_SEITENVERHAELTNIS = 10.0      # Schriftzüge: Sierre-Zinal 7,5 : 1, Frauenlauf 9,1 : 1

IMG_RE = re.compile(r"<img\b[^>]*>", re.I | re.S)
ATTR_RE = re.compile(r"""([a-zA-Z_:][\w:.-]*)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""")
LINK_RE = re.compile(r"<link\b[^>]*>", re.I | re.S)
LOGO_WORT = re.compile(r"logo|brand|wordmark|signet", re.I)
NICHT_LOGO = re.compile(
    r"sponsor|partner|footer|payment|zahlung|paypal|visa|mastercard|social|facebook|instagram|"
    r"youtube|twitter|tiktok|linkedin|strava|whatsapp|app-?store|google-?play|cookie|flag|flagge|"
    r"lang|sprache|icon-|arrow|pfeil|search|suche|menu|burger|close|placeholder|spinner|loader|"
    r"datasport|raceresult|mikatiming|ticket|award|siegel|zertifik|certif|label|wmra|aims|"
    r"world-?athletics|gold-?label|uci\b|logo-?(?:white-)?small", re.I)


def slug(name: str) -> str:
    s = name.lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(alt, neu)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def lade_liste(pfad: Path | None = None) -> list[dict]:
    try:
        return json.loads((pfad or GROSSE_EVENTS).read_text(encoding="utf-8"))["events"]
    except (OSError, ValueError, KeyError):
        return []


def _attrs(tag: str) -> dict[str, str]:
    return {k.lower(): unescape(v.strip("\"'")) for k, v in ATTR_RE.findall(tag)}


# Unterveranstaltungen und Beiwerk, die oft neben dem Hauptlogo stehen.
NEBEN_LOGO = re.compile(r"green|expo|mile|frauenlauf|kids|kinder|bambini|schul|staffel|nordic|"
                        r"inline|skate|handbike|walking|charity|volunteer|helfer|team|neg\b|white|weiss", re.I)
A_RE = re.compile(r"<a\b[^>]*>", re.I | re.S)


def _verlinkt_startseite(davor: str, basis: str) -> bool:
    """Steht das Bild in einem Link auf die Startseite derselben Seite?"""
    links = list(A_RE.finditer(davor))
    if not links or "</a>" in davor[links[-1].end():].lower():
        return False
    href = _attrs(links[-1].group(0)).get("href", "")
    ziel = urlparse(urljoin(basis, href))
    if ziel.netloc and ziel.netloc.replace("www.", "") != urlparse(basis).netloc.replace("www.", ""):
        return False
    return ziel.path.rstrip("/") in ("", "/de", "/en", "/index.html", "/index.php", "/home", "/de/home")


def _woerter(text: str) -> set[str]:
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return {w for w in re.split(r"[^a-z0-9]+", text) if len(w) >= 4}


def _bild_quelle(a: dict[str, str]) -> str | None:
    """Die beste Bildadresse eines <img>: srcset (größte), sonst die
    Lazy-Load-Attribute, sonst src."""
    for key in ("srcset", "data-srcset"):
        if a.get(key):
            teile = []
            for eintrag in a[key].split(","):
                stuecke = eintrag.strip().split()
                if not stuecke:
                    continue
                w = 0
                if len(stuecke) > 1 and re.match(r"^\d+(\.\d+)?[wx]$", stuecke[1]):
                    w = float(stuecke[1][:-1]) * (1000 if stuecke[1].endswith("x") else 1)
                teile.append((w, stuecke[0]))
            if teile:
                return max(teile)[1]
    for key in ("data-src", "data-lazy-src", "data-original", "src"):
        v = a.get(key, "")
        if v and not v.startswith("data:"):
            return v
    return None


def kandidaten(html: str, basis: str, rennen: str = "") -> list[tuple[float, str]]:
    """[(Punkte, absolute Bildadresse)] - beste zuerst."""
    woerter = _woerter(rennen) | _woerter(urlparse(basis).netloc.replace("www.", "").rsplit(".", 1)[0])
    laenge = max(1, len(html))
    kopf_ende = html.lower().find("</header>")
    aus: dict[str, float] = {}
    for m in IMG_RE.finditer(html):
        a = _attrs(m.group(0))
        src = _bild_quelle(a)
        if not src:
            continue
        eigen = " ".join(a.get(k, "") for k in ("class", "id", "alt", "title")) + " " + src.rsplit("/", 1)[-1]
        umfeld = html[max(0, m.start() - 260):m.start()]
        # nur das letzte öffnende Element davor zählt als „umschließend"
        umfeld = umfeld[umfeld.rfind("<", 0, max(0, len(umfeld) - 1)):] if "<" in umfeld else umfeld
        if not (LOGO_WORT.search(eigen) or LOGO_WORT.search(umfeld)):
            continue
        if NICHT_LOGO.search(eigen) or NICHT_LOGO.search(umfeld):
            continue
        p = 10.0
        p += 6 * (1 - m.start() / laenge)
        if _verlinkt_startseite(html[max(0, m.start() - 600):m.start()], basis):
            p += 8          # das Logo im Kopf führt fast immer zur Startseite
        if re.search(r"(^|[/_-])logo(@2x)?\.(svg|png|webp|jpe?g)$", src.lower().split("?")[0]):
            p += 3
        if NEBEN_LOGO.search(eigen):
            p -= 6
        if kopf_ende > 0 and m.start() < kopf_ende:
            p += 4
        if LOGO_WORT.search(eigen):
            p += 3
        if woerter & _woerter(eigen):
            p += 3
        if src.lower().split("?")[0].endswith(".svg"):
            p += 1
        url = urljoin(basis, src)
        aus[url] = max(aus.get(url, 0), p)
    for m in LINK_RE.finditer(html):
        a = _attrs(m.group(0))
        rel = a.get("rel", "").lower()
        if "apple-touch-icon" in rel and a.get("href"):
            groesse = re.findall(r"\d+", a.get("sizes", "180"))
            if not groesse or int(groesse[0]) >= 150:
                url = urljoin(basis, a["href"])
                aus.setdefault(url, 1.0)
    return sorted(((p, u) for u, p in aus.items()), key=lambda x: -x[0])


# ---------------------------------------------------------------- Bilder

def _rastern_svg(daten: bytes) -> bytes | None:
    """SVG → PNG: Chromium (Playwright für Node, wenn installiert), sonst
    ffmpeg mit librsvg."""
    with tempfile.TemporaryDirectory() as tmp:
        quelle, ziel = Path(tmp) / "l.svg", Path(tmp) / "l.png"
        quelle.write_bytes(daten)
        js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
              "const p=await b.newPage({deviceScaleFactor:4,viewport:{width:600,height:400}});"
              f"await p.goto('{quelle.as_uri()}');const e=await p.$('svg');"
              f"await e.screenshot({{path:'{ziel}',omitBackground:true}});await b.close();}})();")
        try:
            wurzel = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
            subprocess.run(["node", "-e", js], check=True, timeout=90, capture_output=True,
                           env={**os.environ, "NODE_PATH": wurzel})
            if ziel.exists():
                return ziel.read_bytes()
        except (subprocess.SubprocessError, OSError):        # dann ffmpeg
            pass
        try:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-width", "1200",
                            "-keep_ar", "1", "-i", str(quelle), "-frames:v", "1", str(ziel)],
                           check=True, timeout=60)
            return ziel.read_bytes()
        except (subprocess.SubprocessError, OSError):
            return None


def aufbereiten(daten: bytes, ist_svg: bool = False):
    """Bytes → (RGBA-Bild zugeschnitten, hell) oder None, wenn es nicht
    nach einem Logo aussieht (zu klein, zu lang, leer)."""
    from PIL import Image, ImageChops
    if ist_svg or daten.lstrip()[:5] in (b"<?xml", b"<svg ") or b"<svg" in daten[:400]:
        daten = _rastern_svg(daten)
        if not daten:
            return None
    try:
        bild = Image.open(io.BytesIO(daten))
        bild.seek(0)
        bild = bild.convert("RGBA")
    except Exception:                                        # noqa: BLE001 - kein Bild
        return None
    alpha = bild.getchannel("A")
    transparent = alpha.getextrema()[0] < 250
    if transparent:
        box = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
    else:
        # einfarbiger Rand: Farbe der Ecke abziehen
        ecke = bild.getpixel((0, 0))
        hg = Image.new("RGBA", bild.size, ecke)
        diff = ImageChops.difference(bild, hg).convert("L").point(lambda v: 255 if v > 28 else 0)
        box = diff.getbbox()
    if not box:
        return None
    bild = bild.crop(box)
    w, h = bild.size
    if max(w, h) < MIN_KANTE or max(w, h) / max(1, min(w, h)) > MAX_SEITENVERHAELTNIS:
        return None
    if max(w, h) > MAX_KANTE:
        f = MAX_KANTE / max(w, h)
        bild = bild.resize((max(1, int(w * f)), max(1, int(h * f))), Image.LANCZOS)
    return bild, ist_hell(bild)


def ist_hell(bild) -> bool:
    """Ein Logo mit weißen Teilen auf transparentem Grund (weiße Schrift für
    dunkle Kopfzeilen, auch neben farbigen Zeichen wie bei ALB Extrem oder
    Rad am Ring) - mehr als ein Drittel fast weiß und kaum Schwarz -
    gehört auf eine dunkle Karte."""
    if bild.getchannel("A").getextrema()[0] >= 250:
        return False
    from PIL import ImageStat
    maske = bild.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    if not maske.getbbox():
        return False
    weiss = bild.convert("L").point(lambda v: 255 if v > 225 else 0)
    from PIL import ImageChops
    r, g, b, _ = [k.point(lambda v: 255 if v < 70 else 0) for k in bild.split()]
    dunkel = ImageChops.multiply(ImageChops.multiply(r, g), b)       # alle Kanäle dunkel = schwarz
    flaeche = max(1, ImageStat.Stat(maske).sum[0])
    anteil = ImageStat.Stat(ImageChops.multiply(weiss, maske)).sum[0] / flaeche
    schwarz = ImageStat.Stat(ImageChops.multiply(dunkel, maske)).sum[0] / flaeche
    return anteil > 0.3 and schwarz < 0.1      # schwarze Schrift (Kiel.Lauf) bleibt auf Weiß


# ---------------------------------------------------------------- Abruf

def _lade_bild(abrufer, url: str) -> bytes | None:
    if not re.match(r"https?://", url) or not abrufer._darf(url):
        return None
    try:
        with abrufer.s.get(url, timeout=15, stream=True) as r:
            if r.status_code != 200:
                return None
            daten = b""
            for block in r.iter_content(65536):
                daten += block
                if len(daten) > MAX_BILD_BYTES:
                    return None
            return daten
    except Exception:                                        # noqa: BLE001
        return None


def lade_meta(ordner: Path = LOGO_ORDNER) -> dict:
    try:
        return json.loads((ordner / "logos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def speichere_meta(meta: dict, ordner: Path = LOGO_ORDNER) -> None:
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "logos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True),
                                       encoding="utf-8")


def logo_fuer(ev: dict, abrufer=None, ordner: Path = LOGO_ORDNER, meta: dict | None = None,
              heute: dt.date | None = None, neu: bool = False) -> dict | None:
    """Sorgt dafür, dass das Logo eines großen Events im Cache liegt, und
    gibt dessen Eintrag zurück ({datei, hell, …}) - None ohne Logo."""
    heute = heute or dt.date.today()
    eigene_meta = meta is None
    meta = lade_meta(ordner) if meta is None else meta
    s = slug(ev["name"])
    if ev.get("logo") is False:
        return None
    alt = meta.get(s)
    if alt and not neu:
        try:
            frisch = (heute - dt.date.fromisoformat(alt["geprueft"])).days < GUELTIG_TAGE
        except (KeyError, ValueError):
            frisch = False
        gleiche_quelle = alt.get("logo_url_hand") == ev.get("logo_url")
        if frisch and gleiche_quelle:
            if alt.get("datei") and (ordner / alt["datei"]).exists():
                return alt
            if not alt.get("datei"):
                return None
    if abrufer is None:
        from insta_veranstalter import Abrufer
        abrufer = Abrufer()
    liste: list[tuple[float, str]] = []
    if ev.get("logo_url"):
        liste.append((100.0, ev["logo_url"]))
    elif ev.get("webseite"):
        html = abrufer.holen(ev["webseite"])
        if html:
            liste = kandidaten(html, ev["webseite"], ev["name"])[:6]
    eintrag = {"geprueft": heute.isoformat(), "seite": ev.get("webseite"), "logo_url_hand": ev.get("logo_url"),
               "datei": None}
    for _, url in liste:
        daten = _lade_bild(abrufer, url)
        if not daten:
            continue
        erg = aufbereiten(daten, url.lower().split("?")[0].endswith(".svg"))
        if not erg:
            continue
        bild, hell = erg
        ordner.mkdir(parents=True, exist_ok=True)
        bild.save(ordner / f"{s}.png")
        eintrag.update({"datei": f"{s}.png", "bild": url, "hell": hell, "groesse": list(bild.size)})
        break
    meta[s] = eintrag
    if eigene_meta:
        speichere_meta(meta, ordner)
    return eintrag if eintrag["datei"] else None


def logo_bild(logo_id: str, ordner: Path | None = None):
    """(RGBA-Bild, hell) eines GEPRÜFTEN Logos oder None."""
    from PIL import Image
    pfad = (ordner or GEPRUEFT) / f"{logo_id}.png"
    if not pfad.is_file():
        return None
    bild = Image.open(pfad).convert("RGBA")
    return bild, ist_hell(bild)


def vorhanden(beitrag: dict, ordner: Path | None = None) -> tuple[int, list[str]]:
    """(Zahl der Logo-Folien mit geprüftem Logo, Namen ohne Logo)."""
    folien = [f for f in beitrag.get("folien", []) if f.get("logo_id")]
    ohne = [f.get("name", f["logo_id"]) for f in folien if not ((ordner or GEPRUEFT) / f"{f['logo_id']}.png").is_file()]
    return len(folien) - len(ohne), ohne


def lade_gepruefte(ordner: Path | None = None) -> dict:
    try:
        return json.loads(((ordner or GEPRUEFT) / "logos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def uebernehmen(logo_id: str, url: str | None = None, abrufer=None, ordner: Path | None = None,
                heute: dt.date | None = None) -> Path | None:
    """Ein angesehenes Logo nach logos/<slug>.png - aus dem Cache des
    Sammelns oder neu von `url` (auch eine lokale Datei)."""
    ordner = ordner or GEPRUEFT
    heute = heute or dt.date.today()
    cache = lade_meta()
    ev = {slug(e["name"]): e for e in lade_liste()}.get(logo_id)
    if ev is None:
        raise SystemExit(f"{logo_id}: kein Event dieses Namens in grosse_events.json")
    if url:
        if re.match(r"https?://", url):
            if abrufer is None:
                from insta_veranstalter import Abrufer
                abrufer = Abrufer()
            daten = _lade_bild(abrufer, url)
        else:
            daten = Path(url).read_bytes()
        erg = aufbereiten(daten, url.lower().split("?")[0].endswith(".svg")) if daten else None
        if not erg:
            print(f"{logo_id}: {url} ist kein brauchbares Logo")
            return None
        bild, quelle = erg[0], url
    else:
        e = cache.get(logo_id) or {}
        if not e.get("datei") or not (LOGO_ORDNER / e["datei"]).exists():
            print(f"{logo_id}: nichts im Cache - erst sammeln oder --url")
            return None
        from PIL import Image
        bild, quelle = Image.open(LOGO_ORDNER / e["datei"]).convert("RGBA"), e.get("bild")
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{logo_id}.png"
    bild.save(ziel, optimize=True)
    meta = lade_gepruefte(ordner)
    meta[logo_id] = {"quelle": quelle, "seite": ev.get("webseite"), "geprueft": heute.isoformat()}
    (ordner / "logos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                                       encoding="utf-8")
    return ziel


def uebersicht(ziel: Path, ordner: Path | None = None, gepruefte: bool = False) -> Path:
    """Kontaktbogen (zum Durchsehen): je Event eine Kachel wie im Reel,
    darunter der Name; ohne Logo rot umrandet. `gepruefte`: die Dateien
    aus logos/, sonst die gesammelten Kandidaten."""
    from PIL import Image, ImageDraw
    liste = lade_liste()
    spalten, kw, kh = 6, 300, 230
    zeilen = max(1, (len(liste) + spalten - 1) // spalten)
    bogen = Image.new("RGB", (spalten * kw, zeilen * kh), (200, 204, 212))
    d = ImageDraw.Draw(bogen)
    if gepruefte:
        pfade = {slug(e["name"]): (ordner or GEPRUEFT) / f"{slug(e['name'])}.png" for e in liste}
    else:
        meta = lade_meta(ordner or LOGO_ORDNER)
        pfade = {k: (ordner or LOGO_ORDNER) / v["datei"] for k, v in meta.items() if v.get("datei")}
    for i, ev in enumerate(liste):
        x, y = (i % spalten) * kw, (i // spalten) * kh
        pfad = pfade.get(slug(ev["name"]))
        logo = Image.open(pfad).convert("RGBA") if pfad and pfad.is_file() else None
        hell = bool(logo and ist_hell(logo))
        d.rounded_rectangle([x + 10, y + 10, x + kw - 10, y + kh - 50], radius=16,
                            fill=(11, 27, 51) if hell else (255, 255, 255),
                            outline=None if logo else (220, 30, 30), width=4)
        if logo:
            logo.thumbnail((kw - 50, kh - 90))
            bogen.paste(logo, (x + (kw - logo.width) // 2, y + 10 + (kh - 60 - logo.height) // 2), logo)
        d.text((x + 12, y + kh - 44), ev["name"][:40], fill=(0, 0, 0))
        d.text((x + 12, y + kh - 28), slug(ev["name"])[:44], fill=(70, 70, 90))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bogen.save(ziel)
    return ziel


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description="Logos der großen Events sammeln, prüfen, übernehmen.")
    unter = ap.add_subparsers(dest="befehl", required=True)
    s1 = unter.add_parser("sammeln", help="Kandidaten von den Startseiten in den Cache holen")
    s1.add_argument("--neu", action="store_true", help="Cache ignorieren")
    s1.add_argument("--nur", default=None, help="nur Events, deren Name das enthält")
    s1.add_argument("--uebersicht", type=Path, default=None, help="Kontaktbogen als PNG schreiben")
    s2 = unter.add_parser("uebernehmen", help="angesehene Logos nach logos/ legen")
    s2.add_argument("slugs", nargs="+")
    s2.add_argument("--url", default=None, help="Bildadresse oder Datei statt des Cache (nur mit EINEM slug)")
    s3 = unter.add_parser("bogen", help="Kontaktbogen der geprüften Logos")
    s3.add_argument("ziel", type=Path)
    a = ap.parse_args()
    if a.befehl == "sammeln":
        from insta_veranstalter import Abrufer
        abr = Abrufer()
        meta = lade_meta()
        ok = 0
        liste = [e for e in lade_liste() if not a.nur or a.nur.lower() in e["name"].lower()]
        for ev in liste:
            e = logo_fuer(ev, abr, meta=meta, neu=a.neu)
            speichere_meta(meta)
            ok += bool(e)
            print(f"{'OK  ' if e else '--  '}{slug(ev['name'])}" + (f"  {e['bild']}" if e else ""))
        print(f"{ok} von {len(liste)} mit Kandidat")
        if a.uebersicht:
            print(uebersicht(a.uebersicht))
    elif a.befehl == "uebernehmen":
        if a.url and len(a.slugs) != 1:
            raise SystemExit("--url nur mit einem slug")
        for sl in a.slugs:
            print(uebernehmen(sl, a.url) or f"{sl}: nicht übernommen")
    else:
        print(uebersicht(a.ziel, gepruefte=True))
