import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Place
from backend.models.schemas import PlaceCreate, PlaceUpdate, PlaceOut

router = APIRouter(tags=["Places"])


def _make_id(name: str, city: str) -> str:
    """Generate a stable slug ID from name + city. e.g. 'Lahore Fort' → 'lahore-fort'"""
    raw = f"{name}-{city}".lower()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


# ---------------------------------------------------------------------------
# GET all places (with optional filters)
# ---------------------------------------------------------------------------
@router.get("/places", response_model=list[PlaceOut])
def list_places(
    city:     str | None = Query(default=None),
    province: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Place)
    if city:     q = q.filter(Place.city.ilike(f"%{city}%"))
    if province: q = q.filter(Place.province.ilike(f"%{province}%"))
    if category: q = q.filter(Place.category.ilike(f"%{category}%"))
    return q.order_by(Place.name).all()


# ---------------------------------------------------------------------------
# GET single place
# ---------------------------------------------------------------------------
@router.get("/places/{place_id}", response_model=PlaceOut)
def get_place(place_id: str, db: Session = Depends(get_db)):
    place = db.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail=f"Place '{place_id}' not found")
    return place


# ---------------------------------------------------------------------------
# POST create place
# ---------------------------------------------------------------------------
@router.post("/places", response_model=PlaceOut, status_code=201)
def create_place(body: PlaceCreate, db: Session = Depends(get_db)):
    place_id = _make_id(body.name, body.city)

    if db.get(Place, place_id):
        raise HTTPException(status_code=409, detail=f"Place '{place_id}' already exists")

    place = Place(id=place_id, **body.model_dump())
    db.add(place)
    db.commit()
    db.refresh(place)
    return place


# ---------------------------------------------------------------------------
# PUT update place
# ---------------------------------------------------------------------------
@router.put("/places/{place_id}", response_model=PlaceOut)
def update_place(place_id: str, body: PlaceUpdate, db: Session = Depends(get_db)):
    place = db.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail=f"Place '{place_id}' not found")

    # Only update fields that were actually sent in the request
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(place, field, value)

    db.commit()
    db.refresh(place)
    return place


# ---------------------------------------------------------------------------
# DELETE place
# ---------------------------------------------------------------------------
@router.delete("/places/{place_id}", status_code=204)
def delete_place(place_id: str, db: Session = Depends(get_db)):
    place = db.get(Place, place_id)
    if not place:
        raise HTTPException(status_code=404, detail=f"Place '{place_id}' not found")
    db.delete(place)
    db.commit()