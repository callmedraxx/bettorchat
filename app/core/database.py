"""
Database connection and session management.
Uses in-memory store for development, PostgreSQL for production.
"""
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# In-memory database for development
if settings.ENVIRONMENT == "development" or not settings.DATABASE_URL:
    # Use SQLite in-memory for development
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
else:
    # Use PostgreSQL for production
    SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Session:
    """
    Dependency for getting database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

