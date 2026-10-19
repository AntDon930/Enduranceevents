// Anmeldesperre für die Vorschau unter /vorschau/ (seit 19.10.2026, vom
// Nutzer gewünscht: „eine Anmeldesperre wie bei admin.html … bei der
// Vorschau"). pages.yml kopiert diese Datei beim Deploy nach vorschau/ und
// setzt sie als erstes Skript in den <head> jeder Vorschau-Seite. Im
// Clubs-Branch steht sie nicht; beim Launch fällt sie mit den
// Vorschau-Schritten weg.
//
// Wer darf: wer angemeldet ist UND in Firestore unter admins/<uid> steht –
// dieselbe Regel wie admin.html (istAdmin() in firestore.rules; das eigene
// Dokument darf jede/r abfragen, die Liste nie). Abgefragt per REST mit dem
// ID-Token, ohne das 344-KB-Firestore-SDK. Die Anmeldung gilt für die ganze
// Domain: Wer auf endurance-events.de angemeldet ist, ist es hier auch.
//
// GRENZE: Das ist ein Sichtschutz im Browser, kein Tresor. GitHub Pages
// liefert jede Datei an jeden aus – wer die Adresse kennt und Quelltext oder
// Datendateien direkt abruft, bekommt sie. Gesperrt ist, was die Seite ZEIGT.
//
// Fail-closed: Bis das Konto bestätigt ist, ist alles außer der Sperre
// unsichtbar (opacity, nicht display – sonst misst Leaflet auf karte.html
// einen Container ohne Größe) und nicht bedienbar (inert, pointer-events).
// Lädt Firebase nicht, bleibt die Seite zu.
(function () {
  'use strict';

  var FIREBASE_PFAD = 'vendor/firebase-10.14.1/';
  var root = document.documentElement;
  var skript = document.currentScript;
  var basis = skript && skript.src ? skript.src : location.href;
  var en = false;
  try { en = localStorage.getItem('endurance-lang') === 'en'; } catch (e) { /* ignorieren */ }

  var T = en ? {
    titel: 'Preview',
    text: 'This preview is only for the site operator. Sign in with your admin account.',
    google: 'Sign in with Google',
    email: 'Signed up with email? Sign in on endurance-events.de and reload this page.',
    startseite: 'To endurance-events.de',
    pruefen: 'Checking access …',
    kein: 'This account has no access to the preview.',
    uid: 'Account ID:',
    abmelden: 'Sign out',
    fehler: 'Sign-in is not reachable right now.',
    neu: 'Reload'
  } : {
    titel: 'Vorschau',
    text: 'Diese Vorschau ist nur für den Betreiber. Melde dich mit deinem Admin-Konto an.',
    google: 'Mit Google anmelden',
    email: 'Mit E-Mail registriert? Melde dich auf endurance-events.de an und lade diese Seite neu.',
    startseite: 'Zu endurance-events.de',
    pruefen: 'Zugang wird geprüft …',
    kein: 'Dieses Konto hat keinen Zugang zur Vorschau.',
    uid: 'Konto-ID:',
    abmelden: 'Abmelden',
    fehler: 'Die Anmeldung ist gerade nicht erreichbar.',
    neu: 'Neu laden'
  };

  // Sofort zu – noch bevor <body> existiert.
  root.classList.add('vs-zu');
  var stil = document.createElement('style');
  stil.textContent =
    'html.vs-zu body{overflow:hidden!important}' +
    'html.vs-zu body>:not(#vs-sperre){opacity:0!important;pointer-events:none!important}' +
    '#vs-sperre{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;' +
    'justify-content:center;padding:16px;background:#0B1B33;color:#EDF1F7;' +
    'font:16px/1.5 Barlow,system-ui,-apple-system,"Segoe UI",sans-serif}' +
    '#vs-sperre .vs-karte{max-width:420px;width:100%;background:#13233D;border:1px solid #2A3A56;' +
    'border-radius:16px;padding:24px}' +
    '#vs-sperre h1{margin:0 0 8px;font:700 30px/1.1 "Barlow Condensed",Barlow,system-ui,sans-serif}' +
    '#vs-sperre p{margin:0 0 14px}' +
    '#vs-sperre .vs-klein{font-size:14px;color:#B9C3D3}' +
    '#vs-sperre code{word-break:break-all;font-size:13px}' +
    '#vs-sperre button,#vs-sperre a.vs-knopf{display:inline-flex;align-items:center;min-height:44px;' +
    'padding:0 16px;margin:0 8px 8px 0;border-radius:10px;border:1px solid #2A3A56;background:#1C2C48;' +
    'color:#EDF1F7;font:500 15px/1 Barlow,system-ui,sans-serif;text-decoration:none;cursor:pointer}' +
    '#vs-sperre button.vs-haupt{background:#EDF1F7;color:#0B1B33;border-color:#EDF1F7}';
  (document.head || root).appendChild(stil);

  var sperre = null;
  var auth = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function zu(html) {
    root.classList.add('vs-zu');
    if (!sperre) {
      sperre = document.createElement('div');
      sperre.id = 'vs-sperre';
      sperre.setAttribute('role', 'dialog');
      sperre.setAttribute('aria-modal', 'true');
      sperre.setAttribute('aria-labelledby', 'vs-titel');
    }
    if (sperre.parentNode !== document.body) document.body.appendChild(sperre);
    Array.prototype.forEach.call(document.body.children, function (el) {
      if (el !== sperre) el.setAttribute('inert', '');
    });
    sperre.innerHTML = '<div class="vs-karte"><h1 id="vs-titel">' + esc(T.titel) + '</h1>' + html + '</div>';
  }

  function auf() {
    root.classList.remove('vs-zu');
    if (sperre && sperre.parentNode) sperre.parentNode.removeChild(sperre);
    Array.prototype.forEach.call(document.body.children, function (el) { el.removeAttribute('inert'); });
  }

  function startseite() {
    return '<a class="vs-knopf" href="/">' + esc(T.startseite) + '</a>';
  }

  function zeigeLogin() {
    zu('<p>' + esc(T.text) + '</p>' +
      '<p><button type="button" class="vs-haupt" id="vs-google">' + esc(T.google) + '</button>' + startseite() + '</p>' +
      '<p class="vs-klein">' + esc(T.email) + '</p>');
    document.getElementById('vs-google').addEventListener('click', mitGoogle);
  }

  function zeigeKeinZugang(uid) {
    zu('<p>' + esc(T.kein) + '</p><p class="vs-klein">' + esc(T.uid) + ' <code>' + esc(uid) + '</code></p>' +
      '<p><button type="button" id="vs-abmelden">' + esc(T.abmelden) + '</button>' + startseite() + '</p>');
    document.getElementById('vs-abmelden').addEventListener('click', function () { auth.signOut(); });
  }

  function zeigeFehler() {
    zu('<p>' + esc(T.fehler) + '</p><p><button type="button" class="vs-haupt" id="vs-neu">' + esc(T.neu) +
      '</button>' + startseite() + '</p>');
    document.getElementById('vs-neu').addEventListener('click', function () { location.reload(); });
  }

  function mitGoogle() {
    var provider = new window.firebase.auth.GoogleAuthProvider();
    auth.signInWithPopup(provider).catch(function (err) {
      var code = err && err.code;
      // Popup gesperrt (Safari, In-App-Browser): über die Weiterleitung –
      // derselbe Ausweg wie in auth.js. Nach der Rückkehr meldet
      // onAuthStateChanged das Konto von selbst.
      if (code === 'auth/popup-blocked' || code === 'auth/operation-not-supported-in-this-environment') {
        auth.signInWithRedirect(provider).catch(zeigeFehler);
      }
    });
  }

  function ladeSkript(pfad) {
    return new Promise(function (ok, fehler) {
      var s = document.createElement('script');
      s.src = new URL(pfad, basis).href;
      s.onload = ok;
      s.onerror = function () { fehler(new Error(pfad)); };
      document.head.appendChild(s);
    });
  }

  // Die meisten Vorschau-Seiten laden Firebase selbst (defer, also vor
  // DOMContentLoaded) – dann wird es benutzt, nicht ein zweites Mal geladen.
  // Impressum, Datenschutz und Wartung laden es nicht.
  function firebaseBereit() {
    var kette = Promise.resolve();
    if (!window.firebase) kette = kette.then(function () { return ladeSkript(FIREBASE_PFAD + 'firebase-app-compat.js'); });
    kette = kette.then(function () { if (!window.firebase.auth) return ladeSkript(FIREBASE_PFAD + 'firebase-auth-compat.js'); });
    kette = kette.then(function () { if (!window.FIREBASE_CONFIG) return ladeSkript('firebase-config.js'); });
    return kette.then(function () {
      if (!window.firebase.apps.length) window.firebase.initializeApp(window.FIREBASE_CONFIG);
      return window.firebase.auth();
    });
  }

  function istAdmin(user) {
    return user.getIdToken().then(function (token) {
      var projekt = window.firebase.app().options.projectId;
      var url = 'https://firestore.googleapis.com/v1/projects/' + encodeURIComponent(projekt) +
        '/databases/(default)/documents/admins/' + encodeURIComponent(user.uid);
      return fetch(url, { headers: { Authorization: 'Bearer ' + token }, cache: 'no-store' });
    }).then(function (antwort) {
      if (antwort.ok) return true;
      if (antwort.status === 403 || antwort.status === 404) return false;
      throw new Error('HTTP ' + antwort.status);
    });
  }

  function start() {
    zu('<p class="vs-klein">' + esc(T.pruefen) + '</p>');
    firebaseBereit().then(function (a) {
      auth = a;
      auth.onAuthStateChanged(function (user) {
        if (!user) { zeigeLogin(); return; }
        zu('<p class="vs-klein">' + esc(T.pruefen) + '</p>');
        istAdmin(user).then(function (ja) {
          if (ja) auf(); else zeigeKeinZugang(user.uid);
        }, zeigeFehler);
      });
    }, zeigeFehler);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
