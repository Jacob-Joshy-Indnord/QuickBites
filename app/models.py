"""SQLAlchemy models for the menu tree (categories then items).

`Category` belongs to an outlet (outlet_id), has a name and a sort position,
and owns its items with cascade delete. `MenuItem` carries every BRD item
field: name, description, price in integer paise, veg flag, image reference,
optional prep-time override in minutes (5-60) and availability. The outlet
table itself is owned by the outlet-registration task, so outlet_id is an
indexed plain integer here rather than a foreign key. Check constraints keep
price non-negative and the prep override in range at the database level.
"""
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    outlet_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="MenuItem.position, MenuItem.id",
    )


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="ck_item_price_nonneg"),
        CheckConstraint(
            "prep_time_override_minutes IS NULL OR "
            "(prep_time_override_minutes BETWEEN 5 AND 60)",
            name="ck_item_prep_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    outlet_id: Mapped[int] = mapped_column(Integer, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("menu_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_paise: Mapped[int] = mapped_column(Integer)
    is_veg: Mapped[bool] = mapped_column(Boolean)
    image_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prep_time_override_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[Category] = relationship(back_populates="items")
