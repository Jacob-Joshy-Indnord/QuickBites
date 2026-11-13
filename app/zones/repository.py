"""Zone persistence contract and an in-memory implementation.

``ZoneRepository`` is the Protocol every zone store implements. Its methods
are: ``create`` (insert a new active zone), ``update`` (change name and/or
boundary), ``deactivate`` (soft-delete; idempotent), ``get`` (fetch by id or
None), ``list`` (all zones, optionally filtered by active flag) and
``find_active_covering`` (the active zone covering a lng/lat point, or None).
``create`` and ``update`` must enforce case-insensitive name uniqueness and
the active-zone no-overlap rule atomically, raising ``ZoneConflictError``.
``InMemoryZoneRepository`` implements the contract with a dict guarded by a
lock; it backs the unit tests and local development, mirroring
``PostgisZoneRepository`` semantics exactly.
"""

import threading
import uuid
from dataclasses import replace
from typing import Protocol

from shapely.geometry import MultiPolygon

from app.zones.errors import ZoneConflictError, ZoneNotFoundError
from app.zones.geometry import covers_point, interiors_overlap
from app.zones.models import Zone, utcnow


class ZoneRepository(Protocol):
    def create(self, name: str, boundary: MultiPolygon) -> Zone: ...

    def update(
        self, zone_id: uuid.UUID, name: str | None = None, boundary: MultiPolygon | None = None
    ) -> Zone: ...

    def deactivate(self, zone_id: uuid.UUID) -> Zone: ...

    def get(self, zone_id: uuid.UUID) -> Zone | None: ...

    def list(self, is_active: bool | None = None) -> list[Zone]: ...

    def find_active_covering(self, lng: float, lat: float) -> Zone | None: ...


class InMemoryZoneRepository:
    def __init__(self) -> None:
        self._zones: dict[uuid.UUID, Zone] = {}
        self._lock = threading.Lock()

    def _check_conflicts(
        self, name: str, boundary: MultiPolygon, check_overlap: bool, exclude: uuid.UUID | None
    ) -> None:
        for other in self._zones.values():
            if other.id == exclude:
                continue
            if other.name.casefold() == name.casefold():
                raise ZoneConflictError(f"a zone named {other.name!r} already exists")
            if check_overlap and other.is_active and interiors_overlap(other.boundary, boundary):
                raise ZoneConflictError(f"boundary overlaps active zone {other.id}")

    def create(self, name: str, boundary: MultiPolygon) -> Zone:
        with self._lock:
            self._check_conflicts(name, boundary, check_overlap=True, exclude=None)
            now = utcnow()
            zone = Zone(uuid.uuid4(), name, boundary, True, now, now, None)
            self._zones[zone.id] = zone
            return zone

    def update(
        self, zone_id: uuid.UUID, name: str | None = None, boundary: MultiPolygon | None = None
    ) -> Zone:
        with self._lock:
            current = self._zones.get(zone_id)
            if current is None:
                raise ZoneNotFoundError(str(zone_id))
            updated = replace(
                current,
                name=name if name is not None else current.name,
                boundary=boundary if boundary is not None else current.boundary,
                updated_at=utcnow(),
            )
            self._check_conflicts(
                updated.name, updated.boundary, check_overlap=updated.is_active, exclude=zone_id
            )
            self._zones[zone_id] = updated
            return updated

    def deactivate(self, zone_id: uuid.UUID) -> Zone:
        with self._lock:
            current = self._zones.get(zone_id)
            if current is None:
                raise ZoneNotFoundError(str(zone_id))
            if not current.is_active:
                return current
            now = utcnow()
            updated = replace(current, is_active=False, deactivated_at=now, updated_at=now)
            self._zones[zone_id] = updated
            return updated

    def get(self, zone_id: uuid.UUID) -> Zone | None:
        return self._zones.get(zone_id)

    def list(self, is_active: bool | None = None) -> list[Zone]:
        zones = sorted(self._zones.values(), key=lambda z: (z.created_at, str(z.id)))
        if is_active is None:
            return zones
        return [z for z in zones if z.is_active is is_active]

    def find_active_covering(self, lng: float, lat: float) -> Zone | None:
        for zone in self.list(is_active=True):
            if covers_point(zone.boundary, lng, lat):
                return zone
        return None
