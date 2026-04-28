from __future__ import annotations

from datetime import datetime, date, timedelta

import flet as ft

import database as db
from ui.constants import DEFAULT_CATEGORIES, now_month, peso, make_peso
from utils import calendar_date_from_picker


def _dialog_width(page: ft.Page, *, max_width: int = 340, min_width: int = 280) -> int:
    width = page.width or getattr(page, "window_width", None) or max_width
    return int(min(max_width, max(min_width, width - 32)))


def _open_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
    else:
        page.dialog = dialog
        dialog.open = True
        page.update()


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _days_remaining(end_date_str: str | None) -> str:
    if not end_date_str:
        return ""
    try:
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        today = date.today()
        diff = (end - today).days
        if diff < 0:
            return "Expired"
        elif diff == 0:
            return "Ends today!"
        else:
            return f"{diff} day(s) left"
    except Exception:
        return ""


def _duration_label(b) -> str:
    if b.start_date and b.end_date:
        try:
            s = datetime.strptime(b.start_date, "%Y-%m-%d").date()
            e = datetime.strptime(b.end_date, "%Y-%m-%d").date()
            days = (e - s).days + 1
            return f"{days} day(s)"
        except Exception:
            pass
    return f"{b.duration_days} day(s)"


def _make_date_picker(
    page: ft.Page,
    *,
    initial: date,
    on_picked,          # callback(picked: date) -> None
    first_date: datetime | None = None,
    last_date: datetime | None = None,
) -> ft.DatePicker:
    """Create and register a DatePicker in page.overlay."""
    picker = ft.DatePicker(
        first_date=first_date or datetime(2020, 1, 1),
        last_date=last_date or datetime(2099, 12, 31),
    )

    def _on_change(e: ft.ControlEvent):
        picked = calendar_date_from_picker(picker, e)
        if picked is not None:
            on_picked(picked)

    picker.on_change = _on_change
    page.overlay.append(picker)
    return picker


def _open_picker(page: ft.Page, picker: ft.DatePicker, current: date) -> None:
    # Noon avoids midnight UTC/local confusion in the native date picker.
    picker.value = datetime(current.year, current.month, current.day, 12, 0, 0)
    if hasattr(page, "open"):
        page.open(picker)
    else:
        picker.open = True
    page.update()


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

def _edit_budget_dialog(page: ft.Page, b, on_done) -> None:
    """Pre-filled edit dialog for an existing budget limit."""
    peso = make_peso(db.get_currency())  # dynamic currency
    dialog_width = _dialog_width(page)
    sel_start: list[date] = [datetime.strptime(b.start_date, "%Y-%m-%d").date() if b.start_date else date.today()]
    sel_end:   list[date] = [datetime.strptime(b.end_date,   "%Y-%m-%d").date() if b.end_date   else date.today() + timedelta(days=29)]

    limit_input = ft.TextField(
        label="Limit amount (₱)",
        value=f"{b.monthly_limit:.2f}",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        width=200,
    )

    duration_chip = ft.Text("", size=12, color=ft.Colors.CYAN_300, italic=True)

    def _refresh_duration():
        days = (sel_end[0] - sel_start[0]).days + 1
        if days < 1:
            duration_chip.value = "⚠️  End must be after start"
            duration_chip.color = ft.Colors.RED_300
        else:
            duration_chip.value = (
                f"Duration: {days} day(s)  ·  "
                f"{sel_start[0].strftime('%b %d')} → {sel_end[0].strftime('%b %d, %Y')}"
            )
            duration_chip.color = ft.Colors.CYAN_300
        page.update()

    start_btn_label = ft.Text(sel_start[0].strftime("%b %d, %Y"))
    start_btn = ft.OutlinedButton(content=start_btn_label, icon=ft.Icons.CALENDAR_TODAY)

    end_btn_label = ft.Text(sel_end[0].strftime("%b %d, %Y"))
    end_btn = ft.OutlinedButton(content=end_btn_label, icon=ft.Icons.EVENT)

    def _on_start_picked(picked: date):
        sel_start[0] = picked
        start_btn_label.value = picked.strftime("%b %d, %Y")
        if sel_end[0] < picked:
            sel_end[0] = picked
            end_btn_label.value = picked.strftime("%b %d, %Y")
        _refresh_duration()

    def _on_end_picked(picked: date):
        if picked < sel_start[0]:
            page.snack_bar = ft.SnackBar(ft.Text("End date must be on or after start."))
            page.snack_bar.open = True
            page.update()
            return
        sel_end[0] = picked
        end_btn_label.value = picked.strftime("%b %d, %Y")
        _refresh_duration()

    start_picker = _make_date_picker(page, initial=sel_start[0], on_picked=_on_start_picked)
    end_picker   = _make_date_picker(page, initial=sel_end[0],   on_picked=_on_end_picked)
    start_btn.on_click = lambda _: _open_picker(page, start_picker, sel_start[0])
    end_btn.on_click   = lambda _: _open_picker(page, end_picker,   sel_end[0])

    _refresh_duration()

    def _close(dlg):
        if hasattr(page, "close"):
            page.close(dlg)
        else:
            dlg.open = False
            page.update()

    def save(_):
        try:
            val = float(limit_input.value.strip().replace(",", ""))
            if val <= 0:
                raise ValueError
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("Enter a valid positive limit."))
            page.snack_bar.open = True
            page.update()
            return
        if sel_end[0] < sel_start[0]:
            page.snack_bar = ft.SnackBar(ft.Text("End date must be on or after start date."))
            page.snack_bar.open = True
            page.update()
            return
        duration_days = (sel_end[0] - sel_start[0]).days + 1
        db.update_budget_limit(
            budget_id=b.id,
            monthly_limit=val,
            duration_type="custom",
            duration_days=duration_days,
            start_date=sel_start[0].isoformat(),
            end_date=sel_end[0].isoformat(),
        )
        _close(dlg)
        on_done()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(controls=[
            ft.Icon(ft.Icons.EDIT, color=ft.Colors.CYAN_400),
            ft.Text(f"Edit Budget — {b.category}", weight=ft.FontWeight.BOLD, size=15),
        ]),
        content=ft.Container(
            width=dialog_width,
            content=ft.Column(
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(
                        f"Category: {b.category}",
                        size=13,
                        color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                    ),
                    limit_input,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    ft.Column(spacing=4, controls=[
                        ft.Text("Start Date", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                        start_btn,
                    ]),
                    ft.Column(spacing=4, controls=[
                        ft.Text("End Date", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                        end_btn,
                    ]),
                    duration_chip,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: _close(dlg)),
            ft.ElevatedButton(
                "Save Changes",
                icon=ft.Icons.SAVE,
                on_click=save,
                style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    if hasattr(page, "show_dialog"):
        page.show_dialog(dlg)
    else:
        page.dialog = dlg
        dlg.open = True
        page.update()


def budgets_screen(page: ft.Page, on_data_changed) -> ft.Control:
    peso = make_peso(db.get_currency())  # dynamic currency
    # ---- Mutable state ----
    sel_start: list[date] = [date.today()]
    sel_end:   list[date] = [date.today() + timedelta(days=29)]

    # ---- Form fields ----
    category = ft.Dropdown(
        label="Category",
        width=200,
        value=DEFAULT_CATEGORIES[0],
        options=[ft.dropdown.Option(c) for c in DEFAULT_CATEGORIES],
    )
    limit_input = ft.TextField(
        label="Limit amount (₱)",
        width=160,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    # ---- Start date UI ----
    start_btn_label = ft.Text(sel_start[0].strftime("%b %d, %Y"))
    start_btn = ft.OutlinedButton(
        content=start_btn_label,
        icon=ft.Icons.CALENDAR_TODAY,
    )

    # ---- End date UI ----
    end_btn_label = ft.Text(sel_end[0].strftime("%b %d, %Y"))
    end_btn = ft.OutlinedButton(
        content=end_btn_label,
        icon=ft.Icons.EVENT,
    )

    # ---- Duration chip (auto-computed) ----
    duration_chip = ft.Text("", size=12, color=ft.Colors.CYAN_300, italic=True)

    budget_list = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def toast(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg))
        page.snack_bar.open = True
        page.update()

    # ---- Recompute duration label ----
    def _refresh_duration():
        days = (sel_end[0] - sel_start[0]).days + 1
        if days < 1:
            duration_chip.value = "⚠️  End must be after start"
            duration_chip.color = ft.Colors.RED_300
        else:
            duration_chip.value = f"Duration: {days} day(s)  ·  {sel_start[0].strftime('%b %d')} → {sel_end[0].strftime('%b %d, %Y')}"
            duration_chip.color = ft.Colors.CYAN_300
        page.update()

    # ---- Start date picker ----
    def _on_start_picked(picked: date):
        sel_start[0] = picked
        start_btn_label.value = picked.strftime("%b %d, %Y")
        # If end is now before start, push end forward
        if sel_end[0] < picked:
            sel_end[0] = picked
            end_btn_label.value = picked.strftime("%b %d, %Y")
        _refresh_duration()

    start_picker = _make_date_picker(page, initial=sel_start[0], on_picked=_on_start_picked)
    start_btn.on_click = lambda _: _open_picker(page, start_picker, sel_start[0])

    # ---- End date picker ----
    def _on_end_picked(picked: date):
        if picked < sel_start[0]:
            toast("End date must be on or after the start date.")
            return
        sel_end[0] = picked
        end_btn_label.value = picked.strftime("%b %d, %Y")
        _refresh_duration()

    end_picker = _make_date_picker(page, initial=sel_end[0], on_picked=_on_end_picked)
    end_btn.on_click = lambda _: _open_picker(page, end_picker, sel_end[0])

    # Initialise label
    _refresh_duration()

    # ---- Save ----
    def save_limit(_):
        try:
            value = float(limit_input.value)
            if value <= 0:
                raise ValueError
        except ValueError:
            toast("Enter a valid positive limit.")
            return

        if sel_end[0] < sel_start[0]:
            toast("End date must be on or after start date.")
            return

        duration_days = (sel_end[0] - sel_start[0]).days + 1

        db.set_budget_limit(
            category=category.value,
            monthly_limit=value,
            duration_type="custom",
            duration_days=duration_days,
            start_date=sel_start[0].isoformat(),
            end_date=sel_end[0].isoformat(),
        )
        limit_input.value = ""
        refresh()
        on_data_changed()
        toast(f"Budget set! {sel_start[0].strftime('%b %d')} → {sel_end[0].strftime('%b %d, %Y')}  ({duration_days} days)")

    # ---- Budget list ----
    def refresh():
        budget_list.controls.clear()
        limits = db.get_budget_limits()
        today_str = date.today().isoformat()

        if not limits:
            budget_list.controls.append(
                ft.Text("No budget limits yet. Add one above.", color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE))
            )
            page.update()
            return

        for b in limits:
            start = b.start_date or now_month() + "-01"
            end   = b.end_date   or today_str

            if b.end_date and b.end_date < today_str:
                period_label = ft.Text(
                    "Period ended",
                    color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                    size=11,
                    italic=True,
                )
            else:
                period_label = ft.Text(
                    _days_remaining(b.end_date),
                    color=ft.Colors.AMBER_300,
                    size=11,
                    weight=ft.FontWeight.BOLD,
                )

            spend_map = db.get_expense_summary_range(start, end)
            spent = spend_map.get(b.category, 0.0)
            ratio = min(spent / b.monthly_limit, 1.0) if b.monthly_limit else 0.0
            over  = spent > b.monthly_limit
            color = ft.Colors.RED_400 if over else ft.Colors.CYAN_400

            dur_display = _duration_label(b)

            def make_edit(budget=b):
                def _edit(_):
                    def done():
                        refresh()
                        on_data_changed()
                    _edit_budget_dialog(page, budget, done)
                return _edit

            def make_delete(budget=b):
                def _del(_):
                    def confirm_del(_):
                        if hasattr(page, "close"):
                            page.close(confirm_dlg)
                        else:
                            confirm_dlg.open = False
                            page.update()
                        db.delete_budget_limit(budget.id)
                        refresh()
                        on_data_changed()
                        toast("Budget limit deleted.")
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
                            ft.Text("Delete Budget Limit?", weight=ft.FontWeight.BOLD),
                        ]),
                        content=ft.Text(
                            f"Remove the budget limit for '{budget.category}'?\n\n"
                            f"Limit: {peso(budget.monthly_limit)}\n\n"
                            "Your transactions won't be deleted. This cannot be undone.",
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
            start_fmt = datetime.strptime(start, "%Y-%m-%d").strftime("%b %d") if start else "—"
            end_fmt   = datetime.strptime(end,   "%Y-%m-%d").strftime("%b %d, %Y") if end else "—"

            budget_list.controls.append(
                ft.Card(
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Column(
                                            spacing=0,
                                            controls=[
                                                ft.Text(b.category, weight=ft.FontWeight.BOLD, size=15),
                                                ft.Text(
                                                    f"{dur_display}  ·  {start_fmt} → {end_fmt}",
                                                    size=11,
                                                    color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                                                ),
                                            ],
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            controls=[
                                                ft.Text(
                                                    f"{peso(spent)} / {peso(b.monthly_limit)}",
                                                    size=13,
                                                ),
                                                period_label,
                                            ],
                                        ),
                                    ],
                                ),
                                ft.ProgressBar(
                                    value=ratio,
                                    color=color,
                                    bgcolor=ft.Colors.with_opacity(0.24, ft.Colors.ON_SURFACE),
                                    border_radius=4,
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            "🚨 Over budget na bro!" if over else "✅ On track",
                                            color=ft.Colors.RED_300 if over else ft.Colors.GREEN_300,
                                            size=12,
                                        ),
                                        ft.Text(
                                            f"{ratio * 100:.0f}% used",
                                            size=11,
                                            color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
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
                                            on_click=make_edit(b),
                                        ),
                                        ft.TextButton(
                                            "Delete",
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            style=ft.ButtonStyle(color=ft.Colors.RED_300),
                                            on_click=make_delete(b),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
            )
        page.update()

    refresh()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text(
                                "Set Budget Limit",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                            ),

                            # ── Row 1: category + amount ──────────────────────
                            ft.ResponsiveRow(
                                controls=[
                                    ft.Container(col={"xs": 12, "md": 7}, content=category),
                                    ft.Container(col={"xs": 12, "md": 5}, content=limit_input),
                                ],
                            ),

                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),

                            # ── Row 2: Start Date ─────────────────────────────
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text(
                                        "Start Date",
                                        size=12,
                                        color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                                        weight=ft.FontWeight.W_500,
                                    ),
                                    start_btn,
                                ],
                            ),

                            # ── Row 3: End Date ───────────────────────────────
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text(
                                        "End Date",
                                        size=12,
                                        color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                                        weight=ft.FontWeight.W_500,
                                    ),
                                    end_btn,
                                ],
                            ),

                            # ── Auto-computed duration ─────────────────────────
                            duration_chip,

                            ft.ElevatedButton(
                                "Save Budget Limit",
                                icon=ft.Icons.SAVE,
                                on_click=save_limit,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.CYAN_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                        ],
                    ),
                )
            ),
            ft.Text("Your Budget Trackers", weight=ft.FontWeight.BOLD, size=14),
            budget_list,
        ],
    )
