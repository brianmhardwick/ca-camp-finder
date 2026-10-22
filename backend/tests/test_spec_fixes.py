"""
Tests for the 2026-10-21 spec-alignment fixes (Brian's 2026-10-20 spec):

1. Advance job re-poll burst + next-day catch-up.
2. Crystal Pier 12-month advance watch.
3. Seasonal gate on the cancellation loop (arrivals May 15 – Sep 15 only).
4. Offseason idle mode (no polling outside the season).
5. Failed Crystal Pier scrape logs an error, never "ok"/0; dead
   scan_days_ahead setting removed.
"""
import sys
import types
from datetime import date, datetime, timedelta

import pytest
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.scheduler import advance, runner
from app.scheduler.season import is_in_season

PACIFIC = pytz.timezone("America/Los_Angeles")


def _pt(y, m, d, hour=10):
    return PACIFIC.localize(datetime(y, m, d, hour, 0))


# ── Season (shared single source of truth) ────────────────────────────────────

def test_season_boundaries():
    assert is_in_season(date(2027, 5, 15)) is True
    assert is_in_season(date(2027, 5, 14)) is False
    assert is_in_season(date(2027, 9, 15)) is True
    assert is_in_season(date(2027, 9, 16)) is False
    assert is_in_season(date(2027, 1, 1)) is False
    assert is_in_season(date(2027, 7, 4)) is True


# ── Fix 2: advance targets for both booking windows ──────────────────────────

def test_advance_targets_reserveca_open_day():
    # Sat Nov 21, 2026: the May 21, 2027 Friday opens (6-month window).
    assert date(2027, 5, 21).weekday() == 4
    assert advance.get_advance_targets(date(2026, 11, 21)) == [
        ("reserveca", date(2027, 5, 21))
    ]


def test_advance_targets_crystal_pier_open_day():
    # Thu Aug 20, 2026: the Aug 20, 2027 Friday opens (12-month window).
    assert date(2027, 8, 20).weekday() == 4
    assert advance.get_advance_targets(date(2026, 8, 20)) == [
        ("crystal_pier", date(2027, 8, 20))
    ]


def test_advance_targets_none_on_ordinary_day():
    # Aug 21, 2026: +6mo is out of season, +12mo is a Saturday.
    assert advance.get_advance_targets(date(2026, 8, 21)) == []


def test_advance_targets_respect_season_end():
    # Sep 17, 2027 is a Friday but past the Sep 15 season end, so the day
    # 6 months earlier (Mar 17, 2027) must NOT produce a ReserveCA target.
    assert date(2027, 9, 17).weekday() == 4
    assert advance.get_advance_friday(date(2027, 3, 17), 6) is None


# ── Fix 1: re-poll burst gating + catch-up ────────────────────────────────────

def _stub_advance_now(monkeypatch, fixed_dt):
    def fake_now(tz=None):
        return fixed_dt

    monkeypatch.setattr(
        "app.scheduler.advance.datetime",
        type("dt", (), {"now": staticmethod(fake_now)}),
    )


def _record_check_window(monkeypatch):
    calls = []

    async def fake_check_window(window, friday):
        calls.append((window, friday))

    monkeypatch.setattr(advance, "_check_window", fake_check_window)
    return calls


@pytest.mark.asyncio
async def test_repoll_active_only_in_burst_window_on_open_days(monkeypatch):
    calls = _record_check_window(monkeypatch)

    _stub_advance_now(monkeypatch, _pt(2026, 11, 21, hour=9))
    await advance.run_advance_repoll_check()
    assert calls == [("reserveca", date(2027, 5, 21))]

    calls.clear()
    _stub_advance_now(monkeypatch, _pt(2026, 11, 21, hour=7))  # before 08:00
    await advance.run_advance_repoll_check()
    assert calls == []

    _stub_advance_now(monkeypatch, _pt(2026, 11, 21, hour=11))  # burst over
    await advance.run_advance_repoll_check()
    assert calls == []

    _stub_advance_now(monkeypatch, _pt(2026, 11, 22, hour=9))  # not an open day
    await advance.run_advance_repoll_check()
    assert calls == []


@pytest.mark.asyncio
async def test_advance_check_includes_yesterday_catchup(monkeypatch):
    calls = _record_check_window(monkeypatch)
    # Sun Nov 22, 2026: nothing opens today, but yesterday (Nov 21) was the
    # May 21, 2027 window opening — the 08:00 job must catch it up.
    _stub_advance_now(monkeypatch, _pt(2026, 11, 22, hour=8))
    await advance.run_advance_booking_check()
    assert calls == [("reserveca", date(2027, 5, 21))]


# ── Fixes 3+4: seasonal gate on the cancellation loop ─────────────────────────

def _stub_runner_now(monkeypatch, fixed_dt):
    monkeypatch.setattr(runner, "_now_pacific", lambda: fixed_dt)


def test_gate_closed_in_winter(monkeypatch):
    _stub_runner_now(monkeypatch, _pt(2026, 12, 2))  # Wednesday
    assert runner.get_target_dates("") == [
        date(2026, 12, 4), date(2026, 12, 5),
        date(2026, 12, 11), date(2026, 12, 12),
    ]
    assert runner.get_in_season_target_dates("") == []


def test_gate_open_mid_season(monkeypatch):
    _stub_runner_now(monkeypatch, _pt(2027, 7, 7))  # Wednesday
    assert runner.get_in_season_target_dates("") == [
        date(2027, 7, 9), date(2027, 7, 10),
        date(2027, 7, 16), date(2027, 7, 17),
    ]


def test_gate_filters_dates_at_season_start(monkeypatch):
    _stub_runner_now(monkeypatch, _pt(2027, 5, 12))  # Wednesday
    # Weekend 1 straddles the boundary: Fri May 14 is out, Sat May 15 is in.
    assert runner.get_in_season_target_dates("") == [
        date(2027, 5, 15), date(2027, 5, 21), date(2027, 5, 22),
    ]


def test_gate_closed_after_season_end(monkeypatch):
    _stub_runner_now(monkeypatch, _pt(2027, 9, 13))  # Monday
    # Next Friday is Sep 17 — past the Sep 15 season end.
    assert runner.get_in_season_target_dates("") == []


def test_gate_keeps_crystal_pier_summer_shape(monkeypatch):
    _stub_runner_now(monkeypatch, _pt(2027, 7, 7))
    # Crystal Pier 3-night-min season: Thu + Fri check-ins, all in season.
    assert runner.get_in_season_target_dates("crystal_pier") == [
        date(2027, 7, 8), date(2027, 7, 9),
        date(2027, 7, 15), date(2027, 7, 16),
    ]


# ── DB-backed runner tests ────────────────────────────────────────────────────

@pytest.fixture()
def db_session_factory(monkeypatch):
    from app.database import Base
    import app.models  # noqa: F401 — register tables

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("app.database.SessionLocal", factory)
    return factory


def _add_location(factory, slug="test_loc", scraper_type="reserveca"):
    from app.models import Location

    db = factory()
    try:
        loc = Location(
            name="Test Location",
            slug=slug,
            scraper_type=scraper_type,
            enabled=True,
            booking_url="https://example.com/",
            scraper_config="{}",
        )
        db.add(loc)
        db.commit()
        return loc.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_offseason_run_skips_scrape_and_writes_no_log(
    monkeypatch, db_session_factory
):
    """Fixes 3+4: outside the season a scheduled run performs no scrape and
    writes no CheckLog — the service idles."""
    from app.models import CheckLog

    loc_id = _add_location(db_session_factory)
    _stub_runner_now(monkeypatch, _pt(2026, 12, 2))  # winter

    class ExplodingScraper:
        def __init__(self, location):
            raise AssertionError("scraper must not be constructed offseason")

    monkeypatch.setattr(
        "app.scrapers.reservecalifornia.ReserveCaliforniaScraper",
        ExplodingScraper,
    )

    await runner.run_check_for_location(loc_id)

    db = db_session_factory()
    try:
        assert db.query(CheckLog).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_failed_crystal_pier_scrape_logs_error(
    monkeypatch, db_session_factory
):
    """Fix 5: a Crystal Pier scrape that fails outright produces an error
    CheckLog, never an 'ok' with 0 units."""
    from app.models import CheckLog
    from app.scrapers.base import ScraperError

    loc_id = _add_location(
        db_session_factory, slug="pier_loc", scraper_type="crystal_pier"
    )
    _stub_runner_now(monkeypatch, _pt(2027, 7, 7))  # in season

    class FailingPierScraper:
        def __init__(self, location):
            self.location = location

        async def check_availability(self, dates):
            raise ScraperError("Crystal Pier scrape failed for all 4 date(s)")

    monkeypatch.setattr(
        "app.scrapers.crystal_pier.CrystalPierScraper", FailingPierScraper
    )

    await runner.run_check_for_location(loc_id)

    db = db_session_factory()
    try:
        logs = db.query(CheckLog).all()
        assert len(logs) == 1
        assert logs[0].status == "error"
        assert logs[0].units_found == 0
    finally:
        db.close()


# ── Fix 5: Crystal Pier scraper raises on total failure ───────────────────────

class _FakeTimeoutError(Exception):
    pass


class _FakePage:
    def __init__(self, goto_outcomes):
        self._goto_outcomes = list(goto_outcomes)

    async def goto(self, url, **kwargs):
        outcome = self._goto_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome

    async def wait_for_selector(self, *args, **kwargs):
        raise _FakeTimeoutError("no availability widget")


class _FakePlaywright:
    def __init__(self, page):
        self._page = page
        self.chromium = self

    async def launch(self, **kwargs):
        return self

    async def new_context(self, **kwargs):
        return self

    async def new_page(self):
        return self._page

    async def close(self):
        pass


class _FakePlaywrightCM:
    def __init__(self, pw):
        self._pw = pw

    async def __aenter__(self):
        return self._pw

    async def __aexit__(self, *exc):
        return False


def _install_fake_playwright(monkeypatch, page):
    pw = _FakePlaywright(page)
    fake_module = types.ModuleType("playwright.async_api")
    fake_module.async_playwright = lambda: _FakePlaywrightCM(pw)
    fake_module.TimeoutError = _FakeTimeoutError
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_module)


def _pier_scraper():
    from app.scrapers.crystal_pier import CrystalPierScraper

    return CrystalPierScraper(types.SimpleNamespace(id=99))


@pytest.mark.asyncio
async def test_crystal_pier_raises_when_all_dates_fail(monkeypatch):
    from app.scrapers.base import ScraperError

    page = _FakePage([RuntimeError("net::ERR_CONNECTION_RESET")] * 2)
    _install_fake_playwright(monkeypatch, page)

    with pytest.raises(ScraperError):
        await _pier_scraper().check_availability(
            [date(2027, 7, 9), date(2027, 7, 10)]
        )


@pytest.mark.asyncio
async def test_crystal_pier_partial_failure_returns_results(monkeypatch):
    # First date fails, second loads but shows no availability widget:
    # partial failure is not a failed scrape — returns [] without raising.
    page = _FakePage([RuntimeError("boom"), None])
    _install_fake_playwright(monkeypatch, page)

    results = await _pier_scraper().check_availability(
        [date(2027, 7, 9), date(2027, 7, 10)]
    )
    assert results == []


@pytest.mark.asyncio
async def test_crystal_pier_missing_playwright_raises(monkeypatch):
    from app.scrapers.base import ScraperError

    empty_module = types.ModuleType("playwright.async_api")  # no async_playwright
    monkeypatch.setitem(sys.modules, "playwright.async_api", empty_module)

    with pytest.raises(ScraperError):
        await _pier_scraper().check_availability([date(2027, 7, 9)])


# ── Fix 5: dead scan_days_ahead setting removed ───────────────────────────────

def test_scan_days_ahead_setting_removed():
    from app.config import settings
    from app.schemas import SettingsResponse, SettingsUpdate

    assert not hasattr(settings, "scan_days_ahead")
    assert "scan_days_ahead" not in SettingsResponse.model_fields
    assert "scan_days_ahead" not in SettingsUpdate.model_fields
