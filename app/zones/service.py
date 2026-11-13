"""Zone domain service: create, edit, deactivate and resolve points.

``ZoneService`` is the single entry point the HTTP layer (and later the
address-resolution, outlet-assignment and surge modules) uses to work with
zones. It wraps a ``ZoneRepository`` and exposes: ``create_zone`` (new active
zone), ``update_zone`` (rename and/or reshape), ``deactivate_zone`` (soft
delete, idempotent), ``get_zone`` (raises ``ZoneNotFoundError`` when missing),
``list_zones`` (optionally filtered by active flag) and ``resolve_point``,
which returns the active zone covering a latitude/longitude pair or None when
the point is non-serviceable. Because ``resolve_point`` only ever considers
active zones, a deactivated zone stops being serviceable the moment the
deactivation commits — the acceptance scenario of task-ZwUtwpRON0k.
"""

import uuid

from shapely.geometry import MultiPolygon

from app.zones.errors import ZoneNotFoundError
from app.zones.models import Zone
from app.zones.repository import ZoneRepository


class ZoneService:
    def __init__(self, repository: ZoneRepository) -> None:
        self._repository = repository

    def create_zone(self, name: str, boundary: MultiPolygon) -> Zone:
        return self._repository.create(name=name, boundary=boundary)

    def update_zone(
        self, zone_id: uuid.UUID, name: str | None = None, boundary: MultiPolygon | None = None
    ) -> Zone:
        return self._repository.update(zone_id, name=name, boundary=boundary)

    def deactivate_zone(self, zone_id: uuid.UUID) -> Zone:
        return self._repository.deactivate(zone_id)

    def get_zone(self, zone_id: uuid.UUID) -> Zone:
        zone = self._repository.get(zone_id)
        if zone is None:
            raise ZoneNotFoundError(str(zone_id))
        return zone

    def list_zones(self, is_active: bool | None = None) -> list[Zone]:
        return self._repository.list(is_active=is_active)

    def resolve_point(self, lat: float, lng: float) -> Zone | None:
        """Active zone covering the point, or None when non-serviceable."""
        return self._repository.find_active_covering(lng=lng, lat=lat)
