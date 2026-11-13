"""Catalogue lookup port used by the cart.

Describes what the cart needs from the menu domain: the Outlet and MenuItem
dataclasses, the CatalogueProvider protocol (get_outlet, get_item) and an
InMemoryCatalogue implementation with an add_outlet/add_item API used by tests
and local development until the real PostgreSQL-backed catalogue tasks land.
Outlets carry minimum_order_paise, defaulting to DEFAULT_MINIMUM_ORDER_PAISE
(9900 paise, i.e. Rs 99). Items carry price, availability and the allowed
option ids with price deltas, so the cart can price lines on the server and
never trust client-supplied prices. Everything is expressed in paise.
"""
from dataclasses import dataclass, field
from typing import Protocol

DEFAULT_MINIMUM_ORDER_PAISE = 9900


@dataclass
class Outlet:
    id: str
    name: str
    minimum_order_paise: int = DEFAULT_MINIMUM_ORDER_PAISE


@dataclass
class MenuItem:
    id: str
    outlet_id: str
    name: str
    price_paise: int
    available: bool = True
    option_deltas: dict[str, int] = field(default_factory=dict)


class CatalogueProvider(Protocol):
    def get_outlet(self, outlet_id: str) -> Outlet | None: ...
    def get_item(self, item_id: str) -> MenuItem | None: ...


class InMemoryCatalogue:
    def __init__(self) -> None:
        self._outlets: dict[str, Outlet] = {}
        self._items: dict[str, MenuItem] = {}

    def add_outlet(self, outlet: Outlet) -> None:
        self._outlets[outlet.id] = outlet

    def add_item(self, item: MenuItem) -> None:
        self._items[item.id] = item

    def get_outlet(self, outlet_id: str) -> Outlet | None:
        return self._outlets.get(outlet_id)

    def get_item(self, item_id: str) -> MenuItem | None:
        return self._items.get(item_id)
