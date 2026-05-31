"""
seed.py — Import tourism_seed.csv into SQLite

Run once to populate the database before your first sync:
    python seed.py

Run again safely — it will SKIP existing records by default.
Pass --reset to wipe and re-import everything:
    python seed.py --reset
"""

import sys
import os
import re
import json
import pandas as pd
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Make sure Python can find our app modules regardless of where you run this
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from database import engine, init_db, SessionLocal
from models.db_models import Place, TourPackage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow():
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    """Convert 'Lahore Fort' → 'lahore-fort'"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe_json(value, fallback="[]") -> str:
    """
    Ensure tags are stored as a valid JSON string.
    Handles cases where CSV has: ["mughal","fort"]  or  mughal,fort  or empty
    """
    if pd.isna(value) or value == "":
        return fallback
    if isinstance(value, str) and value.startswith("["):
        try:
            json.loads(value)   # validate it
            return value
        except json.JSONDecodeError:
            pass
    # Treat as comma-separated plain text
    tags = [t.strip() for t in str(value).split(",") if t.strip()]
    return json.dumps(tags)


def _safe_float(value, fallback=None):
    try:
        return float(value) if not pd.isna(value) else fallback
    except Exception:
        return fallback


def _safe_str(value, fallback="") -> str:
    if pd.isna(value):
        return fallback
    return str(value).strip()


# ---------------------------------------------------------------------------
# Core seeding function
# ---------------------------------------------------------------------------

def seed_places(db, df: pd.DataFrame, reset: bool) -> tuple[int, int, int]:
    """
    Insert place rows from DataFrame into SQLite.

    Returns: (inserted, skipped, updated)
    """
    inserted = skipped = updated = 0

    for _, row in df.iterrows():

        # Use CSV id column if present, otherwise generate from name+city
        if "id" in row and not pd.isna(row["id"]) and str(row["id"]).strip():
            place_id = str(row["id"]).strip()
        else:
            place_id = _slugify(f"{row['name']}-{row['city']}")

        existing = db.get(Place, place_id)

        if existing and not reset:
            skipped += 1
            continue

        if existing and reset:
            db.delete(existing)
            db.flush()

        place = Place(
            id                 = place_id,
            name               = _safe_str(row.get("name")),
            city               = _safe_str(row.get("city")),
            province           = _safe_str(row.get("province")),
            category           = _safe_str(row.get("category")),
            description        = _safe_str(row.get("description")),
            history            = _safe_str(row.get("history")),
            entry_fee          = _safe_str(row.get("entry_fee"), "Free"),
            opening_hours      = _safe_str(row.get("opening_hours"), "Open daily"),
            best_time_to_visit = _safe_str(row.get("best_time_to_visit")),
            image_url          = _safe_str(row.get("image_url")),
            map_url            = _safe_str(row.get("map_url")),
            latitude           = _safe_float(row.get("latitude")),
            longitude          = _safe_float(row.get("longitude")),
            tags               = _safe_json(row.get("tags")),
            created_at         = _utcnow(),
            updated_at         = _utcnow(),
        )

        db.add(place)

        if reset and existing:
            updated += 1
        else:
            inserted += 1

    db.commit()
    return inserted, skipped, updated


# ---------------------------------------------------------------------------
# Optional: seed tour packages from a second CSV or hardcoded defaults
# ---------------------------------------------------------------------------

SAMPLE_PACKAGES = [
    {
        "id":               "lahore-heritage-2day",
        "title":            "Lahore Heritage Weekend",
        "description":      "Explore Lahore's finest Mughal monuments — Lahore Fort, Badshahi Mosque, and Shalimar Gardens — in a curated 2-day itinerary with a local guide.",
        "price":            8500.0,
        "duration_days":    2,
        "places_included":  json.dumps(["lahore-fort", "badshahi-mosque", "shalimar-gardens"]),
        "tags":             json.dumps(["mughal", "heritage", "lahore", "guided"]),
    },
    {
        "id":               "northern-pakistan-7day",
        "title":            "Northern Pakistan Explorer (7 Days)",
        "description":      "Journey from Hunza Valley through Attabad Lake to Fairy Meadows for a Nanga Parbat sunrise. Pakistan's most iconic northern route.",
        "price":            65000.0,
        "duration_days":    7,
        "places_included":  json.dumps(["hunza-valley", "attabad-lake", "fairy-meadows"]),
        "tags":             json.dumps(["northern", "mountains", "adventure", "nature"]),
    },
    {
        "id":               "k2-basecamp-trek-14day",
        "title":            "K2 Base Camp Trek (14 Days)",
        "description":      "The legendary Baltoro Glacier trek to K2 Base Camp at 5150m. Includes Concordia viewpoint and Gasherbrum views. For experienced trekkers.",
        "price":            145000.0,
        "duration_days":    14,
        "places_included":  json.dumps(["k2-basecamp"]),
        "tags":             json.dumps(["k2", "trekking", "adventure", "baltoro", "expert"]),
    },
]


def seed_packages(db, reset: bool) -> tuple[int, int]:
    inserted = skipped = 0

    for pkg_data in SAMPLE_PACKAGES:
        existing = db.get(TourPackage, pkg_data["id"])

        if existing and not reset:
            skipped += 1
            continue

        if existing and reset:
            db.delete(existing)
            db.flush()

        pkg = TourPackage(
            **pkg_data,
            created_at = _utcnow(),
            updated_at = _utcnow(),
        )
        db.add(pkg)
        inserted += 1

    db.commit()
    return inserted, skipped


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    reset = "--reset" in sys.argv

    print("=" * 55)
    print("  WanderRAG — Database Seeder")
    print("=" * 55)

    if reset:
        print("⚠️  --reset flag detected: existing records will be replaced\n")

    # 1. Initialise database tables
    init_db()

    # 2. Load CSV
    csv_path = os.path.join(os.path.dirname(__file__), "data", "tourism_seed.csv")
    if not os.path.exists(csv_path):
        print(f"❌ CSV not found at: {csv_path}")
        print("   Make sure data/tourism_seed.csv exists before running seed.py")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    print(f"📄 Loaded {len(df)} rows from tourism_seed.csv\n")

    db = SessionLocal()

    try:
        # 3. Seed places
        print("📍 Seeding places...")
        ins, skp, upd = seed_places(db, df, reset)
        print(f"   ✅ Inserted : {ins}")
        print(f"   ⏭️  Skipped  : {skp}  (already exist — use --reset to overwrite)")
        print(f"   🔄 Replaced : {upd}\n")

        # 4. Seed tour packages
        print("📦 Seeding tour packages...")
        pkg_ins, pkg_skp = seed_packages(db, reset)
        print(f"   ✅ Inserted : {pkg_ins}")
        print(f"   ⏭️  Skipped  : {pkg_skp}\n")

        # 5. Summary
        total_places   = db.query(Place).count()
        total_packages = db.query(TourPackage).count()

        print("=" * 55)
        print(f"  Database now contains:")
        print(f"    📍 Places        : {total_places}")
        print(f"    📦 Tour packages : {total_packages}")
        print("=" * 55)
        print()
        print("✅ Seeding complete!")
        print()
        print("Next steps:")
        print("  1. Start the server  →  uvicorn main:app --reload --port 8000")
        print("  2. Open browser      →  http://localhost:8000")
        print("  3. Click 'Sync Tourism Data' to embed all records into Pinecone")
        print()

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seeding failed: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()