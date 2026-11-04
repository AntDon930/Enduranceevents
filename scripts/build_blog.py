#!/usr/bin/env python3
"""Erzeugt die Beitragsseiten des Blogs: blog/<slug>.html.

Vom Nutzer am 04.11.2026 gewünscht („neben der Karte einen Reiter für
unsere Blogeinträge … Blog“). Jeder Beitrag steht in blog.json (Titel,
Teaser, Datum, Sportart, Bild) und hat seinen Text als HTML-Baustein in
scripts/blog_texte/<slug>.html. Dieses Skript setzt daraus eine vollständige
Seite zusammen – mit derselben Kopfzeile, denselben Kopf-Skripten
(Wartungsmodus, Hell/Dunkel) und denselben ?v=-Stempeln wie blog.html.
So stehen Kopf und Fuß an EINER Stelle, und jeder Beitrag ist eine echte
Seite, die Suchmaschinen finden.

    python3 scripts/build_blog.py            # alle Beiträge schreiben
    python3 scripts/build_blog.py --check    # nur prüfen (Rückgabe 1, wenn veraltet)

stamp_assets.py ruft es nach dem Stempeln auf; test_blog prüft, dass die
Seiten zum Stand von blog.json, Text und Stempeln passen.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
BLOG_JSON = WURZEL / "blog.json"
TEXTE = WURZEL / "scripts" / "blog_texte"
SEITE_URL = "https://endurance-events.de"
SPORT_KLASSE = {"Laufen": "sport-laufen", "Fahrrad": "sport-fahrrad",
                "Schwimmen": "sport-schwimmen", "Triathlon": "sport-triathlon"}
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


def beitraege() -> list[dict]:
    return json.loads(BLOG_JSON.read_text(encoding="utf-8"))


def _vorlage() -> tuple[str, str]:
    """Kopf-Skripte und Kopfzeile aus blog.html, Pfade eine Ebene höher."""
    quelle = (WURZEL / "blog.html").read_text(encoding="utf-8")
    kopf = quelle[quelle.index("<!-- Wartungsmodus"):quelle.index('<meta name="description"')]
    # Die Wartungsseite liegt eine Ebene höher.
    kopf = kopf.replace("location.replace('wartung.html')", "location.replace('../wartung.html')")
    kopfzeile = quelle[quelle.index("<!-- Dieselbe Kopfzeile"):quelle.index("<main")]
    kopfzeile = re.sub(r'href="(?!https?:|#|\.\./)([^"]+)"', r'href="../\1"', kopfzeile)
    # Im Beitrag ist „Blog“ aktiv, verlinkt aber zurück auf die Übersicht.
    return kopf, kopfzeile


def _stempel(quelle: str, name: str) -> str:
    m = re.search(re.escape(name) + r"\?v=([0-9a-f]+)", quelle)
    return f"{name}?v={m.group(1)}" if m else name


def datum_de(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def seite(b: dict) -> str:
    kopf, kopfzeile = _vorlage()
    blog_html = (WURZEL / "blog.html").read_text(encoding="utf-8")
    site_css = _stempel(blog_html, "site.css")
    stats_js = _stempel(blog_html, "stats.js")
    blog_css = _stempel(blog_html, "blog.css")
    text = (TEXTE / f"{b['slug']}.html").read_text(encoding="utf-8").strip()
    e = html.escape
    url = f"{SEITE_URL}/blog/{b['slug']}.html"
    bild_url = f"{SEITE_URL}/{b['bild']}" if b.get("bild") else f"{SEITE_URL}/og-image.png"
    ld = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": b["titel"], "description": b["teaser"], "datePublished": b["datum"],
        "inLanguage": "de", "image": bild_url, "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "Endurance Events", "url": SEITE_URL},
    }
    tag = (f'<span class="blog-tag {SPORT_KLASSE.get(b.get("sportart"), "")}">{e(b["sportart"])}</span>'
           if b.get("sportart") else "")
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="tdm-reservation" content="1">
<!-- Erzeugt von scripts/build_blog.py aus blog.json und scripts/blog_texte/{e(b['slug'])}.html – nicht von Hand ändern. -->
<title>{e(b['titel'])} – Endurance Events</title>
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#0b1220">
{kopf}<meta name="description" content="{e(b['teaser'])}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Endurance Events">
<meta property="og:title" content="{e(b['titel'])}">
<meta property="og:description" content="{e(b['teaser'])}">
<meta property="og:locale" content="de_DE">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{e(bild_url)}">
<meta property="article:published_time" content="{e(b['datum'])}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<link rel="stylesheet" href="../vendor/fonts/barlow.css">
<link rel="stylesheet" href="../{site_css}">
<link rel="stylesheet" href="../{blog_css}">
</head>
<body>

{kopfzeile}
<main class="blog-main">
<article class="beitrag">
  <a class="beitrag-zurueck" href="../blog.html" id="blog-zurueck">← Alle Beiträge</a>
  <div class="blog-meta">
    {tag}<span>{e(datum_de(b['datum']))}</span><span aria-hidden="true">·</span><span>{int(b.get('lesezeit_min') or 1)} Min. Lesezeit</span>
  </div>
  <h1>{e(b['titel'])}</h1>
{text}
</article>
</main>

<footer class="site-footer">
  <div class="seiten-footer">
    <a id="footer-impressum" href="../impressum.html">Impressum</a>
    <a id="footer-datenschutz" href="../datenschutz.html">Datenschutz</a>
  </div>
</footer>

<script defer src="../vendor/firebase-10.14.1/firebase-app-compat.js"></script>
<script defer src="../vendor/firebase-10.14.1/firebase-auth-compat.js"></script>
<script defer src="../firebase-config.js"></script>
<script defer src="../auth.js"></script>
<script defer src="../{stats_js}"></script>
<script>
(function () {{
  // Der Beitrag selbst ist deutsch; DE/EN schaltet nur die Bedienung um.
  var T = {{
    de: {{ events: 'Events', clubs: 'Clubs', map: 'Karte', blog: 'Blog', back: '← Alle Beiträge', imprint: 'Impressum', privacy: 'Datenschutz' }},
    en: {{ events: 'Events', clubs: 'Clubs', map: 'Map', blog: 'Blog', back: '← All articles', imprint: 'Legal notice', privacy: 'Privacy' }}
  }};
  function setze(lang) {{
    try {{ localStorage.setItem('endurance-lang', lang); }} catch (e) {{ /* ignorieren */ }}
    var t = T[lang];
    document.getElementById('nav-events').textContent = t.events;
    document.getElementById('nav-clubs').textContent = t.clubs;
    document.getElementById('nav-map').textContent = t.map;
    document.getElementById('nav-blog').textContent = t.blog;
    document.getElementById('blog-zurueck').textContent = t.back;
    document.getElementById('footer-impressum').textContent = t.imprint;
    document.getElementById('footer-datenschutz').textContent = t.privacy;
    document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.classList.toggle('active', b.dataset.lang === lang); }});
  }}
  var lang = 'de';
  try {{ var s = localStorage.getItem('endurance-lang'); if (s === 'de' || s === 'en') lang = s; }} catch (e) {{ /* ignorieren */ }}
  document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.addEventListener('click', function () {{ setze(b.dataset.lang); }}); }});
  setze(lang);
}})();
</script>

</body>
</html>
"""


def ziel(b: dict) -> Path:
    return WURZEL / "blog" / f"{b['slug']}.html"


def veraltet() -> list[str]:
    return [b["slug"] for b in beitraege()
            if not ziel(b).exists() or ziel(b).read_text(encoding="utf-8") != seite(b)]


def schreibe() -> int:
    n = 0
    for b in beitraege():
        neu = seite(b)
        p = ziel(b)
        if not p.exists() or p.read_text(encoding="utf-8") != neu:
            p.write_text(neu, encoding="utf-8")
            n += 1
            print(f"  blog/{b['slug']}.html geschrieben")
    return n


def main(argv: list[str]) -> int:
    if "--check" in argv:
        alt = veraltet()
        if alt:
            print("Veraltete Blogseiten: " + ", ".join(alt) + " – python3 scripts/build_blog.py")
            return 1
        print("Blogseiten sind aktuell.")
        return 0
    schreibe()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
