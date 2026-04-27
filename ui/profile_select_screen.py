from __future__ import annotations

import flet as ft

import user_manager as um
from ui.constants import AVATAR_EMOJIS


def show_profile_select_screen(
    page: ft.Page,
    content: ft.Container,
    *,
    auto_resume: bool,
    toggle_theme,
    launch_main_app,
    open_dialog,
    close_dialog,
) -> None:
    if auto_resume:
        remembered_user = um.get_last_active_user()
        if remembered_user is not None:
            launch_main_app(remembered_user)
            return

    page.navigation_bar = None
    page.appbar = ft.AppBar(
        title=ft.Text("AI Smart Saver", weight=ft.FontWeight.BOLD, size=18),
        center_title=True,
        actions=[ft.IconButton(ft.Icons.DARK_MODE, on_click=toggle_theme)],
    )

    users = um.get_users()
    user_cards = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    def rebuild_cards() -> None:
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
        for user in current_users:
            def make_select(current=user):
                def _select(_):
                    launch_main_app(current)

                return _select

            def make_delete(current=user):
                def _delete(_):
                    def confirm_delete(_):
                        close_dialog(page, confirm_dlg)
                        um.delete_user(current.id)
                        rebuild_cards()
                        page.update()

                    confirm_dlg = ft.AlertDialog(
                        modal=True,
                        title=ft.Text("Delete Profile?"),
                        content=ft.Text(
                            f"Delete {current.name}'s profile and ALL their budget data?\n\nThis cannot be undone."
                        ),
                        actions=[
                            ft.TextButton("Cancel", on_click=lambda _: close_dialog(page, confirm_dlg)),
                            ft.ElevatedButton(
                                "Delete",
                                icon=ft.Icons.DELETE,
                                on_click=confirm_delete,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                            ),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    open_dialog(page, confirm_dlg)

                return _delete

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
                                            content=ft.Text(user.emoji, size=26),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                ft.Text(user.name, size=16, weight=ft.FontWeight.BOLD),
                                                ft.Text(
                                                    f"Member since {user.created_at}",
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
                                            on_click=make_select(user),
                                            style=ft.ButtonStyle(
                                                bgcolor=ft.Colors.INDIGO_600,
                                                color=ft.Colors.WHITE,
                                            ),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.DELETE_OUTLINE,
                                            icon_color=ft.Colors.RED_300,
                                            tooltip="Delete profile",
                                            on_click=make_delete(user),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                )
            )
        page.update()

    def open_create_dialog(_=None) -> None:
        name_field = ft.TextField(
            label="Your name",
            hint_text='e.g. "Juan", "Ate Marie"',
            autofocus=True,
        )
        selected_emoji: list[str] = [AVATAR_EMOJIS[0]]
        emoji_row = ft.Row(spacing=6, wrap=True)

        def build_emoji_row() -> None:
            emoji_row.controls.clear()
            for emoji in AVATAR_EMOJIS:
                is_selected = emoji == selected_emoji[0]

                def make_pick(current=emoji):
                    def _pick(_):
                        selected_emoji[0] = current
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
                            if is_selected
                            else ft.Colors.with_opacity(0.1, ft.Colors.WHITE)
                        ),
                        border=ft.border.all(2, ft.Colors.CYAN_400 if is_selected else ft.Colors.TRANSPARENT),
                        alignment=ft.Alignment(0, 0),
                        on_click=make_pick(emoji),
                        content=ft.Text(emoji, size=20),
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
            close_dialog(page, create_dlg)
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
                ft.TextButton("Cancel", on_click=lambda _: close_dialog(page, create_dlg)),
                ft.ElevatedButton(
                    "Create Profile",
                    icon=ft.Icons.PERSON_ADD,
                    on_click=do_create,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(page, create_dlg)

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

    if not users:
        open_create_dialog()
