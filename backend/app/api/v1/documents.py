import sys
import tempfile
from pathlib import Path

# Add project root to path for core module
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Document
from core.ingestion import ingest_document

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc())
    )
    documents = result.scalars().all()
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in documents
        ]
    }


@router.post("/")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload and ingest a PDF document."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF files are accepted.",
        )

    # Validate content type
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF files are accepted.",
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        try:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Empty file uploaded")

            tmp.write(content)
            tmp_path = tmp.name
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    # Process the document
    try:
        document, chunks = await ingest_document(tmp_path, db, original_filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {e}")
    finally:
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "document_id": document.id,
        "filename": document.filename,
        "chunks_created": len(chunks),
        "message": "Document uploaded and ingested successfully",
    }


@router.get("/{document_id}")
async def get_document(document_id: int):
    return {"document_id": document_id}


@router.delete("/{document_id}")
async def delete_document(document_id: int):
    return {"message": "Document deleted"}