#!/bin/bash
# Daily refresh: re-scrape library storytimes, refresh other recurring events,
# rebuild the site, push if changed.
# Run from cron. The push helper authenticates through the Secure Vault, so this
# needs the VM's authd socket (present in the normal agent runtime).
set -euo pipefail
cd "$(dirname "$0")/.."

# Marin sources gate the run. build.py renders FOCUS_REGION ('marin'), so these
# feed the pages we actually publish — a failure here must stop the push rather
# than quietly ship a thinner calendar. Scripts exit non-zero and leave their
# data files untouched when their source yields nothing, so a zero-guard trip
# also stops the push instead of publishing an empty calendar.
#
# The one exception is refresh_marin_mcfl.py: BiblioCommons rate-limits this
# IP with bare 404s after bursts of requests (seen 2026-09-18), so a failed
# MCFL run is a warning, not a blocker. Its entries are weekly recurring
# events with official-source links, so serving yesterday's MCFL list for a
# day is low-harm; the next clean run re-syncs and drops stale series.
python3 scripts/refresh_marin_storytimes.py   # Mill Valley Public Library storytimes (LibCal)
python3 scripts/refresh_marin_events.py       # Recurring weekly events from the Marin Mommies calendar
python3 scripts/refresh_marin_mcfl.py || echo "warning: MCFL refresh failed (likely BiblioCommons throttling); keeping prior MCFL events" >&2
python3 scripts/refresh_marin_parks.py        # Family-relevant Marin County Parks events (Trumba feed) -> data/dated_events_marin_parks.json

# New venues appear whenever the library rotates storytimes to a branch we have
# not seen. This only looks up the ones missing coordinates, so it is usually a
# no-op. Non-fatal on purpose: a geocoder outage must not block the push, and
# events without coordinates simply show no distance.
python3 scripts/geocode_venues.py || echo "warning: venue geocoding failed; events may show no distance" >&2

python3 build.py

if [ -z "$(git status --porcelain)" ]; then
  echo "no changes"
  exit 0
fi

# gh-push-tree lives outside the repo (it holds no secrets; auth comes from the
# Secure Vault at call time).
~/workspace/skills/github/bin/gh-push-tree "$(pwd)" "Daily storytime refresh ($(date +%F))" main

# Keep the local clone in sync with what was just pushed so tomorrow's
# `git status` only shows genuinely new changes.
git fetch -q origin main
git reset -q --hard origin/main
echo "pushed and synced"
