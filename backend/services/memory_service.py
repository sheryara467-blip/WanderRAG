"""
memory_service.py
Short-term aur long-term memory manage karta hai.

Short-term:  Last N messages (sliding window)
Long-term:   User preferences jo conversations se seekhe jaate hain
"""

import json
import uuid
from datetime import datetime, timezone

from groq import Groq
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import ChatSession, ChatMessage, UserMemory

settings = get_settings()

# ── Constants ──────────────────────────────────────────────
SHORT_TERM_WINDOW   = 6    # Last kitne messages LLM ko dikhao
SUMMARIZE_AFTER     = 12   # Itne messages ke baad summarize karo
MAX_MEMORY_KEYS     = 10   # Ek session mein max kitni preferences


# ===========================================================================
# SESSION MANAGEMENT
# ===========================================================================

def get_or_create_session(session_id: str, db: Session) -> ChatSession:
    """Session dhundo ya banao."""
    session = db.get(ChatSession, session_id)
    if not session:
        session = ChatSession(
            id         = session_id,
            title      = "New Chat",
            created_at = datetime.now(timezone.utc),
            updated_at = datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def update_session_title(session_id: str, first_message: str, db: Session):
    """Pehle message se session ka title set karo."""
    session = db.get(ChatSession, session_id)
    if session and session.title == "New Chat":
        # Title = pehle 50 characters of first message
        session.title = first_message[:50] + ("..." if len(first_message) > 50 else "")
        session.updated_at = datetime.now(timezone.utc)
        db.commit()


# ===========================================================================
# MESSAGE STORAGE
# ===========================================================================

def save_message(
    session_id: str,
    role:       str,
    content:    str,
    db:         Session,
    sources:    list = None,
) -> ChatMessage:
    """Ek message save karo aur session update karo."""
    msg = ChatMessage(
        id           = str(uuid.uuid4()),
        session_id   = session_id,
        role         = role,
        content      = content,
        sources_json = json.dumps(sources or []),
        created_at   = datetime.now(timezone.utc),
    )
    db.add(msg)

    # Session updated_at refresh karo
    session = db.get(ChatSession, session_id)
    if session:
        session.updated_at = datetime.now(timezone.utc)

    db.commit()
    return msg


def get_recent_messages(session_id: str, db: Session, limit: int = SHORT_TERM_WINDOW) -> list[dict]:
    """
    Last N messages return karo LLM ke liye.
    Format: [{"role": "user", "content": "..."}, ...]
    """
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    # Reverse karo taake chronological order ho
    messages = list(reversed(messages))

    return [{"role": m.role, "content": m.content} for m in messages]


def get_message_count(session_id: str, db: Session) -> int:
    """Session mein total messages count karo."""
    return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()


# ===========================================================================
# LONG-TERM MEMORY — User Preferences
# ===========================================================================

def save_user_memory(session_id: str, key: str, value: str, db: Session, confidence: str = "high"):
    """
    User preference save ya update karo.
    Agar already exist karta hai toh update karo.
    """
    existing = (
        db.query(UserMemory)
        .filter(UserMemory.session_id == session_id, UserMemory.key == key)
        .first()
    )

    if existing:
        existing.value      = value
        existing.confidence = confidence
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(UserMemory(
            id         = str(uuid.uuid4()),
            session_id = session_id,
            key        = key,
            value      = value,
            confidence = confidence,
            updated_at = datetime.now(timezone.utc),
        ))

    db.commit()


def get_user_memories(session_id: str, db: Session) -> dict:
    """
    Session ki saari preferences ek dict mein return karo.
    Example: {"destination_interest": "mountains", "budget": "medium"}
    """
    memories = (
        db.query(UserMemory)
        .filter(UserMemory.session_id == session_id)
        .all()
    )
    return {m.key: m.value for m in memories}


def extract_and_save_preferences(
    session_id: str,
    user_message: str,
    db: Session,
):
    """
    User ke message se preferences automatically extract karo.
    Groq se lightweight extraction — sirf zaroori cheezein.
    """
    # Sirf tab run karo jab message mein relevant keywords hon
    keywords = [
        "budget", "family", "solo", "kids", "cheap", "expensive",
        "prefer", "like", "love", "interest", "want", "looking for",
        "north", "south", "lahore", "karachi", "gilgit", "hunza",
        "mountain", "beach", "historical", "nature", "adventure"
    ]

    msg_lower = user_message.lower()
    if not any(kw in msg_lower for kw in keywords):
        return  # Koi relevant info nahi — skip karo

    try:
        client = Groq(api_key=settings.groq_api_key)
        prompt = (
            "Extract travel preferences from this message. "
            "Return ONLY a JSON object. Use null if not found.\n"
            "Keys to extract:\n"
            '{"destination_interest": null, "travel_budget": null, '
            '"travel_style": null, "preferred_region": null, '
            '"group_type": null}\n\n'
            f"Message: {user_message}\n\n"
            "Return ONLY JSON, no explanation."
        )

        response = client.chat.completions.create(
            model       = settings.groq_model,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0,
            max_tokens  = 150,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        prefs = json.loads(raw)

        # Sirf non-null values save karo
        for key, value in prefs.items():
            if value and value != "null":
                save_user_memory(session_id, key, str(value), db, confidence="medium")

    except Exception as e:
        # Extraction fail hone par silently skip karo
        print(f"[Memory] Preference extraction skipped: {e}")


# ===========================================================================
# MEMORY CONTEXT BUILDER
# ===========================================================================

def build_memory_context(session_id: str, db: Session) -> str:
    """
    LLM prompt ke liye memory context string banao.
    Combines: session summary (if any) + recent messages + user preferences
    """
    parts = []

    # 1. Long-term preferences
    memories = get_user_memories(session_id, db)
    if memories:
        mem_lines = [f"  - {k.replace('_', ' ').title()}: {v}" for k, v in memories.items()]
        parts.append("USER PREFERENCES (remembered from past):\n" + "\n".join(mem_lines))

    # 2. Session summary (agar summarization ho chuki hai)
    session = db.get(ChatSession, session_id)
    if session and session.is_summarized and session.summary:
        parts.append(f"CONVERSATION SUMMARY (earlier in this chat):\n{session.summary}")

    return "\n\n".join(parts)