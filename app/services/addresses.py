from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import Address


class AddressNotFoundError(Exception):
    pass


def list_addresses(db: DbSession, customer_id: str) -> list[Address]:
    stmt = select(Address).where(Address.customer_id == customer_id).order_by(Address.created_at)
    return list(db.scalars(stmt))


def get_address(db: DbSession, customer_id: str, address_id: str) -> Address:
    address = db.get(Address, address_id)
    if address is None or address.customer_id != customer_id:
        raise AddressNotFoundError()
    return address


def create_address(
    db: DbSession,
    customer_id: str,
    label: str,
    full_text: str,
    latitude: float,
    longitude: float,
    delivery_instructions: str | None,
) -> Address:
    is_first = len(list_addresses(db, customer_id)) == 0
    address = Address(
        customer_id=customer_id,
        label=label,
        full_text=full_text,
        latitude=latitude,
        longitude=longitude,
        delivery_instructions=delivery_instructions,
        is_default=is_first,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def update_address(db: DbSession, customer_id: str, address_id: str, **fields) -> Address:
    address = get_address(db, customer_id, address_id)
    for key, value in fields.items():
        if value is not None:
            setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return address


def delete_address(db: DbSession, customer_id: str, address_id: str) -> None:
    address = get_address(db, customer_id, address_id)
    was_default = address.is_default
    db.delete(address)
    db.flush()
    if was_default:
        remaining = list_addresses(db, customer_id)
        if remaining:
            remaining[0].is_default = True
    db.commit()


def set_default_address(db: DbSession, customer_id: str, address_id: str) -> Address:
    target = get_address(db, customer_id, address_id)
    for address in list_addresses(db, customer_id):
        address.is_default = address.id == target.id
    db.commit()
    db.refresh(target)
    return target
