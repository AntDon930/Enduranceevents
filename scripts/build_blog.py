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
ANZEIGE = {"Fahrrad": "Rad"}  # wie die Sportart-Chips der Übersicht
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


def _anker(text: str) -> str:
    t = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return re.sub(r"^\d+-", "", t) or "abschnitt"


def mit_inhalt(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Gibt jeder Zwischenüberschrift (h2) vor dem Abschlusskasten einen
    Anker und liefert das Inhaltsverzeichnis dazu. Der Kasten
    „beitrag-cta“ ist keine Gliederung, er bleibt ohne Eintrag."""
    schnitt = text.find('<section class="beitrag-cta"')
    vorn, hinten = (text, "") if schnitt < 0 else (text[:schnitt], text[schnitt:])
    inhalt: list[tuple[str, str]] = []

    def ersetze(m: re.Match) -> str:
        titel = re.sub(r"<[^>]+>", "", m.group(1))
        anker = _anker(titel)
        while any(a == anker for a, _ in inhalt):
            anker += "-2"
        inhalt.append((anker, titel))
        return f'<h2 id="{anker}">{m.group(1)}</h2>'

    vorn = re.sub(r"<h2>(.*?)</h2>", ersetze, vorn)
    return vorn + hinten, inhalt


def _weitere(b: dict, alle: list[dict]) -> str:
    """Bis zu drei andere Beiträge: gleiche Sportart zuerst, dann die neuesten."""
    andere = [x for x in alle if x["slug"] != b["slug"]]
    andere = sorted(andere, key=lambda x: x["datum"], reverse=True)
    andere.sort(key=lambda x: x.get("sportart") != b.get("sportart"))
    if not andere:
        return ""
    e = html.escape
    karten = "".join(
        f'''
    <li class="blog-karte"><a href="{e(x['slug'])}.html">
      <div class="blog-karte-bild"><img src="../{e(x.get('bild_klein') or x['bild'])}" alt="{e(x.get('bild_alt', ''))}" loading="lazy" width="480" height="320">{_tag(x)}</div>
      <div class="blog-karte-text"><h3>{e(x['titel'])}</h3><div class="blog-meta"><span>{e(datum_de(x['datum']))}</span><span aria-hidden="true">·</span><span>{int(x.get('lesezeit_min') or 1)} Min.</span></div></div>
    </a></li>''' for x in andere[:3])
    return f'''
  <section class="beitrag-weitere" aria-labelledby="weitere-titel">
    <h2 id="weitere-titel">Weitere Beiträge</h2>
    <ul class="blog-liste">{karten}
    </ul>
  </section>'''


def _tag(b: dict) -> str:
    if not b.get("sportart"):
        return ""
    return (f'<span class="blog-tag {SPORT_KLASSE.get(b["sportart"], "")}">'
            f'{html.escape(ANZEIGE.get(b["sportart"], b["sportart"]))}</span>')


def seite(b: dict) -> str:
    kopf, kopfzeile = _vorlage()
    blog_html = (WURZEL / "blog.html").read_text(encoding="utf-8")
    site_css = _stempel(blog_html, "site.css")
    stats_js = _stempel(blog_html, "stats.js")
    blog_css = _stempel(blog_html, "blog.css")
    text = (TEXTE / f"{b['slug']}.html").read_text(encoding="utf-8").strip()
    text, inhalt = mit_inhalt(text)
    weitere = _weitere(b, beitraege())
    e = html.escape
    url = f"{SEITE_URL}/blog/{b['slug']}.html"
    bild_url = f"{SEITE_URL}/{b['bild']}" if b.get("bild") else f"{SEITE_URL}/og-image.png"
    ld = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": b["titel"], "description": b["teaser"], "datePublished": b["datum"],
        "inLanguage": "de", "image": bild_url, "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "Endurance Events", "url": SEITE_URL},
    }
    tag = _tag(b)
    bild = b.get("bild")
    srcset = (f' srcset="../{e(b["bild_klein"])} 480w, ../{e(bild)} 960w" sizes="(max-width: 1120px) 100vw, 1120px"'
              if b.get("bild_klein") else "")
    hero_bild = (f'<img class="beitrag-hero-bild" src="../{e(bild)}"{srcset} alt="{e(b.get("bild_alt", ""))}" width="960" height="640" fetchpriority="high">'
                 if bild else "")
    nachweis = f'\n  <p class="beitrag-nachweis">{b["bild_nachweis"]}</p>' if b.get("bild_nachweis") else ""
    inhalt_html = ""
    if len(inhalt) >= 3:
        punkte = "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in inhalt)
        inhalt_html = f'''
  <nav class="beitrag-inhalt" aria-labelledby="inhalt-titel">
    <h2 id="inhalt-titel">Inhalt</h2>
    <ol>{punkte}</ol>
  </nav>'''

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
<div class="lese-fortschritt" aria-hidden="true"><span id="lese-balken"></span></div>
<main class="blog-main">
<article class="beitrag">
  <a class="beitrag-zurueck" href="../blog.html" id="blog-zurueck">← Alle Beiträge</a>
  <header class="beitrag-hero{' ohne-bild' if not bild else ''}">
    {hero_bild}
    <div class="beitrag-hero-text">
      <div class="blog-meta">
        {tag}<span>{e(datum_de(b['datum']))}</span><span aria-hidden="true">·</span><span>{int(b.get('lesezeit_min') or 1)} Min. Lesezeit</span>
      </div>
      <h1>{e(b['titel'])}</h1>
    </div>
  </header>{nachweis}
  <div class="beitrag-spalte">{inhalt_html}
{text}
  <div class="beitrag-teilen">
    <span id="teilen-text">Hat dir der Beitrag geholfen? Teil ihn mit deinen Trainingspartnern.</span>
    <button type="button" class="cta-knopf leise" id="teilen-knopf">Beitrag teilen</button>
  </div>
  </div>{weitere}
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
    de: {{ events: 'Events', clubs: 'Clubs', map: 'Karte', blog: 'Blog', back: '← Alle Beiträge', share: 'Beitrag teilen', share_text: 'Hat dir der Beitrag geholfen? Teil ihn mit deinen Trainingspartnern.', copied: 'Link kopiert', imprint: 'Impressum', privacy: 'Datenschutz' }},
    en: {{ events: 'Events', clubs: 'Clubs', map: 'Map', blog: 'Blog', back: '← All articles', share: 'Share article', share_text: 'Found this helpful? Share it with your training partners.', copied: 'Link copied', imprint: 'Legal notice', privacy: 'Privacy' }}
  }};
  function setze(lang) {{
    try {{ localStorage.setItem('endurance-lang', lang); }} catch (e) {{ /* ignorieren */ }}
    var t = T[lang];
    document.getElementById('nav-events').textContent = t.events;
    document.getElementById('nav-clubs').textContent = t.clubs;
    document.getElementById('nav-map').textContent = t.map;
    document.getElementById('nav-blog').textContent = t.blog;
    document.getElementById('blog-zurueck').textContent = t.back;
    document.getElementById('teilen-knopf').textContent = t.share;
    document.getElementById('teilen-text').textContent = t.share_text;
    document.getElementById('footer-impressum').textContent = t.imprint;
    document.getElementById('footer-datenschutz').textContent = t.privacy;
    document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.classList.toggle('active', b.dataset.lang === lang); }});
  }}
  var lang = 'de';
  try {{ var s = localStorage.getItem('endurance-lang'); if (s === 'de' || s === 'en') lang = s; }} catch (e) {{ /* ignorieren */ }}
  document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.addEventListener('click', function () {{ lang = b.dataset.lang; setze(lang); }}); }});
  setze(lang);
  // Teilen: Teilen-Dialog des Geräts, sonst den Link kopieren.
  var knopf = document.getElementById('teilen-knopf');
  knopf.addEventListener('click', function () {{
    var daten = {{ title: document.title, url: location.href.split('#')[0] }};
    if (navigator.share) {{ navigator.share(daten).catch(function () {{}}); return; }}
    if (navigator.clipboard) navigator.clipboard.writeText(daten.url).then(function () {{
      knopf.textContent = T[lang].copied;
      setTimeout(function () {{ knopf.textContent = T[lang].share; }}, 2000);
    }}).catch(function () {{}});
  }});
  // Lesefortschritt oben am Rand – nur Anzeige, nichts wird gespeichert.
  var balken = document.getElementById('lese-balken');
  var artikel = document.querySelector('.beitrag-spalte');
  var geplant = false;
  function fortschritt() {{
    geplant = false;
    var r = artikel.getBoundingClientRect();
    var weg = Math.min(Math.max(-r.top / Math.max(r.height - innerHeight, 1), 0), 1);
    balken.style.transform = 'scaleX(' + weg.toFixed(3) + ')';
  }}
  addEventListener('scroll', function () {{ if (!geplant) {{ geplant = true; requestAnimationFrame(fortschritt); }} }}, {{ passive: true }});
  fortschritt();
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
