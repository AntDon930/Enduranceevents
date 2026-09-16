// sw.js
// =====
// Ein einziger Zweck: dem Browser eine .ics-Datei mit dem richtigen
// Inhaltstyp ausliefern, damit iOS und macOS den Termin dem Kalender
// anbieten.
//
// Warum das nötig ist: Die Seite liegt auf GitHub Pages, es gibt keinen
// Server, der eine Datei je Event erzeugen könnte. Ein Blob- oder
// data-URI aus dem Browser trägt zwar den Typ text/calendar, aber Safari
// behandelt ihn als Download - im Screenshot des Nutzers endete das bei
// "Unknown.ics" und einer Teilen-Liste ohne Kalender. Ein Service Worker
// darf eine Antwort selbst zusammensetzen, inklusive Kopfzeilen; für
// Safari ist das eine echte Server-Antwort, und die führt zum
// "Zum Kalender hinzufügen"-Blatt.
//
// Der Worker fasst NICHTS anderes an: kein Zwischenspeichern, keine
// Offline-Funktion. Alles außer der einen Adresse geht unverändert ins
// Netz - ein Zwischenspeicher wäre bei einer täglich wachsenden
// events.json nur eine Quelle für veraltete Anzeigen.

self.addEventListener('install', () => self.skipWaiting());

// clients.claim(): Der Worker übernimmt auch die schon offenen Seiten,
// sonst wäre er erst beim zweiten Besuch zuständig - und der Nutzer
// stünde beim ersten Klick wieder ohne Kalender da.
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

// Alles unter /kalender/ mit der Endung .ics. Der Dateiname steht damit
// in der Adresse und landet über Content-Disposition beim Kalender -
// "termin.ics" für jedes Event wäre in der Dateiliste nicht zu
// unterscheiden. Die Datei existiert nirgends, der Worker erfindet sie;
// ohne ihn gäbe es dort einen 404.
const ICS_ORDNER = '/kalender/';

// base64url -> UTF-8. Der Umweg über escape/unescape ist der klassische
// Weg, Umlaute korrekt durch atob() zu bekommen (btoa/atob arbeiten
// byteweise); TextDecoder wäre schöner, ist in älteren Safari-Versionen
// im Worker aber nicht überall vorhanden.
function decodeUtf8Base64(b64) {
  const roh = b64.replace(/-/g, '+').replace(/_/g, '/');
  return decodeURIComponent(escape(atob(roh)));
}

self.addEventListener('fetch', (event) => {
  let url;
  try { url = new URL(event.request.url); } catch (e) { return; }
  if (!url.pathname.includes(ICS_ORDNER) || !url.pathname.endsWith('.ics')) return;

  const daten = url.searchParams.get('d');
  if (!daten) return;

  let text;
  try { text = decodeUtf8Base64(daten); } catch (e) { return; }

  const name = url.pathname.split('/').pop() || 'termin.ics';

  event.respondWith(new Response(text, {
    status: 200,
    headers: {
      // Beides zählt: der Typ sagt Safari, dass es ein Termin ist,
      // "inline" verhindert, dass er daraus doch einen Download macht.
      'Content-Type': 'text/calendar; charset=utf-8',
      'Content-Disposition': `inline; filename="${name.replace(/"/g, '')}"`,
      'Cache-Control': 'no-store'
    }
  }));
});
