// Die Detail-Box eines Events - in der Liste (events.html, neben der
// Tabelle) UND auf der Karte (karte.html, oben rechts über der Karte,
// bis zu zwei nebeneinander gestapelt; vom Nutzer am 19.09.2026
// gewünscht: "genau gleiche Struktur wie wenn man auf eins von der Liste
// klickt").
//
// Warum ausgelagert: Die Box hängt an einem Dutzend Helfern - Kennung
// des Events (eventSlug), Name der Kalenderdatei, Kalender-Menü,
// Teilen, Formatierung von Datum und Länge, Kurzmeldung (Toast) - und
// zwei Kopien davon wären beim nächsten Umbau auseinandergelaufen.
// Dieselbe Linie wie bei filters.js und filter-ui.js.
//
// Anbindung: EnduranceDetail.render(container, event, { t, tv, lang,
// onReport, onClose }). `onReport` (Fehler melden) und `onClose` (das ✕)
// sind optional: Fehlt onClose, gibt es kein ✕ (Liste); fehlt onReport,
// gibt es keinen Melde-Knopf. Die Texte (I18N) mischt jede Seite in ihr
// eigenes I18N-Objekt, wie bei den anderen Modulen.
//
// Innerhalb der Box gibt es KEINE Ids, nur Klassen: Auf der Karte stehen
// bis zu zwei Boxen zugleich, und Ids müssten eindeutig sein.
(function (global) {
  'use strict';

  const EF = global.EnduranceFilters;

  const I18N = {
    de: {
      detail_empty: 'Wähle eine Zeile aus, um Details zu sehen.',
      detail_datum: 'Datum', detail_sportart: 'Sportart', detail_kategorie: 'Kategorie',
      detail_standort: 'Stadt/Ort', detail_land: 'Land', detail_laenge: 'Länge',
      detail_wettbewerb: 'Wettbewerb',
      detail_link: 'Zur Veranstalter-Website',
      detail_close: 'Schließen',
      share_event: 'Dieses Event teilen',
      share_event_done: 'Event kopiert!',
      share_fail: 'Kopieren nicht möglich – bitte die Adresszeile verwenden',
      report_btn: 'Fehler zu diesem Event melden',
      cal_btn: 'Zum Kalender hinzufügen',
      cal_google: 'Google Kalender / Gmail',
      cal_outlook: 'Outlook',
      cal_ics: 'Apple Kalender & andere (.ics)',
      cal_note: 'Ganztägiger Termin. Die .ics-Datei wird geladen – zum Eintragen öffnen.',
      cal_note_apple: 'Ganztägiger Termin. Öffnet sich im Kalender – dort auf „Hinzufügen" tippen. Lädt Safari stattdessen eine Datei, diese in „Dateien" antippen.'
    },
    en: {
      detail_empty: 'Select a row to see details.',
      detail_datum: 'Date', detail_sportart: 'Sport', detail_kategorie: 'Category',
      detail_standort: 'City', detail_land: 'Country', detail_laenge: 'Length',
      detail_wettbewerb: 'Race',
      detail_link: 'Visit organizer website',
      detail_close: 'Close',
      share_event: 'Share this event',
      share_event_done: 'Event copied!',
      share_fail: 'Could not copy – please use the address bar',
      report_btn: 'Report an error in this event',
      cal_btn: 'Add to calendar',
      cal_google: 'Google Calendar / Gmail',
      cal_outlook: 'Outlook',
      cal_ics: 'Apple Calendar & others (.ics)',
      cal_note: 'All-day event. The .ics file will download – open it to add the event.',
      cal_note_apple: 'All-day event. Opens in Calendar – tap "Add" there. If Safari downloads a file instead, tap it in "Files".'
    }
  };

  const escapeHtml = (s) => EF.escapeHtml(s);

  // ---------- Wettbewerbs-Label ----------

  const CANONICAL_RACE_NAMES = {
    'marathon': 42.2,
    'halbmarathon': 21.1,
    'half marathon': 21.1,
    'halbmarathon (hm)': 21.1
  };

  // Die Wettbewerbs-Bezeichnung, ODER null wenn sie nur die Länge
  // wiederholt.
  //
  // Die Quellen benennen einen Wettbewerb oft schlicht mit seiner Distanz
  // ("50 km", "6 km") oder mit deren kanonischem Namen ("Halbmarathon").
  // Beides steht schon in der Längen-Spalte; im Detailbereich erschien es
  // dadurch zweimal ("Race 50 km" über "Length 50 km"), in der Liste als
  // Unterzeile unter dem Namen. Bei gerundeten Quellenangaben sah es sogar
  // nach einem Widerspruch aus: Unterzeile "6 km" über der Spalte "5.5 km".
  //
  // Bezeichnungen mit eigener Aussage bleiben: "Laufen", "Wandern",
  // "Moslig 8000", "5×5 km Staffel", "26 km Trail". Das Feld selbst bleibt
  // in events.json erhalten - die Duplikat-Erkennung der Scraper braucht
  // es (über "Halbmarathon" wurde der doppelte München-Halbmarathon
  // gefunden).
  function displayWettbewerb(e) {
    const label = (e.wettbewerb || '').trim();
    if (!label) return null;
    const km = e.laenge_km;

    // Kanonischer Name, der genau die gespeicherte Länge bezeichnet?
    const canonical = CANONICAL_RACE_NAMES[label.toLowerCase()];
    if (canonical != null && km != null && Math.abs(canonical - Number(km)) <= 0.5) return null;

    // Bleibt nach Abzug der Distanzangaben und Füllwörter noch etwas übrig?
    const rest = label
      .replace(/\d{1,3}(?:[.,]\d+)?\s*(?:km|kilometer)\b/gi, ' ')
      .replace(/\b(?:ca|circa|etwa|rund|ungefähr|approx|ungefaehr)\b\.?/gi, ' ')
      .replace(/[\s.,;:\-–|~()]+/g, '')
      .trim();
    return rest ? label : null;
  }

  // ---------- Datum und Länge ----------

  function formatDate(iso, lang) {
    return EF.formatDate(iso, lang);
  }

  function formatRange(start, end, lang) {
    if (start === end) return formatDate(start, lang);
    return `${formatDate(start, lang)} – ${formatDate(end, lang)}`;
  }

  // Dasselbe für die Tabelle und die Detail-Box: Ein mehrtägiges Rennen
  // steht in ZWEI Zeilen - Anfangsdatum samt Gedankenstrich, Enddatum
  // darunter. Vorher brach die Zelle dort um, wo gerade Platz war
  // ("18 Sep 2026 – 20" / "Sep 2026", vom Nutzer gemeldet). Ein <br>
  // statt zweier Blöcke, damit `.cell-clamp` (zwei Zeilen) weiter greift
  // und die Zeilenhöhe von 52 px stimmt.
  // Die Textfassung oben bleibt für Melde-Dialog und Teilen-Text - dort
  // wird der Rückgabewert escaped, ein <br> stünde als Zeichenfolge da.
  function formatRangeHtml(start, end, lang) {
    if (start === end) return escapeHtml(formatDate(start, lang));
    return `${escapeHtml(formatDate(start, lang))} –<br>${escapeHtml(formatDate(end, lang))}`;
  }

  // Was in der Spalte "Länge" und in der Box steht. Nicht jedes Rennen
  // hat eine Strecke: ein 24-Stunden-Lauf ist über die ZEIT begrenzt,
  // gelaufen wird so weit man kommt. Solche Einträge tragen `dauer_h`
  // statt `laenge_km` und zeigen "24 h".
  //
  // Eine bekannte Distanz hat dabei VORRANG, auch wenn beide Felder
  // gesetzt sind: Beim "24h Mad Chicken Run | Marathon, 42 km" ist das
  // "24h" der Name der Veranstaltung, die Zeile selbst aber eine feste
  // 42-km-Strecke. Sie als "24 h" anzuzeigen würde die Distanz
  // verschlucken.
  function formatLength(e, lang) {
    if (e.laenge_km != null) return EF.formatKm(e.laenge_km, lang);
    if (e.dauer_h != null && !Number.isNaN(Number(e.dauer_h))) {
      return EF.formatHours(e.dauer_h, lang);
    }
    // Backyard Ultra ohne Zeitbegrenzung: bewusst "–". Der Lauf endet,
    // wenn nur noch eine Person weiterläuft - es gibt keine Länge, und
    // die Rundenlänge ist keine (siehe clear_backyard_lap_km()).
    return EF.formatKm(null, lang);
  }

  // ---------- Die Kennung eines Events ----------

  // Dateiname der fertigen .ics-Datei. **Muss mit ics_dateiname() in
  // scripts/build_ics.py übereinstimmen** - sonst zeigt der Knopf auf
  // eine Datei, die es nicht gibt. scripts/test_scraper_lib.py prüft
  // beide Umsetzungen gegeneinander (schneidet die vier Funktionen aus
  // DIESER Datei und lässt sie in node laufen), also beim Ändern immer
  // beide anfassen.
  //
  // Aufbau: <datum>-<name>-<distanz>-<ort>.ics. Der Ort gehört dazu, weil
  // Name + Datum + Distanz nicht eindeutig sind ("TEAG - Legend of Cross
  // - Mühlberg" steht am 31.10.2026 mit 10, 17 und 30 km je zweimal in
  // den Daten, einmal unter "Mühlberg" und einmal unter "Drei Gleichen").
  function icsSlug(text) {
    return (text || '')
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/ß/g, 'ss')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48)
      .replace(/^-+|-+$/g, '');
  }

  // Sprachunabhängig, bewusst NICHT über EF.formatKm: Dateiname und Slug
  // müssen in DE und EN gleich sein, sonst zeigt ein geteilter Link ins
  // Leere.
  function icsMasszahl(e) {
    if (e.laenge_km != null) {
      return `${(Math.round(Number(e.laenge_km) * 10) / 10)}km`.replace('.', '-');
    }
    if (e.dauer_h != null) {
      return `${(Math.round(Number(e.dauer_h) * 10) / 10)}h`.replace('.', '-');
    }
    return 'x';
  }

  // Die dauerhafte Kennung eines Events: Datum, Name, Maßzahl, Ort.
  // Zwei Dinge hängen daran, deshalb steht sie nur EINMAL hier:
  //   - der Name der Kalenderdatei (icsFileName, muss zu build_ics.py
  //     passen - test_scraper_lib.py prüft beide gegeneinander),
  //   - der Link auf ein einzelnes Event (?event=…, siehe teileEvent).
  // Eine ID in events.json gibt es nicht, und eine laufende Nummer wäre
  // wertlos: Sie verschiebt sich, sobald ein Event dazukommt oder ein
  // vergangenes wegfällt - ein geteilter Link zeigte dann auf ein
  // fremdes Rennen.
  function eventSlug(e) {
    const teile = [e.datum_start || 'ohne-datum', icsSlug(e.name), icsMasszahl(e)];
    const ort = icsSlug(e.standort);
    if (ort) teile.push(ort);
    return teile.join('-');
  }

  function icsFileName(e) {
    return eventSlug(e) + '.ics';
  }

  // Der Link auf genau dieses Event - immer auf die LISTE, auch von der
  // Karte aus (nur sie kennt ?event=). Absolut, damit er in einer
  // Nachricht anklickbar ist.
  function eventLink(e) {
    const basis = new URL('events.html', global.location.href);
    basis.search = '';
    basis.hash = '';
    return `${basis.toString()}?event=${encodeURIComponent(eventSlug(e))}`;
  }

  // ---------- Kurzmeldung (Toast) ----------

  // Kurz aufpoppende Rückmeldung, mittig unten. Das Element entsteht
  // beim ersten Aufruf - die Seiten müssen es nicht vorhalten.
  let toastEl = null;
  let toastTimer = null;
  function showToast(text) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      toastEl.setAttribute('role', 'status');
      toastEl.setAttribute('aria-live', 'polite');
      toastEl.hidden = true;
      document.body.appendChild(toastEl);
    }
    global.clearTimeout(toastTimer);
    toastEl.textContent = text;
    toastEl.hidden = false;
    // Ein Bildaufbau muss zwischen hidden=false und der Klasse liegen,
    // sonst gibt es keinen Übergang, sondern einen Sprung.
    global.requestAnimationFrame(() => toastEl.classList.add('visible'));
    toastTimer = global.setTimeout(() => {
      toastEl.classList.remove('visible');
      toastTimer = global.setTimeout(() => { toastEl.hidden = true; }, 220);
    }, 1800);
  }

  // Kopieren mit Rückfallweg: `navigator.clipboard` braucht einen
  // sicheren Kontext (https oder localhost). Ohne den hilft ein
  // unsichtbares Textfeld samt execCommand - alt, aber es funktioniert
  // überall.
  function kopiereInAblage(text, t) {
    if (navigator.clipboard && global.isSecureContext !== false) {
      navigator.clipboard.writeText(text)
        .then(() => showToast(t('share_event_done')))
        .catch(() => showToast(t('share_fail')));
      return;
    }
    try {
      const feld = document.createElement('textarea');
      feld.value = text;
      feld.setAttribute('readonly', '');
      feld.style.cssText = 'position:fixed;top:-1000px;opacity:0';
      document.body.appendChild(feld);
      feld.select();
      const ok = document.execCommand('copy');
      feld.remove();
      showToast(ok ? t('share_event_done') : t('share_fail'));
    } catch (err) {
      showToast(t('share_fail'));
    }
  }

  // ---------- Ein einzelnes Event teilen ----------
  //
  // Geteilt wird ein LINK auf genau dieses Event plus die Angaben, die
  // in der Box stehen - kein PDF und kein Bild. Gründe, der Reihe nach:
  //
  //   - Die Box enthält eine Handvoll Fakten und zwei Links. Wer den
  //     Link antippt, landet genau hier: mit "Zum Kalender hinzufügen",
  //     der Veranstalter-Seite und der Karte daneben. Ein PDF kann das
  //     alles nicht, und es veraltet - verlegt der Veranstalter das
  //     Rennen, ist das PDF für immer falsch.
  //   - `navigator.share()` öffnet den Teilen-Dialog des Geräts.
  //     Damit funktionieren WhatsApp, iMessage, Mail, Signal, Notizen
  //     und AirDrop auf einmal, ohne dass die Seite einen einzigen
  //     Dienst kennen muss.
  //   - Ein PDF bräuchte eine Bibliothek (jsPDF o. Ä., ~150-400 KB) für
  //     ein schlechteres Ergebnis. Wo ein PDF sinnvoll wäre: die ganze
  //     gefilterte Liste als Saisonplan - das ist eine andere Funktion,
  //     und dafür reicht später ein Druck-Stylesheet (der Browser
  //     schreibt daraus selbst ein PDF).
  //
  // Ohne `navigator.share` (Firefox am Rechner, Safari am Mac je nach
  // Version) wird Text + Link in die Ablage kopiert.

  // Die Angaben aus der Box, in der Reihenfolge, in der sie dort stehen.
  function eventShareText(e, ctx) {
    const { tv, lang } = ctx;
    const zeilen = [
      e.name,
      `${formatRange(e.datum_start, e.datum_ende, lang)} · ${tv('standort', e.standort)}, ${tv('land', e.land)}`,
      `${tv('art1', e.art1)}${e.art2 ? ' / ' + tv('art2', e.art2) : ''} · ${formatLength(e, lang)}`
    ];
    const wb = displayWettbewerb(e);
    if (wb) zeilen.splice(2, 0, wb);
    return zeilen.join('\n');
  }

  function teileEvent(e, ctx) {
    const url = eventLink(e);
    const text = eventShareText(e, ctx);
    if (navigator.share) {
      // Bricht jemand den Dialog ab, kommt ein AbortError - das ist
      // keine Panne und darf keine Meldung auslösen.
      navigator.share({ title: e.name, text, url }).catch((err) => {
        if (err && (err.name === 'AbortError' || err.name === 'NotAllowedError')) return;
        kopiereInAblage(text + '\n' + url, ctx.t);
      });
      return;
    }
    kopiereInAblage(text + '\n' + url, ctx.t);
  }

  // ---------- Zum Kalender hinzufügen ----------

  // Alle Termine sind GANZTÄGIG. Startzeiten stehen in keiner Quelle
  // verlässlich (und wenn, dann pro Wettbewerb verschieden) - ein
  // ganztägiger Eintrag behauptet keine Uhrzeit, die wir nicht kennen.
  //
  // Ganztägige Termine enden im iCalendar-Format (RFC 5545) am FOLGETAG:
  // DTEND ist exklusiv. Dasselbe gilt für den dates-Parameter von Google
  // und startdt/enddt von Outlook. Ohne das +1 fehlt der letzte Tag.
  function calDatePlusDays(iso, tage) {
    const [j, m, d] = iso.split('-').map(Number);
    const dt = new Date(Date.UTC(j, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + tage);
    return dt.toISOString().slice(0, 10);
  }

  function calFields(e, ctx) {
    const { t, tv, lang } = ctx;
    const start = e.datum_start;
    const endeInklusiv = e.datum_ende && e.datum_ende > start ? e.datum_ende : start;
    const wb = displayWettbewerb(e);
    const titel = wb ? `${e.name} – ${wb}` : e.name;
    const zeilen = [
      `${t('detail_sportart')}: ${tv('art1', e.art1)}${e.art2 ? ' / ' + tv('art2', e.art2) : ''}`,
      `${t('detail_laenge')}: ${formatLength(e, lang)}`
    ];
    if (e.veranstalter_url) zeilen.push(e.veranstalter_url);
    return {
      titel,
      ort: `${tv('standort', e.standort)}${e.land ? ', ' + tv('land', e.land) : ''}`,
      beschreibung: zeilen.join('\n'),
      start,
      endeExklusiv: calDatePlusDays(endeInklusiv, 1),
      url: e.veranstalter_url || ''
    };
  }

  function istIosGeraet() {
    const ua = navigator.userAgent || '';
    return /iPhone|iPad|iPod/.test(ua) || (/Mac/.test(ua) && navigator.maxTouchPoints > 1);
  }

  // Mac ohne Touch = Schreibtisch-macOS. Dort ist der Kalender die
  // Standard-App für .ics, das Öffnen lohnt also genauso.
  function istAppleGeraet() {
    return istIosGeraet() || /Mac/.test(navigator.userAgent || '');
  }

  function schliesseKalenderMenu(box) {
    const menu = box.querySelector('.cal-menu');
    const btn = box.querySelector('.cal-open-btn');
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    if (btn) btn.setAttribute('aria-expanded', 'false');
  }

  function setupCalendarBox(box, e, ctx) {
    const btn = box.querySelector('.cal-open-btn');
    const menu = box.querySelector('.cal-menu');
    if (!btn || !menu) return;
    const f = calFields(e, ctx);
    const kompakt = (iso) => iso.replace(/-/g, '');

    box.querySelector('.cal-google').href =
      'https://calendar.google.com/calendar/render?action=TEMPLATE'
      + `&text=${encodeURIComponent(f.titel)}`
      + `&dates=${kompakt(f.start)}/${kompakt(f.endeExklusiv)}`
      + `&details=${encodeURIComponent(f.beschreibung)}`
      + `&location=${encodeURIComponent(f.ort)}`;

    // Outlook.com deckt private Konten ab; Outlook für Arbeit/Schule
    // (outlook.office.com) versteht dieselbe Adresse und leitet um.
    box.querySelector('.cal-outlook').href =
      'https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose&rru=addevent'
      + '&allday=true'
      + `&subject=${encodeURIComponent(f.titel)}`
      + `&startdt=${f.start}`
      + `&enddt=${f.endeExklusiv}`
      + `&body=${encodeURIComponent(f.beschreibung)}`
      + `&location=${encodeURIComponent(f.ort)}`;

    // Die .ics-Datei liegt fertig im Ordner kalender/ (erzeugt von
    // scripts/build_ics.py, eine je Event). Ein einfacher Link genügt -
    // und nur so kommt die Datei mit dem Inhaltstyp text/calendar vom
    // Server, den iOS braucht, um den Termin dem Kalender anzubieten.
    // Alles, was die Seite selbst erzeugte (Blob, data-URI, sogar eine
    // vom Service Worker erfundene Antwort), war für Safari ein Download.
    //
    // Bewusst OHNE download-Attribut: das würde Safari das Übergeben an
    // den Kalender wieder verbieten. Der Pfad ist relativ - Liste und
    // Karte liegen im selben Ordner wie kalender/.
    box.querySelector('.cal-ics').href = `kalender/${icsFileName(e)}`;
    const noteEl = box.querySelector('.cal-note');
    if (noteEl) noteEl.textContent = ctx.t(istAppleGeraet() ? 'cal_note_apple' : 'cal_note');

    btn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      const offen = !menu.hidden;
      menu.hidden = offen;
      btn.setAttribute('aria-expanded', offen ? 'false' : 'true');
    });
    menu.addEventListener('click', () => schliesseKalenderMenu(box));

    // Klick daneben oder Escape schließt das Menü - EIN Zuhörer für alle
    // Boxen der Seite, nur einmal angemeldet (render() baut die Box bei
    // jedem Klick neu, sonst sammelten sich die Zuhörer an).
    if (!setupCalendarBox.listenersAttached) {
      setupCalendarBox.listenersAttached = true;
      document.addEventListener('click', (ev) => {
        document.querySelectorAll('.detail-panel').forEach((b) => {
          const m = b.querySelector('.cal-menu');
          if (!m || m.hidden) return;
          if (m.contains(ev.target) || b.querySelector('.cal-open-btn').contains(ev.target)) return;
          schliesseKalenderMenu(b);
        });
      });
      document.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Escape') return;
        document.querySelectorAll('.detail-panel').forEach(schliesseKalenderMenu);
      });
    }
  }

  // ---------- Die Box ----------

  const SHARE_SVG = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/>'
    + '<path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg>';
  const CAL_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/></svg>';

  function renderEmpty(container, ctx) {
    container.innerHTML = `<div class="detail-empty">${escapeHtml(ctx.t('detail_empty'))}</div>`;
  }

  // ctx: { t, tv, lang, onReport?, onClose? }. Gibt nichts zurück; die
  // Knöpfe hängen an der Box selbst.
  function render(container, e, ctx) {
    const { t, tv, lang } = ctx;
    const wb = displayWettbewerb(e);
    container.innerHTML = `
      <div class="detail-head">
        <div class="detail-head-text">
          <h2>${escapeHtml(e.name)}</h2>
          <div class="sub">${escapeHtml(tv('standort', e.standort))}, ${escapeHtml(tv('land', e.land))}</div>
        </div>
        <button type="button" class="detail-share event-share-btn"
                title="${escapeHtml(t('share_event'))}" aria-label="${escapeHtml(t('share_event'))}">${SHARE_SVG}</button>
        ${ctx.onClose ? `<button type="button" class="detail-share detail-close"
                title="${escapeHtml(t('detail_close'))}" aria-label="${escapeHtml(t('detail_close'))}">&#10005;</button>` : ''}
      </div>
      <dl class="detail-grid">
        <dt>${escapeHtml(t('detail_datum'))}</dt><dd>${formatRangeHtml(e.datum_start, e.datum_ende, lang)}</dd>
        <dt>${escapeHtml(t('detail_land'))}</dt><dd>${escapeHtml(tv('land', e.land))}</dd>
        <dt>${escapeHtml(t('detail_standort'))}</dt><dd>${escapeHtml(tv('standort', e.standort))}</dd>
        <dt>${escapeHtml(t('detail_sportart'))}</dt><dd>${escapeHtml(tv('art1', e.art1))}</dd>
        <dt>${escapeHtml(t('detail_kategorie'))}</dt><dd>${escapeHtml(e.art2 ? tv('art2', e.art2) : '–')}</dd>
        ${wb ? `<dt>${escapeHtml(t('detail_wettbewerb'))}</dt><dd>${escapeHtml(wb)}</dd>` : ''}
        <dt>${escapeHtml(t('detail_laenge'))}</dt><dd>${formatLength(e, lang)}</dd>
      </dl>
      ${e.veranstalter_url ? `<a class="detail-link" href="${escapeHtml(e.veranstalter_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t('detail_link'))}</a>` : ''}
      <div class="cal-box">
        <button type="button" class="cal-btn cal-open-btn" aria-expanded="false">
          ${CAL_SVG}<span>${escapeHtml(t('cal_btn'))}</span>
        </button>
        <div class="cal-menu" hidden>
          <a class="cal-google" target="_blank" rel="noopener noreferrer">${escapeHtml(t('cal_google'))}</a>
          <a class="cal-outlook" target="_blank" rel="noopener noreferrer">${escapeHtml(t('cal_outlook'))}</a>
          <a class="cal-ics">${escapeHtml(t('cal_ics'))}</a>
          <div class="cal-note"></div>
        </div>
      </div>
      ${ctx.onReport ? `<button type="button" class="report-btn report-open-btn">${escapeHtml(t('report_btn'))}</button>` : ''}
    `;
    container.querySelector('.event-share-btn').addEventListener('click', () => teileEvent(e, ctx));
    if (ctx.onReport) {
      container.querySelector('.report-open-btn').addEventListener('click', () => ctx.onReport(e));
    }
    if (ctx.onClose) {
      container.querySelector('.detail-close').addEventListener('click', () => ctx.onClose(e));
    }
    setupCalendarBox(container, e, ctx);
  }

  global.EnduranceDetail = {
    I18N,
    render,
    renderEmpty,
    displayWettbewerb,
    formatRange,
    formatRangeHtml,
    formatLength,
    eventSlug,
    icsFileName,
    icsMasszahl,
    eventLink,
    eventShareText,
    teileEvent,
    showToast,
    kopiereInAblage
  };
})(typeof window !== 'undefined' ? window : globalThis);
