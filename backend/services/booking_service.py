"""
booking_service.py
Agentic booking assistant — deterministic state machine + Groq NL extraction.

Session flow:
  idle → collecting_name → collecting_phone → collecting_date
       → collecting_people → collecting_notes → confirming → completed

Sessions are kept in memory (reset on server restart).
This is acceptable for a demo/FYP system.
"""

import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from groq import Groq
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.db_models import Booking

settings = get_settings()

# ---------------------------------------------------------------------------
# In-memory session store   { session_id: dict }
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}

REQUIRED = ["place_name", "customer_name", "customer_phone", "travel_date", "number_of_people"]


# ---------------------------------------------------------------------------
# Groq client (lazy singleton)
# ---------------------------------------------------------------------------
_groq: Groq | None = None

def _groq_client() -> Groq:
    global _groq
    if _groq is None:
        _groq = Groq(api_key=settings.groq_api_key)
    return _groq


# ---------------------------------------------------------------------------
# Field extraction via Groq
# Sends a single message → returns a dict of extracted fields.
# ---------------------------------------------------------------------------
def _extract(message: str) -> dict:
    prompt = (
        "Extract travel booking information from the message.\n"
        "Return ONLY a JSON object with these exact keys (null if not found):\n"
        '{"customer_name":null,"customer_phone":null,"customer_email":null,'
        '"travel_date":null,"number_of_people":null,"notes":null}\n\n'
        "Rules:\n"
        "- customer_name: person's full name (string)\n"
        "- customer_phone: phone number (string, keep original format)\n"
        "- customer_email: email address (string)\n"
        "- travel_date: readable date string (e.g. '15 June 2025')\n"
        "- number_of_people: integer count of travellers\n"
        "- notes: any special requests (string)\n"
        "- Return ONLY the JSON object. No explanation.\n\n"
        f'Message: {json.dumps(message)}'
    )
    try:
        resp = _groq_client().chat.completions.create(
            model       = settings.groq_model,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0,
            max_tokens  = 180,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as exc:
        print(f"[BookingAgent] extraction error: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def _new_session(session_id: str, place_id: str | None, place_name: str | None) -> dict:
    return {
        "session_id":      session_id,
        "state":           "collecting_name" if place_name else "collecting_place",
        "place_id":        place_id,
        "place_name":      place_name,
        "customer_name":   None,
        "customer_phone":  None,
        "customer_email":  None,
        "travel_date":     None,
        "number_of_people": None,
        "notes":           None,
        "booking_id":      None,
    }


def _apply_extracted(session: dict, extracted: dict):
    """Merge Groq-extracted fields into session, never overwriting existing values."""
    for field in ["customer_name", "customer_phone", "customer_email",
                  "travel_date", "notes"]:
        val = extracted.get(field)
        if val and not session.get(field):
            session[field] = str(val).strip()

    # number_of_people needs int coercion
    ppl = extracted.get("number_of_people")
    if ppl and not session.get("number_of_people"):
        try:
            session["number_of_people"] = int(ppl)
        except (ValueError, TypeError):
            pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def process_message(
    session_id: str,
    message:    str,
    place_id:   str | None = None,
    place_name: str | None = None,
    db:         Session    = None,
) -> dict:
    """
    Receives one user message and returns the agent's reply + current state.
    """

    # ---------- get or create session ----------
    if session_id not in _sessions:
        _sessions[session_id] = _new_session(session_id, place_id, place_name)
    session = _sessions[session_id]

    # If caller passes a (new) place on a fresh message, update session
    if place_name and not session.get("place_name"):
        session["place_id"]   = place_id
        session["place_name"] = place_name
        session["state"]      = "collecting_name"

    # ---------- guard: already completed ----------
    if session["state"] == "completed":
        return _reply(
            session,
            f"Your booking **{session['booking_id']}** is already confirmed! "
            "Feel free to ask anything else.",
        )

    # ---------- handle confirmation response ----------
    if session["state"] == "confirming":
        return _handle_confirm(session, message, db)

    # ---------- extract fields from user message ----------
    extracted = _extract(message)
    _apply_extracted(session, extracted)

    # Manual fallback: if user is in collecting_place and typed a place name
    if session["state"] == "collecting_place" and not session.get("place_name"):
        session["place_name"] = message.strip()
        session["state"]      = "collecting_name"

    # ---------- ask for the next missing field ----------
    return _ask_next(session)


# ---------------------------------------------------------------------------
# Conversation flow
# ---------------------------------------------------------------------------
def _ask_next(session: dict) -> dict:
    place  = session.get("place_name")
    name   = session.get("customer_name")
    phone  = session.get("customer_phone")
    date   = session.get("travel_date")
    people = session.get("number_of_people")

    if not name:
        session["state"] = "collecting_name"
        intro = f"Great choice! **{place}** is a wonderful destination. 🌟\n\n" if place else ""
        return _reply(session, f"{intro}To get started, what is your **full name**?")

    if not phone:
        session["state"] = "collecting_phone"
        return _reply(session, f"Thanks, **{name}**! 👋\nWhat is your **phone number**?")

    if not date:
        session["state"] = "collecting_date"
        return _reply(session, "What is your **travel date**?\n_(e.g. 20 June 2025)_")

    if not people:
        session["state"] = "collecting_people"
        return _reply(session, f"Got it — **{date}**.\nHow many **people** will be travelling?")

    # All required fields present → show confirmation
    session["state"] = "confirming"
    return _confirmation_reply(session)


def _confirmation_reply(session: dict) -> dict:
    p     = session.get("place_name",      "—")
    name  = session.get("customer_name",   "—")
    phone = session.get("customer_phone",  "—")
    email = session.get("customer_email")  or "Not provided"
    date  = session.get("travel_date",     "—")
    ppl   = session.get("number_of_people","—")
    notes = session.get("notes")           or "None"

    text = (
        "Here's your booking summary 📋\n\n"
        f"🏛️  **Place:** {p}\n"
        f"👤  **Name:** {name}\n"
        f"📞  **Phone:** {phone}\n"
        f"📧  **Email:** {email}\n"
        f"📅  **Date:** {date}\n"
        f"👥  **People:** {ppl}\n"
        f"📝  **Notes:** {notes}\n\n"
        "Does everything look correct?\n"
        "Reply **yes** to confirm, or tell me what to change."
    )
    return {
        **_reply(session, text),
        "summary": {
            "place_name":      p,
            "customer_name":   name,
            "customer_phone":  phone,
            "travel_date":     date,
            "number_of_people": ppl,
        }
    }


def _handle_confirm(session: dict, message: str, db: Session) -> dict:
    """User replied to the confirmation prompt."""
    yes_words = {"yes", "confirm", "book", "ok", "okay", "sure", "correct",
                 "proceed", "go", "go ahead", "book it", "right", "yep", "yup"}

    if any(w in message.lower() for w in yes_words):
        booking_id = _save_booking(session, db)
        session["state"]      = "completed"
        session["booking_id"] = booking_id
        return {
            **_reply(session,
                f"🎉 **Booking Confirmed!**\n\n"
                f"Your reference number is **{booking_id}**.\n"
                f"Our team will contact you at **{session.get('customer_phone')}** "
                f"to confirm your trip to **{session.get('place_name')}**.\n\n"
                "Have a wonderful journey! ✈️"
            ),
            "booking_id": booking_id,
        }

    # User wants to change something — re-extract from their correction
    extracted = _extract(message)
    for field in ["customer_name", "customer_phone", "customer_email",
                  "travel_date", "notes"]:
        val = extracted.get(field)
        if val:
            session[field] = str(val).strip()

    ppl = extracted.get("number_of_people")
    if ppl:
        try:
            session["number_of_people"] = int(ppl)
        except (ValueError, TypeError):
            pass

    session["state"] = "confirming"
    return _confirmation_reply(session)


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------
def _save_booking(session: dict, db: Session) -> str:
    booking_id = f"WR-{uuid.uuid4().hex[:8].upper()}"
    now        = datetime.now(timezone.utc)

    booking = Booking(
        id               = booking_id,
        place_id         = session.get("place_id"),
        package_id       = session.get("package_id") or "",
        place_name       = session.get("place_name", ""),
        user_name        = session.get("customer_name", ""),
        user_email       = session.get("customer_email") or "",
        booking_date     = session.get("travel_date", ""),
        customer_name    = session.get("customer_name", ""),
        customer_phone   = session.get("customer_phone", ""),
        customer_email   = session.get("customer_email") or "",
        travel_date      = session.get("travel_date", ""),
        number_of_people = int(session.get("number_of_people") or 1),
        notes            = session.get("notes") or "",
        status           = "pending",
        created_at       = now,
        updated_at       = now,
    )
    db.add(booking)
    db.commit()
    return booking_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _reply(session: dict, text: str) -> dict:
    return {
        "session_id": session["session_id"],
        "reply":      text,
        "state":      session["state"],
        "booking_id": session.get("booking_id"),
        "summary":    None,
    }


def clear_session(session_id: str):
    _sessions.pop(session_id, None)
