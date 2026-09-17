#!/usr/bin/env python3
"""
Generate the site: one page per city, plus a root city picker.

    python3 build.py

Reads data/*.json and templates/*, writes index.html and <city-slug>/index.html.
Everything it writes is committed, so GitHub Pages still serves plain static
files with no build running anywhere.

Why a build step at all: a city page needs its places sorted by distance from
that city. Doing it here rather than in the browser means each page ships
genuinely different, crawlable content and still works with JavaScript off.
"""

import json, math, os, re, shutil, html, datetime, hashlib

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_NAME = 'MarinKids'

FOCUS_REGION = 'marin'
FOCUS_LABEL = 'Marin County'


def _asset_v(rel):
    with open(os.path.join(ROOT, rel), 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


# Cache-buster for CSS/JS: the hash changes only when the file's contents do,
# so daily data-only rebuilds keep using the cached assets while a code change
# always fetches fresh. Without this, browsers sit on the old app.js after a
# deploy and dated events silently stop rendering.
APP_JS_V = _asset_v('assets/app.js')
CAL_JS_V = _asset_v('assets/calendar.js')
STYLE_V = _asset_v('assets/style.css')

# Change this if the repo is renamed or a custom domain is pointed at the site:
# it drives every canonical URL and the sitemap, and a wrong value silently tells
# search engines the pages live somewhere they don't.
BASE_URL = 'https://mingleiw.github.io/marinkids/'

# A city needs at least this many places within MAX_MILES to get its own page.
# Below that the page would be mostly other cities' content — thin, duplicated,
# and worth less than no page at all.
MIN_PLACES = 4
MAX_MILES = 25

# A city page lists only places within this radius. Without a cap every page
# carries all 30 places in a different order, which is 38 near-duplicate pages
# padded with destinations nobody would drive to from there.
LIST_MILES = 30


def load(name):
    with open(os.path.join(ROOT, 'data', name), encoding='utf-8') as f:
        return json.load(f)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def miles(a, b, c, d):
    R, r = 3958.8, math.pi / 180
    dla, dlo = (c - a) * r, (d - b) * r
    s = math.sin(dla / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin(dlo / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def show_miles(d):
    return ('%.1f' % d) if d < 10 else str(int(round(d)))


REGIONS = {'sf': 'San Francisco', 'marin': 'Marin & North Bay', 'east': 'East Bay',
           'peninsula': 'Peninsula', 'south': 'South Bay', 'sac': 'Sacramento area'}

SEASONAL_CONFIG = {
    'halloween': {
        'icon': 'i-pumpkin',
        'title': 'Halloween',
        'sub': 'Pumpkin patches, haunted trails &amp; more near %s',
    },
}

GROUPS = [('sf', 'San Francisco'), ('marin', 'Marin & North Bay'), ('east', 'East Bay'),
          ('peninsula', 'Peninsula'), ('south', 'South Bay'), ('sac', 'Sacramento area')]

def load_venues():
    """{venue|city: (lat, lon)} for events, or {} when not geocoded yet.

    Written by scripts/geocode_venues.py. Entries it could not resolve carry a
    null lat and are skipped here, so an unresolved venue shows no distance
    rather than a made-up one. Absent file = the site behaves as it did before
    distances existed.
    """
    try:
        rows = load('venues.json')
    except FileNotFoundError:
        return {}
    return {'%s|%s' % (r['venue'], r['city']): (r['lat'], r['lon'])
            for r in rows if r.get('lat') is not None and r.get('lon') is not None}


VENUES = load_venues()

PHOTO_DIR = os.path.join(ROOT, 'assets', 'photos')

def photo_for(slug):
    p = os.path.join(PHOTO_DIR, '%s.webp' % slug)
    return 'assets/photos/%s.webp' % slug if os.path.exists(p) else None

SPRITE = read('templates/sprite.svg')
TIPS = read('templates/tips.html')

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="google-site-verification" content="dm2Pu9RXpaVxuBA3NeG7Tp5krl5A987svIRWzIHpHtE" />
<title>{title}</title>
<meta name="description" content="{desc}" />
<link rel="canonical" href="{canonical}" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{desc}" />
<meta property="og:url" content="{canonical}" />
{og_image}
<link rel="icon" href="{up}assets/favicon.svg" type="image/svg+xml" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="{up}assets/style.css?v=__STYLE_V__" />
<script>document.documentElement.className += ' js';</script>
</head>
<body>

<a class="skip" href="#list">Skip to places</a>
<div class="grain" aria-hidden="true"></div>

''' + SPRITE + '''

<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{up}">
      <span class="brand-mark" aria-hidden="true"><svg width="19" height="19"><use href="#i-park"/></svg></span>
      <span class="brand-text">
        <strong>''' + SITE_NAME + '''</strong>
        <small>Where to take the kids</small>
      </span>
    </a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
'''

# Bake the CSS content hash into the template once: every page served after a
# style.css change points at a new URL, so no browser keeps the old stylesheet.
HEAD = HEAD.replace('__STYLE_V__', STYLE_V)

FOOT = '''
<footer class="site-footer">
  <div class="wrap footer-inner">
    <p class="footer-brand">''' + SITE_NAME + '''</p>
    <p class="footer-note">Find somewhere to take the kids today.</p>
    <p class="footer-disclaimer">
      Places listed are long-running and established.
      <strong>Hours, admission and seasonal closures change without notice &mdash; always
      confirm through the map link before you set out.</strong>
    </p>
  </div>
</footer>
</body>
</html>
'''


def place_card(p, dist=None, up='../'):
    meta = ''
    if dist is not None:
        meta += '<li class="m-dist">%s mi</li>' % show_miles(dist)
    if not FOCUS_REGION:
        meta += '<li class="m-region">%s</li>' % REGIONS.get(p['region'], p['region'])
    meta += '<li class="m-age">%s</li><li class="m-env">%s</li>' % (p['ages'], p['envlabel'])
    photo = photo_for(slugify(p['name']))
    img_html = ''
    if photo:
        img_html = '<img class="card-img" src="%s%s" alt="" width="400" height="225" loading="lazy">' % (up, photo)
    return '''
        <article class="card{imgcls}" data-cat="{cat}" data-age="{age}" data-region="{region}" data-env="{env}"{dattr} data-lat="{lat}" data-lon="{lon}">
          {img}
          <div class="card-top">
            <span class="ico" aria-hidden="true"><svg width="20" height="20"><use href="#{icon}"/></svg></span>
            <div><h3>{name}</h3><p class="en">{where}</p></div>
          </div>
          <p class="desc">{desc}</p>
          <ul class="meta">{meta}</ul>
          <p class="note"><b>Before you go</b> {note}</p>
          <a class="map" href="https://www.google.com/maps/search/?api=1&query={mapq}" target="_blank" rel="noopener">{cta}</a>
        </article>
'''.format(dattr=('' if dist is None else ' data-dist="%.1f"' % dist),
           meta=meta, img=img_html, imgcls=' has-img' if photo else '', **p)


FILTERS = '''
      <div class="filters" role="group" aria-label="Filters">
        <div class="filter-row">
          <span class="filter-label">Age</span>
          <div class="chips" data-group="age">
            <button class="chip is-on" data-v="all">Any age</button>
            <button class="chip" data-v="0-2">Under 3</button>
            <button class="chip" data-v="3-5">3&ndash;5</button>
            <button class="chip" data-v="6-9">6&ndash;9</button>
            <button class="chip" data-v="10+">10 and up</button>
          </div>
        </div>
        <div class="filter-row">
          <span class="filter-label">Weather</span>
          <div class="chips" data-group="env">
            <button class="chip is-on" data-v="all">Either</button>
            <button class="chip" data-v="indoor">Mostly indoors</button>
            <button class="chip" data-v="outdoor">Mostly outdoors</button>
          </div>
        </div>
        <div class="filter-foot">
          <p class="filter-count" id="count" aria-live="polite"></p>
          <button class="reset" id="reset" hidden>Clear all</button>
        </div>
      </div>
'''


EVENT_AGE_TAGS = {
    'Ages 0–5': '0-2 3-5',
    'Babies 0–18 mo': '0-2',
    'All ages': '0-2 3-5 6-9 10+',
    'Under 6': '0-2 3-5',
    'Under 8': '0-2 3-5 6-9',
    '24 months & under': '0-2',
    'Ages 5+': '3-5 6-9 10+',
}


def event_env(e):
    t = (e.get('title') or '').lower()
    v = (e.get('venue') or '').lower()
    if 'outdoor' in t:
        return 'outdoor'
    if 'library' in v or 'museum' in v or 'book' in v:
        return 'indoor'
    if 'market' in t or 'market' in v or 'plaza' in v or 'old town' in v:
        return 'outdoor'
    return ''


def events_jsonld(ev, town, week_dates):
    """schema.org Event markup for what the page actually lists this week.

    The stated long-term plan is ads, so event rich results are worth having.
    Two rules keep this honest, because structured data that disagrees with the
    page is an SEO liability rather than a win:

    - Only events already rendered on this page are described, over the same
      7-day window, so the markup can never advertise more than the page shows.
    - Nothing is invented to satisfy the schema. An event whose hour is not
      sourced gets a date-only startDate rather than a guessed clock time, and
      no offset is emitted at all: Sacramento switches between PDT and PST, and
      a hardcoded offset would be silently wrong for half the year. Local time
      without an offset is valid ISO 8601 and reads as local to the venue.
    """
    items = []
    for e in ev:
        # Weekly events recur, so resolve them to the concrete dates they land
        # on inside the window; dated events already carry one.
        if 'date' in e:
            dates = [e['date']] if e['date'] in week_dates else []
        elif 'day' in e:
            dates = [d for d in sorted(week_dates)
                     if datetime.date.fromisoformat(d).weekday() == (e['day'] - 1) % 7]
        else:
            continue
        for d in dates:
            item = {
                '@type': 'Event',
                'name': e['title'],
                'startDate': '%sT%s' % (d, e['time']) if e.get('time') else d,
                'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
                'eventStatus': 'https://schema.org/EventScheduled',
                'location': {
                    '@type': 'Place',
                    'name': e['venue'],
                    'address': {
                        '@type': 'PostalAddress',
                        'addressLocality': e.get('city', town['name']),
                        'addressRegion': 'CA',
                        'addressCountry': 'US',
                    },
                },
            }
            if e.get('time') and e.get('until'):
                item['endDate'] = '%sT%s' % (d, e['until'])
            if e.get('blurb'):
                item['description'] = e['blurb']
            if e.get('source'):
                item['url'] = e['source']
            items.append(item)
    if not items:
        return ''
    items.sort(key=lambda i: i['startDate'])
    for i in items:
        i['@context'] = 'https://schema.org'
    # </script> inside a JSON string would close the tag early.
    blob = json.dumps(items, ensure_ascii=False, indent=1).replace('</', '<\\/')
    return '<script type="application/ld+json">\n%s\n</script>\n' % blob


def places_jsonld(places):
    """Schema.org TouristAttraction markup for the place cards on a city page."""
    items = []
    for p in places:
        items.append({
            '@type': 'TouristAttraction',
            'name': p['name'],
            'description': html.unescape(p['desc']),
            'url': 'https://www.google.com/maps/search/?api=1&query=%s' % p['mapq'],
            'geo': {
                '@type': 'GeoCoordinates',
                'latitude': p['lat'],
                'longitude': p['lon'],
            },
            'address': {
                '@type': 'PostalAddress',
                'addressLocality': p['where'],
                'addressRegion': 'CA',
                'addressCountry': 'US',
            },
        })
    if not items:
        return ''
    for i in items:
        i['@context'] = 'https://schema.org'
    # </script> inside a JSON string would close the tag early.
    blob = json.dumps(items, ensure_ascii=False, indent=1).replace('</', '<\\/')
    return '<script type="application/ld+json">\n%s\n</script>\n' % blob


def _month_day(d):
    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    return '%s %d' % (months[d.month - 1], d.day)


def format_date_range(dates):
    ds = sorted(datetime.date.fromisoformat(d) for d in dates)
    if len(ds) == 1:
        return _month_day(ds[0])
    all_weekend = all(d.weekday() in (5, 6) for d in ds)
    first, last = ds[0], ds[-1]
    if all_weekend and len(ds) > 2:
        return 'Weekends %s &ndash; %s' % (_month_day(first), _month_day(last))
    if first.month == last.month:
        return '%s &ndash; %s' % (_month_day(first), last.day)
    return '%s &ndash; %s' % (_month_day(first), _month_day(last))


def group_seasonal(events, town):
    from collections import OrderedDict
    groups = OrderedDict()
    for e in events:
        key = e.get('group', e['title'])
        groups.setdefault(key, []).append(e)
    result = []
    for gkey, entries in groups.items():
        entries.sort(key=lambda e: e['date'])
        first = entries[0]
        dates = [e['date'] for e in entries]
        g = {
            'group_key': gkey,
            'title': first['title'],
            'venue': first.get('venue', ''),
            'city': first.get('city', ''),
            'ages': first.get('ages', 'All ages'),
            'blurb': first.get('blurb', ''),
            'source': first.get('source', ''),
            'time': first.get('time', ''),
            'until': first.get('until', ''),
            'seasonal': first['seasonal'],
            'dates': dates,
            'date_label': format_date_range(dates),
        }
        lat = first.get('lat')
        lon = first.get('lon')
        vc = VENUES.get('%s|%s' % (g['venue'], g['city']))
        if vc:
            lat, lon = vc
        if lat is not None and lon is not None:
            g['dist'] = round(miles(town['lat'], town['lon'], lat, lon), 1)
        result.append(g)
    result.sort(key=lambda g: (g.get('dist') is None, g.get('dist', 0)))
    result = [g for g in result if g.get('dist') is not None and g['dist'] <= LIST_MILES]
    return result


def seasonal_section_html(groups, town_name):
    by_season = {}
    for g in groups:
        by_season.setdefault(g['seasonal'], []).append(g)
    out = ''
    for season, items in by_season.items():
        cfg = SEASONAL_CONFIG.get(season, {
            'icon': 'i-park', 'title': season.title(),
            'sub': 'Special events near %s',
        })
        out += '''
  <section class="seasonal seasonal-%s" id="seasonal">
    <div class="wrap">
      <div class="section-head seasonal-head">
        <h2><svg class="seasonal-icon" width="28" height="28"><use href="#%s"/></svg> %s</h2>
        <p class="section-sub">%s</p>
      </div>
      <div class="seasonal-grid">
''' % (html.escape(season), cfg['icon'], html.escape(cfg['title']),
       cfg['sub'] % html.escape(town_name))
        for g in items:
            when = g['date_label']
            if g['time']:
                t = g['time'].split(':')
                h, m = int(t[0]), t[1]
                ap = 'pm' if h >= 12 else 'am'
                h = h % 12 or 12
                start = '%d %s' % (h, ap) if m == '00' else '%d:%s %s' % (h, m, ap)
                if g.get('until'):
                    u = g['until'].split(':')
                    uh, um = int(u[0]), u[1]
                    uap = 'pm' if uh >= 12 else 'am'
                    uh = uh % 12 or 12
                    end = '%d %s' % (uh, uap) if um == '00' else '%d:%s %s' % (uh, um, uap)
                    when += ' &middot; %s &ndash; %s' % (start, end)
                else:
                    when += ' &middot; %s' % start
            dist_chip = ''
            if 'dist' in g:
                dist_chip = '<span class="ev-tag ev-dist">%s mi</span>' % show_miles(g['dist'])
            group_key = g.get('group_key', slugify(g['title']))
            sc_photo = photo_for(group_key)
            sc_img = ''
            if sc_photo:
                sc_img = '<img class="sc-img" src="../%s" alt="" width="400" height="225" loading="lazy">' % sc_photo
            out += '''        <article class="seasonal-card%s">
          %s
          <h3>%s</h3>
          <p class="sc-when">%s</p>
          <p class="sc-where">%s, %s</p>
          <p class="sc-blurb">%s</p>
          <div class="sc-foot">
            %s
            <span class="ev-tag">%s</span>
            <a class="map" href="https://www.google.com/maps/search/?api=1&amp;query=%s" target="_blank" rel="noopener">Map</a>
            %s
          </div>
        </article>
''' % (' has-img' if sc_photo else '',
       sc_img,
       html.escape(g['title']), when,
       html.escape(g['venue']), html.escape(g['city']),
       html.escape(g['blurb']),
       dist_chip, html.escape(g['ages']),
       html.escape(g['venue'] + ' ' + g['city']),
       '<a class="ev-src" href="%s" target="_blank" rel="noopener">Details</a>' % html.escape(g['source']) if g.get('source') else '')
        out += '''      </div>
    </div>
  </section>
'''
    return out


def check_app_contract(page_html, slug):
    """Fail the build if app.js reaches for an element the page does not emit.

    app.js is only loaded on city pages, so every getElementById() in it must
    resolve here. This exists because the two drifted once: a stale build.py was
    committed over a newer one, which dropped the <dialog> markup while leaving
    assets/ untouched. The Details button still rendered, app.js still looked up
    #evDialog, the null guard returned early, and clicking a card silently did
    nothing on the live site. Nothing failed -- it just quietly stopped working.
    """
    needed = set(re.findall(r"getElementById\('([A-Za-z0-9_-]+)'\)", read('assets/app.js')))
    missing = sorted(i for i in needed if ('id="%s"' % i) not in page_html)
    if missing:
        raise SystemExit(
            'build aborted: %s/ is missing element id(s) %s that assets/app.js '
            'looks up. The page template and the script have drifted apart.'
            % (slug, ', '.join(missing)))


def calendar_page(town, events, dated, base):
    slug = slugify(town['name'])
    name = town['name']
    today = datetime.date.today()

    ev = [e for e in events if e['region'] == town['region']]
    ev += [e for e in dated if e['region'] == town['region'] and e['date'] >= str(today)]

    ranked_ev = []
    for e in ev:
        e = dict(e)
        vc = VENUES.get('%s|%s' % (e.get('venue', ''), e.get('city', '')))
        if vc:
            e['dist'] = round(miles(town['lat'], town['lon'], vc[0], vc[1]), 1)
            e['lat'] = vc[0]
            e['lon'] = vc[1]
        e['age_tags'] = EVENT_AGE_TAGS.get(e.get('ages'), '0-2 3-5 6-9 10+')
        e['env'] = event_env(e)
        ranked_ev.append(e)
    ev = ranked_ev

    title = 'Event calendar for %s · %s' % (name, SITE_NAME)
    desc = ('Full calendar of kid-friendly events near %s — markets, storytimes, '
            'open gyms, seasonal events and more.' % name)

    og_img = ''
    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical='%s%s/calendar/' % (base, slug), up='../../',
                      og_image=og_img,
                      nav='<a href="../../"><span class="nav-full">Change city</span>'
                          '<span class="nav-short">Cities</span></a>'
                          '<a href="../">%s</a>' % html.escape(name))

    out += '''
<main id="top">
  <section class="cal-section">
    <div class="wrap">
      <a class="cal-back" href="../">&larr; Back to %s</a>
      <div class="section-head">
        <h2>Event calendar</h2>
        <p class="section-sub">All events near %s &mdash; tap a date to see what&rsquo;s on</p>
      </div>
      <div id="calMonths"></div>
      <div id="calDetail"></div>
    </div>
  </section>
</main>
''' % (html.escape(name), html.escape(name))

    out += '<script>\nvar TOWN = %s;\nvar CAL_EVENTS = %s;\n</script>\n' % (
        json.dumps({'name': name, 'lat': town['lat'], 'lon': town['lon']}),
        json.dumps(ev, ensure_ascii=False))
    out += '<script src="../../assets/calendar.js?v=' + CAL_JS_V + '"></script>\n'
    out += FOOT
    return out


def city_intro(name, listed, ev, seasonal_groups, today):
    n = len(listed)
    indoor = [p for _, p in listed if p.get('env') == 'indoor']
    outdoor = [p for _, p in listed if p.get('env') == 'outdoor']
    free = [p for _, p in listed if (p.get('spec') or {}).get('price', '').startswith('Free')]
    parks = [p for _, p in listed if p.get('cat') in ('outdoors', 'play') and p.get('env') == 'outdoor']

    parts = []
    parts.append('%s has %d kid-friendly spots within driving distance' % (name, n))
    bits = []
    if outdoor:
        bits.append('%d outdoor' % len(outdoor))
    if indoor:
        bits.append('%d indoor' % len(indoor))
    if bits:
        parts[-1] += ' &mdash; %s' % ' and '.join(bits)
    parts[-1] += '.'

    if free and len(free) >= 2:
        parts.append('%d of them are completely free, including %s and %s.' % (
            len(free), free[0]['name'], free[1]['name']))

    if ev:
        week_count = len(ev)
        parts.append('There are %d events on the calendar this week &mdash; '
                     'storytimes, open gyms and markets.' % week_count)

    if seasonal_groups:
        parts.append('Check the seasonal section for pumpkin patches and special events running right now.')

    if parks and len(parks) >= 3:
        close_parks = sorted(listed, key=lambda x: x[0])
        close_parks = [p['name'] for _, p in close_parks
                       if p.get('cat') in ('outdoors', 'play') and p.get('env') == 'outdoor'][:3]
        parts.append('The closest parks are %s, %s and %s.' % (
            close_parks[0], close_parks[1], close_parks[2]))

    return ' '.join(parts)


FILTER_PAGES = [
    {
        'slug': 'indoor',
        'filter': lambda p: p.get('env') == 'indoor',
        'h1': 'Indoor activities for kids near %s',
        'title': 'Indoor activities for kids near %s · %s',
        'desc': 'Indoor play spaces, museums and activities for kids near %s — '
                'perfect for rainy days or foggy afternoons.',
        'lede': 'Play spaces, museums and indoor activities near %(name)s &mdash; '
                '%(n)d options within %(mi)d miles.',
    },
    {
        'slug': 'outdoor',
        'filter': lambda p: p.get('env') == 'outdoor',
        'h1': 'Outdoor activities for kids near %s',
        'title': 'Outdoor activities for kids near %s · %s',
        'desc': 'Parks, beaches and outdoor spots for kids near %s — '
                'sorted by distance so you can find the closest one.',
        'lede': 'Parks, beaches, trails and open-air attractions near %(name)s &mdash; '
                '%(n)d spots within %(mi)d miles.',
    },
    {
        'slug': 'free',
        'filter': lambda p: (p.get('spec') or {}).get('price', '').startswith('Free'),
        'h1': 'Free things to do with kids near %s',
        'title': 'Free things to do with kids near %s · %s',
        'desc': 'Free parks, beaches and trails for kids near %s — '
                'no tickets, no entry fee, just show up.',
        'lede': 'No entry fee, no tickets &mdash; just show up. %(n)d free spots for kids near %(name)s.',
    },
]


def filter_page(town, places, fp, base):
    slug = slugify(town['name'])
    name = town['name']
    ranked = sorted(((miles(town['lat'], town['lon'], p['lat'], p['lon']), p) for p in places),
                    key=lambda x: x[0])
    listed = [(d, p) for d, p in ranked if d <= LIST_MILES and fp['filter'](p)]
    if len(listed) < 2:
        return None

    title = fp['title'] % (name, SITE_NAME)
    desc = fp['desc'] % name
    lede = fp['lede'] % {'name': html.escape(name), 'n': len(listed), 'mi': LIST_MILES}
    canon = '%s%s/%s/' % (base, slug, fp['slug'])
    og_img = ''
    for _, p in listed:
        ph = photo_for(slugify(p['name']))
        if ph:
            og_img = '<meta property="og:image" content="%s%s" />' % (base, ph)
            break

    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical=canon, up='../../',
                      og_image=og_img,
                      nav='<a href="../../"><span class="nav-full">Change city</span>'
                          '<span class="nav-short">Cities</span></a>'
                          '<a href="../">%s</a>' % html.escape(name))

    out += '''
<main id="top">

  <section class="hero">
    <div class="wrap hero-inner">
      <h1 class="hero-title"><span class="hl">%s</span></h1>
      <p class="lede">%s</p>
    </div>
  </section>

  <section class="list-section" id="list">
    <div class="wrap">
      <div class="cards" id="cards">
%s
      </div>
    </div>
  </section>
</main>
''' % (html.escape(fp['h1'] % name), lede,
       ''.join(place_card(p, d, up='../../') for d, p in listed))

    out += places_jsonld([p for _, p in listed])
    out += FOOT
    return out


def city_page(town, places, events, dated, base):
    slug = slugify(town['name'])
    name = town['name']
    ranked = sorted(((miles(town['lat'], town['lon'], p['lat'], p['lon']), p) for p in places),
                    key=lambda x: x[0])
    listed = [(d, p) for d, p in ranked if d <= LIST_MILES]
    near = [p for d, p in ranked if d <= MAX_MILES]
    ev = [e for e in events if e['region'] == town['region']]
    today = datetime.date.today()
    week = {str(today + datetime.timedelta(days=i)) for i in range(7)}
    ev += [e for e in dated if e['region'] == town['region'] and e['date'] in week]

    seasonal_raw = [e for e in dated
                    if e['region'] == town['region']
                    and e.get('seasonal')
                    and e['date'] >= str(today)]
    seasonal_groups = group_seasonal(seasonal_raw, town)

    # How far each event is *from this town*. Copy first: these dicts are shared
    # across every city page, so writing distance in place would leave all five
    # pages showing whichever city was generated last. Baking it here is also
    # what finally makes the pages differ from each other in substance.
    ranked_ev = []
    for e in ev:
        e = dict(e)
        vc = VENUES.get('%s|%s' % (e.get('venue', ''), e.get('city', '')))
        if vc:
            e['dist'] = round(miles(town['lat'], town['lon'], vc[0], vc[1]), 1)
            e['lat'] = vc[0]
            e['lon'] = vc[1]
        ranked_ev.append(e)
    ev = ranked_ev

    title = 'Where to take the kids in %s · %s' % (name, SITE_NAME)
    desc = ('Places to take kids near %s, sorted by how far they are. '
            'The closest is %s, %s miles away.' % (name, ranked[0][1]['name'], show_miles(ranked[0][0])))

    og_img = ''
    for _, p in ranked:
        ph = photo_for(slugify(p['name']))
        if ph:
            og_img = '<meta property="og:image" content="%s%s/%s" />' % (base, slug, ph)
            break

    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical='%s%s/' % (base, slug), up='../',
                      og_image=og_img,
                      nav='<a href="../"><span class="nav-full">Change city</span>'
                          '<span class="nav-short">Cities</span></a>')

    intro = city_intro(name, listed, ev, seasonal_groups, today)

    browse_links = ''
    indoor_n = len([1 for _, p in listed if p.get('env') == 'indoor'])
    outdoor_n = len([1 for _, p in listed if p.get('env') == 'outdoor'])
    free_n = len([1 for _, p in listed if (p.get('spec') or {}).get('price', '').startswith('Free')])
    link_parts = []
    if indoor_n >= 2:
        link_parts.append('<a class="quick-link" href="indoor/"><span class="filter-label">Indoor</span> %d</a>' % indoor_n)
    if outdoor_n >= 2:
        link_parts.append('<a class="quick-link" href="outdoor/"><span class="filter-label">Outdoor</span> %d</a>' % outdoor_n)
    if free_n >= 2:
        link_parts.append('<a class="quick-link" href="free/"><span class="filter-label">Free</span> %d</a>' % free_n)
    link_parts.append('<a class="quick-link" href="calendar/">Calendar</a>')
    if link_parts:
        browse_links = '<nav class="browse-links">%s</nav>' % ''.join(link_parts)

    out += '''
<main id="top">

  <section class="hero">
    <div class="wrap hero-inner">
      <h1 class="hero-title"><span class="hl">Where to take the kids in %s</span></h1>
      <p class="lede">%d places within %d miles, closest first. %s</p>
      <p class="intro">%s</p>
      %s
      <p class="city-switch"><a href="../">Not your city? Pick another &rarr;</a></p>
    </div>
  </section>

  <!-- ad slot: below the fold, above the answer -->

  <div class="wrap"><div class="loc-bar" id="locBar"></div></div>

''' % (html.escape(name), len(listed), LIST_MILES,
       'Weekly markets and events too.' if ev else '',
       intro, browse_links)

    if seasonal_groups:
        out += seasonal_section_html(seasonal_groups, name)

    if ev:
        out += '''
  <section class="week" id="week">
    <div class="wrap">
      <div class="section-head">
        <h2>This week in the %s</h2>
        <p class="section-sub">Regular weekly events &mdash; markets, storytimes, open gyms</p>
      </div>
      <div class="daystrip" id="daystrip" role="tablist" aria-label="Pick a day"></div>
      <div class="events" id="events" role="tabpanel" aria-live="polite"></div>
      <p class="empty" id="weekEmpty" hidden></p>
      <p class="week-foot">
        Times come from what each organiser publishes &mdash; a fixed weekly slot for markets and
        open gyms, a per-date listing for library storytimes. Schedules change and sessions get
        cancelled, so confirm with the venue before you set out.
      </p>
      <a class="cal-cta" href="calendar/">View full calendar &rarr;</a>
    </div>
    <dialog class="ev-dialog" id="evDialog" aria-labelledby="evDialogTitle">
      <form method="dialog">
        <button class="ev-close" value="close" aria-label="Close details">&times;</button>
      </form>
      <div class="ev-detail" id="evDetail"></div>
    </dialog>
  </section>
''' % html.escape(REGIONS.get(town['region'], town['region']))

    out += '''
  <section class="list-section" id="list">
    <div class="wrap">
      <div class="section-head">
        <h2>Places near %s</h2>
        <p class="section-sub">Open year-round, closest first</p>
      </div>
%s
      <div class="cards" id="cards">
%s
      </div>
      <p class="empty" id="empty" hidden>Nothing matches that combination &mdash; try loosening a filter.</p>
    </div>
  </section>
''' % (html.escape(name), FILTERS, ''.join(place_card(p, d) for d, p in listed))

    out += TIPS
    out += '\n</main>\n'
    out += events_jsonld(ev, town, week)
    out += places_jsonld([p for _, p in listed])
    out += '<script>\nvar TOWN = %s;\nvar EVENTS = %s;\n</script>\n' % (
        json.dumps({'name': name, 'lat': town['lat'], 'lon': town['lon']}),
        json.dumps(ev, ensure_ascii=False))
    out += '<script src="../assets/app.js?v=' + APP_JS_V + '"></script>\n'
    check_app_contract(out, slug)
    out += FOOT
    return slug, out


def root_page(towns_with_pages, places, base):
    # Count only places a visitor can actually reach from some city page. Using
    # len(places) advertised the whole file, including Bay Area places that
    # FOCUS_REGION means no page lists -- a number nothing on the site backs up.
    listed = {
        p['name'] for p in places
        for t in towns_with_pages
        if miles(t['lat'], t['lon'], p['lat'], p['lon']) <= LIST_MILES
    }
    area = FOCUS_LABEL if FOCUS_REGION else 'Northern California'
    title = '%s · Where to take the kids in %s' % (SITE_NAME, area)
    desc = ('Pick your city and get places to take the kids, sorted by how far away they are. '
            '%d cities across %s.' % (len(towns_with_pages), area))

    out = HEAD.format(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True),
                      canonical=base, up='', nav='', og_image='')

    links = ''
    for key, label in GROUPS:
        group = [t for t in towns_with_pages if t['region'] == key]
        if not group:
            continue
        links += '        <section class="city-group">\n          <h3>%s</h3>\n          <ul>\n' % html.escape(label)
        for t in group:
            s = slugify(t['name'])
            links += '            <li><a href="%s/">%s</a></li>\n' % (s, html.escape(t['name']))
        links += '          </ul>\n        </section>\n'

    out += '''
<main id="top">
  <section class="hero">
    <div class="wrap hero-inner">
      <h1 class="hero-title">
        <span class="hl">Where are we taking</span>
        <span class="hl">the kids today?</span>
      </h1>
      <p class="lede">
        Things to do with the kids around ''' + (FOCUS_LABEL if FOCUS_REGION else 'Northern California') + ''' &mdash; playgrounds,
        museums, splash pads, farmers&rsquo; markets and library storytimes. Pick your city
        and you get what is on this week plus the places nearest you, with the parking
        and weather notes that decide whether it is worth the drive.
      </p>

      <p class="loc-hint" id="lastCity" hidden></p>
    </div>
  </section>

  <!-- ad slot: between hero and city index -->

  <section class="list-section" id="list">
    <div class="wrap">
      <div class="section-head">
        <h2>Choose your city</h2>
        <p class="section-sub">%d cities, %d places to take the kids. Every city links straight through.</p>
      </div>
      <div class="city-index">
%s      </div>
    </div>
  </section>
</main>
''' % (len(towns_with_pages), len(listed), links)

    out += '''<script>
// Offer the city this browser used last, without getting in the way of the list.
(function () {
  var hint = document.getElementById('lastCity');
  if (!hint) return;
  try {
    var last = localStorage.getItem('owtk.city');
    if (last && document.querySelector('.city-index a[href="' + last + '/"]')) {
      hint.hidden = false;
      hint.innerHTML = 'Last time you looked at <a href="' + last + '/">' +
        document.querySelector('.city-index a[href="' + last + '/"]').textContent + '</a>.';
    }
  } catch (e) {}
})();
</script>
'''
    out += FOOT
    return out


def main():
    towns = load('towns.json')
    if FOCUS_REGION:
        towns = [t for t in towns if t.get('region') == FOCUS_REGION]
    places = load('places.json')
    events = load('events.json')
    # Dated events come from per-source refresh scripts, one file per source
    # so a broken scraper can never wipe another source's data. Each entry
    # carries its own region; city_page filters on it.
    # dated_events_curated.json holds hand-added one-offs (not scraper-owned).
    dated = []
    for f in ('dated_events_sac.json', 'dated_events_marin.json',
              'dated_events_curated.json'):
        try:
            dated += load(f)
        except FileNotFoundError:
            pass  # first run before any refresh; weekly events still render
    base = BASE_URL

    keep, skipped = [], []
    for t in towns:
        n = sum(1 for p in places if miles(t['lat'], t['lon'], p['lat'], p['lon']) <= MAX_MILES)
        (keep if n >= MIN_PLACES else skipped).append((t, n))

    towns_with_pages = [t for t, _ in keep]

    # remove previously generated city directories that no longer qualify
    valid = {slugify(t['name']) for t in towns_with_pages}
    for entry in os.listdir(ROOT):
        p = os.path.join(ROOT, entry)
        if os.path.isdir(p) and os.path.exists(os.path.join(p, '.generated')) and entry not in valid:
            shutil.rmtree(p)

    extra_urls = []
    for t in towns_with_pages:
        slug, page = city_page(t, places, events, dated, base)
        d = os.path.join(ROOT, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(page)
        open(os.path.join(d, '.generated'), 'w').write('written by build.py\n')

        cal = calendar_page(t, events, dated, base)
        cd = os.path.join(d, 'calendar')
        os.makedirs(cd, exist_ok=True)
        open(os.path.join(cd, 'index.html'), 'w', encoding='utf-8').write(cal)
        extra_urls.append('%s%s/calendar/' % (base, slug))

        for fp in FILTER_PAGES:
            fhtml = filter_page(t, places, fp, base)
            if fhtml is None:
                continue
            fd = os.path.join(d, fp['slug'])
            os.makedirs(fd, exist_ok=True)
            open(os.path.join(fd, 'index.html'), 'w', encoding='utf-8').write(fhtml)
            extra_urls.append('%s%s/%s/' % (base, slug, fp['slug']))

    open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8').write(
        root_page(towns_with_pages, places, base))

    urls = [base] + ['%s%s/' % (base, slugify(t['name'])) for t in towns_with_pages]
    urls += extra_urls
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += ''.join('  <url><loc>%s</loc></url>\n' % u for u in urls)
    sm += '</urlset>\n'
    open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8').write(sm)
    open(os.path.join(ROOT, 'robots.txt'), 'w', encoding='utf-8').write(
        'User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n' % base)

    print('built %d city pages' % len(towns_with_pages))
    if skipped:
        print('skipped (fewer than %d places within %d mi):' % (MIN_PLACES, MAX_MILES))
        for t, n in skipped:
            print('   %-14s %d' % (t['name'], n))


if __name__ == '__main__':
    main()
