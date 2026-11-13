"""PostgreSQL/PostGIS implementation of the zone repository.

``PostgisZoneRepository`` stores zones in the ``zones`` table created by
``migrations/0001_create_zones.sql`` using SQLAlchemy Core and parameterised
SQL. Public methods mirror ``ZoneRepository``: ``create``, ``update``,
``deactivate``, ``get``, ``list`` and ``find_active_covering`` (ST_Covers on
active rows only, served by a partial GiST index). Writes that can conflict
take a transaction-scoped advisory lock so two concurrent edits cannot both
pass the no-overlap check; the unique lower(name) index is the final guard
and its violation is mapped to ``ZoneConflictError``. Helpers: ``_conflict``
runs the name and overlap checks, ``_geojson`` serialises Shapely geometry
and ``_to_zone`` maps a result row to the domain ``Zone``.
"""

import json
import uuid

from shapely.geometry import MultiPolygon, shape
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from app.zones.errors import ZoneConflictError, ZoneNotFoundError
from app.zones.geometry import to_geojson
from app.zones.models import Zone

_COLUMNS = """
    id, name, ST_AsGeoJSON(boundary) AS boundary_geojson, is_active,
    created_at, updated_at, deactivated_at
"""
_GEOM = "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(CAST(:boundary AS text)), 4326))"
# Serialises zone writes; admin edits are rare so contention is negligible.
_WRITE_LOCK = "SELECT pg_advisory_xact_lock(hashtext('quickbites.zones.write'))"


def _geojson(boundary: MultiPolygon) -> str:
    return json.dumps(to_geojson(boundary))


def _to_zone(row) -> Zone:
    return Zone(
        id=row.id,
        name=row.name,
        boundary=MultiPolygon(shape(json.loads(row.boundary_geojson))),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deactivated_at=row.deactivated_at,
    )


class PostgisZoneRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def _conflict(
        self,
        conn: Connection,
        name: str,
        boundary: MultiPolygon,
        check_overlap: bool,
        exclude: uuid.UUID | None,
    ) -> None:
        params = {"name": name, "exclude": exclude, "boundary": _geojson(boundary)}
        clash = conn.execute(
            text(
                "SELECT name FROM zones WHERE lower(name) = lower(:name) "
                "AND id IS DISTINCT FROM CAST(:exclude AS uuid) LIMIT 1"
            ),
            params,
        ).first()
        if clash:
            raise ZoneConflictError(f"a zone named {clash.name!r} already exists")
        if not check_overlap:
            return
        overlap = conn.execute(
            text(
                f"SELECT id FROM zones WHERE is_active "
                f"AND id IS DISTINCT FROM CAST(:exclude AS uuid) "
                f"AND ST_Intersects(boundary, {_GEOM}) AND NOT ST_Touches(boundary, {_GEOM}) "
                f"LIMIT 1"
            ),
            params,
        ).first()
        if overlap:
            raise ZoneConflictError(f"boundary overlaps active zone {overlap.id}")

    def create(self, name: str, boundary: MultiPolygon) -> Zone:
        try:
            with self._engine.begin() as conn:
                conn.execute(text(_WRITE_LOCK))
                self._conflict(conn, name, boundary, check_overlap=True, exclude=None)
                row = conn.execute(
                    text(
                        f"INSERT INTO zones (id, name, boundary) "
                        f"VALUES (:id, :name, {_GEOM}) RETURNING {_COLUMNS}"
                    ),
                    {"id": uuid.uuid4(), "name": name, "boundary": _geojson(boundary)},
                ).one()
                return _to_zone(row)
        except IntegrityError as exc:
            raise ZoneConflictError("zone violates a uniqueness constraint") from exc

    def update(
        self, zone_id: uuid.UUID, name: str | None = None, boundary: MultiPolygon | None = None
    ) -> Zone:
        try:
            with self._engine.begin() as conn:
                conn.execute(text(_WRITE_LOCK))
                current = conn.execute(
                    text(f"SELECT {_COLUMNS} FROM zones WHERE id = :id FOR UPDATE"),
                    {"id": zone_id},
                ).first()
                if current is None:
                    raise ZoneNotFoundError(str(zone_id))
                current_zone = _to_zone(current)
                new_name = name if name is not None else current_zone.name
                new_boundary = boundary if boundary is not None else current_zone.boundary
                self._conflict(
                    conn, new_name, new_boundary,
                    check_overlap=current_zone.is_active, exclude=zone_id,
                )
                row = conn.execute(
                    text(
                        f"UPDATE zones SET name = :name, boundary = {_GEOM}, updated_at = now() "
                        f"WHERE id = :id RETURNING {_COLUMNS}"
                    ),
                    {"id": zone_id, "name": new_name, "boundary": _geojson(new_boundary)},
                ).one()
                return _to_zone(row)
        except IntegrityError as exc:
            raise ZoneConflictError("zone violates a uniqueness constraint") from exc

    def deactivate(self, zone_id: uuid.UUID) -> Zone:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"UPDATE zones SET is_active = false, deactivated_at = now(), "
                    f"updated_at = now() WHERE id = :id AND is_active RETURNING {_COLUMNS}"
                ),
                {"id": zone_id},
            ).first()
            if row is None:  # already inactive (idempotent) or missing
                row = conn.execute(
                    text(f"SELECT {_COLUMNS} FROM zones WHERE id = :id"), {"id": zone_id}
                ).first()
            if row is None:
                raise ZoneNotFoundError(str(zone_id))
            return _to_zone(row)

    def get(self, zone_id: uuid.UUID) -> Zone | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {_COLUMNS} FROM zones WHERE id = :id"), {"id": zone_id}
            ).first()
            return _to_zone(row) if row else None

    def list(self, is_active: bool | None = None) -> list[Zone]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {_COLUMNS} FROM zones "
                    f"WHERE CAST(:is_active AS boolean) IS NULL OR is_active = :is_active "
                    f"ORDER BY created_at, id"
                ),
                {"is_active": is_active},
            )
            return [_to_zone(r) for r in rows]

    def find_active_covering(self, lng: float, lat: float) -> Zone | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {_COLUMNS} FROM zones WHERE is_active "
                    f"AND ST_Covers(boundary, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)) "
                    f"ORDER BY created_at, id LIMIT 1"
                ),
                {"lng": lng, "lat": lat},
            ).first()
            return _to_zone(row) if row else None
