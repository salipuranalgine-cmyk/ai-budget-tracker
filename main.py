from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

import flet as ft

import database as db
import notifications as notif
import user_manager as um
from ui.budgets_screen import budgets_screen
from ui.dashboard_screen import dashboard_screen
from ui.profile_select_screen import show_profile_select_screen
from ui.settings_screen import settings_screen
from ui.transactions_screen import transactions_screen


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
    elif hasattr(page, "close"):
        page.close(dialog)
    else:
        dialog.open = False
        page.update()


def main(page: ft.Page):
    um.init_users_db()

    icon_path = Path(__file__).resolve().parent / "assets" / "Icon.ico"

    page.title = "AI Smart Saver - Budget Guardian"
    page.window.icon = str(icon_path)
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.window_min_width = 360
    page.window_min_height = 640
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.CYAN)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)

    content = ft.Container(expand=True)
    title = ft.Text("AI Smart Saver", weight=ft.FontWeight.BOLD, size=18)

    # Mutable references shared across closures
    nav_ref: list[ft.NavigationBar | None] = [None]
    render_ref: list[Callable[[int], None] | None] = [None]

    def toggle_theme(_):
        page.theme_mode = (
            ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        )
        if render_ref[0] is not None and nav_ref[0] is not None:
            render_ref[0](nav_ref[0].selected_index)
            return
        page.update()

    # ── USER SELECTION SCREEN ────────────────────────────────────────────────

    def show_user_select(auto_resume: bool = True):
        show_profile_select_screen(
            page,
            content,
            auto_resume=auto_resume,
            toggle_theme=toggle_theme,
            launch_main_app=launch_main_app,
            open_dialog=_open_dialog,
            close_dialog=_close_dialog,
        )

    def launch_main_app(user: um.UserProfile):
        """Initialize the budget app for the selected user profile."""
        um.set_last_active_user(user.id)
        db.set_user_db(um.get_db_path(user.id))
        db.init_db()
        db.init_notifications_table()
        applied = db.apply_due_recurring()

        # Reset notifications for fresh session
        notif.reset()

        title.value = "Dashboard"

        # ── Notification bell state ──────────────────────────────────────────
        bell_icon  = ft.Ref[ft.IconButton]()
        badge_text = ft.Ref[ft.Text]()
        badge_dot  = ft.Ref[ft.Container]()

        def _refresh_bell():
            count = notif.unread_count()
            if badge_text.current:
                badge_text.current.value   = str(count) if count < 100 else "99+"
                badge_dot.current.visible  = count > 0
                bell_icon.current.icon     = (
                    ft.Icons.NOTIFICATIONS_ROUNDED if count > 0
                    else ft.Icons.NOTIFICATIONS_OUTLINED
                )
            try:
                page.update()
            except Exception:
                pass

        notif.subscribe(_refresh_bell)

        # ── Notification panel dialog ────────────────────────────────────────
        def _open_notif_panel(_=None):
            notif_list = ft.Column(
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )

            TYPE_META = {
                "budget_exceeded": ("🔴", "#ef4444"),
                "budget_warning":  ("🟠", "#f97316"),
                "bill_due":        ("📅", "#38bdf8"),
                "ai_insight":      ("🤖", "#a78bfa"),
                "info":            ("ℹ️",  "#64748b"),
            }

            def _rebuild_list():
                notif_list.controls.clear()
                all_notifs = notif.get_all()
                if not all_notifs:
                    notif_list.controls.append(
                        ft.Container(
                            padding=40,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=8,
                                controls=[
                                    ft.Text("🔔", size=36),
                                    ft.Text("All caught up!",
                                            size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text("No notifications yet.",
                                            size=12,
                                            color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                                ],
                            ),
                        )
                    )
                else:
                    for n in all_notifs:
                        icon_char, accent = TYPE_META.get(
                            n.notif_type, ("🔔", "#64748b")
                        )
                        def _make_dismiss(nid):
                            def _dismiss(_):
                                notif.mark_read(nid)
                                _rebuild_list()
                                page.update()
                            return _dismiss

                        notif_list.controls.append(
                            ft.Container(
                                border_radius=12,
                                bgcolor=ft.Colors.with_opacity(
                                    0.03 if n.read else 0.08, ft.Colors.WHITE
                                ),
                                border=ft.border.all(
                                    1,
                                    ft.Colors.with_opacity(
                                        0.06 if n.read else 0.18, accent
                                    ),
                                ),
                                padding=ft.Padding(left=0, right=12, top=0, bottom=0),
                                content=ft.Row(
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    controls=[
                                        # Colored left bar
                                        ft.Container(
                                            width=4,
                                            border_radius=ft.BorderRadius(
                                                top_left=12, bottom_left=12,
                                                top_right=0, bottom_right=0,
                                            ),
                                            bgcolor=accent if not n.read
                                            else ft.Colors.with_opacity(0.25, accent),
                                            height=None,
                                            expand=False,
                                        ),
                                        ft.Container(width=10),
                                        # Icon
                                        ft.Container(
                                            padding=ft.padding.only(top=12),
                                            content=ft.Text(icon_char, size=20),
                                        ),
                                        ft.Container(width=10),
                                        # Content
                                        ft.Column(
                                            expand=True,
                                            spacing=3,
                                            controls=[
                                                ft.Container(height=10),
                                                ft.Row(
                                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                    controls=[
                                                        ft.Text(
                                                            n.title,
                                                            size=13,
                                                            weight=ft.FontWeight.BOLD
                                                            if not n.read
                                                            else ft.FontWeight.W_400,
                                                            expand=True,
                                                            color=ft.Colors.WHITE
                                                            if not n.read
                                                            else ft.Colors.with_opacity(
                                                                0.6, ft.Colors.ON_SURFACE
                                                            ),
                                                        ),
                                                        ft.Text(
                                                            n.timestamp,
                                                            size=10,
                                                            color=ft.Colors.with_opacity(
                                                                0.4, ft.Colors.ON_SURFACE
                                                            ),
                                                        ),
                                                    ],
                                                ),
                                                ft.Text(
                                                    n.body,
                                                    size=12,
                                                    max_lines=3,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                    color=ft.Colors.with_opacity(
                                                        0.5 if n.read else 0.78,
                                                        ft.Colors.ON_SURFACE,
                                                    ),
                                                ),
                                                ft.Container(height=8),
                                            ],
                                        ),
                                        # Dismiss dot / mark-read button
                                        ft.Container(
                                            padding=ft.padding.only(top=12),
                                            content=ft.IconButton(
                                                icon=ft.Icons.CIRCLE
                                                if not n.read
                                                else ft.Icons.CIRCLE_OUTLINED,
                                                icon_color=accent if not n.read
                                                else ft.Colors.with_opacity(
                                                    0.25, ft.Colors.ON_SURFACE
                                                ),
                                                icon_size=10,
                                                tooltip="Mark as read",
                                                on_click=_make_dismiss(n.id),
                                            ),
                                        ),
                                    ],
                                ),
                            )
                        )
                try:
                    page.update()
                except Exception:
                    pass

            def _mark_all(_):
                notif.mark_all_read()
                _rebuild_list()

            def _clear_all(_):
                notif.clear_all()
                _rebuild_list()

            panel_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=8, controls=[
                            ft.Text("🔔", size=20),
                            ft.Text("Notifications",
                                    weight=ft.FontWeight.BOLD, size=16),
                        ]),
                        ft.Row(spacing=0, controls=[
                            ft.TextButton(
                                "Mark all read",
                                icon=ft.Icons.DONE_ALL_ROUNDED,
                                on_click=_mark_all,
                                style=ft.ButtonStyle(
                                    color=ft.Colors.with_opacity(
                                        0.6, ft.Colors.ON_SURFACE
                                    )
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                                icon_color=ft.Colors.RED_300,
                                tooltip="Clear all",
                                on_click=_clear_all,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=20,
                                on_click=lambda _: _close_panel(),
                            ),
                        ]),
                    ],
                ),
                content=ft.Container(
                    width=480,
                    height=500,
                    content=notif_list,
                ),
                actions=[],
            )

            def _close_panel():
                panel_dlg.open = False
                page.update()

            page.overlay.append(panel_dlg)
            panel_dlg.open = True
            _rebuild_list()
            page.update()

        # ── Bell button widget ───────────────────────────────────────────────
        def _open_notif_panel_v2(_=None):
            notif_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
            selected_ids: set[int] = set()
            selection_mode = [False]

            type_meta = {
                "budget_exceeded": (ft.Icons.ERROR_ROUNDED, "#ef4444"),
                "budget_warning": (ft.Icons.WARNING_AMBER_ROUNDED, "#f97316"),
                "bill_due": (ft.Icons.CALENDAR_MONTH, "#38bdf8"),
                "ai_insight": (ft.Icons.AUTO_AWESOME, "#a78bfa"),
                "info": (ft.Icons.INFO_OUTLINED, "#64748b"),
            }

            def _show_overlay_dialog(dialog: ft.AlertDialog) -> None:
                if dialog not in page.overlay:
                    page.overlay.append(dialog)
                dialog.open = True
                page.update()

            def _hide_overlay_dialog(dialog: ft.AlertDialog) -> None:
                dialog.open = False
                page.update()

            def _show_confirm(title_text: str, body_text: str, confirm_text: str, action) -> None:
                confirm_dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(title_text, weight=ft.FontWeight.BOLD),
                    content=ft.Text(body_text),
                    actions=[
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda _: _hide_overlay_dialog(confirm_dlg),
                        ),
                        ft.ElevatedButton(
                            confirm_text,
                            icon=ft.Icons.DELETE,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.RED_400,
                                color=ft.Colors.WHITE,
                            ),
                            on_click=lambda _: (_hide_overlay_dialog(confirm_dlg), action()),
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                _show_overlay_dialog(confirm_dlg)

            def _sync_toolbar(total_count: int) -> None:
                select_btn.text = "Done" if selection_mode[0] else "Select"
                select_btn.icon = ft.Icons.CLOSE if selection_mode[0] else ft.Icons.CHECKLIST_RTL
                bulk_actions.visible = selection_mode[0]
                selection_status.visible = selection_mode[0]
                selection_status.value = f"{len(selected_ids)} selected" if selection_mode[0] else ""
                mark_all_btn.disabled = total_count == 0
                clear_all_btn.disabled = total_count == 0
                select_all_btn.disabled = total_count == 0 or len(selected_ids) == total_count
                clear_selection_btn.disabled = len(selected_ids) == 0
                delete_selected_btn.disabled = len(selected_ids) == 0

            def _toggle_selection_mode(_=None) -> None:
                selection_mode[0] = not selection_mode[0]
                if not selection_mode[0]:
                    selected_ids.clear()
                _rebuild_list()

            def _toggle_selected(nid: int, checked: bool) -> None:
                if checked:
                    selected_ids.add(nid)
                else:
                    selected_ids.discard(nid)
                _rebuild_list()

            def _select_all(_=None) -> None:
                for item in notif.get_all():
                    selected_ids.add(item.id)
                _rebuild_list()

            def _clear_selection(_=None) -> None:
                selected_ids.clear()
                _rebuild_list()

            def _mark_all(_=None) -> None:
                notif.mark_all_read()
                _rebuild_list()

            def _delete_one(item) -> None:
                selected_ids.discard(item.id)
                notif.delete(item.id)
                _rebuild_list()

            def _confirm_delete_one(item) -> None:
                _show_confirm(
                    "Delete notification?",
                    f'"{item.title}" will be permanently deleted.',
                    "Delete",
                    lambda: _delete_one(item),
                )

            def _delete_selected_now() -> None:
                notif.delete_selected(list(selected_ids))
                selected_ids.clear()
                selection_mode[0] = False
                _rebuild_list()

            def _confirm_delete_selected(_=None) -> None:
                count = len(selected_ids)
                if count == 0:
                    return
                _show_confirm(
                    "Delete selected notifications?",
                    f"{count} selected notification(s) will be permanently deleted.",
                    "Delete selected",
                    _delete_selected_now,
                )

            def _clear_all_now() -> None:
                selected_ids.clear()
                selection_mode[0] = False
                notif.clear_all()
                _rebuild_list()

            def _confirm_clear_all(_=None) -> None:
                _show_confirm(
                    "Clear all notifications?",
                    "This will permanently delete every notification in the list. This cannot be undone.",
                    "Clear all",
                    _clear_all_now,
                )

            def _rebuild_list() -> None:
                notif_list.controls.clear()
                all_notifs = notif.get_all()

                if selection_mode[0]:
                    valid_ids = {item.id for item in all_notifs}
                    selected_ids.intersection_update(valid_ids)
                    if not all_notifs:
                        selection_mode[0] = False
                        selected_ids.clear()

                if not all_notifs:
                    notif_list.controls.append(
                        ft.Container(
                            padding=40,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=8,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.NOTIFICATIONS_NONE,
                                        size=36,
                                        color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE),
                                    ),
                                    ft.Text("All caught up!", size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        "No notifications yet.",
                                        size=12,
                                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                                    ),
                                ],
                            ),
                        )
                    )
                else:
                    for item in all_notifs:
                        icon_name, accent = type_meta.get(
                            item.notif_type, (ft.Icons.NOTIFICATIONS, "#64748b")
                        )

                        def _make_mark_read(nid: int):
                            def _mark_read_one(_):
                                notif.mark_read(nid)
                                _rebuild_list()
                            return _mark_read_one

                        def _make_toggle(nid: int):
                            def _toggle(e):
                                _toggle_selected(nid, bool(e.control.value))
                            return _toggle

                        row_controls: list[ft.Control] = []
                        if selection_mode[0]:
                            row_controls.extend(
                                [
                                    ft.Container(
                                        padding=ft.padding.only(left=10, top=12),
                                        content=ft.Checkbox(
                                            value=item.id in selected_ids,
                                            on_change=_make_toggle(item.id),
                                        ),
                                    ),
                                    ft.Container(width=2),
                                ]
                            )

                        row_controls.extend(
                            [
                                ft.Container(
                                    width=4,
                                    border_radius=ft.BorderRadius(
                                        top_left=12,
                                        bottom_left=12,
                                        top_right=0,
                                        bottom_right=0,
                                    ),
                                    bgcolor=accent if not item.read else ft.Colors.with_opacity(0.25, accent),
                                ),
                                ft.Container(width=10),
                                ft.Container(
                                    padding=ft.padding.only(top=12),
                                    content=ft.Icon(icon_name, size=20, color=accent),
                                ),
                                ft.Container(width=10),
                                ft.Column(
                                    expand=True,
                                    spacing=3,
                                    controls=[
                                        ft.Container(height=10),
                                        ft.Row(
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            controls=[
                                                ft.Text(
                                                    item.title,
                                                    size=13,
                                                    weight=ft.FontWeight.BOLD if not item.read else ft.FontWeight.W_400,
                                                    expand=True,
                                                    color=ft.Colors.WHITE if not item.read else ft.Colors.with_opacity(
                                                        0.6, ft.Colors.ON_SURFACE
                                                    ),
                                                ),
                                                ft.Text(
                                                    item.timestamp,
                                                    size=10,
                                                    color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            item.body,
                                            size=12,
                                            max_lines=3,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            color=ft.Colors.with_opacity(
                                                0.5 if item.read else 0.78,
                                                ft.Colors.ON_SURFACE,
                                            ),
                                        ),
                                        ft.Container(height=8),
                                    ],
                                ),
                            ]
                        )

                        if not selection_mode[0]:
                            row_controls.append(
                                ft.Container(
                                    padding=ft.padding.only(top=4),
                                    content=ft.Column(
                                        spacing=0,
                                        controls=[
                                            ft.IconButton(
                                                icon=ft.Icons.CIRCLE if not item.read else ft.Icons.CIRCLE_OUTLINED,
                                                icon_color=accent if not item.read else ft.Colors.with_opacity(
                                                    0.25, ft.Colors.ON_SURFACE
                                                ),
                                                icon_size=10,
                                                tooltip="Mark as read",
                                                on_click=_make_mark_read(item.id),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_300,
                                                tooltip="Delete notification",
                                                on_click=lambda _, current=item: _confirm_delete_one(current),
                                            ),
                                        ],
                                    ),
                                )
                            )

                        notif_list.controls.append(
                            ft.Container(
                                border_radius=12,
                                bgcolor=ft.Colors.with_opacity(0.03 if item.read else 0.08, ft.Colors.WHITE),
                                border=ft.border.all(
                                    1,
                                    ft.Colors.with_opacity(0.06 if item.read else 0.18, accent),
                                ),
                                padding=ft.Padding(left=0, right=12, top=0, bottom=0),
                                content=ft.Row(
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    controls=row_controls,
                                ),
                            )
                        )

                _sync_toolbar(len(all_notifs))
                try:
                    page.update()
                except Exception:
                    pass

            selection_status = ft.Text(
                "",
                visible=False,
                size=11,
                color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE),
            )
            mark_all_btn = ft.TextButton(
                "Mark all read",
                icon=ft.Icons.DONE_ALL_ROUNDED,
                on_click=_mark_all,
                style=ft.ButtonStyle(
                    color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)
                ),
            )
            select_btn = ft.TextButton(
                "Select",
                icon=ft.Icons.CHECKLIST_RTL,
                on_click=_toggle_selection_mode,
                style=ft.ButtonStyle(
                    color=ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE)
                ),
            )
            clear_all_btn = ft.IconButton(
                icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                icon_color=ft.Colors.RED_300,
                tooltip="Clear all",
                on_click=_confirm_clear_all,
            )
            select_all_btn = ft.TextButton(
                "Select all",
                icon=ft.Icons.DONE_ALL,
                on_click=_select_all,
            )
            clear_selection_btn = ft.TextButton(
                "Clear selection",
                icon=ft.Icons.REMOVE_DONE,
                on_click=_clear_selection,
            )
            delete_selected_btn = ft.ElevatedButton(
                "Delete selected",
                icon=ft.Icons.DELETE,
                disabled=True,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.RED_400,
                    color=ft.Colors.WHITE,
                ),
                on_click=_confirm_delete_selected,
            )
            bulk_actions = ft.Row(
                visible=False,
                wrap=True,
                spacing=6,
                controls=[
                    selection_status,
                    select_all_btn,
                    clear_selection_btn,
                    delete_selected_btn,
                ],
            )

            panel_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Notifications", weight=ft.FontWeight.BOLD, size=16),
                                bulk_actions,
                            ],
                        ),
                        ft.Row(
                            spacing=0,
                            controls=[
                                mark_all_btn,
                                select_btn,
                                clear_all_btn,
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=20,
                                    on_click=lambda _: _close_panel(),
                                ),
                            ],
                        ),
                    ],
                ),
                content=ft.Container(
                    width=520,
                    height=520,
                    content=notif_list,
                ),
                actions=[],
            )

            def _close_panel() -> None:
                panel_dlg.open = False
                page.update()

            if panel_dlg not in page.overlay:
                page.overlay.append(panel_dlg)
            panel_dlg.open = True
            _rebuild_list()
            page.update()

        bell_button = ft.Stack(
            width=48,
            height=48,
            controls=[
                ft.IconButton(
                    ref=bell_icon,
                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                    icon_size=24,
                    tooltip="Notifications",
                    on_click=_open_notif_panel_v2,
                ),
                ft.Container(
                    ref=badge_dot,
                    visible=False,
                    right=6,
                    top=6,
                    width=18,
                    height=18,
                    border_radius=9,
                    bgcolor=ft.Colors.RED_500,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        "0",
                        ref=badge_text,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ),
            ],
        )

        # ── Data changed handler — refresh notifications on every change ──────
        def on_data_changed():
            # Re-scan budgets + bills whenever data changes
            currency_code = db.get_currency()
            expense_map   = db.get_month_expense_summary(
                __import__("datetime").date.today().strftime("%Y-%m")
            )
            budget_limits = db.get_budget_limits()
            upcoming      = db.get_upcoming_recurring(days=365 * 10)
            notif.generate_budget_notifications(budget_limits, expense_map)
            notif.generate_bill_notifications(upcoming)

            if nav_ref[0] is not None:
                render(nav_ref[0].selected_index)

        def render(index: int):
            if index == 0:
                title.value = "Dashboard"
                content.content = dashboard_screen(page, on_data_changed)
            elif index == 1:
                title.value = "Transactions"
                content.content = transactions_screen(page, on_data_changed)
            elif index == 2:
                title.value = "Budgets"
                content.content = budgets_screen(page, on_data_changed)
            else:
                title.value = "Settings"
                content.content = settings_screen(page)
            page.update()
        render_ref[0] = render

        def nav_change(e: ft.ControlEvent):
            render(e.control.selected_index)

        resize_state = {
            "width": page.width or 0,
            "height": page.height or 0,
        }

        def handle_resize(_):
            if nav_ref[0] is None or render_ref[0] is None:
                return
            width = page.width or 0
            height = page.height or 0
            width_changed = abs(width - resize_state["width"]) >= 32
            height_changed = abs(height - resize_state["height"]) >= 48
            if nav_ref[0].selected_index == 0 and (width_changed or height_changed):
                resize_state["width"] = width
                resize_state["height"] = height
                render_ref[0](0)

        page.on_resize = handle_resize

        nav = ft.NavigationBar(
            selected_index=0,
            on_change=nav_change,
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                    selected_icon=ft.Icons.RECEIPT_LONG,
                    label="Transactions",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                    selected_icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
                    label="Budgets",
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Settings",
                ),
            ],
        )
        nav_ref[0] = nav

        def switch_user(_):
            """Return to the profile selection screen."""
            notif.unsubscribe(_refresh_bell)
            notif.reset()
            nav_ref[0] = None
            render_ref[0] = None
            page.on_resize = None
            show_user_select(auto_resume=False)

        page.appbar = ft.AppBar(
            title=title,
            center_title=False,
            actions=[
                ft.TextButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Text(user.emoji, size=18),
                            ft.Text(user.name, size=13,
                                    color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE)),
                        ],
                    ),
                    tooltip="Switch profile",
                    on_click=switch_user,
                ),
                bell_button,
                ft.IconButton(ft.Icons.DARK_MODE, on_click=toggle_theme),
            ],
        )
        page.navigation_bar = nav

        if not page.controls:
            page.add(content)
        page.update()

        # Initial render + notification scan
        render(0)

        # Generate initial notifications after first render
        expense_map   = db.get_month_expense_summary(
            __import__("datetime").date.today().strftime("%Y-%m")
        )
        budget_limits = db.get_budget_limits()
        upcoming      = db.get_upcoming_recurring(days=365 * 10)
        notif.generate_budget_notifications(budget_limits, expense_map)
        notif.generate_bill_notifications(upcoming)

        if applied > 0:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ {applied} recurring transaction(s) auto-applied today!"),
                duration=4000,
            )
            page.snack_bar.open = True
            page.update()

        if db.is_first_run():
            intro = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Welcome, {user.name}! 👋"),
                content=ft.Text(
                    "Welcome! Start by tapping \"+ Income\" on the Dashboard to record your current cash or salary.\n\n"
                    "Then use Transactions to log every expense or income — "
                    "recurring bills like electricity and salary are auto-tracked!\n\n"
                    "Set budget limits in the Budgets tab to stay on track.\n\n"
                    "This app is fully offline — your data stays on this device."
                ),
                actions=[
                    ft.ElevatedButton(
                        "Let's go!",
                        on_click=lambda _: _close_dialog(page, intro),
                    )
                ],
            )
            _open_dialog(page, intro)
            db.mark_first_run_seen()

    # ── STARTUP ──────────────────────────────────────────────────────────────
    page.add(content)
    show_user_select()


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")

