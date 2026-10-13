
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from pypdf import PdfReader

from app.schemas.document import (
    DocumentChunk,
    DocumentUploadResponse,
    StoredDocument,
)


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MiB
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Store generated files inside backend/data/ingested.
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "ingested"


class DocumentIngestionService:
    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or DATA_DIR

    def _extract_text(
        self, filename: str, content: bytes
    ) -> tuple[str, str, int | None]:
        extension = Path(filename).suffix.lower()

        if extension == ".txt":
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    "TXT files must use UTF-8 encoding."
                ) from exc

            return text, "text/plain", None

        if extension == ".pdf":
            try:
                reader = PdfReader(BytesIO(content), strict=True)
                pages = [
                    page.extract_text() or ""
                    for page in reader.pages
                ]
            except Exception as exc:
                raise ValueError(
                    "The PDF is invalid or could not be read."
                ) from exc

            return "\n\n".join(pages), "application/pdf", len(pages)

        raise ValueError("Only PDF and TXT files are supported.")

    def _chunk_text(self, text: str) -> list[DocumentChunk]:
        chunks = []
        step = CHUNK_SIZE - CHUNK_OVERLAP

        for index, start in enumerate(range(0, len(text), step)):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end]

            if not chunk_text.strip():
                continue

            chunks.append(
                DocumentChunk(
                    index=index,
                    text=chunk_text,
                    start_char=start,
                    end_char=end,
                )
            )

            if end == len(text):
                break

        return chunks

    def ingest(
        self, filename: str, content: bytes
    ) -> DocumentUploadResponse:
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("File exceeds the 10 MiB size limit.")

        if not content:
            raise ValueError("The uploaded file is empty.")

        text, content_type, page_count = self._extract_text(
            filename, content
        )

        # Normalize line endings and excessive whitespace.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text).strip()

        if not text:
            raise ValueError(
                "No extractable text was found. "
                "Scanned PDFs require OCR, which is not supported yet."
            )

        chunks = self._chunk_text(text)
        document_id = str(uuid4())

        document = StoredDocument(
            document_id=document_id,
            filename=Path(filename).name,
            content_type=content_type,
            created_at=datetime.now(timezone.utc),
            page_count=page_count,
            character_count=len(text),
            chunks=chunks,
        )

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.storage_dir / f"{document_id}.json"
        output_path.write_text(
            json.dumps(document.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )

        return DocumentUploadResponse(
            document_id=document_id,
            filename=document.filename,
            page_count=page_count,
            character_count=len(text),
            chunk_count=len(chunks),
            preview=text[:500],
        )

    def get_document(self, document_id: str) -> StoredDocument | None:
        try:
            safe_id = str(UUID(document_id))
        except ValueError:
            return None

        path = self.storage_dir / f"{safe_id}.json"
        if not path.is_file():
            return None

        return StoredDocument.model_validate_json(
            path.read_text(encoding="utf-8")
        )


def get_document_ingestion_service() -> DocumentIngestionService:
    return DocumentIngestionService()
