"""Pydantic request and response schemas for the admin zone API.

These models define the public REST contract published in OpenAPI.
``GeoJSONPolygon`` and ``GeoJSONMultiPolygon`` describe the accepted boundary
shapes (WGS 84, [lng, lat] order) and are combined into the discriminated
``Boundary`` union. ``ZoneCreate`` requires a non-blank ``name`` (trimmed,
1-100 chars) and a ``boundary``; ``ZoneUpdate`` accepts either or both and
rejects an empty patch. Both run ``_validate_boundary``, which delegates to
``geometry.to_multipolygon`` so malformed or self-intersecting polygons fail
with 422 before reaching the database. ``ZoneOut`` is the response body;
its ``from_zone`` classmethod converts a domain ``Zone`` into the
serialisable shape, always emitting the boundary as a MultiPolygon.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.zones.geometry import to_geojson, to_multipolygon
from app.zones.models import Zone

ZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Position = list[float]


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[Position]]


class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Position]]]


Boundary = Annotated[GeoJSONPolygon | GeoJSONMultiPolygon, Field(discriminator="type")]


def _validate_boundary(boundary: GeoJSONPolygon | GeoJSONMultiPolygon | None):
    if boundary is not None:
        to_multipolygon(boundary.model_dump())
    return boundary


class ZoneCreate(BaseModel):
    name: ZoneName
    boundary: Boundary

    _check_boundary = field_validator("boundary")(_validate_boundary)


class ZoneUpdate(BaseModel):
    name: ZoneName | None = None
    boundary: Boundary | None = None

    _check_boundary = field_validator("boundary")(_validate_boundary)

    @model_validator(mode="after")
    def _require_a_change(self) -> "ZoneUpdate":
        if self.name is None and self.boundary is None:
            raise ValueError("provide at least one of: name, boundary")
        return self


class ZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    boundary: GeoJSONMultiPolygon
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None

    @classmethod
    def from_zone(cls, zone: Zone) -> "ZoneOut":
        return cls(
            id=zone.id,
            name=zone.name,
            boundary=GeoJSONMultiPolygon(**to_geojson(zone.boundary)),
            is_active=zone.is_active,
            created_at=zone.created_at,
            updated_at=zone.updated_at,
            deactivated_at=zone.deactivated_at,
        )
