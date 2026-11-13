"""Database wiring for the menu service.

Provides the SQLAlchemy declarative `Base`, the engine and session factory,
and `get_session`, a FastAPI dependency that yields one session per request.
The URL comes from the DATABASE_URL environment variable (PostgreSQL in
deployment, e.g. postgresql+psycopg://...) and defaults to a local SQLite
file for development. `init_db` creates tables from the models; a real
deployment should replace it with migrations. Tests override `get_session`
with an in-memory database so nothing here needs a running server.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session


def init_db():
    from app import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
