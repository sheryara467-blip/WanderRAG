"""
csv_service.py

Handles CSV import and export.
CSV is NOT the source of truth — SQLite is.
Import = load CSV → upsert into SQLite → let sync detect changes.
Export = read SQLite → write CSV.
"""

import re
import io
import json
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.db_models import Place


def _utcnow():
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe_str(value, fallback="") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    return str(value).strip()


def _safe_float(value, fallback=None):
    try:
        return float(value) if not pd.isna(value) else fallback
    except Exception:
        return fallback


def _safe_json(value, fallback="[]") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    s = str(value).strip()
    if s.startswith("["):
        try:
            json.loads(s)
            return s
        except Exception:
            pass
    tags = [t.strip() for t in s.split(",") if t.strip()]
    return json.dumps(tags)


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------

def import_csv(db: Session, file_bytes: bytes) -> dict:
    """
    Parse CSV bytes → upsert records into SQLite.
    Returns stats dict: inserted, updated, skipped, errors.

    After this runs, the sync service will detect hash differences
    and re-embed only the changed records. CSV never touches Pinecone directly.
    """
    inserted = updated = skipped = errors = 0
    error_details = []

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        return {
            "inserted": 0, "updated": 0,
            "skipped": 0, "errors": 1,
            "error_details": [f"Could not parse CSV: {str(e)}"],
        }

    required_columns = {"name", "city", "province", "category"}
    missing = required_columns - set(df.columns.str.lower())
    if missing:
        return {
            "inserted": 0, "updated": 0, "skipped": 0, "errors": 1,
            "error_details": [f"Missing required columns: {missing}"],
        }

    for idx, row in df.iterrows():
        try:
            # Determine ID
            if "id" in row and _safe_str(row.get("id")):
                place_id = _safe_str(row["id"])
            else:
                name = _safe_str(row.get("name", ""))
                city = _safe_str(row.get("city", ""))
                if not name or not city:
                    skipped += 1
                    continue
                place_id = _slugify(f"{name}-{city}")

            existing = db.get(Place, place_id)

            new_data = {
                "name":               _safe_str(row.get("name")),
                "city":               _safe_str(row.get("city")),
                "province":           _safe_str(row.get("province")),
                "category":           _safe_str(row.get("category")),
                "description":        _safe_str(row.get("description")),
                "history":            _safe_str(row.get("history")),
                "entry_fee":          _safe_str(row.get("entry_fee"), "Free"),
                "opening_hours":      _safe_str(row.get("opening_hours"), "Open daily"),
                "best_time_to_visit": _safe_str(row.get("best_time_to_visit")),
                "image_url":          _safe_str(row.get("image_url")),
                "map_url":            _safe_str(row.get("map_url")),
                "latitude":           _safe_float(row.get("latitude")),
                "longitude":          _safe_float(row.get("longitude")),
                "tags":               _safe_json(row.get("tags")),
            }

            if existing:
                # Update every field — sync will detect which chunks changed
                for field, value in new_data.items():
                    setattr(existing, field, value)
                existing.updated_at = _utcnow()
                updated += 1
            else:
                place = Place(id=place_id, **new_data,
                              created_at=_utcnow(), updated_at=_utcnow())
                db.add(place)
                inserted += 1

        except Exception as e:
            errors += 1
            error_details.append(f"Row {idx + 2}: {str(e)}")

    db.commit()

    return {
        "inserted":     inserted,
        "updated":      updated,
        "skipped":      skipped,
        "errors":       errors,
        "error_details": error_details,
        "message":      (
            f"Import complete. {inserted} inserted, {updated} updated, "
            f"{skipped} skipped, {errors} errors. "
            "Run sync to push changes to Pinecone."
        ),
    }


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------

# Columns exported — same order as tourism_seed.csv
EXPORT_COLUMNS = [
    "id", "name", "city", "province", "category",
    "description", "history", "entry_fee", "opening_hours",
    "best_time_to_visit", "image_url", "map_url",
    "latitude", "longitude", "tags", "updated_at",
]


def export_csv(db: Session) -> str:
    """
    Read all places from SQLite and return a CSV string.
    Caller wraps this in a StreamingResponse.
    """
    places = db.query(Place).order_by(Place.name).all()

    rows = []
    for p in places:
        rows.append({
            "id":                 p.id,
            "name":               p.name,
            "city":               p.city,
            "province":           p.province,
            "category":           p.category,
            "description":        p.description,
            "history":            p.history,
            "entry_fee":          p.entry_fee,
            "opening_hours":      p.opening_hours,
            "best_time_to_visit": p.best_time_to_visit,
            "image_url":          p.image_url,
            "map_url":            p.map_url,
            "latitude":           p.latitude,
            "longitude":          p.longitude,
            "tags":               p.tags,
            "updated_at":         p.updated_at.isoformat() if p.updated_at else "",
        })

    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    return df.to_csv(index=False)