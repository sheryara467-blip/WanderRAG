from groq import Groq
from backend.config import get_settings
from backend.models.db_models import Place, TourPackage

settings = get_settings()
_client  = None   # lazy init to avoid loading at import time


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def build_context(places: list[Place], packages: list[TourPackage]) -> str:
    """
    Format retrieved DB records into a readable context block for the LLM.
    The LLM is grounded to this context — it cannot hallucinate places.
    """
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


def generate_answer(query: str, context: str) -> str:
    """
    Call Groq LLM with the retrieved context and user query.
    The system prompt strictly grounds the model to the provided context.
    """
    system_prompt = (
        "You are WanderRAG, a friendly and knowledgeable Pakistan tourism assistant. "
        "Answer the user's question using ONLY the tourism information provided below. "
        "If the information isn't in the context, say so honestly — do not invent places or facts. "
        "Be warm, helpful, and concise. Use bullet points where appropriate.\n\n"
        f"TOURISM CONTEXT:\n{context}"
    )

    client   = _get_client()
    response = client.chat.completions.create(
        model    = settings.groq_model,
        messages = [
            {"role": "system",  "content": system_prompt},
            {"role": "user",    "content": query},
        ],
        temperature = 0.3,   # low temperature = factual, consistent answers
        max_tokens  = 1024,
    )

    return response.choices[0].message.content.strip()