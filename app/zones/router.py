"""Admin REST endpoints for managing delivery zones.

All routes live under ``/admin/zones`` and require the ops admin role through
``require_ops_admin`` (ops agents get 403, anonymous callers 401). Endpoint
functions: ``create_zone`` (POST, 201), ``list_zones`` (GET, optional
``is_active`` filter), ``get_zone`` (GET by id), ``update_zone`` (PATCH name
and/or boundary) and ``deactivate_zone`` (POST ``/{zone_id}/deactivate``,
idempotent soft delete that immediately makes the zone non-serviceable).
``get_zone_service`` builds a ``ZoneService`` from the repository stored on
``app.state``. Domain errors are translated to HTTP by ``_http_errors``:
``ZoneNotFoundError`` becomes 404 and ``ZoneConflictError`` (duplicate name or
overlap with another active zone) becomes 409.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import require_ops_admin
from app.zones.errors import ZoneConflictError, ZoneNotFoundError
from app.zones.geometry import to_multipolygon
from app.zones.schemas import ZoneCreate, ZoneOut, ZoneUpdate
from app.zones.service import ZoneService

router = APIRouter(
    prefix="/admin/zones",
    tags=["admin: zones"],
    dependencies=[Depends(require_ops_admin)],
)


def get_zone_service(request: Request) -> ZoneService:
    return ZoneService(request.app.state.zone_repository)


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except ZoneNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zone not found") from None
    except ZoneConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ZoneOut)
def create_zone(payload: ZoneCreate, service: ZoneService = Depends(get_zone_service)) -> ZoneOut:
    with _http_errors():
        zone = service.create_zone(payload.name, to_multipolygon(payload.boundary.model_dump()))
    return ZoneOut.from_zone(zone)


@router.get("", response_model=list[ZoneOut])
def list_zones(
    is_active: bool | None = None, service: ZoneService = Depends(get_zone_service)
) -> list[ZoneOut]:
    return [ZoneOut.from_zone(z) for z in service.list_zones(is_active=is_active)]


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: uuid.UUID, service: ZoneService = Depends(get_zone_service)) -> ZoneOut:
    with _http_errors():
        return ZoneOut.from_zone(service.get_zone(zone_id))


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: uuid.UUID, payload: ZoneUpdate, service: ZoneService = Depends(get_zone_service)
) -> ZoneOut:
    boundary = to_multipolygon(payload.boundary.model_dump()) if payload.boundary else None
    with _http_errors():
        zone = service.update_zone(zone_id, name=payload.name, boundary=boundary)
    return ZoneOut.from_zone(zone)


@router.post("/{zone_id}/deactivate", response_model=ZoneOut)
def deactivate_zone(
    zone_id: uuid.UUID, service: ZoneService = Depends(get_zone_service)
) -> ZoneOut:
    with _http_errors():
        return ZoneOut.from_zone(service.deactivate_zone(zone_id))
