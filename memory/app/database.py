"""Database engine, session factory, and SQLite hardening for the memory store."""

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import logging
import os

DATABASE_URL = os.getenv("MEMORY_DATABASE_URL", "sqlite:///./context.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

logger = logging.getLogger(__name__)

_current_engine = engine
_current_session_factory = SessionLocal


def bind_engine(new_engine) -> None:
    global _current_engine, _current_session_factory
    _current_engine = new_engine
    _current_session_factory = sessionmaker(bind=new_engine)



def _ensure_cart_columns() -> None:
    """Idempotently add columns used by databases created before they existed."""
    with _current_engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(cart_items)")).fetchall()
        column_names = {col[1] for col in columns}

        if "price" not in column_names:
            try:
                conn.execute(text("ALTER TABLE cart_items ADD COLUMN price REAL"))
                conn.commit()
                logging.info("memory | added price column to cart_items")
            except Exception as exc:
                logging.warning(f"memory | could not add price column: {exc}")

        if "url" not in column_names:
            try:
                conn.execute(text("ALTER TABLE cart_items ADD COLUMN url TEXT"))
                conn.commit()
                logging.info("memory | added url column to cart_items")
            except Exception as exc:
                logging.warning(f"memory | could not add url column: {exc}")
        conn.commit()


def _ensure_user_columns() -> None:
    """Idempotently add auth columns to users tables created before they existed."""
    with _current_engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        column_names = {col[1] for col in columns}

        for name, ddl in (
            ("username", "VARCHAR"),
            ("password_hash", "VARCHAR"),
            ("created_at", "DATETIME"),
        ):
            if name not in column_names:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
                    conn.commit()
                    logging.info("memory | added %s column to users", name)
                except Exception as exc:
                    logging.warning(f"memory | could not add {name} column: {exc}")
        conn.commit()


def _ensure_session_columns() -> None:
    """Attach nullable sessions support without invalidating legacy messages."""
    with _current_engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(messages)")).fetchall()
        if columns and "session_id" not in {column[1] for column in columns}:
            try:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN session_id INTEGER NULL")
                )
                conn.commit()
                logging.info("memory | added nullable session_id column to messages")
            except Exception as exc:
                logging.warning("memory | could not add session_id column: %s", exc)
        conn.commit()


def _configure_sqlite() -> None:
    """Apply the local SQLite durability/concurrency defaults."""
    if not _current_engine.url.get_backend_name().startswith("sqlite"):
        return
    with _current_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA busy_timeout = 5000")
        journal_mode = conn.exec_driver_sql("PRAGMA journal_mode = WAL").scalar()
        logging.info(
            "memory | SQLite journal_mode=%s busy_timeout=5000",
            journal_mode,
        )


def _ensure_cart_unique_index() -> None:
    """Deduplicate legacy rows and idempotently add the cart uniqueness guard."""
    with _current_engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM cart_items
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM cart_items
                GROUP BY user_id, item
            )
        """))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_cart_items_user_item "
            "ON cart_items (user_id, item)"
        ))
    logging.info("memory | cart_items user/item index ready")


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA busy_timeout = 5000")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()


def initialize_database() -> None:
    """Create tables (if needed) and apply SQLite hardening. Idempotent."""
    from . import models  # noqa: F401  (registers tables on Base)

    Base.metadata.create_all(bind=_current_engine)
    _ensure_cart_columns()
    _ensure_user_columns()
    _ensure_session_columns()
    _configure_sqlite()
    _ensure_cart_unique_index()
