// Die Filter-Bedienelemente von events.html UND karte.html: die
// Spalten-/Filterknöpfe mit ihrem schwebenden Panel (Name, Datum, Land,
// Stadt/Ort mit Umkreissuche, Sportart, Kategorie, Länge).
//
// Warum ausgelagert: Auf der Karte ließen sich Filter nur ansehen und
// wegnehmen, gesetzt wurden sie ausschließlich in der Liste. Beide Seiten
// zeigen jetzt dieselben Knöpfe und dasselbe Panel - einmal gebaut, nicht
// zweimal nachgebaut. Der Filterzustand selbst und die Regeln, was ein
// Filter bedeutet, stehen in filters.js; hier ist nur die Bedienung.
//
// Anbindung: EnduranceFilterUI.create({ state, getEvents, t, tv, getLang,
// onChange, setOrigin }) gibt einen Bedienteil zurück. `onChange` ruft die
// Seite auf ihre Art neu auf (Liste: Tabelle, Karte: Marker), `setOrigin`
// ist optional und darf mehr tun als den Ausgangspunkt zu setzen.
//
// Das Panel folgt seinem Knopf beim Scrollen und schließt sich NICHT
// (siehe folgeDemKnopf) - das war auf 390 px nötig, sonst ließ sich der
// Stadt/Ort-Filter gar nicht öffnen.
(function (global) {
  'use strict';

  const EF = global.EnduranceFilters;

  // Texte der Panels und die Spaltennamen, die beide Seiten brauchen.
  // Jede Seite mischt sie in ihr eigenes I18N-Objekt (Object.assign),
  // damit t() unverändert funktioniert.
  const I18N = {
    de: {
      col_datum: 'Datum',
      col_name: 'Name',
      col_sportart: 'Sportart',
      col_standort: 'Stadt/Ort',
      col_land: 'Land',
      col_kategorie: 'Kategorie',
      col_laenge: 'Länge',
      select_all: 'Alle',
      select_none: 'Keine',
      name_search_placeholder: 'Name suchen…',
      range_von_km: 'Von (km)',
      range_bis_km: 'Bis (km)',
      no_values: 'Keine Werte für die aktuelle Auswahl.',
      no_dates: 'Keine Termine vorhanden.',
      radius_title: 'Umkreissuche',
      geo_btn: '📍 Aktuellen Standort verwenden',
      geo_origin_set: (label) => `Ausgangspunkt: ${label}`,
      geo_no_origin: 'Kein Ausgangspunkt gewählt.',
      origin_clear: 'Ausgangspunkt entfernen',
      radius_value: (km) => `Umkreis: ${km} km`,
      radius_disabled: 'Umkreis (erst Standort oder Ort wählen)',
      place_search_label: 'Ort oder PLZ als Ausgangspunkt',
      place_search_placeholder: 'Stadt, Ort oder PLZ eingeben…',
      places_loading: 'Ortsverzeichnis wird geladen…',
      places_error: 'Ortsverzeichnis konnte nicht geladen werden.',
      places_empty: 'Kein Ort gefunden.',
      geo_locating: 'Standort wird ermittelt…',
      geo_unsupported: 'Geolocation wird von diesem Browser nicht unterstützt.',
      geo_unavailable: (msg) => `Standort nicht verfügbar: ${msg}`,
      geo_denied: 'Standortzugriff wurde abgelehnt. Tippe noch einmal auf den Knopf – dann fragt der Browser erneut.',
      geo_denied_blocked: 'Der Browser hat gar nicht erst gefragt: Die Erlaubnis für diese Seite ist gespeichert abgelehnt oder systemweit aus. So gibst du sie frei:',
      geo_retry: '📍 Standort erneut versuchen',
      geo_help_ios: [
        'Einstellungen → Apps → Safari → Standort auf „Fragen" stellen (ältere iOS-Versionen: Einstellungen → Safari → Standort).',
        'Einstellungen → Datenschutz & Sicherheit → Ortungsdienste einschalten, dort „Safari-Websites" auf „Beim Verwenden der App".',
        'Diese Seite neu laden und noch einmal auf den Knopf tippen.'
      ],
      geo_help_other: [
        'Auf das Schloss- bzw. Info-Symbol links in der Adresszeile tippen und den Standort für diese Seite erlauben.',
        'Danach die Seite neu laden und noch einmal auf den Knopf tippen.'
      ],
      geo_help_fallback: 'Geht auch ohne Standort: unten einfach Ort oder PLZ eintippen – der Umkreis arbeitet genauso.',
      geo_timeout: 'Die Standortabfrage hat zu lange gedauert. Bitte noch einmal versuchen.',
      geo_insecure: 'Standortabfrage geht nur über HTTPS. Lokal getestet? Dann die Seite über https:// oder http://localhost öffnen.',
      geo_current_label: 'Aktueller Standort'
    },
    en: {
      col_datum: 'Date',
      col_name: 'Name',
      col_sportart: 'Sport',
      col_standort: 'City',
      col_land: 'Country',
      col_kategorie: 'Category',
      col_laenge: 'Length',
      select_all: 'All',
      select_none: 'None',
      name_search_placeholder: 'Search name…',
      range_von_km: 'From (km)',
      range_bis_km: 'To (km)',
      no_values: 'No values for the current selection.',
      no_dates: 'No dates available.',
      radius_title: 'Radius search',
      geo_btn: '📍 Use current location',
      geo_origin_set: (label) => `Starting point: ${label}`,
      geo_no_origin: 'No starting point selected.',
      origin_clear: 'Remove starting point',
      radius_value: (km) => `Radius: ${km} km`,
      radius_disabled: 'Radius (pick a location or place first)',
      place_search_label: 'Place or postcode as starting point',
      place_search_placeholder: 'Enter a city, town or postcode…',
      places_loading: 'Loading place directory…',
      places_error: 'Could not load the place directory.',
      places_empty: 'No place found.',
      geo_locating: 'Getting location…',
      geo_unsupported: 'Geolocation is not supported by this browser.',
      geo_unavailable: (msg) => `Location unavailable: ${msg}`,
      geo_denied: 'Location access was denied. Tap the button again and the browser will ask once more.',
      geo_denied_blocked: 'The browser did not even ask: permission for this site is stored as denied, or location is off system-wide. Here is how to allow it:',
      geo_retry: '📍 Try location again',
      geo_help_ios: [
        'Settings → Apps → Safari → Location: set it to “Ask” (older iOS: Settings → Safari → Location).',
        'Settings → Privacy & Security → Location Services: turn it on and set “Safari Websites” to “While Using the App”.',
        'Reload this page and tap the button again.'
      ],
      geo_help_other: [
        'Tap the lock or info icon at the left of the address bar and allow location for this site.',
        'Then reload the page and tap the button again.'
      ],
      geo_help_fallback: 'Works without location too: just type a place or postcode below – the radius search behaves the same.',
      geo_timeout: 'Getting your location took too long. Please try again.',
      geo_insecure: 'Location lookup only works over HTTPS. Testing locally? Open the page via https:// or http://localhost.',
      geo_current_label: 'Current location'
    }
  };

  // ISO-Ländercode -> der Landname, wie er in events.json steht
  // (places.json speichert DE/AT/CH, die Anzeige übersetzt tv('land', …)).
  const LAND_BY_CODE = { DE: 'Deutschland', AT: 'Österreich', CH: 'Schweiz' };

  const MONTH_NAMES = {
    de: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
    en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
  };
  // Zuordnung Sportart -> erlaubte Kategorie-Werte.
  const ART2_BY_ART1 = {
    'Laufen': ['Straße', 'Trail/Cross', 'Bahn', 'Berg', 'Hindernis', 'Backcountry Ultra'],
    'Schwimmen': ['Freiwasser', 'Becken'],
    'Fahrrad': ['Straße', 'Zeitfahren', 'Mountainbike', 'Gravel', 'Bahn', 'Cyclecross'],
    // Triathlon ist die Mehrsport-Schublade: Duathlon (Laufen-Rad-Laufen),
    // Aquathlon (Schwimmen-Laufen) und SwimRun sind keine Triathlons im
    // Wortsinn, gehören aber zur selben Familie - und die genaue Form ist
    // genau die Auskunft, die jemand hier sucht. Dieselben Werte erzeugt
    // ART2_KEYWORDS_TRIATHLON in scraper_lib.py; test_kategorie
    // vergleicht beide Listen.
    'Triathlon': ['Straße', 'Cross', 'Duathlon', 'Aquathlon', 'Swimrun',
                  'Quadrathlon', 'Indoor']
  };
  // Alle Kategorien, die ART2_BY_ART1 kennt - die Gegenstuecke zu
  // BEKANNTE_WERTE fuer `art2`.
  const ALLE_ART2 = Object.keys(ART2_BY_ART1)
    .reduce((alle, a1) => alle.concat(ART2_BY_ART1[a1]), []);

  // Die filterbaren Spalten. Dieselbe Liste baut in der Liste die
  // Tabellenköpfe und auf der Karte die Knopfreihe - eine Spalte
  // hinzufügen heißt: hier eintragen, nicht an zwei Stellen.
  const COLUMNS = [
    { key: 'name', labelKey: 'col_name', type: 'text' },
    { key: 'datum', labelKey: 'col_datum', type: 'date-tree' },
    { key: 'land', labelKey: 'col_land', type: 'checkbox' },
    { key: 'standort', labelKey: 'col_standort', type: 'standort' },
    { key: 'art1', labelKey: 'col_sportart', type: 'checkbox' },
    { key: 'art2', labelKey: 'col_kategorie', type: 'checkbox' },
    { key: 'laenge_km', labelKey: 'col_laenge', type: 'number-range' }
  ];

  // Welche Werte die Seite überhaupt kennt - unabhängig davon, ob heute
  // schon ein Event dazu in den Daten steht. Nur der Abo-Dialog fragt so
  // (`alleWerte: true`): Ein Abo schaut in die Zukunft, und „jedes neue
  // Radrennen in der Schweiz" muss man abonnieren können, BEVOR das erste
  // in events.json steht. Genau daran wäre der Wunsch des Nutzers sonst
  // gescheitert - damals gab es kein einziges Fahrrad-Event, „Fahrrad"
  // stand also gar nicht zur Wahl. Inzwischen stehen neun Radrennen in
  // den Daten; fürs Schwimmen und für die Schweiz gilt das Argument
  // unverändert.
  // In der Liste bleibt es bei den vorhandenen Werten: Ein Filter, der
  // garantiert null Treffer liefert, ist dort nur Ballast.
  const BEKANNTE_WERTE = {
    land: EF.LAENDER,
    art1: Object.keys(EF.DISTANCE_CATEGORIES)
  };

  const DISTANCE_CATEGORIES = EF.DISTANCE_CATEGORIES;
  const DISTANCE_CATEGORY_LABELS = EF.DISTANCE_CATEGORY_LABELS;
  const DATE_PRESETS = EF.DATE_PRESETS;
  const RADIUS_MIN_KM = EF.RADIUS_MIN_KM;
  const RADIUS_MAX_KM = EF.RADIUS_MAX_KM;
  const RADIUS_DEFAULT_KM = EF.RADIUS_DEFAULT_KM;

  const escapeHtml = EF.escapeHtml;

  // iPadOS meldet sich in Safari als "Macintosh"; der Touch-Zähler
  // verrät trotzdem, dass ein iPad davorsteht. Gebraucht für den
  // richtigen Einstellungs-Pfad in der Standort-Hilfe.
  function istIosGeraet() {
    const ua = navigator.userAgent || '';
    return /iPhone|iPad|iPod/.test(ua) || (/Mac/.test(ua) && navigator.maxTouchPoints > 1);
  }

  function create(opts) {
    const state = opts.state;
    const t = opts.t;
    const tv = opts.tv;
    const getEvents = opts.getEvents;
    const lang = opts.getLang || (() => 'de');
    const onChange = opts.onChange || (() => {});
    // Auch Werte anbieten, zu denen es noch kein Event gibt (siehe
    // BEKANNTE_WERTE). Der Abo-Dialog setzt das, die Liste nicht.
    const alleWerte = !!opts.alleWerte;

    // Ein einziges, an <body> gehängtes Panel (fixed positioniert), damit
    // es nie vom scrollenden Tabellen-Container abgeschnitten wird.
    let openColKey = null;
    let openTriggerEl = null;
    const floatingPanel = document.createElement('div');
    floatingPanel.className = 'filter-panel';
    floatingPanel.hidden = true;
    document.body.appendChild(floatingPanel);

    // Wohin das Panel gehört. Voreinstellung ist <body>; der Abo-Dialog
    // gibt seinen Overlay-Kasten an, und das aus zwei Gründen:
    //   - Der Dialog liegt bei z-index 2000, das Panel bei 1000 - an
    //     <body> gehängt verschwände es hinter dem Dialog.
    //   - Die Fokusfessel des Dialogs (auth.js `dialogTasten`) sucht ihre
    //     Ziele im Overlay; ein Panel daneben wäre per Tastatur nicht
    //     erreichbar.
    // Als Funktion übergeben, weil der Overlay-Kasten beim create() oft
    // noch nicht geholt ist; umgehängt wird erst beim Öffnen.
    const panelParent = typeof opts.panelParent === 'function'
      ? opts.panelParent
      : () => (opts.panelParent || document.body);

    // Knöpfe, die dieses Modul selbst gebaut hat (Karte). Die Liste baut
    // ihre Knöpfe in die Tabellenköpfe und meldet sie über attachButton().
    const buttons = [];

    // Welcher Sportart-Tab im Länge-Panel offen ist. Kein Filter, nur
    // Bedienzustand - deshalb hier und nicht in `state`.
    let activeDistanceSportTab = 'Laufen';

    // Beides steht in filters.js, damit die Tage im Datums-Baum genauso
    // aussehen wie in der Datums-Spalte der Liste.
    const uniqueSorted = values => EF.uniqueSorted(values, lang());
    const formatDate = iso => EF.formatDate(iso, lang());

    function applyPreset(preset) {
      EF.applyDatePreset(state, preset, uniqueSorted(getEvents().map(e => e.datum_start)));
    }

    // Welche Werte ein Mengen-Filter überhaupt anbieten kann. Auch die
    // Chips fragen das (für "Land: Alle" statt drei Einzel-Chips).
    function columnOptions(colKey) {
      if (colKey === 'art2') return availableArt2Options();
      const vorhanden = getEvents().map(e => e[colKey]);
      if (alleWerte && BEKANNTE_WERTE[colKey]) {
        return uniqueSorted(vorhanden.concat(BEKANNTE_WERTE[colKey]));
      }
      return uniqueSorted(vorhanden);
    }

    // Filtert diese Spalte gerade? Färbt ihren Knopf.
    function columnHasFilter(colKey) {
      if (colKey === 'land') return state.land.size > 0;
      if (colKey === 'name') return !!state.nameQuery.trim();
      if (colKey === 'art1') return state.art1.size > 0;
      if (colKey === 'art2') return state.art2.size > 0;
      if (colKey === 'standort') return state.standort.size > 0 || !!(state.origin && state.radiusKm != null);
      if (colKey === 'datum') return state.selectedDays.size > 0;
      if (colKey === 'laenge_km') return state.laengeMin !== '' || state.laengeMax !== '' || state.distanceCategories.size > 0;
      return false;
    }

    function availableArt2Options() {
      const roh = getEvents().map(e => e.art2);
      const presentArt2 = uniqueSorted(alleWerte ? roh.concat(ALLE_ART2) : roh);
      if (state.art1.size === 0) return presentArt2;
      const allowed = new Set();
      state.art1.forEach(a1 => (ART2_BY_ART1[a1] || []).forEach(a2 => allowed.add(a2)));
      return presentArt2.filter(a2 => allowed.has(a2));
    }

    function buildDateTreeNodes() {
      const byYear = {};
      getEvents().forEach(e => {
        const [y, m] = e.datum_start.split('-');
        byYear[y] = byYear[y] || {};
        byYear[y][m] = byYear[y][m] || new Set();
        byYear[y][m].add(e.datum_start);
      });
      return Object.keys(byYear).sort().map(year => {
        const months = byYear[year];
        const yearDays = Object.values(months).flatMap(s => Array.from(s));
        return {
          key: year,
          label: year,
          days: yearDays,
          children: Object.keys(months).sort().map(month => {
            const monthDays = Array.from(months[month]).sort();
            return {
              key: `${year}-${month}`,
              label: `${MONTH_NAMES[lang()][parseInt(month, 10) - 1]} ${year}`,
              days: monthDays,
              children: monthDays.map(day => ({
                key: day,
                label: formatDate(day),
                days: [day],
                children: null
              }))
            };
          })
        };
      });
    }

    function openPanel(col, triggerEl) {
      openColKey = col.key;
      openTriggerEl = triggerEl;
      const eltern = panelParent() || document.body;
      if (floatingPanel.parentNode !== eltern) eltern.appendChild(floatingPanel);
      floatingPanel.hidden = false;
      renderFilterPanel(col, floatingPanel);
      positionFloatingPanel(triggerEl);
      updateIndicators();
    }

    // closePanel(zurueckZumKnopf): Beim Schließen per Tastatur (Escape)
    // muss der Fokus zurück an den Knopf - sonst steht er an einem
    // Element, das es nicht mehr gibt, und die nächste Tab-Taste beginnt
    // wieder oben auf der Seite. Beim Klick außerhalb wird der Fokus
    // NICHT verschoben: dort hat der Klick schon sein eigenes Ziel.
    function closePanel(zurueckZumKnopf) {
      const knopf = openTriggerEl;
      const hatteFokus = floatingPanel.contains(document.activeElement);
      openColKey = null;
      openTriggerEl = null;
      floatingPanel.hidden = true;
      floatingPanel.innerHTML = '';
      updateIndicators();
      if (zurueckZumKnopf && hatteFokus && knopf && knopf.isConnected) {
        try { knopf.focus(); } catch (e) { /* ignorieren */ }
      }
    }

    // Tastaturbedienung des Panels. Escape schließt es (und gibt den
    // Fokus zurück), Tab aus dem Panel heraus schließt es ebenfalls -
    // ein Panel, das man verlassen hat, schwebt sonst weiter über der
    // Seite. Die Häkchen, Regler und Felder darin sind von sich aus mit
    // der Tastatur bedienbar, dafür braucht es nichts.
    floatingPanel.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' || ev.key === 'Esc') {
        ev.stopPropagation();
        closePanel(true);
      }
    });
    floatingPanel.addEventListener('focusout', (ev) => {
      // relatedTarget ist null, wenn das Panel sich gerade selbst neu
      // gezeichnet hat (das fokussierte Element ist dann weg) - das ist
      // KEIN Verlassen und darf nicht schließen.
      const ziel = ev.relatedTarget;
      if (!ziel) return;
      if (floatingPanel.contains(ziel)) return;
      if (openTriggerEl && (ziel === openTriggerEl || openTriggerEl.contains(ziel))) return;
      closePanel();
    });

    // Ist der Spaltenknopf noch zu sehen? Geprüft wird gegen das Fenster
    // UND gegen den scrollenden Tabellen-Container: Waagerecht aus der
    // Tabelle geschobene Spaltenköpfe liegen zwar noch im Fenster, sind
    // aber vom Container abgeschnitten.
    function isTriggerVisible(triggerEl) {
      // Ein aus dem Dokument gelöster Knopf (Tabellenkopf neu gebaut, siehe
      // attachButton) hat gar keine Position mehr.
      if (!triggerEl.isConnected) return false;
      const rect = triggerEl.getBoundingClientRect();
      const schneidet = (box) => rect.bottom > box.top && rect.top < box.bottom
        && rect.right > box.left && rect.left < box.right;
      if (!schneidet({ top: 0, bottom: window.innerHeight, left: 0, right: window.innerWidth })) return false;
      const wrap = triggerEl.closest('.table-wrap');
      return !wrap || schneidet(wrap.getBoundingClientRect());
    }

    function positionFloatingPanel(triggerEl) {
      // Hängt der Knopf nicht mehr im Dokument, liefert
      // getBoundingClientRect() lauter Nullen - das Panel spränge in die
      // linke obere Ecke (genau der vom Nutzer gemeldete Fehler). Dann
      // lieber stehen lassen, wo es ist; den neuen Knopf derselben Spalte
      // übernimmt attachButton().
      if (!triggerEl.isConnected) return;
      const rect = triggerEl.getBoundingClientRect();
      const panelWidth = floatingPanel.offsetWidth || 260;
      const panelHeight = floatingPanel.offsetHeight || 200;
      let left = rect.right - panelWidth;
      left = Math.max(8, Math.min(left, window.innerWidth - panelWidth - 8));
      let top = rect.bottom + 6;
      if (top + panelHeight > window.innerHeight - 8) {
        top = Math.max(8, rect.top - panelHeight - 6);
      }
      floatingPanel.style.left = left + 'px';
      floatingPanel.style.top = top + 'px';
    }

    function renderFilterPanel(col, panel) {
      if (col.type === 'checkbox') renderCheckboxPanel(col, panel);
      else if (col.type === 'standort') renderStandortPanel(panel);
      else if (col.type === 'date-tree') renderDateTreePanel(panel);
      else if (col.type === 'text') renderTextPanel(panel);
      else if (col.type === 'number-range') renderNumberRangePanel(panel);
    }

    function renderCheckboxPanel(col, panel) {
      const options = columnOptions(col.key);
      const selectedSet = state[col.key];
      Array.from(selectedSet).forEach(v => { if (!options.includes(v)) selectedSet.delete(v); });

      panel.innerHTML = '';
      const actions = document.createElement('div');
      actions.className = 'fp-actions';
      actions.innerHTML = `<a data-act="all">${escapeHtml(t('select_all'))}</a><a data-act="none">${escapeHtml(t('select_none'))}</a>`;
      panel.appendChild(actions);

      if (options.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'fp-empty';
        empty.textContent = t('no_values');
        panel.appendChild(empty);
      } else {
        const list = document.createElement('div');
        list.className = 'filter-list';
        options.forEach(opt => {
          const label = document.createElement('label');
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.value = opt;
          cb.checked = selectedSet.has(opt);
          cb.addEventListener('change', () => {
            if (cb.checked) selectedSet.add(opt); else selectedSet.delete(opt);
            if (col.key === 'art1') {
              const valid = new Set(availableArt2Options());
              Array.from(state.art2).forEach(v => { if (!valid.has(v)) state.art2.delete(v); });
              pruneDistanceCategoriesForArt1();
            }
            onChange();
          });
          label.appendChild(cb);
          label.appendChild(document.createTextNode(tv(col.key, opt)));
          list.appendChild(label);
        });
        panel.appendChild(list);
      }

      actions.querySelector('[data-act="all"]').addEventListener('click', () => {
        options.forEach(o => selectedSet.add(o));
        if (col.key === 'art1') {
          const valid = new Set(availableArt2Options());
          Array.from(state.art2).forEach(v => { if (!valid.has(v)) state.art2.delete(v); });
          pruneDistanceCategoriesForArt1();
        }
        onChange();
      });
      actions.querySelector('[data-act="none"]').addEventListener('click', () => {
        selectedSet.clear();
        if (col.key === 'art1') pruneDistanceCategoriesForArt1();
        onChange();
      });
    }

    // Entfernt Distanzkategorie-Auswahlen für Sportarten, die nach einer
    // Sportart-Filteränderung nicht mehr ausgewählt sind (sonst würde die
    // Länge-Auswahl "ins Leere laufen", weil kein Event mehr passt).
    function pruneDistanceCategoriesForArt1() {
      if (state.art1.size === 0) return;
      Array.from(state.distanceCategories).forEach(compositeKey => {
        const sport = compositeKey.slice(0, compositeKey.indexOf(':'));
        if (!state.art1.has(sport)) state.distanceCategories.delete(compositeKey);
      });
    }

    // ---------- Ortsverzeichnis für die Umkreissuche ----------

    // `places.json` enthält alle Orte und Postleitzahlen von Deutschland,
    // Österreich und der Schweiz (~35.000 Einträge, gebaut von
    // scripts/build_places.py aus GeoNames-Daten). Die Datei ist rund
    // 1,6 MB groß und wird deshalb erst geladen, wenn jemand den
    // Stadt/Ort-Filter öffnet - nicht schon beim Seitenaufruf.
    let placesIndex = null;
    let placesState = 'idle';   // 'idle' | 'loading' | 'ready' | 'error'
    let placesPromise = null;
    // Die letzte Eingabe im Suchfeld. Liegt außerhalb von `state`, weil sie
    // kein Filter ist - sie überlebt nur das Neuzeichnen des Panels.
    let placeQuery = '';

    // Suchschlüssel für Ortsnamen: klein, ohne Umlaute, ohne Sonderzeichen.
    // Muss zu `normalisiere()` in scripts/build_places.py passen, damit
    // "muenchen", "München" und "munchen" denselben Ort finden und
    // "Sankt Anton" den Ort erwischt, der in den Daten "St. Anton" heißt.
    function normalizePlaceText(text) {
      return (text || '')
        .toLowerCase()
        .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
        .normalize('NFD').replace(/[̀-ͯ]/g, '')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim()
        .replace(/\b(sankt|saint|ste)\b/g, 'st');
    }

    function loadPlaces() {
      if (placesPromise) return placesPromise;
      placesState = 'loading';
      placesPromise = fetch('places.json')
        .then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
        .then(data => {
          const laender = data.laender || [];
          const regionen = data.regionen || [];
          // Kompaktes Zeilenformat: [name, landIdx, regionIdx, lat, lon,
          // einwohner, "plz plz …"] - siehe Kopf von build_places.py.
          // Die Reihenfolge (größte Orte zuerst) bleibt erhalten und
          // dient in searchPlaces() als Rangfolge bei Gleichstand.
          placesIndex = (data.orte || []).map(row => ({
            name: row[0],
            land: laender[row[1]] || '',
            region: regionen[row[2]] || '',
            lat: row[3],
            lon: row[4],
            norm: normalizePlaceText(row[0]),
            plz: row[6] ? row[6].split(' ') : []
          }));
          placesState = 'ready';
        })
        .catch(() => { placesState = 'error'; });
      return placesPromise;
    }

    // Wie viele Treffer die Vorschlagsliste höchstens zeigt.
    const MAX_PLACE_RESULTS = 25;

    // Trefferliste zur Eingabe. Gesucht wird in Ortsnamen UND
    // Postleitzahlen; eine Eingabe aus Ziffern ist eine PLZ-Suche.
    function searchPlaces(query) {
      if (!placesIndex) return [];
      const raw = (query || '').trim();
      const digits = raw.replace(/[^0-9]/g, '');
      const norm = normalizePlaceText(raw);
      if (norm.length < 2 && digits.length < 2) return [];

      const treffer = [];
      for (const ort of placesIndex) {
        let rang = -1;
        if (digits.length >= 2 && ort.plz.some(plz => plz.startsWith(digits))) rang = 0;
        else if (norm.length >= 2) {
          if (ort.norm.startsWith(norm)) rang = 1;
          else if (ort.norm.includes(' ' + norm)) rang = 2;   // "Frankfurt" findet "Bad Frankfurt…"
          else if (ort.norm.includes(norm)) rang = 3;
        }
        if (rang >= 0) treffer.push({ ort, rang });
      }
      // Stabile Sortierung: innerhalb eines Rangs bleibt die Reihenfolge
      // aus der Datei - und die ist nach Einwohnerzahl absteigend. So
      // steht bei "mün" München vor Münchendorf.
      treffer.sort((a, b) => a.rang - b.rang);
      return treffer.slice(0, MAX_PLACE_RESULTS).map(x => x.ort);
    }

    // Setzt den Ausgangspunkt der Umkreissuche. Was darüber hinaus
    // geschieht, entscheidet die Seite (die Liste schaltet die
    // Entfernungs-Spalte und die Sortierung mit) - deshalb der Haken.
    function setOrigin(origin) {
      if (opts.setOrigin) opts.setOrigin(origin);
      else EF.setOriginPlain(state, origin);
    }

    // Der Stadt/Ort-Filter ist reine Umkreissuche: erst der Ausgangspunkt
    // (aktueller Standort oder eingetippter Ort/PLZ), dann der Regler.
    //
    // Die frühere Liste mit Häkchen für jeden Ort aus events.json ist
    // bewusst weg: das waren ~2000 Einträge, und wer in einem Ort ohne
    // Event wohnt, fand seinen eigenen dort nie. Ein Ortsfilter aus einem
    // Kartenlink (?standort=…) wirkt weiter und lässt sich über seinen
    // Chip entfernen.
    function renderStandortPanel(panel) {
      panel.innerHTML = '';

      const section = document.createElement('div');
      section.className = 'radius-section';
      const radiusTitle = document.createElement('div');
      radiusTitle.className = 'radius-title';
      radiusTitle.textContent = t('radius_title');
      section.appendChild(radiusTitle);

      // 1. Aktueller Standort
      const geoBtn = document.createElement('button');
      geoBtn.type = 'button';
      geoBtn.className = 'geo-btn';
      geoBtn.textContent = t('geo_btn');
      section.appendChild(geoBtn);

      const statusEl = document.createElement('div');
      statusEl.className = 'radius-status';
      statusEl.textContent = state.origin ? t('geo_origin_set', state.origin.label) : t('geo_no_origin');
      section.appendChild(statusEl);

      // Erscheint erst, wenn der Browser den Zugriff gespeichert verweigert:
      // dann hilft kein zweiter Klick, sondern nur die Einstellung.
      const geoHelp = document.createElement('div');
      geoHelp.className = 'geo-help';
      geoHelp.hidden = true;
      section.appendChild(geoHelp);

      if (state.origin) {
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'origin-clear';
        clearBtn.textContent = '✕ ' + t('origin_clear');
        clearBtn.addEventListener('click', () => {
          setOrigin(null);
          clearBtn.blur();   // sonst zeichnet refresh() nicht neu
          onChange();
        });
        section.appendChild(clearBtn);
      }

      // 2. Umkreis-Regler (1-200 km)
      const sliderRow = document.createElement('div');
      sliderRow.className = 'radius-slider-row' + (state.origin ? '' : ' disabled');
      const sliderValue = document.createElement('div');
      sliderValue.className = 'radius-value';
      const slider = document.createElement('input');
      slider.type = 'range';
      slider.min = String(RADIUS_MIN_KM);
      slider.max = String(RADIUS_MAX_KM);
      slider.step = '1';
      slider.value = String(state.radiusKm != null ? state.radiusKm : RADIUS_DEFAULT_KM);
      slider.disabled = !state.origin;
      slider.setAttribute('aria-label', t('radius_title'));
      sliderValue.textContent = state.origin ? t('radius_value', slider.value) : t('radius_disabled');
      sliderRow.appendChild(sliderValue);
      sliderRow.appendChild(slider);

      const scale = document.createElement('div');
      scale.className = 'radius-scale';
      scale.innerHTML = `<span>${RADIUS_MIN_KM} km</span><span>${RADIUS_MAX_KM} km</span>`;
      sliderRow.appendChild(scale);
      section.appendChild(sliderRow);

      // Beim Ziehen nur die Beschriftung mitlaufen lassen; neu gefiltert
      // wird erst beim Loslassen ('change'). Sonst würde die ganze
      // Tabelle bei jedem Pixel Fingerbewegung neu aufgebaut.
      slider.addEventListener('input', () => {
        sliderValue.textContent = t('radius_value', slider.value);
      });
      slider.addEventListener('change', () => {
        state.radiusKm = Number(slider.value);
        // Kein blur() hier: der Regler soll für die Pfeiltasten den Fokus
        // behalten. Dass refresh() deswegen nicht neu zeichnet,
        // ist richtig - Beschriftung und Reglerstellung stimmen bereits.
        onChange();
      });

      // 3. Ortssuche über places.json
      const searchWrap = document.createElement('div');
      searchWrap.className = 'place-search';
      const searchLabel = document.createElement('div');
      searchLabel.className = 'radius-title';
      searchLabel.textContent = t('place_search_label');
      searchWrap.appendChild(searchLabel);

      const searchInput = document.createElement('input');
      searchInput.type = 'text';
      searchInput.autocomplete = 'off';
      searchInput.placeholder = t('place_search_placeholder');
      searchInput.value = placeQuery;
      searchWrap.appendChild(searchInput);

      const results = document.createElement('div');
      results.className = 'place-results';
      searchWrap.appendChild(results);

      // Meldezeile für "wird geladen", "nichts gefunden" und Ladefehler.
      // Ohne Eingabe bleibt sie leer: Das Feld erklärt sich über seinen
      // Platzhalter, und die Quellenangabe zu den Ortsdaten steht in der
      // Fußzeile der Startseite, nicht hier im Weg.
      const note = document.createElement('div');
      note.className = 'place-note';
      searchWrap.appendChild(note);
      section.appendChild(searchWrap);

      function renderResults() {
        results.innerHTML = '';
        if (placesState === 'loading') { note.textContent = t('places_loading'); return; }
        if (placesState === 'error') { note.textContent = t('places_error'); return; }
        const query = searchInput.value.trim();
        if (!query) { note.textContent = ''; return; }
        const treffer = searchPlaces(query);
        if (treffer.length === 0) { note.textContent = t('places_empty'); return; }
        note.textContent = '';
        treffer.forEach(ort => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'place-result';
          const meta = [ort.region, tv('land', LAND_BY_CODE[ort.land] || ort.land)]
            .filter(Boolean).join(' · ');
          btn.innerHTML = `${escapeHtml(ort.name)}<span class="place-meta">${escapeHtml(meta)} · ${escapeHtml(ort.plz.slice(0, 3).join(', '))}${ort.plz.length > 3 ? ' …' : ''}</span>`;
          btn.addEventListener('click', () => {
            setOrigin({ lat: ort.lat, lon: ort.lon, label: ort.name });
            placeQuery = searchInput.value;
            // Fokus abgeben, sonst zeichnet refresh() das Panel
            // nicht neu und der Regler bliebe ausgegraut.
            btn.blur();
            onChange();
          });
          results.appendChild(btn);
        });
      }

      searchInput.addEventListener('input', () => {
        placeQuery = searchInput.value;
        renderResults();
      });

      renderResults();
      if (placesState === 'idle' || placesState === 'loading') {
        loadPlaces().then(renderResults);
      }

      function zeigeGeoHilfe() {
        const schritte = t(istIosGeraet() ? 'geo_help_ios' : 'geo_help_other');
        geoHelp.innerHTML = '<ol>' + schritte.map(zeile => `<li>${escapeHtml(zeile)}</li>`).join('') +
          `</ol><span class="geo-help-fallback">${escapeHtml(t('geo_help_fallback'))}</span>`;
        geoHelp.hidden = false;
      }

      geoBtn.addEventListener('click', () => {
        if (!navigator.geolocation) {
          statusEl.textContent = t('geo_unsupported');
          return;
        }
        // Ohne sicheren Kontext (http:// außer localhost) lehnen die Browser
        // die Abfrage mit einem nichtssagenden "User denied Geolocation" ab -
        // besser vorher sagen, woran es liegt.
        if (window.isSecureContext === false) {
          statusEl.textContent = t('geo_insecure');
          return;
        }
        geoHelp.hidden = true;
        statusEl.textContent = t('geo_locating');
        geoBtn.disabled = true;
        const gestartet = Date.now();
        navigator.geolocation.getCurrentPosition(
          pos => {
            setOrigin({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: t('geo_current_label') });
            // WICHTIG: erst den Fokus vom Button nehmen. refresh()
            // zeichnet das offene Filter-Panel NICHT neu, solange der Fokus
            // darin liegt (damit eine Eingabe im Namensfeld nicht abreißt) -
            // und der geklickte Button liegt genau dort. Ohne das blieb der
            // Standort zwar gespeichert, das Panel zeigte aber weiter
            // "Standort wird ermittelt…" und der Umkreis-Regler blieb
            // ausgegraut: die Funktion sah aus wie kaputt.
            geoBtn.blur();
            onChange();
          },
          err => {
            geoBtn.disabled = false;
            if (err.code === 1) {
              // Fehlercode 1 hat zwei sehr verschiedene Ursachen, und der
              // Unterschied entscheidet, was der Nutzer tun muss:
              // Kommt die Absage praktisch sofort, hat der Browser gar nicht
              // gefragt - die Entscheidung steht schon fest (einmal abgelehnt
              // und gemerkt) oder die Ortungsdienste sind systemweit aus.
              // Dann hilft nur die Einstellung, ein zweiter Klick nicht.
              // Hat der Nutzer dagegen eben selbst "Nicht erlauben" getippt,
              // vergehen Sekunden - und beim nächsten Klick fragt der Browser
              // wieder.
              const sofort = Date.now() - gestartet < 800;
              statusEl.textContent = sofort ? t('geo_denied_blocked') : t('geo_denied');
              geoBtn.textContent = t('geo_retry');
              if (sofort) zeigeGeoHilfe();
            }
            else if (err.code === 3) statusEl.textContent = t('geo_timeout');
            else statusEl.textContent = t('geo_unavailable', err.message || String(err.code));
          },
          // maximumAge: eine Position aus den letzten fünf Minuten darf der
          // Browser direkt zurückgeben - das spart beim zweiten Öffnen des
          // Panels die volle Ortung.
          { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
        );
      });

      // Zusatz, kein Ersatz: Safari unterstützt navigator.permissions für
      // "geolocation" nicht überall (und wirft dort beim Namen eine
      // Ausnahme). Wo es geht, sagen wir schon beim Öffnen des Panels, dass
      // der Zugriff gespeichert abgelehnt ist - sonst tippt der Nutzer auf
      // einen Knopf, der nie etwas tun kann.
      if (!state.origin && navigator.permissions && navigator.permissions.query) {
        try {
          navigator.permissions.query({ name: 'geolocation' })
            .then(res => {
              if (res.state === 'denied' && !state.origin && geoHelp.hidden) {
                statusEl.textContent = t('geo_denied_blocked');
                geoBtn.textContent = t('geo_retry');
                zeigeGeoHilfe();
              }
            })
            .catch(() => {});
        } catch (e) {
          /* Browser ohne Unterstützung: dann eben erst nach dem Klick. */
        }
      }

      panel.appendChild(section);
    }

    function renderDateTreePanel(panel) {
      panel.innerHTML = '';
      const actions = document.createElement('div');
      actions.className = 'fp-actions';
      actions.innerHTML = `<a data-act="all">${escapeHtml(t('select_all'))}</a><a data-act="none">${escapeHtml(t('select_none'))}</a>`;
      panel.appendChild(actions);

      const presetWrap = document.createElement('div');
      presetWrap.className = 'date-presets';
      DATE_PRESETS.forEach(preset => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'date-preset' + (state.datePreset === preset.key ? ' active' : '');
        btn.textContent = t(preset.labelKey);
        btn.addEventListener('click', () => {
          if (state.datePreset === preset.key) {
            state.selectedDays.clear();
            state.datePreset = null;
          } else {
            applyPreset(preset);
          }
          onChange();
          renderDateTreePanel(panel);
          if (openTriggerEl) positionFloatingPanel(openTriggerEl);
        });
        presetWrap.appendChild(btn);
      });
      panel.appendChild(presetWrap);

      const nodes = buildDateTreeNodes();
      const allDays = uniqueSorted(getEvents().map(e => e.datum_start));

      if (nodes.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'fp-empty';
        empty.textContent = t('no_dates');
        panel.appendChild(empty);
      } else {
        const treeWrap = document.createElement('div');
        treeWrap.className = 'date-tree';
        nodes.forEach(n => treeWrap.appendChild(buildTreeNode(n)));
        panel.appendChild(treeWrap);
      }

      actions.querySelector('[data-act="all"]').addEventListener('click', () => {
        allDays.forEach(d => state.selectedDays.add(d));
        state.datePreset = null;
        onChange();
      });
      actions.querySelector('[data-act="none"]').addEventListener('click', () => {
        state.selectedDays.clear();
        state.datePreset = null;
        onChange();
      });
    }

    function buildTreeCheckboxLabel(node) {
      const label = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      const allSelected = node.days.every(d => state.selectedDays.has(d));
      const noneSelected = node.days.every(d => !state.selectedDays.has(d));
      cb.checked = allSelected;
      cb.indeterminate = !allSelected && !noneSelected;
      cb.addEventListener('change', () => {
        if (cb.checked) node.days.forEach(d => state.selectedDays.add(d));
        else node.days.forEach(d => state.selectedDays.delete(d));
        // Von Hand angefasst: das Zeitraum-Etikett stimmt dann nicht mehr.
        state.datePreset = null;
        onChange();
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(node.label));
      return label;
    }

    function buildTreeNode(node) {
      const wrap = document.createElement('div');
      wrap.className = 'tree-node';
      const row = document.createElement('div');
      row.className = 'tree-row';
      const hasChildren = Array.isArray(node.children) && node.children.length > 0;

      if (hasChildren) {
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'tree-toggle';
        const expanded = state.treeExpanded.has(node.key);
        toggleBtn.textContent = expanded ? '▾' : '▸';
        row.appendChild(toggleBtn);
        row.appendChild(buildTreeCheckboxLabel(node));
        wrap.appendChild(row);

        const childrenWrap = document.createElement('div');
        childrenWrap.className = 'tree-children';
        childrenWrap.hidden = !expanded;
        node.children.forEach(child => childrenWrap.appendChild(buildTreeNode(child)));
        wrap.appendChild(childrenWrap);

        toggleBtn.addEventListener('click', () => {
          if (state.treeExpanded.has(node.key)) state.treeExpanded.delete(node.key);
          else state.treeExpanded.add(node.key);
          const nowExpanded = state.treeExpanded.has(node.key);
          childrenWrap.hidden = !nowExpanded;
          toggleBtn.textContent = nowExpanded ? '▾' : '▸';
          if (openTriggerEl) positionFloatingPanel(openTriggerEl);
        });
      } else {
        const spacer = document.createElement('span');
        spacer.className = 'tree-spacer';
        row.appendChild(spacer);
        row.appendChild(buildTreeCheckboxLabel(node));
        wrap.appendChild(row);
      }

      return wrap;
    }

    function renderTextPanel(panel) {
      panel.innerHTML = '';
      const input = document.createElement('input');
      input.type = 'text';
      input.placeholder = t('name_search_placeholder');
      input.value = state.nameQuery;
      input.addEventListener('input', () => {
        state.nameQuery = input.value;
        onChange();
      });
      panel.appendChild(input);
    }

    function renderNumberRangePanel(panel) {
      panel.innerHTML = '';

      // Sportart-Tabs für die Distanzkategorien: nur Sportarten anzeigen, die
      // auch im Sportart-Filter ausgewählt sind (ist dort nichts gewählt,
      // stehen alle zur Wahl). Ist nur eine Sportart relevant, brauchen wir
      // keine Tabs - dann direkt deren Kategorien zeigen.
      const allSports = Object.keys(DISTANCE_CATEGORIES);
      const visibleSports = state.art1.size > 0
        ? allSports.filter(s => state.art1.has(s))
        : allSports;
      if (visibleSports.length === 0) visibleSports.push(...allSports);
      if (!visibleSports.includes(activeDistanceSportTab)) {
        activeDistanceSportTab = visibleSports[0];
      }

      if (visibleSports.length > 1) {
        const tabsWrap = document.createElement('div');
        tabsWrap.className = 'distance-tabs';
        visibleSports.forEach(sport => {
          const tabBtn = document.createElement('button');
          tabBtn.type = 'button';
          tabBtn.className = 'distance-tab' + (activeDistanceSportTab === sport ? ' active' : '');
          tabBtn.textContent = tv('art1', sport);
          tabBtn.addEventListener('click', () => {
            activeDistanceSportTab = sport;
            renderNumberRangePanel(panel);
            if (openTriggerEl) positionFloatingPanel(openTriggerEl);
          });
          tabsWrap.appendChild(tabBtn);
        });
        panel.appendChild(tabsWrap);
      }

      const catList = document.createElement('div');
      catList.className = 'filter-list distance-categories';
      // Die Zeitrennen-Kategorie nur anbieten, wenn diese Sportart überhaupt
      // ein zeitlich begrenztes Event hat - eine Auswahl, die garantiert 0
      // Treffer liefert, ist nur Ballast im Panel.
      const hatZeitrennen = getEvents().some(
        e => e.art1 === activeDistanceSportTab && e.dauer_h != null);
      (DISTANCE_CATEGORIES[activeDistanceSportTab] || [])
        .filter(cat => !cat.zeit || hatZeitrennen)
        .forEach(cat => {
        const compositeKey = `${activeDistanceSportTab}:${cat.key}`;
        const label = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = state.distanceCategories.has(compositeKey);
        cb.addEventListener('change', () => {
          if (cb.checked) state.distanceCategories.add(compositeKey);
          else state.distanceCategories.delete(compositeKey);
          onChange();
        });
        label.appendChild(cb);
        label.appendChild(document.createTextNode(DISTANCE_CATEGORY_LABELS[lang()][cat.key]));
        catList.appendChild(label);
      });
      panel.appendChild(catList);

      const wrap = document.createElement('div');
      wrap.className = 'range-row';
      const minLabel = document.createElement('label');
      minLabel.textContent = t('range_von_km');
      const minInput = document.createElement('input');
      minInput.type = 'number';
      minInput.min = '0';
      minInput.step = '0.1';
      minLabel.appendChild(minInput);
      const maxLabel = document.createElement('label');
      maxLabel.textContent = t('range_bis_km');
      const maxInput = document.createElement('input');
      maxInput.type = 'number';
      maxInput.min = '0';
      maxInput.step = '0.1';
      maxLabel.appendChild(maxInput);
      wrap.appendChild(minLabel);
      wrap.appendChild(maxLabel);
      panel.appendChild(wrap);

      minInput.value = state.laengeMin;
      maxInput.value = state.laengeMax;
      minInput.addEventListener('input', () => { state.laengeMin = minInput.value; onChange(); });
      maxInput.addEventListener('input', () => { state.laengeMax = maxInput.value; onChange(); });
    }

    // Das offene Panel neu an seinem Knopf ausrichten, ohne seinen Inhalt
    // anzufassen. Nötig, weil die Liste ihre Spaltenbreiten erst beim
    // Zeichnen der Tabelle festlegt: Ein Ausgangspunkt schaltet die
    // Entfernungs-Spalte zu, danach steht der Stadt/Ort-Knopf woanders als
    // beim buildHeader() kurz davor. Die Liste ruft das am Ende von
    // render() auf. Anders als beim Scrollen wird hier NICHT geschlossen -
    // ein Neuzeichnen soll kein offenes Panel wegnehmen.
    function reposition() {
      if (openColKey === null || !openTriggerEl) return;
      if (isTriggerVisible(openTriggerEl)) positionFloatingPanel(openTriggerEl);
    }

    function refresh() {
      if (openColKey === null) return;
      if (floatingPanel.contains(document.activeElement)) return;
      const col = COLUMNS.find(c => c.key === openColKey);
      if (col) {
        renderFilterPanel(col, floatingPanel);
        if (openTriggerEl) positionFloatingPanel(openTriggerEl);
      }
    }

    // Färbt jeden Filterknopf der Seite: blau, wenn seine Spalte filtert,
    // und als "offen" markiert, solange sein Panel aufliegt. Gilt für die
    // Knöpfe im Tabellenkopf (Liste) genauso wie für die Knopfreihe (Karte)
    // - beide tragen die Klasse .col-filter-btn und ihr data-col.
    // Färbt die Filterknöpfe DIESER Bedieneinheit: blau, wenn ihre Spalte
    // filtert, und als "offen" markiert, solange ihr Panel aufliegt.
    //
    // Bewusst über `buttons` und NICHT über
    // `document.querySelectorAll('.col-filter-btn')`: Auf einer Seite
    // kann es mehrere Bedieneinheiten mit eigenem Zustand geben (die
    // Liste hat ihre Spaltenköpfe, der Abo-Dialog in events.html seine
    // eigene Knopfreihe mit einem zweiten Filterzustand). Eine globale
    // Abfrage hätte die Knöpfe der einen Einheit nach dem Zustand der
    // anderen gefärbt - je nachdem, welche zuletzt gezeichnet hat.
    //
    // Abgehängte Knöpfe fallen dabei heraus: `buildHeader()` in der
    // Liste baut die Spaltenköpfe bei jedem Ausgangspunkt neu, die alten
    // bleiben sonst für immer in der Sammlung.
    function updateIndicators() {
      for (let i = buttons.length - 1; i >= 0; i--) {
        if (!buttons[i].isConnected) buttons.splice(i, 1);
      }
      buttons.forEach(btn => {
        const col = btn.dataset.col;
        btn.classList.toggle('has-filter', columnHasFilter(col));
        btn.classList.toggle('open', openColKey === col);
        // Für Tastatur und Screenreader: der Knopf öffnet ein Panel, und
        // ob es offen ist, steht nicht nur in der Farbe.
        btn.setAttribute('aria-haspopup', 'dialog');
        btn.setAttribute('aria-expanded', openColKey === col ? 'true' : 'false');
      });
    }

    // Einen fremd gebauten Knopf (Liste: im Tabellenkopf) an das Panel
    // hängen.
    function attachButton(btn, col) {
      btn.dataset.col = col.key;
      // Der Tabellenkopf wird neu gebaut, WÄHREND ein Panel offen ist: Ein
      // Ausgangspunkt im Stadt/Ort-Filter schaltet die Entfernungs-Spalte
      // zu, also ruft setOrigin() buildHeader() - und ersetzt dabei jeden
      // Spaltenknopf durch einen neuen. Der alte Knopf, an dem das Panel
      // hing, war danach aus dem Dokument gelöst; sein
      // getBoundingClientRect() lieferte Nullen und das Panel klebte in
      // der linken oberen Ecke, weit weg von seiner Spalte (vom Nutzer
      // gemeldet). Der neue Knopf derselben Spalte übernimmt deshalb die
      // Ankerrolle.
      //
      // Positioniert wird hier noch nicht: Der Knopf hängt in diesem
      // Moment meist noch nicht im Dokument (der Aufrufer fügt ihn erst
      // danach ein), hätte also selbst keine Position. Das erledigt der
      // refresh() des folgenden render() bzw. das nächste Scrollen.
      if (openColKey === col.key) openTriggerEl = btn;
      // In die eigene Sammlung, damit updateIndicators() nur die Knöpfe
      // DIESER Bedieneinheit färbt (siehe dort).
      if (buttons.indexOf(btn) < 0) buttons.push(btn);
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (openColKey === col.key) closePanel();
        else openPanel(col, btn);
      });
      // Escape, während der Fokus noch am Knopf steht (das Panel öffnet
      // sich ohne den Fokus mitzunehmen - eine Maus-Bedienung soll nicht
      // plötzlich im Panel landen).
      btn.addEventListener('keydown', (ev) => {
        if ((ev.key === 'Escape' || ev.key === 'Esc') && openColKey === col.key) {
          ev.stopPropagation();
          closePanel(true);
        }
        // Pfeil nach unten öffnet das Panel und geht hinein - dasselbe
        // Muster wie bei einer Auswahlliste.
        if (ev.key === 'ArrowDown') {
          ev.preventDefault();
          if (openColKey !== col.key) openPanel(col, btn);
          const erstes = floatingPanel.querySelector(
            'input:not([disabled]), button:not([disabled]), select, a[href]');
          if (erstes) erstes.focus();
        }
      });
    }

    // Knopfreihe mit Beschriftung (Karte): "Land ▾". Dieselben Panels wie
    // in der Liste, nur ohne Tabelle drumherum.
    // `opts.ohne`: Spalten, die hier keinen Knopf bekommen. Der
    // Abo-Dialog lässt damit „Datum" weg - ein Abo schaut in die
    // Zukunft, ein Datumsfilter wäre dort sinnlos.
    function buildButtonBar(container, opts) {
      const ohne = (opts && opts.ohne) || [];
      container.innerHTML = '';
      buttons.length = 0;
      COLUMNS.filter(col => ohne.indexOf(col.key) < 0).forEach(col => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'col-filter-btn';
        btn.innerHTML = `<span>${escapeHtml(t(col.labelKey))}</span><span aria-hidden="true">▾</span>`;
        attachButton(btn, col);       // meldet den Knopf auch an `buttons`
        container.appendChild(btn);
      });
      updateIndicators();
    }

    // Klick außerhalb schließt das Panel; Scrollen und Verkleinern lassen
    // es seinem Knopf folgen.
    document.addEventListener('click', (ev) => {
      if (openColKey === null) return;
      // composedPath() statt ev.target/.contains(): ein Klick auf ein Element,
      // das sein eigener Handler synchron neu rendert (z. B. Sportart-Tabs),
      // hängt das Zielelement aus - .contains() würde das fälschlich als
      // "Klick außerhalb" werten und das Panel sofort wieder schließen.
      const path = ev.composedPath ? ev.composedPath() : [ev.target];
      if (!path.includes(floatingPanel)) {
        closePanel();
      }
    });
    // Das Panel ist `fixed` positioniert und hängt optisch an seinem
    // Spaltenknopf. Scrollt die Seite oder die Tabelle, wandert es
    // deshalb mit - statt sich, wie früher, einfach zu schließen.
    //
    // Das Schließen ging auf schmalen Bildschirmen schief: Dort ist
    // die Tabelle breiter als das Fenster, die Spalten ab "Stadt/Ort"
    // erreicht man nur durch waagerechtes Scrollen. Ein Scroll-Ereignis,
    // das kurz vor dem Tippen ausgelöst wurde (iOS scrollt nach dem
    // Wischen noch nach), wird erst NACH dem Klick zugestellt: Das
    // Panel ging auf und sofort wieder zu. Auf 390 px Breite ließ sich
    // der Stadt/Ort-Filter so gar nicht öffnen.
    //
    // Dasselbe beim Verkleinern: Auf Android schiebt die
    // Bildschirmtastatur das Fenster zusammen und löst `resize` aus -
    // ein Tippen ins Namens- oder Ortssuchfeld hätte das Panel
    // geschlossen, bevor der erste Buchstabe drin war.
    let folgeFrame = null;
    const folgeDemKnopf = () => {
      if (openColKey === null || !openTriggerEl || folgeFrame !== null) return;
      // requestAnimationFrame: Während eines Schwungs feuern
      // Scroll-Ereignisse dicht an dicht, neu positioniert werden muss
      // aber höchstens einmal pro Bild.
      folgeFrame = requestAnimationFrame(() => {
        folgeFrame = null;
        if (openColKey === null || !openTriggerEl) return;
        if (isTriggerVisible(openTriggerEl)) positionFloatingPanel(openTriggerEl);
        else closePanel();   // ohne sichtbaren Anker schwebt es nur herum
      });
    };
    window.addEventListener('scroll', folgeDemKnopf, true);
    window.addEventListener('resize', folgeDemKnopf);
    return {
      COLUMNS,
      attachButton,
      buildButtonBar,
      open: openPanel,
      close: closePanel,
      refresh,
      reposition,
      updateIndicators,
      columnHasFilter,
      options: columnOptions,
      availableArt2Options,
      pruneDistanceCategoriesForArt1,
      openKey: () => openColKey,
      panelHasFocus: () => floatingPanel.contains(document.activeElement),
      // Die Eingabe im Ortssuchfeld ist kein Filter, überlebt aber das
      // Neuzeichnen des Panels - beim Zurücksetzen muss sie mit weg.
      resetTransient: () => { placeQuery = ''; }
    };
  }

  global.EnduranceFilterUI = { I18N, COLUMNS, create };
})(typeof window !== 'undefined' ? window : globalThis);
