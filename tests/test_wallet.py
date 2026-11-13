"""Tests for the append-only wallet transaction log.

Covers the spec scenarios "Running balance correct" and "No negative
balance", plus supporting guarantees: ledger postings are balanced and
reference the wallet liability account, wallet and ledger rows cannot be
updated or deleted, repeated origin references are idempotent, and the REST
endpoints (POST credit, POST debit, GET balance, GET transactions) map
domain errors to HTTP status codes. Fixtures build an in-memory SQLite
database per test and a FastAPI TestClient bound to it. Helper tests
exercise the minimal ledger directly: unbalanced entries are rejected and
update/delete attempts on postings raise.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import ledger, wallet
from app.api import create_app
from app.models import Base, LedgerPosting, WalletTransaction


@pytest.fixture
def session():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    app = create_app(lambda: session)
    return TestClient(app)


def test_running_balance_and_origin(session):
    c = wallet.credit(session, "cust1", 10000, "refund", "order-1")
    d = wallet.debit(session, "cust1", 3000, "order_payment", "order-2")
    assert (c.balance_after, d.balance_after) == (10000, 7000)
    assert (c.origin_type, c.origin_id) == ("refund", "order-1")
    assert (d.origin_type, d.origin_id) == ("order_payment", "order-2")
    assert wallet.get_balance(session, "cust1") == 7000


def test_debit_exceeding_balance_rejected(session):
    wallet.credit(session, "cust1", 1000, "refund", "order-1")
    with pytest.raises(wallet.InsufficientBalance):
        wallet.debit(session, "cust1", 1001, "order_payment", "order-2")
    assert wallet.get_balance(session, "cust1") == 1000
    assert session.query(WalletTransaction).count() == 1


def test_non_positive_amount_rejected(session):
    with pytest.raises(ValueError):
        wallet.credit(session, "cust1", 0, "refund", "o")


def test_balances_are_per_customer(session):
    wallet.credit(session, "a", 500, "refund", "o1")
    assert wallet.get_balance(session, "b") == 0


def test_ledger_postings_balanced(session):
    wallet.credit(session, "cust1", 10000, "refund", "order-1")
    wallet.debit(session, "cust1", 3000, "order_payment", "order-2")
    rows = session.query(LedgerPosting).all()
    assert sum(r.amount for r in rows if r.side == "debit") == \
        sum(r.amount for r in rows if r.side == "credit")
    liab = [r for r in rows if r.account_code == ledger.WALLET_LIABILITY]
    assert [(r.side, r.amount) for r in liab] == [("credit", 10000), ("debit", 3000)]


def test_idempotent_origin(session):
    a = wallet.credit(session, "cust1", 500, "refund", "order-1")
    b = wallet.credit(session, "cust1", 500, "refund", "order-1")
    assert a.id == b.id
    assert wallet.get_balance(session, "cust1") == 500


def test_unbalanced_ledger_entry_rejected(session):
    with pytest.raises(ledger.UnbalancedEntry):
        ledger.post_entry(session, "x", "y", [("a", "debit", 10), ("b", "credit", 9)])


def test_rows_are_immutable(session):
    t = wallet.credit(session, "cust1", 500, "refund", "order-1")
    session.commit()
    t.amount = 1
    with pytest.raises(Exception):
        session.flush()
    session.rollback()
    session.delete(session.query(LedgerPosting).first())
    with pytest.raises(Exception):
        session.flush()
    session.rollback()


def test_api_flow(client):
    r = client.post("/wallets/c1/credits", json={"amount": 10000, "origin_type": "refund", "origin_id": "o1"})
    assert r.status_code == 201 and r.json()["balance_after"] == 10000
    r = client.post("/wallets/c1/debits", json={"amount": 3000, "origin_type": "order_payment", "origin_id": "o2"})
    assert r.status_code == 201 and r.json()["balance_after"] == 7000
    assert client.get("/wallets/c1").json() == {"customer_id": "c1", "balance": 7000}
    assert len(client.get("/wallets/c1/transactions").json()) == 2


def test_api_overdraw_rejected(client):
    r = client.post("/wallets/c1/debits", json={"amount": 1, "origin_type": "order_payment", "origin_id": "o"})
    assert r.status_code == 422
    r = client.post("/wallets/c1/credits", json={"amount": -5, "origin_type": "refund", "origin_id": "o"})
    assert r.status_code == 422
