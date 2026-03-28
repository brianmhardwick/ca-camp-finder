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
