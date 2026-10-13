
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_ingestion import (
    DocumentIngestionService,
    get_document_ingestion_service,
)


@pytest.fixture
def client(tmp_path):
    service = DocumentIngestionService(storage_dir=tmp_path)
    app.dependency_overrides[get_document_ingestion_service] = (
        lambda: service
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_document_ingestion_service, None
    )


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
