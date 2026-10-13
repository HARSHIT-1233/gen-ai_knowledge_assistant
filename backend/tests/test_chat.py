
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.chat import get_ollama_service


class FakeOllamaService:
    async def chat(self, messages):
        return "Cloud computing provides computing resources over the internet."


client = TestClient(app)


def test_chat_endpoint():
    app.dependency_overrides[get_ollama_service] = (
        lambda: FakeOllamaService()
    )

    try:
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "What is cloud computing?",
                    }
                ]
            },
        )

        assert response.status_code == 200

        data = response.json()
        assert "Cloud computing" in data["answer"]
        assert data["model"] == "qwen2.5:1.5b"
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_empty_messages():
    response = client.post(
        "/api/v1/chat",
        json={"messages": []},
    )

    assert response.status_code == 422
