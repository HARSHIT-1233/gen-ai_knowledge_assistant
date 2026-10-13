
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging_config import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.environment,
    )
    yield
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for a document-grounded GenAI "
        "knowledge and research assistant."
    ),
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    """Provide a simple welcome message."""
    return {
        "message": "GenAI Knowledge & Research Assistant API",
        "docs": "/docs",
        "health": "/health",
    }
