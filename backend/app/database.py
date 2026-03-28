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


def _seed_locations():
    import json
    from app.models import Location

    db = SessionLocal()
    try:
        if db.query(Location).count() > 0:
            return  # already seeded

        locations = [
            Location(
                name="San Elijo State Beach (RV)",
                slug="san_elijo",
                scraper_type="reserveca",
                enabled=True,
                booking_url="https://www.reservecalifornia.com/Web/#!park/717",
                scraper_config=json.dumps({"facility_id": 717, "unit_type_id": 29}),
            ),
            Location(
                name="South Carlsbad State Beach (RV)",
                slug="south_carlsbad",
                scraper_type="reserveca",
                enabled=True,
                booking_url="https://www.reservecalifornia.com/Web/#!park/720",
                scraper_config=json.dumps({"facility_id": 720, "unit_type_id": 29}),
            ),
            Location(
                name="Carlsbad State Beach (RV)",
                slug="carlsbad",
                scraper_type="reserveca",
                enabled=True,
                booking_url="https://www.reservecalifornia.com/Web/#!park/718",
                scraper_config=json.dumps({"facility_id": 718, "unit_type_id": 29}),
            ),
            Location(
                name="Silver Strand State Beach (RV)",
                slug="silver_strand",
                scraper_type="reserveca",
                enabled=True,
                booking_url="https://www.reservecalifornia.com/Web/#!park/595",
                scraper_config=json.dumps({"facility_id": 595, "unit_type_id": 29}),
            ),
            Location(
                name="Crystal Pier Hotel",
                slug="crystal_pier",
                scraper_type="crystal_pier",
                enabled=True,
                booking_url="https://www.crystalpier.com/reservations/",
                scraper_config=json.dumps({}),
            ),
            Location(
                name="Crystal Cove Cottages",
                slug="crystal_cove",
                scraper_type="crystal_cove",
                enabled=True,
                booking_url="https://www.reservecalifornia.com/Web/#!park/728",
                scraper_config=json.dumps({"facility_id": 728, "unit_type_id": 0}),
            ),
        ]
        db.add_all(locations)
        db.commit()
    finally:
        db.close()
