#!/usr/bin/env python3
"""Daily refresh of family/kids-relevant Marin County Parks events.

Source: the county's official Trumba calendar feed
(https://www.trumba.com/calendars/marin_parks.json), which backs
https://www.parks.marincounty.gov/discoverlearn/events-calendar.
No API key needed; plain JSON.

Idempotent: data/dated_events_marin_parks.json is fully owned by this
script -- each run replaces it with the fresh feed. build.py loads that
file alongside the other dated-event files (one file per source, so a
broken scraper can never wipe another source's data).

Only family/kids-appropriate programs are kept (ranger walks, nature
programs, story/nature events, "all ages" listings). Volunteer workdays,
restoration crews, and commission meetings are filtered out.

Cross-source dedupe: Marin Mommies republishes some ranger events, so an
entry whose normalized (title, date) already appears in any other dated
file or matches a recurring events.json entry is skipped.

Zero-guard: if the feed fetch fails or parses to zero events, exits
nonzero and leaves the data file untouched.
"""
import json
import re
import html as H
import os
import subprocess
import sys
import time
from datetime import date

UA = "marinkids-refresh/1.0 (daily refresh; contact via github.com/mingleiw/marinkids)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(ROOT, "data", "dated_events_marin_parks.json")
EVENTS_JSON = os.path.join(ROOT, "data", "events.json")
FEED = "https://www.trumba.com/calendars/marin_parks.json"

# Strong kid/family signals: include on sight (unless excluded below).
KID_RES = [
    r"\bkids?\b", r"\bfamil", r"\bchild", r"\btoddler", r"\byouth",
    r"\bstory", r"\bjunior\b", r"all ages", r"\bpreschool", r"puppet",
    r"\bowl\b", r"stargaz", r"\bdiscovery\b", r"\bmovie\b", r"pumpkin",
]
# Generic ranger programming: only when it is actually a walk/hike/stroll
# program (not career talks or coffee meetups).
RANGER_OK_RES = [r"walk", r"hike", r"stroll", r"program", r"junior"]
EXCLUDE_RES = [
    r"workday", r"restoration", r"stewardship", r"weeding", r"commission",
    r"meeting", r"volunteer", r"training", r"\bboard\b", r"ipm\b",
    r"cleanup", r"invasive", r"13 and older", r"13\+", r"adults only",
    r"21\+", r"career", r"becoming a",
]

# Park/preserve location -> nearest site town (display only; region=marin
# puts the event on every town page and geocoding adds the distance).
LOCATION_CITY = {
    "black point boat launch": "Novato",
    "bolinas lagoon": "Bolinas",
    "bolinas lagoon preserve": "Bolinas",
    "bolinas park": "Fairfax",
    "deer island preserve": "Novato",
    "hal brown park": "San Rafael",
    "indian tree preserve": "Novato",
    "indian valley preserve": "Novato",
    "king mountain summit": "Larkspur",
    "lagoon park": "San Rafael",
    "las gallinas treatment ponds": "San Rafael",
    "loch lomond marina": "San Rafael",
    "lucas valley field office": "San Rafael",
    "marin headlands": "Sausalito",
    "mcinnis park": "San Rafael",
    "mcnears beach park": "San Rafael",
    "mill valley/sausalito path": "Mill Valley",
    "paradise beach park": "Tiburon",
    "point reyes national seashore": "Point Reyes Station",
    "point reyes park": "Point Reyes Station",
    "point reyes playground": "Point Reyes Station",
    "ring mountain preserve": "Corte Madera",
    "roy's redwoods preserve": "Fairfax",
    "rush creek preserve": "Novato",
    "samuel p taylor state park": "San Rafael",
    "stafford lake park": "Novato",
    "terra linda sleep hollow preserve": "San Rafael",
    "veterans memorial auditorium": "San Rafael",
    "white hill preserve": "Fairfax",
}


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


def relevant(title, desc):
    text = f"{title} {desc}"
    if any(re.search(p, text, re.I) for p in EXCLUDE_RES):
        return False
    if any(re.search(p, text, re.I) for p in KID_RES):
        return True
    # Ranger-led walks / nature walks are the county's family programming
    # even when the blurb doesn't say "family".
    if re.search(r"nature walk", title, re.I):
        return True
    if re.search(r"\branger", title, re.I) and any(
            re.search(p, text, re.I) for p in RANGER_OK_RES):
        return True
    return False


def infer_ages(title):
    t = title.lower()
    if re.search(r"toddler|bab(y|ies)", t):
        return "Under 3"
    return "All ages"


def main():
    raw = fetch(FEED)
    try:
        feed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        print("ERROR: parks Trumba feed did not parse; keeping prior data",
              file=sys.stderr)
        return 1
    if not feed:
        print("ERROR: parks Trumba feed returned zero events; keeping prior data",
              file=sys.stderr)
        return 1

    today = str(date.today())

    # Cross-source dedupe keys: (norm_title, date) from every other dated
    # file, plus recurring events (title + their weekday).
    seen_dated = set()
    for f in ("dated_events_curated.json", "dated_events_marin.json",
              "dated_events_sac.json"):
        p = os.path.join(ROOT, "data", f)
        try:
            for e in json.load(open(p)):
                if e.get("date"):
                    seen_dated.add((norm_title(e.get("title", "")), e["date"]))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    recurring = []
    try:
        for e in json.load(open(EVENTS_JSON)):
            if e.get("day") is not None:
                recurring.append((norm_title(e.get("title", "")), e["day"]))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    fresh, skipped_dup, skipped_irrelevant = [], 0, 0
    for ev in feed:
        if ev.get("canceled"):
            continue
        title = clean(ev.get("title"))
        desc = clean(ev.get("description"))
        if not relevant(title, desc):
            skipped_irrelevant += 1
            continue
        start = (ev.get("startDateTime") or "")[:16]  # local ISO
        if len(start) < 16:
            continue
        d, t = start.split("T")
        if d < today:
            continue
        end = (ev.get("endDateTime") or "")[:16]
        until = end.split("T")[1] if len(end) >= 16 and end[:10] == d else None
        loc = clean(ev.get("location"))
        if not loc or loc.lower() == "tbd":
            continue
        key = (norm_title(title), d)
        if key in seen_dated:
            skipped_dup += 1
            continue
        wd = (date(*map(int, d.split("-"))).weekday() + 1) % 7
        if any(nt == norm_title(title) and wday == wd for nt, wday in recurring):
            skipped_dup += 1
            continue
        city = LOCATION_CITY.get(loc.lower(), "San Rafael")
        blurb = desc
        if len(blurb) > 700:
            blurb = blurb[:697].rsplit(" ", 1)[0] + "…"
        entry = {
            "date": d,
            "time": t,
            "title": title,
            "venue": loc,
            "city": city,
            "region": "marin",
            "ages": infer_ages(title),
            "blurb": blurb,
            "source": ev.get("permaLinkUrl") or
                      "https://www.parks.marincounty.gov/discoverlearn/events-calendar",
        }
        if until and until != t:
            entry["until"] = until
        fresh.append(entry)
        seen_dated.add(key)

    fresh.sort(key=lambda e: (e["date"], e["time"]))
    json.dump(fresh, open(OUT_FILE, "w"), indent=1, ensure_ascii=False)
    open(OUT_FILE, "a").write("\n")

    print(f"marin-parks refresh: {len(fresh)} upcoming family events "
          f"({skipped_irrelevant} non-family filtered, {skipped_dup} duplicates skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
