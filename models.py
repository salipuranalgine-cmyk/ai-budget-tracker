from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Transaction:
    id: int
    txn_type: str
    amount: float
    category: str
    description: str
    txn_date: str
    logged_date: Optional[str] = None


@dataclass(slots=True)
class BudgetLimit:
    id: int
    category: str
    monthly_limit: float
    duration_type: str = "month"
    duration_days: int = 30
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass(slots=True)
class RecurringTransaction:
    id: int
    txn_type: str
    amount: float
    category: str
    description: str
    frequency: str
    frequency_days: int
    start_date: str
    next_date: str
    active: bool