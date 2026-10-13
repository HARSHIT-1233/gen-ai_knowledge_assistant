import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.schemas.document import (
    DocumentSummary,
    DocumentUploadResponse,
    StoredDocument,
)
from app.services.document_ingestion import (
    MAX_FILE_SIZE,
    DocumentIngestionService,
    get_document_ingestion_service,
)
from app.services.knowledge import (
    KnowledgeService,
    get_knowledge_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    service: Annotated[
        DocumentIngestionService,
        Depends(get_document_ingestion_service),
    ],
) -> DocumentUploadResponse:
    try:
        # Read at most one byte beyond the limit to detect oversized files.
        content = await file.read(MAX_FILE_SIZE + 1)
        return service.ingest(file.filename or "", content)

    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            if message.startswith("Only PDF and TXT")
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=message) from exc

    finally:
        await file.close()


@router.get("", response_model=list[DocumentSummary])
def list_documents(
    service: Annotated[
        DocumentIngestionService,
        Depends(get_document_ingestion_service),
    ],
    knowledge: Annotated[
        KnowledgeService,
        Depends(get_knowledge_service),
    ],
) -> list[DocumentSummary]:
    indexed_counts = knowledge.indexed_counts_by_document()

    return [
        DocumentSummary(
            document_id=doc.document_id,
            filename=doc.filename,
            content_type=doc.content_type,
            created_at=doc.created_at,
            page_count=doc.page_count,
            character_count=doc.character_count,
            chunk_count=len(doc.chunks),
            indexed_chunk_count=indexed_counts.get(doc.document_id, 0),
        )
        for doc in service.list_documents()
    ]


@router.get("/{document_id}", response_model=StoredDocument)
def get_document(
    document_id: UUID,
    service: Annotated[
        DocumentIngestionService,
        Depends(get_document_ingestion_service),
    ],
) -> StoredDocument:
    document = service.get_document(str(document_id))

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    service: Annotated[
        DocumentIngestionService,
        Depends(get_document_ingestion_service),
    ],
    knowledge: Annotated[
        KnowledgeService,
        Depends(get_knowledge_service),
    ],
) -> None:
    document = service.get_document(str(document_id))

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Remove indexed chunks before deleting the source document so we
    # never leave orphaned vectors behind. If the index is unreadable we
    # abort rather than silently leaving inconsistent state.
    try:
        knowledge.delete_document_vectors(document.document_id)
    except RuntimeError as exc:
        logger.error(
            "Aborting deletion of %s: vector index unreadable",
            document.document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The vector index is unreadable, so the document was "
                "not deleted. Remove backend/data/vector_index.json and retry."
            ),
        ) from exc

    if not service.delete_document(document.document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
