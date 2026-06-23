from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, UniqueConstraint
from database import Base


# ---------------------------------------------------------------------------
# Helper: current UTC time. Used as default for timestamp columns.
# ---------------------------------------------------------------------------
def _utcnow():
    return datetime.now(timezone.utc)


# ===========================================================================
# PLACES
# Core tourism entity. Every field that a visitor would want to know.
# ===========================================================================
class Place(Base):
    __tablename__ = "places"

    # Stable human-readable slug: "lahore-fort", "badshahi-mosque"
    # Generated at insert time. Never changes — safe as Pinecone vector ID.
    id = Column(String, primary_key=True, index=True)

    # --- Identity ---
    name        = Column(String, nullable=False)
    city        = Column(String, nullable=False, index=True)
    province    = Column(String, nullable=False, index=True)
    category    = Column(String, nullable=False, index=True)  # historical/nature/food/etc.

    # --- Descriptive fields (go into the DESCRIPTIVE embedding chunk) ---
    description = Column(Text, default="")
    history     = Column(Text, default="")
    tags        = Column(Text, default="[]")   # stored as JSON string: '["mughal","fort"]'

    # --- Factual fields (go into the FACTUAL embedding chunk) ---
    entry_fee         = Column(String, default="Free")
    opening_hours     = Column(String, default="Open daily")
    best_time_to_visit = Column(String, default="")

    # --- Media & location ---
    image_url  = Column(String, default="")
    map_url    = Column(String, default="")
    latitude   = Column(Float,  nullable=True)
    longitude  = Column(Float,  nullable=True)

    # --- Audit ---
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<Place id={self.id!r} name={self.name!r} city={self.city!r}>"


# ===========================================================================
# TOUR PACKAGES
# Bundled itineraries referencing multiple places.
# ===========================================================================
class TourPackage(Base):
    __tablename__ = "tour_packages"

    id              = Column(String, primary_key=True, index=True)
    title           = Column(String, nullable=False)
    description     = Column(Text, default="")
    price           = Column(Float, default=0.0)         # PKR
    duration_days   = Column(Integer, default=1)
    places_included = Column(Text, default="[]")         # JSON list of place IDs
    tags            = Column(Text, default="[]")

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<TourPackage id={self.id!r} title={self.title!r}>"


# ===========================================================================
# BOOKINGS  (Phase 3 ready — table exists now, routes added later)
# ===========================================================================
# Replace the existing Booking class with this:

class Booking(Base):
    __tablename__ = "bookings"

    # Human-readable reference: WR-A1B2C3D4
    id               = Column(String, primary_key=True, index=True)

    # Legacy columns kept for compatibility with older local SQLite tables.
    # New code uses the customer_* and travel_date fields below.
    user_name        = Column(String, nullable=False, default="")
    user_email       = Column(String, nullable=False, default="")
    booking_date     = Column(String, nullable=False, default="")

    # What is being booked (one of these will be set)
    place_id         = Column(String, nullable=True, index=True)
    package_id       = Column(String, nullable=False, default="", index=True)
    place_name       = Column(String, nullable=False, default="")

    # Customer details
    customer_name    = Column(String, nullable=False)
    customer_phone   = Column(String, nullable=False)
    customer_email   = Column(String, default="")

    # Trip details
    travel_date      = Column(String, nullable=False)
    number_of_people = Column(Integer, default=1)
    notes            = Column(Text, default="")

    # Workflow status
    status           = Column(String, default="pending")
    # pending | confirmed | cancelled | completed

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<Booking {self.id!r} {self.customer_name!r} → {self.place_name!r}>"

# ===========================================================================
# RECORD HASHES  — the brain of the incremental sync system
#
# One row per (record_id, chunk_type) pair.
# chunk_type is either "desc" or "facts" (for places)
# or "package" (for tour packages).
#
# Why two rows per place?
#   Changing entry_fee should NOT re-embed the rich historical description.
#   Splitting into two chunks means only the changed chunk is re-embedded.
#
# Pinecone vector ID convention:
#   "{record_id}_desc"    e.g. "lahore-fort_desc"
#   "{record_id}_facts"   e.g. "lahore-fort_facts"
#   "{record_id}_package" e.g. "hunza-3day_package"
# ===========================================================================
class RecordHash(Base):
    __tablename__ = "record_hashes"

    # Composite primary key: one row per (record, chunk)
    record_id   = Column(String, primary_key=True)
    chunk_type  = Column(String, primary_key=True)  # "desc" | "facts" | "package"

    record_type  = Column(String, nullable=False)   # "place" | "package"
    content_hash = Column(String, nullable=False)   # MD5 of the text that was embedded
    vector_id    = Column(String, nullable=False)   # Pinecone vector ID stored here

    last_synced_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("record_id", "chunk_type", name="uq_record_chunk"),
    )

    def __repr__(self):
        return (
            f"<RecordHash record_id={self.record_id!r} "
            f"chunk_type={self.chunk_type!r} hash={self.content_hash[:8]!r}...>"
        )


# ── Existing imports aur models ke baad add karo ──────────

class ChatSession(Base):
    """
    Har user ka ek session hota hai.
    Session ID frontend se aata hai (localStorage mein store hota hai).
    """
    __tablename__ = "chat_sessions"

    id            = Column(String, primary_key=True)   # UUID
    title         = Column(String, default="New Chat") # pehle message se auto-set
    created_at    = Column(DateTime(timezone=True), default=_utcnow)
    updated_at    = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    is_summarized = Column(Integer, default=0)         # 0=no, 1=yes
    summary       = Column(Text, default="")           # summarized history


class ChatMessage(Base):
    """
    Har session ke messages store hote hain.
    role: 'user' ya 'assistant'
    """
    __tablename__ = "chat_messages"

    id         = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    role       = Column(String, nullable=False)   # 'user' | 'assistant'
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Konse Pinecone sources use hue is answer ke liye
    sources_json = Column(Text, default="[]")


class UserMemory(Base):
    """
    Long-term user preferences.
    Ek session se sikhke store hote hain — agli baar use hote hain.

    Examples:
      key='destination_interest', value='northern pakistan, mountains'
      key='travel_budget',        value='medium (PKR 20,000-50,000)'
      key='travel_style',         value='family with kids'
      key='preferred_region',     value='Punjab, Gilgit-Baltistan'
    """
    __tablename__ = "user_memory"

    id         = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    key        = Column(String, nullable=False)
    value      = Column(Text, nullable=False)
    confidence = Column(String, default="high")  # high | medium | low
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("session_id", "key", name="uq_session_memory_key"),
    )