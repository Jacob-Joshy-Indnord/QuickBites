"""Tests for the customer address CRUD API.

Covers the acceptance scenario (marking a second address default unsets the
previous one so exactly one default remains), first-address auto-default,
create with is_default, list, partial update, delete of a non-default address,
409 on deleting the default, per-customer isolation, validation errors, and
that a custom PiiCipher stores ciphertext internally while the API returns
plaintext.
"""
from fastapi.testclient import TestClient

from app.addresses import AddressRepository
from app.main import create_app

H = {"X-Customer-Id": "c1"}


def body(label="Home", **kw):
    return {"label": label, "full_text": "12 MG Road", "geo": {"lat": 12.97, "lng": 77.59}, **kw}


def client(repo=None):
    return TestClient(create_app(repo))


def defaults(c, h=H):
    return [a["id"] for a in c.get("/addresses", headers=h).json() if a["is_default"]]


def test_second_default_unsets_previous():
    c = client()
    a = c.post("/addresses", headers=H, json=body("Home")).json()
    b = c.post("/addresses", headers=H, json=body("Work")).json()
    assert a["is_default"] and not b["is_default"]
    assert c.post(f"/addresses/{b['id']}/default", headers=H).json()["is_default"]
    assert defaults(c) == [b["id"]]


def test_create_with_is_default_replaces_default():
    c = client()
    c.post("/addresses", headers=H, json=body("Home"))
    b = c.post("/addresses", headers=H, json=body("Work", is_default=True)).json()
    assert defaults(c) == [b["id"]]


def test_update_and_list():
    c = client()
    a = c.post("/addresses", headers=H, json=body()).json()
    r = c.patch(f"/addresses/{a['id']}", headers=H, json={"label": "Flat", "instructions": "Ring bell"})
    assert r.json()["label"] == "Flat" and r.json()["instructions"] == "Ring bell"
    assert r.json()["full_text"] == "12 MG Road" and r.json()["is_default"]
    assert c.patch(f"/addresses/{a['id']}", headers=H, json={"label": None}).status_code == 422


def test_delete_non_default_ok_default_rejected():
    c = client()
    a = c.post("/addresses", headers=H, json=body()).json()
    b = c.post("/addresses", headers=H, json=body("Work")).json()
    r = c.delete(f"/addresses/{a['id']}", headers=H)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "cannot_delete_default_address"
    assert c.delete(f"/addresses/{b['id']}", headers=H).status_code == 204
    assert len(c.get("/addresses", headers=H).json()) == 1


def test_delete_default_after_switching_default():
    c = client()
    a = c.post("/addresses", headers=H, json=body()).json()
    b = c.post("/addresses", headers=H, json=body("Work")).json()
    c.post(f"/addresses/{b['id']}/default", headers=H)
    assert c.delete(f"/addresses/{a['id']}", headers=H).status_code == 204
    assert defaults(c) == [b["id"]]


def test_customers_isolated_and_validation():
    c = client()
    a = c.post("/addresses", headers=H, json=body()).json()
    other = {"X-Customer-Id": "c2"}
    assert c.get("/addresses", headers=other).json() == []
    assert c.delete(f"/addresses/{a['id']}", headers=other).status_code == 404
    assert c.post("/addresses", headers=H, json=body(geo={"lat": 99, "lng": 0})).status_code == 422
    bad = body(); bad["geo"] = {"lat": 99, "lng": 0}
    assert c.post("/addresses", headers=H, json=bad).status_code == 422


class RevCipher:
    def encrypt(self, v): return v[::-1]
    def decrypt(self, v): return v[::-1]


def test_pii_stored_encrypted_returned_plain():
    repo = AddressRepository(RevCipher())
    c = client(repo)
    a = c.post("/addresses", headers=H, json=body("Home")).json()
    assert a["label"] == "Home"
    assert repo._data["c1"][a["id"]]["label"] == "emoH"
