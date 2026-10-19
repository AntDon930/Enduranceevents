// Clubs: wiederkehrende, offene Treffs (Run Clubs, Social Rides,
// Schwimm-Treffs) - seit dem 19.10.2026, vom Nutzer gewünscht: „Falls der
// User mal an einem Wochenende in Hamburg ist, sieht er auf meiner Karte,
// wo am Wochenende überall Run Clubs oder Cycling oder Swim Clubs
// starten."
//
// Diese Datei ist das gemeinsame Werkzeug von clubs.html (Liste) und
// karte.html (Schalter Events / Clubs / Beide):
//
//   - die TERMINE werden aus der Regel ausgerechnet ("jeden Dienstag
//     19:00", "alle zwei Wochen ab dem 4.10.", "jeden 1. Sonntag im
//     Monat"), nie von Hand eingetragen - sonst wäre der "nächste
//     Termin" nach einer Woche falsch;
//   - die STUFE (Anfänger / Mittel / Fortgeschritten) kommt aus der
//     Quelle oder aus dem Tempo (Grenzen in STUFEN_GRENZEN);
//   - die DETAIL-BOX eines Clubs nutzt die Klassen der Event-Box
//     (event-detail.css), damit Liste und Karte gleich aussehen.
//
// Datenformat: clubs.json, beschrieben in README („Clubs").
(function (global) {
  'use strict';

  const EF = global.EnduranceFilters;
  const EED = global.EnduranceDetail;
  const escapeHtml = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const ARTEN = ['Laufen', 'Fahrrad', 'Schwimmen'];
  const RHYTHMEN = ['woechentlich', 'zweiwoechentlich', 'monatlich', 'einmalig'];
  const STUFEN = ['anfaenger', 'mittel', 'fortgeschritten'];
  const MERKMALE = ['anfaengerfreundlich', 'mehrere_gruppen', 'no_drop', 'kaffee', 'gepaeck', 'dusche', 'frauen'];
  // Wie weit voraus nach dem nächsten Termin gesucht wird. Monatliche
  // Treffs mit Sommerpause brauchen mehr als ein paar Wochen.
  const SUCHE_TAGE = 400;

  const I18N = {
    de: {
      art_Laufen: 'Laufen', art_Fahrrad: 'Rad', art_Schwimmen: 'Schwimmen',
      club: 'Club',
      stufe_anfaenger: 'Anfänger', stufe_mittel: 'Mittel', stufe_fortgeschritten: 'Fortgeschritten',
      rh_woechentlich: 'Wöchentlich', rh_zweiwoechentlich: 'Alle 2 Wochen', rh_monatlich: 'Monatlich', rh_einmalig: 'Einzeltermine',
      wt_lang: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
      wt_plural: ['sonntags', 'montags', 'dienstags', 'mittwochs', 'donnerstags', 'freitags', 'samstags'],
      jeden: (tag) => `Jeden ${tag}`,
      alle2: (tagPl) => `Alle 2 Wochen ${tagPl}`,
      nter: (n, tag) => n === -1 ? `Letzter ${tag} im Monat` : `Jeden ${n}. ${tag} im Monat`,
      uhr: (z) => `${z} Uhr`,
      kostenlos: 'Kostenlos',
      kostet: (b) => `${b} €`,
      anm_nein: 'Einfach vorbeikommen',
      anm_empfohlen: 'Anmeldung empfohlen',
      anm_pflicht: 'Anmeldung nötig',
      m_anfaengerfreundlich: 'Anfängerfreundlich',
      m_mehrere_gruppen: 'Mehrere Tempogruppen',
      m_no_drop: 'No-Drop (niemand wird abgehängt)',
      m_kaffee: 'Kaffee danach',
      m_gepaeck: 'Gepäck abgeben',
      m_dusche: 'Dusche',
      m_frauen: 'Nur Frauen',
      sprache_en: 'Englisch ok',
      d_naechster: 'Nächster Termin',
      d_kein_termin: 'Gerade kein Termin (Saisonpause)',
      d_treffpunkt: 'Treffpunkt',
      d_wann: 'Wann',
      d_strecke: 'Strecke & Tempo',
      d_stufe: 'Stufe',
      d_kosten: 'Kosten',
      d_anmeldung: 'Anmeldung',
      d_weitere: 'Weitere Termine',
      d_web: 'Zur Webseite',
      d_instagram: 'Instagram',
      d_strava: 'Strava',
      d_karte: 'Auf der Karte',
      d_liste: 'In der Liste',
      d_kalender: 'In den Kalender',
      d_teilen: 'Club teilen',
      d_schliessen: 'Schließen',
      d_geprueft: (d) => `Zuletzt geprüft: ${d}. Treffs ändern sich oft – vor dem ersten Mal kurz auf der Webseite oder bei Instagram nachsehen.`,
      d_saison: (a, b) => `Saison ${a} – ${b}`,
      d_link_kopiert: 'Link kopiert',
      dauer: (m) => `ca. ${m} Min.`,
      tempo_unbekannt: 'Tempo: keine Angabe',
      stufe_unbekannt: 'keine Angabe',
      rel_heute: 'heute', rel_morgen: 'morgen'
    },
    en: {
      art_Laufen: 'Running', art_Fahrrad: 'Cycling', art_Schwimmen: 'Swimming',
      club: 'Club',
      stufe_anfaenger: 'Beginner', stufe_mittel: 'Intermediate', stufe_fortgeschritten: 'Advanced',
      rh_woechentlich: 'Weekly', rh_zweiwoechentlich: 'Every 2 weeks', rh_monatlich: 'Monthly', rh_einmalig: 'One-off sessions',
      wt_lang: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
      wt_plural: ['Sundays', 'Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays'],
      jeden: (tag) => `Every ${tag}`,
      alle2: (tagPl) => `Every other week on ${tagPl}`,
      nter: (n, tag) => n === -1 ? `Last ${tag} of the month` : `${['', '1st', '2nd', '3rd', '4th'][n] || n + 'th'} ${tag} of the month`,
      uhr: (z) => z,
      kostenlos: 'Free',
      kostet: (b) => `€${b}`,
      anm_nein: 'Just show up',
      anm_empfohlen: 'Sign-up recommended',
      anm_pflicht: 'Sign-up required',
      m_anfaengerfreundlich: 'Beginner-friendly',
      m_mehrere_gruppen: 'Several pace groups',
      m_no_drop: 'No-drop ride',
      m_kaffee: 'Coffee afterwards',
      m_gepaeck: 'Bag drop',
      m_dusche: 'Showers',
      m_frauen: 'Women only',
      sprache_en: 'English ok',
      d_naechster: 'Next session',
      d_kein_termin: 'No session right now (off-season)',
      d_treffpunkt: 'Meeting point',
      d_wann: 'When',
      d_strecke: 'Distance & pace',
      d_stufe: 'Level',
      d_kosten: 'Cost',
      d_anmeldung: 'Sign-up',
      d_weitere: 'Upcoming',
      d_web: 'Visit website',
      d_instagram: 'Instagram',
      d_strava: 'Strava',
      d_karte: 'On the map',
      d_liste: 'In the list',
      d_kalender: 'Add to calendar',
      d_teilen: 'Share club',
      d_schliessen: 'Close',
      d_geprueft: (d) => `Last checked: ${d}. Clubs change often – check their website or Instagram before you go.`,
      d_saison: (a, b) => `Season ${a} – ${b}`,
      d_link_kopiert: 'Link copied',
      dauer: (m) => `approx. ${m} min`,
      tempo_unbekannt: 'Pace: not stated',
      stufe_unbekannt: 'not stated',
      rel_heute: 'today', rel_morgen: 'tomorrow'
    }
  };

  function tx(lang, key, ...args) {
    const satz = I18N[lang] || I18N.de;
    const wert = key in satz ? satz[key] : I18N.de[key];
    return typeof wert === 'function' ? wert(...args) : wert;
  }

  // ---------- Datum ohne Zeitzonen-Ärger ----------
  //
  // Gerechnet wird mit UTC-Tagen ("2026-10-21" -> Tag 20747): kein
  // Sommerzeit-Sprung kann einen Termin um einen Tag verschieben.

  function tagNr(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    return Math.round(Date.UTC(y, m - 1, d) / 86400000);
  }
  function isoVonTag(nr) {
    const d = new Date(nr * 86400000);
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
  }
  // 1 = Montag … 7 = Sonntag (ISO), wie in clubs.json.
  function isoWochentag(nr) {
    const wt = new Date(nr * 86400000).getUTCDay();
    return wt === 0 ? 7 : wt;
  }
  function heuteIso(jetzt) {
    const n = jetzt || new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
  }
  function minutenJetzt(jetzt) {
    const n = jetzt || new Date();
    return n.getHours() * 60 + n.getMinutes();
  }
  function minutenVon(uhrzeit) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(uhrzeit || '');
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }

  // Liegt der Tag in der Saison ("05-01" bis "09-30"; auch über den
  // Jahreswechsel, "11-01" bis "03-31")?
  function inSaison(club, iso) {
    const s = club.saison;
    if (!s || !s.von || !s.bis) return true;
    const md = iso.slice(5);
    return s.von <= s.bis ? (md >= s.von && md <= s.bis) : (md >= s.von || md <= s.bis);
  }

  // Findet die Regel an diesem Tag statt?
  function terminAmTag(termin, nr) {
    // Einzeltermin (seit dem 19.10.2026, vom Nutzer: „wir können schon auch
    // Einzeltermine aufnehmen … das sind auch Community-Läufe"): genau ein Tag.
    if (termin.rhythmus === 'einmalig') return !!termin.datum && isoVonTag(nr) === termin.datum;
    if (isoWochentag(nr) !== termin.wochentag) return false;
    if (termin.rhythmus === 'woechentlich') return true;
    if (termin.rhythmus === 'zweiwoechentlich') {
      if (!termin.ab) return false;
      const diff = nr - tagNr(termin.ab);
      return ((diff % 14) + 14) % 14 === 0;
    }
    if (termin.rhythmus === 'monatlich') {
      const tagImMonat = new Date(nr * 86400000).getUTCDate();
      if (termin.nter === -1) {
        const d = new Date(nr * 86400000);
        const letzter = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
        return tagImMonat + 7 > letzter;
      }
      return Math.ceil(tagImMonat / 7) === (termin.nter || 1);
    }
    return false;
  }

  // Alle Termine von `vonIso` bis `bisIso` (je einschließlich), nach Tag
  // und Uhrzeit sortiert: [{ datum, uhrzeit, termin }].
  // opts.jetzt: ein Termin von HEUTE, dessen Uhrzeit vorbei ist, zählt
  // nicht mehr (sonst stünde um 20 Uhr noch "heute 19:00" als nächster).
  function termineImZeitraum(club, vonIso, bisIso, opts) {
    const liste = [];
    if (!club || !Array.isArray(club.termine)) return liste;
    const von = tagNr(vonIso);
    const bis = tagNr(bisIso);
    const ausfaelle = new Set(club.ausfaelle || []);
    const heute = opts && opts.jetzt ? tagNr(heuteIso(opts.jetzt)) : null;
    const minute = opts && opts.jetzt ? minutenJetzt(opts.jetzt) : null;
    for (let nr = von; nr <= bis; nr++) {
      const iso = isoVonTag(nr);
      if (ausfaelle.has(iso) || !inSaison(club, iso)) continue;
      club.termine.forEach(termin => {
        if (!terminAmTag(termin, nr)) return;
        if (heute === nr && minute != null) {
          const m = minutenVon(termin.uhrzeit);
          if (m != null && m < minute) return;
        }
        liste.push({ datum: iso, uhrzeit: termin.uhrzeit || '', termin });
      });
    }
    liste.sort((a, b) => (a.datum < b.datum ? -1 : a.datum > b.datum ? 1 : (a.uhrzeit < b.uhrzeit ? -1 : a.uhrzeit > b.uhrzeit ? 1 : 0)));
    return liste;
  }

  function naechsteTermine(club, anzahl, jetzt) {
    const n = jetzt || new Date();
    const von = heuteIso(n);
    const bis = isoVonTag(tagNr(von) + SUCHE_TAGE);
    return termineImZeitraum(club, von, bis, { jetzt: n }).slice(0, anzahl || 1);
  }

  function naechsterTermin(club, jetzt) {
    return naechsteTermine(club, 1, jetzt)[0] || null;
  }

  // ---------- Zeiträume für den Filter "Wann" ----------
  //
  // Dieselben Wörter auf Liste und Karte (?wann=…). "Wochenende" wie der
  // Zeitraum-Knopf der Events (filters.js): ab Samstag, an einem
  // Sonntag nur der Sonntag.
  const WANN = ['heute', 'morgen', 'wochenende', 'woche'];
  function wannZeitraum(key, jetzt) {
    const n = jetzt || new Date();
    const heute = tagNr(heuteIso(n));
    const wt = isoWochentag(heute);
    if (key === 'heute') return [isoVonTag(heute), isoVonTag(heute)];
    if (key === 'morgen') return [isoVonTag(heute + 1), isoVonTag(heute + 1)];
    if (key === 'wochenende') {
      if (wt === 7) return [isoVonTag(heute), isoVonTag(heute)];
      const sa = wt === 6 ? heute : heute + (6 - wt);
      return [isoVonTag(sa), isoVonTag(sa + 1)];
    }
    if (key === 'woche') return [isoVonTag(heute), isoVonTag(heute + 6)];
    return null;
  }

  // ---------- Tempo und Stufe ----------
  //
  // Die Grenzen (vom Nutzer: „kann man an dem Pace festlegen"):
  //   Laufen     min/km     langsamer als 6:00 Anfänger, 5:00–6:00 Mittel, schneller Fortgeschritten
  //   Fahrrad    km/h       unter 25 Anfänger, 25–30 Mittel, über 30 Fortgeschritten
  //   Schwimmen  min/100 m  langsamer als 2:15 Anfänger, 1:45–2:15 Mittel, schneller Fortgeschritten
  // Eine Spanne ("5:30–6:30") kann zwei Stufen überdecken - viele Clubs
  // laufen in mehreren Gruppen.
  const STUFEN_GRENZEN = {
    Laufen: { einheit: 'sek', anfaenger: 360, fortgeschritten: 300 },
    Schwimmen: { einheit: 'sek', anfaenger: 135, fortgeschritten: 105 },
    Fahrrad: { einheit: 'kmh', anfaenger: 25, fortgeschritten: 30 }
  };

  function sekunden(wert) {
    if (typeof wert === 'number') return wert;
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(wert || '').trim());
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }

  function stufeVonWert(art, wert) {
    const g = STUFEN_GRENZEN[art];
    if (!g || wert == null) return null;
    if (g.einheit === 'sek') {
      const s = sekunden(wert);
      if (s == null) return null;
      if (s > g.anfaenger) return 0;
      if (s >= g.fortgeschritten) return 1;
      return 2;
    }
    const v = Number(wert);
    if (!Number.isFinite(v)) return null;
    if (v < g.anfaenger) return 0;
    if (v <= g.fortgeschritten) return 1;
    return 2;
  }

  function stufenAusPace(art, pace) {
    if (!pace) return [];
    const a = stufeVonWert(art, pace.von);
    const b = stufeVonWert(art, pace.bis);
    const werte = [a, b].filter(x => x != null);
    if (!werte.length) return [];
    const lo = Math.min(...werte), hi = Math.max(...werte);
    return STUFEN.slice(lo, hi + 1);
  }

  // Die Stufen eines Clubs: aus der Quelle (`stufen`), sonst aus dem
  // Tempo des Clubs und seiner Einheiten. Leer = keine Angabe.
  function stufen(club) {
    if (Array.isArray(club.stufen) && club.stufen.length) {
      return STUFEN.filter(s => club.stufen.includes(s));
    }
    const menge = new Set(stufenAusPace(club.art, club.pace));
    (club.termine || []).forEach(t => stufenAusPace(club.art, t.pace).forEach(s => menge.add(s)));
    return STUFEN.filter(s => menge.has(s));
  }

  function formatPace(art, pace, lang) {
    if (!pace || (pace.von == null && pace.bis == null)) return '';
    const sep = '–';
    const teil = (v) => (typeof v === 'number' && EF ? EF.formatNumber(v, lang) : String(v));
    const spanne = pace.von != null && pace.bis != null && String(pace.von) !== String(pace.bis)
      ? `${teil(pace.von)}${sep}${teil(pace.bis)}` : teil(pace.von != null ? pace.von : pace.bis);
    if (art === 'Fahrrad') return `${spanne} km/h`;
    if (art === 'Schwimmen') return `${spanne} min/100 m`;
    return `${spanne} min/km`;
  }

  function formatDistanz(km, lang) {
    if (!Array.isArray(km) || !km.length) return '';
    const f = (v) => EF && EF.formatNumber ? EF.formatNumber(v, lang) : String(v);
    return km[0] === km[1] || km[1] == null ? `${f(km[0])} km` : `${f(km[0])}–${f(km[1])} km`;
  }

  function formatKosten(club, lang) {
    const k = club.kosten || {};
    if (k.gratis) return tx(lang, 'kostenlos') + (k.text ? ` (${k.text})` : '');
    if (k.text) return k.text;
    if (k.betrag_eur != null) return tx(lang, 'kostet', EF ? EF.formatNumber(k.betrag_eur, lang) : k.betrag_eur);
    return '–';
  }

  function istGratis(club) {
    return !!(club.kosten && club.kosten.gratis);
  }

  // "Jeden Dienstag, 19:00 Uhr" / "Alle 2 Wochen samstags, 09:00 Uhr" /
  // "Jeden 1. Sonntag im Monat, 10:00 Uhr".
  function formatRegel(termin, lang) {
    if (termin.rhythmus === 'einmalig') {
      const d = EF ? EF.formatDateLong(termin.datum, lang).replace(/\s\d{4}$/, '') : termin.datum;
      return termin.uhrzeit ? `${d}, ${tx(lang, 'uhr', termin.uhrzeit)}` : d;
    }
    const wtIdx = termin.wochentag % 7;   // 7 (So) -> 0
    const tag = tx(lang, 'wt_lang')[wtIdx];
    let text;
    if (termin.rhythmus === 'zweiwoechentlich') text = tx(lang, 'alle2', tx(lang, 'wt_plural')[wtIdx]);
    else if (termin.rhythmus === 'monatlich') text = tx(lang, 'nter', termin.nter || 1, tag);
    else text = tx(lang, 'jeden', tag);
    return termin.uhrzeit ? `${text}, ${tx(lang, 'uhr', termin.uhrzeit)}` : text;
  }

  // Der Rhythmus des Clubs als ein Wort (für die Kachel): der häufigste
  // seiner Einheiten.
  function rhythmusVon(club) {
    const r = (club.termine || []).map(t => t.rhythmus);
    if (r.includes('woechentlich')) return 'woechentlich';
    if (r.includes('zweiwoechentlich')) return 'zweiwoechentlich';
    if (r.includes('monatlich')) return 'monatlich';
    return r[0] || 'woechentlich';
  }

  function formatTerminKurz(t, lang) {
    if (!t) return '';
    const rel = EF ? EF.relativeDays(t.datum, lang) : '';
    const datum = EF ? EF.formatDateLong(t.datum, lang).replace(/\s\d{4}$/, '') : t.datum;
    const vorn = rel === 'heute' || rel === 'today' || rel === 'morgen' || rel === 'tomorrow'
      ? rel.charAt(0).toUpperCase() + rel.slice(1) : datum;
    return `${vorn}${t.uhrzeit ? ', ' + tx(lang, 'uhr', t.uhrzeit) : ''}`;
  }

  function sportClass(art) { return EED ? EED.sportClass(art) : 'sport-laufen'; }
  function sportIcon(art, size) { return EED ? EED.sportIcon(art, size) : ''; }

  // ---------- Suche, Filter, Links ----------

  function heuhaufen(club) {
    return [club.name, club.stadt, club.treffpunkt, club.art].filter(Boolean).join(' ').toLowerCase();
  }

  // Die Filter der Clubs-Liste (und des Schalters auf der Karte):
  // f = { art: Set, stufe: Set, stadt: Set, gratis: bool, wann: key|null,
  //       suche: string, zeitraum: [von, bis]|null, tage: Set|null }
  function passt(club, f, jetzt) {
    if (f.art && f.art.size && !f.art.has(club.art)) return false;
    if (f.stadt && f.stadt.size && !f.stadt.has(club.stadt)) return false;
    if (f.land && f.land.size && !f.land.has(club.land)) return false;
    if (f.gratis && !istGratis(club)) return false;
    if (f.stufe && f.stufe.size) {
      const s = stufen(club);
      if (!s.some(x => f.stufe.has(x))) return false;
    }
    if (f.suche) {
      const h = heuhaufen(club);
      if (!f.suche.toLowerCase().split(/\s+/).filter(Boolean).every(w => h.includes(w))) return false;
    }
    if (f.origin && f.radiusKm != null && EF) {
      if (club.lat == null || EF.haversineKm(f.origin.lat, f.origin.lon, club.lat, club.lon) > f.radiusKm) return false;
    }
    const zeitraum = f.zeitraum || (f.wann ? wannZeitraum(f.wann, jetzt) : null);
    if (zeitraum) {
      const heute = heuteIso(jetzt);
      const von = zeitraum[0] < heute ? heute : zeitraum[0];
      if (von > zeitraum[1]) return false;
      const termine = termineImZeitraum(club, von, zeitraum[1], { jetzt: jetzt || new Date() });
      if (!termine.length) return false;
    }
    if (f.tage && f.tage.size) {
      const tage = Array.from(f.tage).sort();
      const termine = termineImZeitraum(club, tage[0], tage[tage.length - 1], { jetzt: jetzt || new Date() });
      if (!termine.some(t => f.tage.has(t.datum))) return false;
    }
    return true;
  }

  function clubLink(club) {
    return 'clubs.html?club=' + encodeURIComponent(club.id);
  }
  function kartenLink(club) {
    return 'karte.html?ebene=clubs&club=' + encodeURIComponent(club.id);
  }

  // ---------- Kalender: EIN wiederkehrender Termin ----------
  //
  // Eine .ics mit RRULE statt einer Datei je Termin: Der Kalender zeigt
  // den Treff dann jede Woche, ohne dass wir je etwas nachschieben.
  const ICS_TAG = ['', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'];
  function rrule(termin) {
    if (termin.rhythmus === 'einmalig') return null;
    const tag = ICS_TAG[termin.wochentag];
    if (termin.rhythmus === 'zweiwoechentlich') return `FREQ=WEEKLY;INTERVAL=2;BYDAY=${tag}`;
    if (termin.rhythmus === 'monatlich') return `FREQ=MONTHLY;BYDAY=${termin.nter === -1 ? -1 : (termin.nter || 1)}${tag}`;
    return `FREQ=WEEKLY;BYDAY=${tag}`;
  }
  function icsText(club, naechster, lang) {
    const termin = naechster.termin;
    const [h, m] = (termin.uhrzeit || '09:00').split(':');
    const start = naechster.datum.replace(/-/g, '') + `T${h.padStart(2, '0')}${m}00`;
    const dauer = club.dauer_min || 60;
    const endeMin = Number(h) * 60 + Number(m) + dauer;
    const endeTag = isoVonTag(tagNr(naechster.datum) + Math.floor(endeMin / 1440)).replace(/-/g, '');
    const ende = `${endeTag}T${String(Math.floor((endeMin % 1440) / 60)).padStart(2, '0')}${String(endeMin % 60).padStart(2, '0')}00`;
    const esc = (s) => String(s || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
    const beschreibung = [lang === 'en' ? club.beschreibung_en : club.beschreibung_de, club.webseite || club.instagram || ''].filter(Boolean).join('\n');
    return [
      'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//endurance-events.de//Clubs//DE', 'CALSCALE:GREGORIAN',
      'BEGIN:VTIMEZONE', 'TZID:Europe/Berlin',
      'BEGIN:DAYLIGHT', 'TZOFFSETFROM:+0100', 'TZOFFSETTO:+0200', 'TZNAME:CEST', 'DTSTART:19700329T020000', 'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU', 'END:DAYLIGHT',
      'BEGIN:STANDARD', 'TZOFFSETFROM:+0200', 'TZOFFSETTO:+0100', 'TZNAME:CET', 'DTSTART:19701025T030000', 'RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU', 'END:STANDARD',
      'END:VTIMEZONE',
      'BEGIN:VEVENT',
      `UID:club-${club.id}-${termin.wochentag}-${(termin.uhrzeit || '').replace(':', '')}@endurance-events.de`,
      `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')}`,
      `DTSTART;TZID=Europe/Berlin:${start}`,
      `DTEND;TZID=Europe/Berlin:${ende}`,
      rrule(termin) ? `RRULE:${rrule(termin)}` : null,
      `SUMMARY:${esc(club.name)}`,
      `LOCATION:${esc([club.treffpunkt, club.stadt].filter(Boolean).join(', '))}`,
      `DESCRIPTION:${esc(beschreibung)}`,
      club.webseite ? `URL:${club.webseite}` : null,
      'END:VEVENT', 'END:VCALENDAR'
    ].filter(Boolean).join('\r\n') + '\r\n';
  }

  // ---------- Die Detail-Box ----------

  const PIN_SVG = '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>';
  const UHR_SVG = '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>';
  const STRECKE_SVG = '<path d="M4 17c3-6 5-6 8 0s5 6 8 0"/><circle cx="4" cy="17" r="1.5"/><circle cx="20" cy="17" r="1.5"/>';
  const STUFE_SVG = '<path d="M5 20v-5M12 20V9M19 20V4"/>';
  const EURO_SVG = '<path d="M17 6.5A6.5 6.5 0 1 0 17 17.5"/><path d="M4 10h9M4 14h9"/>';
  const ANM_SVG = '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>';
  const EXT_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9"/><path d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6"/></svg>';
  const SHARE_SVG = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg>';
  const CAL_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/></svg>';
  const MAP_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/></svg>';
  const LIST_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  const GRUPPE_SVG = '<circle cx="8" cy="8" r="3"/><circle cx="16.5" cy="9" r="2.5"/><path d="M2.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5"/><path d="M13.5 14.6c.9-.4 1.9-.6 3-.6 2.4 0 4.3 1.6 4.8 4.5"/>';

  function icon(pfad, size) {
    const px = size || 16;
    return `<svg viewBox="0 0 24 24" width="${px}" height="${px}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${pfad}</svg>`;
  }
  function fakt(pfad, titel, inhalt) {
    return `<div class="fact"><span class="fact-icon" aria-hidden="true">${icon(pfad)}</span><div><dt>${escapeHtml(titel)}</dt><dd>${inhalt}</dd></div></div>`;
  }
  function gruppenIcon(size) { return icon(GRUPPE_SVG, size); }

  function formatGeprueft(iso, lang) {
    return EF ? EF.formatDate(iso, lang) : iso;
  }

  function streckeText(club, lang) {
    const teile = [];
    const d = formatDistanz(club.distanz_km, lang);
    if (d) teile.push(d);
    if (club.dauer_min) teile.push(tx(lang, 'dauer', club.dauer_min));
    const p = formatPace(club.art, club.pace, lang);
    if (p) teile.push(p);
    return teile.join(' · ');
  }

  const TYP_EN = { Rennrad: 'Road bike', Gravel: 'Gravel', MTB: 'MTB', gemischt: 'Mixed bikes',
    Freiwasser: 'Open water', Hallenbad: 'Indoor pool', Freibad: 'Outdoor pool' };
  function merkmalTags(club, lang) {
    const tags = [];
    (club.merkmale || []).forEach(m => { if (MERKMALE.includes(m)) tags.push(tx(lang, 'm_' + m)); });
    if (club.rad_typ) tags.push(lang === 'en' ? (TYP_EN[club.rad_typ] || club.rad_typ) : club.rad_typ);
    if (club.schwimm_ort) tags.push(lang === 'en' ? (TYP_EN[club.schwimm_ort] || club.schwimm_ort) : club.schwimm_ort);
    if ((club.sprachen || []).includes('en')) tags.push(tx(lang, 'sprache_en'));
    if (club.saison && club.saison.von && club.saison.bis) {
      const f = (md) => { const [mo, d] = md.split('-'); return `${Number(d)}.${Number(mo)}.`; };
      tags.push(tx(lang, 'd_saison', f(club.saison.von), f(club.saison.bis)));
    }
    return tags;
  }

  function teile(club, lang) {
    const url = new URL(clubLink(club), global.location.href).href;
    const titel = club.name;
    if (navigator.share) {
      navigator.share({ title: titel, text: `${titel} – ${club.stadt}`, url }).catch(() => {});
      return;
    }
    const fertig = () => { if (EED && EED.showToast) EED.showToast(tx(lang, 'd_link_kopiert')); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(fertig, () => {});
  }

  // ctx: { lang, onClose?, mapLink?: bool, listLink?: bool, distanceText? }
  function renderDetail(container, club, ctx) {
    const lang = ctx.lang || 'de';
    const jetzt = new Date();
    const kommende = naechsteTermine(club, 4, jetzt);
    const naechster = kommende[0] || null;
    const s = stufen(club);
    const kat = `${tx(lang, 'art_' + club.art)} · ${tx(lang, 'club')}`;
    let datumGross, relativ = '';
    if (naechster) {
      datumGross = escapeHtml(EF.formatDateLong(naechster.datum, lang)) + (naechster.uhrzeit ? `<br>${escapeHtml(tx(lang, 'uhr', naechster.uhrzeit))}` : '');
      relativ = EF.relativeDays(naechster.datum, lang);
    } else {
      datumGross = escapeHtml(tx(lang, 'd_kein_termin'));
    }
    const regeln = (club.termine || []).map(t =>
      escapeHtml(formatRegel(t, lang)) + (t.bezeichnung ? ` <span class="club-bez">(${escapeHtml(t.bezeichnung)})</span>` : '')
    ).join('<br>');
    const strecke = streckeText(club, lang);
    const einheitenTempo = (club.termine || []).filter(t => t.pace || t.distanz_km).map(t => {
      const teil = [formatDistanz(t.distanz_km, lang), formatPace(club.art, t.pace, lang)].filter(Boolean).join(' · ');
      return teil ? `${t.bezeichnung ? escapeHtml(t.bezeichnung) + ': ' : ''}${escapeHtml(teil)}` : '';
    }).filter(Boolean);
    const streckeHtml = [strecke ? escapeHtml(strecke) : '', ...einheitenTempo].filter(Boolean).join('<br>') || escapeHtml(tx(lang, 'tempo_unbekannt'));
    const anm = club.anmeldung ? tx(lang, 'anm_' + club.anmeldung) + (club.anmeldung_ueber ? ` (${club.anmeldung_ueber})` : '') : '–';
    const tags = merkmalTags(club, lang);
    const beschreibung = lang === 'en' ? (club.beschreibung_en || club.beschreibung_de) : club.beschreibung_de;
    const hauptLink = club.webseite || club.instagram || club.strava;
    const weitere = kommende.slice(1);

    container.innerHTML = `
      <div class="detail-head">
        <div class="detail-head-text">
          <div class="detail-overline">${escapeHtml(tx(lang, 'd_naechster'))}</div>
          <div class="detail-date">${datumGross}</div>
          ${relativ ? `<div class="detail-relative">${escapeHtml(relativ)}</div>` : ''}
        </div>
        <button type="button" class="detail-share club-share-btn" title="${escapeHtml(tx(lang, 'd_teilen'))}" aria-label="${escapeHtml(tx(lang, 'd_teilen'))}">${SHARE_SVG}</button>
        ${ctx.onClose ? `<button type="button" class="detail-share detail-close" title="${escapeHtml(tx(lang, 'd_schliessen'))}" aria-label="${escapeHtml(tx(lang, 'd_schliessen'))}">&#10005;</button>` : ''}
      </div>
      <div class="detail-badges">
        <div class="detail-badge ${sportClass(club.art)}">${sportIcon(club.art, 15)}<span>${escapeHtml(kat)}</span></div>
        <div class="detail-badge detail-badge--club">${gruppenIcon(15)}<span>${escapeHtml(tx(lang, 'rh_' + rhythmusVon(club)))}</span></div>
      </div>
      <h2>${escapeHtml(club.name)}</h2>
      ${beschreibung ? `<p class="club-beschreibung">${escapeHtml(beschreibung)}</p>` : ''}
      ${tags.length ? `<div class="club-tags">${tags.map(x => `<span class="club-tag">${escapeHtml(x)}</span>`).join('')}</div>` : ''}
      <dl class="detail-grid club-grid">
        ${fakt(PIN_SVG, tx(lang, 'd_treffpunkt'), `${escapeHtml(club.treffpunkt || '')}${club.treffpunkt ? ',<br>' : ''}${escapeHtml(club.stadt)}${ctx.distanceText ? ` · ${escapeHtml(ctx.distanceText)}` : ''}`)}
        ${fakt(UHR_SVG, tx(lang, 'd_wann'), regeln || '–')}
        ${fakt(STRECKE_SVG, tx(lang, 'd_strecke'), streckeHtml)}
        ${fakt(STUFE_SVG, tx(lang, 'd_stufe'), s.length ? s.map(x => `<span class="stufe-pill stufe-${x}">${escapeHtml(tx(lang, 'stufe_' + x))}</span>`).join(' ') : escapeHtml(tx(lang, 'stufe_unbekannt')))}
        ${fakt(EURO_SVG, tx(lang, 'd_kosten'), escapeHtml(formatKosten(club, lang)))}
        ${fakt(ANM_SVG, tx(lang, 'd_anmeldung'), escapeHtml(anm))}
      </dl>
      ${weitere.length ? `<div class="detail-section-title">${escapeHtml(tx(lang, 'd_weitere'))}</div>
        <ul class="club-weitere">${weitere.map(t => `<li>${escapeHtml(formatTerminKurz(t, lang))}${t.termin.bezeichnung ? ` · ${escapeHtml(t.termin.bezeichnung)}` : ''}</li>`).join('')}</ul>` : ''}
      ${hauptLink ? `<a class="detail-link club-hauptlink" href="${escapeHtml(hauptLink)}" target="_blank" rel="noopener noreferrer"><span>${escapeHtml(club.webseite ? tx(lang, 'd_web') : club.instagram ? tx(lang, 'd_instagram') : tx(lang, 'd_strava'))}</span>${EXT_SVG}</a>` : ''}
      <div class="detail-actions">
        ${naechster ? `<button type="button" class="cal-btn club-cal-btn">${CAL_SVG}<span>${escapeHtml(tx(lang, 'd_kalender'))}</span></button>` : ''}
        ${club.instagram && club.webseite ? `<a class="cal-btn club-social" href="${escapeHtml(club.instagram)}" target="_blank" rel="noopener noreferrer">${escapeHtml(tx(lang, 'd_instagram'))}</a>` : ''}
        ${club.strava && (club.webseite || club.instagram) ? `<a class="cal-btn club-social" href="${escapeHtml(club.strava)}" target="_blank" rel="noopener noreferrer">${escapeHtml(tx(lang, 'd_strava'))}</a>` : ''}
        ${ctx.mapLink ? `<a class="cal-btn detail-map-btn" href="${escapeHtml(kartenLink(club))}">${MAP_SVG}<span>${escapeHtml(tx(lang, 'd_karte'))}</span></a>` : ''}
        ${ctx.listLink ? `<a class="cal-btn detail-list-btn" href="${escapeHtml(clubLink(club))}">${LIST_SVG}<span>${escapeHtml(tx(lang, 'd_liste'))}</span></a>` : ''}
      </div>
      ${club.geprueft ? `<p class="club-geprueft">${escapeHtml(tx(lang, 'd_geprueft', formatGeprueft(club.geprueft, lang)))}</p>` : ''}
    `;
    container.querySelector('.club-share-btn').addEventListener('click', () => teile(club, lang));
    if (ctx.onClose) container.querySelector('.detail-close').addEventListener('click', () => ctx.onClose(club));
    const cal = container.querySelector('.club-cal-btn');
    if (cal) {
      cal.addEventListener('click', () => {
        const blob = new Blob([icsText(club, naechster, lang)], { type: 'text/calendar;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `club-${club.id}.ics`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      });
    }
    const stats = global.EnduranceStats;
    if (stats) {
      stats.event('detail', { ev: 'Club: ' + club.name, sp: club.art });
      container.querySelectorAll('.club-hauptlink, .club-social').forEach(a => {
        a.addEventListener('click', () => stats.event('veranstalter', { ev: 'Club: ' + club.name, sp: club.art }));
      });
    }
  }

  // ---------- Laden ----------

  async function loadClubs() {
    const res = await fetch('clubs.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const daten = await res.json();
    const liste = Array.isArray(daten) ? daten : (daten.clubs || []);
    // Unsichere Clubs (`pruefung_offen`, Korrekturliste
    // scripts/clubs_korrekturliste.py) sind ausgeblendet, bis der Betreiber
    // sie geprüft hat – wie bei den Events. Mit ?pruefen=1 in der Adresse
    // sind sie zum Nachsehen sichtbar.
    let pruefen = false;
    try { pruefen = new URLSearchParams(global.location.search).get('pruefen') === '1'; } catch (e) { /* ignorieren */ }
    return liste.filter(c => c && c.id && ARTEN.includes(c.art) && Array.isArray(c.termine) && c.termine.length
      && (pruefen || !c.pruefung_offen)
      // Nur noch vergangene Einzeltermine: der Club ist (vorerst) vorbei.
      && (pruefen || !c.termine.every(t => t.rhythmus === 'einmalig') || naechsterTermin(c)));
  }

  global.EnduranceClubs = {
    I18N, ARTEN, RHYTHMEN, STUFEN, MERKMALE, WANN, STUFEN_GRENZEN,
    tx, loadClubs, termineImZeitraum, naechsteTermine, naechsterTermin, wannZeitraum,
    stufen, stufenAusPace, formatPace, formatDistanz, formatKosten, formatRegel, formatTerminKurz,
    rhythmusVon, istGratis, passt, clubLink, kartenLink, icsText, rrule, renderDetail,
    sportClass, sportIcon, gruppenIcon, streckeText, merkmalTags
  };
})(typeof window !== 'undefined' ? window : globalThis);
