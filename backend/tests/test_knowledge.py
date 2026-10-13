
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.schemas.knowledge import KnowledgeSource
from app.services.knowledge import get_knowledge_service
from app.services.ollama import get_ollama_service

from app.core.config import Settings
from app.services.document_ingestion import DocumentIngestionService
from app.services.knowledge import KnowledgeService

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


def test_knowledge_ask_handles_no_relevant_sources():
    app.dependency_overrides[get_knowledge_service] = (
        lambda: EmptyKnowledgeService()
    )

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/knowledge/ask",
                json={
                    "question": "What are the advantages of requirements engineering?"
                },
            )

        assert response.status_code == 200

        data = response.json()
        assert data["sources"] == []
        assert "couldn't find sufficiently relevant information" in (
            data["answer"].lower()
        )
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

def test_search_filters_chunks_below_threshold_sync(
    tmp_path, monkeypatch
):
    import asyncio
    import json

    settings = Settings(
        knowledge_similarity_threshold=0.7,
        ollama_embed_model="nomic-embed-text",
    )
    service = KnowledgeService(settings=settings)
    service.index_path = tmp_path / "vector_index.json"

    entries = [
        {
            "document_id": "doc-1",
            "filename": "notes.txt",
            "chunk_index": 0,
            "text": "Highly relevant passage",
            "embedding": [1.0, 0.0],
            "embedding_model": "nomic-embed-text",
        },
        {
            "document_id": "doc-2",
            "filename": "other.txt",
            "chunk_index": 0,
            "text": "Weakly relevant passage",
            "embedding": [0.5, 0.8660254],
            "embedding_model": "nomic-embed-text",
        },
    ]

    service.index_path.write_text(
        json.dumps(entries), encoding="utf-8"
    )

    async def fake_embed(texts):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(service, "_embed", fake_embed)

    results = asyncio.run(
        service.search("test question", top_k=4)
    )

    assert len(results) == 1
    assert results[0].text == "Highly relevant passage"
    assert results[0].score >= 0.7


def _knowledge_service(tmp_path):
    service = KnowledgeService()
    service.document_dir = tmp_path
    service.index_path = tmp_path / "vector_index.json"
    return service


def test_index_document_endpoint_success(tmp_path, monkeypatch):
    ingestion = DocumentIngestionService(storage_dir=tmp_path)
    uploaded = ingestion.ingest(
        "notes.txt", b"Retrieval augmented generation improves accuracy."
    )

    service = _knowledge_service(tmp_path)

    async def fake_embed(texts):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(service, "_embed", fake_embed)

    app.dependency_overrides[get_knowledge_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/knowledge/index/{uploaded.document_id}"
            )
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)

    assert response.status_code == 200
    assert response.json()["indexed_chunks"] == uploaded.chunk_count


def test_index_missing_document_returns_404(tmp_path):
    app.dependency_overrides[get_knowledge_service] = (
        lambda: _knowledge_service(tmp_path)
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/knowledge/index/"
                "00000000-0000-0000-0000-000000000000"
            )
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)

    assert response.status_code == 404


def test_index_invalid_document_id_returns_404(tmp_path):
    app.dependency_overrides[get_knowledge_service] = (
        lambda: _knowledge_service(tmp_path)
    )
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/knowledge/index/not-a-uuid")
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)

    assert response.status_code == 404


def test_index_embedding_failure_returns_503(tmp_path, monkeypatch):
    ingestion = DocumentIngestionService(storage_dir=tmp_path)
    uploaded = ingestion.ingest("notes.txt", b"Some text to embed.")

    service = _knowledge_service(tmp_path)

    async def failing_embed(texts):
        raise RuntimeError("Ollama is down")

    monkeypatch.setattr(service, "_embed", failing_embed)

    app.dependency_overrides[get_knowledge_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/knowledge/index/{uploaded.document_id}"
            )
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)

    assert response.status_code == 503