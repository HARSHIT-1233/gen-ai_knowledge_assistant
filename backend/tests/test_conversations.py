"""
Tests for conversation CRUD and RAG-enabled message sending.
All Ollama and KnowledgeService calls are mocked.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.knowledge import KnowledgeSource
from app.services.conversation_store import (
    ConversationStore,
    get_conversation_store,
)
from app.services.knowledge import KnowledgeService, get_knowledge_service
from app.services.ollama import OllamaService, get_ollama_service


# ── Fakes ────────────────────────────────────────────────────────────


class FakeOllama:
    async def chat(self, messages):
        return "This is a mocked response."


class FakeOllamaWithRag:
    async def chat(self, messages):
        # Validate that a grounded system prompt is present.
        assert any(
            "document-grounded" in m.content
            for m in messages
            if m.role == "system"
        ), "Expected grounded system prompt when use_knowledge=True"
        return "Based on the documents [S1], the answer is yes."


class FakeKnowledgeWithResults:
    async def search(self, question, top_k=4):
        return [
            KnowledgeSource(
                source_id="S1",
                document_id="00000000-0000-0000-0000-000000000001",
                filename="notes.txt",
                chunk_index=0,
                score=0.92,
                text="This is the relevant excerpt.",
            )
        ]

    def indexed_counts_by_document(self):
        return {}


class FakeKnowledgeEmpty:
    async def search(self, question, top_k=4):
        return []

    def indexed_counts_by_document(self):
        return {}


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    return ConversationStore(data_dir=tmp_path)


@pytest.fixture
def client(store):
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_ollama_service] = lambda: FakeOllama()
    app.dependency_overrides[get_knowledge_service] = (
        lambda: FakeKnowledgeEmpty()
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _create(client, title="Test conversation"):
    r = client.post("/api/v1/conversations", json={"title": title})
    assert r.status_code == 201
    return r.json()


# ── Tests ─────────────────────────────────────────────────────────────


def test_create_conversation(client):
    data = _create(client, "My first chat")
    assert data["title"] == "My first chat"
    assert data["message_count"] == 0
    assert "id" in data


def test_list_conversations_empty(client):
    r = client.get("/api/v1/conversations")
    assert r.status_code == 200
    assert r.json()["conversations"] == []


def test_list_conversations_after_create(client):
    _create(client, "Chat A")
    _create(client, "Chat B")
    r = client.get("/api/v1/conversations")
    assert r.status_code == 200
    assert len(r.json()["conversations"]) == 2


def test_get_conversation(client):
    conv = _create(client)
    r = client.get(f"/api/v1/conversations/{conv['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == conv["id"]
    assert r.json()["messages"] == []


def test_get_missing_conversation_returns_404(client):
    r = client.get(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404


def test_send_message_general_chat(client):
    conv = _create(client)
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "Hello?", "use_knowledge": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert "mocked response" in data["answer"]
    assert data["sources"] == []
    assert len(data["messages"]) == 2  # user + assistant


def test_send_message_title_auto_set(client):
    conv = _create(client)
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "What is machine learning?"},
    )
    r = client.get(f"/api/v1/conversations/{conv['id']}")
    assert "What is machine learning" in r.json()["title"]


def test_send_message_knowledge_mode_with_sources(store):
    """use_knowledge=True triggers RAG retrieval and returns sources."""
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_ollama_service] = (
        lambda: FakeOllamaWithRag()
    )
    app.dependency_overrides[get_knowledge_service] = (
        lambda: FakeKnowledgeWithResults()
    )

    try:
        with TestClient(app) as c:
            conv = c.post(
                "/api/v1/conversations", json={"title": "RAG chat"}
            ).json()
            r = c.post(
                f"/api/v1/conversations/{conv['id']}/messages",
                json={"content": "Tell me about notes.", "use_knowledge": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert "[S1]" in data["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filename"] == "notes.txt"


def test_send_message_knowledge_mode_no_results(client):
    """use_knowledge=True with no matches falls back to plain chat."""
    conv = _create(client)
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        json={"content": "An unusual query.", "use_knowledge": True},
    )
    assert r.status_code == 200
    assert r.json()["sources"] == []


class FakeOllamaFailing:
    async def chat(self, messages):
        raise RuntimeError("model unavailable")


def test_get_conversation_invalid_id_returns_400(client):
    response = client.get("/api/v1/conversations/not-a-uuid")
    assert response.status_code == 400


def test_send_message_missing_conversation_returns_404(client):
    response = client.post(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "Hello?"},
    )
    assert response.status_code == 404


def test_model_error_does_not_persist_exchange(store):
    """A failed model call must not save a misleading exchange."""
    app.dependency_overrides[get_conversation_store] = lambda: store
    app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaFailing()
    app.dependency_overrides[get_knowledge_service] = (
        lambda: FakeKnowledgeEmpty()
    )

    try:
        with TestClient(app) as c:
            conv = c.post(
                "/api/v1/conversations", json={"title": "Broken"}
            ).json()
            response = c.post(
                f"/api/v1/conversations/{conv['id']}/messages",
                json={"content": "Will this persist?"},
            )
            history = c.get(
                f"/api/v1/conversations/{conv['id']}"
            ).json()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert history["messages"] == []


def test_delete_conversation(client):
    conv = _create(client)
    r = client.delete(f"/api/v1/conversations/{conv['id']}")
    assert r.status_code == 204

    r2 = client.get(f"/api/v1/conversations/{conv['id']}")
    assert r2.status_code == 404


def test_delete_missing_conversation_returns_404(client):
    r = client.delete(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404


def test_conversation_history_persists(client):
    """Messages sent in earlier turns appear in subsequent history."""
    conv = _create(client)
    cid = conv["id"]

    client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "First message"},
    )
    client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"content": "Second message"},
    )

    r = client.get(f"/api/v1/conversations/{cid}")
    msgs = r.json()["messages"]
    assert len(msgs) == 4  # 2 user + 2 assistant
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user", "assistant"]
