# CA Camp Finder — Spec Audit (2026-10-21)

Read-only audit of the backend against Brian's monitoring spec (set 2026-10-20).
Code audited: `backend/app/scheduler/{windows,advance,runner}.py`, `backend/app/config.py`,
`backend/app/main.py`, `backend/app/scrapers/{reservecalifornia,crystal_pier}.py`,
`backend/app/api/admin.py`. This code is md5-identical to what runs in the Pi containers.
No code was changed.

**Spec recap**
1. Cancellation watch: arrivals mid-May–mid-Sep ONLY, concentrated on cancel-without-penalty
   deadline windows — no perpetual year-round polling.
2. Advance booking: same mid-May–mid-Sep arrival window, checked the moment each date's
   booking window opens.
3. Crystal Pier's window opens 12 months out; ReserveCA's is 6 months.
4. Offseason: periodic check-ins suffice.

---

## Item 1 — Cancellation watch: seasonal + deadline-concentrated

**What the code does**

- The main loop (`runner.py:51-83`, `get_target_dates`) computes target check-ins as the
  **next 2 weekends only** (Fri + Sat per weekend; Thu + Fri for Crystal Pier in its
  mid-Jun–Sep 3-night-minimum season, `runner.py:43-48, 71-82`). There is **no seasonal
  gate anywhere**: the same dates are polled in December as in July. Nothing in
  `runner.py`, `windows.py`, or the scrapers tests whether a target arrival falls inside
  mid-May–mid-Sep.
- Jobs run perpetually, per location (`runner.py:243-256, 258-263`), at an interval from
  `windows.py:77-84`: 15 min during "peak" windows, 60 min otherwise
  (`config.py:10-11`; `.env` confirms 60 / 15).
- The deadline-concentration half **is implemented**: `windows.py` encodes each operator's
  cancel policy and shortens the interval to 15 min on the deadline weekdays —
  CA State Parks 48-hour policy → Wed/Thu all day + Fri morning (`windows.py:26-44`);
  Crystal Pier 7-day policy → Fri/Sat (`windows.py:47-60`); Campland 72-hour policy →
  Tue/Wed (`windows.py:63-74`).
- Dead config: `scan_days_ahead = 90` (`config.py:14`) is exposed in the admin API
  (`api/admin.py:48, 58-59`) but **never consumed** by the scheduler or any scraper.
  The loop's real horizon is ~2 weekends, not 90 days.

**Match?** ❌ Partial at best. Deadline-weekday concentration: yes. Seasonal restriction
(mid-May–mid-Sep arrivals only): **absent** — the loop polls near-term weekends
year-round, which is exactly the perpetual polling the spec superseded.

**Change needed**
- Add a seasonal gate to the main loop: when today's target weekends fall outside the
  arrival season (mid-May–mid-Sep), skip checks (or drop to the Item 4 offseason cadence).
  Natural place: `get_target_dates` / `run_check_for_location` in `runner.py`, reusing the
  season definition from `advance.py:24-38` (single source of truth — see Item 2 note on
  the season end date).
- Decide and document whether "season" gates by arrival date or by calendar date —
  the current 2-weekend horizon makes them nearly equivalent in practice.
- Either wire `scan_days_ahead` into target-date generation or remove it from config/admin
  so the settings surface stops implying a 90-day scan that doesn't exist.

## Item 2 — Advance booking at window-open, same summer window

**What the code does**

- A dedicated job exists (`advance.py`): registered in `runner.py:280-291` as a
  CronTrigger **daily at 08:00 America/Los_Angeles**. Each day it computes
  `today + 6 calendar months` (`advance.py:48-58`) and only does work when that date is a
  Friday inside the season, then checks all enabled ReserveCA + Crystal Cove locations
  for Fri–Sun 2-night availability and sends one batch Pushover per location.
- The season used is **May 15 – Sep 30** (`advance.py:24-38`), not the spec's
  mid-May–**mid-Sep**. The last two "summer" Fridays (Sep 17–19 and Sep 24–26 weekends)
  are outside the spec window.
- It is a **single shot**: one check per location per open day, fired at 08:00:00 — the
  exact release moment. On scraper error it writes an `error` CheckLog and moves on
  (`advance.py`, `_check_location_advance` exception path). There is **no re-poll, no
  retry, and no catch-up**: the target is strictly *today* + 6 months, so if the 08:00
  run races the release, errors, or the app is down that morning, that weekend is never
  re-checked by this job — and at 6 months out it is far beyond the main loop's
  2-weekend horizon, so nothing else catches it either.
- Scope is Fridays only (Fri–Sun weekends), by design.

**Match?** ⚠️ Mostly, with one structural flaw. Window math and the 08:00 fire time are
right, and the calendar at `~/workspace/goals/ca-camp-finder/files/window-open-calendar-summer-2027.md`
(19 summer Fridays; first opens **Sat Nov 21, 2026**) matches this logic. But
"check the moment the window opens" is implemented as one un-retried attempt at that
moment — the known weak point Brian flagged ("sharper sniper"). Season end (Sep 30)
also overshoots the spec (mid-Sep).

**Change needed**
- Add a re-poll burst on open days: after the 08:00 fire, repeat the check every few
  minutes for the first 1–2 hours (and ideally a same-day retry on error), restricted to
  that day's target Friday. This is the single highest-value change — first window opens
  Nov 21, 2026.
- Add a next-day catch-up: if yesterday's target Friday has no successful CheckLog,
  check it today.
- Align the season end with the spec (Sep 15 vs the coded Sep 30) — one constant in
  `advance.py:25-26`, shared with the Item 1 gate.

## Item 3 — Crystal Pier 12-month window (ReserveCA 6 months)

**What the code does**

- ReserveCA 6 months: implemented correctly, with calendar-month arithmetic and
  month-end clamping (`advance.py:29-35`), covered by tests
  (`backend/tests/test_advance_booking.py`).
- Crystal Pier 12 months: **not implemented anywhere.** The advance job's location query
  filters to `scraper_type in ["reserveca", "crystal_cove"]` (`advance.py:86-90`) —
  Crystal Pier is excluded. A codebase-wide search finds no 12-month / Crystal Pier
  advance logic in any scraper or scheduler module. Crystal Pier is only ever checked
  by the last-minute loop (next 2 weekends).

**Match?** ❌ Half. The 6-month ReserveCA half matches; the Crystal Pier 12-month
advance watch — the thing that makes Crystal Pier bookable at all in summer, since its
inventory opens a year out and is gone long before the last-minute loop's horizon —
does not exist.

**Change needed**
- Add a Crystal Pier advance monitor parallel to `advance.py`: daily (or weekly)
  computation of `today + 12 months`, same summer-Friday targeting, using
  `CrystalPierScraper`, with its own Pushover path (can reuse `send_advance_alert`).
- Note the standing caveat: Crystal Pier checks only succeed from a residential IP
  (VM egress is TLS-blocked), so this job is only meaningful on the Pi instance —
  consistent with Brian's 2026-10-21 decision to keep the process on the Pi.

## Item 4 — Offseason: periodic check-ins suffice

**What the code does**

- There is **no offseason mode**. Per-location jobs poll at 15/60 min all year
  (`runner.py:243-263`, `windows.py:77-84`); the only cadence variation is the
  weekday peak logic. Nothing reduces polling outside the season, and there is no
  periodic health/self-check distinct from the polling loop itself.

**Match?** ❌ No. Offseason behavior is identical to in-season behavior minus the
weekday peaks.

**Change needed**
- When the Item 1 seasonal gate is closed, drop location jobs to a long periodic
  interval (e.g. a single daily liveness/availability sweep) instead of 15/60-min
  polling — this falls out naturally if the gate and the cadence change are implemented
  together in `runner.py`/`windows.py`.

---

## Related observations (check-cycle reliability, not spec items)

- `runner.py:127-131`: a check is logged `status="ok"` whenever the scraper returns a
  non-None result; the Crystal Pier scraper returns `[]` on several failure paths, so a
  fully-failed Crystal Pier scrape can still log "ok" with 0 units. (Known issue; the
  Aug 2026 silent-alert-death scar argues for an explicit error status when a scraper
  raises or returns its failure sentinel.)
- Because `get_target_dates` only ever looks 2 weekends out, `total_found` and alerting
  give no visibility into cancellations for weekends 3+ weeks away until they enter the
  window — acceptable for a *last-minute* watch, but worth stating since the unused
  `scan_days_ahead=90` setting suggests otherwise.

## Prioritized change list

1. **Advance re-poll burst + next-day catch-up** (`advance.py` / `runner.py:280-291`) —
   the 08:00 single shot can silently miss a whole summer weekend; first 2027-season
   window opens **Nov 21, 2026**. Highest value, deadline-driven.
2. **Crystal Pier 12-month advance monitor** (new module beside `advance.py`) —
   an entire spec item is unimplemented; without it Crystal Pier summer inventory is
   only visible after it's long gone.
3. **Seasonal gate on the main cancellation loop** (`runner.py` target dates +
   `windows.py` intervals), with the season constant unified and its end aligned to
   the spec (mid-Sep, not Sep 30).
4. **Offseason cadence** — drop to periodic check-ins when the gate is closed
   (implements Item 4; mostly a by-product of #3).
5. **Housekeeping** — wire up or remove the dead `scan_days_ahead` setting; make
   scraper failure produce an explicit `error` CheckLog instead of "ok"/0 units.
