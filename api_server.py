from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import database as db
import user_manager as um

app = FastAPI(title="AI Smart Saver API", version="0.1.0")


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    emoji: str = Field(default=um.DEFAULT_EMOJI, max_length=8)


class TransactionCreate(BaseModel):
    txn_type: str
    amount: float = Field(gt=0)
    category: str
    description: str = ""
    txn_date: Optional[str] = None


class TransactionUpdate(BaseModel):
    txn_type: str
    amount: float = Field(gt=0)
    category: str
    description: str = ""
    txn_date: str


def _activate_user(user_id: int):
    user = um.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.set_user_db(um.get_db_path(user.id))
    db.init_db()
    db.init_notifications_table()
    db.init_chat_tables()
    return user


@app.on_event("startup")
def _startup() -> None:
    um.init_users_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": db.get_backend()}


@app.get("/users")
def list_users() -> list[dict]:
    um.init_users_db()
    return [asdict(user) for user in um.get_users()]


@app.post("/users", status_code=201)
def create_user(payload: UserCreate) -> dict:
    um.init_users_db()
    if um.user_name_exists(payload.name):
        raise HTTPException(status_code=409, detail="A user with that name already exists")
    return asdict(um.add_user(payload.name, payload.emoji))


@app.get("/users/{user_id}/summary")
def user_summary(user_id: int) -> dict:
    _activate_user(user_id)
    db.apply_due_recurring()
    txns = db.get_transactions()
    income = sum(txn.amount for txn in txns if txn.txn_type == "income")
    expenses = sum(txn.amount for txn in txns if txn.txn_type == "expense")
    return {
        "balance": db.get_balance(),
        "starting_balance": db.get_starting_balance(),
        "income_total": round(income, 2),
        "expense_total": round(expenses, 2),
        "transaction_count": len(txns),
        "currency": db.get_currency(),
    }


@app.get("/users/{user_id}/transactions")
def list_transactions(
    user_id: int,
    search: str = "",
    category: str = "All",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
) -> list[dict]:
    _activate_user(user_id)
    txns = db.get_transactions(search, category, date_from, date_to, min_amount, max_amount)
    return [asdict(txn) for txn in txns]


@app.post("/users/{user_id}/transactions", status_code=201)
def create_transaction(user_id: int, payload: TransactionCreate) -> dict[str, int]:
    _activate_user(user_id)
    txn_id = db.add_transaction(
        txn_type=payload.txn_type,
        amount=payload.amount,
        category=payload.category,
        description=payload.description,
        txn_date=payload.txn_date,
    )
    return {"id": txn_id}


@app.put("/users/{user_id}/transactions/{txn_id}", status_code=204)
def update_transaction(user_id: int, txn_id: int, payload: TransactionUpdate) -> None:
    _activate_user(user_id)
    db.update_transaction(
        txn_id=txn_id,
        txn_type=payload.txn_type,
        amount=payload.amount,
        category=payload.category,
        description=payload.description,
        txn_date=payload.txn_date,
    )


@app.delete("/users/{user_id}/transactions/{txn_id}", status_code=204)
def delete_transaction(user_id: int, txn_id: int) -> None:
    _activate_user(user_id)
    db.delete_transaction(txn_id)
