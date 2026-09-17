# Design: SacMoms

## The goal

Help a parent or caregiver, on any given day, decide where to take the kids —
**without making them do the searching.**

> **Scope note.** This document records the design as reasoned through at Bay
> Area / Northern California scope. The site now ships **Sacramento County only**
> — 5 city pages, via `FOCUS_REGION = 'sac'`. Bay Area references below are
> history, not a description of what is built. Current state is *Sacramento-first*
> at the end.

The benchmark is Marin Mommies. Two things about it matter:

- It works because **a human editor curates one county**. Everything within twenty
  minutes, so the reader never asks "is this too far."
- Scaling that model to nine counties means roughly nine times the editorial
  labour. That is the reason nobody has beaten it Bay-Area-wide. It is a
  content-supply problem, not a design problem.

So the bet is: **automated aggregation + personalisation beats editorial breadth.**
The site should answer, not list.

---

## Decisions

| # | Decision | Chosen |
| --- | --- | --- |
| 1 | Content engine | Aggregate from public sources automatically |
| 2 | Where it runs | Scheduled workflow; agent refreshes nightly |
| 3 | Trust gate | Hard provenance — no source URL, no publish |
| 4 | Source allowlist | All three categories from day one |
| 5 | Data model | Three types: events, places, seasonal |
| 6 | Geography | Home location set once, sort by distance |
| 7 | Homepage | Short ranked shortlist — "Today, near you" |
| 8 | Ranking inputs | Weather-aware |
| 9 | Age | No profile — tag items, parent filters |
| 10 | First slice | Prove the pipeline end-to-end on a few sources |
| 11 | Nightly job | Agent-first, crystallise into parsers as sources prove out |

### Why the non-obvious ones

**3 — Hard provenance.** An agent generating listings nightly is a fabrication
risk. It will confidently emit "Toddler Storytime, 10:30am, Berkeley Public
Library" whether or not it read that anywhere, and a parent will drive there.
So: every item carries the URL it was read from, that URL must be on the
allowlist, and the build drops anything failing schema or provenance. Each
listing shows its source so a parent can verify in one tap.

Corollary: **if a source fails to fetch, keep the last known-good data.** Silent
data loss is worse than slightly stale data.

**5 — Seasonal as a first-class type.** Arguably just a date-ranged event, but
making it its own type forces a **required validity window**, so it self-retires.
A pumpkin patch still listed in December is the fastest way to look abandoned.
Structural beats disciplined.

**6 — Distance over regions.** "East Bay" spans Richmond to Fremont, about fifty
miles. A region filter cannot answer "is this worth the drive," which is the
actual question. Home location is stored in `localStorage`, never leaves the
browser, so **ranking runs client-side.**

**8 — Weather.** In a region where it is 55°F and fogged in at Ocean Beach while
85°F in Walnut Creek, and where half the year is a rainy season, today's forecast
is the most decision-changing fact available. Open-Meteo needs no API key, is
called client-side, and **must degrade silently to the plain ranking on failure.**

**9 — No age profile.** Chosen deliberately for a zero-friction first visit.
Known cost: the shortlist loses its second-strongest signal, so a toddler
lap-sit can surface for a parent of a nine-year-old. Mitigation, pending
confirmation: remember the age chip they last tapped, the way we remember
location. Never ask — just don't make them re-tap it every visit.

**4 — Broad sources day one.** Chosen over a library-first ramp. Consequence:
with ~40 sources you cannot eyeball whether last night's run worked, so
**per-source health tracking is part of the build, not a follow-up.** Each run
records per source: fetched, items found, items rejected, and why.

---

## Architecture

```
nightly cron (GitHub Actions)
      │
      ├── read sources/registry.json      name, url, region, type, allowed domain
      ├── agent extracts candidate items  agent-first; freeze stable ones into parsers
      ├── geocode venues                  needed for distance ranking
      ├── VALIDATE ─── reject: no source URL / off-allowlist / bad schema
      │                on total source failure → keep last known-good
      ├── write data/{events,places,seasonal}.json  + data/health.json
      └── commit → Pages redeploys

browser (static, no server)
      ├── read JSON
      ├── home location from localStorage
      ├── weather from Open-Meteo (degrades silently)
      └── rank → shortlist, then full list
```

No server, no database, no vendor. The site stays a fast static page that reads
JSON files.

---

## Data model

Three types sharing a common core:

```jsonc
{
  "id": "stable-hash",
  "type": "event | place | seasonal",
  "title": "Preschool Storytime",
  "venue": "Belvedere Tiburon Library",
  "city": "Tiburon",
  "region": "marin",
  "lat": 37.87, "lon": -122.46,     // required: distance ranking
  "ages": "2–5",                     // display + filter, not a profile
  "indoor": true,
  "blurb": "…",
  "sourceUrl": "https://…",          // REQUIRED — no publish without it
  "fetchedAt": "2026-09-16T08:00:00Z"
}
```

Type-specific:

- **event** — `day` (0–6) + `time` for weekly recurrence, or a specific `date`
- **place** — no schedule; always open
- **seasonal** — `validFrom` / `validUntil`, **required**, auto-expires

### Editorial rule

**No opening hours, admission prices or one-off dates written by hand.** They
change constantly and a stale value sends a family on a wasted trip. Items carry
things that rarely change plus a map link that is always current.

---

## Sequencing

**First slice — prove the pipeline.** Pick 3–5 sources across the three types.
Build the registry, agent extraction, the provenance validator, published JSON,
and render through the existing UI.

This attacks the only genuinely unproven assumption — *can an agent reliably pull
real, correctly-dated items out of heterogeneous sources, at a nightly cost worth
paying* — while it is still cheap to find out. It answers three things: real
per-night cost, true error rate, and whether "no source URL, no publish" rejects
half the output.

Weather, distance ranking and the shortlist come **after** there is genuine data
to rank. They are conventional work; the pipeline is the risk.

---

## Blockers

1. ~~**Actions token is clamped read-only on this fork.**~~ **Moot.** The nightly
   job never ran in GitHub Actions. `scripts/daily_refresh.sh` runs from cron in
   an agent runtime and pushes via a helper that authenticates through the Secure
   Vault at call time, so no Actions token and no repo secret is involved. The
   workflow that hit `Resource not accessible by integration` was removed rather
   than left failing.
2. **API key secret** for the agent in CI.
3. **"Meta Muse"** — named as the day-one data source; term not yet explained.
   Its output format determines the schema to build against.
4. ~~No outbound web in the authoring environment.~~ **Wrong.** `WebSearch`
   routes server-side and works; only `curl` and `WebFetch` go through the
   sandbox proxy and are blocked. Research can happen here. Fetching a specific
   URL to parse still cannot, so extraction code is still only testable in CI,
   and the pipeline should still fail closed.

## Sacramento added

Elk Grove is the intended first city, so the site now covers the Sacramento
area as a sixth region: nine places (four inside Elk Grove itself) and two
recurring markets. From Elk Grove the nearest listed place went from 59 miles
to 0.7.

Sources were found by search and filtered by hand. Two things that would have
shipped as errors without checking:

- The first results for "Elk Grove library storytime" are **Elk Grove Village,
  Illinois** — a different state entirely.
- The Elk Grove branch of Sacramento Public Library **stopped serving at its old
  address on 25 July 2026** and is relocating, with a grand opening given only
  as "early Fall 2026". No storytime is listed there, because it cannot be
  confirmed running.

The header label changed from "Bay Area" to "Northern California". **Both are now
superseded:** the site is branded SacMoms and scoped to Sacramento County, and the
title, header and Open Graph copy all say so. The branding question recorded here
is closed.

## URL architecture

One page per city, at `/<city-slug>/`, with the root reduced to a city picker.

The reason a build step appeared, after "no build step" had been a stated virtue:
a city page needs its places sorted by distance *from that city*. Computing that
at build time rather than in the browser means each page ships genuinely
different, crawlable content, and the full list renders with JavaScript off.
`build.py` writes 38 city pages, the root, a sitemap and robots.txt; all of it is
committed, so Pages still serves plain static files and nothing runs on deploy.

Two guards exist because the stated long-term goal is ads, and ads mean traffic,
and traffic means these pages have to be worth indexing:

- **`MIN_PLACES` / `MAX_MILES`** — a city needs 4 places within 25 miles to get a
  page. Four towns don't qualify (Santa Rosa has none within 25 miles) and are
  skipped rather than published thin.
- **`LIST_MILES`** — a page lists only places within 40 miles. Without it all 38
  pages carry the same 30 places in a different order, which is the doorway-page
  pattern search engines demote. With it, Elk Grove lists 9 Sacramento places and
  Berkeley lists 17 Bay Area ones.

The root page originally carried both a `<select>` and a full list of `<a>`
links: a dropdown is not crawlable, so a picker alone would have left every city
page undiscoverable.

**The dropdown is gone.** It made sense at 38 cities across six regions, where a
long list needs collapsing. At five cities it showed the same five names twice on
one short page, and a dropdown costs a tap, a scroll and a selection where a link
costs one tap. The crawlable `<a>` links were always the half that mattered, so
they stay and are now the only way in, under the heading *Choose your city*. The
"last time you looked at X" shortcut moved to the hero and still works.

If the city count ever grows enough that the list stops being scannable, the
answer is a filter or a search box over real links — not a `<select>` that
duplicates them.

## Status

- Placeholder events **deleted** — they were invented, and this is a public URL.
- 21 real places remain, still hand-written in `index.html`; they migrate to
  `data/places.json` when the schema lands.
- Calendar engine renders an honest empty state with no events.

### POC shipped — decisions 6, 7, 8 proven

The consumer half now runs on the 21 real places:

- **Home location** (decision 6) — 41 Bay Area towns, stored in `localStorage`,
  never sent anywhere. Distances shown per place, list sorted nearest-first.
- **Shortlist** (decision 7) — top three, each stating *why* it was chosen
  ("1.6 mi away · indoors"). Respects the filters.
- **Weather** (decision 8) — Open-Meteo, client-side, reorders the shortlist.

Verified across all three weather states by intercepting the request: rain
promotes Chabot (indoor, 6.2 mi) above Tilden (outdoor, 2.4 mi) — the weighting
genuinely changes the answer, not just the label. With the request blocked, the
page silently falls back to distance-only, which is the path that actually runs
in this environment.

Coordinates are hand-entered approximations, accurate enough to rank 5 miles
against 40 (Berkeley→Lawrence Hall 1.6 mi, Berkeley→Gilroy 69.3 mi). The pipeline
replaces them with real geocoding; the map link stays authoritative.

**Still unproven: the pipeline itself** (decisions 1–4, 11), which is the part
that can actually kill the project. It cannot be built here — no outbound web, no
API key, and the Actions token is still clamped read-only.

---

## Sacramento-first — current state

Scope narrowed from Northern California to **Sacramento County**, and the site was
rebranded **Kidventures → SacMoms**. `FOCUS_REGION = 'sac'` in `build.py` filters
towns at build time; the Bay Area towns, places and Marin events stay in `data/`
rather than being deleted, so widening scope later is a one-line change.

Ships today: `/sacramento/`, `/elk-grove/`, `/folsom/`, `/rancho-cordova/`,
`/citrus-heights/`, plus the root picker. 30 places (9 in region), 51 weekly
events (7 in region), 123 dated Sacramento library storytimes.

### The pipeline is no longer unproven

The paragraph above is superseded. `scripts/daily_refresh.sh` runs from cron in an
agent runtime, scrapes, rebuilds, commits and pushes. `data/dated_events_sac.json`
holds **123 real dated storytimes**, each with its own per-event source URL on
`engage.saclibrary.org` — decisions 1–4 and 11 demonstrated end to end on a real
source. Decision 3 (hard provenance) held: nothing publishes without a source URL.

Two things learned in the running system:

- **Verbatim beats tidy.** Four scraped titles carry a literal ASCII `?` where a
  dash belongs. It is in the library's own listing, not a decoding fault. Left
  as-is: normalising it would make the page disagree with the source it links to.
- **Fail-closed has a blast radius.** Scrapers exit non-zero on an empty scrape so
  a bad run cannot publish an empty calendar — correct. But `daily_refresh.sh` is
  `set -e`, so a **Mill Valley** outage aborted the run before Sacramento was
  rebuilt or pushed, over data `FOCUS_REGION` discards. Fail-closed has to be
  scoped to the data that actually ships; the Marin calls are now non-fatal.

### Open issue: the SEO guards stopped guarding

`MIN_PLACES` / `MAX_MILES` / `LIST_MILES` were the answer to decision-driven
worry about doorway pages, and under Bay Area scope they worked. Under
Sacramento-only scope they are inert:

- all 9 in-region places fall within `LIST_MILES` of all 5 towns, so nothing is
  excluded and every page lists the same 9
- events match on `region`, not proximity, so every page ships a **byte-identical
  `EVENTS` payload** — verified, 35 events, identical across all five
- Folsom, Rancho Cordova and Citrus Heights share an identical top-four

So the pages differ only by sort order and printed distances. At five pages this
is arguably honest — distance ordering *is* the answer a parent wants — but it is
exactly the pattern the thresholds were added to prevent, and it gets worse with
every city added.

The guards were geometry-based, and geometry stopped discriminating when the
region got small relative to the radius. **A threshold that encodes an assumption
about scale silently stops working when the scale changes**, without erroring.

Fixing it means making pages differ in substance: match events by distance from
the town rather than by region, and add places outside the Sacramento core. Until
then, city count should not grow.
