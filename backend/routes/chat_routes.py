from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.schemas import ChatRequest, ChatResponse
from services.rag_pipeline import run_rag_pipeline

router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main RAG + Memory chat endpoint.
    session_id frontend se aata hai (localStorage mein store hota hai).
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        return run_rag_pipeline(
            query      = request.query,
            session_id = request.session_id,
            db         = db,
            top_k      = request.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))