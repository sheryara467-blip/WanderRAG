"""
booking_routes.py
Handles:
  POST /api/booking-agent/message  — conversational agent
  POST /api/bookings               — direct create (admin use)
  GET  /api/bookings               — list all (admin)
  GET  /api/bookings/{id}          — detail
  PUT  /api/bookings/{id}/status   — status update (admin)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Booking
from backend.models.schemas import (
    BookingAgentRequest, BookingAgentResponse,
    BookingCreate, BookingOut, BookingStatusUpdate,
)
from services import booking_service

router = APIRouter(tags=["Bookings"])

VALID_STATUSES = {"pending", "confirmed", "cancelled", "completed"}


# ---------------------------------------------------------------------------
# Booking agent — conversational endpoint
# ---------------------------------------------------------------------------
@router.post("/booking-agent/message", response_model=BookingAgentResponse)
def agent_message(body: BookingAgentRequest, db: Session = Depends(get_db)):
    """
    Process one turn of the booking conversation.
    The frontend calls this for every message the user sends in the booking modal.
    """
    result = booking_service.process_message(
        session_id = body.session_id,
        message    = body.message,
        place_id   = body.place_id,
        place_name = body.place_name,
        db         = db,
    )
    return BookingAgentResponse(**result)


# ---------------------------------------------------------------------------
# Direct booking creation (admin / programmatic use)
# ---------------------------------------------------------------------------
@router.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(body: BookingCreate, db: Session = Depends(get_db)):
    now        = datetime.now(timezone.utc)
    booking_id = f"WR-{uuid.uuid4().hex[:8].upper()}"

    booking = Booking(
        id               = booking_id,
        place_id         = body.place_id,
        package_id       = body.package_id or "",
        place_name       = body.place_name,
        user_name        = body.customer_name,
        user_email       = body.customer_email or "",
        booking_date     = body.travel_date,
        customer_name    = body.customer_name,
        customer_phone   = body.customer_phone,
        customer_email   = body.customer_email or "",
        travel_date      = body.travel_date,
        number_of_people = body.number_of_people,
        notes            = body.notes or "",
        status           = "pending",
        created_at       = now,
        updated_at       = now,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# List all bookings (admin)
# ---------------------------------------------------------------------------
@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Booking)
    if status:
        q = q.filter(Booking.status == status)
    return q.order_by(Booking.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Single booking detail
# ---------------------------------------------------------------------------
@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    b = db.get(Booking, booking_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")
    return b


# ---------------------------------------------------------------------------
# Update booking status (admin)
# ---------------------------------------------------------------------------
@router.put("/bookings/{booking_id}/status", response_model=BookingOut)
def update_status(
    booking_id: str,
    body: BookingStatusUpdate,
    db: Session = Depends(get_db),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Choose from: {sorted(VALID_STATUSES)}"
        )
    b = db.get(Booking, booking_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found")

    b.status     = body.status
    b.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(b)
    return b
