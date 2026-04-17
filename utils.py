"""Shared helpers for the app."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


def calendar_date_from_datetime(val: Any) -> Optional[date]:
    """
    Local calendar date from a DatePicker value.

    Flet may send UTC datetimes; using .year/.month/.day on those gives the UTC
    calendar day and can be one day off from what the user picked.
    """
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if not isinstance(val, datetime):
        return None
    if val.tzinfo is not None:
        return val.astimezone().date()
    return val.date()


def calendar_date_from_picker_event_data(raw: Any) -> Optional[date]:
    """Parse DatePicker Event.data into a local calendar date."""
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return calendar_date_from_datetime(raw)
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return date.fromisoformat(s)
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return calendar_date_from_datetime(dt)


def calendar_date_from_picker(picker: Any, e: Any) -> Optional[date]:
    """
    Resolve the picked calendar date from a DatePicker event.

    Prefer event.data, then e.control.value, then picker.value (Flet varies).
    """
    d = calendar_date_from_picker_event_data(getattr(e, "data", None))
    if d is not None:
        return d
    ctrl = getattr(e, "control", None)
    if ctrl is not None:
        d = calendar_date_from_datetime(getattr(ctrl, "value", None))
        if d is not None:
            return d
    return calendar_date_from_datetime(getattr(picker, "value", None))