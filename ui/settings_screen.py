from __future__ import annotations

from datetime import datetime
from pathlib import Path

import flet as ft

import database as db
from ui.constants import CURRENCY_LABELS


AI_MODE_LABELS = {
    "smart": "Smart (recommended for slower PCs)",
    "online_first": "Online first (fastest if API key is saved)",
    "offline_first": "Offline first (private, but slower on weak PCs)",
}

MASK_PREFIX = "*" * 18


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_dialog(page: ft.Page, dlg: ft.AlertDialog) -> None:
    if hasattr(page, "show_dialog"):
        page.show_dialog(dlg)
    else:
        page.dialog = dlg
        dlg.open = True
        page.update()


def _close_dialog(page: ft.Page, dlg: ft.AlertDialog) -> None:
    if hasattr(page, "close"):
        page.close(dlg)
    else:
        dlg.open = False
        page.update()


def _link_btn(label: str, url: str) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        label,
        icon=ft.Icons.OPEN_IN_NEW,
        url=url,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.INDIGO_600,
            color=ft.Colors.WHITE,
        ),
    )


def _info_card(
    icon: str,
    icon_color: str,
    title: str,
    body: str,
    badge_text: str | None = None,
    badge_color: str = ft.Colors.CYAN_400,
) -> ft.Container:
    header_controls: list[ft.Control] = [
        ft.Icon(icon, size=16, color=icon_color),
        ft.Text(title, weight=ft.FontWeight.BOLD, size=13),
    ]
    if badge_text:
        header_controls.append(
            ft.Container(
                padding=ft.Padding(5, 2, 5, 2),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.18, badge_color),
                content=ft.Text(badge_text, size=10, color=badge_color),
            )
        )

    return ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(spacing=8, controls=header_controls),
                ft.Text(
                    body,
                    size=12,
                    color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                ),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# AI Guide dialog
# ---------------------------------------------------------------------------

def _show_ai_guide(page: ft.Page) -> None:
    ollama_cmd = ft.Container(
        padding=10,
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        content=ft.Text(
            "ollama pull llama3.2",
            font_family="monospace",
            size=13,
        ),
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_400),
                        ft.Text("AI Setup Guide", weight=ft.FontWeight.BOLD, size=16),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=20,
                    on_click=lambda _: _close_dialog(page, dlg),
                ),
            ],
        ),
        content=ft.Container(
            width=560,
            height=560,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=14,
                controls=[
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_400),
                        content=ft.Text(
                            "Your app can use either local AI on this PC or cloud AI from Anthropic. "
                            "If your computer feels slow, Smart mode or Online First is usually the best choice.",
                            size=13,
                        ),
                    ),
                    ft.Text("Option A - Offline AI with Ollama", weight=ft.FontWeight.BOLD, size=14),
                    _info_card(
                        ft.Icons.WIFI_OFF,
                        ft.Colors.CYAN_400,
                        "Who this is for",
                        "Best if you want everything local and private. It works without internet after setup, "
                        "but local models can be slow on low-end CPUs.",
                        badge_text="PC only",
                    ),
                    ft.Text("Step 1 - Download Ollama", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Install Ollama on your PC. It runs quietly in the background once installed.",
                        size=12,
                    ),
                    _link_btn("Download Ollama", "https://ollama.com/download"),
                    ft.Text("Step 2 - Pull a model", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Open Command Prompt or Terminal, then run this one-time command:",
                        size=12,
                    ),
                    ollama_cmd,
                    ft.Text(
                        "Smaller models are friendlier to weaker hardware. If you have several models installed, "
                        "the app now tries to pick a lighter one first.",
                        size=12,
                    ),
                    ft.Divider(),
                    ft.Text("Option B - Online AI with Anthropic", weight=ft.FontWeight.BOLD, size=14),
                    _info_card(
                        ft.Icons.CLOUD,
                        ft.Colors.INDIGO_400,
                        "Why this is faster",
                        "The heavy model runs in the cloud instead of on your CPU, so replies are usually much faster "
                        "on lower-end PCs.",
                        badge_text="PC + Mobile",
                        badge_color=ft.Colors.GREEN_400,
                    ),
                    ft.Text("Step 1 - Create an Anthropic account", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Go to the Anthropic Console, sign in, and create an API key that starts with sk-ant-.",
                        size=12,
                    ),
                    _link_btn("Open Anthropic Console", "https://console.anthropic.com"),
                    ft.Text("Step 2 - Paste the key in Settings", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Back in this app, paste your key into the AI Setup card and save it.",
                        size=12,
                    ),
                    ft.Text("Step 3 - Set AI Response Mode", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(
                        "Use Smart mode for the best balance, or Online First if you want to always chase the faster cloud path when available.",
                        size=12,
                    ),
                ],
            ),
        ),
        actions=[],
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# Main settings screen
# ---------------------------------------------------------------------------

def settings_screen(page: ft.Page) -> ft.Control:
    def toast(msg: str) -> None:
        page.snack_bar = ft.SnackBar(ft.Text(msg))
        page.snack_bar.open = True
        page.update()

    def ai_mode_help_text(mode: str) -> str:
        if mode == "online_first":
            return (
                "Fastest option when your Anthropic key is saved. If cloud AI is unavailable, "
                "the app will still try Ollama."
            )
        if mode == "offline_first":
            return (
                "Best for privacy and offline use, but local models can feel slow on low-end CPUs."
            )
        return (
            "Recommended for low-end PCs: use Anthropic first when a key is saved, otherwise "
            "fall back to Ollama."
        )

    def export_csv(_) -> None:
        filename = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path.cwd() / "exports" / filename
        saved = db.export_transactions_csv(str(path))
        toast(f"Exported: {saved}")

    current_key = db.get_anthropic_api_key()
    current_ai_mode = db.get_ai_provider_mode()
    key_display = f"{MASK_PREFIX}{current_key[-6:]}" if len(current_key) > 6 else current_key

    api_key_field = ft.TextField(
        label="Anthropic API Key",
        hint_text="sk-ant-...",
        value=key_display,
        password=True,
        can_reveal_password=True,
        expand=True,
    )
    key_status = ft.Text(
        "API key saved - cloud AI is ready." if current_key else
        "No API key yet. See the guide below to get started.",
        size=12,
        color=ft.Colors.GREEN_400 if current_key else
        ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE),
    )

    ai_mode_dd = ft.Dropdown(
        label="AI response mode",
        value=current_ai_mode,
        options=[
            ft.dropdown.Option(code, label)
            for code, label in AI_MODE_LABELS.items()
        ],
        width=420,
    )
    ai_mode_status = ft.Text(
        ai_mode_help_text(current_ai_mode),
        size=12,
        color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
    )

    def save_api_key(_) -> None:
        raw = api_key_field.value.strip()
        if raw.startswith(MASK_PREFIX):
            toast("Key unchanged - it is already saved.")
            return
        if raw and not raw.startswith("sk-ant-"):
            toast("That does not look like an Anthropic key. It should start with sk-ant-.")
            return

        db.set_anthropic_api_key(raw)
        if raw:
            key_status.value = "API key saved - cloud AI is ready."
            key_status.color = ft.Colors.GREEN_400
            toast("API key saved. Smart or Online First will usually be fastest.")
        else:
            key_status.value = "No API key yet. See the guide below to get started."
            key_status.color = ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)
            toast("API key cleared.")
        page.update()

    def clear_api_key(_) -> None:
        api_key_field.value = ""
        db.set_anthropic_api_key("")
        key_status.value = "No API key yet. See the guide below to get started."
        key_status.color = ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)
        toast("API key cleared.")
        page.update()

    def save_ai_mode(_) -> None:
        mode = ai_mode_dd.value or "smart"
        db.set_ai_provider_mode(mode)
        ai_mode_status.value = f"Saved. {ai_mode_help_text(mode)}"
        ai_mode_status.color = ft.Colors.GREEN_400
        toast("AI response mode saved. It will apply on your next AI question.")
        page.update()

    current_currency = db.get_currency()
    currency_dd = ft.Dropdown(
        label="Select currency",
        value=current_currency,
        options=[
            ft.dropdown.Option(code, label)
            for code, label in CURRENCY_LABELS.items()
        ],
        width=320,
    )
    currency_status = ft.Text(
        f"Currently using: {CURRENCY_LABELS.get(current_currency, current_currency)}",
        size=12,
        color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
    )

    def save_currency(_) -> None:
        code = currency_dd.value or "PHP"
        db.set_currency(code)
        currency_status.value = f"Saved. Now using: {CURRENCY_LABELS.get(code, code)}"
        currency_status.color = ft.Colors.GREEN_400
        toast(f"Currency changed to {code}. Switch tabs or restart the app if needed.")
        page.update()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        controls=[
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_400),
                                            ft.Text("AI Setup", weight=ft.FontWeight.BOLD, size=16),
                                        ],
                                    ),
                                    ft.OutlinedButton(
                                        "How to set up AI?",
                                        icon=ft.Icons.HELP_OUTLINE,
                                        on_click=lambda _: _show_ai_guide(page),
                                    ),
                                ],
                            ),
                            ft.Text(
                                "Budget Bro AI can run locally with Ollama or in the cloud with Anthropic. "
                                "On weaker PCs, Smart mode or Online First usually feels much faster.",
                                size=12,
                                color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                            ),
                            ft.Divider(height=1),
                            _info_card(
                                ft.Icons.WIFI_OFF,
                                ft.Colors.CYAN_400,
                                "Offline AI (Ollama)",
                                "Private and works without internet after setup. Great for privacy, but local model generation can be slow on low-end hardware.",
                                badge_text="PC only",
                            ),
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.Icon(ft.Icons.SPEED, size=16, color=ft.Colors.AMBER_400),
                                                ft.Text("AI Response Mode", weight=ft.FontWeight.BOLD, size=13),
                                            ],
                                        ),
                                        ft.Text(
                                            "Choose whether the app should prioritize speed or offline privacy.",
                                            size=12,
                                            color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                                        ),
                                        ai_mode_dd,
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.ElevatedButton(
                                                    "Save AI Mode",
                                                    icon=ft.Icons.SAVE,
                                                    on_click=save_ai_mode,
                                                    style=ft.ButtonStyle(
                                                        bgcolor=ft.Colors.AMBER_700,
                                                        color=ft.Colors.WHITE,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        ai_mode_status,
                                    ],
                                ),
                            ),
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.Icon(ft.Icons.CLOUD, size=16, color=ft.Colors.INDIGO_400),
                                                ft.Text("Online AI (Anthropic API)", weight=ft.FontWeight.BOLD, size=13),
                                                ft.Container(
                                                    padding=ft.Padding(5, 2, 5, 2),
                                                    border_radius=6,
                                                    bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_400),
                                                    content=ft.Text(
                                                        "PC + Mobile",
                                                        size=10,
                                                        color=ft.Colors.GREEN_300,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            "Cloud AI is usually the quickest route on slower computers because your CPU does not have to run the model itself.",
                                            size=12,
                                            color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                                        ),
                                        ft.Row(controls=[api_key_field]),
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.ElevatedButton(
                                                    "Save Key",
                                                    icon=ft.Icons.SAVE,
                                                    on_click=save_api_key,
                                                    style=ft.ButtonStyle(
                                                        bgcolor=ft.Colors.INDIGO_600,
                                                        color=ft.Colors.WHITE,
                                                    ),
                                                ),
                                                ft.OutlinedButton(
                                                    "Clear",
                                                    icon=ft.Icons.DELETE_OUTLINE,
                                                    on_click=clear_api_key,
                                                ),
                                            ],
                                        ),
                                        key_status,
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.CURRENCY_EXCHANGE, color=ft.Colors.GREEN_400),
                                    ft.Text("Currency", weight=ft.FontWeight.BOLD, size=16),
                                ],
                            ),
                            ft.Text(
                                "Choose the currency used across the whole app - balances, transactions, budgets, and charts.",
                                size=12,
                                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                            ),
                            currency_dd,
                            ft.ElevatedButton(
                                "Save Currency",
                                icon=ft.Icons.SAVE,
                                on_click=save_currency,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.GREEN_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                            currency_status,
                        ],
                    ),
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.DOWNLOAD_DONE, color=ft.Colors.BLUE_400),
                                    ft.Text("Export Data", weight=ft.FontWeight.BOLD, size=16),
                                ],
                            ),
                            ft.Text(
                                "Export your transaction history as CSV so you can open it in Excel, Google Sheets, or another tool.",
                                size=12,
                                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                            ),
                            ft.ElevatedButton(
                                "Export Transactions CSV",
                                icon=ft.Icons.FILE_DOWNLOAD,
                                on_click=export_csv,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.BLUE_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                        ],
                    ),
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.LOCK, color=ft.Colors.CYAN_400),
                                    ft.Text("Privacy", weight=ft.FontWeight.BOLD, size=16),
                                ],
                            ),
                            ft.Text(
                                "Your budget data stays in local SQLite files on this device. If you use cloud AI, only the prompt you send to the model goes over the internet.",
                                size=12,
                                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            ),
        ],
    )
