"""
Database configuration and session management.

Uses SQLite for local MVP. To switch to PostgreSQL, set the DATABASE_URL
environment variable:
    DATABASE_URL=postgresql+asyncpg://user:password@host/db
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./backtest_research.db")

# SQLite-specific connect_args; ignored by PostgreSQL
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,  # Set True for SQL query logging during development
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once at startup."""
    # Import models to ensure they are registered with Base
    from app.models import experiment  # noqa: F401
    Base.metadata.create_all(bind=engine)
