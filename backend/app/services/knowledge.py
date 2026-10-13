import json
import logging
import math
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from app.core.config import Settings, get_settings
from app.schemas.document import StoredDocument
from app.schemas.knowledge import KnowledgeSource


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = BACKEND_DIR / "data" / "ingested"
INDEX_PATH = BACKEND_DIR / "data" / "vector_index.json"


class KnowledgeService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.document_dir = DOCUMENT_DIR
        self.index_path = INDEX_PATH

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings using Ollama's local embedding API."""
        url = (
            f"{self.settings.ollama_base_url.rstrip('/')}"
            "/api/embed"
        )

        embeddings: list[list[float]] = []

        # Batch inputs to limit memory usage for large documents.
        async with httpx.AsyncClient(timeout=120.0) as client:
            for start in range(0, len(texts), 32):
                batch = texts[start : start + 32]
                response = await client.post(
                    url,
                    json={
                        "model": self.settings.ollama_embed_model,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                result = response.json().get("embeddings")

                if (
                    not isinstance(result, list)
                    or len(result) != len(batch)
                    or any(
                        not isinstance(vector, list)
                        or not vector
                        or not all(
                            isinstance(value, (int, float))
                            and math.isfinite(value)
                            for value in vector
                        )
                        for vector in result
                    )
                ):
                    raise RuntimeError(
                        "Ollama returned invalid embeddings."
                    )

                embeddings.extend(result)

        return embeddings

    def _read_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []

        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("The local vector index is invalid.") from exc

        if not isinstance(data, list):
            raise RuntimeError("The local vector index is invalid.")

        return data

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(entries, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.index_path)

    def delete_document_vectors(self, document_id: str) -> int:
        try:
            safe_id = str(UUID(document_id))
        except (ValueError, TypeError, AttributeError):
            return 0

        entries = self._read_index()
        retained = [
            entry
            for entry in entries
            if entry.get("document_id") != safe_id
        ]

        removed_count = len(entries) - len(retained)

        if removed_count:
            self._write_index(retained)

        return removed_count

    def indexed_counts_by_document(self) -> dict[str, int]:
        """Return a mapping of document_id → number of indexed chunks."""
        try:
            entries = self._read_index()
        except RuntimeError as exc:
            # A corrupt index should not break document listing.
            logger.warning("Could not read vector index: %s", exc)
            return {}

        counts: dict[str, int] = {}
        for entry in entries:
            doc_id = entry.get("document_id")
            if isinstance(doc_id, str):
                counts[doc_id] = counts.get(doc_id, 0) + 1
        return counts

    async def index_document(
        self, document_id: str
    ) -> dict[str, Any] | None:
        # Restrict IDs to UUIDs so they cannot become filesystem paths.
        try:
            safe_id = str(UUID(document_id))
        except ValueError:
            return None

        path = self.document_dir / f"{safe_id}.json"
        if not path.is_file():
            return None

        document = StoredDocument.model_validate_json(
            path.read_text(encoding="utf-8")
        )

        if not document.chunks:
            raise ValueError("The document has no text chunks.")

        texts = [chunk.text for chunk in document.chunks]
        vectors = await self._embed(texts)

        entries = [
            {
                "document_id": document.document_id,
                "filename": document.filename,
                "chunk_index": chunk.index,
                "text": chunk.text,
                "embedding": vector,
                "embedding_model": self.settings.ollama_embed_model,
            }
            for chunk, vector in zip(
                document.chunks, vectors, strict=True
            )
        ]

        current = self._read_index()

        # Replace old vectors for this document when re-indexing.
        current = [
            entry
            for entry in current
            if entry.get("document_id") != safe_id
        ]
        current.extend(entries)
        self._write_index(current)

        return {
            "document_id": document.document_id,
            "filename": document.filename,
            "indexed_chunks": len(entries),
        }

    @staticmethod
    def _cosine(
        left: list[float], right: list[float]
    ) -> float:
        if len(left) != len(right):
            raise ValueError("Embedding dimensions do not match.")

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot / (left_norm * right_norm)

    async def search(
        self, question: str, top_k: int = 4
    ) -> list[KnowledgeSource]:
        entries = self._read_index()
        if not entries:
            return []

        query_vector = (await self._embed([question]))[0]
        scored: list[tuple[float, dict[str, Any]]] = []

        for entry in entries:
            if entry.get("embedding_model") != (
                self.settings.ollama_embed_model
            ):
                continue

            vector = entry.get("embedding")
            if not isinstance(vector, list):
                continue

            try:
                score = self._cosine(query_vector, vector)
            except ValueError:
                # Skip incompatible vectors, such as vectors from
                # a different embedding model.
                continue

            scored.append((score, entry))

        scored.sort(key=lambda item: item[0], reverse=True)

        # Keep only chunks that meet the configured relevance threshold.
        threshold = self.settings.knowledge_similarity_threshold
        relevant = [
            (score, entry)
            for score, entry in scored
            if score >= threshold
        ]

        return [
            KnowledgeSource(
                source_id=f"S{rank}",
                document_id=entry["document_id"],
                filename=entry["filename"],
                chunk_index=entry["chunk_index"],
                score=score,
                text=entry["text"],
            )
            for rank, (score, entry) in enumerate(
                relevant[:top_k], start=1
            )
        ]


def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
