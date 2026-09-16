// auth.js
// =========
// Gemeinsames Login/Registrierung-Modul für index.html, events.html und
// karte.html. Baut den "Anmelden"-Button (neben dem Home-Button) und ein
// Login/Registrierungs-Modal (Google + E-Mail/Passwort mit
// Bestätigungs-E-Mail). "Mit Apple anmelden" ist ausgeblendet, siehe
// SHOW_APPLE_SIGNIN weiter unten - Apple Sign-In erfordert ein
// kostenpflichtiges Apple-Developer-Konto, das für dieses Projekt nicht
// existiert.
//
// Voraussetzung: firebase-config.js sowie die Firebase-compat-SDKs
// (firebase-app-compat.js, firebase-auth-compat.js,
// firebase-firestore-compat.js) müssen VOR diesem Skript geladen sein.
// Solange window.FIREBASE_CONFIGURED === false ist (Platzhalter-Config),
// zeigt der Login-Button einen freundlichen "noch nicht eingerichtet"-
// Hinweis statt kaputter Buttons oder Konsolenfehlern.
//
// Öffentliche API (für events.html's "Benachrichtige mich"-Funktion):
//   window.EndauranceAuth.getUser()                 -> firebase.User | null
//   window.EndauranceAuth.onAuthChange(cb)           -> cb(user) bei jeder Änderung
//   window.EndauranceAuth.openModal('login'|'register')
//   window.EndauranceAuth.reportEventError({event, kategorie, beschreibung})
//                                                    -> Promise<void>
//     (meldet einen Datenfehler; meldet bei Bedarf anonym an)
//   window.EndauranceAuth.saveFilterSubscription(filters) -> Promise<void>
//     (filters: einfaches, serialisierbares Objekt der aktuell aktiven
//     Filter OHNE das Datum - siehe events.html)

(function () {
  'use strict';

  const I18N = {
    de: {
      login: 'Anmelden',
      loggedInShort: (email) => email.length > 22 ? email.slice(0, 20) + '…' : email,
      logout: 'Abmelden',
      modalTitleLogin: 'Anmelden',
      modalTitleRegister: 'Registrieren',
      googleBtn: 'Mit Google anmelden',
      appleBtn: 'Mit Apple anmelden',
      appleSoon: 'Bald verfügbar – erfordert ein Apple-Developer-Konto',
      or: 'oder',
      nameLabel: 'Name (optional)',
      emailLabel: 'E-Mail',
      emailPlaceholder: 'deine@email.de',
      passwordLabel: 'Passwort',
      passwordConfirmLabel: 'Passwort bestätigen',
      submitLogin: 'Anmelden',
      submitRegister: 'Registrieren',
      noAccount: 'Noch kein Konto?',
      hasAccount: 'Schon ein Konto?',
      switchToRegister: 'Registrieren',
      switchToLogin: 'Anmelden',
      close: 'Schließen',
      notConfigured: 'Login ist in dieser Vorschau noch nicht eingerichtet (Firebase-Konfiguration fehlt) – siehe README.md.',
      passwordMismatch: 'Die Passwörter stimmen nicht überein.',
      passwordTooShort: 'Das Passwort muss mindestens 6 Zeichen haben.',
      verifyEmailSent: 'Konto erstellt! Wir haben dir eine Bestätigungs-E-Mail geschickt.',
      emailNotVerifiedBanner: 'Bitte bestätige deine E-Mail-Adresse (Link in der Mail, die wir dir geschickt haben).',
      resendVerification: 'Erneut senden',
      verificationResent: 'Bestätigungsmail erneut gesendet.',
      errorPrefix: 'Fehler: ',
      'auth/email-already-in-use': 'Für diese E-Mail existiert bereits ein Konto.',
      'auth/invalid-email': 'Ungültige E-Mail-Adresse.',
      'auth/weak-password': 'Das Passwort ist zu schwach (mind. 6 Zeichen).',
      'auth/wrong-password': 'Falsches Passwort.',
      'auth/invalid-credential': 'E-Mail oder Passwort ist falsch.',
      'auth/user-not-found': 'Kein Konto mit dieser E-Mail gefunden.',
      'auth/popup-closed-by-user': 'Anmeldefenster wurde geschlossen.',
      'auth/network-request-failed': 'Netzwerkfehler – bitte Verbindung prüfen.',
      'auth/account-exists-with-different-credential': 'Für diese E-Mail gibt es schon ein Konto mit einer anderen Anmeldeart. Bitte so anmelden wie beim ersten Mal.',
      'auth/unauthorized-domain': 'Diese Adresse ist in Firebase nicht als erlaubte Domain eingetragen.',
      redirecting: 'Weiterleitung zu Google …',
      inAppBrowserHint: 'Die Anmeldung klappt in diesem eingebetteten Browser (z. B. in Instagram oder Facebook) nicht. Bitte öffne die Seite im normalen Browser – über das Menü „…“ oben rechts, „In Safari/Chrome öffnen“.'
    },
    en: {
      login: 'Sign in',
      loggedInShort: (email) => email.length > 22 ? email.slice(0, 20) + '…' : email,
      logout: 'Sign out',
      modalTitleLogin: 'Sign in',
      modalTitleRegister: 'Register',
      googleBtn: 'Sign in with Google',
      appleBtn: 'Sign in with Apple',
      appleSoon: 'Coming soon – requires an Apple Developer account',
      or: 'or',
      nameLabel: 'Name (optional)',
      emailLabel: 'Email',
      emailPlaceholder: 'you@email.com',
      passwordLabel: 'Password',
      passwordConfirmLabel: 'Confirm password',
      submitLogin: 'Sign in',
      submitRegister: 'Register',
      noAccount: "Don't have an account?",
      hasAccount: 'Already have an account?',
      switchToRegister: 'Register',
      switchToLogin: 'Sign in',
      close: 'Close',
      notConfigured: 'Login is not set up in this preview yet (missing Firebase configuration) – see README.md.',
      passwordMismatch: 'Passwords do not match.',
      passwordTooShort: 'Password must be at least 6 characters.',
      verifyEmailSent: 'Account created! We sent you a verification email.',
      emailNotVerifiedBanner: 'Please verify your email address (link in the email we sent you).',
      resendVerification: 'Resend',
      verificationResent: 'Verification email resent.',
      errorPrefix: 'Error: ',
      'auth/email-already-in-use': 'An account with this email already exists.',
      'auth/invalid-email': 'Invalid email address.',
      'auth/weak-password': 'Password is too weak (min. 6 characters).',
      'auth/wrong-password': 'Wrong password.',
      'auth/invalid-credential': 'Email or password is incorrect.',
      'auth/user-not-found': 'No account found for this email.',
      'auth/popup-closed-by-user': 'Sign-in window was closed.',
      'auth/network-request-failed': 'Network error – please check your connection.',
      'auth/account-exists-with-different-credential': 'An account with this email already exists using a different sign-in method. Please use the one you signed up with.',
      'auth/unauthorized-domain': 'This address is not listed as an authorised domain in Firebase.',
      redirecting: 'Redirecting to Google …',
      inAppBrowserHint: 'Signing in does not work inside this embedded browser (e.g. Instagram or Facebook). Please open the page in your normal browser – via the “…” menu at the top right, “Open in Safari/Chrome”.'
    }
  };

  function currentLang() {
    try {
      const saved = localStorage.getItem('endurance-lang');
      if (saved === 'de' || saved === 'en') return saved;
    } catch (e) { /* localStorage evtl. nicht verfügbar */ }
    return 'de';
  }

  function t(key, ...args) {
    const entry = I18N[currentLang()][key];
    if (typeof entry === 'function') return entry(...args);
    return entry || key;
  }

  function errorMessage(err) {
    const code = err && err.code;
    if (code && I18N[currentLang()][code]) return I18N[currentLang()][code];
    return t('errorPrefix') + (err && err.message ? err.message : String(err));
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------------------------------------------------------------------
  // Firebase-Init (best-effort; bleibt inaktiv, solange nicht konfiguriert)
  // ---------------------------------------------------------------------
  const configured = !!(window.FIREBASE_CONFIGURED && window.firebase);
  let auth = null;
  if (configured) {
    try {
      firebase.initializeApp(window.FIREBASE_CONFIG);
      auth = firebase.auth();
    } catch (e) {
      console.error('Firebase-Initialisierung fehlgeschlagen:', e);
    }
  }

  // ---------------------------------------------------------------------
  // Firestore wird NACHGELADEN, nicht mitgeladen
  // ---------------------------------------------------------------------
  // firebase-firestore-compat.js ist 344 KB (102 KB gzip) - mehr als das
  // Doppelte von Auth und App zusammen. Gebraucht wird es an genau zwei
  // Stellen, und beide sind Nutzerhandlungen: ein Filterabo speichern und
  // eine Fehlermeldung abschicken. Als <script> im HTML verzoegerte es
  // dagegen JEDEN Seitenaufruf, weil das Inline-Skript der Liste erst
  // nach allen vorangehenden Skripten laeuft - events.json wurde also
  // erst abgerufen, nachdem eine halbe Megabyte Firebase da war.
  //
  // Deshalb: hier nachladen, wenn es zum ersten Mal gebraucht wird.
  // prepareFirestore() startet das vorausschauend (Melde-Dialog geoeffnet,
  // Abo-Box sichtbar), damit beim Absenden nichts mehr zu warten ist.
  const FIRESTORE_SDK_URL =
    'https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore-compat.js';
  let dbPromise = null;

  function ensureDb() {
    if (!configured || !auth) return Promise.reject(new Error('not-configured'));
    if (!dbPromise) {
      const sdkGeladen = (window.firebase && firebase.firestore)
        ? Promise.resolve()
        : new Promise((resolve, reject) => {
            const tag = document.createElement('script');
            tag.src = FIRESTORE_SDK_URL;
            tag.async = true;
            tag.onload = resolve;
            tag.onerror = () => reject(new Error('firestore-sdk'));
            document.head.appendChild(tag);
          });
      dbPromise = sdkGeladen.then(() => firebase.firestore());
      // Einen Fehlschlag nicht einbrennen: beim naechsten Versuch (z. B.
      // nach kurzem Netzausfall) soll wieder geladen werden duerfen.
      dbPromise.catch(() => { dbPromise = null; });
    }
    return dbPromise;
  }

  const authChangeListeners = [];
  function notifyAuthChange(user) {
    authChangeListeners.forEach(cb => { try { cb(user); } catch (e) { console.error(e); } });
  }

  // "Angemeldet" heißt hier: mit einem echten Konto, nicht mit der
  // anonymen Kennung, die reportEventError im Hintergrund anlegt.
  //
  // Diese Unterscheidung ist nicht kosmetisch. Wer einen Datenfehler
  // meldet, ist danach aus Firebase-Sicht angemeldet - ohne E-Mail-
  // Adresse. Ohne die Prüfung bot die Seite demselben Menschen kurz
  // darauf "Benachrichtigen, sobald verfügbar" an, speicherte ein Abo
  // mit email: null und meldete "Gespeichert!". Eine E-Mail hätte es
  // dafür nie geben können: Die Cloud Function hätte to: null in die
  // mail-Collection geschrieben. Ein stiller Fehlschlag, den niemand
  // bemerkt - deshalb gilt eine anonyme Kennung überall dort, wo es um
  // Konto und Benachrichtigung geht, als "nicht angemeldet".
  function isRealUser(user) {
    return !!(user && !user.isAnonymous);
  }

  // ---------------------------------------------------------------------
  // UI aufbauen: Button (im Mount-Punkt #auth-mount) + Modal (an <body>)
  // ---------------------------------------------------------------------
  const STYLE = `
    .ee-auth-btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 5px 14px; border-radius: 999px; border: none;
      background: #fff; color: #14315e; cursor: pointer;
      font-size: 0.8rem; font-weight: 700;
    }
    .ee-auth-btn:hover { opacity: 0.92; }
    .ee-auth-user { display: inline-flex; align-items: center; gap: 8px; }
    .ee-auth-user button {
      padding: 4px 11px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.55);
      background: rgba(255,255,255,0.14); color: #fff; cursor: pointer; font-size: 0.75rem; font-weight: 600;
    }
    .ee-modal-overlay {
      position: fixed; inset: 0; background: rgba(10,14,20,0.55);
      display: flex; align-items: center; justify-content: center;
      z-index: 2000; padding: 16px;
    }
    .ee-modal-overlay[hidden] { display: none; }
    .ee-modal {
      background: var(--panel, #fff); color: var(--text, #1c1f24);
      border-radius: 14px; padding: 28px 26px; width: 100%; max-width: 380px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.35); position: relative;
      max-height: 90vh; overflow-y: auto;
    }
    .ee-modal h2 { margin: 0 0 18px; font-size: 1.3rem; text-align: center; }
    .ee-modal-close {
      position: absolute; top: 12px; right: 14px; border: none; background: transparent;
      font-size: 1.3rem; cursor: pointer; color: var(--text-muted, #6b7280); line-height: 1;
    }
    .ee-social-btn {
      display: flex; align-items: center; justify-content: center; gap: 10px;
      width: 100%; padding: 11px; border-radius: 10px; border: 1px solid var(--border, #e0e3e8);
      background: var(--panel, #fff); color: var(--text, #1c1f24); font-weight: 600; font-size: 0.92rem;
      cursor: pointer; margin-bottom: 10px;
    }
    .ee-social-btn:hover { background: var(--row-hover, #eef4ff); }
    .ee-social-btn[disabled] { opacity: 0.5; cursor: not-allowed; }
    .ee-social-btn[disabled]:hover { background: var(--panel, #fff); }
    .ee-social-icon { width: 18px; height: 18px; flex-shrink: 0; }
    .ee-divider { display: flex; align-items: center; gap: 10px; margin: 14px 0; color: var(--text-muted, #6b7280); font-size: 0.82rem; }
    .ee-divider::before, .ee-divider::after { content: ''; flex: 1; height: 1px; background: var(--border, #e0e3e8); }
    .ee-field { margin-bottom: 12px; }
    .ee-field label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 5px; }
    .ee-field input {
      width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border, #e0e3e8);
      background: var(--bg, #f7f8fa); color: var(--text, #1c1f24); font-size: 0.92rem;
    }
    .ee-submit-btn {
      width: 100%; padding: 12px; border: none; border-radius: 10px;
      background: var(--accent, #14509a); color: #fff; font-weight: 700; font-size: 0.95rem;
      cursor: pointer; margin-top: 4px;
    }
    .ee-submit-btn:hover { opacity: 0.92; }
    .ee-switch-mode { text-align: center; margin-top: 14px; font-size: 0.85rem; color: var(--text-muted, #6b7280); }
    .ee-switch-mode a { color: var(--accent, #14509a); font-weight: 700; cursor: pointer; text-decoration: none; }
    .ee-form-msg { font-size: 0.85rem; padding: 9px 11px; border-radius: 8px; margin-bottom: 12px; }
    .ee-form-msg.error { background: #fdeaea; color: #8a1f1f; }
    .ee-form-msg.success { background: #e8f6ec; color: #1f6b3a; }
    .ee-verify-banner {
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      background: #fff6e0; color: #6b4b00; border-radius: 8px; padding: 8px 12px;
      font-size: 0.8rem; margin: 0 0 12px;
    }
    .ee-verify-banner button { border: none; background: none; color: #14509a; font-weight: 700; cursor: pointer; padding: 0; }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = STYLE;
  document.head.appendChild(styleEl);

  const overlay = document.createElement('div');
  overlay.className = 'ee-modal-overlay';
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="ee-modal" role="dialog" aria-modal="true">
      <button type="button" class="ee-modal-close" aria-label="${escapeHtml(t('close'))}">✕</button>
      <div id="ee-modal-body"></div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
  overlay.querySelector('.ee-modal-close').addEventListener('click', closeModal);

  function closeModal() { overlay.hidden = true; }

  // "Mit Apple anmelden" ist ausgeblendet. Apple Sign-In setzt ein
  // Apple-Developer-Konto für 99 $ im Jahr voraus; das Projekt soll
  // vorerst ohne laufende Kosten auskommen, und ein dauerhaft
  // ausgegrauter Button wäre nur Ballast im Dialog.
  //
  // Zum Aktivieren reicht `true` NICHT. Hier steht bisher nur die
  // Hülle: das Markup des Buttons (fest auf `disabled`, ohne
  // Klick-Behandlung) und das Icon. Es gibt keine signInWithApple() -
  // ein früherer Kommentar an dieser Stelle behauptete das, was beim
  // Aktivieren nur zu einem toten Button geführt hätte. Nötig wären:
  //   1. Apple-Developer-Konto, dort Service ID, Key und Team ID
  //      anlegen und den Anbieter in der Firebase-Konsole einrichten,
  //   2. eine signInWithApple() analog zu signInWithGoogle() -
  //      `new firebase.auth.OAuthProvider('apple.com')` statt
  //      GoogleAuthProvider, der Rest (Popup, Weiterleitung als
  //      Fallback, handleRedirectResult) gilt unverändert,
  //   3. `disabled` aus dem Markup entfernen und den Button wie
  //      #ee-google-btn verdrahten.
  const SHOW_APPLE_SIGNIN = false;

  const GOOGLE_ICON = '<svg class="ee-social-icon" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.5 29.3 35.5 24 35.5c-6.9 0-12.5-5.6-12.5-12.5S17.1 10.5 24 10.5c3.2 0 6.1 1.2 8.3 3.2l5.7-5.7C34.6 4.9 29.6 3 24 3 12.4 3 3 12.4 3 24s9.4 21 21 21 21-9.4 21-21c0-1.4-.1-2.7-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.9 18.9 13 24 13c3.2 0 6.1 1.2 8.3 3.2l5.7-5.7C34.6 6.9 29.6 5 24 5c-7.7 0-14.3 4.4-17.7 10.7z"/><path fill="#4CAF50" d="M24 45c5.5 0 10.4-1.9 14.3-5.1l-6.6-5.4c-2 1.5-4.6 2.5-7.7 2.5-5.3 0-9.7-3.4-11.3-8.1l-6.6 5.1C9.6 40.4 16.2 45 24 45z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.5l6.6 5.4C40.9 36.7 45 31 45 24c0-1.4-.1-2.7-.4-3.5z"/></svg>';
  const APPLE_ICON = '<svg class="ee-social-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M16.365 1.43c0 1.14-.463 2.15-1.187 2.9-.75.75-1.98 1.34-3.02 1.26-.12-1.1.43-2.24 1.13-2.98.78-.82 2.14-1.44 3.08-1.18zM20.5 17.24c-.55 1.27-.81 1.83-1.52 2.95-.99 1.56-2.38 3.5-4.1 3.52-1.53.02-1.92-.99-4-.98-2.08.01-2.5 1-4.03.98-1.72-.02-3.03-1.77-4.02-3.33C.28 17.02-.6 12.16 1.24 8.86c.94-1.68 2.6-2.75 4.4-2.77 1.63-.02 3.16 1.1 4.15 1.1.98 0 2.85-1.36 4.8-1.16.82.03 3.12.33 4.6 2.5-.12.08-2.75 1.6-2.72 4.8.03 3.82 3.35 5.09 3.03 5.21z"/></svg>';

  function renderLoginBody() {
    const body = overlay.querySelector('#ee-modal-body');
    body.innerHTML = `
      <h2>${escapeHtml(t('modalTitleLogin'))}</h2>
      <div id="ee-form-msg"></div>
      ${!configured ? `<div class="ee-form-msg error">${escapeHtml(t('notConfigured'))}</div>` : ''}
      <button type="button" class="ee-social-btn" id="ee-google-btn" ${configured ? '' : 'disabled'}>${GOOGLE_ICON}<span>${escapeHtml(t('googleBtn'))}</span></button>
      ${SHOW_APPLE_SIGNIN ? `<button type="button" class="ee-social-btn" id="ee-apple-btn" disabled title="${escapeHtml(t('appleSoon'))}">${APPLE_ICON}<span>${escapeHtml(t('appleBtn'))}</span></button>` : ''}
      <div class="ee-divider">${escapeHtml(t('or'))}</div>
      <form id="ee-login-form">
        <div class="ee-field">
          <label>${escapeHtml(t('emailLabel'))}</label>
          <input type="email" id="ee-login-email" placeholder="${escapeHtml(t('emailPlaceholder'))}" required autocomplete="email" ${configured ? '' : 'disabled'}>
        </div>
        <div class="ee-field">
          <label>${escapeHtml(t('passwordLabel'))}</label>
          <input type="password" id="ee-login-password" required autocomplete="current-password" ${configured ? '' : 'disabled'}>
        </div>
        <button type="submit" class="ee-submit-btn" ${configured ? '' : 'disabled'}>${escapeHtml(t('submitLogin'))}</button>
      </form>
      <div class="ee-switch-mode">${escapeHtml(t('noAccount'))} <a id="ee-switch-register">${escapeHtml(t('switchToRegister'))}</a></div>
    `;
    body.querySelector('#ee-switch-register').addEventListener('click', renderRegisterBody);
    if (!configured) return;
    body.querySelector('#ee-google-btn').addEventListener('click', signInWithGoogle);
    body.querySelector('#ee-login-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const email = body.querySelector('#ee-login-email').value.trim();
      const password = body.querySelector('#ee-login-password').value;
      setFormMsg(null);
      auth.signInWithEmailAndPassword(email, password)
        .then(() => closeModal())
        .catch(err => setFormMsg(errorMessage(err), 'error'));
    });
  }

  function renderRegisterBody() {
    const body = overlay.querySelector('#ee-modal-body');
    body.innerHTML = `
      <h2>${escapeHtml(t('modalTitleRegister'))}</h2>
      <div id="ee-form-msg"></div>
      ${!configured ? `<div class="ee-form-msg error">${escapeHtml(t('notConfigured'))}</div>` : ''}
      <button type="button" class="ee-social-btn" id="ee-google-btn" ${configured ? '' : 'disabled'}>${GOOGLE_ICON}<span>${escapeHtml(t('googleBtn'))}</span></button>
      ${SHOW_APPLE_SIGNIN ? `<button type="button" class="ee-social-btn" id="ee-apple-btn" disabled title="${escapeHtml(t('appleSoon'))}">${APPLE_ICON}<span>${escapeHtml(t('appleBtn'))}</span></button>` : ''}
      <div class="ee-divider">${escapeHtml(t('or'))}</div>
      <form id="ee-register-form">
        <div class="ee-field">
          <label>${escapeHtml(t('nameLabel'))}</label>
          <input type="text" id="ee-reg-name" autocomplete="name" ${configured ? '' : 'disabled'}>
        </div>
        <div class="ee-field">
          <label>${escapeHtml(t('emailLabel'))}</label>
          <input type="email" id="ee-reg-email" placeholder="${escapeHtml(t('emailPlaceholder'))}" required autocomplete="email" ${configured ? '' : 'disabled'}>
        </div>
        <div class="ee-field">
          <label>${escapeHtml(t('passwordLabel'))}</label>
          <input type="password" id="ee-reg-password" required autocomplete="new-password" minlength="6" ${configured ? '' : 'disabled'}>
        </div>
        <div class="ee-field">
          <label>${escapeHtml(t('passwordConfirmLabel'))}</label>
          <input type="password" id="ee-reg-password2" required autocomplete="new-password" minlength="6" ${configured ? '' : 'disabled'}>
        </div>
        <button type="submit" class="ee-submit-btn" ${configured ? '' : 'disabled'}>${escapeHtml(t('submitRegister'))}</button>
      </form>
      <div class="ee-switch-mode">${escapeHtml(t('hasAccount'))} <a id="ee-switch-login">${escapeHtml(t('switchToLogin'))}</a></div>
    `;
    body.querySelector('#ee-switch-login').addEventListener('click', renderLoginBody);
    if (!configured) return;
    body.querySelector('#ee-google-btn').addEventListener('click', signInWithGoogle);
    body.querySelector('#ee-register-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const name = body.querySelector('#ee-reg-name').value.trim();
      const email = body.querySelector('#ee-reg-email').value.trim();
      const password = body.querySelector('#ee-reg-password').value;
      const password2 = body.querySelector('#ee-reg-password2').value;
      setFormMsg(null);
      if (password.length < 6) { setFormMsg(t('passwordTooShort'), 'error'); return; }
      if (password !== password2) { setFormMsg(t('passwordMismatch'), 'error'); return; }
      auth.createUserWithEmailAndPassword(email, password)
        .then(cred => {
          const profileUpdate = name ? cred.user.updateProfile({ displayName: name }) : Promise.resolve();
          return profileUpdate.then(() => cred.user.sendEmailVerification());
        })
        .then(() => setFormMsg(t('verifyEmailSent'), 'success'))
        .catch(err => setFormMsg(errorMessage(err), 'error'));
    });
  }

  function setFormMsg(msg, type) {
    const el = overlay.querySelector('#ee-form-msg');
    if (!el) return;
    if (!msg) { el.innerHTML = ''; return; }
    el.innerHTML = `<div class="ee-form-msg ${type || 'error'}">${escapeHtml(msg)}</div>`;
  }

  // Merkt sich über den Seitenwechsel hinweg, dass wir gerade per
  // signInWithRedirect unterwegs sind. Nach der Rueckkehr wertet
  // handleRedirectResult() das aus: kommt der Nutzer ohne Anmeldung
  // zurück, lag es fast immer am eingebetteten Browser (siehe unten).
  const REDIRECT_FLAG = 'endurance-google-redirect';

  function setRedirectFlag(on) {
    try {
      if (on) sessionStorage.setItem(REDIRECT_FLAG, '1');
      else sessionStorage.removeItem(REDIRECT_FLAG);
    } catch (e) { /* sessionStorage evtl. gesperrt – dann eben ohne */ }
  }

  function hadRedirect() {
    try { return sessionStorage.getItem(REDIRECT_FLAG) === '1'; }
    catch (e) { return false; }
  }

  // Fehlercodes, bei denen das Popup gar nicht erst aufgehen konnte –
  // typisch für In-App-Browser (Instagram, Facebook, LinkedIn) und fuer
  // Browser mit strengem Popup-Blocker. Hier lohnt der zweite Versuch per
  // Weiterleitung. NICHT dabei: 'auth/popup-closed-by-user' – da hat der
  // Nutzer bewusst abgebrochen, eine Weiterleitung wäre übergriffig.
  const POPUP_UNAVAILABLE = [
    'auth/popup-blocked',
    'auth/operation-not-supported-in-this-environment',
    'auth/web-storage-unsupported',
    'auth/internal-error'
  ];

  function signInWithGoogle() {
    if (!configured) return;
    const provider = new firebase.auth.GoogleAuthProvider();
    setFormMsg(null);
    auth.signInWithPopup(provider)
      .then(() => closeModal())
      .catch(err => {
        const code = err && err.code;
        // Zwei Klicks kurz hintereinander: Firebase bricht den ersten
        // Aufruf ab, das zweite Popup läuft noch. Nichts anzeigen.
        if (code === 'auth/cancelled-popup-request') return;
        if (POPUP_UNAVAILABLE.indexOf(code) !== -1) {
          setFormMsg(t('redirecting'), 'success');
          setRedirectFlag(true);
          auth.signInWithRedirect(provider).catch(err2 => {
            setRedirectFlag(false);
            setFormMsg(errorMessage(err2), 'error');
          });
          return;
        }
        setFormMsg(errorMessage(err), 'error');
      });
  }

  // Wertet die Rückkehr von signInWithRedirect aus. Läuft einmal beim
  // Laden jeder Seite; ohne vorangegangene Weiterleitung ist das ein
  // No-op (result.user === null, kein Flag gesetzt).
  function handleRedirectResult() {
    if (!auth) return;
    auth.getRedirectResult()
      .then(result => {
        if (result && result.user) { setRedirectFlag(false); return; }
        if (!hadRedirect()) return;
        // Weiterleitung gestartet, aber ohne Anmeldung zurück: In
        // eingebetteten Browsern blockt der Speicherschutz (Safari ITP)
        // den Austausch mit der Firebase-Domain. Ehrlich sagen, statt
        // stumm zu scheitern.
        setRedirectFlag(false);
        openModal('login');
        setFormMsg(t('inAppBrowserHint'), 'error');
      })
      .catch(err => {
        setRedirectFlag(false);
        openModal('login');
        setFormMsg(errorMessage(err), 'error');
      });
  }

  function openModal(mode) {
    overlay.hidden = false;
    if (mode === 'register') renderRegisterBody(); else renderLoginBody();
  }

  // ---------------------------------------------------------------------
  // Button im Mount-Punkt (#auth-mount, in jeder Seite im top-bar/nav)
  // ---------------------------------------------------------------------
  function renderAuthButton(user) {
    const mount = document.getElementById('auth-mount');
    if (!mount) return;
    mount.innerHTML = '';
    // Anonyme Kennung: weiterhin "Anmelden" anbieten. Sonst stand dort
    // nach einer Fehlermeldung ein "Abmelden" neben einem leeren Namen.
    if (isRealUser(user)) {
      const wrap = document.createElement('div');
      wrap.className = 'ee-auth-user';
      const label = document.createElement('span');
      label.style.color = '#fff';
      label.style.fontSize = '0.8rem';
      label.style.fontWeight = '600';
      label.textContent = t('loggedInShort', user.email || user.displayName || '');
      const signOutBtn = document.createElement('button');
      signOutBtn.type = 'button';
      signOutBtn.textContent = t('logout');
      signOutBtn.addEventListener('click', () => auth && auth.signOut());
      wrap.appendChild(label);
      wrap.appendChild(signOutBtn);
      mount.appendChild(wrap);
    } else {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ee-auth-btn';
      btn.textContent = t('login');
      btn.addEventListener('click', () => openModal('login'));
      mount.appendChild(btn);
    }
  }

  if (auth) {
    auth.onAuthStateChanged(user => {
      renderAuthButton(user);
      notifyAuthChange(user);
    });
    handleRedirectResult();
  } else {
    // Kein Firebase konfiguriert: Button trotzdem anzeigen, öffnet das
    // Modal mit dem "noch nicht eingerichtet"-Hinweis statt nichts zu tun.
    document.addEventListener('DOMContentLoaded', () => renderAuthButton(null));
    if (document.readyState !== 'loading') renderAuthButton(null);
  }

  // ---------------------------------------------------------------------
  // Öffentliche API
  // ---------------------------------------------------------------------
  window.EndauranceAuth = {
    // Gibt NUR echte Konten zurück, nie die anonyme Kennung aus
    // reportEventError - siehe isRealUser(). Aufrufer fragen damit das,
    // was sie eigentlich wissen wollen: "kann diese Person eine E-Mail
    // bekommen?"
    getUser: () => (auth && isRealUser(auth.currentUser) ? auth.currentUser : null),
    isConfigured: () => configured,
    onAuthChange: (cb) => {
      const realOnly = (user) => cb(isRealUser(user) ? user : null);
      authChangeListeners.push(realOnly);
      if (auth) realOnly(auth.currentUser);
    },
    openModal,
    // Speichert ein "Benachrichtige mich"-Filterabo in Firestore. `filters`
    // ist ein einfaches, JSON-serialisierbares Objekt (Arrays statt Sets)
    // OHNE Datumsfilter - siehe events.html renderNotifyPrompt().
    saveFilterSubscription: (filters) => {
      if (!configured || !auth || !isRealUser(auth.currentUser)) {
        return Promise.reject(new Error('not-authenticated'));
      }
      const user = auth.currentUser;
      // Ein Abo ohne Empfänger ist kein Abo. Der Aufrufer kommt hier
      // normalerweise gar nicht an (siehe getUser()), aber ein Abo, das
      // nie zugestellt werden kann, darf auch nicht entstehen, wenn doch
      // jemand direkt hierher findet.
      if (!user.email) {
        return Promise.reject(new Error('no-email'));
      }
      return ensureDb().then((db) => db.collection('filterSubscriptions').add({
        uid: user.uid,
        email: user.email,
        filters: filters,
        notified: false,
        createdAt: firebase.firestore.FieldValue.serverTimestamp()
      }));
    },

    // Firestore vorausschauend nachladen, ohne auf das Ergebnis zu warten:
    // aufgerufen, sobald sich abzeichnet, dass geschrieben wird (Melde-
    // Dialog auf, Abo-Box sichtbar). Fehler sind hier bewusst egal - der
    // echte Aufruf versucht es dann noch einmal und meldet sie.
    prepareFirestore: () => { ensureDb().catch(() => {}); },

    // Nimmt eine Fehlermeldung zu einem Event auf (siehe events.html,
    // "Fehler zu diesem Event melden").
    //
    // Melden soll OHNE Anmeldung gehen - eine Hürde würde die meisten
    // Meldungen verhindern, und genau die sind der Zweck. Trotzdem wird
    // nicht unangemeldet geschrieben: Ein offener Schreibzugriff wäre bei
    // öffentlich sichtbarem apiKey eine Einladung, die Datenbank zu
    // fluten. Stattdessen legt Firebase im Hintergrund eine ANONYME
    // Kennung an (signInAnonymously). Die Nutzer merken davon nichts, die
    // Firestore-Regeln können aber weiterhin `request.auth != null`
    // verlangen und Meldungen einer Kennung zuordnen.
    //
    // Voraussetzung: In der Firebase-Konsole muss unter
    // Sicherheit -> Authentication -> Sign-in method der Anbieter
    // "Anonym" aktiviert sein. Fehlt er, schlägt der Aufruf mit
    // auth/operation-not-allowed fehl - die Meldung darüber steht in
    // events.html.
    reportEventError: ({ event, kategorie, beschreibung }) => {
      if (!configured || !auth) return Promise.reject(new Error('not-configured'));

      const ensureUser = auth.currentUser
        ? Promise.resolve(auth.currentUser)
        : auth.signInAnonymously().then((cred) => cred.user);

      // Beides parallel: das Firestore-SDK laedt, waehrend die anonyme
      // Anmeldung laeuft.
      return Promise.all([ensureDb(), ensureUser]).then(([db, user]) =>
        db.collection('errorReports').add({
          uid: user.uid,
          // Bei einer anonymen Kennung ist email null - bewusst
          // mitgeschrieben, damit man angemeldete Melder unterscheiden kann.
          email: user.email || null,
          anonym: !!user.isAnonymous,
          kategorie: kategorie,
          // Auf 600 Zeichen begrenzt - dieselbe Grenze prüfen die
          // Security Rules; ein längerer Text würde dort abgelehnt.
          beschreibung: String(beschreibung || '').trim().slice(0, 600),
          // Das Event so festhalten, wie es zum Meldezeitpunkt in der
          // Liste stand. Ohne diesen Schnappschuss wäre später nicht
          // nachvollziehbar, worauf sich die Meldung bezog - die Daten
          // ändern sich täglich.
          event: {
            name: event.name || null,
            datum_start: event.datum_start || null,
            standort: event.standort || null,
            land: event.land || null,
            art1: event.art1 || null,
            art2: event.art2 || null,
            laenge_km: event.laenge_km ?? null,
            wettbewerb: event.wettbewerb || null,
            veranstalter_url: event.veranstalter_url || null
          },
          status: 'neu',
          createdAt: firebase.firestore.FieldValue.serverTimestamp()
        })
      );
    }
  };

  // ---------------------------------------------------------------------
  // Nachzuegler-Warteschlange
  // ---------------------------------------------------------------------
  // Die Firebase-Skripte und diese Datei haengen mit `defer` im HTML: sie
  // laden parallel zum Seitenaufbau, laufen aber erst NACH dem Inline-
  // Skript der Seite. Fuer die Liste ist das der ganze Sinn der Sache
  // (events.json wird sofort abgerufen, statt auf 200 KB Firebase zu
  // warten) - nur kann events.html dann noch kein onAuthChange
  // registrieren. Wer zu frueh dran ist, legt seinen Listener in
  // window.EE_AUTH_QUEUE ab und wird hier nachtraeglich angemeldet.
  const wartende = window.EE_AUTH_QUEUE;
  window.EE_AUTH_QUEUE = {
    push: (cb) => { window.EndauranceAuth.onAuthChange(cb); }
  };
  if (Array.isArray(wartende)) {
    wartende.forEach((cb) => {
      try { window.EndauranceAuth.onAuthChange(cb); } catch (e) { console.error(e); }
    });
  }
})();
