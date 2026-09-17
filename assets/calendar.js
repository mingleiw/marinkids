/* Calendar page: month grids with event expansion.
   Loaded only on /<city>/calendar/index.html. */

(function () {
  if (typeof TOWN === 'undefined' || typeof CAL_EVENTS === 'undefined') return;

  var DAYS  = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  var MONTHS = ['January','February','March','April','May','June',
                'July','August','September','October','November','December'];

  var calEl = document.getElementById('calMonths');
  var detailEl = document.getElementById('calDetail');
  if (!calEl || !detailEl) return;

  var sm = window._sacmoms || {};

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
  function ymd(d) {
    return d.getFullYear() + '-' +
      ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function evDist(e) {
    var loc = sm.userLoc ? sm.userLoc() : null;
    if (loc && e.lat && e.lon) return sm.haversine(loc.lat, loc.lon, e.lat, e.lon);
    if (e.dist !== undefined) return e.dist;
    return null;
  }

  var today = new Date(); today.setHours(0, 0, 0, 0);
  var todayStr = ymd(today);

  /* Compute the range of months to show: from today's month through the last
     dated event's month. Weekly events repeat on every matching day. */
  var lastDate = todayStr;
  for (var i = 0; i < CAL_EVENTS.length; i++) {
    if (CAL_EVENTS[i].date && CAL_EVENTS[i].date > lastDate) lastDate = CAL_EVENTS[i].date;
  }
  var startMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  var endParts = lastDate.split('-');
  var endMonth = new Date(+endParts[0], +endParts[1] - 1, 1);

  /* Build index: which dates have events. */
  var datedIndex = {};  /* 'YYYY-MM-DD' -> [event, ...] */
  var weeklyByDay = {};  /* 0-6 -> [event, ...] */
  for (var k = 0; k < CAL_EVENTS.length; k++) {
    var e = CAL_EVENTS[k];
    if (e.date) {
      if (!datedIndex[e.date]) datedIndex[e.date] = [];
      datedIndex[e.date].push(e);
    } else if (e.day !== undefined) {
      if (!weeklyByDay[e.day]) weeklyByDay[e.day] = [];
      weeklyByDay[e.day].push(e);
    }
  }

  function eventsForDate(dateStr) {
    var d = new Date(dateStr + 'T00:00:00');
    var dow = d.getDay();
    var list = (datedIndex[dateStr] || []).concat(weeklyByDay[dow] || []);
    list.sort(function (a, b) {
      var ta = a.time || '99:99', tb = b.time || '99:99';
      return ta < tb ? -1 : (ta > tb ? 1 : 0);
    });
    return list;
  }

  function countForDate(dateStr) {
    var d = new Date(dateStr + 'T00:00:00');
    var dow = d.getDay();
    return (datedIndex[dateStr] || []).length + (weeklyByDay[dow] || []).length;
  }

  var selectedDate = null;

  function renderMonths() {
    calEl.innerHTML = '';
    var m = new Date(startMonth);
    while (m <= endMonth) {
      var monthDiv = document.createElement('div');
      monthDiv.className = 'cal-month';
      monthDiv.setAttribute('data-month', m.getFullYear() + '-' + ('0' + (m.getMonth() + 1)).slice(-2));

      var header = document.createElement('h3');
      header.className = 'cal-month-title';
      header.textContent = MONTHS[m.getMonth()] + ' ' + m.getFullYear();
      monthDiv.appendChild(header);

      var grid = document.createElement('div');
      grid.className = 'cal-grid';

      /* Day-of-week headers */
      for (var h = 0; h < 7; h++) {
        var hd = document.createElement('div');
        hd.className = 'cal-head';
        hd.textContent = SHORT[h].charAt(0);
        grid.appendChild(hd);
      }

      /* Leading blanks */
      var first = new Date(m.getFullYear(), m.getMonth(), 1);
      var startDow = first.getDay();
      for (var b = 0; b < startDow; b++) {
        var blank = document.createElement('div');
        blank.className = 'cal-cell cal-blank';
        grid.appendChild(blank);
      }

      /* Days */
      var daysInMonth = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
      for (var day = 1; day <= daysInMonth; day++) {
        var dateStr = m.getFullYear() + '-' + ('0' + (m.getMonth() + 1)).slice(-2) + '-' + ('0' + day).slice(-2);
        var cell = document.createElement('button');
        cell.type = 'button';
        var isPast = dateStr < todayStr;
        var isToday = dateStr === todayStr;
        var count = countForDate(dateStr);
        var isSelected = dateStr === selectedDate;

        cell.className = 'cal-cell cal-day' +
          (isPast ? ' cal-past' : '') +
          (isToday ? ' cal-today' : '') +
          (isSelected ? ' cal-selected' : '') +
          (count > 0 ? ' cal-has-events' : '');
        cell.setAttribute('data-date', dateStr);
        cell.setAttribute('aria-label', day + ' ' + MONTHS[m.getMonth()] +
          (count ? ', ' + count + (count === 1 ? ' event' : ' events') : ', no events'));

        var num = document.createElement('span');
        num.className = 'cal-num';
        num.textContent = day;
        cell.appendChild(num);

        if (count > 0 && !isPast) {
          var dot = document.createElement('span');
          dot.className = 'cal-dot';
          dot.setAttribute('aria-hidden', 'true');
          cell.appendChild(dot);
        }

        if (!isPast || isToday) {
          cell.addEventListener('click', (function (ds) {
            return function () { selectDate(ds); };
          })(dateStr));
        } else {
          cell.disabled = true;
        }

        grid.appendChild(cell);
      }

      monthDiv.appendChild(grid);

      /* Event detail panel inserted after each month grid */
      var panel = document.createElement('div');
      panel.className = 'cal-events-panel';
      panel.setAttribute('data-panel-month', m.getFullYear() + '-' + ('0' + (m.getMonth() + 1)).slice(-2));
      panel.hidden = true;
      monthDiv.appendChild(panel);

      calEl.appendChild(monthDiv);
      m.setMonth(m.getMonth() + 1);
    }
  }

  function selectDate(dateStr) {
    if (selectedDate === dateStr) {
      selectedDate = null;
      clearSelection();
      return;
    }
    selectedDate = dateStr;

    /* Update cell highlights */
    calEl.querySelectorAll('.cal-day').forEach(function (c) {
      c.classList.toggle('cal-selected', c.getAttribute('data-date') === dateStr);
    });

    /* Hide all panels, show the right one */
    calEl.querySelectorAll('.cal-events-panel').forEach(function (p) { p.hidden = true; });
    var monthKey = dateStr.substring(0, 7);
    var panel = calEl.querySelector('[data-panel-month="' + monthKey + '"]');
    if (!panel) return;

    var events = eventsForDate(dateStr);
    var d = new Date(dateStr + 'T00:00:00');
    var label = DAYS[d.getDay()] + ', ' + MONTHS[d.getMonth()] + ' ' + d.getDate();

    if (events.length === 0) {
      panel.innerHTML = '<p class="cal-no-events">Nothing listed on ' + esc(label) + '.</p>';
    } else {
      var html = '<h4 class="cal-events-title">' + esc(label) +
        ' <span class="cal-events-count">' + events.length +
        (events.length === 1 ? ' event' : ' events') + '</span></h4>';
      html += '<div class="cal-events-list">';
      html += events.map(function (e) {
        var when = e.time ? hhmm(e.time) + (e.until ? ' – ' + hhmm(e.until) : '') : '';
        var dist = evDist(e);
        var distChip = dist !== null
          ? '<span class="ev-tag ev-dist">' + esc(showMiles(dist)) + ' mi</span>'
          : '';
        var seasonalTag = e.seasonal
          ? '<span class="ev-tag cal-seasonal-tag">Seasonal</span>'
          : '';
        return '<article class="event">' +
          '<div class="ev-time' + (when ? '' : ' ev-time-unknown') + '">' +
            (when ? esc(when) : 'Time TBC') + '</div>' +
          '<div class="ev-body">' +
            '<h3>' + esc(e.title) + '</h3>' +
            '<p class="ev-where">' + esc(e.venue) + ', ' + esc(e.city) + '</p>' +
            '<p class="ev-blurb">' + esc(e.blurb) + '</p>' +
            '<div class="ev-foot">' +
              seasonalTag +
              distChip +
              '<span class="ev-tag">' + esc(e.ages) + '</span>' +
              '<a class="map" href="https://www.google.com/maps/search/?api=1&query=' +
                encodeURIComponent(e.venue + ' ' + e.city) + '" target="_blank" rel="noopener">Directions</a>' +
              (e.source ? '<a class="ev-src" href="' + esc(e.source) + '" target="_blank" rel="noopener">Official listing</a>' : '') +
            '</div>' +
          '</div></article>';
      }).join('');
      html += '</div>';
      panel.innerHTML = html;
    }
    panel.hidden = false;

    /* Scroll the panel into view if it's below the fold */
    try { panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
    catch (err) { panel.scrollIntoView(); }
  }

  function clearSelection() {
    calEl.querySelectorAll('.cal-day').forEach(function (c) {
      c.classList.remove('cal-selected');
    });
    calEl.querySelectorAll('.cal-events-panel').forEach(function (p) { p.hidden = true; });
  }

  renderMonths();

  /* Auto-select today if it has events */
  if (countForDate(todayStr) > 0) {
    selectDate(todayStr);
  }
})();
