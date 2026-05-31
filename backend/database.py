import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings


# ─────────────────────────────────────────────────────────────
# SQLite-only pragma — WAL mode + foreign keys
# Sirf SQLite ke liye kaam karta hai
# PostgreSQL par yeh automatically skip ho jaata hai
# kyunki PostgreSQL PRAGMA support nahi karta
# ─────────────────────────────────────────────────────────────
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # PostgreSQL hoga toh yeh check fail hoga aur kuch nahi karega
    if not hasattr(dbapi_connection, "execute"):
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # PostgreSQL ya koi aur DB hoga toh PRAGMA error dega
        # hum silently skip kar dete hain
        pass


class Base(DeclarativeBase):
    pass


BACKEND_DIR = Path(__file__).resolve().parent


def _resolve_database_url() -> str:
    url = (
        get_settings().database_url
        or os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    )

    # Render aur Neon dono "postgres://" dete hain
    # lekin SQLAlchemy ko "postgresql://" chahiye
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Agar PostgreSQL hai toh seedha return karo
    # baaki SQLite path resolution ka kaam nahi
    if not url.startswith("sqlite:///"):
        return url

    # ── SQLite local path fix ─────────────────────────────────
    # Relative path ko absolute path mein convert karta hai
    # taake Windows/Linux dono par sahi kaam kare
    path_part = url.replace("sqlite:///", "", 1)
    is_windows_abs = len(path_part) > 2 and path_part[1:3] in {":/", ":\\"}
    if path_part.startswith("/") or is_windows_abs:
        return url

    clean_path = path_part[2:] if path_part.startswith("./") else path_part
    db_path = BACKEND_DIR / clean_path
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = _resolve_database_url()

IS_SQLITE    = DATABASE_URL.startswith("sqlite")
IS_POSTGRES  = DATABASE_URL.startswith("postgresql")

# ─────────────────────────────────────────────────────────────
# Engine — SQLite aur PostgreSQL ke liye alag settings hain
# ─────────────────────────────────────────────────────────────
if IS_SQLITE:
    # SQLite: check_same_thread zaroori hai FastAPI threads ke liye
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    # PostgreSQL (Render / Neon):
    # check_same_thread nahi chahiye
    # pool_pre_ping — broken connections auto-recover karta hai
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """FastAPI dependency — har request ke liye ek session deta hai."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_booking_columns():
    """
    Purane local SQLite databases ke liye backward compatibility.

    IMPORTANT: Yeh function sirf SQLite par chalta hai.
    PostgreSQL par yeh skip ho jaata hai kyunki:
      1. Neon/Render par fresh DB hoti hai — saare columns pehle se hote hain
      2. PostgreSQL ka ALTER TABLE syntax alag hota hai (DEFAULT inline nahi)
      3. Production mein yeh zaroorat nahi — init_db() sab banata hai
    """
    if IS_POSTGRES:
        # PostgreSQL par skip — fresh DB mein sab columns already hain
        return

    inspector = inspect(engine)
    if "bookings" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("bookings")}

    # SQLite mein missing columns add karo
    # (yeh sirf local development ke liye hai)
    required_columns = {
        "user_name":         "VARCHAR DEFAULT ''",
        "user_email":        "VARCHAR DEFAULT ''",
        "booking_date":      "VARCHAR DEFAULT ''",
        "place_id":          "VARCHAR",
        "package_id":        "VARCHAR",
        "place_name":        "VARCHAR DEFAULT ''",
        "customer_name":     "VARCHAR DEFAULT ''",
        "customer_phone":    "VARCHAR DEFAULT ''",
        "customer_email":    "VARCHAR DEFAULT ''",
        "travel_date":       "VARCHAR DEFAULT ''",
        "number_of_people":  "INTEGER DEFAULT 1",
        "notes":             "TEXT DEFAULT ''",
        "status":            "VARCHAR DEFAULT 'pending'",
        "created_at":        "DATETIME",
        "updated_at":        "DATETIME",
    }

    with engine.begin() as connection:
        for col_name, col_type in required_columns.items():
            if col_name not in existing:
                connection.execute(
                    text(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_type}")
                )
                print(f"  Added missing column: bookings.{col_name}")


def init_db():
    """
    Server start hone par saare tables banata hai.
    SQLite aur PostgreSQL dono par kaam karta hai.
    """
    from models import db_models  # noqa: F401 — models register hote hain Base mein

    # SQLite ke liye data/ folder banao
    # PostgreSQL par yeh skip hota hai — folder ki zaroorat nahi
    if IS_SQLITE:
        os.makedirs(BACKEND_DIR / "data", exist_ok=True)

    Base.metadata.create_all(bind=engine)
    _ensure_booking_columns()

    db_type = "PostgreSQL" if IS_POSTGRES else "SQLite"
    print(f"Database tables initialised ({db_type})")