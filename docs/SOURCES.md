# MarinKids event sources

How each source feeds the site, and — just as important — what was
deliberately left out and why. Updated 2026-09-18.

## Live sources (run by scripts/daily_refresh.sh)

| Source | Script | What it ingests | Gating |
|---|---|---|---|
| Mill Valley Public Library | `refresh_marin_storytimes.py` | Storytimes via LibCal | fatal |
| Marin Mommies calendar | `refresh_marin_events.py` | Recurring weekly kids events (aggregator used as a *discovery* source; entries keep hand-fixed original-source links) | fatal |
| Marin County Free Library | `refresh_marin_mcfl.py` | Recurring kids events via BiblioCommons (official library calendar) | **non-fatal**: BiblioCommons rate-limits this IP with bare 404s after request bursts (observed 2026-09-18); a failed run warns and keeps prior data |
| Marin County Parks | `refresh_marin_parks.py` | Family-relevant ranger/nature programs via the county's public Trumba JSON feed → `data/dated_events_marin_parks.json` | fatal |

## Hand-verified recurring events (no automation possible)

| Source | Origin tag | Why manual |
|---|---|---|
| San Rafael Public Library (Downtown Storytime, Spanish Sing-Along, Lego Saturdays, Kids' Builders Club, Pokémon Club) | `srpl` | srpubliclibrary.org blocks automated fetches at the connection level (curl returns 000). Five weekly programs verified on the live site 2026-09-18. Re-verify by hand when the library's calendar changes. |
| San Anselmo Library (Bilingual Spanish Storytime Wed, Sing and Stomp Fri; Monday storytime already via Marin Mommies) | `sananselmo` | Mon/Wed/Fri 10:30 storytime & movement programs at Imagination Park, verified on the town's official calendar (sananselmo.gov) 2026-09-18. Hand-maintained; re-verify if the schedule changes. |

## Hand-verified dated events (`data/dated_events_curated.json`)

- **Slide Ranch** Family Farm Days + Campouts (official events page, verified 2026-09-18)
- **Marine Mammal Center** Marine Science Sundays (official program page, verified 2026-09-18)
- **Marin MOCA** Family Day, 2nd Sundays (official page, verified 2026-09-18)
- **Book Passage** Saturday Storytime, 1st Saturdays (official calendar page, verified 2026-09-18; direct curl 403s)
- Fall one-offs (Mill Valley Fall Arts Festival, Tam Valley Oktoberfest, San Rafael PorchFest, Halloween Harvest Festival, Corte Madera Oktoberfest, San Domenico Garden Fair, Scary at the Berry, Halloween Sausalito) are marked `"provisional": true` — their 2026 details were only verified via Marin Mommies, not the organizers' own sites.

## Deliberately skipped

- **Rec-department class/catalog PDFs** — only special drop-in events are ingested, never class catalogs.
- **Facebook Events** — login-walled; skipped.
- **Macaroni Kid** — unverified for this use; skipped.
- **Marin Humane** — blocks automated fetches (403); their events page served stale December 2025 content when read via browser. No current kids events ingested.
- **Larkspur Library** — has a valid official RSS feed, but it returned zero items (2026-09-18). Nothing to ingest; re-check later.
- **San Anselmo Library** — Bilingual Spanish Storytime and Sing and Stomp are hand-maintained (`sananselmo` origin); Monday storytime is covered via the Marin Mommies refresh.
- **Belvedere Tiburon Library** — same: already covered via Marin Mommies.
- **Sausalito Library** — no machine-readable events feed found during research; nothing ingested. Revisit if a feed appears.
- **Farmers markets** — well covered by Marin Mommies; only children-specific programming would be added, none found missing.
- **Bay Area Discovery Museum** — official Goblin Jamboree dates already in `dated_events_curated.json`; no other current kids events found missing.
- **Pumpkin patches** — per standing rule, only farms with 2026 dates/hours on their own official sites are listed; none of the researched patches passed.
- **Ronnie's Awesome List / Mommy Poppins** — aggregators; used only for monitoring, never as event links.
