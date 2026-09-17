#!/usr/bin/env python3
"""Daily refresh of recurring weekly Marin events from the Marin Mommies calendar.

Idempotent: replaces the set of events.json entries tagged
origin="marin-mommies" with a fresh scrape. Entries matched by normalized title
keep their hand-fixed fields (original-source URLs, blurbs, ages); day/time/until
come from the fresh scrape. Truly new events get their detail page fetched and are
flagged so a human can swap the Marin Mommies link for the original organizer URL.

Zero-guard: if the scrape yields no weekly events, exits nonzero and leaves
events.json untouched (same contract as the storytime scrapers).
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

BASE = "https://www.marinmommies.com"
UA = "sacmoms-refresh/1.0 (daily refresh; contact via github.com/mingleiw/sacmoms)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(ROOT, "data", "events.json")
ORIGIN = "marin-mommies"


def fetch(url):
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA, url],
        capture_output=True, text=True,
    ).stdout
    time.sleep(0.4)
    return out


def clean(s):
    s = H.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def norm_title(t):
    t = t.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def parse_day(html):
    rows = re.split(r'<div class="views-row ', html)[1:]
    events = []
    for row in rows:
        m = re.search(r'views-field-title.*?<a href="(/calendar/[^"]+)">(.*?)</a>', row, re.S)
        if not m:
            continue
        slug, title = m.group(1), clean(m.group(2))
        dt = re.search(r'content="(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})', row)
        venue = re.search(r'views-field-field-address-locality.*?<strong>(.*?)</strong>', row, re.S)
        body = re.search(r'views-field-body.*?<span class="field-content">(.*?)</span>', row, re.S)
        events.append({
            "slug": slug,
            "title": title,
            "date": dt.group(1) if dt else None,
            "time": f"{dt.group(2)}:{dt.group(3)}" if dt else None,
            "venue_str": clean(venue.group(1)) if venue else "",
            "blurb": clean(body.group(1)) if body else "",
        })
    return events


def parse_detail(html):
    end = re.search(r'date-display-end[^>]*>([^<]+)<', html)
    body = re.search(r'views-field-body.*?<div class="field-items".*?>(.*?)</div>', html, re.S)
    return {
        "until_disp": clean(end.group(1)) if end else None,
        "body": clean(body.group(1)) if body else "",
    }


def to_24h(disp):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", disp.strip().lower())
    if not m:
        return None
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def infer_ages(title):
    t = title.lower()
    if re.search(r"crawl|bab(y|ies)|newborn|stroller", t):
        return "Babies & toddlers"
    if re.search(r"\btots?\b|littles|wiggle", t):
        return "Under 6"
    if re.search(r"26 ?mo|toddler", t):
        return "Under 3"
    if re.search(r"story ?time|music time", t):
        return "Under 6"
    if re.search(r"0[–-]5|preschool", t):
        return "Under 6"
    if re.search(r"\b(4|5)[–-]\d{1,2}\b", t):
        return "Ages 4+"
    if re.search(r"board game|parkour", t):
        return "Ages 5+"
    if re.search(r"mosaic|craft", t):
        return "Ages 4+"
    return "All ages"


def main():
    start = date.today()
    days = [start + timedelta(days=i) for i in range(21)]

    by_slug = defaultdict(list)
    for d in days:
        html = fetch(f"{BASE}/calendar/{d.isoformat()}")
        for ev in parse_day(html):
            if ev["date"]:
                by_slug[ev["slug"]].append(ev)

    # Detect weekly recurrences (same logic as the original import).
    recurring = []
    for slug, occs in sorted(by_slug.items()):
        first = occs[0]
        if "mill valley" in first["venue_str"].lower():
            continue  # covered by the Mill Valley library scraper
        js_days = Counter()
        times = Counter()
        for o in occs:
            y, m_, d_ = map(int, o["date"].split("-"))
            js_days[(date(y, m_, d_).weekday() + 1) % 7] += 1
            if o["time"]:
                times[o["time"]] += 1
        if len(js_days) >= 5:
            continue  # daily drop-in, no weekly slot
        recur = [(wd, n) for wd, n in js_days.items() if n >= 2]
        if not recur:
            continue  # one-off / seasonal
        wd = max(recur, key=lambda x: x[1])[0]
        time_24 = times.most_common(1)[0][0] if times else None
        venue_str = first["venue_str"]
        if ", " in venue_str:
            venue, city = venue_str.rsplit(", ", 1)
        else:
            venue, city = venue_str, venue_str
        recurring.append({
            "slug": slug, "title": first["title"], "day": wd,
            "time": time_24 or "10:00",
            "venue": venue.strip(), "city": city.strip(),
            "blurb": first["blurb"], "n_occs": len(occs),
        })

    existing = json.load(open(EVENTS_JSON))
    managed = [e for e in existing if e.get("origin") == ORIGIN]
    others = [e for e in existing if e.get("origin") != ORIGIN]
    by_title = {norm_title(e["title"]): e for e in managed}

    # Dedupe: the calendar sometimes lists the same weekly event under two slugs
    # with conflicting schedules. Prefer the candidate matching the existing
    # entry (stability bias); otherwise the one with more occurrences.
    by_key = defaultdict(list)
    for r in recurring:
        by_key[norm_title(r["title"])].append(r)
    deduped = []
    for key, cands in by_key.items():
        if len(cands) == 1:
            deduped.append(cands[0])
            continue
        old = by_title.get(key)
        if old is not None:
            match = [c for c in cands
                     if (c["day"], c["time"]) == (old.get("day"), old.get("time"))]
            if match:
                deduped.append(match[0])
                print(f"  AMBIGUOUS: {old['title']} listed twice; kept prior schedule")
                continue
        deduped.append(max(cands, key=lambda c: c["n_occs"]))
        print(f"  AMBIGUOUS: {cands[0]['title']} listed twice; kept most-listed schedule")
    recurring = deduped

    if not recurring:
        print("ERROR: scrape returned zero recurring events; keeping prior data", file=sys.stderr)
        return 1

    fresh, added, dropped, updated = [], [], [], []
    seen = set()
    for r in recurring:
        key = norm_title(r["title"])
        seen.add(key)
        if key in by_title:
            e = dict(by_title[key])  # keep hand-fixed fields (source, blurb, ages)
            if (e.get("day"), e.get("time")) != (r["day"], r["time"]):
                updated.append((e["title"], e.get("day"), e.get("time"), r["day"], r["time"]))
            e["day"] = r["day"]
            e["time"] = r["time"]
            e["origin"] = ORIGIN
            fresh.append(e)
        else:
            detail = parse_detail(fetch(BASE + r["slug"]))
            until = to_24h(detail["until_disp"]) if detail["until_disp"] else None
            blurb = detail["body"] or r["blurb"]
            blurb = re.sub(r"\.\.\.$", "", blurb).strip()
            # Cards clamp the blurb to three lines in CSS and the details
            # dialog shows the rest, so storing the full text costs nothing on
            # screen. The cap is only a guard against a runaway page body.
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
                "source": BASE + r["slug"],
                "day": r["day"],
                "origin": ORIGIN,
            }
            if until and until != e["time"]:
                e["until"] = until
            fresh.append(e)
            added.append(e["title"])

    for e in managed:
        if norm_title(e["title"]) not in seen:
            dropped.append(e["title"])

    json.dump(others + fresh, open(EVENTS_JSON, "w"), indent=1, ensure_ascii=False)
    open(EVENTS_JSON, "a").write("\n")

    print(f"marin-mommies refresh: {len(fresh)} weekly events "
          f"({len(updated)} rescheduled, {len(added)} new, {len(dropped)} dropped)")
    for t in added:
        print(f"  NEW (needs original source link): {t}")
    for t, od, ot, nd, nt in updated:
        print(f"  RESCHEDULED: {t} (day {od} {ot} -> day {nd} {nt})")
    for t in dropped:
        print(f"  DROPPED (no longer listed): {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
