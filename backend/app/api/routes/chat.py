
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ollama import (
    OllamaService,
    get_ollama_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: OllamaService = Depends(get_ollama_service),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    try:
        answer = await service.chat(request.messages)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        logger.warning("Ollama request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Ollama is unavailable or returned an invalid response.",
        ) from exc

    return ChatResponse(
        answer=answer,
        model=settings.ollama_model,
    )
