from sqlalchemy.orm import Session
from backend.models.db_models import Place, TourPackage
from backend.services.embedding_service import get_embedding_service
from backend.services.pinecone_service import get_pinecone_service


def retrieve_relevant_records(query: str, db: Session, top_k: int = 5) -> dict:
    """
    1. Embed the user's query
    2. Search Pinecone for similar vectors
    3. Fetch full records from SQLite using the returned IDs
    4. Return places and packages separately (deduped)

    Returns:
        {
          "places":   [Place, ...],
          "packages": [TourPackage, ...],
          "scores":   {"record_id": score, ...}
        }
    """
    embedder = get_embedding_service()
    pinecone  = get_pinecone_service()

    # Embed the query
    query_vector = embedder.embed(query)

    # Fetch more than top_k because two vectors per place (_desc + _facts)
    # means the same place can appear twice — we deduplicate below
    matches = pinecone.query(vector=query_vector, top_k=top_k * 2)

    # Keep only the best score per record_id across both its chunks
    best_scores: dict[str, float] = {}
    for match in matches:
        record_id = match["metadata"].get("record_id", "")
        score     = match["score"]
        if record_id not in best_scores or score > best_scores[record_id]:
            best_scores[record_id] = score

    # Separate place IDs from package IDs, preserving score order
    place_ids   = []
    package_ids = []
    for match in matches:
        meta        = match["metadata"]
        record_id   = meta.get("record_id", "")
        record_type = meta.get("record_type", "place")
        if record_type == "place" and record_id not in place_ids:
            place_ids.append(record_id)
        elif record_type == "package" and record_id not in package_ids:
            package_ids.append(record_id)

    # Trim to actual top_k after deduplication
    place_ids   = place_ids[:top_k]
    package_ids = package_ids[:top_k]

    # Fetch full records from SQLite using the IDs Pinecone returned.
    # SQL IN does not preserve Pinecone ranking, so restore score order after fetch.
    places = []
    if place_ids:
        rows = db.query(Place).filter(Place.id.in_(place_ids)).all()
        by_id = {row.id: row for row in rows}
        places = [by_id[place_id] for place_id in place_ids if place_id in by_id]

    packages = []
    if package_ids:
        rows = db.query(TourPackage).filter(TourPackage.id.in_(package_ids)).all()
        by_id = {row.id: row for row in rows}
        packages = [by_id[package_id] for package_id in package_ids if package_id in by_id]

    query_lower = query.strip().lower()
    places.sort(
        key=lambda place: (
            0 if place.name and place.name.lower() in query_lower else 1,
            -best_scores.get(place.id, 0.0),
        )
    )

    return {
        "places":   places,
        "packages": packages,
        "scores":   best_scores,
    }
