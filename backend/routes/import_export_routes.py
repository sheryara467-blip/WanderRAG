import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from services.csv_service import import_csv, export_csv

router = APIRouter(tags=["CSV Import / Export"])


@router.post("/import-csv")
async def import_csv_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file → upsert records into SQLite.
    Does NOT touch Pinecone. Run /api/sync after import to push changes.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = import_csv(db, contents)

    # If CSV was unparseable, return 422
    if result["errors"] and result["inserted"] == 0 and result["updated"] == 0:
        raise HTTPException(status_code=422, detail=result["error_details"])

    return result


@router.get("/export-csv")
def export_csv_route(db: Session = Depends(get_db)):
    """
    Download all places from SQLite as a CSV file.
    This is a snapshot of the current database state.
    """
    csv_content = export_csv(db)

    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=wanderrag_places_export.csv"
        },
    )