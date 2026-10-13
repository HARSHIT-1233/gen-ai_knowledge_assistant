"""Regression tests for document deletion and vector-index consistency.

These tests use temporary directories only and never touch real data.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_ingestion import (
    MAX_FILE_SIZE,
    DocumentIngestionService,
    get_document_ingestion_service,
)
from app.services.knowledge import KnowledgeService, get_knowledge_service


@pytest.fixture
def ctx(tmp_path):
    ingestion = DocumentIngestionService(storage_dir=tmp_path)
    knowledge = KnowledgeService()
    knowledge.document_dir = tmp_path
    knowledge.index_path = tmp_path / "vector_index.json"

    app.dependency_overrides[get_document_ingestion_service] = (
        lambda: ingestion
    )
    app.dependency_overrides[get_knowledge_service] = lambda: knowledge

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            knowledge=knowledge,
            ingestion=ingestion,
            tmp_path=tmp_path,
        )

    app.dependency_overrides.pop(get_document_ingestion_service, None)
    app.dependency_overrides.pop(get_knowledge_service, None)


def _upload(client, name="notes.txt", content=b"Some indexable content."):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (name, content, "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _write_index(path, entries):
    path.write_text(json.dumps(entries), encoding="utf-8")


def test_delete_document_removes_associated_vectors(ctx):
    doc_id = _upload(ctx.client)
    other_id = "11111111-1111-1111-1111-111111111111"

    _write_index(
        ctx.knowledge.index_path,
        [
            {"document_id": doc_id, "chunk_index": 0, "text": "a"},
            {"document_id": doc_id, "chunk_index": 1, "text": "b"},
            {"document_id": other_id, "chunk_index": 0, "text": "c"},
        ],
    )

    delete = ctx.client.delete(f"/api/v1/documents/{doc_id}")
    assert delete.status_code == 204

    remaining = json.loads(ctx.knowledge.index_path.read_text("utf-8"))
    assert [entry["document_id"] for entry in remaining] == [other_id]


def test_list_reports_indexed_chunk_count(ctx):
    doc_id = _upload(ctx.client)
    _write_index(
        ctx.knowledge.index_path,
        [
            {"document_id": doc_id, "chunk_index": 0, "text": "a"},
            {"document_id": doc_id, "chunk_index": 1, "text": "b"},
        ],
    )

    listing = ctx.client.get("/api/v1/documents")
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["indexed_chunk_count"] == 2
    assert items[0]["chunk_count"] == 1


def test_list_skips_malformed_persisted_records(ctx):
    doc_id = _upload(ctx.client)
    (ctx.tmp_path / "broken.json").write_text("{ not valid json", encoding="utf-8")

    listing = ctx.client.get("/api/v1/documents")
    assert listing.status_code == 200
    ids = [item["document_id"] for item in listing.json()]
    assert ids == [doc_id]


def test_list_tolerates_corrupt_vector_index(ctx):
    _upload(ctx.client)
    ctx.knowledge.index_path.write_text("not json", encoding="utf-8")

    listing = ctx.client.get("/api/v1/documents")
    assert listing.status_code == 200
    assert listing.json()[0]["indexed_chunk_count"] == 0


def test_upload_rejects_oversized_file(ctx):
    oversized = b"a" * (MAX_FILE_SIZE + 1)
    response = ctx.client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.txt", oversized, "text/plain")},
    )
    assert response.status_code == 422


def test_delete_aborts_when_index_is_corrupt(ctx):
    doc_id = _upload(ctx.client)
    ctx.knowledge.index_path.write_text("not json", encoding="utf-8")

    delete = ctx.client.delete(f"/api/v1/documents/{doc_id}")
    assert delete.status_code == 500

    # The document must still exist so no inconsistent state is created.
    assert ctx.client.get(f"/api/v1/documents/{doc_id}").status_code == 200
