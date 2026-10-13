
import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.schemas.document import (
    DocumentUploadResponse,
    StoredDocument,
)
from app.services.document_ingestion import (
    DocumentIngestionService,
    get_document_ingestion_service,
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
        # Read at most one byte beyond the permitted size.
        from app.services.document_ingestion import MAX_FILE_SIZE

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


@router.get("/{document_id}", response_model=StoredDocument)
def get_document(
    document_id: str,
    service: Annotated[
        DocumentIngestionService,
        Depends(get_document_ingestion_service),
    ],
) -> StoredDocument:
    document = service.get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return document
