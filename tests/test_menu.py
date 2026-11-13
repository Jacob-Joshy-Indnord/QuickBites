"""Tests for the menu category and item CRUD API (task-TjvI0j6ZpXY).

This module verifies the restaurant-facing menu management endpoints. It
builds an isolated in-memory SQLite database per test and overrides the app's
session dependency. Fixtures: `client` (TestClient) and `owner` (auth headers
for an owner of outlet 1). Tests: test_item_saved_with_all_fields (the spec
scenario: price, veg flag and prep override appear under the category),
test_menu_tree_nests_items, test_update_and_delete_item,
test_category_crud, test_validation_rejects_bad_price_and_prep,
test_cross_outlet_access_denied, test_unauthenticated_rejected and
test_item_in_foreign_category_rejected.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, expire_on_commit=False)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def hdr(outlet=1, role="OWNER"):
    return {"X-User-Id": "u1", "X-Outlet-Id": str(outlet), "X-Role": role}


@pytest.fixture()
def owner():
    return hdr()


def mk_cat(client, h, name="Starters"):
    r = client.post("/outlets/1/categories", json={"name": name}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


ITEM = {
    "name": "Paneer Tikka",
    "description": "Char-grilled",
    "price_paise": 24900,
    "is_veg": True,
    "image_ref": "img/paneer.jpg",
    "prep_time_override_minutes": 15,
    "is_available": True,
}


def test_item_saved_with_all_fields(client, owner):
    cat = mk_cat(client, owner)
    r = client.post(f"/outlets/1/categories/{cat['id']}/items", json=ITEM, headers=owner)
    assert r.status_code == 201, r.text
    item = r.json()
    for k, v in ITEM.items():
        assert item[k] == v
    tree = client.get("/outlets/1/menu", headers=owner).json()
    items = tree["categories"][0]["items"]
    assert len(items) == 1
    for k, v in ITEM.items():
        assert items[0][k] == v


def test_menu_tree_nests_items(client, owner):
    a = mk_cat(client, owner, "A")
    b = mk_cat(client, owner, "B")
    client.post(f"/outlets/1/categories/{b['id']}/items", json=ITEM, headers=owner)
    tree = client.get("/outlets/1/menu", headers=owner).json()
    assert [c["name"] for c in tree["categories"]] == ["A", "B"]
    assert tree["categories"][0]["items"] == []
    assert len(tree["categories"][1]["items"]) == 1


def test_update_and_delete_item(client, owner):
    cat = mk_cat(client, owner)
    item = client.post(
        f"/outlets/1/categories/{cat['id']}/items", json=ITEM, headers=owner
    ).json()
    r = client.patch(
        f"/outlets/1/items/{item['id']}",
        json={"price_paise": 19900, "prep_time_override_minutes": None},
        headers=owner,
    )
    assert r.status_code == 200
    assert r.json()["price_paise"] == 19900
    assert r.json()["prep_time_override_minutes"] is None
    assert r.json()["name"] == "Paneer Tikka"
    assert client.delete(f"/outlets/1/items/{item['id']}", headers=owner).status_code == 204
    assert client.get(f"/outlets/1/items/{item['id']}", headers=owner).status_code == 404


def test_category_crud(client, owner):
    cat = mk_cat(client, owner)
    r = client.patch(f"/outlets/1/categories/{cat['id']}", json={"name": "Mains"}, headers=owner)
    assert r.json()["name"] == "Mains"
    assert client.delete(f"/outlets/1/categories/{cat['id']}", headers=owner).status_code == 204
    assert client.get("/outlets/1/menu", headers=owner).json()["categories"] == []


def test_delete_category_removes_items(client, owner):
    cat = mk_cat(client, owner)
    item = client.post(
        f"/outlets/1/categories/{cat['id']}/items", json=ITEM, headers=owner
    ).json()
    client.delete(f"/outlets/1/categories/{cat['id']}", headers=owner)
    assert client.get(f"/outlets/1/items/{item['id']}", headers=owner).status_code == 404


@pytest.mark.parametrize(
    "patch",
    [
        {"price_paise": -1},
        {"price_paise": 10.5},
        {"prep_time_override_minutes": 4},
        {"prep_time_override_minutes": 61},
        {"name": ""},
    ],
)
def test_validation_rejects_bad_values(client, owner, patch):
    cat = mk_cat(client, owner)
    r = client.post(
        f"/outlets/1/categories/{cat['id']}/items", json={**ITEM, **patch}, headers=owner
    )
    assert r.status_code == 422


def test_cross_outlet_access_denied(client, owner):
    cat = mk_cat(client, owner)
    other = hdr(outlet=2)
    assert client.get("/outlets/1/menu", headers=other).status_code == 403
    assert client.post(
        f"/outlets/1/categories/{cat['id']}/items", json=ITEM, headers=other
    ).status_code == 403


def test_unauthenticated_rejected(client):
    assert client.get("/outlets/1/menu").status_code == 401
    bad = {"X-User-Id": "u", "X-Outlet-Id": "1", "X-Role": "CUSTOMER"}
    assert client.get("/outlets/1/menu", headers=bad).status_code == 403


def test_item_in_foreign_category_rejected(client, owner):
    cat = mk_cat(client, owner)
    r = client.post(f"/outlets/1/categories/9999/items", json=ITEM, headers=owner)
    assert r.status_code == 404
    assert cat["id"] != 9999
