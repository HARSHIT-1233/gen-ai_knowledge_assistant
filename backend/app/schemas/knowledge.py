
from pydantic import BaseModel, Field


class IndexDocumentResponse(BaseModel):
    document_id: str
    filename: str
    indexed_chunks: int


class KnowledgeAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=8)


class KnowledgeSource(BaseModel):
    source_id: str
    document_id: str
    filename: str
    chunk_index: int
    score: float
    text: str


class KnowledgeAskResponse(BaseModel):
    answer: str
    model: str
    sources: list[KnowledgeSource]
