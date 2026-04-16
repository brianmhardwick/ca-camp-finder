from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables, seed locations on first run, and apply migrations."""
    from app.models import Location, AvailabilityLog, CheckLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _seed_locations()
    _migrate_scraper_configs()


# ReserveCA migrated to Tyler Technologies in 2025/2026.
# New API: california-rdr.prod.cali.rd12.recreation-management.tylerapp.com/rdr/search/grid
# facility_id = section-level FacilityId for search/grid API
# place_id    = park-level PlaceId for booking URLs
# unit_type_id = 0 (all types); old UnitTypeId 29 no longer valid in new system
_SEED_DATA = [
    {
        "name": "San Elijo State Beach (RV)",
        "slug": "san_elijo",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/park/709/",
        "scraper_config": '{"facility_id": 665, "unit_type_id": 0, "place_id": 709}',
    },
    {
        "name": "South Carlsbad State Beach (RV)",
        "slug": "south_carlsbad",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/park/720/",
        "scraper_config": '{"facility_id": 714, "unit_type_id": 0, "place_id": 720}',
    },
    {
        "name": "Carlsbad State Beach (RV)",
        "slug": "carlsbad",
        "scraper_type": "reserveca",
        "enabled": False,
        "booking_url": "https://www.reservecalifornia.com/park/1105/",
        "scraper_config": '{"facility_id": 1105, "unit_type_id": 0, "place_id": 1105}',
    },
    {
        "name": "Silver Strand State Beach (RV)",
        "slug": "silver_strand",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/park/715/",
        "scraper_config": '{"facility_id": 694, "unit_type_id": 0, "place_id": 715}',
    },
    {
        "name": "Crystal Pier Hotel",
        "slug": "crystal_pier",
        "scraper_type": "crystal_pier",
        "enabled": True,
        "booking_url": "https://www.crystalpier.com/reservations/",
        "scraper_config": "{}",
    },
    {
        "name": "Crystal Cove Cottages",
        "slug": "crystal_cove",
        "scraper_type": "crystal_cove",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/park/634/",
        "scraper_config": '{"facility_id": 757, "unit_type_id": 0, "place_id": 634}',
    },
    {
        "name": "San Onofre – San Mateo (RV)",
        "slug": "san_onofre_san_mateo",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/park/712/",
        "scraper_config": '{"facility_id": 685, "unit_type_id": 0, "place_id": 712}',
    },
    {
        "name": "Campland on the Bay",
        "slug": "campland",
        "scraper_type": "campland",
        "enabled": True,
        "booking_url": "https://www.campland.com/",
        "scraper_config": "{}",
    },
]

# Mapping of old (pre-Tyler migration) scraper_config to new values, keyed by slug.
_SCRAPER_CONFIG_MIGRATIONS = {
    "san_elijo":         '{"facility_id": 665, "unit_type_id": 0, "place_id": 709}',
    "south_carlsbad":    '{"facility_id": 714, "unit_type_id": 0, "place_id": 720}',
    "carlsbad":          '{"facility_id": 1105, "unit_type_id": 0, "place_id": 1105}',
    "silver_strand":     '{"facility_id": 694, "unit_type_id": 0, "place_id": 715}',
    "crystal_cove":      '{"facility_id": 757, "unit_type_id": 0, "place_id": 634}',
    "san_onofre_san_mateo": '{"facility_id": 685, "unit_type_id": 0, "place_id": 712}',
}


def _seed_locations():
    from app.models import Location

    db = SessionLocal()
    try:
        for loc_data in _SEED_DATA:
            if not db.query(Location).filter(Location.slug == loc_data["slug"]).first():
                db.add(Location(**loc_data))
        db.commit()
    finally:
        db.close()


def _migrate_scraper_configs():
    """Update existing locations to new Tyler Tech facility IDs if still on old config."""
    import json as _json
    from app.models import Location

    db = SessionLocal()
    try:
        for slug, new_config in _SCRAPER_CONFIG_MIGRATIONS.items():
            loc = db.query(Location).filter(Location.slug == slug).first()
            if not loc:
                continue
            try:
                cfg = _json.loads(loc.scraper_config)
            except Exception:
                continue
            new_cfg = _json.loads(new_config)
            if cfg.get("facility_id") != new_cfg["facility_id"]:
                loc.scraper_config = new_config
        db.commit()
    finally:
        db.close()
