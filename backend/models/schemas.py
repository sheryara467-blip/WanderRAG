from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    tags:               Optional[str] = "[]"       # JSON string
    entry_fee:          Optional[str] = "Free"
    opening_hours:      Optional[str] = "Open daily"
    best_time_to_visit: Optional[str] = ""
    image_url:          Optional[str] = ""
    map_url:            Optional[str] = ""
    latitude:           Optional[float] = None
    longitude:          Optional[float] = None


class PlaceCreate(PlaceBase):
    """Body for POST /api/places — id is auto-generated from name+city."""
    pass


class PlaceUpdate(BaseModel):
    """Body for PUT /api/places/{id} — all fields optional."""
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
    """Response model — includes id and timestamps."""
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
    places_included:  Optional[str] = "[]"   # JSON string of place IDs
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
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)   # how many vectors to retrieve


class SourceCard(BaseModel):
    """A single retrieved place shown as a card in the frontend."""
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
    score:              float   # kept for internal filtering; hidden from tourist UI


class ChatResponse(BaseModel):
    answer:  str
    sources: List[SourceCard]
    query:   str


# ===========================================================================
# SYNC schemas
# ===========================================================================

class SyncReport(BaseModel):
    """Returned by POST /api/sync after a sync run."""
    added:             int
    updated:           int
    deleted:           int
    skipped:           int
    total_pinecone:    int
    duration_seconds:  float
    details:           List[str]   # human-readable log lines for the frontend


# ===========================================================================
# HEALTH schemas
# ===========================================================================

class HealthResponse(BaseModel):
    status:          str      # "ok" | "degraded"
    database:        bool
    pinecone:        bool
    embedding_model: bool
    app_version:     str
    environment:     str

# ===========================================================================
# BOOKING AGENT schemas
# ===========================================================================

class BookingAgentRequest(BaseModel):
    """Sent by the tourist frontend for every message in a booking session."""
    session_id:  str
    message:     str                    = Field(..., min_length=1, max_length=2000)
    place_id:    Optional[str]  = None  # only on the very first call (Book button)
    place_name:  Optional[str]  = None  # only on the very first call


class BookingAgentResponse(BaseModel):
    """Reply from the booking agent."""
    session_id:  str
    reply:       str
    state:       str    # idle | collecting_* | confirming | completed
    booking_id:  Optional[str] = None   # set only when state == "completed"
    summary:     Optional[dict] = None  # set when state == "confirming"


# ===========================================================================
# BOOKING CRUD schemas
# ===========================================================================

class BookingCreate(BaseModel):
    place_id:         Optional[str]  = None
    package_id:       Optional[str]  = None
    place_name:       str
    customer_name:    str
    customer_phone:   str
    customer_email:   Optional[str]  = ""
    travel_date:      str
    number_of_people: int             = Field(default=1, ge=1)
    notes:            Optional[str]  = ""


class BookingStatusUpdate(BaseModel):
    status: str   # pending | confirmed | cancelled | completed


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