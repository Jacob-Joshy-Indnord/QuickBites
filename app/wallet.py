"""Wallet service: append-only credit and debit rows with running balance.

Functions: credit(session, customer_id, amount, origin_type, origin_id)
adds a credit row; debit(...) adds a debit row and raises
InsufficientBalance when it would take the balance below zero;
get_balance returns the latest balance_after (0 if none); list_transactions
returns rows oldest first. Each write locks the customer's Wallet row
(SELECT FOR UPDATE on PostgreSQL) to serialise balance computation,
posts a balanced ledger entry against wallet_liability, and is idempotent
on (customer, kind, origin_type, origin_id): replays return the original
row. Amounts are integer paise and must be positive. The caller owns the
transaction commit.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ledger
from app.models import Wallet, WalletTransaction


class InsufficientBalance(Exception):
    pass


def get_balance(session: Session, customer_id: str) -> int:
    last = session.scalars(
        select(WalletTransaction).where(WalletTransaction.customer_id == customer_id)
        .order_by(WalletTransaction.id.desc()).limit(1)).first()
    return last.balance_after if last else 0


def list_transactions(session: Session, customer_id: str) -> list[WalletTransaction]:
    return list(session.scalars(
        select(WalletTransaction).where(WalletTransaction.customer_id == customer_id)
        .order_by(WalletTransaction.id)))


def _record(session: Session, customer_id: str, kind: str, amount: int,
            origin_type: str, origin_id: str) -> WalletTransaction:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (paise)")
    if session.get(Wallet, customer_id, with_for_update=True) is None:
        session.add(Wallet(customer_id=customer_id))
        session.flush()
    existing = session.scalars(select(WalletTransaction).where(
        WalletTransaction.customer_id == customer_id, WalletTransaction.kind == kind,
        WalletTransaction.origin_type == origin_type,
        WalletTransaction.origin_id == origin_id)).first()
    if existing:
        return existing
    balance = get_balance(session, customer_id)
    new_balance = balance + amount if kind == "credit" else balance - amount
    if new_balance < 0:
        raise InsufficientBalance(f"balance {balance} < debit {amount}")
    entry_id = uuid.uuid4().hex
    wallet_side, other_side = ("credit", "debit") if kind == "credit" else ("debit", "credit")
    ledger.post_entry(session, entry_id, f"wallet {kind} {origin_type}:{origin_id}",
                      [(ledger.WALLET_LIABILITY, wallet_side, amount),
                       (ledger.PLATFORM_CASH, other_side, amount)])
    txn = WalletTransaction(customer_id=customer_id, kind=kind, amount=amount,
                            balance_after=new_balance, origin_type=origin_type,
                            origin_id=origin_id, ledger_entry_id=entry_id)
    session.add(txn)
    session.flush()
    return txn


def credit(session, customer_id, amount, origin_type, origin_id):
    return _record(session, customer_id, "credit", amount, origin_type, origin_id)


def debit(session, customer_id, amount, origin_type, origin_id):
    return _record(session, customer_id, "debit", amount, origin_type, origin_id)
