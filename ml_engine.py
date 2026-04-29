"""
ml_engine.py
============
scikit-learn ML layer for Budget Guardian.

WHAT THIS FILE DOES (junior-friendly overview):
------------------------------------------------
Machine learning is just math on your data to find patterns.
This file does three things:

  1. ANOMALY DETECTOR  (IsolationForest)
     Learns what a "normal" transaction looks like for you.
     When you log something way outside your normal range,
     it flags it as suspicious. Great for catching mistakes
     or truly unusual spending.

  2. SPENDING FORECASTER  (LinearRegression)
     Looks at how much you spent per category each month,
     draws a trend line through that history, and predicts
     what next month will look like.

  3. AUTO-RETRAIN SCHEDULER
     Checks on every app startup whether it's time to retrain
     based on the user's chosen schedule (daily / weekly / monthly).
     Retraining = feeding the models your newest data so predictions
     stay fresh. This is how real ML pipelines work in production.

HOW MODELS ARE SAVED:
---------------------
We use `joblib` (ships with scikit-learn) to save trained model
objects to disk as .pkl files. Think of it like pickle but optimised
for numpy arrays. Models are stored per-user in:
    user_data/ml_models/<username_slug>/

MINIMUM DATA THRESHOLDS:
------------------------
ML needs enough data to find real patterns, not noise.
  - Anomaly detector: needs at least 30 expense transactions
  - Forecaster: needs at least 3 months of data per category
If data is too thin, we skip training and return a clear message.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ── scikit-learn imports ──────────────────────────────────────────────────────
# IsolationForest: unsupervised anomaly detection
# LinearRegression: supervised regression for forecasting
# numpy: scikit-learn needs arrays, not plain Python lists
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
import numpy as np
import joblib  # saves/loads trained model objects to disk

# ── App imports ───────────────────────────────────────────────────────────────
from backend import database as db

# ── Constants ─────────────────────────────────────────────────────────────────
ML_MODELS_DIR = Path("user_data") / "ml_models"

# Minimum rows needed before we even attempt to train
MIN_TRANSACTIONS_FOR_ANOMALY = 30   # need a decent sample to define "normal"
MIN_MONTHS_FOR_FORECAST      = 3    # need at least 3 data points for a trend line
MIN_TRANSACTIONS_FOR_LIVE_ANOMALY = 12
LIVE_ANOMALY_TREES = 48

# IsolationForest contamination: roughly what % of data we expect to be anomalies.
# 0.05 means "flag the most extreme 5% as suspicious."
# Real-world personal finance: most transactions are normal, so keep this low.
ANOMALY_CONTAMINATION = 0.05

# Retrain schedule options (stored as strings in app_meta)
SCHEDULE_DAILY   = "daily"
SCHEDULE_WEEKLY  = "weekly"
SCHEDULE_MONTHLY = "monthly"
VALID_SCHEDULES  = {SCHEDULE_DAILY, SCHEDULE_WEEKLY, SCHEDULE_MONTHLY}

_retrain_lock = threading.Lock()
_retraining_dbs: set[str] = set()


# =============================================================================
# SECTION 1: MODEL STORAGE
# Helpers to figure out WHERE to save/load models for the current user.
# =============================================================================

def _get_model_dir() -> Path:
    """
    Return the directory where we store this user's trained models.
    We derive the folder name from the active DB filename so each
    user gets their own isolated model set.
    """
    db_stem = Path(db.DB_FILE).stem          # e.g. "budget_user_3"
    model_dir = ML_MODELS_DIR / db_stem
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def _model_path(name: str) -> Path:
    """Return the full .pkl path for a named model."""
    return _get_model_dir() / f"{name}.pkl"


def _db_training_key() -> str:
    return db.get_storage_key()


def _save_model(name: str, model) -> None:
    """Persist a trained scikit-learn model to disk using joblib."""
    joblib.dump(model, _model_path(name))


def _load_model(name: str):
    """
    Load a previously saved model from disk.
    Returns None if the model file doesn't exist yet
    (e.g. first run, or user cleared their data).
    """
    path = _model_path(name)
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


# =============================================================================
# SECTION 2: RETRAIN SCHEDULE
# Read and write the user's chosen schedule + last retrain timestamp.
# All stored in app_meta (same table used by currency, API key, etc.)
# =============================================================================

def get_retrain_schedule() -> str:
    """Return the user's chosen retrain schedule. Defaults to 'weekly'."""
    conn = db._connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'ml_retrain_schedule'"
    ).fetchone()
    conn.close()
    if row and row["value"] in VALID_SCHEDULES:
        return row["value"]
    return SCHEDULE_WEEKLY  # sensible default


def set_retrain_schedule(schedule: str) -> None:
    """
    Save the user's chosen retrain schedule.
    Called from settings_screen when the user picks Daily/Weekly/Monthly.
    """
    if schedule not in VALID_SCHEDULES:
        schedule = SCHEDULE_WEEKLY

    conn = db._connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('ml_retrain_schedule', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (schedule,),
    )
    conn.commit()
    conn.close()


def get_last_retrain_date() -> Optional[date]:
    """Return the date of the last successful retrain, or None if never trained."""
    conn = db._connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'ml_last_retrain'"
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return date.fromisoformat(row["value"])
    except (ValueError, TypeError):
        return None


def _set_last_retrain_date(d: date) -> None:
    """Record today as the last retrain date."""
    conn = db._connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('ml_last_retrain', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (d.isoformat(),),
    )
    conn.commit()
    conn.close()


def is_retrain_due() -> bool:
    """
    Check whether it's time to retrain based on the user's schedule.

    How this works (real MLOps concept called "scheduled retraining"):
      - We record the date of the last successful training run.
      - On every app startup, we compare that date to today.
      - If the gap is >= the schedule interval, we retrain.
      - If the model has never been trained, we always attempt it.
    """
    last = get_last_retrain_date()
    if last is None:
        return True   # never trained → always attempt

    today = date.today()
    schedule = get_retrain_schedule()

    if schedule == SCHEDULE_DAILY:
        return (today - last).days >= 1
    elif schedule == SCHEDULE_WEEKLY:
        return (today - last).days >= 7
    elif schedule == SCHEDULE_MONTHLY:
        return (today - last).days >= 30
    return False


# =============================================================================
# SECTION 3: DATA PREPARATION
# Pull raw transaction data from SQLite and shape it into numpy arrays
# that scikit-learn can actually work with.
# =============================================================================

def _get_expense_transactions() -> list[dict]:
    """
    Fetch all expense transactions from the DB.
    Returns a list of dicts with keys: amount, category, txn_date.
    """
    conn = db._connect()
    rows = conn.execute(
        """
        SELECT amount, category, txn_date
        FROM transactions
        WHERE txn_type = 'expense'
        ORDER BY txn_date ASC
        """
    ).fetchall()
    conn.close()
    return [
        {
            "amount":   float(row["amount"]),
            "category": row["category"],
            "txn_date": row["txn_date"],
        }
        for row in rows
    ]


def _build_anomaly_features(transactions: list[dict]) -> np.ndarray:
    """
    Convert transaction dicts into a 2D numpy array for IsolationForest.

    Features we use per transaction:
      - amount         : the actual peso/currency amount
      - day_of_week    : 0=Monday ... 6=Sunday (spending patterns vary by weekday)
      - day_of_month   : 1-31 (salary dates, bill cycles)

    Why these features?
    IsolationForest finds anomalies by randomly splitting the feature space.
    Points that are easy to isolate (few splits needed) = anomalies.
    Points that need many splits to isolate = normal.
    Adding date features helps it understand that a large spend on the 1st
    (payday) is normal, but the same amount on a random Tuesday might not be.
    """
    rows = []
    for t in transactions:
        try:
            d = date.fromisoformat(t["txn_date"])
        except (ValueError, TypeError):
            d = date.today()

        rows.append([
            t["amount"],
            d.weekday(),    # 0-6
            d.day,          # 1-31
        ])

    # np.array turns our Python list into a matrix scikit-learn can work with
    return np.array(rows, dtype=float)


def _get_monthly_category_totals() -> dict[str, list[tuple[int, float]]]:
    """
    Group expense transactions by (category, month) and sum amounts.

    Returns a dict: { category -> [(month_index, total_spent), ...] }

    month_index is a plain integer (0, 1, 2, ...) representing the
    chronological order of months. LinearRegression needs numbers, not dates.

    Example output:
    {
      "Food & Groceries": [(0, 3200.0), (1, 3800.0), (2, 2900.0)],
      "Transport":        [(0, 800.0),  (1, 750.0),  (2, 900.0)],
    }
    """
    conn = db._connect()
    rows = conn.execute(
        """
        SELECT
            category,
            substr(txn_date, 1, 7) AS month,   -- "YYYY-MM"
            SUM(amount) AS total
        FROM transactions
        WHERE txn_type = 'expense'
        GROUP BY category, month
        ORDER BY month ASC
        """
    ).fetchall()
    conn.close()

    # Collect all unique months to create a consistent integer index
    all_months_set: set[str] = {row["month"] for row in rows}
    all_months_sorted = sorted(all_months_set)
    month_to_idx = {m: i for i, m in enumerate(all_months_sorted)}

    category_data: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        cat = row["category"]
        idx = month_to_idx[row["month"]]
        total = float(row["total"])
        category_data.setdefault(cat, []).append((idx, total))

    return category_data


def _build_live_forecast(
    category: str,
    month_totals: list[tuple[int, float]],
    model: LinearRegression | None,
) -> dict[str, float | str | int]:
    values = np.array([total for _, total in month_totals], dtype=float)
    last_idx = month_totals[-1][0]
    last_total = float(values[-1])

    if model is not None:
        predicted = float(model.predict([[last_idx + 1]])[0])
        slope = float(model.coef_[0])
        fit_score = float(model.score(np.array([[idx] for idx, _ in month_totals], dtype=float), values))
    elif len(month_totals) >= 2:
        prev_total = float(values[-2])
        slope = last_total - prev_total
        predicted = last_total + slope
        fit_score = max(0.0, 1.0 - min(1.0, abs(slope) / max(last_total, prev_total, 1.0)))
    else:
        slope = 0.0
        predicted = last_total
        fit_score = 0.35

    reliability = _forecast_reliability_pct(month_totals, fit_score)

    if slope > 50:
        trend = "up"
    elif slope < -50:
        trend = "down"
    else:
        trend = "stable"

    return {
        "category": category,
        "predicted_amount": max(0.0, round(predicted, 2)),
        "trend": trend,
        "slope": round(slope, 2),
        "reliability_pct": reliability,
        "months_of_history": len(month_totals),
    }


def _forecast_reliability_pct(month_totals: list[tuple[int, float]], fit_score: float | None = None) -> int:
    months_factor = min(1.0, len(month_totals) / 6.0)
    values = np.array([total for _, total in month_totals], dtype=float)

    if len(values) >= 2:
        mean_value = max(float(values.mean()), 1.0)
        volatility = float(np.std(values) / mean_value)
        stability_factor = max(0.0, 1.0 - min(1.0, volatility))
    else:
        stability_factor = 0.35

    fit_factor = 0.35 if fit_score is None else max(0.0, min(1.0, fit_score))
    combined = (0.55 * months_factor) + (0.25 * stability_factor) + (0.20 * fit_factor)
    return int(round(25 + combined * 70))


def _anomaly_reliability_pct(transaction_count: int, transactions: list[dict] | None = None) -> int:
    if transaction_count <= 0:
        return 0

    volume_factor = min(1.0, transaction_count / 80.0)
    history = transactions if transactions is not None else _get_expense_transactions()
    diversity_factor = min(1.0, len({t["category"] for t in history}) / 8.0)
    combined = (0.75 * volume_factor) + (0.25 * diversity_factor)
    return int(round(20 + combined * 75))


def get_forecast_reliability_pct() -> int:
    summary = get_forecast_summary()
    if not summary:
        return 0
    return int(round(sum(int(item["reliability_pct"]) for item in summary) / len(summary)))


def get_anomaly_reliability_pct() -> int:
    transactions = _get_expense_transactions()
    return _anomaly_reliability_pct(len(transactions), transactions)


def _build_live_anomaly_model(transactions: list[dict]) -> IsolationForest | None:
    if len(transactions) < MIN_TRANSACTIONS_FOR_LIVE_ANOMALY:
        return None

    model = IsolationForest(
        contamination=ANOMALY_CONTAMINATION,
        random_state=42,
        n_estimators=LIVE_ANOMALY_TREES,
    )
    model.fit(_build_anomaly_features(transactions))
    return model


# =============================================================================
# SECTION 4: TRAINING
# The actual model training logic. This is where scikit-learn does its work.
# =============================================================================

def train_anomaly_detector() -> str:
    """
    Train an IsolationForest on all expense transactions.

    IsolationForest (quick explanation for juniors):
    - It builds many random decision trees.
    - For each transaction, it measures how quickly that point gets isolated
      by random cuts in the feature space.
    - Anomalies are isolated quickly (short path length).
    - Normal points take longer to isolate (they're surrounded by similar points).
    - contamination=0.05 tells it "expect ~5% of data to be anomalies."

    Returns a status string (shown in UI / logs).
    """
    transactions = _get_expense_transactions()

    if len(transactions) < MIN_TRANSACTIONS_FOR_ANOMALY:
        needed = MIN_TRANSACTIONS_FOR_ANOMALY - len(transactions)
        return (
            f"Not enough data yet. Log {needed} more expense transactions "
            f"to enable anomaly detection (need {MIN_TRANSACTIONS_FOR_ANOMALY} total)."
        )

    X = _build_anomaly_features(transactions)

    # Train the model
    # random_state=42 makes results reproducible (a common convention in ML)
    model = IsolationForest(
        contamination=ANOMALY_CONTAMINATION,
        random_state=42,
        n_estimators=100,   # number of trees — more = better but slower
    )
    model.fit(X)

    _save_model("anomaly_detector", model)
    return f"Anomaly detector trained on {len(transactions)} transactions."


def train_forecaster() -> str:
    """
    Train one LinearRegression model per expense category.

    LinearRegression (quick explanation for juniors):
    - Finds the best straight line through your monthly spending data.
    - X axis = month number (0, 1, 2, ...)
    - Y axis = total spent that month
    - Once we have the line, we plug in the NEXT month number to get a prediction.
    - It's simple, fast, and surprisingly effective for short-term trends.

    We save a dict of { category: LinearRegression model } as one file.
    Categories with fewer than MIN_MONTHS_FOR_FORECAST months are skipped.

    Returns a status string.
    """
    category_data = _get_monthly_category_totals()

    if not category_data:
        return "No expense data found. Start logging transactions to enable forecasting."

    trained_models: dict[str, LinearRegression] = {}
    skipped: list[str] = []

    for category, month_totals in category_data.items():
        if len(month_totals) < MIN_MONTHS_FOR_FORECAST:
            skipped.append(category)
            continue

        # X must be a 2D array for scikit-learn: shape (n_samples, n_features)
        # We reshape our list of month indexes to [[0], [1], [2], ...]
        X = np.array([[idx] for idx, _ in month_totals], dtype=float)
        y = np.array([total for _, total in month_totals], dtype=float)

        model = LinearRegression()
        model.fit(X, y)
        trained_models[category] = model

    if not trained_models:
        return (
            f"Not enough monthly history yet. Need at least {MIN_MONTHS_FOR_FORECAST} "
            f"months of data per category to forecast."
        )

    _save_model("forecasters", trained_models)

    trained_count = len(trained_models)
    skip_count = len(skipped)
    msg = f"Forecaster trained on {trained_count} categories."
    if skip_count:
        msg += f" ({skip_count} categories skipped — need more months of data.)"
    return msg


def train_all() -> dict[str, str]:
    """
    Train both models and record the retrain date.
    Returns a dict of results for each model (shown in UI).

    This is the function called by the scheduler AND the manual "Retrain Now" button.
    """
    results = {
        "anomaly":    train_anomaly_detector(),
        "forecaster": train_forecaster(),
    }
    _set_last_retrain_date(date.today())
    return results


# =============================================================================
# SECTION 5: INFERENCE (MAKING PREDICTIONS)
# These are the functions your UI calls to get actual ML results.
# =============================================================================

def detect_anomalies(limit: int = 20) -> list[dict]:
    """
    Run the trained anomaly detector on recent transactions.

    Returns a list of flagged transactions, sorted worst-first.
    Each dict has: amount, category, txn_date, anomaly_score

    anomaly_score: lower (more negative) = more anomalous.
    We convert this to a human-readable "suspicion level".

    If no model is trained yet, returns an empty list.
    """
    transactions = _get_expense_transactions()
    if len(transactions) < 5:
        return []

    model: IsolationForest | None = _load_model("anomaly_detector")
    if model is None:
        model = _build_live_anomaly_model(transactions)
        if model is None:
            return []

    X = _build_anomaly_features(transactions)

    # predict() returns: 1 = normal, -1 = anomaly
    predictions = model.predict(X)

    # score_samples() returns the raw anomaly score.
    # More negative = more isolated = more anomalous.
    scores = model.score_samples(X)

    reliability_pct = _anomaly_reliability_pct(len(transactions), transactions)
    anomalies = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:   # flagged as anomaly
            t = transactions[i]
            anomalies.append({
                "amount":        t["amount"],
                "category":      t["category"],
                "txn_date":      t["txn_date"],
                "anomaly_score": float(score),
                "reliability_pct": reliability_pct,
            })

    # Sort by score ascending (most suspicious first)
    anomalies.sort(key=lambda x: x["anomaly_score"])

    return anomalies[:limit]


def forecast_next_month() -> dict[str, float]:
    """
    Predict spending for each category next month.

    Returns a dict: { category: predicted_amount }
    Amounts are clipped to 0 (regression can predict negatives for declining trends).

    If no model is trained, returns an empty dict.
    """
    models: dict[str, LinearRegression] | None = _load_model("forecasters")
    if not models:
        return {}

    # Figure out what "next month index" is
    # We need to know the highest month index used in training
    category_data = _get_monthly_category_totals()

    predictions: dict[str, float] = {}

    for category, regression in models.items():
        if category not in category_data:
            continue

        month_totals = category_data[category]
        last_idx = max(idx for idx, _ in month_totals)
        next_idx = last_idx + 1

        # Predict: model expects a 2D array [[next_month_number]]
        predicted = regression.predict([[next_idx]])[0]

        # Clip to 0 — spending can't be negative
        predictions[category] = max(0.0, round(float(predicted), 2))

    return predictions


def get_forecast_summary() -> list[dict]:
    """
    Return forecast results as a sorted list of dicts for easy UI rendering.
    Each dict: { category, predicted_amount, trend }

    trend: "up" / "down" / "stable" based on regression slope.
    """
    models: dict[str, LinearRegression] | None = _load_model("forecasters")
    predictions = forecast_next_month()
    category_data = _get_monthly_category_totals()
    summary = []

    for category, month_totals in category_data.items():
        model = models.get(category) if models else None
        live_item = _build_live_forecast(category, month_totals, model)
        if category in predictions:
            live_item["predicted_amount"] = predictions[category]
        summary.append(live_item)

    # Sort by predicted amount descending (biggest spending first)
    summary.sort(key=lambda x: x["predicted_amount"], reverse=True)
    return summary


# =============================================================================
# SECTION 6: STARTUP HOOK
# Call this function when the app starts (after user login).
# It checks the schedule and retrains if needed — silently in the background.
# =============================================================================

def check_and_retrain() -> dict[str, str] | None:
    """
    Called on app startup after the user DB is set.
    If retraining is due, trains both models and returns the results dict.
    If not due yet, returns None (no work done).

    Pattern used in production ML systems:
      - App starts
      - Check: is it time to retrain?
      - Yes → retrain in background thread → update model files
      - No  → load existing models and serve predictions immediately
    """
    if is_retrain_due():
        db_key = _db_training_key()
        with _retrain_lock:
            if db_key in _retraining_dbs:
                return {"status": "training"}
            _retraining_dbs.add(db_key)

        def _run_background_retrain(training_key: str) -> None:
            try:
                train_all()
            finally:
                with _retrain_lock:
                    _retraining_dbs.discard(training_key)

        threading.Thread(
            target=_run_background_retrain,
            args=(db_key,),
            daemon=True,
            name=f"ml-retrain-{Path(db.DB_FILE).stem}",
        ).start()
        return {"status": "started"}
    return None


# =============================================================================
# SECTION 7: ML STATUS
# Helper for the settings screen to show the user what's happening.
# =============================================================================

def get_ml_status() -> dict:
    """
    Return a summary of the current ML state for display in settings.

    Returns:
    {
        "anomaly_model_ready":   bool,
        "forecast_model_ready":  bool,
        "last_retrain":          str  (human readable),
        "schedule":              str  (daily/weekly/monthly),
        "next_retrain":          str  (human readable),
        "transaction_count":     int,
        "months_of_data":        int,
    }
    """
    last = get_last_retrain_date()
    schedule = get_retrain_schedule()
    transactions = _get_expense_transactions()
    category_data = _get_monthly_category_totals()

    # Count distinct months across all categories
    months_of_data = 0
    if category_data:
        all_indices = set()
        for totals in category_data.values():
            for idx, _ in totals:
                all_indices.add(idx)
        months_of_data = len(all_indices)

    # Calculate next retrain date
    if last is None:
        next_retrain = "As soon as you have enough data"
    else:
        if schedule == SCHEDULE_DAILY:
            next_date = last + timedelta(days=1)
        elif schedule == SCHEDULE_WEEKLY:
            next_date = last + timedelta(days=7)
        else:
            next_date = last + timedelta(days=30)

        days_away = (next_date - date.today()).days
        if days_away <= 0:
            next_retrain = "Due now"
        elif days_away == 1:
            next_retrain = "Tomorrow"
        else:
            next_retrain = f"In {days_away} days"

    return {
        "anomaly_model_ready":  _model_path("anomaly_detector").exists(),
        "forecast_model_ready": _model_path("forecasters").exists(),
        "last_retrain":         last.strftime("%b %d, %Y") if last else "Never",
        "schedule":             schedule.capitalize(),
        "next_retrain":         next_retrain,
        "transaction_count":    len(transactions),
        "months_of_data":       months_of_data,
    }
