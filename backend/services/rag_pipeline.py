# from sqlalchemy.orm import Session
# from services.retrieval_service import retrieve_relevant_records
# from services.llm_service import build_context, generate_answer
# from models.schemas import ChatResponse, SourceCard


# def run_rag_pipeline(query: str, db: Session, top_k: int = 5) -> ChatResponse:
#     """
#     Full RAG pipeline:
#       1. Retrieve relevant places/packages from Pinecone + SQLite
#       2. Build context string from full DB records
#       3. Generate answer with Groq LLM
#       4. Build source cards for the frontend UI
#     """

#     # Step 1: Retrieve
#     retrieved = retrieve_relevant_records(query, db, top_k=top_k)
#     places    = retrieved["places"]
#     packages  = retrieved["packages"]
#     scores    = retrieved["scores"]

#     # Step 2: Build context
#     context = build_context(places, packages)

#     # Step 3: Generate answer
#     answer = generate_answer(query, context)

#     # Step 4: Build source cards (only places shown as cards in frontend)
#     source_cards = [
#         SourceCard(
#             id        = p.id,
#             name      = p.name,
#             city      = p.city,
#             province  = p.province,
#             category  = p.category,
#             entry_fee = p.entry_fee,
#             image_url = p.image_url,
#             map_url   = p.map_url,
#             opening_hours      = p.opening_hours,
#             best_time_to_visit = p.best_time_to_visit,
#             score     = round(scores.get(p.id, 0.0), 3),
#         )
#         for p in places
#     ]

#     return ChatResponse(
#         answer  = answer,
#         sources = source_cards,
#         query   = query,
#     )






"""
rag_pipeline.py — UPDATED: memory inject hota hai
"""

from sqlalchemy.orm import Session

from models.schemas import ChatResponse, SourceCard
from services.retrieval_service import retrieve_relevant_records
from services.llm_service import build_context, generate_answer
from services.memory_service import (
    get_or_create_session,
    save_message,
    get_recent_messages,
    build_memory_context,
    extract_and_save_preferences,
    update_session_title,
    get_message_count,
)
from services.summarization_service import should_summarize, summarize_session


def run_rag_pipeline(
    query:      str,
    session_id: str,
    db:         Session,
    top_k:      int = 5,
) -> ChatResponse:
    """
    Full RAG pipeline with memory:

    1. Session ensure karo
    2. Summarize karo agar zaroorat ho
    3. Pinecone se retrieve karo
    4. Memory context build karo
    5. Chat history lao
    6. LLM generate karo
    7. Messages save karo
    8. Preferences extract karo
    """

    # ── Step 1: Session ensure ─────────────────────────────
    get_or_create_session(session_id, db)

    # ── Step 2: Auto-summarize agar messages zyada hain ────
    if should_summarize(session_id, db):
        summarize_session(session_id, db)

    # ── Step 3: RAG Retrieval ──────────────────────────────
    retrieved = retrieve_relevant_records(query, db, top_k=top_k)
    places    = retrieved["places"]
    packages  = retrieved["packages"]
    scores    = retrieved["scores"]
    context   = build_context(places, packages)

    # ── Step 4: Memory context ─────────────────────────────
    memory_context = build_memory_context(session_id, db)

    # ── Step 5: Chat history (short-term memory) ───────────
    chat_history = get_recent_messages(session_id, db)
    # Current query already alag se jayegi — history mein mat daalo

    # ── Step 6: LLM Answer ────────────────────────────────
    answer = generate_answer(
        query          = query,
        context        = context,
        chat_history   = chat_history,
        memory_context = memory_context,
    )

    # ── Step 7: Messages save karo ────────────────────────
    # User message
    save_message(session_id, "user", query, db)

    # Session title set karo pehli baar
    if get_message_count(session_id, db) <= 2:
        update_session_title(session_id, query, db)

    # Assistant response
    sources_for_db = [
        {"id": p.id, "name": p.name, "score": scores.get(p.id, 0)}
        for p in places
    ]
    save_message(session_id, "assistant", answer, db, sources=sources_for_db)

    # ── Step 8: Preferences extract karo (background) ─────
    extract_and_save_preferences(session_id, query, db)

    # ── Step 9: Source cards build karo ───────────────────
    source_cards = [
        SourceCard(
            id        = p.id,
            name      = p.name,
            city      = p.city,
            province  = p.province,
            category  = p.category,
            entry_fee = p.entry_fee,
            image_url = p.image_url,
            score     = round(scores.get(p.id, 0.0), 3),
        )
        for p in places
    ]

    return ChatResponse(
        answer     = answer,
        sources    = source_cards,
        query      = query,
        session_id = session_id,
    )