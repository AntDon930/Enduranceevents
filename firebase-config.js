// Firebase-Konfiguration für Login/Registrierung (Google- und
// E-Mail/Passwort-Anmeldung mit Bestätigungs-E-Mail) sowie die
// "Benachrichtige mich"-Filterabos (Firestore). Wird von auth.js geladen.
//
// EINMALIGES SETUP (siehe README.md, Abschnitt "Login/Anmeldung
// einrichten" für die ausführliche Anleitung):
//   1. Firebase-Projekt anlegen: https://console.firebase.google.com/
//      Der kostenlose "Spark"-Tarif genügt für Login UND Firestore.
//      (Nur die optionale E-Mail-Benachrichtigung per Cloud Function
//      braucht "Blaze", siehe README.)
//   2. Linke Spalte -> "Sicherheit" -> Authentication -> Jetzt starten
//      -> Reiter "Sign-in method"/"Anbieter": "Google" UND
//      "E-Mail/Passwort" aktivieren. Bei Google wird eine Support-
//      E-Mail verlangt - die eigene Adresse genügt.
//   3. Authentication -> Einstellungen -> Autorisierte Domains:
//      antdon930.github.io eintragen (sonst schlägt der Login auf der
//      live GitHub-Pages-Seite mit "auth/unauthorized-domain" fehl,
//      auch wenn er lokal funktioniert).
//   4. Linke Spalte -> "Datenbanken und Speicher" -> Firestore Database
//      -> Datenbank erstellen (Produktionsmodus; die Security Rules aus
//      firestore.rules übernehmen). Nur für "Benachrichtige mich"
//      nötig, nicht für den Login selbst.
//   5. Projektübersicht -> "App hinzufügen" -> Web (</>) -> Namen
//      vergeben -> das dort angezeigte Config-Objekt HIERHER kopieren
//      (ersetzt die "REPLACE_ME"-Platzhalter unten). Firebase Hosting
//      dabei NICHT einrichten - die Seite läuft auf GitHub Pages.
//
// Hinweis zur Navigation: Die Firebase-Konsole hat die linke Spalte
// umgestellt. Ältere Anleitungen (auch von Google) sprechen noch von
// "Build -> Authentication"; heute liegt Authentication unter
// "Sicherheit" und Firestore unter "Datenbanken und Speicher".
//
// Diese Werte (apiKey etc.) sind für Firebase-WEB-Apps kein Geheimnis -
// sie dürfen bedenkenlos hier im öffentlichen Repo/auf GitHub Pages
// liegen. Der eigentliche Zugriffsschutz läuft über Firebase Security
// Rules (Firestore) bzw. die Autorisierten Domains (Auth), nicht über
// Geheimhaltung dieser Werte.
window.FIREBASE_CONFIG = {
  apiKey: "REPLACE_ME",
  authDomain: "REPLACE_ME.firebaseapp.com",
  projectId: "REPLACE_ME",
  storageBucket: "REPLACE_ME.appspot.com",
  messagingSenderId: "REPLACE_ME",
  appId: "REPLACE_ME"
};

// Wird automatisch ausgewertet: Solange apiKey noch "REPLACE_ME" ist,
// zeigt auth.js einen freundlichen "Login ist noch nicht eingerichtet"-
// Hinweis statt kaputter Buttons oder Konsolenfehlern.
window.FIREBASE_CONFIGURED = window.FIREBASE_CONFIG.apiKey !== "REPLACE_ME";
