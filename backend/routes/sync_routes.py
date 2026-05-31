from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.schemas import SyncReport
from services.sync_service import run_incremental_sync

router = APIRouter(tags=["Sync"])

# Store the last sync report in memory for GET /sync/status
_last_sync_report: dict | None = None


@router.post("/sync", response_model=SyncReport)
def trigger_sync(db: Session = Depends(get_db)):
    """
    Trigger an incremental sync.
    Only changed records are re-embedded. Unchanged records are skipped.
    """
    global _last_sync_report
    try:
        report          = run_incremental_sync(db)
        _last_sync_report = report
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/sync/status", response_model=SyncReport | None)
def sync_status():
    """Returns the result of the last sync run (in-memory, resets on restart)."""
    if _last_sync_report is None:
        raise HTTPException(status_code=404, detail="No sync has been run yet")
    return _last_sync_report