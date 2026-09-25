"""Retrieval module for searching similar chunks using pgvector cosine similarity."""

from typing import List, Tuple

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from core.embeddings import get_embedding


async def search_chunks(
    query: str, db_session: AsyncSession, top_k: int = 5
) -> List[Tuple[Chunk, Document, float]]:
    """Search for chunks similar to the query using cosine similarity.

    Args:
        query: Search query text.
        db_session: Async database session.
        top_k: Number of top results to return.

    Returns:
        List of tuples (Chunk, Document, similarity_score) ordered by similarity (highest first).
    """
    # Generate embedding for the query
    query_embedding = await get_embedding(query)

    # Use pgvector's cosine distance operator (<=>) for similarity search
    # cosine_distance = 1 - cosine_similarity, so we order by distance ASC (similarity DESC)
    stmt = (
        select(
            Chunk,
            Document,
            Chunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    result = await db_session.execute(stmt)
    rows = result.all()

    for chunk, document, distance in rows:
        print("\n--- RETRIEVED CHUNK ---")
        print("Document:", document.filename)
        print("Chunk index:", chunk.chunk_index)
        print("Distance:", float(distance))
        print("Similarity:", 1.0 - float(distance))
        print("Content:", chunk.content[:1000])


    # Convert distance to similarity score (1 - distance)
    matches = []
    for chunk, document, distance in rows:
        similarity = 1.0 - float(distance)
        matches.append((chunk, document, similarity))

    return matches