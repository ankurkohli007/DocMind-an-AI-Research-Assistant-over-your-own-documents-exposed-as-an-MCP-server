"""QA module for answering questions using retrieved context and OpenAI chat completion."""

import os
from typing import List, Tuple

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document, Query
from core.retrieval import search_chunks


# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CHAT_MODEL = "gpt-4o-mini"
MAX_CONTEXT_CHUNKS = 5
SNIPPET_LENGTH = 200


async def answer_query(question: str, db_session: AsyncSession) -> Tuple[str, List[dict]]:
    """Answer a question using retrieved document chunks and OpenAI chat completion.

    Args:
        question: User's question.
        db_session: Async database session.

    Returns:
        Tuple of (answer_text, list_of_citations).
        Each citation is a dict with: filename, snippet, similarity_score.
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    # Retrieve relevant chunks
    matches = await search_chunks(question, db_session, top_k=MAX_CONTEXT_CHUNKS)

    if not matches:
        return (
            "I don't have any documents to answer this question. Please upload a PDF first.",
            [],
        )

    # Build context from retrieved chunks
    context_parts = []
    citations = []

    for chunk, document, similarity in matches:
        context_parts.append(f"[Source: {document.filename}]\n{chunk.content}")
        # Create snippet for citation
        snippet = chunk.content[:SNIPPET_LENGTH]
        if len(chunk.content) > SNIPPET_LENGTH:
            snippet += "..."
        citations.append(
            {
                "filename": document.filename,
                "snippet": snippet,
                "similarity_score": round(similarity, 4),
            }
        )

    context = "\n\n---\n\n".join(context_parts)

    # Build the prompt
    system_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
If the context doesn't contain enough information to answer the question, say so honestly.
Do not use your general knowledge - only use the provided document excerpts.
When you reference information, cite the source filename in your answer."""

    user_prompt = f"""Context from uploaded documents:
{context}

Question: {question}

Answer the question based only on the context above. If the context doesn't contain the answer, say "I don't have enough information in the uploaded documents to answer this question." and explain what information would be needed."""

    try:
        response = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        answer = response.choices[0].message.content.strip()
        return answer, citations

    except Exception as e:
        raise ValueError(f"Failed to generate answer: {e}")


async def log_query(
    question: str, answer: str, db_session: AsyncSession
) -> Query:
    """Log a question and answer to the queries table.

    Args:
        question: User's question.
        answer: Generated answer.
        db_session: Async database session.

    Returns:
        The created Query record.
    """
    query = Query(question=question, answer=answer)
    db_session.add(query)
    await db_session.commit()
    await db_session.refresh(query)
    return query