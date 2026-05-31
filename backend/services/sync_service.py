import hashlib
import json
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models.db_models import Place, TourPackage, RecordHash
from services.embedding_service import get_embedding_service
from services.pinecone_service import get_pinecone_service


# ===========================================================================
# TEXT BUILDERS
# These functions produce the exact text that gets embedded.
# The hash is calculated from this text — so any field change = new hash.
#
# SPLIT STRATEGY (field-level change detection):
#
#   DESCRIPTIVE chunk ("_desc"):
#     name, city, province, category, description, history, tags
#     → Rich semantic content. Changes rarely.
#
#   FACTUAL chunk ("_facts"):
#     entry_fee, opening_hours, best_time_to_visit
#     → Operational info. Changes more often (price updates, hours).
#
# Result: updating entry_fee only re-embeds _facts. The heavy descriptive
#         embedding is untouched. This is the core efficiency of this system.
# ===========================================================================

def build_desc_text(place: Place) -> str:
    """Descriptive embedding text for a place."""
    tags = _parse_tags(place.tags)
    return (
        f"Place: {place.name}\n"
        f"Location: {place.city}, {place.province}\n"
        f"Category: {place.category}\n"
        f"Description: {place.description}\n"
        f"History: {place.history}\n"
        f"Tags: {', '.join(tags)}"
    ).strip()


def build_facts_text(place: Place) -> str:
    """Factual embedding text for a place."""
    return (
        f"Place: {place.name}\n"
        f"Entry Fee: {place.entry_fee}\n"
        f"Opening Hours: {place.opening_hours}\n"
        f"Best Time to Visit: {place.best_time_to_visit}"
    ).strip()


def build_package_text(pkg: TourPackage) -> str:
    """Single embedding text for a tour package."""
    tags = _parse_tags(pkg.tags)
    return (
        f"Tour Package: {pkg.title}\n"
        f"Description: {pkg.description}\n"
        f"Price: PKR {pkg.price:,.0f}\n"
        f"Duration: {pkg.duration_days} days\n"
        f"Tags: {', '.join(tags)}"
    ).strip()


def _parse_tags(tags_str: str) -> list[str]:
    try:
        return json.loads(tags_str or "[]")
    except Exception:
        return []


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ===========================================================================
# MAIN SYNC FUNCTION
# ===========================================================================

def run_incremental_sync(db: Session) -> dict:
    """
    Compares every place and package in the database against the stored hashes.
    Only changed or new records are re-embedded and upserted to Pinecone.
    Deleted records are removed from Pinecone.

    Returns a report dict with counts and log lines.
    """
    start_time = time.time()

    embedder = get_embedding_service()
    pinecone  = get_pinecone_service()

    # Counters
    added   = 0
    updated = 0
    deleted = 0
    skipped = 0
    details = []   # human-readable log lines shown in frontend

    # ------------------------------------------------------------------
    # STEP 1: Load all stored hashes from DB into a fast lookup dict
    #   key:  (record_id, chunk_type)
    #   value: RecordHash row
    # ------------------------------------------------------------------
    stored_hashes: dict[tuple, RecordHash] = {
        (rh.record_id, rh.chunk_type): rh
        for rh in db.query(RecordHash).all()
    }

    # Track which (record_id, chunk_type) pairs we see in this sync run.
    # Anything in stored_hashes but NOT in seen_keys was deleted.
    seen_keys: set[tuple] = set()

    # Collect all vectors to upsert in one batch call
    vectors_to_upsert: list[dict] = []
    hash_rows_to_save: list[dict] = []   # new/updated RecordHash data

    # ------------------------------------------------------------------
    # STEP 2: Process all PLACES
    # ------------------------------------------------------------------
    places = db.query(Place).all()
    details.append(f"📍 Found {len(places)} places in database")

    for place in places:
        for chunk_type, text_fn, chunk_label in [
            ("desc",  build_desc_text,  "descriptive"),
            ("facts", build_facts_text, "factual"),
        ]:
            vector_id = f"{place.id}_{chunk_type}"
            text      = text_fn(place)
            new_hash  = _md5(text)
            key       = (place.id, chunk_type)

            seen_keys.add(key)
            existing  = stored_hashes.get(key)

            if existing is None:
                # --- ADDED: new place, never synced before ---
                vectors_to_upsert.append(_make_vector(vector_id, text, embedder, place))
                hash_rows_to_save.append(_make_hash_row(place.id, chunk_type, "place", new_hash, vector_id))
                added += 1
                details.append(f"  ➕ ADDED   [{chunk_label}] {place.name} ({place.id})")

            elif existing.content_hash != new_hash:
                # --- UPDATED: this specific chunk changed ---
                vectors_to_upsert.append(_make_vector(vector_id, text, embedder, place))
                hash_rows_to_save.append(_make_hash_row(place.id, chunk_type, "place", new_hash, vector_id))
                updated += 1
                details.append(f"  🔄 UPDATED [{chunk_label}] {place.name} ({place.id})")

            else:
                # --- SKIPPED: hash identical, nothing to do ---
                skipped += 1

    # ------------------------------------------------------------------
    # STEP 3: Process all TOUR PACKAGES (single chunk per package)
    # ------------------------------------------------------------------
    packages = db.query(TourPackage).all()
    details.append(f"📦 Found {len(packages)} tour packages in database")

    for pkg in packages:
        vector_id = f"{pkg.id}_package"
        text      = build_package_text(pkg)
        new_hash  = _md5(text)
        key       = (pkg.id, "package")

        seen_keys.add(key)
        existing  = stored_hashes.get(key)

        if existing is None:
            vectors_to_upsert.append(_make_package_vector(vector_id, text, embedder, pkg))
            hash_rows_to_save.append(_make_hash_row(pkg.id, "package", "package", new_hash, vector_id))
            added += 1
            details.append(f"  ➕ ADDED   [package] {pkg.title} ({pkg.id})")

        elif existing.content_hash != new_hash:
            vectors_to_upsert.append(_make_package_vector(vector_id, text, embedder, pkg))
            hash_rows_to_save.append(_make_hash_row(pkg.id, "package", "package", new_hash, vector_id))
            updated += 1
            details.append(f"  🔄 UPDATED [package] {pkg.title} ({pkg.id})")

        else:
            skipped += 1

    # ------------------------------------------------------------------
    # STEP 4: Detect DELETED records
    # Anything in stored_hashes that we did NOT see = was deleted from DB
    # ------------------------------------------------------------------
    deleted_vector_ids = []
    deleted_keys       = set(stored_hashes.keys()) - seen_keys

    for (record_id, chunk_type) in deleted_keys:
        rh = stored_hashes[(record_id, chunk_type)]
        deleted_vector_ids.append(rh.vector_id)
        db.delete(rh)
        deleted += 1
        details.append(f"  🗑️  DELETED [{chunk_type}] record_id={record_id}")

    # ------------------------------------------------------------------
    # STEP 5: Batch upsert changed vectors to Pinecone
    # ------------------------------------------------------------------
    if vectors_to_upsert:
        details.append(f"⬆️  Upserting {len(vectors_to_upsert)} vectors to Pinecone...")
        pinecone.upsert_vectors(vectors_to_upsert)

    # ------------------------------------------------------------------
    # STEP 6: Delete removed vectors from Pinecone
    # ------------------------------------------------------------------
    if deleted_vector_ids:
        details.append(f"🗑️  Deleting {len(deleted_vector_ids)} vectors from Pinecone...")
        pinecone.delete_vectors(deleted_vector_ids)

    # ------------------------------------------------------------------
    # STEP 7: Persist updated hashes to DB
    # ------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    for row in hash_rows_to_save:
        existing_row = db.get(RecordHash, (row["record_id"], row["chunk_type"]))
        if existing_row:
            existing_row.content_hash  = row["content_hash"]
            existing_row.vector_id     = row["vector_id"]
            existing_row.last_synced_at = now
        else:
            db.add(RecordHash(
                record_id      = row["record_id"],
                chunk_type     = row["chunk_type"],
                record_type    = row["record_type"],
                content_hash   = row["content_hash"],
                vector_id      = row["vector_id"],
                last_synced_at = now,
            ))

    db.commit()

    # ------------------------------------------------------------------
    # STEP 8: Build final report
    # ------------------------------------------------------------------
    total_pinecone    = pinecone.get_total_vectors()
    duration_seconds  = round(time.time() - start_time, 2)

    details.append(f"✅ Sync complete in {duration_seconds}s")
    details.append(f"   Added: {added} | Updated: {updated} | Deleted: {deleted} | Skipped: {skipped}")
    details.append(f"   Total vectors in Pinecone: {total_pinecone}")

    # Print to terminal for development visibility
    for line in details:
        print(line)

    return {
        "added":            added,
        "updated":          updated,
        "deleted":          deleted,
        "skipped":          skipped,
        "total_pinecone":   total_pinecone,
        "duration_seconds": duration_seconds,
        "details":          details,
    }


# ===========================================================================
# PRIVATE HELPERS
# ===========================================================================

def _make_vector(vector_id: str, text: str, embedder, place: Place) -> dict:
    """Build a Pinecone-ready vector dict for a place chunk."""
    return {
        "id":     vector_id,
        "values": embedder.embed(text),
        "metadata": {
            "record_id":   place.id,
            "record_type": "place",
            "chunk_type":  vector_id.split("_")[-1],
            "name":        place.name,
            "city":        place.city,
            "province":    place.province,
            "category":    place.category,
            "entry_fee":   place.entry_fee,
            "image_url":   place.image_url,
        },
    }


def _make_package_vector(vector_id: str, text: str, embedder, pkg: TourPackage) -> dict:
    """Build a Pinecone-ready vector dict for a tour package."""
    return {
        "id":     vector_id,
        "values": embedder.embed(text),
        "metadata": {
            "record_id":    pkg.id,
            "record_type":  "package",
            "chunk_type":   "package",
            "name":         pkg.title,
            "price":        pkg.price,
            "duration_days": pkg.duration_days,
        },
    }


def _make_hash_row(
    record_id: str,
    chunk_type: str,
    record_type: str,
    content_hash: str,
    vector_id: str,
) -> dict:
    return {
        "record_id":    record_id,
        "chunk_type":   chunk_type,
        "record_type":  record_type,
        "content_hash": content_hash,
        "vector_id":    vector_id,
    }