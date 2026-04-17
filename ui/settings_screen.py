from __future__ import annotations

from datetime import datetime
from pathlib import Path

import flet as ft

import database as db
from ui.constants import CURRENCIES, CURRENCY_LABELS


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
    """A tappable button that opens a URL in the browser."""
    return ft.ElevatedButton(
        label,
        icon=ft.Icons.OPEN_IN_NEW,
        url=url,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.INDIGO_600,
            color=ft.Colors.WHITE,
        ),
    )


# ---------------------------------------------------------------------------
# AI Guide dialog — full step-by-step, PC + Mobile
# ---------------------------------------------------------------------------

def _show_ai_guide(page: ft.Page) -> None:
    """Opens a detailed in-app guide for setting up the AI."""

    # ── Tab 1: Overview ─────────────────────────────────────────────────────
    overview_content = ft.Column(
        spacing=12,
        controls=[
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_400),
                content=ft.Column(spacing=6, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.LIGHTBULB, color=ft.Colors.AMBER_400, size=18),
                        ft.Text("How Budget Bro AI works", weight=ft.FontWeight.BOLD, size=14),
                    ]),
                    ft.Text(
                        "Budget Bro AI reads your spending data and gives you "
                        "personalized Taglish advice — like having a kuya/ate "
                        "who's also a financial advisor. 😄",
                        size=13,
                    ),
                ]),
            ),
            ft.Divider(),
            ft.Text("Choose your setup:", weight=ft.FontWeight.BOLD, size=14),

            # Option A
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.CYAN_400),
                content=ft.Column(spacing=6, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.CYAN_400, size=18),
                        ft.Text("Option A — Offline AI (Ollama)", weight=ft.FontWeight.BOLD, size=13),
                        ft.Container(
                            padding=ft.Padding(5, 2, 5, 2),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.CYAN_400),
                            content=ft.Text("PC/Laptop only", size=10, color=ft.Colors.CYAN_300),
                        ),
                    ]),
                    ft.Text(
                        "✅ Completely FREE — no account needed\n"
                        "✅ Works without internet after setup\n"
                        "✅ Your data never leaves your device\n"
                        "❌ Requires a PC or laptop (not for phones)\n"
                        "❌ Needs ~2–4 GB storage for the AI model",
                        size=12,
                    ),
                ]),
            ),

            # Option B
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.INDIGO_400),
                content=ft.Column(spacing=6, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.CLOUD, color=ft.Colors.INDIGO_400, size=18),
                        ft.Text("Option B — Online AI (Anthropic)", weight=ft.FontWeight.BOLD, size=13),
                        ft.Container(
                            padding=ft.Padding(5, 2, 5, 2),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_400),
                            content=ft.Text("PC + Mobile ✓", size=10, color=ft.Colors.GREEN_300),
                        ),
                    ]),
                    ft.Text(
                        "✅ Works on PC AND mobile phone\n"
                        "✅ No downloads, no installation\n"
                        "✅ Free credits when you sign up\n"
                        "❌ Requires internet connection\n"
                        "❌ Needs a free Anthropic account",
                        size=12,
                    ),
                ]),
            ),

            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                content=ft.Text(
                    "💡 Tip: If you're on mobile, go straight to Option B. "
                    "If you're on PC and want full privacy, use Option A.",
                    size=12,
                    italic=True,
                    color=ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE),
                ),
            ),
        ],
    )

    # ── Tab 2: Ollama (PC offline) ──────────────────────────────────────────
    ollama_content = ft.Column(
        spacing=12,
        controls=[
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.CYAN_400),
                content=ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.CYAN_400),
                    ft.Column(spacing=2, controls=[
                        ft.Text("Ollama — Offline AI", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text("PC / Laptop only (Windows, Mac, Linux)", size=11,
                                color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE)),
                    ]),
                ]),
            ),

            ft.Text("Step 1 — Download Ollama", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "Go to the Ollama website and download the installer for your OS "
                "(Windows, macOS, or Linux). It's free.",
                size=12,
            ),
            _link_btn("Download Ollama (ollama.com)", "https://ollama.com/download"),

            ft.Divider(height=1),
            ft.Text("Step 2 — Install Ollama", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "Run the downloaded installer and follow the steps — "
                "it's just like installing any normal app. "
                "After installing, Ollama runs quietly in the background.",
                size=12,
            ),

            ft.Divider(height=1),
            ft.Text("Step 3 — Download an AI model", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "Open your Terminal (Mac/Linux) or Command Prompt (Windows) "
                "and type this command then press Enter:",
                size=12,
            ),
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
                content=ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.TERMINAL, size=14,
                                color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                        ft.Text(
                            "ollama pull llama3.2",
                            font_family="monospace",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
            ),
            ft.Text(
                "This downloads the llama3.2 model (~2 GB). "
                "It only downloads once — after that it works offline forever.",
                size=12,
                color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
            ),

            ft.Divider(height=1),
            ft.Text("Step 4 — Keep Ollama running, then tap Ask AI", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "As long as Ollama is running on your PC, Budget Bro AI will work automatically. "
                "No extra setup needed — just go to the Dashboard and tap 'Ask AI'. That's it! 🎉",
                size=12,
            ),

            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_400),
                content=ft.Column(spacing=4, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.HELP_OUTLINE, size=14, color=ft.Colors.AMBER_400),
                        ft.Text("How to open Terminal / Command Prompt?", weight=ft.FontWeight.BOLD, size=12),
                    ]),
                    ft.Text(
                        "• Windows: Press  Win + R,  type  cmd,  press Enter\n"
                        "• Mac: Press  Cmd + Space,  type  Terminal,  press Enter\n"
                        "• Linux: Press  Ctrl + Alt + T",
                        size=12,
                    ),
                ]),
            ),
        ],
    )

    # ── Tab 3: Anthropic API (PC + Mobile) ──────────────────────────────────
    anthropic_content = ft.Column(
        spacing=12,
        controls=[
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.INDIGO_400),
                content=ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.CLOUD, color=ft.Colors.INDIGO_400),
                    ft.Column(spacing=2, controls=[
                        ft.Text("Anthropic API — Online AI", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text("Works on PC and mobile phones ✓", size=11,
                                color=ft.Colors.GREEN_400),
                    ]),
                ]),
            ),

            ft.Text("Step 1 — Create a free Anthropic account", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "Go to the Anthropic Console website and sign up for a free account. "
                "New accounts get free credits to start with.",
                size=12,
            ),
            _link_btn("Open Anthropic Console", "https://console.anthropic.com"),

            ft.Divider(height=1),
            ft.Text("Step 2 — Get your API Key", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "After logging in:\n"
                "1) Click 'API Keys' in the left sidebar\n"
                "2) Click 'Create Key'\n"
                "3) Give it a name (e.g. 'Budget App')\n"
                "4) Copy the key — it starts with  sk-ant-...",
                size=12,
            ),
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_400),
                content=ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=14, color=ft.Colors.AMBER_400),
                    ft.Text(
                        "Save the key somewhere safe! You can only see it once.",
                        size=12,
                        weight=ft.FontWeight.W_500,
                    ),
                ]),
            ),

            ft.Divider(height=1),
            ft.Text("Step 3 — Paste your key in Settings", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "Go back to the Settings screen, scroll down to the 'AI Setup' section, "
                "paste your key in the API Key field, and tap Save Key.",
                size=12,
            ),

            ft.Divider(height=1),
            ft.Text("Step 4 — Tap Ask AI on the Dashboard", weight=ft.FontWeight.BOLD, size=13),
            ft.Text(
                "That's it! As long as you have internet, Budget Bro AI is ready. "
                "Works on PC and on your phone. 📱💻",
                size=12,
            ),

            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                content=ft.Column(spacing=4, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14,
                                color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                        ft.Text("About pricing", weight=ft.FontWeight.BOLD, size=12),
                    ]),
                    ft.Text(
                        "This app uses the claude-haiku model which is the most affordable. "
                        "One AI insight costs a tiny fraction of a peso. "
                        "Free credits last a long time for personal use.",
                        size=12,
                        color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                    ),
                ]),
            ),
        ],
    )

    # ── Tabs (Flet 0.8x: TabBar + TabBarView inside Tabs.content; Tab uses label) ──
    def _tab_scroll_body(column: ft.Column) -> ft.Container:
        return ft.Container(
            padding=ft.Padding(0, 12, 0, 0),
            content=ft.Column(scroll=ft.ScrollMode.AUTO, controls=[column]),
        )

    tabs = ft.Tabs(
        length=3,
        selected_index=0,
        animation_duration=200,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Overview"),
                        ft.Tab(label="Ollama (PC)"),
                        ft.Tab(label="API (Mobile+PC)"),
                    ],
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        _tab_scroll_body(overview_content),
                        _tab_scroll_body(ollama_content),
                        _tab_scroll_body(anthropic_content),
                    ],
                ),
            ],
        ),
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(spacing=8, controls=[
            ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_400),
            ft.Text("AI Setup Guide", weight=ft.FontWeight.BOLD, size=16),
        ]),
        content=ft.Container(
            width=400,
            height=460,
            content=tabs,
        ),
        actions=[
            ft.ElevatedButton(
                "Got it!",
                icon=ft.Icons.CHECK,
                on_click=lambda _: _close_dialog(page, dlg),
                style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# Main settings screen
# ---------------------------------------------------------------------------

def settings_screen(page: ft.Page) -> ft.Control:
    def toast(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg))
        page.snack_bar.open = True
        page.update()

    # ── CSV Export ────────────────────────────────────────────────────────────
    def export_csv(_):
        filename = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = Path.cwd() / "exports" / filename
        saved = db.export_transactions_csv(str(path))
        toast(f"Exported: {saved}")

    # ── AI Setup ─────────────────────────────────────────────────────────────
    current_key = db.get_anthropic_api_key()
    key_display = ("•" * 20 + current_key[-6:]) if len(current_key) > 6 else current_key

    api_key_field = ft.TextField(
        label="Anthropic API Key",
        hint_text="sk-ant-...",
        value=key_display,
        password=True,
        can_reveal_password=True,
        expand=True,
    )

    key_status = ft.Text(
        "✅ API key saved — Online AI is active." if current_key else
        "No API key yet. See the guide below to get started.",
        size=12,
        color=ft.Colors.GREEN_400 if current_key else
              ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE),
    )

    def save_api_key(_):
        raw = api_key_field.value.strip()
        if raw.startswith("••"):
            toast("Key unchanged — it's already saved, bro.")
            return
        if raw and not raw.startswith("sk-ant-"):
            toast("That doesn't look like an Anthropic key (should start with sk-ant-).")
            return
        db.set_anthropic_api_key(raw)
        if raw:
            key_status.value = "✅ API key saved — Online AI is active."
            key_status.color = ft.Colors.GREEN_400
            toast("API key saved! Online AI is now active.")
        else:
            key_status.value = "No API key yet. See the guide below to get started."
            key_status.color = ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)
            toast("API key cleared.")
        page.update()

    def clear_api_key(_):
        api_key_field.value = ""
        db.set_anthropic_api_key("")
        key_status.value = "No API key yet. See the guide below to get started."
        key_status.color = ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)
        toast("API key cleared.")
        page.update()

    # ── Currency picker ─────────────────────────────────────────────────
    current_currency = db.get_currency()
    currency_dd = ft.Dropdown(
        label="Select currency",
        value=current_currency,
        options=[
            ft.dropdown.Option(code, label)
            for code, label in CURRENCY_LABELS.items()
        ],
        width=300,
    )
    currency_status = ft.Text(
        f"Currently using: {CURRENCY_LABELS.get(current_currency, current_currency)}",
        size=12,
        color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
    )

    def save_currency(_):
        code = currency_dd.value or "PHP"
        db.set_currency(code)
        currency_status.value = f"✅ Saved! Now using: {CURRENCY_LABELS.get(code, code)}"
        currency_status.color = ft.Colors.GREEN_400
        toast(f"Currency changed to {code} — restart the app or switch tabs to see it.")
        page.update()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        controls=[
            # ── AI Setup card ─────────────────────────────────────────────────
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            # Header row
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_400),
                                        ft.Text("AI Setup", weight=ft.FontWeight.BOLD, size=16),
                                    ]),
                                    ft.OutlinedButton(
                                        "How to set up AI?",
                                        icon=ft.Icons.HELP_OUTLINE,
                                        on_click=lambda _: _show_ai_guide(page),
                                    ),
                                ],
                            ),
                            ft.Text(
                                "Budget Bro AI gives personalized Taglish budget advice. "
                                "Two options: offline via Ollama (PC only) or online via Anthropic API (PC + mobile).",
                                size=12,
                                color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                            ),
                            ft.Divider(height=1),
                            # Offline status row
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                                content=ft.Column(spacing=6, controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.Icon(ft.Icons.WIFI_OFF, size=16, color=ft.Colors.CYAN_400),
                                        ft.Text("Offline AI (Ollama)", weight=ft.FontWeight.BOLD, size=13),
                                        ft.Container(
                                            padding=ft.Padding(5, 2, 5, 2),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.CYAN_400),
                                            content=ft.Text("PC only", size=10, color=ft.Colors.CYAN_300),
                                        ),
                                    ]),
                                    ft.Text(
                                        "If Ollama is installed and running on your PC, it's automatically used — "
                                        "no key needed. Tap 'How to set up AI?' for install instructions.",
                                        size=12,
                                        color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                                    ),
                                ]),
                            ),
                            # Online API key row
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                                content=ft.Column(spacing=8, controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.Icon(ft.Icons.CLOUD, size=16, color=ft.Colors.INDIGO_400),
                                        ft.Text("Online AI (Anthropic API)", weight=ft.FontWeight.BOLD, size=13),
                                        ft.Container(
                                            padding=ft.Padding(5, 2, 5, 2),
                                            border_radius=6,
                                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.GREEN_400),
                                            content=ft.Text("PC + Mobile ✓", size=10, color=ft.Colors.GREEN_300),
                                        ),
                                    ]),
                                    ft.Row(controls=[api_key_field]),
                                    ft.Row(spacing=8, controls=[
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
                                    ]),
                                    key_status,
                                ]),
                            ),
                        ],
                    ),
                )
            ),


            # ── Currency card ─────────────────────────────────────────────────
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Icon(ft.Icons.CURRENCY_EXCHANGE, color=ft.Colors.GREEN_400),
                                ft.Text("Currency", weight=ft.FontWeight.BOLD, size=16),
                            ]),
                            ft.Text(
                                "Choose the currency used across the whole app — "
                                "balances, transactions, budgets, and charts.",
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
            # ── Export card ───────────────────────────────────────────────────
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Text("Export Data", weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(
                                "Download all your transactions as a CSV file — "
                                "open in Excel, Google Sheets, or any spreadsheet app.",
                                size=12,
                                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                            ),
                            ft.ElevatedButton(
                                "Export CSV",
                                icon=ft.Icons.DOWNLOAD,
                                on_click=export_csv,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.CYAN_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                        ],
                    ),
                )
            ),

            # ── PWA install card ──────────────────────────────────────────────
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Icon(ft.Icons.INSTALL_MOBILE, color=ft.Colors.CYAN_400),
                                ft.Text("Add to Home Screen", weight=ft.FontWeight.BOLD, size=16),
                            ]),
                            ft.Text(
                                "Use this app offline like a real mobile app:\n"
                                "1) Open the web app URL in your mobile browser\n"
                                "2) Tap the browser menu (three-dot or Share button)\n"
                                '3) Choose "Add to Home Screen"\n\n'
                                "It will work fully offline — your data stays on this device.",
                                size=13,
                                color=ft.Colors.with_opacity(0.80, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            ),

            # ── About card ────────────────────────────────────────────────────
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Text("💰", size=20),
                                ft.Text("About Budget Guardian", weight=ft.FontWeight.BOLD, size=16),
                            ]),
                            ft.Text(
                                "AI Smart Saver — Budget Guardian PH\n"
                                "Track income, expenses, and recurring bills.\n"
                                "Get AI-powered insights in Taglish.\n\n"
                                "Your data is stored 100% locally — private and offline.",
                                size=13,
                                color=ft.Colors.with_opacity(0.80, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            ),
        ],
    )