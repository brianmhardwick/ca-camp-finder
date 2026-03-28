import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.database import init_db
    from app.scheduler.runner import start_scheduler

    logger.info("Initialising database...")
    init_db()

    logger.info("Starting availability scheduler...")
    start_scheduler()

    yield

    # Shutdown
    from app.scheduler.runner import stop_scheduler
    stop_scheduler()
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="CA Camp Finder",
    description="Monitors late cancellations at San Diego beach campgrounds and nearby hotels",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # nginx proxies in prod; wildcard fine here
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import locations, logs, admin  # noqa: E402

app.include_router(locations.router)
app.include_router(logs.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"service": "ca-camp-finder-backend", "status": "ok"}
