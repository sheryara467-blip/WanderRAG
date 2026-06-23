"""
llm_service.py — UPDATED with conversation history + memory
"""

from groq import Groq
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import Place, TourPackage

settings = get_settings()
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def build_context(places: list[Place], packages: list[TourPackage]) -> str:
    """Retrieved tourism records ko context string mein convert karo."""
    parts = []

    for p in places:
        parts.append(
            f"PLACE: {p.name}\n"
            f"  City: {p.city}, {p.province}\n"
            f"  Category: {p.category}\n"
            f"  Description: {p.description}\n"
            f"  History: {p.history}\n"
            f"  Entry Fee: {p.entry_fee}\n"
            f"  Opening Hours: {p.opening_hours}\n"
            f"  Best Time to Visit: {p.best_time_to_visit}"
        )

    for pkg in packages:
        parts.append(
            f"TOUR PACKAGE: {pkg.title}\n"
            f"  Description: {pkg.description}\n"
            f"  Price: PKR {pkg.price:,.0f}\n"
            f"  Duration: {pkg.duration_days} days"
        )

    return "\n\n".join(parts) if parts else "No relevant tourism information found."


def generate_answer(
    query:          str,
    context:        str,
    chat_history:   list[dict] = None,    # Short-term memory
    memory_context: str        = "",       # Long-term memory
) -> str:
    """
    Groq LLM se answer generate karo.

    Prompt structure:
    ┌─────────────────────────────────────────────┐
    │ SYSTEM                                      │
    │   - WanderRAG ka role                       │
    │   - User preferences (long-term memory)     │
    │   - Retrieved tourism context               │
    ├─────────────────────────────────────────────┤
    │ MESSAGES (short-term memory)                │
    │   - Previous conversation turns             │
    │   - Current user query                      │
    └─────────────────────────────────────────────┘
    """

    # System prompt mein tourism context + user memory dono inject karo
    system_prompt = (
        "You are WanderRAG, a friendly Pakistan tourism AI assistant.\n"
        "Answer using ONLY the tourism context provided. "
        "If information is not in the context, say so honestly.\n"
        "Be warm, concise, and helpful. Use bullet points when listing places.\n"
    )

    # Long-term memory add karo (agar hai)
    if memory_context:
        system_prompt += f"\n{memory_context}\n"

    # Tourism context add karo
    system_prompt += f"\nTOURISM CONTEXT:\n{context}"

    # Messages build karo
    messages = [{"role": "system", "content": system_prompt}]

    # Short-term history add karo (last 6 messages)
    if chat_history:
        messages.extend(chat_history)

    # Current query add karo
    messages.append({"role": "user", "content": query})

    client   = _get_client()
    response = client.chat.completions.create(
        model       = settings.groq_model,
        messages    = messages,
        temperature = 0.3,
        max_tokens  = 1024,
    )

    return response.choices[0].message.content.strip()