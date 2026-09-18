#!/usr/bin/env python3
"""Daily refresh of recurring kids/family events from the Marin County Free
Library (MCFL) BiblioCommons calendar.

Idempotent: replaces the set of events.json entries tagged origin="mcfl"
with a fresh scrape. Entries matched by normalized title keep their
hand-fixed fields; day/time/until come from the fresh scrape. New events
flag the same "needs original source link" note as the marin-mommies
refresher (the source here IS the library's own page, so links are final).

How it works: BiblioCommons exposes no feed, but the event search pages are
server-rendered HTML with one card per occurrence. We pull the kid/family
audience result pages (early-stopping once cards run past ~5 weeks out),
group cards by event id, and keep events that recur on the same weekday
at least twice in the window -- the same recurrence rule as
refresh_marin_events.py.

Cross-origin dedupe: Marin Mommies republishes most MCFL storytimes, so any
candidate already present in events.json under ANY origin (same normalized
title + weekday + start time + venue) is skipped rather than duplicated.

Zero-guard: if the scrape yields no weekly events, exits nonzero and leaves
events.json untouched (same contract as the other refreshers).
"""
import json
import re
import html as H
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta

UA = "marinkids-refresh/1.0 (daily refresh; contact via github.com/mingleiw/marinkids)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(ROOT, "data", "events.json")
ORIGIN = "mcfl"
BASE = "https://marinlibrary.bibliocommons.com"

# BiblioCommons audience facet ids (scraped from the events page 2026-09-18;
# opaque but stable). Teens excluded: the site targets young kids.
AUDIENCES = {
    "families": "5fc70596c6979286093e62a3",
    "babies": "5fc52113ebec963a0084eb4b",
    "toddlers": "5ff7aeb025c2fc430bf25de4",
    "preschoolers": "5ff7aec25b24473a006c31fc",
    "kids": "5fc5210efc38cd4500b278dd",
    "tweens": "5ff7aedd0c78da240030f526",
}

# MCFL branch name as shown on cards -> (venue name, town)
BRANCHES = {
    "civic center": ("Civic Center Library", "San Rafael"),
    "fairfax": ("Fairfax Library", "Fairfax"),
    "novato": ("Novato Library", "Novato"),
    "south novato": ("South Novato Library", "Novato"),
    "corte madera": ("Corte Madera Library", "Corte Madera"),
    "marin city": ("Marin City Library", "Marin City"),
    "bolinas": ("Bolinas Library", "Bolinas"),
    "point reyes": ("Point Reyes Library", "Point Reyes"),
    "stinson beach": ("Stinson Beach Library", "Stinson Beach"),
    "inverness": ("Inverness Library", "Inverness"),
}

WINDOW_DAYS = 35  # stop paging once cards run past this


def fetch(url):
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, url],
        capture_output=True, text=True,
    ).stdout
    time.sleep(0.5)
    return out


def clean(s):
    s = H.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def norm_title(t):
    t = t.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def tidy_title(t):
    # Cards promote listings as "Title Featured Event. Title" (doubled with
    # the promo label in the middle) or append " Featured Event." at the end.
    t = re.sub(r"\s*featured event\.?", "", t, flags=re.I).strip()
    m = re.match(r"^(.+?)\.?\s+\1$", t)
    if m:
        t = m.group(1).strip()
    return t


# The Families audience also catches adult/tech programs and paused series.
SKIP_TITLE_RES = [
    r"\bon break\b", r"\bcancelled\b", r"\bhiatus\b", r"\bpostponed\b",
    r"tech help", r"homework help", r"all things apple", r"drop-in tech",
    r"esl\b", r"conversation club", r"book club", r"writers?\b",
    r"art talk", r"film screening", r"master class",
]


MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def parse_card(it):
    """One cp-events-search-item block -> occurrence dict or None."""
    m_id = re.search(r'href="(/events/([0-9a-f]{24}))"', it)
    m_t = re.search(r'cp-event-title.*?<a[^>]*>(.*?)</a>', it, re.S)
    m_dt = re.search(r'cp-event-date-time[^>]*>(.*?)</div>', it, re.S)
    m_loc = re.search(r'cp-event-location-name[^>]*>(.*?)</div>', it, re.S)
    m_desc = re.search(r'cp-event-description[^>]*>(.*?)</div>', it, re.S)
    if not (m_id and m_t and m_dt):
        return None
    title = tidy_title(clean(m_t.group(1)))
    raw_title = clean(m_t.group(1))
    if any(re.search(p, raw_title, re.I) for p in SKIP_TITLE_RES):
        return None  # paused/cancelled series, or adult programs
    dt_txt = clean(m_dt.group(1))
    if re.search(r"all day", dt_txt, re.I):
        return None  # displays/exhibits, not timed programs
    m_date = re.search(r"on ([A-Z][a-z]+) (\d{1,2}), (\d{4})", dt_txt)
    if not m_date:
        return None
    mon = MONTHS[m_date.group(1).lower()]
    d = date(int(m_date.group(3)), mon, int(m_date.group(2)))
    m_time = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)\s*[–-]\s*(\d{1,2}):(\d{2})\s*(am|pm)",
                       dt_txt, re.I)

    def to24(h, mi, ap):
        h = int(h)
        if ap.lower() == "p" and h != 12:
            h += 12
        if ap.lower() == "a" and h == 12:
            h = 0
        return f"{h:02d}:{mi}"

    if m_time:
        start = to24(m_time.group(1), m_time.group(2), m_time.group(3))
        until = to24(m_time.group(4), m_time.group(5), m_time.group(6))
    else:
        m1 = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", dt_txt, re.I)
        if not m1:
            return None
        start, until = to24(m1.group(1), m1.group(2), m1.group(3)), None
    branch_raw = clean(m_loc.group(1)).replace("Event location:", "").strip() if m_loc else ""
    # Card text doubles the branch ("Bolinas  Bolinas"); collapse it.
    branch = re.sub(r"^(.+?)\s+\1$", r"\1", branch_raw, flags=re.I).strip().lower()
    if branch not in BRANCHES:
        return None
    venue, city = BRANCHES[branch]
    desc = clean(m_desc.group(1)) if m_desc else ""
    return {
        "event_id": m_id.group(2), "link": BASE + m_id.group(1),
        "title": title, "date": d, "start": start,
        "until": until if until != start else None,
        "venue": venue, "city": city, "blurb": desc,
    }


def detail_title(link):
    """Canonical title from the event's own page (list cards sometimes drop
    status prefixes like 'ON BREAK:')."""
    html = fetch(link)
    m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
    if not m:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
    return clean(m.group(1)) if m else ""


def infer_ages(title):
    t = title.lower()
    if re.search(r"bab(y|ies)|bounce|newborn", t):
        return "Babies & toddlers"
    if re.search(r"toddler", t):
        return "Under 3"
    if re.search(r"story ?time|sing|music|wiggle|bounce", t):
        return "Under 6"
    if re.search(r"preschool", t):
        return "Under 6"
    if re.search(r"lego|chess|craft", t):
        return "Ages 4+"
    if re.search(r"homework|tween", t):
        return "Ages 6+"
    return "All ages"


def main():
    start = date.today()
    horizon = start + timedelta(days=WINDOW_DAYS)

    seen_ids = set()
    occs = []  # occurrence dicts
    # Families audience: page until cards run past the horizon.
    for page in range(1, 11):
        html = fetch(f"{BASE}/v2/events?audiences={AUDIENCES['families']}&page={page}")
        items = re.split(r'class="cp-events-search-item"', html)[1:]
        if not items:
            break
        max_date = start
        for it in items:
            c = parse_card(it)
            if not c:
                continue
            max_date = max(max_date, c["date"])
            key = (c["event_id"], c["venue"])
            if key in seen_ids:
                continue
            seen_ids.add(key)
            occs.append(c)
        if max_date > horizon:
            break
    if not occs:
        print("ERROR: MCFL scrape returned zero occurrences; keeping prior data",
              file=sys.stderr)
        return 1

    # Other kid audiences: first page only, to catch strays the Families
    # audience misses (heavy overlap, so this is cheap).
    for name, aid in AUDIENCES.items():
        if name == "families":
            continue
        html = fetch(f"{BASE}/v2/events?audiences={aid}&page=1")
        for it in re.split(r'class="cp-events-search-item"', html)[1:]:
            c = parse_card(it)
            if not c:
                continue
            key = (c["event_id"], c["venue"])
            if key in seen_ids:
                continue
            seen_ids.add(key)
            occs.append(c)

    # Recurrence detection: BiblioCommons mints a fresh event id per
    # occurrence, so group by (title, venue, start time) instead. Same
    # weekday >= 2 occurrences, not a daily drop-in.
    by_event = defaultdict(list)
    for o in occs:
        if any(re.search(p, o["title"], re.I) for p in SKIP_TITLE_RES):
            continue  # adult programs / paused series caught by the audience filter
        by_event[(norm_title(o["title"]), o["venue"], o["start"])].append(o)
    recurring = []
    for (nt, venue, start), os_ in sorted(by_event.items()):
        js_days = Counter((o["date"].weekday() + 1) % 7 for o in os_)
        if len(js_days) >= 5:
            continue  # daily drop-in
        recur = [(wd, n) for wd, n in js_days.items() if n >= 2]
        if not recur:
            continue  # one-off
        wd = max(recur, key=lambda x: x[1])[0]
        first = os_[0]
        untils = Counter(o["until"] for o in os_ if o["until"])
        recurring.append({
            "title": first["title"], "day": wd,
            "time": start,
            "until": untils.most_common(1)[0][0] if untils else None,
            "venue": venue, "city": first["city"],
            "blurb": max((o["blurb"] for o in os_), key=len, default=""),
            "source": first["link"],
        })

    if not recurring:
        print("ERROR: MCFL scrape found no weekly events; keeping prior data",
              file=sys.stderr)
        return 1

    existing = json.load(open(EVENTS_JSON))
    managed = [e for e in existing if e.get("origin") == ORIGIN]
    others = [e for e in existing if e.get("origin") != ORIGIN]
    # Match on the full slot (title, venue, weekday, time): a series can
    # legitimately list occurrences at more than one time (e.g. Fairfax
    # Bilingual Storytime has 09:30 and 10:15 slots), and title-only
    # matching collapsed those into one entry and flip-flopped on updates.
    by_slot = {}
    by_series = defaultdict(list)
    for e in managed:
        skey = (norm_title(e.get("title", "")), e.get("venue", ""), e.get("day"))
        by_series[skey].append(e)
        by_slot[skey + (e.get("time"),)] = e

    def covered(title, day, time_, venue):
        """Already on the site under any origin (Marin Mommies republishes
        most MCFL storytimes) -> skip instead of duplicating."""
        nt, nv = norm_title(title), norm_title(venue)
        for e in existing:
            if (norm_title(e.get("title", "")) == nt
                    and e.get("day") == day and e.get("time") == time_
                    and norm_title(e.get("venue", "")) == nv):
                return True
        return False

    fresh, added, dropped, updated, skipped = [], [], [], [], []
    seen = set()
    for r in recurring:
        skey = (norm_title(r["title"]), r["venue"], r["day"])
        tkey = skey + (r["time"],)
        seen.add(tkey)
        if tkey in by_slot:
            e = by_slot[tkey]
            e["day"] = r["day"]
            e["time"] = r["time"]
            e["origin"] = ORIGIN
            fresh.append(e)
        elif (len(by_series.get(skey, [])) == 1
                and by_series[skey][0]["source"] == r["source"]
                and not covered(r["title"], r["day"], r["time"], r["venue"])):
            # Genuine reschedule of a single-slot series: keep the entry,
            # move it to the new time.
            e = by_series[skey][0]
            if (e.get("day"), e.get("time")) != (r["day"], r["time"]):
                updated.append((e["title"], e.get("day"), e.get("time"),
                                r["day"], r["time"]))
            e["day"] = r["day"]
            e["time"] = r["time"]
            e["origin"] = ORIGIN
            fresh.append(e)
        elif covered(r["title"], r["day"], r["time"], r["venue"]):
            skipped.append(r["title"])
        else:
            canon = detail_title(r["source"])
            if any(re.search(p, canon, re.I) for p in SKIP_TITLE_RES):
                print(f"  SKIPPED (paused/adult per detail page): {r['title']}")
                continue
            blurb = r["blurb"]
            if len(blurb) > 700:
                blurb = blurb[:697].rsplit(" ", 1)[0] + "…"
            e = {
                "time": r["time"],
                "title": r["title"],
                "venue": r["venue"],
                "city": r["city"],
                "region": "marin",
                "ages": infer_ages(r["title"]),
                "blurb": blurb,
                "source": r["source"],  # the library's own event page
                "day": r["day"],
                "origin": ORIGIN,
            }
            if r["until"] and r["until"] != e["time"]:
                e["until"] = r["until"]
            fresh.append(e)
            added.append(e["title"])

    for e in managed:
        skey = (norm_title(e.get("title", "")), e.get("venue", ""), e.get("day"))
        if skey + (e.get("time"),) not in seen:
            dropped.append(e["title"])

    json.dump(others + fresh, open(EVENTS_JSON, "w"), indent=1, ensure_ascii=False)
    open(EVENTS_JSON, "a").write("\n")

    print(f"mcfl refresh: {len(fresh)} weekly events "
          f"({len(updated)} rescheduled, {len(added)} new, {len(dropped)} dropped, "
          f"{len(skipped)} already covered by other sources)")
    for t in added:
        print(f"  NEW: {t}")
    for t, od, ot, nd, nt in updated:
        print(f"  RESCHEDULED: {t} (day {od} {ot} -> day {nd} {nt})")
    for t in dropped:
        print(f"  DROPPED (no longer listed): {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
