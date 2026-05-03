from __future__ import annotations

import base64
from time import monotonic

import flet as ft

import user_manager as um
from ui.constants import AVATAR_EMOJIS

_PROFILE_HERO_IMAGE = "Icon.ico"


def _allow_page_action(page: ft.Page, key: str, cooldown: float = 0.45) -> bool:
    gates = getattr(page, "_click_gate_until", None)
    if gates is None:
        gates = {}
        setattr(page, "_click_gate_until", gates)
    now = monotonic()
    allowed_at = float(gates.get(key, 0.0))
    if now < allowed_at:
        return False
    gates[key] = now + cooldown
    return True


def _begin_modal(page: ft.Page, key: str, cooldown: float = 0.45) -> bool:
    if not _allow_page_action(page, key, cooldown):
        return False
    open_modals = getattr(page, "_open_modal_keys", None)
    if open_modals is None:
        open_modals = set()
        setattr(page, "_open_modal_keys", open_modals)
    if key in open_modals:
        return False
    open_modals.add(key)
    return True


def _end_modal(page: ft.Page, key: str) -> None:
    open_modals = getattr(page, "_open_modal_keys", None)
    if open_modals is not None:
        open_modals.discard(key)


def _dialog_width(page: ft.Page, *, max_width: int = 420, min_width: int = 280) -> int:
    width = page.width or getattr(page, "window_width", None) or max_width
    return int(min(max_width, max(min_width, width - 40)))


def _dialog_height(page: ft.Page, *, max_height: int, min_height: int = 240, chrome_space: int = 220) -> int:
    height = page.height or getattr(page, "window_height", None) or max_height
    return int(min(max_height, max(min_height, height - chrome_space)))


def _avatar_view(
    *,
    emoji: str,
    avatar_image: str | None,
    size: int,
    font_size: int,
    ring_color: str = "#22d3ee",
) -> ft.Control:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size / 2,
        padding=2,
        bgcolor=ft.Colors.with_opacity(0.18, ring_color),
        content=ft.Container(
            border_radius=(size - 4) / 2,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor="#0f172a",
            alignment=ft.Alignment(0, 0),
            content=(
                ft.Image(src=avatar_image, fit=ft.BoxFit.COVER)
                if avatar_image
                else ft.Text(emoji, size=font_size)
            ),
        ),
    )


def _pill(text: str, *, bgcolor: str, color: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(10, 5, 10, 5),
        border_radius=999,
        bgcolor=bgcolor,
        content=ft.Text(text, size=10, weight=ft.FontWeight.W_600, color=color),
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
    width = page.width or getattr(page, "window_width", None) or 0
    compact = bool(width) and width < 700
    is_admin_mode = {"value": False}

    if auto_resume:
        remembered_user = um.get_last_active_user()
        if remembered_user is not None and not remembered_user.requires_user_password:
            launch_main_app(remembered_user)
            return

    mode_button_icon = ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED, size=18)
    mode_button_text = ft.Text("Switch to Admin")
    mode_button = ft.OutlinedButton(
        content=ft.Row(
            tight=True,
            spacing=8,
            controls=[mode_button_icon, mode_button_text],
        ),
    )
    page.navigation_bar = None
    page.appbar = ft.AppBar(
        title=ft.Text("AI Smart Saver", weight=ft.FontWeight.BOLD, size=18),
        center_title=True,
        actions=[
            mode_button,
            ft.IconButton(ft.Icons.DARK_MODE, on_click=toggle_theme),
        ],
    )

    def _dismiss_modal(dlg: ft.AlertDialog, key: str) -> None:
        close_dialog(page, dlg)
        _end_modal(page, key)

    def _get_avatar_picker():
        avatar_picker = getattr(page, "_profile_avatar_picker", None)
        if avatar_picker is not None:
            return avatar_picker
        try:
            avatar_picker = ft.FilePicker()
        except Exception:
            return None
        setattr(page, "_profile_avatar_picker", avatar_picker)
        service_registry = getattr(page, "_services", None)
        if service_registry is not None and hasattr(service_registry, "register_service"):
            try:
                service_registry.register_service(avatar_picker)
            except Exception:
                return None
        return avatar_picker

    user_cards = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO)
    profile_count_text = ft.Text(size=24, weight=ft.FontWeight.BOLD)
    protected_count_text = ft.Text(size=24, weight=ft.FontWeight.BOLD)
    mode_banner = ft.Text(size=12, color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE))
    search_field = ft.TextField(
        hint_text="Search profiles",
        prefix_icon=ft.Icons.SEARCH,
        border_radius=14,
        dense=True,
        expand=True,
    )
    clear_search_button = ft.IconButton(
        icon=ft.Icons.CLOSE,
        tooltip="Clear search",
        visible=False,
    )
    create_profile_button = ft.ElevatedButton(
        "Create New Profile",
        icon=ft.Icons.PERSON_ADD_OUTLINED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.WHITE,
            color="#0f766e",
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )

    def _apply_mode_state() -> None:
        if is_admin_mode["value"]:
            mode_button_icon.name = ft.Icons.PERSON_OUTLINED
            mode_button_text.value = "Switch to User"
            mode_banner.value = "Admin Mode: edit and delete controls are enabled."
        else:
            mode_button_icon.name = ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED
            mode_button_text.value = "Switch to Admin"
            mode_banner.value = "User Mode: create and open profiles only."

    def _pick_avatar(on_selected, on_done=None) -> None:
        async def _pick_async():
            avatar_picker = _get_avatar_picker()
            if avatar_picker is None:
                page.snack_bar = ft.SnackBar(ft.Text("Photo picker is not available in this app mode yet."))
                page.snack_bar.open = True
                page.update()
                if on_done is not None:
                    on_done(False)
                return
            try:
                files = await avatar_picker.pick_files(
                    allow_multiple=False,
                    allowed_extensions=["png", "jpg", "jpeg", "webp"],
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True,
                )
                if not files:
                    if on_done is not None:
                        on_done(False)
                    return
                avatar_bytes = getattr(files[0], "bytes", None)
                if not avatar_bytes:
                    page.snack_bar = ft.SnackBar(ft.Text("Could not read that image. Try another file."))
                    page.snack_bar.open = True
                    page.update()
                    if on_done is not None:
                        on_done(False)
                    return
                on_selected(
                    avatar_bytes
                    if isinstance(avatar_bytes, str)
                    else base64.b64encode(avatar_bytes).decode("utf-8")
                )
                if on_done is not None:
                    on_done(True)
            except Exception:
                page.snack_bar = ft.SnackBar(ft.Text("Photo picker failed to open. Try again."))
                page.snack_bar.open = True
                page.update()
                if on_done is not None:
                    on_done(False)

        page.run_task(_pick_async)

    def _prompt_for_password(
        *,
        title: str,
        subtitle: str,
        on_confirm,
        confirm_label: str = "Continue",
        on_success=None,
    ) -> None:
        password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            autofocus=True,
        )
        error_text = ft.Text("", color=ft.Colors.RED_300, size=12, visible=False)

        def _submit(_=None):
            if not _allow_page_action(page, "password_submit", 0.4):
                return
            value = (password_field.value or "").strip()
            if not value:
                error_text.value = "Enter the password."
                error_text.visible = True
                page.update()
                return
            error_text.visible = False
            if on_confirm(value):
                _dismiss_modal(dlg, "password_prompt")
                if on_success is not None:
                    on_success()
                return
            error_text.value = "Password is incorrect."
            error_text.visible = True
            page.update()

        password_field.on_submit = _submit

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=_dialog_width(page, max_width=360, min_width=280),
                height=_dialog_height(page, max_height=220, min_height=160, chrome_space=260),
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Text(subtitle, size=12, color=ft.Colors.with_opacity(0.64, ft.Colors.ON_SURFACE)),
                        password_field,
                        error_text,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _dismiss_modal(dlg, "password_prompt")),
                ft.ElevatedButton(confirm_label, icon=ft.Icons.LOCK_OPEN, on_click=_submit),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        if not _begin_modal(page, "password_prompt"):
            return
        open_dialog(page, dlg)

    def _attempt_launch(user: um.UserProfile, *, bypass_password: bool = False) -> None:
        if not _allow_page_action(page, f"launch_profile:{user.id}", 0.55):
            return
        if bypass_password or not user.requires_user_password:
            launch_main_app(user)
            return

        def _verify(raw_password: str) -> bool:
            if not um.verify_user_password(user, raw_password):
                return False
            launch_main_app(user)
            return True

        _prompt_for_password(
            title=f"Open {user.name}",
            subtitle="Enter the profile password to open this profile.",
            on_confirm=_verify,
            confirm_label="Open",
        )

    def _enter_admin_mode() -> None:
        def _verify(raw_password: str) -> bool:
            if not um.verify_master_admin_password(raw_password):
                return False
            is_admin_mode["value"] = True
            _apply_mode_state()
            rebuild_cards()
            page.update()
            return True

        _prompt_for_password(
            title="Enter Admin Mode",
            subtitle="Enter the master admin password stored in PostgreSQL.",
            on_confirm=_verify,
            confirm_label="Enter",
        )

    def _toggle_mode(_):
        if not _allow_page_action(page, "toggle_mode", 0.4):
            return
        if is_admin_mode["value"]:
            is_admin_mode["value"] = False
            _apply_mode_state()
            rebuild_cards()
            page.update()
            return
        _enter_admin_mode()

    def _open_profile_dialog(
        existing_user: um.UserProfile | None = None,
        *,
        allow_password_edit: bool,
        password_notice: str | None = None,
    ) -> None:
        if not _begin_modal(page, "profile_editor"):
            return
        is_edit = existing_user is not None
        selected_emoji = [um.DEFAULT_EMOJI if existing_user is None else existing_user.emoji]
        selected_avatar = [None if existing_user is None else existing_user.avatar_image]
        avatar_state = {"loading": False}

        name_field = ft.TextField(
            label="Profile name",
            hint_text='e.g. "Juan", "Ate Marie"',
            autofocus=True,
            value="" if existing_user is None else existing_user.name,
            border_radius=14,
        )
        user_password_field = ft.TextField(
            label="User password",
            password=True,
            can_reveal_password=True,
            hint_text="Needed when opening this profile",
            border_radius=14,
            visible=allow_password_edit,
        )
        if is_edit and allow_password_edit:
            user_password_field.helper_text = "Leave blank to keep the current password."

        avatar_preview = ft.Container()
        avatar_mode_text = ft.Text(size=11, color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE))
        emoji_row = ft.Row(spacing=8, wrap=True, run_spacing=8)
        import_photo_button = ft.OutlinedButton("Import Photo", icon=ft.Icons.IMAGE_OUTLINED)
        save_button = ft.ElevatedButton(
            "Save Changes" if is_edit else "Create Profile",
            icon=ft.Icons.SAVE if is_edit else ft.Icons.PERSON_ADD,
            style=ft.ButtonStyle(
                bgcolor="#0891b2",
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=14),
            ),
        )

        def _set_avatar_loading(is_loading: bool) -> None:
            avatar_state["loading"] = is_loading
            import_photo_button.disabled = is_loading
            import_photo_button.text = "Loading photo..." if is_loading else "Import Photo"
            save_button.disabled = is_loading
            name_field.disabled = is_loading
            if allow_password_edit:
                user_password_field.disabled = is_loading
            page.update()

        def refresh_avatar_preview() -> None:
            avatar_preview.content = _avatar_view(
                emoji=selected_emoji[0],
                avatar_image=selected_avatar[0],
                size=88,
                font_size=34,
            )
            avatar_mode_text.value = "Imported photo active" if selected_avatar[0] else "Emoji avatar active"

        def build_emoji_row() -> None:
            emoji_row.controls.clear()
            for emoji in AVATAR_EMOJIS:
                is_selected = emoji == selected_emoji[0] and selected_avatar[0] is None

                def make_pick(current=emoji):
                    def _pick(_):
                        if avatar_state["loading"]:
                            return
                        selected_emoji[0] = current
                        selected_avatar[0] = None
                        build_emoji_row()
                        refresh_avatar_preview()
                        page.update()

                    return _pick

                emoji_row.controls.append(
                    ft.Container(
                        width=42,
                        height=42,
                        border_radius=21,
                        bgcolor=ft.Colors.with_opacity(0.28, "#22d3ee") if is_selected else ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                        border=ft.border.all(2, "#22d3ee" if is_selected else ft.Colors.TRANSPARENT),
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
            _set_avatar_loading(True)
            _pick_avatar(on_avatar_selected, lambda _: _set_avatar_loading(False))

        def save_profile(_):
            if not _allow_page_action(page, "profile_save", 0.6):
                return
            if avatar_state["loading"]:
                page.snack_bar = ft.SnackBar(ft.Text("Wait for the photo to finish loading first."))
                page.snack_bar.open = True
                page.update()
                return

            name = (name_field.value or "").strip()
            if not name:
                page.snack_bar = ft.SnackBar(ft.Text("Enter a profile name."))
                page.snack_bar.open = True
                page.update()
                return

            if um.user_name_exists(name, exclude_user_id=None if existing_user is None else existing_user.id):
                page.snack_bar = ft.SnackBar(ft.Text(f"'{name}' already exists!"))
                page.snack_bar.open = True
                page.update()
                return

            user_password = (user_password_field.value or "").strip() or None
            if allow_password_edit and existing_user is None and not user_password:
                page.snack_bar = ft.SnackBar(ft.Text("Set a user password for the new profile."))
                page.snack_bar.open = True
                page.update()
                return

            if existing_user is None:
                new_user = um.add_user(
                    name,
                    selected_emoji[0],
                    selected_avatar[0],
                    user_password=user_password,
                )
                _dismiss_modal(profile_dlg, "profile_editor")
                launch_main_app(new_user)
                return

            um.update_user(
                existing_user.id,
                name=name,
                emoji=selected_emoji[0],
                avatar_image=selected_avatar[0],
                user_password=user_password if allow_password_edit else None,
                keep_existing_password=True,
            )
            _dismiss_modal(profile_dlg, "profile_editor")
            rebuild_cards()
            page.snack_bar = ft.SnackBar(ft.Text("Profile updated."))
            page.snack_bar.open = True
            page.update()

        import_photo_button.on_click = import_photo
        save_button.on_click = save_profile
        build_emoji_row()
        refresh_avatar_preview()

        profile_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Profile" if is_edit else "Create Profile", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=_dialog_width(page, max_width=440, min_width=300),
                height=_dialog_height(page, max_height=560, min_height=280, chrome_space=240),
                content=ft.Column(
                    tight=True,
                    spacing=16,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[avatar_preview]),
                        ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[avatar_mode_text]),
                        ft.Row(
                            wrap=True,
                            spacing=8,
                            run_spacing=6,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[import_photo_button],
                        ),
                        ft.Text("Avatar emoji", size=12, color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE)),
                        emoji_row,
                        name_field,
                        ft.Container(
                            visible=password_notice is not None,
                            padding=ft.Padding(12, 10, 12, 10),
                            border_radius=14,
                            bgcolor=ft.Colors.with_opacity(0.08, "#0ea5e9"),
                            border=ft.border.all(1, ft.Colors.with_opacity(0.18, "#22d3ee")),
                            content=ft.Text(
                                password_notice or "",
                                size=11,
                                color=ft.Colors.with_opacity(0.68, ft.Colors.ON_SURFACE),
                            ),
                        ),
                        user_password_field,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _dismiss_modal(profile_dlg, "profile_editor")),
                save_button,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(page, profile_dlg)

    def rebuild_cards() -> None:
        current_users = um.get_users()
        query = (search_field.value or "").strip().lower()
        visible_users = [
            user for user in current_users
            if not query or query in user.name.lower()
        ]

        user_cards.controls.clear()
        profile_count_text.value = str(len(visible_users))
        protected_count_text.value = str(sum(1 for user in visible_users if user.requires_user_password))
        clear_search_button.visible = bool(query)

        if not current_users:
            user_cards.controls.append(
                ft.Container(
                    padding=32,
                    border_radius=24,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.08, "#22d3ee")),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Text("No profiles yet", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Create your first secured profile to start tracking money with style.",
                                text_align=ft.TextAlign.CENTER,
                                size=12,
                                color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            )
            page.update()
            return

        if not visible_users:
            user_cards.controls.append(
                ft.Container(
                    padding=24,
                    border_radius=20,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.08, "#22d3ee")),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Text("No matching profiles", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Try a different name or clear the search.",
                                text_align=ft.TextAlign.CENTER,
                                size=12,
                                color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            )
            page.update()
            return

        for user in visible_users:
            meta_chips = ft.Row(
                wrap=True,
                spacing=6,
                run_spacing=6,
                controls=[
                    _pill(
                        "Password protected" if user.requires_user_password else "Quick open",
                        bgcolor=ft.Colors.with_opacity(0.10, "#0ea5e9"),
                        color="#67e8f9",
                    ),
                ],
            )

            def make_select(current=user):
                def _select(_):
                    _attempt_launch(current)
                return _select

            def make_admin_open(current=user):
                def _open(_):
                    _attempt_launch(current, bypass_password=True)
                return _open

            def make_edit(current=user):
                def _edit(_):
                    _open_profile_dialog(
                        current,
                        allow_password_edit=True,
                        password_notice=(
                            "Current passwords cannot be shown because they are stored securely. "
                            "Leave the field blank to keep the current password, or type a new one to reset it."
                        ),
                    )
                return _edit

            def make_user_edit(current=user):
                def _open_limited_edit() -> None:
                    _open_profile_dialog(
                        current,
                        allow_password_edit=False,
                        password_notice="You can update the profile name and avatar here. Password changes stay admin-only.",
                    )

                def _verify(raw_password: str) -> bool:
                    if not um.verify_user_password(current, raw_password):
                        return False
                    return True

                def _edit(_):
                    if not current.requires_user_password:
                        _open_limited_edit()
                        return
                    _prompt_for_password(
                        title=f"Edit {current.name}",
                        subtitle="Enter this profile password to edit the name and photo.",
                        on_confirm=_verify,
                        confirm_label="Continue",
                        on_success=_open_limited_edit,
                    )

                return _edit

            def make_delete(current=user):
                def _delete(_):
                    if not _begin_modal(page, "delete_profile"):
                        return
                    def confirm_delete(_):
                        if not _allow_page_action(page, "delete_profile_confirm", 0.6):
                            return
                        _dismiss_modal(confirm_dlg, "delete_profile")
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
                            ft.TextButton("Cancel", on_click=lambda _: _dismiss_modal(confirm_dlg, "delete_profile")),
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

            action_controls = [
                ft.ElevatedButton(
                    "Open",
                    icon=ft.Icons.LOGIN,
                    on_click=make_select(user),
                    style=ft.ButtonStyle(
                        bgcolor="#0f766e",
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ]
            if is_admin_mode["value"]:
                action_controls.extend(
                    [
                        ft.OutlinedButton("Open as Admin", icon=ft.Icons.ADMIN_PANEL_SETTINGS, on_click=make_admin_open(user)),
                        ft.OutlinedButton("Edit", icon=ft.Icons.EDIT_OUTLINED, on_click=make_edit(user)),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_300,
                            tooltip="Delete profile",
                            on_click=make_delete(user),
                        ),
                    ]
                )
            else:
                action_controls.append(
                    ft.OutlinedButton("Edit", icon=ft.Icons.EDIT_OUTLINED, on_click=make_user_edit(user))
                )

            user_cards.controls.append(
                ft.Container(
                    border_radius=26,
                    padding=ft.Padding(18, 18, 18, 18),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=[
                            ft.Colors.with_opacity(0.14, "#0891b2"),
                            ft.Colors.with_opacity(0.04, "#0f172a"),
                        ],
                    ),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.14, "#22d3ee")),
                    content=ft.ResponsiveRow(
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                col={"xs": 12, "md": 8},
                                content=ft.Row(
                                    spacing=16,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        _avatar_view(
                                            emoji=user.emoji,
                                            avatar_image=user.avatar_image,
                                            size=68,
                                            font_size=30,
                                        ),
                                        ft.Column(
                                            expand=True,
                                            spacing=6,
                                            controls=[
                                                ft.Text(user.name, size=18, weight=ft.FontWeight.BOLD),
                                                ft.Text(
                                                    f"Member since {user.created_at}",
                                                    size=11,
                                                    color=ft.Colors.with_opacity(0.56, ft.Colors.ON_SURFACE),
                                                ),
                                                meta_chips,
                                            ],
                                        ),
                                    ],
                                ),
                            ),
                            ft.Container(
                                col={"xs": 12, "md": 4},
                                alignment=ft.Alignment(1, 0),
                                content=ft.Row(
                                    wrap=True,
                                    spacing=6,
                                    run_spacing=6,
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=action_controls,
                                ),
                            ),
                        ],
                    ),
                )
            )
        page.update()

    hero = ft.Container(
        expand=True,
        alignment=ft.Alignment(-1, 0),
        border_radius=30,
        padding=ft.Padding(26, 24, 26, 24),
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=["#082f49", "#0f766e", "#164e63"],
        ),
        content=ft.Column(
            spacing=10,
            controls=[
                _pill("Secure profiles", bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE), color=ft.Colors.WHITE),
                ft.Text(
                    "Choose the right workspace before you budget.",
                    size=28 if not compact else 22,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                ft.Text(
                    "Create password-protected profiles for each person, then switch into admin mode only when you need to manage them.",
                    size=13,
                    color=ft.Colors.with_opacity(0.78, ft.Colors.WHITE),
                ),
                ft.Row(
                    wrap=True,
                    spacing=10,
                    run_spacing=8,
                    alignment=ft.MainAxisAlignment.START,
                    controls=[create_profile_button],
                ),
                mode_banner,
            ],
        ),
    )

    summary_strip = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[
            ft.Container(
                col={"xs": 12, "sm": 6},
                border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                padding=16,
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text("Profiles", size=11, color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE)),
                        profile_count_text,
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 12, "sm": 6},
                border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                padding=16,
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text("Protected", size=11, color=ft.Colors.with_opacity(0.58, ft.Colors.ON_SURFACE)),
                        protected_count_text,
                    ],
                ),
            ),
        ],
    )

    def _on_search_change(_):
        rebuild_cards()

    def _clear_search(_):
        search_field.value = ""
        rebuild_cards()
        page.update()

    search_field.on_change = _on_search_change
    clear_search_button.on_click = _clear_search

    search_bar = ft.Row(
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            search_field,
            clear_search_button,
        ],
    )

    content.content = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=18,
        controls=[
            hero,
            summary_strip,
            search_bar,
            user_cards,
        ],
    )

    mode_button.on_click = _toggle_mode
    create_profile_button.on_click = lambda _: _open_profile_dialog(
        allow_password_edit=True,
        password_notice="Set the user password used to open this profile.",
    )
    _apply_mode_state()
    rebuild_cards()

    if not page.controls:
        page.add(content)
    page.update()

    if not um.get_users():
        _open_profile_dialog(
            allow_password_edit=True,
            password_notice="Set the user password used to open this profile.",
        )
