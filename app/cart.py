"""Single-outlet cart API with minimum order value check.

Contains the in-memory CartStore (one cart per customer, tied to one outlet),
CartService (add_item, update_line, remove_line, get_cart, validate_checkout)
and build_router(), which exposes GET /cart, POST /cart/items,
PATCH /cart/items/{line_id}, DELETE /cart/items/{line_id} and
POST /cart/checkout/validate. Adding an item from a different outlet returns
409 replace_cart_required and changes nothing unless replace_cart is true.
Cart responses report subtotal, payable total, minimum and shortfall in paise;
checkout validation returns 422 while a shortfall exists. Customers are
identified by the X-Customer-Id header until auth lands.
"""
import uuid
from typing import Callable

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.billing import (BillAdjustments, compute_payable_paise,
                         compute_shortfall_paise, zero_adjustments)
from app.catalogue import CatalogueProvider


class AddItem(BaseModel):
    outlet_id: str
    item_id: str
    quantity: int = Field(ge=1, le=99)
    option_ids: list[str] = []
    replace_cart: bool = False


class UpdateLine(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartService:
    def __init__(self, catalogue: CatalogueProvider,
                 adjustments: Callable[[str, int], BillAdjustments] = zero_adjustments):
        self.catalogue = catalogue
        self.adjustments = adjustments
        self.carts: dict[str, dict] = {}

    def _unit_price(self, item, option_ids: list[str]) -> int:
        for o in option_ids:
            if o not in item.option_deltas:
                raise HTTPException(422, {"code": "invalid_option", "option_id": o})
        return item.price_paise + sum(item.option_deltas[o] for o in option_ids)

    def add_item(self, customer: str, body: AddItem) -> dict:
        outlet = self.catalogue.get_outlet(body.outlet_id)
        item = self.catalogue.get_item(body.item_id)
        if outlet is None or item is None or item.outlet_id != outlet.id:
            raise HTTPException(404, {"code": "item_not_found"})
        if not item.available:
            raise HTTPException(409, {"code": "item_unavailable"})
        unit = self._unit_price(item, body.option_ids)
        cart = self.carts.get(customer)
        if cart and cart["lines"] and cart["outlet_id"] != outlet.id:
            if not body.replace_cart:
                raise HTTPException(409, {
                    "code": "replace_cart_required",
                    "current_outlet_id": cart["outlet_id"],
                    "requested_outlet_id": outlet.id})
            cart = None
        if cart is None:
            cart = self.carts[customer] = {"outlet_id": outlet.id, "lines": {}}
        for line in cart["lines"].values():
            if line["item_id"] == item.id and sorted(line["option_ids"]) == sorted(body.option_ids):
                line["quantity"] = min(99, line["quantity"] + body.quantity)
                break
        else:
            cart["lines"][uuid.uuid4().hex] = {
                "item_id": item.id, "name": item.name, "option_ids": list(body.option_ids),
                "unit_price_paise": unit, "quantity": body.quantity}
        return self.get_cart(customer)

    def _cart(self, customer: str) -> dict:
        cart = self.carts.get(customer)
        if not cart or not cart["lines"]:
            raise HTTPException(404, {"code": "cart_not_found"})
        return cart

    def update_line(self, customer: str, line_id: str, qty: int) -> dict:
        cart = self._cart(customer)
        if line_id not in cart["lines"]:
            raise HTTPException(404, {"code": "line_not_found"})
        cart["lines"][line_id]["quantity"] = qty
        return self.get_cart(customer)

    def remove_line(self, customer: str, line_id: str) -> dict:
        cart = self._cart(customer)
        if cart["lines"].pop(line_id, None) is None:
            raise HTTPException(404, {"code": "line_not_found"})
        if not cart["lines"]:
            del self.carts[customer]
        return self.get_cart(customer)

    def get_cart(self, customer: str) -> dict:
        cart = self.carts.get(customer)
        if not cart or not cart["lines"]:
            return {"outlet_id": None, "lines": [], "subtotal_paise": 0,
                    "payable_paise": 0, "minimum_order_paise": 0,
                    "shortfall_paise": 0, "checkout_blocked": True}
        outlet = self.catalogue.get_outlet(cart["outlet_id"])
        lines = [{"line_id": k, **v, "line_total_paise": v["unit_price_paise"] * v["quantity"]}
                 for k, v in cart["lines"].items()]
        subtotal = sum(l["line_total_paise"] for l in lines)
        payable = compute_payable_paise(subtotal, self.adjustments(outlet.id, subtotal))
        shortfall = compute_shortfall_paise(payable, outlet.minimum_order_paise)
        return {"outlet_id": outlet.id, "lines": lines, "subtotal_paise": subtotal,
                "payable_paise": payable, "minimum_order_paise": outlet.minimum_order_paise,
                "shortfall_paise": shortfall, "checkout_blocked": shortfall > 0}

    def validate_checkout(self, customer: str) -> dict:
        self._cart(customer)
        cart = self.get_cart(customer)
        if cart["checkout_blocked"]:
            raise HTTPException(422, {"code": "minimum_order_not_met",
                                      "shortfall_paise": cart["shortfall_paise"]})
        return cart


def build_router(service: CartService) -> APIRouter:
    router = APIRouter(prefix="/cart", tags=["cart"])

    def customer(x_customer_id: str = Header(...)) -> str:
        return x_customer_id

    @router.get("")
    def get_cart(c: str = Depends(customer)):
        return service.get_cart(c)

    @router.post("/items")
    def add(body: AddItem, c: str = Depends(customer)):
        return service.add_item(c, body)

    @router.patch("/items/{line_id}")
    def update(line_id: str, body: UpdateLine, c: str = Depends(customer)):
        return service.update_line(c, line_id, body.quantity)

    @router.delete("/items/{line_id}")
    def remove(line_id: str, c: str = Depends(customer)):
        return service.remove_line(c, line_id)

    @router.post("/checkout/validate")
    def validate(c: str = Depends(customer)):
        return service.validate_checkout(c)

    return router
