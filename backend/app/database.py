"""
FAZ 3: SQLite & SQLAlchemy ORM Veritabanı Bağlantısı (database.py)
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency Injection için veritabanı oturumu üreteci."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
