"""
Database setup — SQLAlchemy 2.x with SQLite.

Creates the engine, session factory, and ORM base.
Tables are created automatically on first run.
The database file lives in the configured data directory.
"""

import logging
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger("labmate.database")


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Practical(Base):
    """
    A saved practical document.

    Stores the original question, generation metadata,
    and the structured content sections as a JSON string.
    """
    __tablename__ = "practicals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(200), nullable=False, index=True)
    practical_number = Column(String(20), nullable=True)
    title = Column(String(500), nullable=False)
    question = Column(Text, nullable=False)
    language = Column(String(50), nullable=True)
    # Sections stored as JSON string:
    # {"aim": "...", "theory": "...", "code": "...", ...}
    sections_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Practical id={self.id} subject='{self.subject}' title='{self.title[:30]}'>"


# ---------------------------------------------------------------------------
# Engine and session setup
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    data_dir = Path(settings.database_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Data directory ready: %s", data_dir.resolve())


def create_db_engine():
    """Create and return the SQLAlchemy engine."""
    _ensure_data_dir()
    engine = create_engine(
        settings.database_url,
        echo=settings.app_debug,
        connect_args={"check_same_thread": False},  # Required for SQLite
    )
    return engine


def init_db(engine):
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized: %s", settings.database_path)


def get_session_factory(engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
