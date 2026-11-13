"""Repository contract tests shared by every ZoneRepository implementation.

The same behavioural contract is run against ``InMemoryZoneRepository``
always, and against ``PostgisZoneRepository`` when the ``TEST_DATABASE_URL``
environment variable points at a disposable PostGIS database (the fixture
applies ``migrations/0001_create_zones.sql`` and truncates ``zones`` between
tests). The ``repository`` fixture yields each implementation in turn. Tests
cover the acceptance rule that a deactivated zone no longer covers points,
point-on-edge coverage, case-insensitive name uniqueness, the active-zone
no-overlap rule (edges may touch), editing a zone, idempotent deactivation,
not-found errors, and list filtering. ``_square`` builds a MultiPolygon square
from its south-west corner.
"""

import os
import pathlib
import uuid

import pytest
from shapely.geometry import MultiPolygon, box

from app.zones.errors import ZoneConflictError, ZoneNotFoundError
from app.zones.repository import InMemoryZoneRepository

MIGRATION = pathlib.Path(__file__).parent.parent / "migrations" / "0001_create_zones.sql"


def _square(lng: float, lat: float, size: float = 0.01) -> MultiPolygon:
    return MultiPolygon([box(lng, lat, lng + size, lat + size)])


def _postgis_repository():
    from sqlalchemy import create_engine, text

    from app.zones.postgis_repository import PostgisZoneRepository

    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as conn:
        conn.exec_driver_sql(MIGRATION.read_text())
        conn.execute(text("TRUNCATE zones"))
    return PostgisZoneRepository(engine)


@pytest.fixture(params=["memory", "postgis"])
def repository(request):
    if request.param == "memory":
        return InMemoryZoneRepository()
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL not set; PostGIS contract tests skipped")
    return _postgis_repository()


def test_deactivated_zone_no_longer_covers_points(repository):
    zone = repository.create("Indiranagar", _square(77.59, 12.97))
    assert repository.find_active_covering(lng=77.595, lat=12.975).id == zone.id

    deactivated = repository.deactivate(zone.id)

    assert deactivated.is_active is False and deactivated.deactivated_at is not None
    assert repository.find_active_covering(lng=77.595, lat=12.975) is None


def test_point_on_edge_is_covered(repository):
    zone = repository.create("Edge", _square(0, 0))
    assert repository.find_active_covering(lng=0, lat=0.005).id == zone.id


def test_point_outside_all_zones_is_not_covered(repository):
    repository.create("Somewhere", _square(0, 0))
    assert repository.find_active_covering(lng=5, lat=5) is None


def test_name_unique_case_insensitive(repository):
    repository.create("Whitefield", _square(0, 0))
    with pytest.raises(ZoneConflictError):
        repository.create("WHITEFIELD", _square(1, 1))


def test_overlap_rejected_but_touching_allowed(repository):
    repository.create("A", _square(0, 0))
    with pytest.raises(ZoneConflictError):
        repository.create("B", _square(0.005, 0.005))
    repository.create("C", _square(0.01, 0))


def test_update_changes_name_and_boundary(repository):
    zone = repository.create("Old", _square(0, 0))
    updated = repository.update(zone.id, name="New", boundary=_square(2, 2))
    assert updated.name == "New"
    assert repository.find_active_covering(lng=0.005, lat=0.005) is None
    assert repository.find_active_covering(lng=2.005, lat=2.005).id == zone.id


def test_update_overlap_rejected(repository):
    repository.create("A", _square(0, 0))
    b = repository.create("B", _square(1, 1))
    with pytest.raises(ZoneConflictError):
        repository.update(b.id, boundary=_square(0.005, 0))


def test_inactive_zone_may_be_reshaped_over_active_zone(repository):
    repository.create("A", _square(0, 0))
    b = repository.create("B", _square(1, 1))
    repository.deactivate(b.id)
    repository.update(b.id, boundary=_square(0.005, 0))


def test_deactivate_idempotent(repository):
    zone = repository.create("Z", _square(0, 0))
    first = repository.deactivate(zone.id)
    assert repository.deactivate(zone.id).deactivated_at == first.deactivated_at


def test_missing_zone(repository):
    missing = uuid.uuid4()
    assert repository.get(missing) is None
    with pytest.raises(ZoneNotFoundError):
        repository.update(missing, name="x")
    with pytest.raises(ZoneNotFoundError):
        repository.deactivate(missing)


def test_list_filters(repository):
    a = repository.create("A", _square(0, 0))
    b = repository.create("B", _square(1, 1))
    repository.deactivate(b.id)
    assert [z.id for z in repository.list()] == [a.id, b.id]
    assert [z.id for z in repository.list(is_active=True)] == [a.id]
    assert [z.id for z in repository.list(is_active=False)] == [b.id]
