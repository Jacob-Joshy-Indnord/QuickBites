"""Shared pytest fixtures for the QuickBites backend test suite.

This module builds isolated FastAPI applications backed by the in-memory zone
repository so the API can be exercised without a live PostGIS server. It
defines ``square`` — a helper returning a closed GeoJSON polygon for an
axis-aligned square given its south-west corner and size — plus the fixtures
``zone_repository`` (a fresh ``InMemoryZoneRepository`` per test), ``app``
(an application whose ``get_current_principal`` dependency is overridden by a
mutable holder), ``as_role`` (a callable switching the caller between
ops_admin, ops_agent or anonymous), ``client`` (a TestClient signed in as an
ops admin by default) and ``zone_service`` (the domain service sharing the
same repository).
"""

import pytest
from fastapi.testclient import TestClient

from app.core.auth import OpsRole, Principal, get_current_principal
from app.main import create_app
from app.zones.repository import InMemoryZoneRepository
from app.zones.service import ZoneService


def square(lng: float, lat: float, size: float = 0.01) -> dict:
    """Closed GeoJSON polygon with south-west corner (lng, lat)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [lng, lat],
            [lng + size, lat],
            [lng + size, lat + size],
            [lng, lat + size],
            [lng, lat],
        ]],
    }


@pytest.fixture
def zone_repository() -> InMemoryZoneRepository:
    return InMemoryZoneRepository()


@pytest.fixture
def _principal_holder() -> dict:
    return {"principal": Principal(subject="idp|admin-1", role=OpsRole.OPS_ADMIN)}


@pytest.fixture
def app(zone_repository, _principal_holder):
    application = create_app(zone_repository=zone_repository)

    def _current_principal() -> Principal:
        principal = _principal_holder["principal"]
        if principal is None:
            return get_current_principal()  # fail closed exactly like production
        return principal

    application.dependency_overrides[get_current_principal] = _current_principal
    return application


@pytest.fixture
def as_role(_principal_holder):
    def _switch(role: OpsRole | None) -> None:
        _principal_holder["principal"] = (
            None if role is None else Principal(subject=f"idp|{role.value}", role=role)
        )

    return _switch


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def zone_service(zone_repository) -> ZoneService:
    return ZoneService(zone_repository)
