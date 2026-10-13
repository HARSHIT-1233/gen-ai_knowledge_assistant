
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.schemas.knowledge import KnowledgeSource
from app.services.knowledge import get_knowledge_service
from app.services.ollama import get_ollama_service


class FakeKnowledgeService:
    async def search(self, question, top_k=4):
        return [
            KnowledgeSource(
                source_id="S1",
                document_id="00000000-0000-0000-0000-000000000001",
                filename="aws-notes.txt",
                chunk_index=0,
                score=0.87,
                text="Right-size resources and remove unused instances.",
            )
        ]


class FakeOllamaService:
    async def chat(self, messages):
        assert any(
            "[S1]" in message.content
            for message in messages
        )
        return (
            "Right-size resources and remove unused instances "
            "to reduce AWS costs [S1]."
        )


class EmptyKnowledgeService:
    async def search(self, question, top_k=4):
        return []


@pytest.fixture
def client():
    app.dependency_overrides[get_knowledge_service] = (
        lambda: FakeKnowledgeService()
    )
    app.dependency_overrides[get_ollama_service] = (
        lambda: FakeOllamaService()
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_knowledge_ask_returns_answer_and_sources(client):
    response = client.post(
        "/api/v1/knowledge/ask",
        json={
            "question": "How can I reduce AWS costs?",
            "top_k": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "[S1]" in data["answer"]
    assert data["sources"][0]["filename"] == "aws-notes.txt"
    assert data["sources"][0]["source_id"] == "S1"
    assert data["model"] == get_settings().ollama_model


def test_knowledge_ask_requires_indexed_documents():
    app.dependency_overrides[get_knowledge_service] = (
        lambda: EmptyKnowledgeService()
    )
    app.dependency_overrides[get_ollama_service] = (
        lambda: FakeOllamaService()
    )

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/knowledge/ask",
                json={"question": "How can I reduce AWS costs?"},
            )

        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_knowledge_ask_rejects_invalid_top_k(client):
    response = client.post(
        "/api/v1/knowledge/ask",
        json={
            "question": "How can I reduce AWS costs?",
            "top_k": 100,
        },
    )

    assert response.status_code == 422
