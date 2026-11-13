"""End-to-end tests for the admin Zone CRUD API (task-ZwUtwpRON0k).

These tests drive the FastAPI application through TestClient against the
in-memory repository. They cover the acceptance scenario "Deactivated zone
not serviceable" (``test_deactivated_zone_not_serviceable``), the create, get,
list, edit and deactivate happy paths, idempotent deactivation, 404s for
unknown zones, 409s for duplicate names and for polygons overlapping another
active zone, 422s for malformed GeoJSON, and the RBAC rule inherited from
task-tphOBokN7Z0: ops agents are rejected with 403 and anonymous callers with
401. Helper ``_create`` posts a zone and returns the JSON body. Every test
function name states the behaviour it verifies so failures read as specs.
"""

import uuid

from app.core.auth import OpsRole
from tests.conftest import square

BLR_LNG, BLR_LAT = 77.59, 12.97  # GeoJSON order is [lng, lat]


def _create(client, name="Indiranagar", boundary=None) -> dict:
    response = client.post(
        "/admin/zones",
        json={"name": name, "boundary": boundary or square(BLR_LNG, BLR_LAT)},
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Acceptance scenario -------------------------------------------------------

def test_deactivated_zone_not_serviceable(client, zone_service):
    zone = _create(client)
    inside_lat, inside_lng = BLR_LAT + 0.005, BLR_LNG + 0.005
    assert zone_service.resolve_point(lat=inside_lat, lng=inside_lng).id == uuid.UUID(zone["id"])

    response = client.post(f"/admin/zones/{zone['id']}/deactivate")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert zone_service.resolve_point(lat=inside_lat, lng=inside_lng) is None


# --- Create --------------------------------------------------------------------

def test_create_zone_returns_active_zone(client):
    body = _create(client)
    assert body["name"] == "Indiranagar"
    assert body["is_active"] is True
    assert body["deactivated_at"] is None
    assert body["boundary"]["type"] == "MultiPolygon"


def test_create_rejects_duplicate_name(client):
    _create(client)
    response = client.post(
        "/admin/zones", json={"name": "indiranagar", "boundary": square(BLR_LNG + 1, BLR_LAT)}
    )
    assert response.status_code == 409


def test_create_rejects_overlap_with_active_zone(client):
    _create(client)
    response = client.post(
        "/admin/zones",
        json={"name": "Overlap", "boundary": square(BLR_LNG + 0.005, BLR_LAT + 0.005)},
    )
    assert response.status_code == 409


def test_create_allows_zone_sharing_only_an_edge(client):
    _create(client)
    _create(client, name="Neighbour", boundary=square(BLR_LNG + 0.01, BLR_LAT))


def test_create_allows_overlap_with_deactivated_zone(client):
    old = _create(client)
    client.post(f"/admin/zones/{old['id']}/deactivate")
    _create(client, name="Replacement", boundary=square(BLR_LNG + 0.005, BLR_LAT + 0.005))


def test_create_rejects_unclosed_ring(client):
    boundary = square(BLR_LNG, BLR_LAT)
    boundary["coordinates"][0].pop()
    response = client.post("/admin/zones", json={"name": "Bad", "boundary": boundary})
    assert response.status_code == 422


def test_create_rejects_self_intersecting_polygon(client):
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
    }
    response = client.post("/admin/zones", json={"name": "Bowtie", "boundary": bowtie})
    assert response.status_code == 422


def test_create_rejects_out_of_range_coordinates(client):
    response = client.post(
        "/admin/zones", json={"name": "Bad", "boundary": square(179.999, 95.0)}
    )
    assert response.status_code == 422


def test_create_rejects_blank_name(client):
    response = client.post("/admin/zones", json={"name": "   ", "boundary": square(1, 1)})
    assert response.status_code == 422


# --- Read ----------------------------------------------------------------------

def test_get_zone(client):
    zone = _create(client)
    response = client.get(f"/admin/zones/{zone['id']}")
    assert response.status_code == 200
    assert response.json() == zone


def test_get_unknown_zone_returns_404(client):
    assert client.get(f"/admin/zones/{uuid.uuid4()}").status_code == 404


def test_list_zones_filters_by_active_flag(client):
    active = _create(client, name="Active")
    inactive = _create(client, name="Inactive", boundary=square(BLR_LNG + 1, BLR_LAT))
    client.post(f"/admin/zones/{inactive['id']}/deactivate")

    all_ids = {z["id"] for z in client.get("/admin/zones").json()}
    active_ids = {z["id"] for z in client.get("/admin/zones?is_active=true").json()}

    assert all_ids == {active["id"], inactive["id"]}
    assert active_ids == {active["id"]}


# --- Edit ----------------------------------------------------------------------

def test_edit_zone_name_and_boundary(client, zone_service):
    zone = _create(client)
    moved = square(BLR_LNG + 2, BLR_LAT)

    response = client.patch(
        f"/admin/zones/{zone['id']}", json={"name": "Koramangala", "boundary": moved}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Koramangala"
    assert zone_service.resolve_point(lat=BLR_LAT + 0.005, lng=BLR_LNG + 0.005) is None
    assert zone_service.resolve_point(lat=BLR_LAT + 0.005, lng=BLR_LNG + 2.005) is not None


def test_edit_rejects_overlap_with_other_active_zone(client):
    _create(client, name="A")
    b = _create(client, name="B", boundary=square(BLR_LNG + 1, BLR_LAT))
    response = client.patch(
        f"/admin/zones/{b['id']}", json={"boundary": square(BLR_LNG + 0.005, BLR_LAT)}
    )
    assert response.status_code == 409


def test_edit_allows_reshaping_own_boundary(client):
    zone = _create(client)
    response = client.patch(
        f"/admin/zones/{zone['id']}", json={"boundary": square(BLR_LNG, BLR_LAT, size=0.02)}
    )
    assert response.status_code == 200


def test_edit_rejects_empty_body(client):
    zone = _create(client)
    assert client.patch(f"/admin/zones/{zone['id']}", json={}).status_code == 422


def test_edit_unknown_zone_returns_404(client):
    response = client.patch(f"/admin/zones/{uuid.uuid4()}", json={"name": "X"})
    assert response.status_code == 404


# --- Deactivate ----------------------------------------------------------------

def test_deactivate_is_idempotent(client):
    zone = _create(client)
    first = client.post(f"/admin/zones/{zone['id']}/deactivate").json()
    second = client.post(f"/admin/zones/{zone['id']}/deactivate").json()
    assert first["deactivated_at"] is not None
    assert second["deactivated_at"] == first["deactivated_at"]


def test_deactivate_unknown_zone_returns_404(client):
    assert client.post(f"/admin/zones/{uuid.uuid4()}/deactivate").status_code == 404


# --- RBAC ----------------------------------------------------------------------

def test_ops_agent_cannot_manage_zones(client, as_role):
    zone = _create(client)
    as_role(OpsRole.OPS_AGENT)

    assert client.post("/admin/zones", json={"name": "X", "boundary": square(0, 0)}).status_code == 403
    assert client.patch(f"/admin/zones/{zone['id']}", json={"name": "Y"}).status_code == 403
    assert client.post(f"/admin/zones/{zone['id']}/deactivate").status_code == 403
    assert client.get("/admin/zones").status_code == 403


def test_anonymous_caller_is_rejected(client, as_role):
    as_role(None)
    assert client.get("/admin/zones").status_code == 401
