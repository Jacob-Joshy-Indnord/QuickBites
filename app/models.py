import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.utcnow()


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    phone_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class OtpRequest(Base):
    """One OTP challenge issued for a phone number.

    Generating a new OTP supersedes any prior active request for the same
    phone number, so "the same request" in the lockout rule maps to the
    single active row per phone number.
    """

    __tablename__ = "otp_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    phone_number: Mapped[str] = mapped_column(String, index=True)
    code_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)


class PhoneLockout(Base):
    __tablename__ = "phone_lockouts"

    phone_number: Mapped[str] = mapped_column(String, primary_key=True)
    locked_until: Mapped[datetime] = mapped_column(DateTime)


class Session(Base):
    """Minimal post-verification session marker.

    Full access/refresh token issuance (15 min / 30 day, per-device
    revocation) is a separate story; this only proves that OTP verification
    can hand back something a client can use as a session reference.
    """

    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.id"), index=True)
    label: Mapped[str] = mapped_column(String)
    full_text: Mapped[str] = mapped_column(String)
    latitude: Mapped[float] = mapped_column()
    longitude: Mapped[float] = mapped_column()
    delivery_instructions: Mapped[str | None] = mapped_column(String, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    customer: Mapped[Customer] = relationship(back_populates="addresses")
