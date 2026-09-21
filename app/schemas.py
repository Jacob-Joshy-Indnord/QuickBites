from datetime import datetime

from pydantic import BaseModel, Field


class OtpRequestIn(BaseModel):
    phone_number: str = Field(min_length=6, max_length=20)


class OtpRequestOut(BaseModel):
    phone_number: str
    expires_at: datetime


class OtpVerifyIn(BaseModel):
    phone_number: str
    code: str = Field(min_length=6, max_length=6)


class OtpVerifyOut(BaseModel):
    verified: bool
    customer_id: str
    session_token: str


class AddressIn(BaseModel):
    label: str
    full_text: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    delivery_instructions: str | None = None


class AddressUpdate(BaseModel):
    label: str | None = None
    full_text: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delivery_instructions: str | None = None


class AddressOut(BaseModel):
    id: str
    customer_id: str
    label: str
    full_text: str
    latitude: float
    longitude: float
    delivery_instructions: str | None
    is_default: bool

    model_config = {"from_attributes": True}
