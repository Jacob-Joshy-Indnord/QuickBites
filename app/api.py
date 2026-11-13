"""FastAPI routes exposing the wallet transaction log.

create_app(session_factory) builds the app. Endpoints: POST
/wallets/{customer_id}/credits and /debits (body: amount in paise > 0,
origin_type, origin_id; 201 with the new row, 422 on an overdraw or invalid
amount), GET /wallets/{customer_id} (current balance) and GET
/wallets/{customer_id}/transactions (history, oldest first). There are
deliberately no update or delete routes. The session factory is injected so
tests can use SQLite and production can supply a PostgreSQL session; each
write commits on success and rolls back on failure. TxnOut is the response
schema; CreateIn is the request schema.
"""
from datetime import datetime
from typing import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app import wallet


class CreateIn(BaseModel):
    amount: int = Field(gt=0, description="Amount in paise")
    origin_type: str = Field(min_length=1, max_length=32)
    origin_id: str = Field(min_length=1, max_length=64)


class TxnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: str
    kind: str
    amount: int
    balance_after: int
    origin_type: str
    origin_id: str
    ledger_entry_id: str
    created_at: datetime


def create_app(get_session: Callable[[], Session]) -> FastAPI:
    app = FastAPI(title="QuickBites Wallet")

    def _write(fn, customer_id: str, body: CreateIn):
        session = get_session()
        try:
            txn = fn(session, customer_id, body.amount, body.origin_type, body.origin_id)
            out = TxnOut.model_validate(txn)
            session.commit()
            return out
        except wallet.InsufficientBalance as e:
            session.rollback()
            raise HTTPException(422, str(e))
        except Exception:
            session.rollback()
            raise

    @app.post("/wallets/{customer_id}/credits", response_model=TxnOut, status_code=201)
    def credit(customer_id: str, body: CreateIn):
        return _write(wallet.credit, customer_id, body)

    @app.post("/wallets/{customer_id}/debits", response_model=TxnOut, status_code=201)
    def debit(customer_id: str, body: CreateIn):
        return _write(wallet.debit, customer_id, body)

    @app.get("/wallets/{customer_id}")
    def balance(customer_id: str):
        return {"customer_id": customer_id,
                "balance": wallet.get_balance(get_session(), customer_id)}

    @app.get("/wallets/{customer_id}/transactions", response_model=list[TxnOut])
    def transactions(customer_id: str):
        return wallet.list_transactions(get_session(), customer_id)

    return app
