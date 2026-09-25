from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from core.qa import answer_query, log_query

router = APIRouter(prefix="/api/v1/queries", tags=["queries"])


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[dict]


@router.post("/", response_model=QueryResponse)
async def ask_question(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    """Ask a question and get an answer based on uploaded documents."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        answer, citations = await answer_query(request.question, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {e}")

    # Log the query
    try:
        await log_query(request.question, answer, db)
    except Exception:
        # Don't fail the request if logging fails
        pass

    return QueryResponse(
        question=request.question,
        answer=answer,
        citations=citations,
    )