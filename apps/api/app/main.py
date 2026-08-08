import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.redis_client import get_redis
from app.models import User  # noqa: F401 — register models with metadata

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
