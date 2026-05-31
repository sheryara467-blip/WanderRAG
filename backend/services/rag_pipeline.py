from sqlalchemy.orm import Session
from services.retrieval_service import retrieve_relevant_records
from services.llm_service import build_context, generate_answer
from models.schemas import ChatResponse, SourceCard


def run_rag_pipeline(query: str, db: Session, top_k: int = 5) -> ChatResponse:
    """
    Full RAG pipeline:
      1. Retrieve relevant places/packages from Pinecone + SQLite
      2. Build context string from full DB records
      3. Generate answer with Groq LLM
      4. Build source cards for the frontend UI
    """

    # Step 1: Retrieve
    retrieved = retrieve_relevant_records(query, db, top_k=top_k)
    places    = retrieved["places"]
    packages  = retrieved["packages"]
    scores    = retrieved["scores"]

    # Step 2: Build context
    context = build_context(places, packages)

    # Step 3: Generate answer
    answer = generate_answer(query, context)

    # Step 4: Build source cards (only places shown as cards in frontend)
    source_cards = [
        SourceCard(
            id        = p.id,
            name      = p.name,
            city      = p.city,
            province  = p.province,
            category  = p.category,
            entry_fee = p.entry_fee,
            image_url = p.image_url,
            map_url   = p.map_url,
            opening_hours      = p.opening_hours,
            best_time_to_visit = p.best_time_to_visit,
            score     = round(scores.get(p.id, 0.0), 3),
        )
        for p in places
    ]

    return ChatResponse(
        answer  = answer,
        sources = source_cards,
        query   = query,
    )
