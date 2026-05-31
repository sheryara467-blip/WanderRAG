import sys
from pathlib import Path

# Render par Python ko backend/ folder ka path batao
# taake models, routes, services sab mil sakein
sys.path.insert(0, str(Path(__file__).resolve().parent))


from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import init_db
from services.embedding_service import get_embedding_service
from services.pinecone_service import get_pinecone_service

from routes.health_routes import router as health_router
from routes.chat_routes   import router as chat_router
from routes.places_routes import router as places_router
from routes.sync_routes   import router as sync_router
from routes.admin_routes  import router as admin_router
from routes.booking_routes import router as booking_router
settings = get_settings()

# ---------------------------------------------------------------------------
# Absolute path resolution using pathlib
# __file__ = .../Tourism_assistant/backend/main.py
# BACKEND_DIR  = .../Tourism_assistant/backend
# FRONTEND_DIR = .../Tourism_assistant/frontend
# ---------------------------------------------------------------------------
BACKEND_DIR  = Path(__file__).resolve().parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*52}")
    print(f"  🚀  {settings.app_name}  v{settings.app_version}")
    print(f"{'='*52}")

    # Validate frontend directory exists before startup completes
    if not FRONTEND_DIR.exists():
        print(f"⚠️  Frontend folder not found: {FRONTEND_DIR}")
        print("    Create Tourism_assistant/frontend/ with index.html and admin.html")
    else:
        print(f"✅  Frontend  → {FRONTEND_DIR}")

    # Initialise SQLite tables
    init_db()

    # Load embedding model into memory (slow once, instant after)
    print("⏳  Loading embedding model...")
    get_embedding_service()
    print("✅  Embedding model ready")

    # Connect to Pinecone
    print("⏳  Connecting to Pinecone...")
    get_pinecone_service()
    print("✅  Pinecone connected\n")

    # Print access URLs
    print(f"  Tourist UI  →  http://127.0.0.1:8000/")
    print(f"  Admin UI    →  http://127.0.0.1:8000/admin")
    print(f"  API Docs    →  http://127.0.0.1:8000/docs")
    print(f"{'='*52}\n")

    yield  # app is live

    print("👋  Shutting down WanderRAG")


app = FastAPI(
    title       = settings.app_name,
    version     = settings.app_version,
    description = "AI-Powered Tourism Guide and Booking Platform",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ---------------------------------------------------------------------------
# API routers — registered FIRST so /api/* is never caught by static mount
# ---------------------------------------------------------------------------
app.include_router(health_router, prefix="/api")
app.include_router(chat_router,   prefix="/api")
app.include_router(places_router, prefix="/api")
app.include_router(sync_router,   prefix="/api")
app.include_router(admin_router,  prefix="/api")
app.include_router(booking_router, prefix="/api")
# ---------------------------------------------------------------------------
# Explicit HTML page routes
# These are registered BEFORE the static mount so they take priority
# ---------------------------------------------------------------------------
@app.get("/admin", include_in_schema=False)
def serve_admin():
    return FileResponse(FRONTEND_DIR / "admin.html")

@app.get("/", include_in_schema=False)
def serve_tourist():
    return FileResponse(FRONTEND_DIR / "index.html")

# ---------------------------------------------------------------------------
# Static file mount — serves CSS, JS, assets from /frontend/
# Must come LAST — acts as catch-all for anything not matched above
# ---------------------------------------------------------------------------
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)
