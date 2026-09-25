"""Document ingestion pipeline.

Pipeline:
    PDF -> text extraction -> chunking -> OpenAI embeddings -> PostgreSQL
"""

import re
from pathlib import Path
from typing import List, Tuple

import asyncpg
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Document, Chunk

from core.embeddings import get_embedding

from pgvector.asyncpg import register_vector


# ---------------------------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from all pages of a PDF."""

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}")

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            raise ValueError(
                f"Failed to extract text from PDF page {page_number}: {e}"
            )

        if text.strip():
            pages.append(text)

    full_text = "\n\n".join(pages)

    # Normalize whitespace while preserving paragraph breaks.
    full_text = re.sub(r"[ \t]+", " ", full_text)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = full_text.strip()

    if not full_text:
        raise ValueError(
            "No text could be extracted from the PDF. "
            "The PDF may contain scanned images instead of selectable text."
        )

    return full_text


# ---------------------------------------------------------------------------
# TEXT CHUNKING
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> List[str]:
    """Split text into overlapping chunks.

    Args:
        text: Full document text.
        chunk_size: Approximate maximum characters per chunk.
        chunk_overlap: Characters shared between consecutive chunks.

    Returns:
        List of non-empty text chunks.
    """

    if not text or not text.strip():
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        # Try to end on a natural boundary.
        if end < text_length:
            boundary_candidates = [
                text.rfind(". ", start, end),
                text.rfind("? ", start, end),
                text.rfind("! ", start, end),
                text.rfind("\n", start, end),
                text.rfind(" ", start, end),
            ]

            best_boundary = max(boundary_candidates)

            # Only use the boundary if it isn't too close to the
            # beginning of the chunk.
            if best_boundary > start + (chunk_size * 0.5):
                end = best_boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - chunk_overlap

        # Safety check to prevent an infinite loop.
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


# ---------------------------------------------------------------------------
# DOCUMENT INGESTION
# ---------------------------------------------------------------------------

async def ingest_document(
    file_path: str,
    db_session: AsyncSession,
    original_filename: str = None,
) -> Tuple[Document, List[Chunk]]:
    """Ingest a PDF document.

    Steps:
        1. Extract text from PDF.
        2. Split text into chunks.
        3. Generate an OpenAI embedding for each chunk.
        4. Insert document into PostgreSQL.
        5. Insert chunks and embeddings into PostgreSQL.

    Note:
        db_session is currently kept in the function signature because
        documents.py passes the FastAPI SQLAlchemy session. The actual
        database writes below use asyncpg, matching the existing implementation.
    """

    # -----------------------------------------------------------------------
    # 1. Extract text
    # -----------------------------------------------------------------------

    text = extract_text_from_pdf(file_path)

    # -----------------------------------------------------------------------
    # 2. Split text into chunks
    # -----------------------------------------------------------------------

    text_chunks = chunk_text(text)

    if not text_chunks:
        raise ValueError("No chunks generated from document")

    # -----------------------------------------------------------------------
    # 3. Generate embeddings
    # -----------------------------------------------------------------------

    embeddings: List[List[float]] = []

    for index, chunk_text_content in enumerate(text_chunks):
        try:
            embedding = await get_embedding(chunk_text_content)
            embeddings.append(embedding)
        except Exception as e:
            raise ValueError(
                f"Failed to generate embedding for chunk {index}: {e}"
            )

    # -----------------------------------------------------------------------
    # 4. Database connection
    # -----------------------------------------------------------------------

    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )

    conn = await asyncpg.connect(
        db_url,
        ssl=False,
        timeout=120,
        statement_cache_size=0,
    )
    await register_vector(conn)

    chunks: List[Chunk] = []

    try:
        async with conn.transaction():

            # ---------------------------------------------------------------
            # Insert document
            # ---------------------------------------------------------------

            filename = original_filename or Path(file_path).name

            document_id = await conn.fetchval(
                """
                INSERT INTO documents (filename)
                VALUES ($1)
                RETURNING id
                """,
                filename,
            )

            # ---------------------------------------------------------------
            # Insert chunks
            # ---------------------------------------------------------------

            insert_rows = [
                (document_id, chunk_text_content, embedding, idx)
                for idx, (chunk_text_content, embedding) in enumerate(
                    zip(text_chunks, embeddings)
                )
            ]

            await conn.executemany(
                """
                INSERT INTO chunks (document_id, content, embedding, chunk_index)
                VALUES ($1, $2, $3, $4)
                """,
                insert_rows,
            )

            inserted_rows = await conn.fetch(
                """
                SELECT id, chunk_index
                FROM chunks
                WHERE document_id = $1
                ORDER BY chunk_index
                """,
                document_id,
            )

            id_by_index = {row["chunk_index"]: row["id"] for row in inserted_rows}

            for idx, (chunk_text_content, embedding) in enumerate(
                zip(text_chunks, embeddings)
            ):
                chunk = Chunk(
                    id=id_by_index[idx],
                    document_id=document_id,
                    content=chunk_text_content,
                    embedding=embedding,
                    chunk_index=idx,
                )
                chunks.append(chunk)

            # ---------------------------------------------------------------
            # Fetch inserted document
            # ---------------------------------------------------------------

            document_row = await conn.fetchrow(
                """
                SELECT id, filename, uploaded_at
                FROM documents
                WHERE id = $1
                """,
                document_id,
            )

            if not document_row:
                raise ValueError(
                    f"Failed to retrieve inserted document {document_id}"
                )

            document = Document(
                id=document_row["id"],
                filename=document_row["filename"],
                uploaded_at=document_row["uploaded_at"],
            )

    finally:
        await conn.close()

    return document, chunks
