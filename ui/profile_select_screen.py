from __future__ import annotations

import base64

import flet as ft

import user_manager as um
from ui.constants import AVATAR_EMOJIS

_PROFILE_HERO_IMAGE = "Icon.ico"


def _dialog_width(page: ft.Page, *, max_width: int = 320, min_width: int = 260) -> int:
    width = page.width or getattr(page, "window_width", None) or max_width
    return int(min(max_width, max(min_width, width - 40)))


def _avatar_view(
    *,
    emoji: str,
    avatar_image: str | None,
    size: int,
    font_size: int,
) -> ft.Control:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size / 2,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.CYAN_400),
        alignment=ft.Alignment(0, 0),
        content=(
            ft.Image(src=avatar_image, fit=ft.BoxFit.COVER)
            if avatar_image
            else ft.Text(emoji, size=font_size)
        ),
    )


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
    compact = (page.width or 0) < 560 if (page.width or 0) else False
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

    avatar_picker = ft.FilePicker()
    service_registry = getattr(page, "_services", None)
    if service_registry is not None and hasattr(service_registry, "register_service"):
        service_registry.register_service(avatar_picker)

    users = um.get_users()
    user_cards = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    def _pick_avatar(on_selected) -> None:
        async def _pick_async():
            files = await avatar_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg", "webp"],
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not files:
                return
            avatar_bytes = getattr(files[0], "bytes", None)
            if not avatar_bytes:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Could not read that image. Try another file.")
                )
                page.snack_bar.open = True
                page.update()
                return
            on_selected(
                avatar_bytes
                if isinstance(avatar_bytes, str)
                else base64.b64encode(avatar_bytes).decode("utf-8")
            )

        page.run_task(_pick_async)

    def _open_profile_dialog(existing_user: um.UserProfile | None = None) -> None:
        is_edit = existing_user is not None
        name_field = ft.TextField(
            label="Your name",
            hint_text='e.g. "Juan", "Ate Marie"',
            autofocus=True,
            value="" if existing_user is None else existing_user.name,
        )
        selected_emoji: list[str] = [
            um.DEFAULT_EMOJI if existing_user is None else existing_user.emoji
        ]
        selected_avatar: list[str | None] = [
            None if existing_user is None else existing_user.avatar_image
        ]
        avatar_preview = ft.Container()
        avatar_mode_text = ft.Text(size=11, color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE))
        emoji_row = ft.Row(spacing=6, wrap=True)
        clear_photo_button = ft.TextButton("Use Emoji")

        def refresh_avatar_preview() -> None:
            avatar_preview.content = _avatar_view(
                emoji=selected_emoji[0],
                avatar_image=selected_avatar[0],
                size=76,
                font_size=30,
            )
            avatar_mode_text.value = (
                "Imported photo is active"
                if selected_avatar[0]
                else "Emoji avatar is active"
            )
            clear_photo_button.disabled = selected_avatar[0] is None

        def build_emoji_row() -> None:
            emoji_row.controls.clear()
            for emoji in AVATAR_EMOJIS:
                is_selected = emoji == selected_emoji[0]

                def make_pick(current=emoji):
                    def _pick(_):
                        selected_emoji[0] = current
                        selected_avatar[0] = None
                        build_emoji_row()
                        refresh_avatar_preview()
                        page.update()

                    return _pick

                emoji_row.controls.append(
                    ft.Container(
                        width=40,
                        height=40,
                        border_radius=20,
                        bgcolor=(
                            ft.Colors.with_opacity(0.3, ft.Colors.CYAN_400)
                            if is_selected and selected_avatar[0] is None
                            else ft.Colors.with_opacity(0.1, ft.Colors.WHITE)
                        ),
                        border=ft.border.all(
                            2,
                            ft.Colors.CYAN_400
                            if is_selected and selected_avatar[0] is None
                            else ft.Colors.TRANSPARENT,
                        ),
                        alignment=ft.Alignment(0, 0),
                        on_click=make_pick(emoji),
                        content=ft.Text(emoji, size=20),
                    )
                )

        def on_avatar_selected(avatar_b64: str) -> None:
            selected_avatar[0] = avatar_b64
            refresh_avatar_preview()
            page.update()

        def import_photo(_):
            _pick_avatar(on_avatar_selected)

        def clear_photo(_):
            selected_avatar[0] = None
            refresh_avatar_preview()
            build_emoji_row()
            page.update()

        clear_photo_button.on_click = clear_photo
        build_emoji_row()
        refresh_avatar_preview()

        def save_profile(_):
            name = name_field.value.strip()
            if not name:
                page.snack_bar = ft.SnackBar(ft.Text("Enter a name, bro."))
                page.snack_bar.open = True
                page.update()
                return
            if um.user_name_exists(name, exclude_user_id=None if existing_user is None else existing_user.id):
                page.snack_bar = ft.SnackBar(ft.Text(f"'{name}' already exists!"))
                page.snack_bar.open = True
                page.update()
                return

            if existing_user is None:
                new_user = um.add_user(name, selected_emoji[0], selected_avatar[0])
                close_dialog(page, profile_dlg)
                launch_main_app(new_user)
                return

            um.update_user(
                existing_user.id,
                name=name,
                emoji=selected_emoji[0],
                avatar_image=selected_avatar[0],
            )
            close_dialog(page, profile_dlg)
            rebuild_cards()
            page.snack_bar = ft.SnackBar(ft.Text("Profile updated."))
            page.snack_bar.open = True
            page.update()

        profile_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Profile" if is_edit else "New Profile", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=_dialog_width(page, max_width=360, min_width=280),
                content=ft.Column(
                    tight=True,
                    spacing=14,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Image(
                                    src=_PROFILE_HERO_IMAGE,
                                    width=64,
                                    height=64,
                                    fit=ft.BoxFit.CONTAIN,
                                ),
                            ],
                        ),
                        ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[avatar_preview]),
                        ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[avatar_mode_text]),
                        ft.Row(
                            wrap=True,
                            spacing=6,
                            run_spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.OutlinedButton("Import Photo", icon=ft.Icons.IMAGE_OUTLINED, on_click=import_photo),
                                clear_photo_button,
                            ],
                        ),
                        name_field,
                        ft.Text(
                            "Pick your avatar emoji:",
                            size=12,
                            color=ft.Colors.with_opacity(0.54, ft.Colors.ON_SURFACE),
                        ),
                        emoji_row,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: close_dialog(page, profile_dlg)),
                ft.ElevatedButton(
                    "Save Changes" if is_edit else "Create Profile",
                    icon=ft.Icons.SAVE if is_edit else ft.Icons.PERSON_ADD,
                    on_click=save_profile,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(page, profile_dlg)

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

            def make_edit(current=user):
                def _edit(_):
                    _open_profile_dialog(current)

                return _edit

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
                        content=ft.ResponsiveRow(
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    col={"xs": 12, "sm": 8},
                                    content=ft.Row(
                                        spacing=14,
                                        controls=[
                                            _avatar_view(
                                                emoji=user.emoji,
                                                avatar_image=user.avatar_image,
                                                size=52,
                                                font_size=26,
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                expand=True,
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
                                ),
                                ft.Container(
                                    col={"xs": 12, "sm": 4},
                                    alignment=ft.Alignment(1, 0),
                                    content=ft.Row(
                                        wrap=compact,
                                        alignment=ft.MainAxisAlignment.END,
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
                                                ft.Icons.EDIT_OUTLINED,
                                                icon_color=ft.Colors.BLUE_300,
                                                tooltip="Edit profile",
                                                on_click=make_edit(user),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.DELETE_OUTLINE,
                                                icon_color=ft.Colors.RED_300,
                                                tooltip="Delete profile",
                                                on_click=make_delete(user),
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                )
            )
        page.update()

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
                    spacing=8,
                    controls=[
                        ft.Image(
                            src=_PROFILE_HERO_IMAGE,
                            width=88,
                            height=88,
                            fit=ft.BoxFit.CONTAIN,
                        ),
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
                on_click=lambda _: _open_profile_dialog(),
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
        _open_profile_dialog()
