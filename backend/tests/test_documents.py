
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_ingestion import (
    DocumentIngestionService,
    get_document_ingestion_service,
)
from app.services.knowledge import (
    KnowledgeService,
    get_knowledge_service,
)


@pytest.fixture
def client(tmp_path):
    ingestion_service = DocumentIngestionService(storage_dir=tmp_path)

    knowledge_service = KnowledgeService()
    knowledge_service.document_dir = tmp_path
    knowledge_service.index_path = tmp_path / "vector_index.json"

    app.dependency_overrides[get_document_ingestion_service] = (
        lambda: ingestion_service
    )
    app.dependency_overrides[get_knowledge_service] = (
        lambda: knowledge_service
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_document_ingestion_service, None)
    app.dependency_overrides.pop(get_knowledge_service, None)


def test_upload_and_retrieve_text_document(client):
    content = (
        "Cloud cost optimization reduces waste. "
        "Monitor usage and right-size resources."
    )

    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "cloud-notes.txt",
                content.encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["filename"] == "cloud-notes.txt"
    assert data["character_count"] > 0
    assert data["chunk_count"] >= 1
    assert "Cloud cost optimization" in data["preview"]

    document_response = client.get(
        f"/api/v1/documents/{data['document_id']}"
    )

    assert document_response.status_code == 200
    stored = document_response.json()
    assert stored["document_id"] == data["document_id"]
    assert len(stored["chunks"]) == data["chunk_count"]


def test_upload_rejects_unsupported_extension(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "notes.docx",
                b"not a supported document",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": ("empty.txt", b"", "text/plain")
        },
    )

    assert response.status_code == 422


def test_missing_document_returns_404(client):
    response = client.get(
        "/api/v1/documents/"
        "00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


# ── Regression / expansion tests ─────────────────────────────────────


def test_list_documents_empty(client):
    """GET /documents on a fresh service returns an empty list."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_after_upload(client):
    """Uploaded document appears in list with indexed_chunk_count zero."""
    content = b"Retrieval-augmented generation improves factual accuracy."
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("rag-notes.txt", content, "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["document_id"]

    listing = client.get("/api/v1/documents")
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["document_id"] == doc_id
    assert items[0]["indexed_chunk_count"] == 0


def test_delete_document(client):
    """Upload → delete returns 204; subsequent GET returns 404."""
    content = b"Temporary document for deletion test."
    upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("temp.txt", content, "text/plain")},
    )
    assert upload.status_code == 201
    doc_id = upload.json()["document_id"]

    delete = client.delete(f"/api/v1/documents/{doc_id}")
    assert delete.status_code == 204

    get = client.get(f"/api/v1/documents/{doc_id}")
    assert get.status_code == 404


def test_delete_missing_document_returns_404(client):
    """DELETE on an unknown UUID returns 404."""
    response = client.delete(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


def test_malformed_document_id_returns_422(client):
    """GET with a non-UUID document_id returns 422."""
    response = client.get("/api/v1/documents/not-a-uuid")
    assert response.status_code == 422
