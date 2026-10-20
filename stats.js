// stats.js
// ========
// Die eigene Besucherstatistik - ohne Cookies, ohne Kennung, die den Tag
// überlebt, ohne fremden Dienst. Jede Seite lädt diese Datei (defer); sie
// schickt beim Laden EINEN Seitenaufruf und danach einzelne Aktionen
// (Event geöffnet, Veranstalter-Klick, Kalender, Teilen, Abo, Meldung,
// Suchbegriff, gesetzter Filter, Werbeplatz) an die Cloud Function `collect`
// (functions/index.js). Die zählt sie in Firestore (`hits`), rechnet sie
// stündlich zu Tageswerten zusammen (`stats_daily`), und admin.html
// zeigt sie - nur für den Betreiber.
//
// Was NICHT geschieht, und warum es hier steht, nicht nur in der
// Datenschutzerklärung:
//   - Kein Cookie, kein localStorage-Eintrag zur Wiedererkennung. Die
//     Sitzungskennung `s` lebt im sessionStorage des Tabs und stirbt mit
//     ihm; sie trennt nur "ein Besuch mit fünf Seiten" von "fünf Besuchen".
//   - Die IP-Adresse wird hier gar nicht angefasst - sie kommt beim Server
//     ohnehin an, der bildet daraus mit dem Browser-String und einem
//     täglich neuen Zufallsschlüssel einen Hash (Besucher des Tages) und
//     speichert die Adresse nie. Am nächsten Tag ist der Schlüssel ein
//     anderer, ein Profil über Tage ist damit nicht möglich.
//   - Keine Koordinaten, kein Suchfeld-Inhalt mit E-Mail-Adresse (Begriffe
//     mit @ werden verworfen), keine Rohadresse der Seite - nur der
//     Seitenname (index, events, karte …).
//   - Nichts auf localhost/127.0.0.1 (Rauchtest, lokaler Server), nichts
//     bei `navigator.webdriver`, bei Global Privacy Control / Do Not Track
//     und nicht, wenn jemand die Statistik für sein Gerät abgeschaltet
//     hat (Knopf in der Datenschutzerklärung: EnduranceStats.aus()).
//
// Öffentliche API:
//   EnduranceStats.event(name, props)      eine Aktion melden
//   EnduranceStats.filterParams(string)    Filterzustand (EF.toParams) melden -
//                                          geschickt wird nur, was sich
//                                          gegenüber dem letzten Stand ändert
//   EnduranceStats.anzeige(element, platz) einen WERBEPLATZ zählen: eine
//                                          Einblendung, sobald das Element
//                                          zur Hälfte eine Sekunde im Bild
//                                          war (einmal je Seitenaufruf), und
//                                          jeden Klick darauf - daraus
//                                          rechnet admin.html die Klickrate.
//                                          Gebaut am 14.10.2026, bevor es
//                                          Werbung gibt; NOCH RUFT ES KEINE
//                                          SEITE. Vor dem ersten Werbeplatz
//                                          den Abschnitt „Besucherstatistik"
//                                          in datenschutz.html ergänzen (er
//                                          zählt die Aktionen auf) - die
//                                          Datenschutzerklärung wurde am
//                                          14.10.2026 bewusst NICHT geändert.
//   EnduranceStats.aus() / .an() / .istAus()   Abschalten je Gerät
//   EnduranceStats.aktiv()                 ob diese Seite gerade sendet
//
// Die Liste EREIGNISSE steht als Kopie in functions/index.js
// (STATS_EREIGNISSE) - test_scraper_lib.py (test_statistik) vergleicht
// beide; was dort nicht steht, verwirft die Function.
(function (global) {
  'use strict';

  var ENDPOINT = 'https://europe-west1-endurance-5177a.cloudfunctions.net/collect';
  var SPEICHER_AUS = 'endurance-stats';       // 'aus' = für dieses Gerät abgeschaltet
  var SITZUNG_SCHLUESSEL = 'endurance-stats-sid';
  var MAX_JE_SEITE = 40;                      // mehr Treffer schickt eine Seite nicht
  var VERZOEGERUNG_MS = 1200;                 // Filter/Suche: erst nach einer Pause melden
  var EREIGNISSE = ['pv', 'detail', 'veranstalter', 'kalender', 'teilen', 'abo', 'melden', 'fehlt', 'suche', 'filter', 'standort', 'anzeige_sicht', 'anzeige_klick'];
  // Welche Zusatzangabe wie lang sein darf - alles andere fliegt.
  var PROP_LAENGE = { ev: 120, sp: 20, art: 20, rhythmus: 20, kategorie: 20, q: 60, k: 20, w: 60, platz: 40 };
  var ANZEIGE_SICHT_MS = 1000;                // so lange muss ein Werbeplatz im Bild sein

  var gesendet = 0;
  var sitzungImSpeicher = null;
  var gesehen = {};                 // detail: je Veranstaltung einmal je Seite
  var filterStand = null;           // zuletzt gemeldeter Filterzustand je Schlüssel
  var filterNeu = null;             // der neueste, noch nicht gemeldete
  var filterTimer = {};

  function istAus() {
    try { return localStorage.getItem(SPEICHER_AUS) === 'aus'; } catch (e) { return false; }
  }

  function stumm() {
    var host = (global.location && global.location.hostname) || '';
    if (!host || host === 'localhost' || host === '127.0.0.1' || host === '[::1]') return true;
    if (global.location.protocol === 'file:') return true;
    if (navigator.webdriver) return true;
    if (/bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|pingdom/i.test(navigator.userAgent || '')) return true;
    if (navigator.globalPrivacyControl === true) return true;
    if (navigator.doNotTrack === '1' || global.doNotTrack === '1') return true;
    return istAus();
  }

  function zufall() {
    var bytes = new Uint8Array(8);
    if (global.crypto && global.crypto.getRandomValues) {
      global.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    var s = '';
    for (var j = 0; j < bytes.length; j++) s += (bytes[j] < 16 ? '0' : '') + bytes[j].toString(16);
    return s;
  }

  // Die Sitzung des Tabs: ein Zufallswert, der mit dem Tab stirbt. Ohne
  // sessionStorage (privater Modus mancher Browser) gilt er nur für diese
  // eine Seite - dann zählt jeder Aufruf als eigener Besuch.
  function sitzung() {
    if (sitzungImSpeicher) return sitzungImSpeicher;
    try {
      var s = sessionStorage.getItem(SITZUNG_SCHLUESSEL);
      if (s && /^[0-9a-f]{16}$/.test(s)) {
        sitzungImSpeicher = { id: s, neu: false };
      } else {
        s = zufall();
        sessionStorage.setItem(SITZUNG_SCHLUESSEL, s);
        sitzungImSpeicher = { id: s, neu: true };
      }
    } catch (e) {
      sitzungImSpeicher = { id: zufall(), neu: true };
    }
    return sitzungImSpeicher;
  }

  function seite() {
    var p = (global.location.pathname || '').split('/').pop() || 'index.html';
    p = p.replace(/\.html?$/i, '').toLowerCase();
    return p || 'index';
  }

  function referrerHost() {
    try {
      if (!document.referrer) return '';
      var u = new URL(document.referrer);
      if (u.hostname === global.location.hostname) return '';
      return u.hostname.replace(/^www\./, '').toLowerCase().slice(0, 100);
    } catch (e) { return ''; }
  }

  function kurz(wert, max) {
    if (typeof wert !== 'string') return '';
    return wert.trim().slice(0, max);
  }

  function kampagne() {
    var p;
    try { p = new URLSearchParams(global.location.search); } catch (e) { return {}; }
    return {
      q: kurz(p.get('utm_source'), 60).toLowerCase(),
      m: kurz(p.get('utm_medium'), 60).toLowerCase(),
      c: kurz(p.get('utm_campaign'), 60).toLowerCase()
    };
  }

  // Dieselben Grenzen wie die Seite selbst: unter 700 px Kacheln statt
  // Tabelle (Handy), ab 1024 px die Breite eines Laptops.
  function geraet() {
    var w = global.innerWidth || (global.screen && global.screen.width) || 0;
    return w < 700 ? 'handy' : w < 1024 ? 'tablet' : 'rechner';
  }

  function browserUndSystem() {
    var ua = navigator.userAgent || '';
    var br = '', os = '';
    var uad = navigator.userAgentData;
    // Der eingebaute Browser der Instagram-App (14.10.2026, Marketing
    // über den Account „AusdauerMaschine"): Er nennt sich im Browser-String
    // "Instagram 3xx.x", schickt aber oft keinen Referrer. Als eigener
    // „Browser" gezählt, ordnet stats_aggregate.js den Besuch dem Kanal
    // Instagram zu, auch wenn der Link ohne utm_source geteilt wurde.
    if (/\bInstagram\b/.test(ua)) br = 'Instagram';
    else if (uad && uad.brands && uad.brands.length) {
      var marken = uad.brands.map(function (b) { return b.brand; }).join(' ');
      if (/Edge/i.test(marken)) br = 'Edge';
      else if (/Opera|OPR/i.test(marken)) br = 'Opera';
      else if (/Samsung/i.test(marken)) br = 'Samsung Internet';
      else if (/Chrome|Chromium/i.test(marken)) br = 'Chrome';
      var pf = uad.platform || '';
      if (/Windows/i.test(pf)) os = 'Windows';
      else if (/mac/i.test(pf)) os = 'macOS';
      else if (/Android/i.test(pf)) os = 'Android';
      else if (/Chrome ?OS/i.test(pf)) os = 'Chrome OS';
      else if (/Linux/i.test(pf)) os = 'Linux';
      else if (/iOS/i.test(pf)) os = 'iOS';
    }
    if (!br) {
      if (/Edg(e|A|iOS)?\//.test(ua)) br = 'Edge';
      else if (/OPR\/|Opera/.test(ua)) br = 'Opera';
      else if (/SamsungBrowser/.test(ua)) br = 'Samsung Internet';
      else if (/Firefox\/|FxiOS/.test(ua)) br = 'Firefox';
      else if (/Chrome\/|CriOS\//.test(ua)) br = 'Chrome';
      else if (/Safari\//.test(ua)) br = 'Safari';
      else br = 'Sonstige';
    }
    if (!os) {
      // iPadOS meldet sich als "Macintosh" - mit Touch ist es ein iPad.
      if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) os = 'iOS';
      else if (/Android/.test(ua)) os = 'Android';
      else if (/Windows/.test(ua)) os = 'Windows';
      else if (/Mac OS X|Macintosh/.test(ua)) os = 'macOS';
      else if (/CrOS/.test(ua)) os = 'Chrome OS';
      else if (/Linux/.test(ua)) os = 'Linux';
      else os = 'Sonstige';
    }
    return { br: br, os: os };
  }

  function zeitzone() {
    try { return kurz(Intl.DateTimeFormat().resolvedOptions().timeZone, 40); } catch (e) { return ''; }
  }

  function uebertrage(daten) {
    if (gesendet >= MAX_JE_SEITE) return;
    gesendet++;
    var body;
    try { body = JSON.stringify(daten); } catch (e) { return; }
    // text/plain: eine "einfache" Anfrage ohne Vorab-Anfrage (Preflight),
    // und sendBeacon überlebt auch den Seitenwechsel.
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'text/plain' }))) return;
    } catch (e) { /* weiter mit fetch */ }
    try {
      fetch(ENDPOINT, {
        method: 'POST', body: body, keepalive: true, mode: 'cors', credentials: 'omit',
        headers: { 'Content-Type': 'text/plain' }
      }).catch(function () { /* Statistik ist Beiwerk - kein Fehler für die Seite */ });
    } catch (e) { /* ignorieren */ }
  }

  function seitenaufruf() {
    if (stumm()) return;
    var sz = sitzung();
    var k = kampagne();
    var bs = browserUndSystem();
    var html = document.documentElement;
    var sl = (html.getAttribute('lang') || '').slice(0, 2).toLowerCase();
    uebertrage({
      e: 'pv',
      p: seite(),
      r: referrerHost(),
      q: k.q, m: k.m, c: k.c,
      tz: zeitzone(),
      la: kurz(navigator.language, 12),
      sl: sl === 'en' ? 'en' : 'de',
      th: html.getAttribute('data-theme') === 'light' ? 'light' : 'dark',
      dv: geraet(),
      br: bs.br, os: bs.os,
      s: sz.id,
      n: sz.neu
    });
  }

  function saubereProps(pr) {
    var out = {};
    var hat = false;
    if (!pr || typeof pr !== 'object') return null;
    Object.keys(PROP_LAENGE).forEach(function (key) {
      var wert = pr[key];
      if (typeof wert === 'number') wert = String(wert);
      if (typeof wert !== 'string') return;
      wert = wert.trim().slice(0, PROP_LAENGE[key]);
      if (!wert) return;
      out[key] = wert;
      hat = true;
    });
    return hat ? out : null;
  }

  function event(name, pr) {
    if (EREIGNISSE.indexOf(name) < 0 || name === 'pv') return;
    if (stumm()) return;
    var props = saubereProps(pr);
    if (name === 'detail') {
      // Dieselbe Veranstaltung noch einmal (Strecken-Pille, Sprachwechsel,
      // Neuzeichnen) ist kein zweites Öffnen.
      var schluessel = props && props.ev ? props.ev : '';
      if (gesehen[schluessel]) return;
      gesehen[schluessel] = true;
    }
    if (name === 'suche') {
      if (!props || !props.q || props.q.length < 2 || props.q.indexOf('@') >= 0) return;
      props.q = props.q.toLowerCase();
    }
    var daten = { e: name, p: seite(), s: sitzung().id };
    if (props) daten.pr = props;
    uebertrage(daten);
  }

  // ---------- Filter ----------
  // Der Zustand kommt als Parameterkette (EF.toParams(state).toString()),
  // genau das, was auch in der Adresse steht. Gemeldet wird je Schlüssel
  // nur der UNTERSCHIED zum letzten gemeldeten Stand - und erst nach einer
  // Pause, damit "Laufen, Fahrrad, Schwimmen" als drei Werte ankommt und
  // nicht jeder Tastendruck im Suchfeld als eigener Begriff.
  var LISTEN_SCHLUESSEL = { sportart: 'sportart', land: 'land', art2: 'kategorie', kat: 'laenge', standort: 'ort' };
  var EINZEL_SCHLUESSEL = { zeitraum: 'zeitraum', umkreis: 'umkreis', sort: 'sortierung', gruppiert: 'gruppiert' };

  function parseParams(str) {
    var out = {};
    try {
      new URLSearchParams(str || '').forEach(function (wert, key) { out[key] = wert; });
    } catch (e) { /* leer */ }
    return out;
  }

  function meldeUnterschied(key) {
    var alt = filterStand[key] || '';
    var neu = filterNeu[key] || '';
    filterStand[key] = neu;
    if (alt === neu) return;
    if (key === 's' || key === 'q') {
      if (neu) event('suche', { q: neu });
      return;
    }
    if (key === 'ort') {
      if (neu) event('standort');
      return;
    }
    if (key === 'tage') {
      if (neu) event('filter', { k: 'zeitraum', w: 'tage' });
      return;
    }
    if (key === 'kmmin' || key === 'kmmax') {
      if (neu) event('filter', { k: 'laenge', w: key === 'kmmin' ? 'ab ' + neu + ' km' : 'bis ' + neu + ' km' });
      return;
    }
    if (LISTEN_SCHLUESSEL[key]) {
      var vorher = alt ? alt.split(',') : [];
      var dazu = (neu ? neu.split(',') : []).filter(function (w) { return w && vorher.indexOf(w) < 0; });
      dazu.slice(0, 5).forEach(function (w) { event('filter', { k: LISTEN_SCHLUESSEL[key], w: w }); });
      return;
    }
    if (EINZEL_SCHLUESSEL[key] && neu) event('filter', { k: EINZEL_SCHLUESSEL[key], w: neu });
  }

  function filterParams(str) {
    if (stumm()) return;
    if (filterStand === null) filterStand = parseParams(global.location.search);
    filterNeu = parseParams(str);
    var alle = {};
    Object.keys(filterStand).forEach(function (k) { alle[k] = true; });
    Object.keys(filterNeu).forEach(function (k) { alle[k] = true; });
    Object.keys(alle).forEach(function (key) {
      if ((filterStand[key] || '') === (filterNeu[key] || '')) return;
      if (filterTimer[key]) clearTimeout(filterTimer[key]);
      filterTimer[key] = setTimeout(function () {
        filterTimer[key] = null;
        meldeUnterschied(key);
      }, VERZOEGERUNG_MS);
    });
  }

  // ---------- Werbeplätze ----------
  // Eine Einblendung zählt, wenn mindestens die Hälfte des Elements eine
  // Sekunde lang im Bild war (so misst es auch der IAB-Standard für
  // „viewable impressions") - einmal je Seitenaufruf und Platz; ein
  // Klick auf irgendetwas im Element zählt als Klick (auch mittlere
  // Maustaste). Ohne IntersectionObserver (sehr alte Browser) zählt die
  // Einblendung beim Einhängen.
  var anzeigeGesehen = {};
  function anzeige(element, platz) {
    if (!element || typeof platz !== 'string' || !platz || stumm()) return;
    var key = kurz(platz, PROP_LAENGE.platz);
    function sicht() {
      if (anzeigeGesehen[key]) return;
      anzeigeGesehen[key] = true;
      event('anzeige_sicht', { platz: key });
    }
    if (global.IntersectionObserver) {
      var timer = null;
      var beobachter = new IntersectionObserver(function (eintraege) {
        eintraege.forEach(function (x) {
          if (x.isIntersecting && x.intersectionRatio >= 0.5) {
            if (!timer) timer = setTimeout(function () { sicht(); beobachter.disconnect(); }, ANZEIGE_SICHT_MS);
          } else if (timer) {
            clearTimeout(timer); timer = null;
          }
        });
      }, { threshold: [0.5] });
      beobachter.observe(element);
    } else {
      sicht();
    }
    element.addEventListener('click', function () { event('anzeige_klick', { platz: key }); });
    element.addEventListener('auxclick', function (ev) { if (ev.button === 1) event('anzeige_klick', { platz: key }); });
  }

  global.EnduranceStats = {
    event: event,
    filterParams: filterParams,
    anzeige: anzeige,
    aus: function () { try { localStorage.setItem(SPEICHER_AUS, 'aus'); } catch (e) { /* ignorieren */ } },
    an: function () { try { localStorage.removeItem(SPEICHER_AUS); } catch (e) { /* ignorieren */ } },
    istAus: istAus,
    aktiv: function () { return !stumm(); }
  };

  // Der Seitenaufruf nach dem Aufbau der Seite - dann stehen Sprache
  // (setLanguage setzt <html lang>) und Farbschema fest. setTimeout(0),
  // weil die Inline-Skripte der Seiten im selben Durchgang noch laufen.
  function start() { setTimeout(seitenaufruf, 0); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
