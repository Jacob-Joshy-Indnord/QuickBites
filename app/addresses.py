"""Customer address book API.

Defines PiiCipher/NoOpCipher (hook for field-level PII encryption of label,
text and instructions), AddressIn/AddressUpdate/GeoPoint request models,
AddressRepository (in-memory, per-customer, with create, list, get, update,
delete, set_default) and build_router(), exposing POST/GET /addresses,
PATCH/DELETE /addresses/{id} and POST /addresses/{id}/default. Invariant:
each customer with addresses has exactly one default. The first address
becomes default automatically; setting a default unsets the previous one;
deleting the default is rejected with 409 until another is made default.
"""
import threading
import uuid
from typing import Protocol

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field


class PiiCipher(Protocol):
    def encrypt(self, value: str) -> str: ...
    def decrypt(self, value: str) -> str: ...


class NoOpCipher:
    """Placeholder until a KMS-backed cipher is wired in."""
    def encrypt(self, value: str) -> str:
        return value

    def decrypt(self, value: str) -> str:
        return value


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class AddressIn(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    full_text: str = Field(min_length=1, max_length=500)
    geo: GeoPoint
    instructions: str | None = Field(default=None, max_length=300)
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=50)
    full_text: str | None = Field(default=None, min_length=1, max_length=500)
    geo: GeoPoint | None = None
    instructions: str | None = Field(default=None, max_length=300)


class AddressRepository:
    def __init__(self, cipher: PiiCipher | None = None):
        self.cipher = cipher or NoOpCipher()
        self._data: dict[str, dict[str, dict]] = {}
        self._lock = threading.Lock()

    def _view(self, rec: dict) -> dict:
        d = self.cipher.decrypt
        return {"id": rec["id"], "label": d(rec["label"]), "full_text": d(rec["full_text"]),
                "geo": rec["geo"],
                "instructions": d(rec["instructions"]) if rec["instructions"] is not None else None,
                "is_default": rec["is_default"]}

    def _enc(self, v: str | None) -> str | None:
        return None if v is None else self.cipher.encrypt(v)

    def create(self, cust: str, body: AddressIn) -> dict:
        with self._lock:
            book = self._data.setdefault(cust, {})
            make_default = body.is_default or not book
            if make_default:
                for r in book.values():
                    r["is_default"] = False
            rec = {"id": uuid.uuid4().hex, "label": self._enc(body.label),
                   "full_text": self._enc(body.full_text), "geo": body.geo.model_dump(),
                   "instructions": self._enc(body.instructions), "is_default": make_default}
            book[rec["id"]] = rec
            return self._view(rec)

    def list(self, cust: str) -> list[dict]:
        with self._lock:
            return [self._view(r) for r in self._data.get(cust, {}).values()]

    def _get(self, cust: str, aid: str) -> dict:
        rec = self._data.get(cust, {}).get(aid)
        if rec is None:
            raise HTTPException(404, {"code": "address_not_found"})
        return rec

    def update(self, cust: str, aid: str, body: AddressUpdate) -> dict:
        with self._lock:
            rec = self._get(cust, aid)
            for f in body.model_fields_set:
                v = getattr(body, f)
                if f == "geo":
                    if v is None:
                        raise HTTPException(422, {"code": "geo_required"})
                    rec["geo"] = v.model_dump()
                elif v is None and f != "instructions":
                    raise HTTPException(422, {"code": f"{f}_required"})
                else:
                    rec[f] = self._enc(v)
            return self._view(rec)

    def set_default(self, cust: str, aid: str) -> dict:
        with self._lock:
            rec = self._get(cust, aid)
            for r in self._data[cust].values():
                r["is_default"] = False
            rec["is_default"] = True
            return self._view(rec)

    def delete(self, cust: str, aid: str) -> None:
        with self._lock:
            rec = self._get(cust, aid)
            if rec["is_default"]:
                raise HTTPException(409, {"code": "cannot_delete_default_address"})
            del self._data[cust][aid]


def build_router(repo: AddressRepository) -> APIRouter:
    router = APIRouter(prefix="/addresses", tags=["addresses"])

    def customer(x_customer_id: str = Header(...)) -> str:
        return x_customer_id

    @router.post("", status_code=201)
    def create(body: AddressIn, c: str = Depends(customer)):
        return repo.create(c, body)

    @router.get("")
    def list_(c: str = Depends(customer)):
        return repo.list(c)

    @router.patch("/{aid}")
    def update(aid: str, body: AddressUpdate, c: str = Depends(customer)):
        return repo.update(c, aid, body)

    @router.post("/{aid}/default")
    def set_default(aid: str, c: str = Depends(customer)):
        return repo.set_default(c, aid)

    @router.delete("/{aid}", status_code=204)
    def delete(aid: str, c: str = Depends(customer)):
        repo.delete(c, aid)

    return router
