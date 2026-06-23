"""
summarization_service.py
Jab messages SUMMARIZE_AFTER limit cross karein,
purane messages summarize karke replace karo.

Kyun zaroorat hai:
  - LLM ka context window limited hai (~8000 tokens)
  - 20+ messages = too many tokens = slow/expensive
  - Summary se important info rehti hai, tokens kam hote hain
"""

from datetime import datetime, timezone

from groq import Groq
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import ChatSession, ChatMessage
from services.memory_service import SUMMARIZE_AFTER, SHORT_TERM_WINDOW

settings = get_settings()


def should_summarize(session_id: str, db: Session) -> bool:
    """
    Check karo ke summarization ki zaroorat hai ya nahi.
    Condition: messages > SUMMARIZE_AFTER AND last summarization ke baad bhi zyada messages
    """
    session = db.get(ChatSession, session_id)
    if not session:
        return False

    total = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()

    # Pehli baar: SUMMARIZE_AFTER limit cross ho
    # Dobara: har SHORT_TERM_WINDOW messages ke baad
    if not session.is_summarized:
        return total >= SUMMARIZE_AFTER
    else:
        # Agar already summarized hai toh check karo
        # ke summary ke baad kitne naye messages hain
        return total >= SUMMARIZE_AFTER + SHORT_TERM_WINDOW


def summarize_session(session_id: str, db: Session) -> str:
    """
    Purani chat ko summarize karo.
    Last SHORT_TERM_WINDOW messages rakhte hain — baaki summarize ho jaate hain.
    """
    # Saare messages lao
    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    if len(all_messages) <= SHORT_TERM_WINDOW:
        return ""  # Koi zaroorat nahi

    # Purane messages (summarize karne wale)
    messages_to_summarize = all_messages[:-SHORT_TERM_WINDOW]

    # Conversation text banao
    convo_text = "\n".join([
        f"{m.role.upper()}: {m.content}"
        for m in messages_to_summarize
    ])

    try:
        client = Groq(api_key=settings.groq_api_key)

        prompt = (
            "Summarize this Pakistan tourism chat conversation. "
            "Keep it concise (max 150 words). "
            "Focus on: places discussed, user preferences shown, "
            "questions asked, and any booking intent.\n\n"
            f"CONVERSATION:\n{convo_text}\n\n"
            "Write summary in 3rd person. Start with 'User asked about...'"
        )

        response = client.chat.completions.create(
            model       = settings.groq_model,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.3,
            max_tokens  = 200,
        )

        summary = response.choices[0].message.content.strip()

        # Session mein summary save karo
        session = db.get(ChatSession, session_id)
        if session:
            # Existing summary ke saath combine karo
            if session.summary:
                session.summary = session.summary + "\n\n" + summary
            else:
                session.summary = summary

            session.is_summarized = 1
            session.updated_at    = datetime.now(timezone.utc)
            db.commit()

        print(f"[Summarizer] Session {session_id[:8]}... summarized ({len(messages_to_summarize)} messages)")
        return summary

    except Exception as e:
        print(f"[Summarizer] Failed: {e}")
        return ""