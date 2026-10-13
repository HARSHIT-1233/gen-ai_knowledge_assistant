
import httpx

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatMessage


class OllamaService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def chat(self, messages: list[ChatMessage]) -> str:
        url = (
            f"{self.settings.ollama_base_url.rstrip('/')}"
            "/api/chat"
        )

        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                message.model_dump() for message in messages
            ],
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        answer = data.get("message", {}).get("content")
        if not isinstance(answer, str):
            raise RuntimeError("Invalid response from Ollama")

        return answer


def get_ollama_service() -> OllamaService:
    return OllamaService()
