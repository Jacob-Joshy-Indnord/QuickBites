"""Domain model for delivery zones.

This module defines ``Zone``, the immutable record that the service and every
repository exchange. A zone has a UUID ``id``, a human-readable ``name``
(unique case-insensitively), a ``boundary`` stored as a Shapely MultiPolygon
in WGS 84 (SRID 4326, coordinates in longitude/latitude order), an
``is_active`` flag, and ``created_at``, ``updated_at`` and ``deactivated_at``
timestamps in UTC. Deactivation is a soft delete: rows are kept for history,
audit and reporting, but inactive zones never resolve a point as serviceable.
The only function besides the dataclass itself is ``utcnow``, a small helper
returning a timezone-aware current UTC timestamp used by repositories.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from shapely.geometry import MultiPolygon


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Zone:
    id: uuid.UUID
    name: str
    boundary: MultiPolygon
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None = None
