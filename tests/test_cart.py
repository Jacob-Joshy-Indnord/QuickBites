"""Tests for the single-outlet cart API and minimum order value check.

Covers: replace-cart conflict when adding from another outlet (nothing changes
until replace_cart=true), add/update/remove line behaviour, the Rs 80 subtotal
vs Rs 99 default minimum giving a Rs 19 shortfall with checkout blocked, and
the confirmed rule that the minimum is evaluated after discounts and including
fees and taxes. Uses an InMemoryCatalogue fixture and FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient

from app.billing import BillAdjustments
from app.catalogue import InMemoryCatalogue, MenuItem, Outlet
from app.main import create_app

H = {"X-Customer-Id": "c1"}


def make(adjustments=None):
    cat = InMemoryCatalogue()
    cat.add_outlet(Outlet("A", "Outlet A"))
    cat.add_outlet(Outlet("B", "Outlet B"))
    cat.add_item(MenuItem("a1", "A", "Dosa", 8000, option_deltas={"cheese": 2000}))
    cat.add_item(MenuItem("a2", "A", "Idli", 5000))
    cat.add_item(MenuItem("b1", "B", "Pizza", 30000))
    cat.add_item(MenuItem("a3", "A", "Gone", 5000, available=False))
    kw = {"adjustments": adjustments} if adjustments else {}
    return TestClient(create_app(cat, **kw))


def add(c, outlet, item, qty=1, **kw):
    return c.post("/cart/items", headers=H,
                  json={"outlet_id": outlet, "item_id": item, "quantity": qty, **kw})


def test_different_outlet_returns_conflict_and_changes_nothing():
    c = make()
    add(c, "A", "a1")
    r = add(c, "B", "b1")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "replace_cart_required"
    cart = c.get("/cart", headers=H).json()
    assert cart["outlet_id"] == "A" and len(cart["lines"]) == 1


def test_replace_cart_when_confirmed():
    c = make()
    add(c, "A", "a1")
    r = add(c, "B", "b1", replace_cart=True)
    assert r.status_code == 200 and r.json()["outlet_id"] == "B"
    assert len(r.json()["lines"]) == 1


def test_add_update_remove_and_merge():
    c = make()
    add(c, "A", "a1")
    cart = add(c, "A", "a1", 2).json()
    assert len(cart["lines"]) == 1 and cart["lines"][0]["quantity"] == 3
    lid = cart["lines"][0]["line_id"]
    assert c.patch(f"/cart/items/{lid}", headers=H, json={"quantity": 2}).json()["subtotal_paise"] == 16000
    assert c.delete(f"/cart/items/{lid}", headers=H).json()["lines"] == []


def test_options_priced_and_validated_server_side():
    c = make()
    assert add(c, "A", "a1", option_ids=["cheese"]).json()["subtotal_paise"] == 10000
    assert add(c, "A", "a1", option_ids=["bogus"]).status_code == 422
    assert add(c, "A", "a3").status_code == 409


def test_shortfall_reported_and_checkout_blocked():
    c = make()
    cart = add(c, "A", "a1").json()
    assert cart["subtotal_paise"] == 8000
    assert cart["shortfall_paise"] == 1900 and cart["checkout_blocked"] is True
    r = c.post("/cart/checkout/validate", headers=H)
    assert r.status_code == 422 and r.json()["detail"]["shortfall_paise"] == 1900


def test_checkout_allowed_at_minimum():
    c = make()
    add(c, "A", "a1", 2)
    assert c.post("/cart/checkout/validate", headers=H).status_code == 200


def test_minimum_applies_after_discount_including_fees_and_tax():
    c = make(lambda o, s: BillAdjustments(discount_paise=3000, fees_paise=4000, tax_paise=500))
    cart = add(c, "A", "a1", 2).json()  # 16000-3000+4000+500 = 17500
    assert cart["payable_paise"] == 17500 and cart["shortfall_paise"] == 0
    c2 = make(lambda o, s: BillAdjustments(discount_paise=7000))
    cart = add(c2, "A", "a1", 2).json()  # 9000 payable < 9900
    assert cart["shortfall_paise"] == 900 and cart["checkout_blocked"]
