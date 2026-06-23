"""
memory_routes.py
Chat history aur user memory ke liye API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import ChatSession, ChatMessage, UserMemory
from models.schemas import ChatSessionOut, ChatMessageOut, UserMemoryOut

router = APIRouter(tags=["Memory"])


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Ek session ke saare messages return karo (chat history reload ke liye)."""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages


@router.get("/sessions/{session_id}/memory", response_model=list[UserMemoryOut])
def get_session_memory(session_id: str, db: Session = Depends(get_db)):
    """Session ki user preferences return karo."""
    memories = (
        db.query(UserMemory)
        .filter(UserMemory.session_id == session_id)
        .all()
    )
    return memories


@router.delete("/sessions/{session_id}/memory")
def clear_session_memory(session_id: str, db: Session = Depends(get_db)):
    """Session ki saari preferences delete karo."""
    db.query(UserMemory).filter(UserMemory.session_id == session_id).delete()
    db.commit()
    return {"message": "Memory cleared"}


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Single session detail."""
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session