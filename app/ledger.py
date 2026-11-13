"""Minimal double-entry ledger used by the wallet (stub for the real ledger).

Stand-in for task-QR2bS3mpuoY so wallet postings work today; the real
ledger can replace it behind the same post_entry signature. Constants
WALLET_LIABILITY and PLATFORM_CASH name the accounts. post_entry(session,
entry_id, description, lines) validates every line is (account, side,
amount) with a positive integer amount, requires total debits to equal
total credits (else raises UnbalancedEntry), creates unknown accounts, and
adds the append-only LedgerPosting rows. Update and delete protection lives
in app.models. UnbalancedEntry is the error type.
"""
from sqlalchemy.orm import Session

from app.models import LedgerAccount, LedgerPosting

WALLET_LIABILITY = "wallet_liability"
PLATFORM_CASH = "platform_cash"


class UnbalancedEntry(ValueError):
    pass


def post_entry(session: Session, entry_id: str, description: str,
               lines: list[tuple[str, str, int]]) -> None:
    debits = sum(a for _, s, a in lines if s == "debit")
    credits = sum(a for _, s, a in lines if s == "credit")
    if len(lines) < 2 or debits != credits:
        raise UnbalancedEntry(f"debits {debits} != credits {credits}")
    for account, side, amount in lines:
        if side not in ("debit", "credit") or amount <= 0:
            raise ValueError("invalid posting line")
        if session.get(LedgerAccount, account) is None:
            session.add(LedgerAccount(code=account))
            session.flush()
        session.add(LedgerPosting(entry_id=entry_id, account_code=account,
                                  side=side, amount=amount, description=description))
