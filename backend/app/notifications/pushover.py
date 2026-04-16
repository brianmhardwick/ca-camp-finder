"""Pushover notification integration."""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


async def send_availability_alert(
    location_name: str,
    unit_desc: str,
    check_in_date: date,
    price: Optional[Decimal],
    booking_url: str,
) -> bool:
    """
    Send a Pushover notification for a newly found availability.
    Returns True if notification was sent successfully.
    """
    if not settings.pushover_user_key or not settings.pushover_api_token:
        logger.warning("Pushover credentials not configured — skipping notification")
        return False

    price_str = f" · ${price:.0f}/night" if price else ""
    message = f"{unit_desc}{price_str}\nCheck-in: {check_in_date.strftime('%a, %b %-d')}"

    payload = {
        "token": settings.pushover_api_token,
        "user": settings.pushover_user_key,
        "title": f"🏕 {location_name} Available!",
        "message": message,
        "url": booking_url,
        "url_title": "Book Now →",
        "priority": 1,   # high priority — bypasses quiet hours
        "sound": "bugle",
        "timestamp": int(__import__("time").time()),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(PUSHOVER_API_URL, data=payload)
            resp.raise_for_status()
            logger.info("Pushover sent for %s on %s", location_name, check_in_date)
            return True
    except Exception as e:
        logger.error("Pushover notification failed: %s", e)
        return False


async def send_batch_alert(
    location_name: str,
    new_results: list,
    booking_url: str,
) -> bool:
    """Send a single batched notification summarising all newly found units."""
    if not settings.pushover_user_key or not settings.pushover_api_token:
        return False
    if not new_results:
        return False

    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for r in new_results:
        by_date[r.check_in_date].append(r.unit_description)

    lines = []
    for d in sorted(by_date):
        units = by_date[d]
        date_str = d.strftime("%a, %b %-d")
        if len(units) <= 3:
            lines.append(f"{date_str}: {', '.join(u.split('#')[-1].strip() if '#' in u else u for u in units)}")
        else:
            sample = ", ".join(u.split('#')[-1].strip() if '#' in u else u for u in units[:3])
            lines.append(f"{date_str}: {sample} +{len(units) - 3} more")

    total = len(new_results)
    message = "\n".join(lines)

    payload = {
        "token": settings.pushover_api_token,
        "user": settings.pushover_user_key,
        "title": f"🏕 {location_name} — {total} site{'s' if total != 1 else ''} available!",
        "message": message,
        "url": booking_url,
        "url_title": "Book Now →",
        "priority": 1,
        "sound": "bugle",
        "timestamp": int(__import__("time").time()),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(PUSHOVER_API_URL, data=payload)
            resp.raise_for_status()
            logger.info("Pushover batch sent for %s (%d units)", location_name, total)
            return True
    except Exception as e:
        logger.error("Pushover batch notification failed: %s", e)
        return False


async def send_test_notification() -> bool:
    """Send a test notification to verify credentials."""
    payload = {
        "token": settings.pushover_api_token,
        "user": settings.pushover_user_key,
        "title": "CA Camp Finder — Test",
        "message": "Your beach camping monitor is up and running! 🏄",
        "sound": "bugle",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(PUSHOVER_API_URL, data=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error("Test notification failed: %s", e)
        return False
