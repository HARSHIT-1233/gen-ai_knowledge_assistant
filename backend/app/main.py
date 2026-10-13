
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
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

# Allow the local Next.js frontend to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(
    chat_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    documents_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    knowledge_router,
    prefix=settings.api_v1_prefix,
)
app.include_router(
    conversations_router,
    prefix=settings.api_v1_prefix,
)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    """Provide a simple welcome message."""
    return {
        "message": "GenAI Knowledge & Research Assistant API",
        "docs": "/docs",
        "health": "/health",
    }
