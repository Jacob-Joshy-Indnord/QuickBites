"""REST router for menu categories and items, scoped per outlet.

Routes under /outlets/{outlet_id}: GET /menu (category tree with items),
POST/PATCH/DELETE /categories[/{id}], POST /categories/{id}/items,
GET/PATCH/DELETE /items/{id}. Every route depends on `access`, which checks
the caller is a restaurant user of that outlet (403 otherwise). Lookups always
filter by outlet_id so one outlet can never read or change another's rows.
Helpers: `_category` and `_item` fetch-or-404. Deleting a category cascades to
its items. Menu versioning and availability toggles are separate tasks.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import Principal, restaurant_user
from app.db import get_session
from app.models import Category, MenuItem
from app.schemas import (
    CategoryCreate, CategoryOut, CategoryUpdate, ItemCreate, ItemOut,
    ItemUpdate, MenuOut,
)

router = APIRouter(prefix="/outlets/{outlet_id}", tags=["menu"])


def access(outlet_id: int, user: Principal = Depends(restaurant_user)) -> int:
    if user.outlet_id != outlet_id:
        raise HTTPException(403, "No access to this outlet")
    return outlet_id


def _category(db: Session, outlet_id: int, category_id: int) -> Category:
    cat = db.scalar(
        select(Category).where(Category.id == category_id, Category.outlet_id == outlet_id)
    )
    if cat is None:
        raise HTTPException(404, "Category not found")
    return cat


def _item(db: Session, outlet_id: int, item_id: int) -> MenuItem:
    item = db.scalar(
        select(MenuItem).where(MenuItem.id == item_id, MenuItem.outlet_id == outlet_id)
    )
    if item is None:
        raise HTTPException(404, "Item not found")
    return item


@router.get("/menu", response_model=MenuOut)
def get_menu(outlet_id: int = Depends(access), db: Session = Depends(get_session)):
    cats = db.scalars(
        select(Category)
        .where(Category.outlet_id == outlet_id)
        .options(selectinload(Category.items))
        .order_by(Category.position, Category.id)
    ).all()
    return {"outlet_id": outlet_id, "categories": cats}


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate, outlet_id: int = Depends(access), db: Session = Depends(get_session)
):
    cat = Category(outlet_id=outlet_id, **body.model_dump())
    db.add(cat)
    db.commit()
    return cat


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryUpdate,
    outlet_id: int = Depends(access), db: Session = Depends(get_session),
):
    cat = _category(db, outlet_id, category_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(cat, k, v)
    db.commit()
    return cat


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int, outlet_id: int = Depends(access), db: Session = Depends(get_session)
):
    db.delete(_category(db, outlet_id, category_id))
    db.commit()
    return Response(status_code=204)


@router.post("/categories/{category_id}/items", response_model=ItemOut, status_code=201)
def create_item(
    category_id: int, body: ItemCreate,
    outlet_id: int = Depends(access), db: Session = Depends(get_session),
):
    _category(db, outlet_id, category_id)
    item = MenuItem(outlet_id=outlet_id, category_id=category_id, **body.model_dump())
    db.add(item)
    db.commit()
    return item


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, outlet_id: int = Depends(access), db: Session = Depends(get_session)):
    return _item(db, outlet_id, item_id)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int, body: ItemUpdate,
    outlet_id: int = Depends(access), db: Session = Depends(get_session),
):
    item = _item(db, outlet_id, item_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("category_id") is not None:
        _category(db, outlet_id, data["category_id"])
    for field in ("name", "price_paise", "is_veg", "is_available", "position", "category_id"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} cannot be null")
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    return item


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, outlet_id: int = Depends(access), db: Session = Depends(get_session)):
    db.delete(_item(db, outlet_id, item_id))
    db.commit()
    return Response(status_code=204)
