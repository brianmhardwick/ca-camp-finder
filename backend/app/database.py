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
    """Create all tables and seed locations on first run."""
    from app.models import Location, AvailabilityLog, CheckLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _seed_locations()


_SEED_DATA = [
    {
        "name": "San Elijo State Beach (RV)",
        "slug": "san_elijo",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/717",
        "scraper_config": '{"facility_id": 717, "unit_type_id": 29}',
    },
    {
        "name": "South Carlsbad State Beach (RV)",
        "slug": "south_carlsbad",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/720",
        "scraper_config": '{"facility_id": 720, "unit_type_id": 29}',
    },
    {
        "name": "Carlsbad State Beach (RV)",
        "slug": "carlsbad",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/718",
        "scraper_config": '{"facility_id": 718, "unit_type_id": 29}',
    },
    {
        "name": "Silver Strand State Beach (RV)",
        "slug": "silver_strand",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/595",
        "scraper_config": '{"facility_id": 595, "unit_type_id": 29}',
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
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/728",
        "scraper_config": '{"facility_id": 728, "unit_type_id": 0}',
    },
    {
        "name": "San Onofre – San Mateo (RV)",
        "slug": "san_onofre_san_mateo",
        "scraper_type": "reserveca",
        "enabled": True,
        "booking_url": "https://www.reservecalifornia.com/Web/#!park/618",
        "scraper_config": '{"facility_id": 618, "unit_type_id": 29}',
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
