
from datetime import datetime

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    index: int
    text: str
    start_char: int
    end_char: int


class StoredDocument(BaseModel):
    document_id: str
    filename: str
    content_type: str
    created_at: datetime
    page_count: int | None
    character_count: int
    chunks: list[DocumentChunk]


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int | None
    character_count: int
    chunk_count: int
    preview: str
