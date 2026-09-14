// Firebase-Konfiguration für Login/Registrierung (Google- und
// E-Mail/Passwort-Anmeldung mit Bestätigungs-E-Mail) sowie die
// "Benachrichtige mich"-Filterabos (Firestore). Wird von auth.js geladen.
//
// EINMALIGES SETUP (siehe README.md, Abschnitt "Login/Anmeldung
// einrichten" für die ausführliche Anleitung):
//   1. Firebase-Projekt anlegen: https://console.firebase.google.com/
//   2. Build -> Authentication -> Sign-in method: "Google" UND
//      "E-Mail/Passwort" aktivieren.
//   3. Authentication -> Settings -> Autorisierte Domains:
//      antdon930.github.io eintragen (sonst schlägt der Login auf der
//      live GitHub-Pages-Seite fehl, auch wenn er lokal funktioniert).
//   4. Build -> Firestore Database -> Datenbank erstellen (Produktionsmodus;
//      die Security Rules aus README.md/firestore.rules übernehmen).
//   5. Projekteinstellungen (Zahnrad oben links) -> "Meine Apps" ->
//      Web-App hinzufügen -> das dort angezeigte Config-Objekt HIERHER
//      kopieren (ersetzt die "REPLACE_ME"-Platzhalter unten).
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
