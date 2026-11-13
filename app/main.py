"""FastAPI application factory for the QuickBites backend.

``create_app`` builds a fresh FastAPI instance, attaches the zone repository
to ``app.state`` and mounts the admin zone router. Callers may inject any
``ZoneRepository`` (tests pass ``InMemoryZoneRepository``); when none is
given, ``_default_zone_repository`` builds a ``PostgisZoneRepository`` from
the ``DATABASE_URL`` environment variable using a pooled SQLAlchemy engine
(``pool_pre_ping`` keeps stale connections from surfacing as 500s). Building
the app through a factory rather than a module-level global keeps tests
isolated and makes it easy to add further capability routers later. Serve it
with ``uvicorn app.main:create_app --factory`` so that no database engine is
created merely by importing this module.
"""

import os

from fastapi import FastAPI
from sqlalchemy import create_engine

from app.zones.postgis_repository import PostgisZoneRepository
from app.zones.repository import ZoneRepository
from app.zones.router import router as zones_router


def _default_zone_repository() -> ZoneRepository:
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return PostgisZoneRepository(engine)


def create_app(zone_repository: ZoneRepository | None = None) -> FastAPI:
    app = FastAPI(title="QuickBites API", version="0.1.0")
    app.state.zone_repository = zone_repository or _default_zone_repository()
    app.include_router(zones_router)
    return app
