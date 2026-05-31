from fastapi import APIRouter
from backend.services.pinecone_service import get_pinecone_service
from backend.services.embedding_service import get_embedding_service
from backend.models.schemas import HealthResponse
from backend.config import get_settings
from backend.database import SessionLocal

router   = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Returns status of all connected services.
    Frontend polls this on load to show the 'connected' badge.
    """
    # Check DB
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        pass

    # Check Pinecone
    pinecone_ok = False
    try:
        pinecone_ok = get_pinecone_service().is_healthy()
    except Exception:
        pass

    # Check embedding model
    embed_ok = False
    try:
        svc      = get_embedding_service()
        embed_ok = svc.model is not None
    except Exception:
        pass

    overall = "ok" if all([db_ok, pinecone_ok, embed_ok]) else "degraded"

    return HealthResponse(
        status          = overall,
        database        = db_ok,
        pinecone        = pinecone_ok,
        embedding_model = embed_ok,
        app_version     = settings.app_version,
        environment     = settings.app_env,
    )