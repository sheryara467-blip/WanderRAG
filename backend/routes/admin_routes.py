from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter(tags=["Admin"])


@router.get("/admin")
def serve_admin():
    """Serve the admin dashboard SPA."""
    admin_path = os.path.join(os.path.dirname(__file__), "..", "static", "admin.html")
    admin_path = os.path.normpath(admin_path)

    if not os.path.exists(admin_path):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"detail": "admin.html not found in static/"},
        )

    return FileResponse(admin_path, media_type="text/html")