#!/usr/bin/env python3
"""
scripts/insta_logos.py
======================

Holt die Logos der großen Events (marketing/instagram/grosse_events.json)
von den Veranstalterseiten - für die Logo-Reels „monat" und „anmeldung"
(insta_inhalte.py). Vom Nutzer am 27.10.2026 so gewählt („Logos von den
Webseiten"), nachdem er auf das Restrisiko hingewiesen wurde: Ein Logo ist
geschützt; die meisten Veranstalter freuen sich über die Werbung, ein
Anspruch darauf besteht aber nicht. Wer widerspricht, bekommt in
grosse_events.json `"logo": false` - dann zeigt das Reel eine Namenskarte.

Wie ein Logo gefunden wird (nur die Startseite aus `webseite`, höflich wie
insta_veranstalter.py: robots.txt, 2 s Pause je Host, 15 s Frist):

  0. `logo_datei` in grosse_events.json: eine Datei in
     marketing/instagram/logos/ (von Hand von der Veranstalterseite geholt,
     wenn die Suche das Logo nicht findet - z. B. Ötztaler Radmarathon: Die
     Seite setzt ihr Logo per JavaScript als SVG-Symbol ein, im HTML stehen
     nur die Sponsoren; vom Nutzer am 27.10.2026 bemerkt: „sicher nicht das
     Garmin Logo"). Schlägt alles.
  1. `logo_url` in grosse_events.json, wenn gesetzt (von Hand).
  2. <img>, deren class/id/alt/src oder das umschließende Element „logo"
     oder „brand" tragen - Sponsoren, Partner, Fuß, soziale Netze,
     Zahlungsarten und Flaggen fliegen raus. Früh auf der Seite, im Kopf
     und mit einem Wort des Rennens im Namen zählt mehr.
  3. apple-touch-icon (mindestens 150 px) als letzter Ausweg.

Aufbereitet wird jedes Logo gleich: SVG über ffmpeg (librsvg) gerastert,
Rand (transparent oder einfarbig) abgeschnitten, auf höchstens 900 px
verkleinert, als PNG mit Alpha abgelegt. Helle Logos auf transparentem
Grund (für dunkle Kopfzeilen gemacht) bekommen `hell: true` - das Reel
legt sie auf eine Navy- statt auf eine weiße Karte.

Ablage: marketing/instagram/.cache/logos/<slug>.png und logos.json
(Quelle, Bildadresse, hell, geprüft) - 30 Tage gültig, auch „kein Logo".
Der Workflow hebt .cache mit actions/cache auf.

    python3 scripts/insta_logos.py              # alle holen (Cache gilt)
    python3 scripts/insta_logos.py --neu        # Cache ignorieren
    python3 scripts/insta_logos.py --uebersicht logos.png   # Kontaktbogen
"""
from __future__ import annotations

import datetime as dt
import io
import json
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
LOGO_ORDNER = MARKETING / ".cache" / "logos"
LOGO_DATEIEN = MARKETING / "logos"           # von Hand abgelegte Logos (logo_datei)
GUELTIG_TAGE = 30
MAX_BILD_BYTES = 4_000_000
MAX_KANTE = 900
MIN_KANTE = 110             # längere Seite nach dem Zuschneiden
MAX_SEITENVERHAELTNIS = 7.0

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
    with tempfile.TemporaryDirectory() as tmp:
        quelle, ziel = Path(tmp) / "l.svg", Path(tmp) / "l.png"
        quelle.write_bytes(daten)
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
    hell = False
    if transparent:
        sichtbar = [px for px in bild.getdata() if px[3] > 128]
        if sichtbar:
            schnitt = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _ in sichtbar) / len(sichtbar)
            hell = schnitt > 205
    return bild, hell


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
    if ev.get("logo_datei"):
        quelle = LOGO_DATEIEN / ev["logo_datei"]
        erg = aufbereiten(quelle.read_bytes(), quelle.suffix.lower() == ".svg") if quelle.exists() else None
        if erg:
            ordner.mkdir(parents=True, exist_ok=True)
            erg[0].save(ordner / f"{s}.png")
            eintrag = {"geprueft": heute.isoformat(), "seite": ev.get("webseite"), "datei": f"{s}.png",
                       "bild": f"logos/{ev['logo_datei']}", "hell": erg[1], "groesse": list(erg[0].size),
                       "logo_datei": ev["logo_datei"]}
            meta[s] = eintrag
            if eigene_meta:
                speichere_meta(meta, ordner)
            return eintrag
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


def logos_fuer_beitrag(beitrag: dict, ordner: Path = LOGO_ORDNER, abrufer=None,
                       heute: dt.date | None = None) -> int:
    """Holt die Logos aller Folien eines Beitrags mit `logo_id` (vor dem
    Rendern, insta_lauf.py). Gibt die Zahl der vorhandenen Logos zurück;
    Fehler sind kein Abbruch - die Folie zeigt dann den Namen."""
    ids = [f["logo_id"] for f in beitrag.get("folien", []) if f.get("logo_id")]
    if not ids:
        return 0
    je_slug = {slug(e["name"]): e for e in lade_liste()}
    meta = lade_meta(ordner)
    n = 0
    for i in ids:
        ev = je_slug.get(i)
        if not ev:
            continue
        try:
            if logo_fuer(ev, abrufer, ordner, meta, heute):
                n += 1
        except Exception as e:                               # noqa: BLE001 - Logo ist Beiwerk
            print(f"  Logo {i}: {type(e).__name__}")
    speichere_meta(meta, ordner)
    return n


def logo_bild(logo_id: str, ordner: Path = LOGO_ORDNER):
    """(RGBA-Bild, hell) aus dem Cache oder None."""
    from PIL import Image
    eintrag = lade_meta(ordner).get(logo_id) or {}
    if not eintrag.get("datei") or not (ordner / eintrag["datei"]).exists():
        return None
    return Image.open(ordner / eintrag["datei"]).convert("RGBA"), bool(eintrag.get("hell"))


def uebersicht(ziel: Path, ordner: Path = LOGO_ORDNER) -> Path:
    """Kontaktbogen aller Logos (zum Durchsehen): je Event eine Kachel wie
    im Reel, darunter der Name; ohne Logo rot umrandet."""
    from PIL import Image, ImageDraw
    liste = lade_liste()
    meta = lade_meta(ordner)
    spalten, kw, kh = 6, 300, 230
    zeilen = max(1, (len(liste) + spalten - 1) // spalten)
    bogen = Image.new("RGB", (spalten * kw, zeilen * kh), (200, 204, 212))
    d = ImageDraw.Draw(bogen)
    for i, ev in enumerate(liste):
        x, y = (i % spalten) * kw, (i // spalten) * kh
        e = meta.get(slug(ev["name"])) or {}
        hell = bool(e.get("hell"))
        d.rounded_rectangle([x + 10, y + 10, x + kw - 10, y + kh - 50], radius=16,
                            fill=(11, 27, 51) if hell else (255, 255, 255),
                            outline=None if e.get("datei") else (220, 30, 30), width=4)
        if e.get("datei") and (ordner / e["datei"]).exists():
            logo = Image.open(ordner / e["datei"]).convert("RGBA")
            logo.thumbnail((kw - 50, kh - 90))
            bogen.paste(logo, (x + (kw - logo.width) // 2, y + 10 + (kh - 60 - logo.height) // 2), logo)
        d.text((x + 12, y + kh - 44), ev["name"][:40], fill=(0, 0, 0))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bogen.save(ziel)
    return ziel


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description="Logos der großen Events holen.")
    ap.add_argument("--neu", action="store_true", help="Cache ignorieren")
    ap.add_argument("--nur", default=None, help="nur Events, deren Name das enthält")
    ap.add_argument("--uebersicht", type=Path, default=None, help="Kontaktbogen als PNG schreiben")
    a = ap.parse_args()
    from insta_veranstalter import Abrufer
    abr = Abrufer()
    meta = lade_meta()
    ok = 0
    liste = [e for e in lade_liste() if not a.nur or a.nur.lower() in e["name"].lower()]
    for ev in liste:
        e = logo_fuer(ev, abr, meta=meta, neu=a.neu)
        speichere_meta(meta)
        ok += bool(e)
        print(f"{'OK  ' if e else '--  '}{ev['name']}" + (f"  {e['bild']}" if e else ""))
    print(f"{ok} von {len(liste)} mit Logo")
    if a.uebersicht:
        print(uebersicht(a.uebersicht))
