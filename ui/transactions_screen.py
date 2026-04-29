from __future__ import annotations

from datetime import datetime, date, timedelta

import flet as ft

from backend import database as db
from models import Transaction, RecurringTransaction
from ui.constants import DEFAULT_CATEGORIES, INCOME_CATEGORIES, now_month, peso, make_peso
from utils import calendar_date_from_picker


# ---------------------------------------------------------------------------
# Frequency options for recurring transactions
# ---------------------------------------------------------------------------

FREQUENCY_OPTIONS = ["Daily", "Weekly", "Bi-weekly", "Monthly", "Yearly", "Custom"]

FREQ_KEY_MAP = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Bi-weekly": "biweekly",
    "Monthly": "monthly",
    "Yearly": "yearly",
    "Custom": "custom",
}

FREQ_DISPLAY = {
    "daily": "Daily",
    "weekly": "Weekly",
    "biweekly": "Bi-weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
    "custom": "Custom",
}

# ---------------------------------------------------------------------------
# Monthly-equivalent multiplier per frequency (for summary totals)
# ---------------------------------------------------------------------------

def _monthly_equiv(amount: float, frequency: str, frequency_days: int) -> float:
    """Approximate how much this recurring item costs/earns per month."""
    if frequency == "daily":
        return amount * 30
    elif frequency == "weekly":
        return amount * 4.33
    elif frequency == "biweekly":
        return amount * 2.17
    elif frequency == "monthly":
        return amount
    elif frequency == "yearly":
        return amount / 12
    elif frequency == "custom" and frequency_days > 0:
        return amount * (30 / frequency_days)
    return amount


# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------

def _open_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
    else:
        page.dialog = dialog
        dialog.open = True
        page.update()


def _close_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    if hasattr(page, "pop_dialog"):
        if page.pop_dialog() is None:
            dialog.open = False
            page.update()
    else:
        dialog.open = False
        page.update()


def _toast(page: ft.Page, text: str) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(text))
    page.snack_bar.open = True
    page.update()


def _dialog_width(page: ft.Page, *, max_width: int = 360, min_width: int = 280) -> int:
    width = page.width or getattr(page, "window_width", None) or max_width
    return int(min(max_width, max(min_width, width - 32)))


# ---------------------------------------------------------------------------
# Date picker helpers
# ---------------------------------------------------------------------------

def _txn_date_badge(txn_date_str: str) -> ft.Control | None:
    """
    Returns a small pill badge showing how many days away a future transaction
    is, or how many days ago a past transaction occurred.
    """
    try:
        txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
        today = date.today()
        diff = (txn_date - today).days
        if diff > 0:
            label = f"In {diff} day{'s' if diff != 1 else ''}"
            bg = ft.Colors.with_opacity(0.2, ft.Colors.CYAN_400)
            fg = ft.Colors.CYAN_300
            icon = ft.Icons.SCHEDULE
        elif diff == 0:
            label = "Today"
            bg = ft.Colors.with_opacity(0.2, ft.Colors.GREEN_400)
            fg = ft.Colors.GREEN_300
            icon = ft.Icons.TODAY
        elif diff >= -30:
            label = f"{abs(diff)} day{'s' if abs(diff) != 1 else ''} ago"
            bg = ft.Colors.with_opacity(0.12, ft.Colors.WHITE)
            fg = ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)
            icon = ft.Icons.HISTORY
        else:
            return None
        return ft.Container(
            padding=ft.Padding(5, 2, 5, 2),
            border_radius=6,
            bgcolor=bg,
            content=ft.Row(
                spacing=3,
                tight=True,
                controls=[
                    ft.Icon(icon, size=10, color=fg),
                    ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_500),
                ],
            ),
        )
    except Exception:
        return None


def _open_picker(page: ft.Page, picker: ft.DatePicker, current: date) -> None:
    """Set the picker initial value to noon (avoids midnight timezone drift) and open it."""
    picker.value = datetime(current.year, current.month, current.day, 12, 0, 0)
    if hasattr(page, "open"):
        page.open(picker)
    else:
        picker.open = True
    page.update()


def _build_single_date_picker(
    page: ft.Page,
    initial: date,
    *,
    btn_icon=ft.Icons.CALENDAR_TODAY,
) -> tuple[list[date], ft.OutlinedButton, ft.DatePicker]:
    """
    Creates ONE date picker.  Returns (sel_date, button, picker).
    sel_date[0] always holds the current selection.
    """
    sel: list[date] = [initial]

    btn_label = ft.Text(initial.strftime("%b %d, %Y"))
    btn = ft.OutlinedButton(
        content=btn_label,
        icon=btn_icon,
    )

    picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2099, 12, 31),
    )

    def _on_change(e):
        picked = calendar_date_from_picker(picker, e)
        if picked is None:
            return
        sel[0] = picked
        btn_label.value = picked.strftime("%b %d, %Y")
        page.update()

    picker.on_change = _on_change
    page.overlay.append(picker)
    btn.on_click = lambda _: _open_picker(page, picker, sel[0])

    return sel, btn, picker


# ---------------------------------------------------------------------------
# ADD / EDIT EXPENSE — popup dialog
# ---------------------------------------------------------------------------

def _expense_dialog(page: ft.Page, on_done, txn: Transaction | None = None) -> None:
    is_edit = txn is not None
    peso = make_peso(db.get_currency())  # dynamic currency
    dialog_width = _dialog_width(page)
    submit_state = {"busy": False}

    balance = db.get_balance()
    month_spend = sum(db.get_month_expense_summary(now_month()).values())

    # --- Type toggle: One-time vs Recurring ---
    txn_mode = ft.Dropdown(
        label="Transaction type",
        width=180,
        value="onetime",
        options=[
            ft.dropdown.Option("onetime", "One-time"),
            ft.dropdown.Option("recurring", "Recurring"),
        ],
    )
    freq_dd = ft.Dropdown(
        label="Repeat every",
        width=160,
        value="Monthly",
        options=[ft.dropdown.Option(f) for f in FREQUENCY_OPTIONS],
        visible=False,
    )
    custom_freq_field = ft.TextField(
        label="Every N days",
        width=110,
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=False,
    )

    amount_field = ft.TextField(
        label=f"Amount ({db.get_currency()})",
        hint_text="e.g. 150",
        value=f"{txn.amount:.2f}" if is_edit else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
    )
    category_dd = ft.Dropdown(
        label="Category",
        value=txn.category if is_edit else DEFAULT_CATEGORIES[0],
        options=[ft.dropdown.Option(c) for c in DEFAULT_CATEGORIES],
    )
    desc_field = ft.TextField(
        label="Details / Notes (optional)",
        hint_text='e.g. "Meralco bill", "Wifi subscription"',
        value=txn.description if is_edit else "",
        multiline=True,
        max_lines=3,
        min_lines=2,
    )

    # ---- Log date (always today, static) ----
    today = date.today()
    log_date_str = today.strftime("%b %d, %Y")

    # ---- Effective date picker ----
    init_effective = (
        datetime.strptime(txn.txn_date, "%Y-%m-%d").date() if is_edit else today
    )
    sel_effective, effective_btn, _eff_picker = _build_single_date_picker(
        page, init_effective, btn_icon=ft.Icons.EVENT
    )

    effective_label = ft.Text(
        "When to deduct from balance",
        size=12,
        color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
        weight=ft.FontWeight.W_500,
    )
    future_note = ft.Text(
        "⏳ Scheduled — balance won't change until this date.",
        size=11,
        color=ft.Colors.AMBER_300,
        visible=sel_effective[0] > today,
    )

    def _refresh_effective_ui():
        is_rec = txn_mode.value == "recurring"
        effective_label.value = (
            "Start date (first bill occurrence)" if is_rec else "When to deduct from balance"
        )
        future_note.visible = sel_effective[0] > today
        page.update()

    _orig_eff_change = _eff_picker.on_change
    def _eff_change_patched(e):
        if _orig_eff_change:
            _orig_eff_change(e)
        future_note.visible = sel_effective[0] > today
        page.update()
    _eff_picker.on_change = _eff_change_patched

    def on_mode_change(e):
        is_rec = txn_mode.value == "recurring"
        freq_dd.visible = is_rec
        custom_freq_field.visible = is_rec and freq_dd.value == "Custom"
        _refresh_effective_ui()

    def on_freq_change(_):
        custom_freq_field.visible = freq_dd.value == "Custom"
        page.update()

    txn_mode.on_change = on_mode_change
    freq_dd.on_change = on_freq_change

    def save(_):
        if submit_state["busy"]:
            return
        submit_state["busy"] = True
        save_btn.disabled = True
        cancel_btn.disabled = True
        page.update()
        try:
            val = float(amount_field.value.strip().replace(",", ""))
            if val <= 0:
                raise ValueError
        except ValueError:
            _toast(page, "Enter a valid positive amount.")
            submit_state["busy"] = False
            save_btn.disabled = False
            cancel_btn.disabled = False
            page.update()
            return

        date_str = sel_effective[0].isoformat()
        is_recurring = txn_mode.value == "recurring"

        if is_recurring and not is_edit:
            freq_label = freq_dd.value or "Monthly"
            freq_key = FREQ_KEY_MAP.get(freq_label, "monthly")
            try:
                freq_days = int(custom_freq_field.value) if freq_key == "custom" else 0
                if freq_key == "custom" and freq_days <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                _toast(page, "Enter a valid number of days for custom frequency.")
                submit_state["busy"] = False
                save_btn.disabled = False
                cancel_btn.disabled = False
                page.update()
                return
            db.add_recurring_transaction(
                txn_type="expense",
                amount=val,
                category=category_dd.value,
                description=desc_field.value.strip(),
                frequency=freq_key,
                frequency_days=freq_days,
                start_date=date_str,
            )
            _toast(page, f"🔁 Recurring bill of {peso(val)} set! Repeats {freq_label.lower()}.")
        else:
            if is_edit:
                db.update_transaction(
                    txn.id, "expense", val,
                    category_dd.value, desc_field.value.strip(), date_str,
                )
                _toast(page, "Expense updated!")
            else:
                db.add_transaction(
                    "expense", val,
                    category_dd.value, desc_field.value.strip(), date_str,
                )
                if sel_effective[0] > today:
                    _toast(page, f"Expense of {peso(val)} scheduled for {sel_effective[0].strftime('%b %d, %Y')}.")
                else:
                    _toast(page, f"Expense of {peso(val)} recorded!")

        _close_dialog(page, dlg)
        on_done(was_recurring=is_recurring and not is_edit)

    cancel_btn = ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, dlg))
    save_btn = ft.ElevatedButton(
        "Save Expense",
        icon=ft.Icons.SAVE,
        on_click=save,
        style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE),
    )
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.MONEY_OFF_CSRED, color=ft.Colors.RED_400),
                ft.Text(
                    "Edit Expense" if is_edit else "Add Expense",
                    weight=ft.FontWeight.BOLD,
                    size=16,
                ),
            ]
        ),
        content=ft.Container(
            width=dialog_width,
            content=ft.Column(
                tight=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    # Balance snapshot
                    ft.Container(
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED_400),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(spacing=2, controls=[
                                    ft.Text("Cash on Hand", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                    ft.Text(peso(balance), size=15, weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.GREEN_300),
                                ]),
                                ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                                    ft.Text("Spent This Month", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                    ft.Text(peso(month_spend), size=15, weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.ORANGE_300),
                                ]),
                            ],
                        ),
                    ),
                    # Recurring toggle (new transactions only)
                    *([] if is_edit else [
                        ft.Text("Transaction type", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                        txn_mode,
                        freq_dd,
                        custom_freq_field,
                    ]),
                    amount_field,
                    category_dd,
                    desc_field,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.HISTORY, size=16, color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                f"Logged on: {log_date_str}",
                                size=12,
                                color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                    effective_label,
                    effective_btn,
                    future_note,
                ],
            ),
        ),
        actions=[
            cancel_btn,
            save_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# ADD / EDIT INCOME — popup dialog
# ---------------------------------------------------------------------------

def _income_dialog(page: ft.Page, on_done, txn: Transaction | None = None) -> None:
    is_edit = txn is not None
    peso = make_peso(db.get_currency())  # dynamic currency
    balance = db.get_balance()
    dialog_width = _dialog_width(page)
    submit_state = {"busy": False}

    # --- Type toggle ---
    txn_mode = ft.Dropdown(
        label="Transaction type",
        width=180,
        value="onetime",
        options=[
            ft.dropdown.Option("onetime", "One-time"),
            ft.dropdown.Option("recurring", "Recurring"),
        ],
    )
    freq_dd = ft.Dropdown(
        label="Repeat every",
        width=160,
        value="Monthly",
        options=[ft.dropdown.Option(f) for f in FREQUENCY_OPTIONS],
        visible=False,
    )
    custom_freq_field = ft.TextField(
        label="Every N days",
        width=110,
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=False,
    )

    # Income category — always shown for one-time, also for recurring
    income_cat_dd = ft.Dropdown(
        label="Income category",
        value=txn.category if is_edit and txn.category in INCOME_CATEGORIES else INCOME_CATEGORIES[0],
        options=[ft.dropdown.Option(c) for c in INCOME_CATEGORIES],
        visible=not is_edit,  # hidden when editing (category locked to original)
    )

    amount_field = ft.TextField(
        label=f"Amount Received ({db.get_currency()})",
        hint_text="e.g. 5000",
        value=f"{txn.amount:.2f}" if is_edit else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
    )
    source_field = ft.TextField(
        label="Source / Notes (optional)",
        hint_text='e.g. "Sahod", "Padala ni Lola"',
        value=txn.description if is_edit else "",
        multiline=True,
        max_lines=2,
        min_lines=1,
    )

    today = date.today()
    log_date_str = today.strftime("%b %d, %Y")

    init_effective = (
        datetime.strptime(txn.txn_date, "%Y-%m-%d").date() if is_edit else today
    )
    sel_effective, effective_btn, _eff_picker = _build_single_date_picker(
        page, init_effective, btn_icon=ft.Icons.EVENT
    )

    effective_label = ft.Text(
        "When to add to balance",
        size=12,
        color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
        weight=ft.FontWeight.W_500,
    )
    future_note = ft.Text(
        "⏳ Scheduled — balance won't update until this date.",
        size=11,
        color=ft.Colors.AMBER_300,
        visible=sel_effective[0] > today,
    )

    def _refresh_effective_ui():
        is_rec = txn_mode.value == "recurring"
        effective_label.value = (
            "Start date (first income occurrence)" if is_rec else "When to add to balance"
        )
        future_note.visible = sel_effective[0] > today
        # income_cat_dd is always visible for new one-time transactions
        income_cat_dd.visible = not is_edit
        page.update()

    _orig_eff_change = _eff_picker.on_change
    def _eff_change_patched(e):
        if _orig_eff_change:
            _orig_eff_change(e)
        future_note.visible = sel_effective[0] > today
        page.update()
    _eff_picker.on_change = _eff_change_patched

    def on_mode_change(e):
        is_rec = txn_mode.value == "recurring"
        freq_dd.visible = is_rec
        custom_freq_field.visible = is_rec and freq_dd.value == "Custom"
        _refresh_effective_ui()

    def on_freq_change(_):
        custom_freq_field.visible = freq_dd.value == "Custom"
        page.update()

    txn_mode.on_change = on_mode_change
    freq_dd.on_change = on_freq_change

    def save(_):
        if submit_state["busy"]:
            return
        submit_state["busy"] = True
        save_btn.disabled = True
        cancel_btn.disabled = True
        page.update()
        try:
            val = float(amount_field.value.strip().replace(",", ""))
            if val <= 0:
                raise ValueError
        except ValueError:
            _toast(page, "Enter a valid positive amount.")
            submit_state["busy"] = False
            save_btn.disabled = False
            cancel_btn.disabled = False
            page.update()
            return

        date_str = sel_effective[0].isoformat()
        is_recurring = txn_mode.value == "recurring"

        if is_recurring and not is_edit:
            freq_label = freq_dd.value or "Monthly"
            freq_key = FREQ_KEY_MAP.get(freq_label, "monthly")
            try:
                freq_days = int(custom_freq_field.value) if freq_key == "custom" else 0
                if freq_key == "custom" and freq_days <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                _toast(page, "Enter a valid number of days.")
                submit_state["busy"] = False
                save_btn.disabled = False
                cancel_btn.disabled = False
                page.update()
                return
            # Use the proper income category instead of hardcoded "Income"
            income_category = income_cat_dd.value or INCOME_CATEGORIES[0]
            db.add_recurring_transaction(
                txn_type="income",
                amount=val,
                category=income_category,
                description=source_field.value.strip(),
                frequency=freq_key,
                frequency_days=freq_days,
                start_date=date_str,
            )
            _toast(page, f"🔁 Recurring income of {peso(val)} set! Repeats {freq_label.lower()}.")
        else:
            category = txn.category if is_edit else (income_cat_dd.value or INCOME_CATEGORIES[0])
            if is_edit:
                db.update_transaction(
                    txn.id, "income", val,
                    category, source_field.value.strip(), date_str,
                )
                _toast(page, "Income updated!")
            else:
                db.add_transaction(
                    "income", val,
                    category, source_field.value.strip(), date_str,
                )
                if sel_effective[0] > today:
                    _toast(page, f"{peso(val)} income scheduled for {sel_effective[0].strftime('%b %d, %Y')}.")
                else:
                    _toast(page, f"{peso(val)} income added!")

        _close_dialog(page, dlg)
        on_done(was_recurring=is_recurring and not is_edit)

    cancel_btn = ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, dlg))
    save_btn = ft.ElevatedButton(
        "Save Income",
        icon=ft.Icons.SAVE,
        on_click=save,
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
    )
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SAVINGS, color=ft.Colors.GREEN_400),
                ft.Text(
                    "Edit Income" if is_edit else "Add Income",
                    weight=ft.FontWeight.BOLD,
                    size=16,
                ),
            ]
        ),
        content=ft.Container(
            width=dialog_width,
            content=ft.Column(
                tight=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=10,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_400),
                        content=ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                                        color=ft.Colors.GREEN_300, size=22),
                                ft.Column(spacing=2, controls=[
                                    ft.Text("Current Cash on Hand", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                    ft.Text(peso(balance), size=16, weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.GREEN_300),
                                ]),
                            ],
                        ),
                    ),
                    # Recurring toggle (new transactions only)
                    *([] if is_edit else [
                        ft.Text("Transaction type", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                        txn_mode,
                        freq_dd,
                        custom_freq_field,
                    ]),
                    # Income category — always shown for new transactions
                    income_cat_dd,
                    amount_field,
                    source_field,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.HISTORY, size=16, color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                f"Logged on: {log_date_str}",
                                size=12,
                                color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                    effective_label,
                    effective_btn,
                    future_note,
                ],
            ),
        ),
        actions=[
            cancel_btn,
            save_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# DELETE confirmation
# ---------------------------------------------------------------------------

def _delete_dialog(page: ft.Page, txn_id: int, on_done) -> None:
    def do_delete(_):
        _close_dialog(page, dlg)
        db.delete_transaction(txn_id)
        _toast(page, "Transaction deleted.")
        on_done()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Delete this transaction?"),
        content=ft.Text("This cannot be undone, bro."),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, dlg)),
            ft.ElevatedButton(
                "Delete",
                icon=ft.Icons.DELETE,
                on_click=do_delete,
                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# EDIT RECURRING — popup dialog
# ---------------------------------------------------------------------------

def _edit_recurring_dialog(page: ft.Page, rec: RecurringTransaction, on_done) -> None:
    peso = make_peso(db.get_currency())  # dynamic currency
    """Dialog to edit an existing recurring transaction's amount, schedule, and details."""
    dialog_width = _dialog_width(page)
    submit_state = {"busy": False}

    is_income = rec.txn_type == "income"
    all_categories = INCOME_CATEGORIES if is_income else DEFAULT_CATEGORIES

    # Reverse-map frequency key → display label
    rev_freq_map = {v: k for k, v in FREQ_KEY_MAP.items()}
    current_freq_label = rev_freq_map.get(rec.frequency, "Monthly")
    if rec.frequency == "custom":
        current_freq_label = "Custom"

    amount_field = ft.TextField(
        label=f"Amount ({db.get_currency()})",
        value=f"{rec.amount:.2f}",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
    )

    # Figure out the best category match (in case old data used "Income")
    cat_options = all_categories
    current_cat = rec.category
    if current_cat not in cat_options:
        current_cat = cat_options[0]

    category_dd = ft.Dropdown(
        label="Category / Source",
        value=current_cat,
        options=[ft.dropdown.Option(c) for c in cat_options],
    )
    desc_field = ft.TextField(
        label="Description / Notes",
        value=rec.description,
        multiline=True,
        max_lines=2,
        min_lines=1,
    )
    freq_dd = ft.Dropdown(
        label="Repeat every",
        value=current_freq_label,
        options=[ft.dropdown.Option(f) for f in FREQUENCY_OPTIONS],
    )
    custom_freq_field = ft.TextField(
        label="Every N days",
        value=str(rec.frequency_days) if rec.frequency == "custom" else "",
        width=120,
        keyboard_type=ft.KeyboardType.NUMBER,
        visible=rec.frequency == "custom",
    )

    def on_freq_change(_):
        custom_freq_field.visible = freq_dd.value == "Custom"
        page.update()

    freq_dd.on_change = on_freq_change

    # Next due date picker
    try:
        init_next = datetime.strptime(rec.next_date, "%Y-%m-%d").date()
    except Exception:
        init_next = date.today()

    sel_next, next_btn, _ = _build_single_date_picker(page, init_next, btn_icon=ft.Icons.EVENT_REPEAT)

    def save(_):
        if submit_state["busy"]:
            return
        submit_state["busy"] = True
        save_btn.disabled = True
        cancel_btn.disabled = True
        page.update()
        try:
            val = float(amount_field.value.strip().replace(",", ""))
            if val <= 0:
                raise ValueError
        except ValueError:
            _toast(page, "Enter a valid positive amount.")
            submit_state["busy"] = False
            save_btn.disabled = False
            cancel_btn.disabled = False
            page.update()
            return

        freq_label = freq_dd.value or "Monthly"
        freq_key = FREQ_KEY_MAP.get(freq_label, "monthly")
        try:
            freq_days = int(custom_freq_field.value) if freq_key == "custom" else 0
            if freq_key == "custom" and freq_days <= 0:
                raise ValueError
        except (ValueError, TypeError):
            _toast(page, "Enter valid number of days.")
            submit_state["busy"] = False
            save_btn.disabled = False
            cancel_btn.disabled = False
            page.update()
            return

        db.update_recurring_transaction(
            rec_id=rec.id,
            amount=val,
            category=category_dd.value,
            description=desc_field.value.strip(),
            frequency=freq_key,
            frequency_days=freq_days,
            next_date=sel_next[0].isoformat(),
        )
        _close_dialog(page, dlg)
        _toast(page, f"🔁 Recurring updated — next due {sel_next[0].strftime('%b %d, %Y')}.")
        on_done()

    color = ft.Colors.GREEN_400 if is_income else ft.Colors.RED_400
    icon = ft.Icons.SAVINGS if is_income else ft.Icons.RECEIPT_LONG
    cancel_btn = ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, dlg))
    save_btn = ft.ElevatedButton(
        "Save Changes",
        icon=ft.Icons.SAVE,
        on_click=save,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700 if is_income else ft.Colors.INDIGO_600,
            color=ft.Colors.WHITE,
        ),
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(icon, color=color),
                ft.Text("Edit Recurring", weight=ft.FontWeight.BOLD, size=16),
            ]
        ),
        content=ft.Container(
            width=dialog_width,
            content=ft.Column(
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Container(
                        padding=ft.Padding(10, 8, 10, 8),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.1, color),
                        content=ft.Text(
                            f"{'Income' if is_income else 'Expense'} · {rec.category}",
                            size=12,
                            color=color,
                            weight=ft.FontWeight.W_500,
                        ),
                    ),
                    amount_field,
                    category_dd,
                    desc_field,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ft.Text("Schedule", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE), weight=ft.FontWeight.W_500),
                    freq_dd,
                    custom_freq_field,
                    ft.Text("Next due date", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                    next_btn,
                    ft.Text(
                        "⚠️ Changing next date skips or brings forward the next auto-deduction.",
                        size=11,
                        color=ft.Colors.AMBER_300,
                    ),
                ],
            ),
        ),
        actions=[
            cancel_btn,
            save_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# Recurring transaction section builder
# ---------------------------------------------------------------------------

def _build_recurring_section(page: ft.Page, on_data_changed) -> ft.Control:
    rec_list = ft.Column(spacing=8)

    def _days_badge(next_date_str: str) -> tuple[ft.Control, str]:
        """Return (badge_widget, urgency_color_hex) based on days until due."""
        try:
            nd = datetime.strptime(next_date_str, "%Y-%m-%d").date()
            diff = (nd - date.today()).days
        except Exception:
            diff = 999

        if diff < 0:
            label = f"OVERDUE {abs(diff)}d"
            bg = ft.Colors.with_opacity(0.25, ft.Colors.RED_400)
            fg = ft.Colors.RED_300
            ic = ft.Icons.WARNING_AMBER_ROUNDED
            border_color = ft.Colors.RED_400
        elif diff == 0:
            label = "Due TODAY"
            bg = ft.Colors.with_opacity(0.25, ft.Colors.ORANGE_400)
            fg = ft.Colors.ORANGE_300
            ic = ft.Icons.NOTIFICATIONS_ACTIVE
            border_color = ft.Colors.ORANGE_400
        elif diff <= 7:
            label = f"Due in {diff}d"
            bg = ft.Colors.with_opacity(0.2, ft.Colors.AMBER_400)
            fg = ft.Colors.AMBER_300
            ic = ft.Icons.SCHEDULE
            border_color = ft.Colors.AMBER_400
        else:
            label = f"In {diff} days"
            bg = ft.Colors.with_opacity(0.12, ft.Colors.WHITE)
            fg = ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)
            ic = ft.Icons.CALENDAR_MONTH
            border_color = ft.Colors.TRANSPARENT

        badge = ft.Container(
            padding=ft.Padding(5, 2, 5, 2),
            border_radius=5,
            bgcolor=bg,
            content=ft.Row(
                spacing=3,
                tight=True,
                controls=[
                    ft.Icon(ic, size=10, color=fg),
                    ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600),
                ],
            ),
        )
        return badge, border_color

    def refresh_rec():
        rec_list.controls.clear()
        recs = db.get_recurring_transactions()

        if not recs:
            rec_list.controls.append(
                ft.Container(
                    padding=ft.Padding(0, 8, 0, 4),
                    content=ft.Text(
                        "Walang recurring pa. Tap Add Expense / Add Income → choose Recurring.",
                        color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                        size=13,
                    ),
                )
            )
            page.update()
            return

        # ── Monthly summary banner ────────────────────────────────────────────
        total_monthly_expense = sum(
            _monthly_equiv(r.amount, r.frequency, r.frequency_days)
            for r in recs if r.txn_type == "expense" and r.active
        )
        total_monthly_income = sum(
            _monthly_equiv(r.amount, r.frequency, r.frequency_days)
            for r in recs if r.txn_type == "income" and r.active
        )

        rec_list.controls.append(
            ft.Container(
                padding=ft.Padding(12, 10, 12, 10),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    controls=[
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=2,
                            controls=[
                                ft.Text("Monthly Bills", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                ft.Text(
                                    peso(total_monthly_expense),
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.RED_300,
                                ),
                            ],
                        ),
                        ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=2,
                            controls=[
                                ft.Text("Monthly Income", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                ft.Text(
                                    peso(total_monthly_income),
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_300,
                                ),
                            ],
                        ),
                        ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=2,
                            controls=[
                                ft.Text("Net / Month", size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                                ft.Text(
                                    peso(total_monthly_income - total_monthly_expense),
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=(
                                        ft.Colors.GREEN_300
                                        if total_monthly_income >= total_monthly_expense
                                        else ft.Colors.RED_300
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

        # ── Per-entry cards ───────────────────────────────────────────────────
        for r in recs:
            is_income = r.txn_type == "income"
            color = ft.Colors.GREEN_400 if is_income else ft.Colors.RED_400
            icon = ft.Icons.ARROW_DOWNWARD if is_income else ft.Icons.ARROW_UPWARD
            freq_label = FREQ_DISPLAY.get(r.frequency, r.frequency.capitalize())
            if r.frequency == "custom":
                freq_label = f"Every {r.frequency_days}d"

            next_fmt = datetime.strptime(r.next_date, "%Y-%m-%d").strftime("%b %d, %Y")
            days_badge, border_col = _days_badge(r.next_date)
            monthly_val = _monthly_equiv(r.amount, r.frequency, r.frequency_days)

            def make_toggle(rec=r):
                def _toggle(_):
                    db.toggle_recurring(rec.id, not rec.active)
                    refresh_rec()
                    on_data_changed()
                return _toggle

            def make_delete_rec(rec=r):
                def _del(_):
                    label = f"{rec.category} — {peso(rec.amount)} ({FREQ_DISPLAY.get(rec.frequency, rec.frequency)})"
                    def confirm_del(_):
                        if hasattr(page, "close"):
                            page.close(confirm_dlg)
                        else:
                            confirm_dlg.open = False
                            page.update()
                        db.delete_recurring(rec.id)
                        refresh_rec()
                        on_data_changed()
                        _toast(page, "Recurring transaction removed.")
                    def cancel_del(_):
                        if hasattr(page, "close"):
                            page.close(confirm_dlg)
                        else:
                            confirm_dlg.open = False
                            page.update()
                    confirm_dlg = ft.AlertDialog(
                        modal=True,
                        title=ft.Row(controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400),
                            ft.Text("Delete Recurring?", weight=ft.FontWeight.BOLD),
                        ]),
                        content=ft.Text(
                            f"Remove this recurring schedule?\n\n{label}\n\n"
                            "Future auto-entries won't be created anymore, but past ones stay.\n"
                            "This cannot be undone.",
                        ),
                        actions=[
                            ft.TextButton("Cancel", on_click=cancel_del),
                            ft.ElevatedButton(
                                "Delete",
                                icon=ft.Icons.DELETE,
                                on_click=confirm_del,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                            ),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    _open_dialog(page, confirm_dlg)
                return _del

            def make_edit_rec(rec=r):
                def _edit(_):
                    def done(**_kw):
                        refresh_rec()
                        on_data_changed()
                    _edit_recurring_dialog(page, rec, done)
                return _edit

            rec_list.controls.append(
                ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=ft.Padding(12, 10, 12, 8),
                        border=ft.border.all(
                            1,
                            border_col if border_col != ft.Colors.TRANSPARENT else ft.Colors.TRANSPARENT,
                        ),
                        border_radius=10,
                        opacity=1.0 if r.active else 0.45,
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=10,
                                            expand=True,
                                            controls=[
                                                ft.Container(
                                                    width=36, height=36,
                                                    border_radius=18,
                                                    bgcolor=ft.Colors.with_opacity(0.15, color),
                                                    alignment=ft.Alignment(0, 0),
                                                    content=ft.Icon(icon, size=16, color=color),
                                                ),
                                                ft.Column(
                                                    spacing=2,
                                                    expand=True,
                                                    controls=[
                                                        ft.Row(
                                                            spacing=6,
                                                            wrap=True,
                                                            controls=[
                                                                ft.Text(
                                                                    r.category,
                                                                    weight=ft.FontWeight.W_600,
                                                                    size=14,
                                                                ),
                                                                ft.Container(
                                                                    padding=ft.Padding(4, 1, 4, 1),
                                                                    border_radius=4,
                                                                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER_400),
                                                                    content=ft.Text(
                                                                        freq_label,
                                                                        size=10,
                                                                        color=ft.Colors.AMBER_300,
                                                                        weight=ft.FontWeight.BOLD,
                                                                    ),
                                                                ),
                                                                days_badge,
                                                            ],
                                                        ),
                                                        ft.Text(
                                                            r.description or "—",
                                                            size=12,
                                                            color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                                                        ),
                                                        ft.Row(
                                                            spacing=4,
                                                            controls=[
                                                                ft.Icon(ft.Icons.EVENT_REPEAT, size=11, color=ft.Colors.CYAN_400),
                                                                ft.Text(
                                                                    f"Next: {next_fmt}",
                                                                    size=11,
                                                                    color=ft.Colors.CYAN_300,
                                                                ),
                                                                ft.Text("·", size=11, color=ft.Colors.with_opacity(0.24, ft.Colors.ON_SURFACE)),
                                                                ft.Text(
                                                                    f"≈{peso(monthly_val)}/mo",
                                                                    size=11,
                                                                    color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            controls=[
                                                ft.Text(
                                                    peso(r.amount),
                                                    color=color,
                                                    size=15,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                                ft.Switch(
                                                    value=r.active,
                                                    active_color=ft.Colors.CYAN_400,
                                                    on_change=make_toggle(r),
                                                    label="On" if r.active else "Off",
                                                    label_position=ft.LabelPosition.LEFT,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    spacing=0,
                                    controls=[
                                        ft.TextButton(
                                            "Edit",
                                            icon=ft.Icons.EDIT_OUTLINED,
                                            on_click=make_edit_rec(r),
                                        ),
                                        ft.TextButton(
                                            "Remove",
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            style=ft.ButtonStyle(color=ft.Colors.RED_300),
                                            on_click=make_delete_rec(r),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                )
            )
        page.update()

    refresh_rec()
    return rec_list


# ---------------------------------------------------------------------------
# MAIN SCREEN
# ---------------------------------------------------------------------------

def transactions_screen(page: ft.Page, on_data_changed) -> ft.Control:
    peso = make_peso(db.get_currency())  # dynamic currency

    search_field = ft.TextField(label="Search", expand=True)
    category_filter = ft.Dropdown(
        label="Category",
        value="All",
        width=155,
        options=(
            [ft.dropdown.Option("All")]
            + [ft.dropdown.Option(c) for c in DEFAULT_CATEGORIES]
            + [ft.dropdown.Option(c) for c in INCOME_CATEGORIES]
            + [ft.dropdown.Option("Income")]
        ),
    )

    def _build_filter_date_button(label: str) -> tuple[list[date | None], ft.OutlinedButton]:
        selected: list[date | None] = [None]
        button_label = ft.Text(label)
        button = ft.OutlinedButton(
            content=button_label,
            icon=ft.Icons.CALENDAR_MONTH,
        )
        picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2099, 12, 31),
        )

        def _sync_button() -> None:
            button_label.value = selected[0].strftime("%b %d, %Y") if selected[0] else label
            button.icon_color = ft.Colors.CYAN_300 if selected[0] else None

        def _on_change(e):
            picked = calendar_date_from_picker(picker, e)
            if picked is None:
                return
            selected[0] = picked
            _sync_button()
            refresh_list()

        picker.on_change = _on_change
        page.overlay.append(picker)
        button.on_click = lambda _: _open_picker(page, picker, selected[0] or date.today())
        _sync_button()
        return selected, button

    date_from_filter, date_from_btn = _build_filter_date_button("Start date")
    date_to_filter, date_to_btn = _build_filter_date_button("End date")

    one_time_list = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    show_recurring_state = [False]
    rec_container = ft.Column(visible=False, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def refresh_recurring():
        rec_container.controls.clear()
        rec_container.controls.append(
            _build_recurring_section(page, on_data_changed)
        )

    def refresh_list(_=None):
        date_from = date_from_filter[0]
        date_to = date_to_filter[0]
        if date_from and date_to and date_from > date_to:
            date_from, date_to = date_to, date_from

        txns = db.get_transactions(
            search=search_field.value.strip(),
            category=category_filter.value,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        )
        one_time_list.controls.clear()

        if not txns:
            has_filters = bool(
                search_field.value.strip()
                or (category_filter.value and category_filter.value != "All")
                or date_from
                or date_to
            )
            one_time_list.controls.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=52, color=ft.Colors.with_opacity(0.24, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                "No matching transactions" if has_filters else "No transactions yet",
                                color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                                text_align=ft.TextAlign.CENTER,
                                size=14,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                "Try a different search, category, or date range."
                                if has_filters else
                                "Add your first expense or income and your transaction history will appear here.",
                                color=ft.Colors.with_opacity(0.42, ft.Colors.ON_SURFACE),
                                text_align=ft.TextAlign.CENTER,
                                size=12,
                            ),
                        ],
                    ),
                )
            )
            page.update()
            return

        running = db.get_balance()

        for txn in txns:
            is_income = txn.txn_type == "income"
            sign = "+" if is_income else "−"
            amt_color = ft.Colors.GREEN_400 if is_income else ft.Colors.RED_400
            arrow_icon = ft.Icons.ARROW_DOWNWARD if is_income else ft.Icons.ARROW_UPWARD
            icon_bg = ft.Colors.with_opacity(
                0.15, ft.Colors.GREEN_400 if is_income else ft.Colors.RED_400
            )
            is_auto = txn.description.startswith("[Auto]")

            balance_after = running
            running = running - txn.amount if is_income else running + txn.amount

            def make_edit(t=txn):
                def _edit(_):
                    def done(**_kw):  # **_kw absorbs was_recurring= from dialog
                        refresh_list()
                        on_data_changed()
                    if t.txn_type == "income":
                        _income_dialog(page, done, t)
                    else:
                        _expense_dialog(page, done, t)
                return _edit

            def make_delete(tid=txn.id):
                def _del(_):
                    def done(**_kw):
                        refresh_list()
                        on_data_changed()
                    _delete_dialog(page, tid, done)
                return _del

            one_time_list.controls.append(
                ft.Card(
                    elevation=2,
                    content=ft.Container(
                        padding=ft.Padding(12, 10, 12, 6),
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    controls=[
                                        ft.Row(
                                            expand=True,
                                            spacing=10,
                                            vertical_alignment=ft.CrossAxisAlignment.START,
                                            controls=[
                                                ft.Container(
                                                    width=38, height=38,
                                                    border_radius=19,
                                                    bgcolor=icon_bg,
                                                    alignment=ft.Alignment(0, 0),
                                                    content=ft.Icon(arrow_icon, size=18, color=amt_color),
                                                ),
                                                ft.Column(
                                                    spacing=2,
                                                    expand=True,
                                                    controls=[
                                                        ft.Row(spacing=6, wrap=True, controls=[
                                                            ft.Text(txn.category, weight=ft.FontWeight.W_600, size=14),
                                                            *(
                                                                [ft.Container(
                                                                    padding=ft.Padding(3, 1, 3, 1),
                                                                    border_radius=4,
                                                                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.AMBER_400),
                                                                    content=ft.Text("Auto", size=9, color=ft.Colors.AMBER_300),
                                                                )]
                                                                if is_auto else []
                                                            ),
                                                            *([_b] if (_b := _txn_date_badge(txn.txn_date)) is not None else []),
                                                        ]),
                                                        ft.Text(
                                                            (txn.description.replace("[Auto] ", "") or "—"),
                                                            size=12,
                                                            color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                                                            max_lines=2,
                                                            overflow=ft.TextOverflow.ELLIPSIS,
                                                        ),
                                                        ft.Row(
                                                            spacing=4,
                                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                            controls=[
                                                                ft.Icon(ft.Icons.HISTORY, size=11, color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)),
                                                                ft.Text(
                                                                    "Logged: "
                                                                    + datetime.strptime(txn.logged_date or txn.txn_date, "%Y-%m-%d").strftime("%b %d, %Y"),
                                                                    size=11,
                                                                    color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                                                                ),
                                                            ],
                                                        ),
                                                        ft.Row(
                                                            spacing=4,
                                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                            controls=[
                                                                ft.Icon(ft.Icons.CALENDAR_TODAY, size=11, color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE)),
                                                                ft.Text(
                                                                    ("Income on: " if is_income else "Deducted on: ")
                                                                    + datetime.strptime(txn.txn_date, "%Y-%m-%d").strftime("%b %d, %Y"),
                                                                    size=11,
                                                                    color=ft.Colors.CYAN_300
                                                                    if datetime.strptime(txn.txn_date, "%Y-%m-%d").date() > date.today()
                                                                    else ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            controls=[
                                                ft.Text(
                                                    f"{sign} {peso(txn.amount)}",
                                                    color=amt_color,
                                                    size=16,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                                ft.Text(
                                                    f"bal: {peso(balance_after)}",
                                                    size=11,
                                                    color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.END,
                                    spacing=0,
                                    controls=[
                                        ft.TextButton("Edit", icon=ft.Icons.EDIT_OUTLINED, on_click=make_edit(txn)),
                                        ft.TextButton(
                                            "Delete",
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            style=ft.ButtonStyle(color=ft.Colors.RED_300),
                                            on_click=make_delete(txn.id),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                )
            )
        page.update()

    def open_expense(_):
        def done(was_recurring=False):
            refresh_list()
            if was_recurring:
                # Keep the recurring panel open and refreshed
                show_recurring_state[0] = True
                rec_container.visible = True
                toggle_rec_btn.content.value = "Hide Recurring"
                toggle_rec_btn.icon = ft.Icons.EXPAND_LESS
                refresh_recurring()
                page.update()
            else:
                on_data_changed()
        _expense_dialog(page, done)

    def open_income(_):
        def done(was_recurring=False):
            refresh_list()
            if was_recurring:
                show_recurring_state[0] = True
                rec_container.visible = True
                toggle_rec_btn.content.value = "Hide Recurring"
                toggle_rec_btn.icon = ft.Icons.EXPAND_LESS
                refresh_recurring()
                page.update()
            else:
                on_data_changed()
        _income_dialog(page, done)

    def toggle_recurring_view(_):
        show_recurring_state[0] = not show_recurring_state[0]
        rec_container.visible = show_recurring_state[0]
        toggle_rec_btn.content.value = "Hide Recurring" if show_recurring_state[0] else "Recurring Schedule"
        toggle_rec_btn.icon = ft.Icons.EXPAND_LESS if show_recurring_state[0] else ft.Icons.REPEAT
        if show_recurring_state[0]:
            refresh_recurring()
        page.update()

    toggle_rec_btn = ft.OutlinedButton(
        content=ft.Text("Recurring Schedule"),
        icon=ft.Icons.REPEAT,
        on_click=toggle_recurring_view,
    )

    def clear_filters(_=None):
        search_field.value = ""
        category_filter.value = "All"
        date_from_filter[0] = None
        date_to_filter[0] = None
        date_from_btn.content.value = "Start date"
        date_to_btn.content.value = "End date"
        date_from_btn.icon_color = None
        date_to_btn.icon_color = None
        refresh_list()

    search_field.on_submit = refresh_list
    category_filter.on_change = refresh_list

    toolbar = ft.Row(
        wrap=True,
        spacing=8,
        controls=[
            ft.ElevatedButton(
                "Add Expense",
                icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                on_click=open_expense,
                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_500, color=ft.Colors.WHITE),
            ),
            ft.ElevatedButton(
                "Add Income",
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                on_click=open_income,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
            ),
            toggle_rec_btn,
        ],
    )

    filter_row = ft.ResponsiveRow(
        controls=[
            ft.Container(col={"xs": 12, "lg": 4}, content=search_field),
            ft.Container(col={"xs": 12, "md": 6, "lg": 2}, content=category_filter),
            ft.Container(col={"xs": 12, "md": 6, "lg": 2}, content=date_from_btn),
            ft.Container(col={"xs": 12, "md": 6, "lg": 2}, content=date_to_btn),
            ft.Container(
                col={"xs": 6, "md": 3, "lg": 1},
                alignment=ft.Alignment(1, 0),
                content=ft.IconButton(ft.Icons.SEARCH, tooltip="Search", on_click=refresh_list),
            ),
            ft.Container(
                col={"xs": 6, "md": 3, "lg": 1},
                alignment=ft.Alignment(1, 0),
                content=ft.IconButton(ft.Icons.CLEAR_ALL, tooltip="Clear filters", on_click=clear_filters),
            ),
        ],
    )

    refresh_list()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            toolbar,
            ft.Card(
                elevation=2,
                content=ft.Container(
                    padding=10,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("🔁 Recurring / Scheduled", weight=ft.FontWeight.BOLD, size=13),
                                ],
                            ),
                            rec_container,
                        ],
                    ),
                ),
                visible=True,
            ),
            ft.Card(
                elevation=2,
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("Find Transactions", weight=ft.FontWeight.BOLD, size=13),
                            ft.Text(
                                "Search by keyword, category, or a single day or date range.",
                                size=11,
                                color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE),
                            ),
                            filter_row,
                        ],
                    ),
                ),
            ),
            ft.Text("All Transactions", weight=ft.FontWeight.BOLD, size=13),
            one_time_list,
        ],
    )
