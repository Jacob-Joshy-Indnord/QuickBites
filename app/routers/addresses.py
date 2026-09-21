from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.schemas import AddressIn, AddressOut, AddressUpdate
from app.services import addresses as address_service

router = APIRouter(prefix="/customers/{customer_id}/addresses", tags=["addresses"])


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(customer_id: str, payload: AddressIn, db: DbSession = Depends(get_db)):
    address = address_service.create_address(
        db,
        customer_id=customer_id,
        label=payload.label,
        full_text=payload.full_text,
        latitude=payload.latitude,
        longitude=payload.longitude,
        delivery_instructions=payload.delivery_instructions,
    )
    return address


@router.get("", response_model=list[AddressOut])
def list_addresses(customer_id: str, db: DbSession = Depends(get_db)):
    return address_service.list_addresses(db, customer_id)


@router.get("/{address_id}", response_model=AddressOut)
def get_address(customer_id: str, address_id: str, db: DbSession = Depends(get_db)):
    try:
        return address_service.get_address(db, customer_id, address_id)
    except address_service.AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="address not found") from exc


@router.patch("/{address_id}", response_model=AddressOut)
def update_address(
    customer_id: str, address_id: str, payload: AddressUpdate, db: DbSession = Depends(get_db)
):
    try:
        return address_service.update_address(
            db, customer_id, address_id, **payload.model_dump(exclude_unset=True)
        )
    except address_service.AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="address not found") from exc


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(customer_id: str, address_id: str, db: DbSession = Depends(get_db)):
    try:
        address_service.delete_address(db, customer_id, address_id)
    except address_service.AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="address not found") from exc


@router.post("/{address_id}/default", response_model=AddressOut)
def set_default_address(customer_id: str, address_id: str, db: DbSession = Depends(get_db)):
    try:
        return address_service.set_default_address(db, customer_id, address_id)
    except address_service.AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="address not found") from exc
