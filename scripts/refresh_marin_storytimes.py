#!/usr/bin/env python3
"""Daily refresh of Mill Valley Public Library storytimes.

The library publishes storytimes as dated instances through its public
LibCal calendar, so they are fetched per date (never encoded as weekly
recurrences) and written to data/dated_events_marin.json. build.py folds
the next 7 days of those into each Marin-area town page.

    python3 scripts/refresh_marin_storytimes.py

Stdlib only. Reads the library's public LibCal JSON feed; writes
data/dated_events_marin.json. Exits non-zero, leaving the file untouched,
when the feed fails or yields zero storytimes — the cron reports that
instead of publishing an empty calendar.
"""

import datetime as dt
import html as htmlmod
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# LibCal "list" endpoint for the library's "Calendar of Events" (cal_id 17002),
# filtered to the "Storytime" category (cat_id 60080). Returns one day's
# events as JSON; no auth needed — this is the same feed the library's own
# website uses.
LIST_URL = ("https://millvalleylibrary.libcal.com/ajax/calendar/list"
            "?c=17002&date={day}&perpage=100&page=1&cats=60080")

OUT_FILE = os.path.join(ROOT, "data", "dated_events_marin.json")

DAYS_AHEAD = 42  # how far out to keep dated entries

VENUE = "Mill Valley Public Library"
CITY = "Mill Valley"
REGION = "marin"


def fetch_day(day):
    req = urllib.request.Request(
        LIST_URL.format(day=day),
        headers={"User-Agent": "sacmoms-refresh/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def strip_tags(s):
    text = re.sub(r"<[^>]+>", " ", s or "")
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_result(r):
    # The feed is already filtered to the library's own "Storytime" category,
    # so the category is the filter — titles vary ("Cuentos con Ritmo",
    # "Sing & Stomp") and a keyword check would drop real storytimes.
    title = (r.get("title") or "").strip()
    if not title or "cancel" in title.lower():
        return None
    if r.get("all_day"):
        return None
    startdt = r.get("startdt") or ""
    m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2})", startdt)
    if not m:
        return None
    date, start = m.group(1), "%s:%s" % (m.group(2), m.group(3))
    enddt = r.get("enddt") or ""
    m = re.match(r"\d{4}-\d{2}-\d{2} (\d{2}):(\d{2})", enddt)
    until = "%s:%s" % (m.group(1), m.group(2)) if m else None

    low = title.lower()
    if "baby" in low:
        ages, blurb = "Babies", "Gentle songs, rhymes and book-sharing for babies and caregivers."
    elif "toddler" in low:
        ages, blurb = "Toddlers", "Books, songs and stories for toddlers and preschoolers with their caregivers."
    else:
        ages, blurb = "All ages", "Songs, rhymes, movement and stories for young children."
    desc = strip_tags(r.get("shortdesc") or r.get("description"))
    if desc and desc.lower() not in blurb.lower():
        blurb = desc
    if "cuento" in low or "bilingual" in blurb.lower() or "espa\u00f1ol" in blurb.lower():
        if "bilingual" not in blurb.lower():
            blurb += " Bilingual Spanish/English."
    location = (r.get("location") or "").strip()
    if location and location.lower() not in blurb.lower():
        blurb += " Meets in the %s." % location

    event = {
        "date": date,
        "time": start,
        "title": title,
        "venue": VENUE,
        "city": CITY,
        "region": REGION,
        "ages": ages,
        "blurb": blurb,
        "source": r.get("url") or "https://millvalleylibrary.libcal.com/",
    }
    if until:
        event["until"] = until
    return event


def main():
    today = dt.date.today()
    cutoff = today + dt.timedelta(days=DAYS_AHEAD)
    events = []
    failed_days = []
    day = today
    while day <= cutoff:
        try:
            data = fetch_day(day.isoformat())
        except Exception as e:  # noqa: BLE001 - one bad day must not kill the run
            failed_days.append((day.isoformat(), str(e)))
        else:
            for r in data.get("results", []):
                e = parse_result(r)
                if e and e["date"] >= today.isoformat():
                    events.append(e)
        day += dt.timedelta(days=1)

    # dedupe on (date, time, title); keep chronological
    seen, uniq = set(), []
    for e in sorted(events, key=lambda e: (e["date"], e["time"], e["title"])):
        key = (e["date"], e["time"], e["title"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)

    if failed_days:
        print("warning: %d day(s) failed to fetch: %s"
              % (len(failed_days), failed_days[:3]), file=sys.stderr)
    if not uniq:
        print("ERROR: zero storytimes parsed (failed days: %d) — leaving %s untouched"
              % (len(failed_days), OUT_FILE), file=sys.stderr)
        sys.exit(1)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote %d dated storytimes to %s (through %s)"
          % (len(uniq), OUT_FILE, cutoff.isoformat()))


if __name__ == "__main__":
    main()
