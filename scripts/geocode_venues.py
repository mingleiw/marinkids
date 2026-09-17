#!/usr/bin/env python3
"""Geocode event venues so city pages can show how far each event is.

Events carry a venue name and a city but no coordinates, so a parent in Elk
Grove sees a storytime in North Highlands with no hint that it is a 20-minute
drive. This resolves each distinct (venue, city) once and writes the result to
data/venues.json, which build.py joins onto events at build time.

    python3 scripts/geocode_venues.py              # fill in what is missing
    python3 scripts/geocode_venues.py --recheck    # re-resolve everything
    python3 scripts/geocode_venues.py --dry-run    # list what it would look up

Stdlib only. Run it where the network reaches nominatim.openstreetmap.org --
the authoring sandbox blocks that host, the cron VM does not.

Two rules, because a wrong coordinate sends a family to the wrong side of the
county and this repo has shipped invented data once already:

  * Every entry records the query, the name Nominatim matched and the date it
    was resolved, so a bad match is auditable rather than anonymous.
  * A venue that cannot be resolved confidently is written with "lat": null and
    skipped by the build, which then shows no distance for it. Never a guess.

Existing entries are kept as-is unless --recheck is passed, so a hand-corrected
coordinate survives later runs. Add "locked": true to make one permanent.
"""

import argparse
import datetime as dt
import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(ROOT, "data", "venues.json")

NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy: at most one request a second, and a real UA that
# identifies the caller. Going faster gets the whole project blocked.
DELAY_S = 1.1
UA = "SacMoms/1.0 (+https://github.com/mingleiw/sacmoms)"

# The site covers Sacramento County; a match outside this box is wrong, however
# confident the geocoder sounds. Elk Grove Village, Illinois has already been
# mistaken for Elk Grove, California once in this project's history.
LAT_RANGE = (38.0, 39.1)
LON_RANGE = (-121.9, -120.8)


def key(venue, city):
    return "%s|%s" % (venue.strip(), city.strip())


def load_events():
    seen = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*events*.json"))):
        with open(path, encoding="utf-8") as f:
            for e in json.load(f):
                if e.get("region") != "sac":
                    continue
                v, c = e.get("venue"), e.get("city")
                if v and c:
                    seen.setdefault(key(v, c), (v, c))
    return seen


def load_existing():
    try:
        with open(OUT_FILE, encoding="utf-8") as f:
            return {key(r["venue"], r["city"]): r for r in json.load(f)}
    except (FileNotFoundError, ValueError):
        return {}


def query(q):
    url = NOMINATIM + "?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "countrycodes": "us"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve(venue, city):
    """Try the venue, then fall back to the venue without its branch suffix.

    Returns (lat, lon, matched_name, used_query) or (None, None, reason, q).
    """
    tries = ["%s, %s, CA, USA" % (venue, city)]
    # "North Highlands - Antelope Library" is two branch names joined by the
    # library's own convention; the second half is the searchable one.
    if " - " in venue:
        tries.append("%s, CA, USA" % venue.split(" - ", 1)[1].strip())
    for q in tries:
        try:
            hits = query(q)
        except Exception as exc:                      # network or parse failure
            print("  ! %s -> %s" % (q, exc), file=sys.stderr)
            time.sleep(DELAY_S)
            continue
        time.sleep(DELAY_S)
        if not hits:
            continue
        lat, lon = float(hits[0]["lat"]), float(hits[0]["lon"])
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            print("  ! %s -> outside Sacramento County (%.4f, %.4f), rejected"
                  % (q, lat, lon), file=sys.stderr)
            continue
        return lat, lon, hits[0].get("display_name", ""), q
    return None, None, "no confident match", tries[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recheck", action="store_true",
                    help="re-resolve entries that already have coordinates")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be looked up, fetch nothing")
    args = ap.parse_args()

    wanted, existing = load_events(), load_existing()
    todo = []
    for k, (v, c) in sorted(wanted.items()):
        cur = existing.get(k)
        if cur and cur.get("locked"):
            continue
        if cur and cur.get("lat") is not None and not args.recheck:
            continue
        todo.append((k, v, c))

    print("%d distinct venues in events, %d already resolved, %d to look up"
          % (len(wanted), sum(1 for r in existing.values() if r.get("lat") is not None), len(todo)))
    if args.dry_run:
        for _, v, c in todo:
            print("  would look up: %s, %s" % (v, c))
        return 0
    if not todo:
        print("nothing to do")
        return 0

    today = dt.date.today().isoformat()
    for k, v, c in todo:
        lat, lon, matched, q = resolve(v, c)
        existing[k] = {
            "venue": v, "city": c, "lat": lat, "lon": lon,
            "query": q, "matched": matched, "resolved": today,
            "source": "nominatim.openstreetmap.org",
        }
        print("  %-46s %s" % (v[:46], ("%.4f, %.4f" % (lat, lon)) if lat is not None else "UNRESOLVED"))

    rows = [existing[k] for k in sorted(existing)]
    got = sum(1 for r in rows if r.get("lat") is not None)
    # Refuse to replace a good file with a worse one: a geocoder outage would
    # otherwise wipe every coordinate and silently drop distances off the site.
    before = sum(1 for r in load_existing().values() if r.get("lat") is not None)
    if got < before:
        print("ERROR: would drop from %d resolved to %d; leaving %s untouched"
              % (before, got, OUT_FILE), file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote %d venues (%d resolved, %d unresolved) to %s"
          % (len(rows), got, len(rows) - got, OUT_FILE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
