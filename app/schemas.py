"""Pydantic request/response schemas for the menu API.

Classes: CategoryCreate / CategoryUpdate (name, position), CategoryOut,
ItemCreate (all BRD item fields; price is a strict non-negative integer in
paise, prep override is 5-60 minutes or null), ItemUpdate (every field
optional, applied as a partial PATCH), ItemOut, CategoryWithItems (a category
with its nested items) and MenuOut (the full menu tree for an outlet).
Strict integer typing stops float prices such as 10.5 from being silently
truncated. Output models read straight from ORM objects.
"""
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    position: StrictInt = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    position: StrictInt | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    outlet_id: int
    name: str
    position: int


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price_paise: StrictInt = Field(ge=0)
    is_veg: StrictBool
    image_ref: str | None = Field(default=None, max_length=500)
    prep_time_override_minutes: StrictInt | None = Field(default=None, ge=5, le=60)
    is_available: StrictBool = True
    position: StrictInt = 0


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price_paise: StrictInt | None = Field(default=None, ge=0)
    is_veg: StrictBool | None = None
    image_ref: str | None = Field(default=None, max_length=500)
    prep_time_override_minutes: StrictInt | None = Field(default=None, ge=5, le=60)
    is_available: StrictBool | None = None
    position: StrictInt | None = None
    category_id: StrictInt | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    outlet_id: int
    category_id: int
    name: str
    description: str | None
    price_paise: int
    is_veg: bool
    image_ref: str | None
    prep_time_override_minutes: int | None
    is_available: bool
    position: int


class CategoryWithItems(CategoryOut):
    items: list[ItemOut]


class MenuOut(BaseModel):
    outlet_id: int
    categories: list[CategoryWithItems]
