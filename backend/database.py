import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


BACKEND_DIR = Path(__file__).resolve().parent


def _resolve_database_url() -> str:
    url = get_settings().database_url or os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
     # ✅ YEH LINE ADD KARO — Render ki zarurat hai
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if not url.startswith("sqlite:///"):
        return url

    path_part = url.replace("sqlite:///", "", 1)
    is_windows_abs = len(path_part) > 2 and path_part[1:3] in {":/", ":\\"}
    if path_part.startswith("/") or is_windows_abs:
        return url

    clean_path = path_part[2:] if path_part.startswith("./") else path_part
    db_path = BACKEND_DIR / clean_path
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = _resolve_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_booking_columns():
    """Keep older local SQLite DBs compatible with the current Booking model."""
    inspector = inspect(engine)
    if "bookings" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("bookings")}
    required_columns = {
        "user_name": "VARCHAR DEFAULT ''",
        "user_email": "VARCHAR DEFAULT ''",
        "booking_date": "VARCHAR DEFAULT ''",
        "place_id": "VARCHAR",
        "package_id": "VARCHAR",
        "place_name": "VARCHAR DEFAULT ''",
        "customer_name": "VARCHAR DEFAULT ''",
        "customer_phone": "VARCHAR DEFAULT ''",
        "customer_email": "VARCHAR DEFAULT ''",
        "travel_date": "VARCHAR DEFAULT ''",
        "number_of_people": "INTEGER DEFAULT 1",
        "notes": "TEXT DEFAULT ''",
        "status": "VARCHAR DEFAULT 'pending'",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing:
                connection.execute(
                    text(f"ALTER TABLE bookings ADD COLUMN {column_name} {column_type}")
                )
                print(f"Added missing bookings.{column_name} column")


def init_db():
    from models import db_models  # noqa: F401

    os.makedirs(BACKEND_DIR / "data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_booking_columns()
    print("Database tables initialised")
