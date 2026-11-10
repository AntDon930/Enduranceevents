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

Seit dem 10.11.2026 ist der Blog zweisprachig (vom Nutzer gewählt: „Alles
auf Englisch“): Zu jedem Beitrag gehört eine englische Fassung – Text in
scripts/blog_texte/en/<slug>.html, Titel/Teaser/Bildtext als `titel_en`,
`teaser_en`, `bild_alt_en`, `bild_nachweis_en` in blog.json – und daraus
die Seite blog/en/<slug>.html. Beide Fassungen nennen sich gegenseitig
(hreflang), der Sprachknopf DE/EN wechselt die Fassung, und wer EN gewählt
hat, landet von einem deutschen Link auf der englischen (und umgekehrt).
Fehlt die englische Fassung, bleibt es beim alten Verhalten: Die deutsche
Seite schaltet nur die Bedienung um.
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
TEXTE_EN = TEXTE / "en"
SEITE_URL = "https://endurance-events.de"
SPORT_KLASSE = {"Laufen": "sport-laufen", "Fahrrad": "sport-fahrrad",
                "Schwimmen": "sport-schwimmen", "Triathlon": "sport-triathlon"}
ANZEIGE = {"Fahrrad": "Rad"}  # wie die Sportart-Chips der Übersicht
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
SPORT_EN = {"Laufen": "Running", "Fahrrad": "Cycling", "Schwimmen": "Swimming", "Triathlon": "Triathlon"}
# Die festen Texte einer Beitragsseite je Sprache (dieselben Wörter wie
# blog.html; die Bedienung im Skript unten trägt sie noch einmal).
UI = {
    "de": {"zurueck": "← Alle Beiträge", "inhalt": "Inhalt", "weitere": "Weitere Beiträge",
           "lesezeit": "{n} Min. Lesezeit", "min": "{n} Min.",
           "teilen_text": "Hat dir der Beitrag geholfen? Teil ihn mit deinen Trainingspartnern.",
           "teilen": "Beitrag teilen", "impressum": "Impressum", "datenschutz": "Datenschutz",
           "karte": "Karte", "seiten": "Seiten", "locale": "de_DE"},
    "en": {"zurueck": "← All articles", "inhalt": "Contents", "weitere": "More articles",
           "lesezeit": "{n} min read", "min": "{n} min",
           "teilen_text": "Found this helpful? Share it with your training partners.",
           "teilen": "Share article", "impressum": "Legal notice", "datenschutz": "Privacy",
           "karte": "Map", "seiten": "Pages", "locale": "en_GB"},
}


def beitraege() -> list[dict]:
    return json.loads(BLOG_JSON.read_text(encoding="utf-8"))


def hat_en(b: dict) -> bool:
    """Gibt es den Beitrag auf Englisch? Text UND Titel/Teaser müssen da sein."""
    return bool(b.get("titel_en") and b.get("teaser_en") and (TEXTE_EN / f"{b['slug']}.html").exists())


def feld(b: dict, name: str, sprache: str) -> str:
    """Ein Feld in der Sprache der Seite; ohne englische Fassung das deutsche."""
    if sprache == "en" and b.get(name + "_en"):
        return b[name + "_en"]
    return b.get(name, "")


def _vorlage(sprache: str = "de") -> tuple[str, str]:
    """Kopf-Skripte und Kopfzeile aus blog.html, Pfade eine Ebene höher
    (die englischen Seiten unter blog/en/ zwei Ebenen)."""
    oben = "../" if sprache == "de" else "../../"
    quelle = (WURZEL / "blog.html").read_text(encoding="utf-8")
    kopf = quelle[quelle.index("<!-- Wartungsmodus"):quelle.index('<meta name="description"')]
    # Die Wartungsseite liegt eine Ebene höher.
    kopf = kopf.replace("location.replace('wartung.html')", f"location.replace('{oben}wartung.html')")
    kopfzeile = quelle[quelle.index("<!-- Dieselbe Kopfzeile"):quelle.index("<main")]
    kopfzeile = re.sub(r'href="(?!https?:|#|\.\./)([^"]+)"', lambda m: f'href="{oben}{m.group(1)}"', kopfzeile)
    if sprache == "en":
        kopfzeile = (kopfzeile.replace('id="nav-map">Karte</a>', 'id="nav-map">Map</a>')
                     .replace('aria-label="Seiten"', 'aria-label="Pages"'))
    # Im Beitrag ist „Blog“ aktiv, verlinkt aber zurück auf die Übersicht.
    return kopf, kopfzeile


def _stempel(quelle: str, name: str) -> str:
    m = re.search(re.escape(name) + r"\?v=([0-9a-f]+)", quelle)
    return f"{name}?v={m.group(1)}" if m else name


def datum_de(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def datum_text(iso: str, sprache: str) -> str:
    if sprache == "en":
        d = date.fromisoformat(iso)
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return datum_de(iso)


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


def _weitere(b: dict, alle: list[dict], sprache: str = "de") -> str:
    """Bis zu drei andere Beiträge: gleiche Sportart zuerst, dann die neuesten.
    Auf einer englischen Seite führt jede Kachel zur englischen Fassung, wo es
    eine gibt (sonst zur deutschen, eine Ebene höher)."""
    andere = [x for x in alle if x["slug"] != b["slug"]]
    andere = sorted(andere, key=lambda x: x["datum"], reverse=True)
    andere.sort(key=lambda x: x.get("sportart") != b.get("sportart"))
    if not andere:
        return ""
    e = html.escape
    ui = UI[sprache]
    oben = "../" if sprache == "de" else "../../"

    def link(x: dict) -> str:
        if sprache == "en" and not hat_en(x):
            return f"../{x['slug']}.html"
        return f"{x['slug']}.html"

    def kurz(x: dict) -> str:
        sp = sprache if (sprache == "de" or hat_en(x)) else "de"
        return e(feld(x, "titel", sp))

    karten = "".join(
        f'''
    <li class="blog-karte"><a href="{e(link(x))}">
      <div class="blog-karte-bild"><img src="{oben}{e(x.get('bild_klein') or x['bild'])}" alt="{e(feld(x, 'bild_alt', sprache))}" loading="lazy" width="480" height="320">{_tag(x, sprache)}</div>
      <div class="blog-karte-text"><h3>{kurz(x)}</h3><div class="blog-meta"><span>{e(datum_text(x['datum'], sprache))}</span><span aria-hidden="true">·</span><span>{ui['min'].format(n=int(x.get('lesezeit_min') or 1))}</span></div></div>
    </a></li>''' for x in andere[:3])
    return f'''
  <section class="beitrag-weitere" aria-labelledby="weitere-titel">
    <h2 id="weitere-titel">{ui['weitere']}</h2>
    <ul class="blog-liste">{karten}
    </ul>
  </section>'''


def _tag(b: dict, sprache: str = "de") -> str:
    if not b.get("sportart"):
        return ""
    name = SPORT_EN.get(b["sportart"], b["sportart"]) if sprache == "en" else ANZEIGE.get(b["sportart"], b["sportart"])
    return (f'<span class="blog-tag {SPORT_KLASSE.get(b["sportart"], "")}">'
            f'{html.escape(name)}</span>')


def url_von(b: dict, sprache: str) -> str:
    return f"{SEITE_URL}/blog/{'en/' if sprache == 'en' else ''}{b['slug']}.html"


def text_von(b: dict, sprache: str) -> str:
    """Der Beitragstext; der englische liegt zwei Ebenen tief, seine Verweise
    auf die Seiten (../events.html …) bekommen deshalb eine Ebene mehr.
    Verweise auf andere Beiträge (tapering.html) bleiben im eigenen Ordner –
    so zeigt ein englischer Beitrag auf den englischen."""
    if sprache == "de":
        return (TEXTE / f"{b['slug']}.html").read_text(encoding="utf-8").strip()
    text = (TEXTE_EN / f"{b['slug']}.html").read_text(encoding="utf-8").strip()
    return re.sub(r'(href|src)="\.\./', r'\1="../../', text)


def seite(b: dict, sprache: str = "de") -> str:
    kopf, kopfzeile = _vorlage(sprache)
    blog_html = (WURZEL / "blog.html").read_text(encoding="utf-8")
    site_css = _stempel(blog_html, "site.css")
    stats_js = _stempel(blog_html, "stats.js")
    blog_css = _stempel(blog_html, "blog.css")
    text, inhalt = mit_inhalt(text_von(b, sprache))
    weitere = _weitere(b, beitraege(), sprache)
    e = html.escape
    ui = UI[sprache]
    oben = "../" if sprache == "de" else "../../"
    titel, teaser = feld(b, "titel", sprache), feld(b, "teaser", sprache)
    url = url_von(b, sprache)
    zweisprachig = hat_en(b)
    bild_url = f"{SEITE_URL}/{b['bild']}" if b.get("bild") else f"{SEITE_URL}/og-image.png"
    ld = {
        "@context": "https://schema.org", "@type": "BlogPosting",
        "headline": titel, "description": teaser, "datePublished": b["datum"],
        "inLanguage": sprache, "image": bild_url, "mainEntityOfPage": url,
        "publisher": {"@type": "Organization", "name": "Endurance Events", "url": SEITE_URL},
    }
    tag = _tag(b, sprache)
    bild = b.get("bild")
    srcset = (f' srcset="{oben}{e(b["bild_klein"])} 480w, {oben}{e(bild)} 960w" sizes="(max-width: 1120px) 100vw, 1120px"'
              if b.get("bild_klein") else "")
    hero_bild = (f'<img class="beitrag-hero-bild" src="{oben}{e(bild)}"{srcset} alt="{e(feld(b, "bild_alt", sprache))}" width="960" height="640" fetchpriority="high">'
                 if bild else "")
    nachweis_text = feld(b, "bild_nachweis", sprache)
    nachweis = f'\n  <p class="beitrag-nachweis">{nachweis_text}</p>' if nachweis_text else ""
    inhalt_html = ""
    if len(inhalt) >= 3:
        punkte = "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in inhalt)
        inhalt_html = f'''
  <nav class="beitrag-inhalt" aria-labelledby="inhalt-titel">
    <h2 id="inhalt-titel">{ui['inhalt']}</h2>
    <ol>{punkte}</ol>
  </nav>'''
    # Die andere Fassung: hreflang für Suchmaschinen, und wer die andere
    # Sprache gewählt hat (endurance-lang), wird gleich dorthin geschickt –
    # bevor die Seite zu sehen ist. Suchmaschinen haben keine gespeicherte
    # Wahl und bleiben auf der Adresse, die sie aufgerufen haben.
    andere_sprache = "en" if sprache == "de" else "de"
    andere = (f"en/{b['slug']}.html" if sprache == "de" else f"../{b['slug']}.html") if zweisprachig else ""
    alternativen = ""
    umleitung = ""
    if zweisprachig:
        alternativen = (f'<link rel="alternate" hreflang="de" href="{url_von(b, "de")}">\n'
                        f'<link rel="alternate" hreflang="en" href="{url_von(b, "en")}">\n'
                        f'<link rel="alternate" hreflang="x-default" href="{url_von(b, "de")}">\n')
        umleitung = (f"<!-- Gewählte Sprache {andere_sprache.upper()}: gleich zur anderen Fassung (build_blog.py). -->\n"
                     f"<script>try {{ if (localStorage.getItem('endurance-lang') === '{andere_sprache}') "
                     f"{{ window.EE_UMLEITUNG = true; location.replace('{andere}' + location.hash); }} }} catch (e) {{ /* ignorieren */ }}</script>\n")
    locale_alt = f'\n<meta property="og:locale:alternate" content="{UI[andere_sprache]["locale"]}">' if zweisprachig else ""
    text_datei = f"scripts/blog_texte/{'en/' if sprache == 'en' else ''}{b['slug']}.html"

    return f"""<!DOCTYPE html>
<html lang="{sprache}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="tdm-reservation" content="1">
<!-- Erzeugt von scripts/build_blog.py aus blog.json und {e(text_datei)} – nicht von Hand ändern. -->
<title>{e(titel)} – Endurance Events</title>
<link rel="icon" href="{oben}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{oben}apple-touch-icon.png">
<link rel="manifest" href="{oben}manifest.webmanifest">
<link rel="canonical" href="{url}">
{alternativen}<meta name="theme-color" content="#0b1220">
{umleitung}{kopf}<meta name="description" content="{e(teaser)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Endurance Events">
<meta property="og:title" content="{e(titel)}">
<meta property="og:description" content="{e(teaser)}">
<meta property="og:locale" content="{ui['locale']}">{locale_alt}
<meta property="og:url" content="{url}">
<meta property="og:image" content="{e(bild_url)}">
<meta property="article:published_time" content="{e(b['datum'])}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<link rel="stylesheet" href="{oben}vendor/fonts/barlow.css">
<link rel="stylesheet" href="{oben}{site_css}">
<link rel="stylesheet" href="{oben}{blog_css}">
</head>
<body>

{kopfzeile}
<div class="lese-fortschritt" aria-hidden="true"><span id="lese-balken"></span></div>
<main class="blog-main">
<article class="beitrag">
  <a class="beitrag-zurueck" href="{oben}blog.html" id="blog-zurueck">{ui['zurueck']}</a>
  <header class="beitrag-hero{' ohne-bild' if not bild else ''}">
    {hero_bild}
    <div class="beitrag-hero-text">
      <div class="blog-meta">
        {tag}<span>{e(datum_text(b['datum'], sprache))}</span><span aria-hidden="true">·</span><span>{ui['lesezeit'].format(n=int(b.get('lesezeit_min') or 1))}</span>
      </div>
      <h1>{e(titel)}</h1>
    </div>
  </header>{nachweis}
  <div class="beitrag-spalte">{inhalt_html}
{text}
  <div class="beitrag-teilen">
    <span id="teilen-text">{ui['teilen_text']}</span>
    <button type="button" class="cta-knopf leise" id="teilen-knopf">{ui['teilen']}</button>
  </div>
  </div>{weitere}
</article>
</main>

<footer class="site-footer">
  <div class="seiten-footer">
    <a id="footer-impressum" href="{oben}impressum.html">{ui['impressum']}</a>
    <a id="footer-datenschutz" href="{oben}datenschutz.html">{ui['datenschutz']}</a>
  </div>
</footer>

<script defer src="{oben}vendor/firebase-10.14.1/firebase-app-compat.js"></script>
<script defer src="{oben}vendor/firebase-10.14.1/firebase-auth-compat.js"></script>
<script defer src="{oben}firebase-config.js"></script>
<script defer src="{oben}auth.js"></script>
<script defer src="{oben}{stats_js}"></script>
<script>
(function () {{
  // Diese Seite ist {'deutsch' if sprache == 'de' else 'englisch'}. Gibt es die andere Fassung, wechselt DE/EN
  // dorthin; sonst schaltet DE/EN nur die Bedienung um.
  if (window.EE_UMLEITUNG) return;
  var SEITE = '{sprache}', ANDERE = '{andere}';
  var T = {{
    de: {{ events: 'Events', clubs: 'Clubs', map: 'Karte', blog: 'Blog', back: '← Alle Beiträge', share: 'Beitrag teilen', share_text: 'Hat dir der Beitrag geholfen? Teil ihn mit deinen Trainingspartnern.', copied: 'Link kopiert', imprint: 'Impressum', privacy: 'Datenschutz' }},
    en: {{ events: 'Events', clubs: 'Clubs', map: 'Map', blog: 'Blog', back: '← All articles', share: 'Share article', share_text: 'Found this helpful? Share it with your training partners.', copied: 'Link copied', imprint: 'Legal notice', privacy: 'Privacy' }}
  }};
  function setze(lang) {{
    try {{ localStorage.setItem('endurance-lang', lang); }} catch (e) {{ /* ignorieren */ }}
    var t = T[lang];
    document.getElementById('nav-events').textContent = t.events;
    // Nur den Text setzen – das Schildchen „new“ bleibt stehen.
    document.getElementById('nav-clubs').firstChild.nodeValue = t.clubs;
    document.getElementById('nav-map').textContent = t.map;
    document.getElementById('nav-blog').textContent = t.blog;
    document.getElementById('blog-zurueck').textContent = t.back;
    document.getElementById('teilen-knopf').textContent = t.share;
    document.getElementById('teilen-text').textContent = t.share_text;
    document.getElementById('footer-impressum').textContent = t.imprint;
    document.getElementById('footer-datenschutz').textContent = t.privacy;
    document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.classList.toggle('active', b.dataset.lang === lang); }});
  }}
  var lang = SEITE;
  if (!ANDERE) {{
    try {{ var s = localStorage.getItem('endurance-lang'); if (s === 'de' || s === 'en') lang = s; }} catch (e) {{ /* ignorieren */ }}
  }}
  document.querySelectorAll('.lang-btn').forEach(function (b) {{ b.addEventListener('click', function () {{
    lang = b.dataset.lang;
    if (ANDERE && lang !== SEITE) {{
      try {{ localStorage.setItem('endurance-lang', lang); }} catch (e) {{ /* ignorieren */ }}
      location.href = ANDERE;
      return;
    }}
    setze(lang);
  }}); }});
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


def ziel(b: dict, sprache: str = "de") -> Path:
    return WURZEL / "blog" / ("en" if sprache == "en" else "") / f"{b['slug']}.html"


def seiten() -> list[tuple[dict, str]]:
    """Alle zu schreibenden Seiten: jeder Beitrag deutsch, dazu englisch, wo es ihn gibt."""
    alle = beitraege()
    return [(b, "de") for b in alle] + [(b, "en") for b in alle if hat_en(b)]


# Die Sitemap für Suchmaschinen (seit 04.11.2026, mit dem Livegang des
# Blogs): die öffentlichen Seiten plus jeder Beitrag, seit dem 10.11.2026
# auch in seiner englischen Fassung. Bewusst NICHT darin:
# admin.html, wartung.html (clubs.html seit dem Launch am 04.11.2026 drin).
# Ohne lastmod bei den festen Seiten – sonst änderte sich die Datei mit
# jedem Datenlauf ohne Inhalt; bei Beiträgen ist es ihr Datum.
SITEMAP = WURZEL / "sitemap.xml"
SITEMAP_SEITEN = ("", "events.html", "karte.html", "clubs.html", "blog.html", "impressum.html", "datenschutz.html")


def sitemap() -> str:
    alle = beitraege()
    neuester = max((b["datum"] for b in alle), default=None)
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<!-- Erzeugt von scripts/build_blog.py – nicht von Hand ändern. -->',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for pfad in SITEMAP_SEITEN:
        lastmod = f"<lastmod>{neuester}</lastmod>" if pfad == "blog.html" and neuester else ""
        zeilen.append(f"  <url><loc>{SEITE_URL}/{pfad}</loc>{lastmod}</url>")
    for b in sorted(alle, key=lambda x: x["datum"], reverse=True):
        zeilen.append(f"  <url><loc>{url_von(b, 'de')}</loc><lastmod>{b['datum']}</lastmod></url>")
        if hat_en(b):
            zeilen.append(f"  <url><loc>{url_von(b, 'en')}</loc><lastmod>{b['datum']}</lastmod></url>")
    zeilen.append("</urlset>")
    return "\n".join(zeilen) + "\n"


def verwaist() -> list[Path]:
    """Englische Seiten ohne englische Fassung in blog.json/Text (zum Aufräumen)."""
    soll = {ziel(b, "en") for b in beitraege() if hat_en(b)}
    ordner = WURZEL / "blog" / "en"
    return sorted(p for p in ordner.glob("*.html") if p not in soll) if ordner.exists() else []


def veraltet() -> list[str]:
    alt = [("en/" if sp == "en" else "") + b["slug"] for b, sp in seiten()
           if not ziel(b, sp).exists() or ziel(b, sp).read_text(encoding="utf-8") != seite(b, sp)]
    alt += [f"en/{p.stem} (verwaist)" for p in verwaist()]
    if not SITEMAP.exists() or SITEMAP.read_text(encoding="utf-8") != sitemap():
        alt.append("sitemap.xml")
    return alt


def schreibe() -> int:
    n = 0
    for b, sp in seiten():
        neu = seite(b, sp)
        p = ziel(b, sp)
        if not p.exists() or p.read_text(encoding="utf-8") != neu:
            p.parent.mkdir(exist_ok=True)
            p.write_text(neu, encoding="utf-8")
            n += 1
            print(f"  blog/{'en/' if sp == 'en' else ''}{b['slug']}.html geschrieben")
    for p in verwaist():
        p.unlink()
        n += 1
        print(f"  blog/en/{p.name} entfernt (keine englische Fassung mehr)")
    neu = sitemap()
    if not SITEMAP.exists() or SITEMAP.read_text(encoding="utf-8") != neu:
        SITEMAP.write_text(neu, encoding="utf-8")
        n += 1
        print("  sitemap.xml geschrieben")
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
