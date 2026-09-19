"""
SatQuery AI — SQLAlchemy 2.0 Database Session & Engine
Supports PostgreSQL in production and SQLite for local development/testing.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config import settings

import os
import logging

logger = logging.getLogger("satquery.db")

db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)


class Base(DeclarativeBase):
    pass


def _init_engine():
    global db_url
    if "postgresql" in db_url:
        try:
            test_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2},
                echo=False,
            )
            from sqlalchemy import text
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("[DB] Connected to PostgreSQL successfully.")
            return test_engine
        except Exception as exc:
            logger.warning(f"[DB] PostgreSQL unavailable ({exc}). Using local SQLite.")
            data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app_data"))
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "satquery.db")
            db_url = f"sqlite:///{db_path}"
            return create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                echo=False,
            )
    else:
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        return create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )


engine = _init_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Auto-create tables if missing
try:
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.warning(f"[DB] Table auto-creation notice: {e}")



def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
