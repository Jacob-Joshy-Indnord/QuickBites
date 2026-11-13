"""SQLAlchemy models for the wallet transaction log and minimal ledger.

Defines Base plus three tables. LedgerAccount holds chart-of-accounts codes.
LedgerPosting is the append-only double-entry postings table: each row is a
debit or credit of integer paise against an account, grouped by entry_id.
WalletTransaction is the append-only customer wallet log: kind (credit or
debit), amount, running balance_after, origin_type/origin_id reference and
the ledger entry it produced. Wallet is a per-customer anchor row used only
as a lock target. Unique (customer, kind, origin) gives idempotency. The
function block_mutation is an ORM listener that raises on any UPDATE or
DELETE of the append-only tables, so history cannot be rewritten.
"""
from datetime import datetime, timezone

from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"
    code: Mapped[str] = mapped_column(String(64), primary_key=True)


class LedgerPosting(Base):
    __tablename__ = "ledger_postings"
    __table_args__ = (CheckConstraint("amount > 0"),
                      CheckConstraint("side IN ('debit','credit')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(64), index=True)
    account_code: Mapped[str] = mapped_column(ForeignKey("ledger_accounts.code"))
    side: Mapped[str] = mapped_column(String(6))
    amount: Mapped[int] = mapped_column(Integer)  # paise
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Wallet(Base):
    __tablename__ = "wallets"
    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0"),
        CheckConstraint("kind IN ('credit','debit')"),
        CheckConstraint("balance_after >= 0"),
        UniqueConstraint("customer_id", "kind", "origin_type", "origin_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("wallets.customer_id"), index=True)
    kind: Mapped[str] = mapped_column(String(6))
    amount: Mapped[int] = mapped_column(Integer)  # paise
    balance_after: Mapped[int] = mapped_column(Integer)  # paise
    origin_type: Mapped[str] = mapped_column(String(32))
    origin_id: Mapped[str] = mapped_column(String(64))
    ledger_entry_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def block_mutation(mapper, connection, target):
    raise RuntimeError(f"{type(target).__name__} rows are append-only")


for _model in (LedgerPosting, WalletTransaction):
    event.listen(_model, "before_update", block_mutation)
    event.listen(_model, "before_delete", block_mutation)
