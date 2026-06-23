from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter(tags=["Admin"])

FRONTEND_ADMIN = Path(__file__).resolve().parents[2] / "frontend" / "admin.html"


@router.get("/admin", include_in_schema=False)
def serve_admin():
    """Serve the admin dashboard through the API prefix if requested."""
    if not FRONTEND_ADMIN.exists():
        raise HTTPException(status_code=404, detail="frontend/admin.html not found")

    return FileResponse(FRONTEND_ADMIN, media_type="text/html")
