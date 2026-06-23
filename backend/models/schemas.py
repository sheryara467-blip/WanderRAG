from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ===========================================================================
# PLACE schemas
# ===========================================================================

class PlaceBase(BaseModel):
    name:               str
    city:               str
    province:           str
    category:           str
    description:        Optional[str] = ""
    history:            Optional[str] = ""
    tags:               Optional[str] = "[]"
    entry_fee:          Optional[str] = "Free"
    opening_hours:      Optional[str] = "Open daily"
    best_time_to_visit: Optional[str] = ""
    image_url:          Optional[str] = ""
    map_url:            Optional[str] = ""
    latitude:           Optional[float] = None
    longitude:          Optional[float] = None


class PlaceCreate(PlaceBase):
    """Body for POST /api/places. id is generated from name and city."""
    pass


class PlaceUpdate(BaseModel):
    """Body for PUT /api/places/{id}. All fields are optional."""
    name:               Optional[str] = None
    city:               Optional[str] = None
    province:           Optional[str] = None
    category:           Optional[str] = None
    description:        Optional[str] = None
    history:            Optional[str] = None
    tags:               Optional[str] = None
    entry_fee:          Optional[str] = None
    opening_hours:      Optional[str] = None
    best_time_to_visit: Optional[str] = None
    image_url:          Optional[str] = None
    map_url:            Optional[str] = None
    latitude:           Optional[float] = None
    longitude:          Optional[float] = None


class PlaceOut(PlaceBase):
    id:         str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ===========================================================================
# TOUR PACKAGE schemas
# ===========================================================================

class TourPackageBase(BaseModel):
    title:            str
    description:      Optional[str] = ""
    price:            Optional[float] = 0.0
    duration_days:    Optional[int] = 1
    places_included:  Optional[str] = "[]"
    tags:             Optional[str] = "[]"


class TourPackageCreate(TourPackageBase):
    pass


class TourPackageOut(TourPackageBase):
    id:         str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ===========================================================================
# CHAT schemas
# ===========================================================================

class ChatRequest(BaseModel):
    query:      str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(..., min_length=1)
    top_k:      int = Field(default=5, ge=1, le=20)


class SourceCard(BaseModel):
    id:                 str
    name:               str
    city:               str
    province:           str
    category:           str
    entry_fee:          str
    image_url:          str
    map_url:            str = ""
    opening_hours:      str = ""
    best_time_to_visit: str = ""
    score:              float


class ChatResponse(BaseModel):
    answer:     str
    sources:    List[SourceCard]
    query:      str
    session_id: str


class ChatMessageOut(BaseModel):
    id:         str
    role:       str
    content:    str
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id:            str
    title:         str
    created_at:    Optional[datetime]
    is_summarized: int
    summary:       Optional[str]

    model_config = {"from_attributes": True}


class UserMemoryOut(BaseModel):
    key:        str
    value:      str
    confidence: str
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ===========================================================================
# SYNC schemas
# ===========================================================================

class SyncReport(BaseModel):
    added:            int
    updated:          int
    deleted:          int
    skipped:          int
    total_pinecone:   int
    duration_seconds: float
    details:          List[str]


# ===========================================================================
# HEALTH schemas
# ===========================================================================

class HealthResponse(BaseModel):
    status:          str
    database:        bool
    pinecone:        bool
    embedding_model: bool
    app_version:     str
    environment:     str


# ===========================================================================
# BOOKING AGENT schemas
# ===========================================================================

class BookingAgentRequest(BaseModel):
    session_id: str
    message:    str = Field(..., min_length=1, max_length=2000)
    place_id:   Optional[str] = None
    place_name: Optional[str] = None


class BookingAgentResponse(BaseModel):
    session_id: str
    reply:      str
    state:      str
    booking_id: Optional[str] = None
    summary:    Optional[dict] = None


# ===========================================================================
# BOOKING CRUD schemas
# ===========================================================================

class BookingCreate(BaseModel):
    place_id:         Optional[str] = None
    package_id:       Optional[str] = None
    place_name:       str
    customer_name:    str
    customer_phone:   str
    customer_email:   Optional[str] = ""
    travel_date:      str
    number_of_people: int = Field(default=1, ge=1)
    notes:            Optional[str] = ""


class BookingStatusUpdate(BaseModel):
    status: str


class BookingOut(BaseModel):
    id:               str
    place_id:         Optional[str]
    package_id:       Optional[str]
    place_name:       str
    customer_name:    str
    customer_phone:   str
    customer_email:   Optional[str]
    travel_date:      str
    number_of_people: int
    notes:            Optional[str]
    status:           str
    created_at:       Optional[datetime]
    updated_at:       Optional[datetime]

    model_config = {"from_attributes": True}
