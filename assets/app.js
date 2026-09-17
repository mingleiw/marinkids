/* Shared by every city page.

   Distances are baked into each card's data-dist at build time (from the
   town centre), so the page works with JavaScript off. When the user shares
   their location, distances recompute from their actual position and
   everything re-sorts. */

(function () {
  if (typeof TOWN === 'undefined') return;

  var cards   = [].slice.call(document.querySelectorAll('#cards .card'));
  var countEl = document.getElementById('count');
  var emptyEl = document.getElementById('empty');
  var resetEl = document.getElementById('reset');
  var cardsEl = document.getElementById('cards');

  var state = { age: 'all', env: 'all' };
  var userLoc = null;

  try {
    var seg = location.pathname.replace(/\/+$/, '').split('/').pop();
    if (seg) localStorage.setItem('owtk.city', seg);
  } catch (e) {}

  try {
    var saved = localStorage.getItem('owtk.loc');
    if (saved) userLoc = JSON.parse(saved);
  } catch (e) {}

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function haversine(lat1, lon1, lat2, lon2) {
    var R = 3958.8, r = Math.PI / 180;
    var dla = (lat2 - lat1) * r, dlo = (lon2 - lon1) * r;
    var a = Math.sin(dla / 2) * Math.sin(dla / 2) +
            Math.cos(lat1 * r) * Math.cos(lat2 * r) *
            Math.sin(dlo / 2) * Math.sin(dlo / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function showMiles(d) {
    return d < 10 ? String(Math.round(d * 10) / 10) : String(Math.round(d));
  }

  function cardDist(card) {
    if (userLoc) {
      var lat = +card.getAttribute('data-lat');
      var lon = +card.getAttribute('data-lon');
      if (lat && lon) return haversine(userLoc.lat, userLoc.lon, lat, lon);
    }
    return +card.getAttribute('data-dist');
  }

  function sortCards() {
    cards.sort(function (a, b) { return cardDist(a) - cardDist(b); });
    cards.forEach(function (c) {
      var mi = showMiles(cardDist(c));
      var el = c.querySelector('.m-dist');
      if (el) el.textContent = mi + ' mi';
      cardsEl.appendChild(c);
    });
  }

  var ZIPS = {
    // Marin County
    '94901':[37.973,-122.531],'94903':[38.019,-122.545],'94904':[37.953,-122.536],
    '94912':[37.973,-122.531],'94913':[37.973,-122.531],'94914':[37.860,-122.529],
    '94915':[37.973,-122.531],'94920':[37.874,-122.457],'94924':[37.919,-122.731],
    '94925':[37.926,-122.528],'94929':[37.867,-122.576],'94930':[37.900,-122.596],
    '94933':[38.015,-122.697],'94937':[38.045,-122.765],'94938':[38.004,-122.669],
    '94939':[37.913,-122.553],'94940':[38.071,-122.634],'94941':[37.906,-122.545],
    '94942':[37.906,-122.545],'94945':[38.107,-122.570],'94946':[38.013,-122.640],
    '94947':[38.127,-122.535],'94948':[38.107,-122.570],'94949':[38.068,-122.514],
    '94950':[38.049,-122.770],'94956':[38.071,-122.724],'94957':[37.960,-122.554],
    '94960':[37.984,-122.588],'94963':[38.009,-122.645],'94964':[37.936,-122.477],
    '94965':[37.859,-122.485],'94966':[37.859,-122.485],'94970':[37.896,-122.626],
    '94971':[38.076,-122.790],'94973':[38.014,-122.669],'94974':[38.004,-122.669],
    '94976':[37.926,-122.528],'94977':[37.913,-122.553],'94978':[37.900,-122.596],
    '94979':[38.013,-122.640],
    // Sonoma County (nearby)
    '94928':[38.246,-122.701],'94931':[38.265,-122.573],'94951':[38.232,-122.637],
    '94952':[38.233,-122.636],'94953':[38.232,-122.637],'94954':[38.262,-122.607],
    '94955':[38.232,-122.637],'94972':[38.354,-122.909],'94975':[38.232,-122.637],
    '94999':[38.232,-122.637],
    '95401':[38.441,-122.714],'95402':[38.441,-122.714],'95403':[38.479,-122.729],
    '95404':[38.434,-122.668],'95405':[38.431,-122.684],'95406':[38.441,-122.714],
    '95407':[38.399,-122.737],'95409':[38.461,-122.651],
    // SF & nearby (visitors coming from the city)
    '94102':[37.781,-122.417],'94103':[37.773,-122.415],'94104':[37.791,-122.402],
    '94105':[37.789,-122.396],'94107':[37.766,-122.399],'94108':[37.793,-122.408],
    '94109':[37.794,-122.422],'94110':[37.749,-122.416],'94111':[37.798,-122.400],
    '94112':[37.720,-122.443],'94114':[37.759,-122.435],'94115':[37.786,-122.437],
    '94116':[37.744,-122.486],'94117':[37.770,-122.444],'94118':[37.782,-122.462],
    '94121':[37.778,-122.494],'94122':[37.759,-122.484],'94123':[37.800,-122.437],
    '94124':[37.734,-122.390],'94127':[37.735,-122.459],'94129':[37.800,-122.464],
    '94130':[37.824,-122.370],'94131':[37.742,-122.438],'94132':[37.724,-122.478],
    '94133':[37.800,-122.411],'94134':[37.719,-122.413],'94158':[37.770,-122.388]
  };

  function buildLocPrompt() {
    var locBar = document.getElementById('locBar');
    if (!locBar) return;

    if (userLoc) {
      var label = userLoc.zip
        ? '\u{1F4CD} Using zip code ' + esc(userLoc.zip)
        : '\u{1F4CD} Using your location';
      locBar.innerHTML = '<span class="loc-status">' + label + '</span>' +
        '<button class="loc-clear-btn">Reset</button>';
      locBar.querySelector('.loc-clear-btn').addEventListener('click', function () {
        userLoc = null;
        try { localStorage.removeItem('owtk.loc'); } catch (e) {}
        sortCards();
        apply();
        buildLocPrompt();
        if (typeof reRenderEvents === 'function') reRenderEvents();
      });
    } else {
      var html = '';
      if ('geolocation' in navigator) {
        html += '<button class="loc-btn">' +
          '\u{1F4CD} Use my location</button>' +
          '<span class="loc-or">or</span>';
      }
      html += '<form class="zip-form">' +
        '<input class="zip-input" type="text" inputmode="numeric" pattern="[0-9]{5}"' +
        ' maxlength="5" placeholder="Enter zip code" aria-label="Zip code">' +
        '<button class="loc-btn zip-go" type="submit">Go</button>' +
        '</form>';
      locBar.innerHTML = html;

      var geoBtn = locBar.querySelector('.loc-btn:not(.zip-go)');
      if (geoBtn) geoBtn.addEventListener('click', requestLocation);

      locBar.querySelector('.zip-form').addEventListener('submit', function (ev) {
        ev.preventDefault();
        var inp = locBar.querySelector('.zip-input');
        var code = (inp.value || '').replace(/\D/g, '');
        if (code.length !== 5) { inp.focus(); return; }
        var coords = ZIPS[code];
        if (!coords) {
          inp.value = '';
          inp.placeholder = 'Zip not found';
          inp.classList.add('zip-err');
          inp.focus();
          return;
        }
        applyLocation({ lat: coords[0], lon: coords[1], zip: code });
      });
    }
  }

  function applyLocation(loc) {
    userLoc = loc;
    try { localStorage.setItem('owtk.loc', JSON.stringify(userLoc)); } catch (e) {}
    sortCards();
    apply();
    buildLocPrompt();
    if (typeof reRenderEvents === 'function') reRenderEvents();
  }

  function requestLocation() {
    var locBar = document.getElementById('locBar');
    var btn = locBar ? locBar.querySelector('.loc-btn:not(.zip-go)') : null;
    if (btn) { btn.textContent = 'Locating…'; btn.disabled = true; }

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        applyLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
      },
      function () {
        if (btn) { btn.textContent = 'Location unavailable'; btn.disabled = true; }
      },
      { enableHighAccuracy: false, timeout: 8000 }
    );
  }

  // Expose for the events IIFE to call
  window._mkids = { userLoc: function () { return userLoc; }, haversine: haversine, showMiles: showMiles, esc: esc };

  function matches(card) {
    for (var k in state) {
      if (state[k] === 'all') continue;
      if ((card.getAttribute('data-' + k) || '').split(/\s+/).indexOf(state[k]) === -1) return false;
    }
    return true;
  }

  function apply() {
    var n = 0;
    cards.forEach(function (c) { var ok = matches(c); c.hidden = !ok; if (ok) n++; });
    var filtered = state.age !== 'all' || state.env !== 'all';
    countEl.textContent = filtered ? n + (n === 1 ? ' place' : ' places') + ' match'
                                   : 'Showing all ' + n + ' places';
    emptyEl.hidden = n !== 0;
    resetEl.hidden = !filtered;
    document.querySelectorAll('[data-group]').forEach(function (g) {
      var key = g.getAttribute('data-group');
      g.querySelectorAll('.chip').forEach(function (b) {
        b.classList.toggle('is-on', b.getAttribute('data-v') === state[key]);
      });
    });
  }

  document.querySelectorAll('[data-group]').forEach(function (g) {
    var key = g.getAttribute('data-group');
    g.addEventListener('click', function (e) {
      var btn = e.target.closest('.chip');
      if (!btn || !g.contains(btn)) return;
      state[key] = btn.getAttribute('data-v');
      apply();
    });
  });

  resetEl.addEventListener('click', function () {
    state = { age: 'all', env: 'all' };
    apply();
  });

  if (userLoc) sortCards();
  buildLocPrompt();
  apply();
})();

/* ---- This week ---- */
(function () {
  var stripEl = document.getElementById('daystrip');
  var evEl    = document.getElementById('events');
  var weekMt  = document.getElementById('weekEmpty');
  if (!stripEl || !evEl || typeof EVENTS === 'undefined') return;

  var DAYS  = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  function ymd(d) {
    return d.getFullYear() + '-' +
      ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }

  var today = new Date(); today.setHours(0, 0, 0, 0);
  var week = [];
  for (var i = 0; i < 7; i++) {
    var d = new Date(today); d.setDate(today.getDate() + i); week.push(d);
  }
  function countFor(d) {
    var n = 0, y = ymd(d);
    for (var k = 0; k < EVENTS.length; k++)
      if (EVENTS[k].day === d.getDay() || EVENTS[k].date === y) n++;
    return n;
  }

  var picked = 0;
  for (var w = 0; w < week.length; w++) {
    if (countFor(week[w])) { picked = w; break; }
  }

  var sm = window._mkids || {};
  function esc(s) {
    if (sm.esc) return sm.esc(s);
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function showMiles(d) {
    return d < 10 ? String(Math.round(d * 10) / 10) : String(Math.round(d));
  }

  function hhmm(t) {
    var p = t.split(':'), h = +p[0], m = p[1], ap = h >= 12 ? 'pm' : 'am';
    h = h % 12; if (h === 0) h = 12;
    return m === '00' ? h + ' ' + ap : h + ':' + m + ' ' + ap;
  }

  function evDist(e) {
    var loc = sm.userLoc ? sm.userLoc() : null;
    if (loc && e.lat && e.lon) return sm.haversine(loc.lat, loc.lon, e.lat, e.lon);
    if (e.dist !== undefined) return e.dist;
    return null;
  }

  function evDistLabel(e) {
    var loc = sm.userLoc ? sm.userLoc() : null;
    if (loc && e.lat && e.lon) return '';  // from user, no "from X" suffix
    return ' from ' + TOWN.name;
  }

  function strip() {
    stripEl.innerHTML = '';
    week.forEach(function (d, i) {
      var b = document.createElement('button');
      b.className = 'day' + (i === picked ? ' is-on' : '');
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-selected', i === picked ? 'true' : 'false');
      b.setAttribute('aria-controls', 'events');
      var label = i === 0 ? 'Today' : (i === 1 ? 'Tomorrow' : SHORT[d.getDay()]);
      var n = countFor(d);
      b.innerHTML = '<span class="day-name">' + label + '</span>' +
                    '<span class="day-num">' + d.getDate() + '</span>' +
                    (n ? '<span class="day-dot" aria-hidden="true"></span>' : '');
      b.setAttribute('aria-label', label + ' ' + d.getDate() + ', ' +
                     (n ? n + (n === 1 ? ' event' : ' events') : 'nothing listed'));
      b.addEventListener('click', function () { picked = i; strip(); render(); });
      stripEl.appendChild(b);
    });
  }

  var shown = [];

  function render() {
    var d = week[picked];
    var list = EVENTS.filter(function (e) { return e.day === d.getDay() || e.date === ymd(d); })
                     .sort(function (a, b) {
                       var ta = a.time || '99:99', tb = b.time || '99:99';
                       return ta < tb ? -1 : (ta > tb ? 1 : 0);
                     });
    shown = list;

    evEl.innerHTML = list.map(function (e, i) {
      var when = e.time ? hhmm(e.time) + (e.until ? ' – ' + hhmm(e.until) : '') : '';
      var dist = evDist(e);
      var distChip = dist !== null
        ? '<span class="ev-tag ev-dist">' + esc(showMiles(dist)) + ' mi</span>'
        : '';
      return '<article class="event" data-i="' + i + '">' +
        '<div class="ev-time' + (when ? '' : ' ev-time-unknown') + '">' +
          (when ? esc(when) : esc(e.timeLabel || 'Time not confirmed')) + '</div>' +
        '<div class="ev-body">' +
          '<h3>' + esc(e.title) + '</h3>' +
          '<p class="ev-where">' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
          '<p class="ev-blurb">' + esc(e.blurb) + '</p>' +
          '<div class="ev-foot">' +
            distChip +
            '<span class="ev-tag">' + esc(e.ages) + '</span>' +
            '<button class="ev-more" type="button">Details</button>' +
            '<a class="map" href="https://www.google.com/maps/search/?api=1&query=' +
              encodeURIComponent(e.venue + ' ' + e.city) + '" target="_blank" rel="noopener">Map</a>' +
            (e.source ? '<a class="ev-src" href="' + esc(e.source) + '" target="_blank" rel="noopener">Where this came from</a>' : '') +
          '</div>' +
        '</div></article>';
    }).join('');

    var when = picked === 0 ? 'today' : (picked === 1 ? 'tomorrow' : 'on ' + DAYS[d.getDay()]);
    weekMt.hidden = list.length !== 0;

    var nxt = -1;
    for (var j = 1; j < week.length; j++) {
      var idx = (picked + j) % week.length;
      if (countFor(week[idx])) { nxt = idx; break; }
    }
    weekMt.textContent = 'Nothing listed ' + when + '.' +
      (nxt > -1 ? ' Next up: ' + (nxt === 0 ? 'today' : nxt === 1 ? 'tomorrow' : DAYS[week[nxt].getDay()]) + '.' : '');
  }

  // Expose so the places IIFE can trigger a re-render after geolocation
  window.reRenderEvents = function () { render(); };

  /* ---- Details ---- */
  var dlg    = document.getElementById('evDialog');
  var detail = document.getElementById('evDetail');

  function keyFor(e) {
    return (e.date || 'w' + e.day) + '-' +
      String(e.title + '-' + e.venue).toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
  }

  function longDate(e) {
    var d = e.date ? new Date(e.date + 'T00:00:00') : week[picked];
    return DAYS[d.getDay()] + ' ' + d.getDate() + ' ' +
      ['January','February','March','April','May','June','July',
       'August','September','October','November','December'][d.getMonth()];
  }

  function openDetail(e, push) {
    if (!dlg || !detail) return;
    var when = e.time ? hhmm(e.time) + (e.until ? ' – ' + hhmm(e.until) : '')
                      : (e.timeLabel || 'Time not confirmed');
    var dist = evDist(e);
    var label = evDistLabel(e);
    detail.innerHTML =
      '<h3 id="evDialogTitle">' + esc(e.title) + '</h3>' +
      '<p class="d-when">' + esc(longDate(e)) + ' · ' + esc(when) + '</p>' +
      '<p class="d-where">' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
      (e.blurb ? '<p class="d-blurb">' + esc(e.blurb) + '</p>' : '') +
      '<div class="d-tags">' +
        (dist === null ? '' :
          '<span class="ev-tag ev-dist">' + esc(showMiles(dist)) + ' mi' + esc(label) + '</span>') +
        '<span class="ev-tag">' + esc(e.ages) + '</span></div>' +
      '<div class="d-acts">' +
        '<a class="map" href="https://www.google.com/maps/search/?api=1&query=' +
          encodeURIComponent(e.venue + ' ' + e.city) +
          '" target="_blank" rel="noopener">Map</a>' +
        (e.source ? '<a class="ev-src" href="' + esc(e.source) +
          '" target="_blank" rel="noopener">Where this came from</a>' : '') +
      '</div>';
    if (push) {
      try { history.pushState(null, '', '#event=' + keyFor(e)); } catch (err) {}
    }
    if (dlg.showModal) { if (!dlg.open) dlg.showModal(); }
    else { dlg.setAttribute('open', ''); }
  }

  if (dlg) {
    dlg.addEventListener('close', function () {
      if (location.hash.indexOf('#event=') === 0) {
        try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
      }
    });
    dlg.addEventListener('click', function (ev) {
      if (ev.target === dlg) dlg.close();
    });
  }

  evEl.addEventListener('click', function (ev) {
    if (ev.target.closest('a')) return;
    var art = ev.target.closest('.event');
    if (!art) return;
    var e = shown[+art.getAttribute('data-i')];
    if (e) openDetail(e, true);
  });

  function fromHash() {
    var m = /^#event=(.+)$/.exec(location.hash);
    if (!m) return;
    for (var i = 0; i < EVENTS.length; i++) {
      if (keyFor(EVENTS[i]) === m[1]) {
        if (EVENTS[i].date) {
          for (var j = 0; j < week.length; j++) {
            if (ymd(week[j]) === EVENTS[i].date) { picked = j; break; }
          }
        }
        strip(); render();
        openDetail(EVENTS[i], false);
        return;
      }
    }
  }

  window.addEventListener('hashchange', function () {
    if (location.hash.indexOf('#event=') === 0) fromHash();
    else if (dlg && dlg.open) dlg.close();
  });

  strip();
  render();
  fromHash();
})();
