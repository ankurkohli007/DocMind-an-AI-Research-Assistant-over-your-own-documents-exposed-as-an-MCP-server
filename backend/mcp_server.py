"""MCP Server for DocMind - thin client over the deployed DocMind API."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.getenv(
    "DOCMIND_API_URL",
    "https://docmind-an-ai-research-assistant-over.onrender.com",
).rstrip("/")

# Render's free tier can take a while to wake up after being idle.
TIMEOUT = httpx.Timeout(120.0)

mcp = FastMCP("docmind")


async def _request(method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.request(method, f"{API_URL}{path}", **kwargs)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def ask_documents(question: str) -> dict:
    """Ask a question and get an answer based on uploaded documents.

    Args:
        question: User's question.

    Returns:
        Dictionary with 'answer' text and 'citations' list.
    """
    return await _request("POST", "/api/v1/queries/", json={"question": question})


@mcp.tool()
async def search_documents(query: str) -> dict:
    """Find the passages in uploaded documents most relevant to a query.

    Args:
        query: Search query text.

    Returns:
        Dictionary with matching passages (filename, snippet, similarity score).
    """
    data = await _request("POST", "/api/v1/queries/", json={"question": query})
    results = data.get("citations", [])
    return {"query": query, "results": results, "count": len(results)}


@mcp.tool()
async def list_documents() -> dict:
    """List all documents that have been uploaded.

    Returns:
        Dictionary with the list of uploaded documents.
    """
    return await _request("GET", "/api/v1/documents/")


if __name__ == "__main__":
    mcp.run()