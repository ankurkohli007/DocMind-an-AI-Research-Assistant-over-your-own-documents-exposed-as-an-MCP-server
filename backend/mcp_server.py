"""MCP Server for DocMind - exposes search and QA tools via MCP protocol."""

import sys
from pathlib import Path

# Add project root to path for core module imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document
from core.qa import answer_query
from core.retrieval import search_chunks


# Create database engine and session maker
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args={"statement_cache_size": 0},
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session():
    """Get a database session for MCP tools."""
    async with async_session_maker() as session:
        yield session


# Initialize MCP server
mcp = FastMCP("docmind")


@mcp.tool()
async def search_documents(query: str) -> dict:
    """Search for document chunks similar to the query using cosine similarity.

    Args:
        query: Search query text.

    Returns:
        Dictionary with 'results' list containing chunks with source document filename and similarity score.
    """
    async with async_session_maker() as db:
        matches = await search_chunks(query, db, top_k=5)

        results = []
        for chunk, document, similarity in matches:
            results.append({
                "chunk_id": chunk.id,
                "document_id": document.id,
                "filename": document.filename,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "similarity_score": round(similarity, 4),
            })

        return {"results": results, "count": len(results)}


@mcp.tool()
async def ask_documents(question: str) -> dict:
    """Ask a question and get an answer based on uploaded documents.

    Args:
        question: User's question.

    Returns:
        Dictionary with 'answer' text and 'citations' list.
    """
    async with async_session_maker() as db:
        answer, citations = await answer_query(question, db)

        return {
            "question": question,
            "answer": answer,
            "citations": citations,
        }


if __name__ == "__main__":
    # Run the MCP server via stdio
    mcp.run()