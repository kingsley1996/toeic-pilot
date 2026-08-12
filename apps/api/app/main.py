import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401 — registers every table on Base.metadata
from app.api.routes import (
    admin,
    admin_ai,
    admin_tests,
    attempt,
    auth,
    coach,
    health,
    learning,
    media,
    practice,
    profile,
)
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Alembic owns the schema everywhere except local development, where
    # create_all keeps a throwaway database usable without running migrations.
    # Leaving it on elsewhere would let the app invent a schema that silently
    # diverges from the migration history.
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("schema_created_from_metadata", extra={"environment": settings.environment})
    else:
        logger.info("schema_managed_by_alembic", extra={"environment": settings.environment})
    try:
        get_redis().ping()
    except redis.ConnectionError:
        logger.warning("redis_unavailable_at_startup")
    yield


app = FastAPI(
    title="TOEIC Pilot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(learning.router, prefix="/api/v1")
app.include_router(practice.router, prefix="/api/v1")
app.include_router(attempt.router, prefix="/api/v1")
app.include_router(coach.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(admin_tests.router, prefix="/api/v1")
app.include_router(admin_ai.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")

# Development only. Everywhere else audio is served from the object store or CDN
# named by AUDIO_PUBLIC_BASE_URL, and the API never sees the request — routing it
# through here would cost the bandwidth twice and, more importantly, break range
# requests, which is what lets a learner scrub through a listening clip.
if settings.environment == "development":
    # StaticFiles refuses to start on a missing directory, and this one is
    # gitignored: a fresh clone that has not run the content pipeline yet would
    # otherwise fail to boot the API at all.
    settings.media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
    # Đường NHẬN file của driver local, đứng thay nhà cung cấp khi chạy máy mình.
    # Cùng điều kiện với mount ở trên, và vì cùng một lý do: ở production file đi
    # thẳng tới Cloudinary/R2 và không byte nào chạy qua tiến trình này.
    app.include_router(media.local_upload_router)
