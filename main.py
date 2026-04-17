from __future__ import annotations

import flet as ft

import database as db
import user_manager as um
from ui.budgets_screen import budgets_screen
from ui.dashboard_screen import dashboard_screen
from ui.settings_screen import settings_screen
from ui.transactions_screen import transactions_screen
from ui.constants import AVATAR_EMOJIS


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

    page.title = "AI Smart Saver - Budget Guardian"
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

    def toggle_theme(_):
        page.theme_mode = (
            ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        )
        page.update()

    # ── USER SELECTION SCREEN ────────────────────────────────────────────────

    def show_user_select():
        """Render the profile picker. Called on first launch or when switching users."""
        page.navigation_bar = None
        page.appbar = ft.AppBar(
            title=ft.Text("AI Smart Saver", weight=ft.FontWeight.BOLD, size=18),
            center_title=True,
            actions=[ft.IconButton(ft.Icons.DARK_MODE, on_click=toggle_theme)],
        )

        users = um.get_users()
        user_cards = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

        def rebuild_cards():
            user_cards.controls.clear()
            current_users = um.get_users()
            if not current_users:
                user_cards.controls.append(
                    ft.Container(
                        padding=30,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(
                            "Walang profile pa.\nGawa ng sariling profile para magsimula!",
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                            size=14,
                        ),
                    )
                )
            for u in current_users:
                def make_select(user=u):
                    def _select(_):
                        launch_main_app(user)
                    return _select

                def make_delete(user=u):
                    def _del(_):
                        def confirm_del(_):
                            _close_dialog(page, confirm_dlg)
                            um.delete_user(user.id)
                            rebuild_cards()
                            page.update()

                        confirm_dlg = ft.AlertDialog(
                            modal=True,
                            title=ft.Text("Delete Profile?"),
                            content=ft.Text(
                                f"Delete {user.name}'s profile and ALL their budget data?\n\nThis cannot be undone."
                            ),
                            actions=[
                                ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, confirm_dlg)),
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

                user_cards.controls.append(
                    ft.Card(
                        elevation=3,
                        content=ft.Container(
                            padding=ft.Padding(14, 12, 10, 12),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=14,
                                        controls=[
                                            ft.Container(
                                                width=52,
                                                height=52,
                                                border_radius=26,
                                                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.CYAN_400),
                                                alignment=ft.Alignment(0, 0),
                                                content=ft.Text(u.emoji, size=26),
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Text(u.name, size=16, weight=ft.FontWeight.BOLD),
                                                    ft.Text(
                                                        f"Member since {u.created_at}",
                                                        size=11,
                                                        color=ft.Colors.with_opacity(0.38, ft.Colors.ON_SURFACE),
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=0,
                                        controls=[
                                            ft.ElevatedButton(
                                                "Select",
                                                icon=ft.Icons.LOGIN,
                                                on_click=make_select(u),
                                                style=ft.ButtonStyle(
                                                    bgcolor=ft.Colors.INDIGO_600,
                                                    color=ft.Colors.WHITE,
                                                ),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_300,
                                                tooltip="Delete profile",
                                                on_click=make_delete(u),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    )
                )
            page.update()

        def open_create_dialog(_=None):
            name_field = ft.TextField(
                label="Your name",
                hint_text='e.g. "Juan", "Ate Marie"',
                autofocus=True,
            )
            selected_emoji: list[str] = [AVATAR_EMOJIS[0]]
            emoji_row = ft.Row(spacing=6, wrap=True)

            def build_emoji_row():
                emoji_row.controls.clear()
                for em in AVATAR_EMOJIS:
                    is_sel = em == selected_emoji[0]
                    def make_pick(e=em):
                        def _pick(_):
                            selected_emoji[0] = e
                            build_emoji_row()
                            page.update()
                        return _pick
                    emoji_row.controls.append(
                        ft.Container(
                            width=40,
                            height=40,
                            border_radius=20,
                            bgcolor=(
                                ft.Colors.with_opacity(0.3, ft.Colors.CYAN_400)
                                if is_sel
                                else ft.Colors.with_opacity(0.1, ft.Colors.WHITE)
                            ),
                            border=ft.border.all(2, ft.Colors.CYAN_400 if is_sel else ft.Colors.TRANSPARENT),
                            alignment=ft.Alignment(0, 0),
                            on_click=make_pick(em),
                            content=ft.Text(em, size=20),
                        )
                    )

            build_emoji_row()

            def do_create(_):
                name = name_field.value.strip()
                if not name:
                    page.snack_bar = ft.SnackBar(ft.Text("Enter a name, bro."))
                    page.snack_bar.open = True
                    page.update()
                    return
                if um.user_name_exists(name):
                    page.snack_bar = ft.SnackBar(ft.Text(f"'{name}' already exists!"))
                    page.snack_bar.open = True
                    page.update()
                    return
                new_user = um.add_user(name, selected_emoji[0])
                _close_dialog(page, create_dlg)
                launch_main_app(new_user)

            create_dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("New Profile", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=320,
                    content=ft.Column(
                        tight=True,
                        spacing=14,
                        controls=[
                            name_field,
                            ft.Text("Pick your avatar:", size=12, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE)),
                            emoji_row,
                        ],
                    ),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _: _close_dialog(page, create_dlg)),
                    ft.ElevatedButton(
                        "Create Profile",
                        icon=ft.Icons.PERSON_ADD,
                        on_click=do_create,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            _open_dialog(page, create_dlg)

        rebuild_cards()

        content.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            controls=[
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Text("💰", size=52),
                            ft.Text(
                                "Budget Guardian",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Select your profile to continue",
                                size=13,
                                color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    )
                ),
                ft.ElevatedButton(
                    "+ New Profile",
                    icon=ft.Icons.PERSON_ADD_OUTLINED,
                    on_click=open_create_dialog,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.CYAN_700,
                        color=ft.Colors.WHITE,
                    ),
                ),
                ft.Divider(color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ft.Container(
                    expand=True,
                    content=user_cards,
                ),
            ],
        )

        if not page.controls:
            page.add(content)
        page.update()

        # If zero users, open create dialog immediately
        if not users:
            open_create_dialog()

    # ── MAIN APP ─────────────────────────────────────────────────────────────

    def launch_main_app(user: um.UserProfile):
        """Initialize the budget app for the selected user profile."""
        db.set_user_db(um.get_db_path(user.id))
        db.init_db()
        applied = db.apply_due_recurring()

        title.value = "Dashboard"

        def on_data_changed():
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

        def nav_change(e: ft.ControlEvent):
            render(e.control.selected_index)

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
            nav_ref[0] = None
            show_user_select()

        page.appbar = ft.AppBar(
            title=title,
            center_title=False,
            actions=[
                # Shows current user + lets them switch
                ft.TextButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Text(user.emoji, size=18),
                            ft.Text(user.name, size=13, color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE)),
                        ],
                    ),
                    tooltip="Switch profile",
                    on_click=switch_user,
                ),
                ft.IconButton(ft.Icons.DARK_MODE, on_click=toggle_theme),
            ],
        )
        page.navigation_bar = nav

        if not page.controls:
            page.add(content)
        page.update()

        render(0)

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