"""
Standalone ReserveCalifornia API tester.
Run from the backend/ directory: python test_reserveca_api.py

Tests the UseDirect API with far-out dates to validate:
  - Network reachability
  - Correct facility IDs
  - SleepingUnitId / UnitTypeId parameters
  - Response structure and date key format
"""
import asyncio
import json
from datetime import date, timedelta

import httpx

BASE_URL = "https://calirdr.usedirect.com/rdr/rdr/fd/camping/availability/site"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Content-Type": "application/json",
    "Referer": "https://www.reservecalifornia.com/",
    "Origin": "https://www.reservecalifornia.com",
}

LOCATIONS = [
    {"name": "San Elijo",        "facility_id": 717, "unit_type_id": 29},
    {"name": "South Carlsbad",   "facility_id": 720, "unit_type_id": 29},
    {"name": "Carlsbad",         "facility_id": 718, "unit_type_id": 29},
    {"name": "Silver Strand",    "facility_id": 595, "unit_type_id": 29},
    {"name": "San Onofre SM",    "facility_id": 686, "unit_type_id": 29},
    {"name": "Crystal Cove",     "facility_id": 728, "unit_type_id": 0},
]

# ─── Test dates: Fridays 3 and 6 months out ──────────────────────────────────
today = date.today()
# Find next Friday
days_until_friday = (4 - today.weekday()) % 7 or 7
next_friday = today + timedelta(days=days_until_friday)
test_dates = [
    next_friday + timedelta(weeks=12),   # ~3 months out
    next_friday + timedelta(weeks=24),   # ~6 months out
]

# ─── Parameter variants to probe ─────────────────────────────────────────────
# SleepingUnitId=83 is hardcoded in the scraper — test 0 vs 83 to see if it filters results
PARAM_VARIANTS = [
    {"label": "current (SleepingUnitId=83)", "SleepingUnitId": 83},
    {"label": "relaxed (SleepingUnitId=0)",  "SleepingUnitId": 0},
]


def build_payload(facility_id: int, unit_type_id: int, check_in: date, sleeping_unit_id: int) -> dict:
    check_out = check_in + timedelta(days=1)
    return {
        "FacilityId": facility_id,          # int, not str — test both
        "StartDate":  check_in.strftime("%m-%d-%Y"),
        "EndDate":    check_out.strftime("%m-%d-%Y"),
        "MinVehicleLength": 0,
        "UnitTypeId": unit_type_id,
        "WebOnly": True,
        "IsADA": False,
        "SleepingUnitId": sleeping_unit_id,
        "UnitCategoryId": 0,
    }


def count_available(data: dict, check_in: date) -> tuple[int, int]:
    """Returns (total_units, free_units) for the given check_in date."""
    units = data.get("Facility", {}).get("Units", {})
    date_key_short = f"{check_in.month}/{check_in.day}/{check_in.year}"
    date_key_pad   = check_in.strftime("%m/%d/%Y")

    total, free = 0, 0
    for unit in units.values():
        if not isinstance(unit, dict):
            continue
        total += 1
        slices = unit.get("Slices", {})
        sl = slices.get(date_key_short) or slices.get(date_key_pad)
        if sl and sl.get("IsFree"):
            free += 1
    return total, free


def inspect_response_structure(data: dict, check_in: date, facility_id: int):
    """Print a quick structural snapshot to diagnose date-key mismatches."""
    units = data.get("Facility", {}).get("Units", {})
    top_keys = list(data.keys())
    facility_keys = list(data.get("Facility", {}).keys())
    print(f"    Top-level keys:    {top_keys}")
    print(f"    Facility keys:     {facility_keys}")
    print(f"    Unit count:        {len(units)}")

    # Show slice keys from first unit to verify date format
    for uid, unit in units.items():
        if isinstance(unit, dict):
            slice_keys = list(unit.get("Slices", {}).keys())[:5]
            print(f"    Sample slice keys: {slice_keys}")
            print(f"    Expected key:      {check_in.month}/{check_in.day}/{check_in.year}")
            break
    else:
        print(f"    ⚠ No units in response — facility {facility_id} may need different params")


async def test_location(loc: dict, check_in: date):
    name        = loc["name"]
    facility_id = loc["facility_id"]
    unit_type   = loc["unit_type_id"]

    print(f"\n{'─'*60}")
    print(f"  {name} (facility={facility_id}, UnitTypeId={unit_type})")
    print(f"  Check-in: {check_in}  ({check_in.strftime('%A')})")
    print(f"{'─'*60}")

    async with httpx.AsyncClient(timeout=30) as client:
        for variant in PARAM_VARIANTS:
            payload = build_payload(facility_id, unit_type, check_in, variant["SleepingUnitId"])
            try:
                resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
                print(f"\n  [{variant['label']}]  HTTP {resp.status_code}")
                if resp.status_code != 200:
                    print(f"  Error: {resp.text[:200]}")
                    continue
                data = resp.json()
                total, free = count_available(data, check_in)
                print(f"  Units returned: {total}  |  IsFree=True: {free}")
                if total == 0 or (total > 0 and free == 0):
                    inspect_response_structure(data, check_in, facility_id)
                elif free > 0:
                    # Show a few available sites
                    units = data.get("Facility", {}).get("Units", {})
                    date_key = f"{check_in.month}/{check_in.day}/{check_in.year}"
                    date_key_pad = check_in.strftime("%m/%d/%Y")
                    shown = 0
                    for uid, unit in units.items():
                        if not isinstance(unit, dict): continue
                        sl = unit.get("Slices", {}).get(date_key) or unit.get("Slices", {}).get(date_key_pad)
                        if sl and sl.get("IsFree"):
                            print(f"  ✓ Site {unit.get('Name','?'):15s}  type={unit.get('UnitTypeName','?'):20s}  price=${sl.get('Price','?')}")
                            shown += 1
                            if shown >= 5:
                                print(f"  ... and more")
                                break
            except Exception as e:
                print(f"  [{variant['label']}]  EXCEPTION: {e}")


async def main():
    print("=" * 60)
    print("  ReserveCalifornia API Test")
    print(f"  Today: {today}")
    print("=" * 60)

    for check_in in test_dates:
        print(f"\n\n{'='*60}")
        print(f"  TEST DATE: {check_in}  ({check_in.strftime('%A, %B %d %Y')})")
        print(f"{'='*60}")
        for loc in LOCATIONS:
            await test_location(loc, check_in)

    print(f"\n\n{'='*60}")
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
