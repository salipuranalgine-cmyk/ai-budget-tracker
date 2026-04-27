from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import flet as ft

import database as db
import ml_engine
from ui.constants import CURRENCY_LABELS


AI_MODE_LABELS = {
    "smart": "Smart (recommended for slower PCs)",
    "online_first": "Online first (fastest if API key is saved)",
    "offline_first": "Offline first (private, but slower on weak PCs)",
}

ML_SCHEDULE_LABELS = {
    "daily":   "Daily — retrain every day (best if you log many transactions)",
    "weekly":  "Weekly — retrain every 7 days (recommended for most users)",
    "monthly": "Monthly — retrain once a month (light usage / older hardware)",
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


def _status_row(label: str, value: str, value_color=None) -> ft.Control:
    """A simple label: value row used inside the ML status dialog."""
    return ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text(
                label, size=12,
                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
            ),
            ft.Text(
                value, size=12,
                weight=ft.FontWeight.W_600,
                color=value_color or ft.Colors.ON_SURFACE,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# ML Status dialog
# This is the "face" for scikit-learn — shows the user exactly what's
# happening with their ML models, whether they're trained or not, and
# lets them retrain manually.
# ---------------------------------------------------------------------------

def _show_ml_status_dialog(
    page: ft.Page,
    on_status_changed: Callable[[], None] | None = None,
) -> None:
    """
    Opens a dialog showing the full status of the scikit-learn ML engine.
    Think of it like a health dashboard for the ML layer.

    WHAT IS SHOWN:
    ─────────────
    • Anomaly Detector status  (IsolationForest — finds unusual transactions)
    • Spending Forecaster status (LinearRegression — predicts next month)
    • Last retrain date
    • Next retrain date based on schedule
    • How many expense transactions exist
    • How many months of history exist
    • What's still needed to enable each model
    • A "Retrain Now" button for immediate manual retraining
    """

    # Mutable container so we can update the dialog content after retraining
    status_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    retrain_status_text = ft.Text(
        "", size=12,
        color=ft.Colors.GREEN_400,
        visible=False,
    )
    retrain_btn = ft.ElevatedButton(
        "Retrain Now",
        icon=ft.Icons.REFRESH,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.PURPLE_700,
            color=ft.Colors.WHITE,
        ),
    )

    def _build_status_content():
        """Pull fresh status from ml_engine and rebuild the column."""
        status_col.controls.clear()
        s = ml_engine.get_ml_status()

        # ── MODEL READINESS SECTION ──────────────────────────────────────────
        def _model_badge(ready: bool) -> ft.Control:
            if ready:
                return ft.Container(
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.GREEN_400),
                    content=ft.Text("✅ Trained & Ready", size=11, color=ft.Colors.GREEN_300),
                )
            return ft.Container(
                padding=ft.Padding(8, 3, 8, 3),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.ORANGE_400),
                content=ft.Text("⏳ Not trained yet", size=11, color=ft.Colors.ORANGE_300),
            )

        status_col.controls.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Column(spacing=12, controls=[

                    # Anomaly Detector
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Icon(ft.Icons.POLICY_ROUNDED, size=16,
                                        color=ft.Colors.PINK_300),
                                ft.Column(spacing=2, controls=[
                                    ft.Text("Anomaly Detector", size=13,
                                            weight=ft.FontWeight.BOLD),
                                    ft.Text("IsolationForest · flags unusual transactions",
                                            size=10,
                                            color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE)),
                                ]),
                            ]),
                            _model_badge(s["anomaly_model_ready"]),
                        ],
                    ),

                    # Forecaster
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Icon(ft.Icons.AUTO_GRAPH_ROUNDED, size=16,
                                        color=ft.Colors.PURPLE_300),
                                ft.Column(spacing=2, controls=[
                                    ft.Text("Spending Forecaster", size=13,
                                            weight=ft.FontWeight.BOLD),
                                    ft.Text("LinearRegression · predicts next month",
                                            size=10,
                                            color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE)),
                                ]),
                            ]),
                            _model_badge(s["forecast_model_ready"]),
                        ],
                    ),
                ]),
            )
        )

        # ── DATA SNAPSHOT ────────────────────────────────────────────────────
        status_col.controls.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Column(spacing=8, controls=[
                    ft.Text("Your Data Snapshot", size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE)),
                    _status_row(
                        "Expense transactions",
                        str(s["transaction_count"]),
                        ft.Colors.CYAN_300 if s["transaction_count"] >= 30
                        else ft.Colors.ORANGE_300,
                    ),
                    _status_row(
                        "Months of history",
                        str(s["months_of_data"]),
                        ft.Colors.CYAN_300 if s["months_of_data"] >= 3
                        else ft.Colors.ORANGE_300,
                    ),
                ]),
            )
        )

        # ── WHAT IS STILL NEEDED ─────────────────────────────────────────────
        needs: list[str] = []
        if s["transaction_count"] < 30:
            remaining = 30 - s["transaction_count"]
            needs.append(
                f"• Anomaly detector needs {remaining} more expense transaction(s) "
                f"(minimum 30 to define what 'normal' looks like for you)."
            )
        if s["months_of_data"] < 3:
            remaining = 3 - s["months_of_data"]
            needs.append(
                f"• Forecaster needs {remaining} more month(s) of history "
                f"(minimum 3 months to draw a reliable trend line)."
            )

        if needs:
            status_col.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE_400),
                    border=ft.border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.ORANGE_400)),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(spacing=6, controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14,
                                        color=ft.Colors.ORANGE_300),
                                ft.Text("What's still needed", size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.ORANGE_300),
                            ]),
                            *[ft.Text(n, size=11,
                                      color=ft.Colors.with_opacity(0.75, ft.Colors.ON_SURFACE))
                              for n in needs],
                        ],
                    ),
                )
            )
        else:
            status_col.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_400),
                    content=ft.Row(spacing=8, controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14,
                                color=ft.Colors.GREEN_300),
                        ft.Text("You have enough data for both models to train!",
                                size=12, color=ft.Colors.GREEN_300),
                    ]),
                )
            )

        # ── RETRAIN SCHEDULE TIMING ──────────────────────────────────────────
        status_col.controls.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Column(spacing=8, controls=[
                    ft.Text("Retrain Schedule", size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE)),
                    _status_row("Schedule",    s["schedule"]),
                    _status_row("Last retrain", s["last_retrain"]),
                    _status_row("Next retrain", s["next_retrain"],
                                ft.Colors.GREEN_300
                                if s["next_retrain"] == "Due now"
                                else None),
                ]),
            )
        )

        # ── WHAT SCIKIT-LEARN ACTUALLY IS ────────────────────────────────────
        # Educational explainer for juniors and curious users
        status_col.controls.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                content=ft.Column(spacing=8, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Text("🧠", size=14),
                        ft.Text("What is scikit-learn?", size=12,
                                weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Text(
                        "scikit-learn is a Python machine learning library. "
                        "This app uses two of its models:\n\n"
                        "• IsolationForest — learns what a normal transaction looks "
                        "like for YOU, then flags anything that doesn't fit.\n\n"
                        "• LinearRegression — draws a trend line through your monthly "
                        "spending history and extends it forward to predict next month.\n\n"
                        "Both models run 100% locally on your device — "
                        "no data is ever sent anywhere.",
                        size=11,
                        color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE),
                    ),
                ]),
            )
        )

    def _do_retrain(_):
        """Trigger an immediate retrain and refresh the dialog."""
        retrain_btn.disabled = True
        retrain_btn.text = "Training…"
        retrain_status_text.visible = False
        page.update()

        try:
            results = ml_engine.train_all()
            anomaly_msg  = results.get("anomaly", "")
            forecast_msg = results.get("forecaster", "")
            retrain_status_text.value = f"Done!\n• {anomaly_msg}\n• {forecast_msg}"
            retrain_status_text.color = ft.Colors.GREEN_400
        except Exception as exc:
            retrain_status_text.value = f"Error: {exc}"
            retrain_status_text.color = ft.Colors.RED_400

        retrain_status_text.visible = True
        retrain_btn.disabled = False
        retrain_btn.text = "Retrain Now"
        _build_status_content()   # refresh the status numbers
        if on_status_changed is not None:
            on_status_changed()
        page.update()

    retrain_btn.on_click = _do_retrain
    _build_status_content()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED, color=ft.Colors.PURPLE_300),
                    ft.Text("ML Engine Status", weight=ft.FontWeight.BOLD, size=16),
                    ft.Container(
                        padding=ft.Padding(6, 2, 6, 2),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.PURPLE_400),
                        content=ft.Text("scikit-learn", size=10,
                                        color=ft.Colors.PURPLE_300),
                    ),
                ]),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=20,
                    on_click=lambda _: _close_dialog(page, dlg),
                ),
            ],
        ),
        content=ft.Container(
            width=520,
            height=540,
            content=ft.Column(
                spacing=12,
                expand=True,
                controls=[
                    ft.Container(expand=True, content=status_col),
                    ft.Divider(height=1),
                    ft.Column(
                        spacing=8,
                        controls=[
                            retrain_status_text,
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                controls=[retrain_btn],
                            ),
                        ],
                    ),
                ],
            ),
        ),
        actions=[],
    )

    _open_dialog(page, dlg)


# ---------------------------------------------------------------------------
# AI Guide dialog (unchanged)
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

    # ── ML Schedule controls ─────────────────────────────────────────────────
    current_schedule = ml_engine.get_retrain_schedule()
    ml_schedule_dd = ft.Dropdown(
        label="Retrain schedule",
        value=current_schedule,
        options=[
            ft.dropdown.Option(code, label)
            for code, label in ML_SCHEDULE_LABELS.items()
        ],
        width=420,
    )
    ml_schedule_status = ft.Text(
        f"Currently: {ML_SCHEDULE_LABELS.get(current_schedule, current_schedule)}",
        size=12,
        color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
    )

    def save_ml_schedule(_) -> None:
        schedule = ml_schedule_dd.value or "weekly"
        ml_engine.set_retrain_schedule(schedule)
        ml_schedule_status.value = f"Saved. {ML_SCHEDULE_LABELS.get(schedule, schedule)}"
        ml_schedule_status.color = ft.Colors.GREEN_400
        refresh_ml_status_ui()
        toast("ML retrain schedule saved.")
        page.update()

    # ── Currency controls ────────────────────────────────────────────────────
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

    # ── Quick ML status badge (shown in the card header) ─────────────────────
    ml_status_summary = ml_engine.get_ml_status()
    both_ready = ml_status_summary["anomaly_model_ready"] and ml_status_summary["forecast_model_ready"]
    ml_badge_text = "Both models ready" if both_ready else "Not trained yet"
    ml_badge_color = ft.Colors.GREEN_400 if both_ready else ft.Colors.ORANGE_400
    ml_badge_label = ft.Text(ml_badge_text, size=10, color=ml_badge_color)
    ml_badge_chip = ft.Container(
        padding=ft.Padding(6, 2, 6, 2),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.18, ml_badge_color),
        content=ml_badge_label,
    )
    ml_last_retrain_value = ft.Text(
        ml_status_summary["last_retrain"],
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
    )
    ml_next_retrain_value = ft.Text(
        ml_status_summary["next_retrain"],
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_300 if ml_status_summary["next_retrain"] == "Due now" else ft.Colors.ON_SURFACE,
    )
    ml_transaction_count_value = ft.Text(
        str(ml_status_summary["transaction_count"]),
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
    )

    def refresh_ml_status_ui() -> None:
        status = ml_engine.get_ml_status()
        ready = status["anomaly_model_ready"] and status["forecast_model_ready"]
        badge_text = "Both models ready" if ready else "Not trained yet"
        badge_color = ft.Colors.GREEN_400 if ready else ft.Colors.ORANGE_400

        ml_badge_label.value = badge_text
        ml_badge_label.color = badge_color
        ml_badge_chip.bgcolor = ft.Colors.with_opacity(0.18, badge_color)
        ml_last_retrain_value.value = status["last_retrain"]
        ml_next_retrain_value.value = status["next_retrain"]
        ml_next_retrain_value.color = (
            ft.Colors.GREEN_300 if status["next_retrain"] == "Due now" else ft.Colors.ON_SURFACE
        )
        ml_transaction_count_value.value = str(status["transaction_count"])

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        controls=[

            # ── AI SETUP CARD ────────────────────────────────────────────────
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

            # ── ML SMART ANALYSIS CARD ───────────────────────────────────────
            # This card lives right after AI Setup since they're both ML features.
            # It lets the user control the retrain schedule and open the status dialog.
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            # Header row: title + status badge + View Status button
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED,
                                                    color=ft.Colors.PURPLE_300),
                                            ft.Text("ML Smart Analysis",
                                                    weight=ft.FontWeight.BOLD, size=16),
                                            ml_badge_chip,
                                        ],
                                    ),
                                    # "View ML Status" button — your requested button
                                    ft.OutlinedButton(
                                        "View ML Status",
                                        icon=ft.Icons.MONITOR_HEART_ROUNDED,
                                        on_click=lambda _: _show_ml_status_dialog(page, refresh_ml_status_ui),
                                        style=ft.ButtonStyle(
                                            side=ft.BorderSide(
                                                1, ft.Colors.with_opacity(0.35, ft.Colors.PURPLE_300)
                                            ),
                                        ),
                                    ),
                                ],
                            ),

                            ft.Text(
                                "scikit-learn powers two local ML models that run on YOUR device. "
                                "They learn from your own spending history — no internet needed.",
                                size=12,
                                color=ft.Colors.with_opacity(0.70, ft.Colors.ON_SURFACE),
                            ),

                            ft.Divider(height=1),

                            # Two model descriptions
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        expand=True,
                                        content=_info_card(
                                            ft.Icons.POLICY_ROUNDED,
                                            ft.Colors.PINK_300,
                                            "Anomaly Detector",
                                            "Flags transactions that look unusual compared to your normal spending patterns.",
                                            badge_text="IsolationForest",
                                            badge_color=ft.Colors.PINK_300,
                                        ),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        content=_info_card(
                                            ft.Icons.AUTO_GRAPH_ROUNDED,
                                            ft.Colors.PURPLE_300,
                                            "Spending Forecaster",
                                            "Predicts next month's spending per category using your historical trends.",
                                            badge_text="LinearRegression",
                                            badge_color=ft.Colors.PURPLE_300,
                                        ),
                                    ),
                                ],
                            ),

                            # Retrain schedule dropdown
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
                                content=ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Row(spacing=8, controls=[
                                            ft.Icon(ft.Icons.SCHEDULE, size=16,
                                                    color=ft.Colors.PURPLE_300),
                                            ft.Text("Auto-Retrain Schedule",
                                                    weight=ft.FontWeight.BOLD, size=13),
                                        ]),
                                        ft.Text(
                                            "How often should the app retrain models with new data? "
                                            "Retraining happens automatically on app startup when the schedule is due.",
                                            size=12,
                                            color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE),
                                        ),
                                        ml_schedule_dd,
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.ElevatedButton(
                                                    "Save Schedule",
                                                    icon=ft.Icons.SAVE,
                                                    on_click=save_ml_schedule,
                                                    style=ft.ButtonStyle(
                                                        bgcolor=ft.Colors.PURPLE_700,
                                                        color=ft.Colors.WHITE,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        ml_schedule_status,
                                    ],
                                ),
                            ),

                            # Last retrain + next retrain quick info
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        expand=True,
                                        padding=ft.Padding(10, 8, 10, 8),
                                        border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Column(spacing=3, controls=[
                                            ft.Text("Last retrain", size=10,
                                                    color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE)),
                                            ml_last_retrain_value,
                                        ]),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        padding=ft.Padding(10, 8, 10, 8),
                                        border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Column(spacing=3, controls=[
                                            ft.Text("Next retrain", size=10,
                                                    color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE)),
                                            ml_next_retrain_value,
                                        ]),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        padding=ft.Padding(10, 8, 10, 8),
                                        border_radius=8,
                                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                        content=ft.Column(spacing=3, controls=[
                                            ft.Text("Transactions", size=10,
                                                    color=ft.Colors.with_opacity(0.50, ft.Colors.ON_SURFACE)),
                                            ml_transaction_count_value,
                                        ]),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            ),

            # ── CURRENCY CARD ────────────────────────────────────────────────
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

            # ── EXPORT CARD ──────────────────────────────────────────────────
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

            # ── PRIVACY CARD ─────────────────────────────────────────────────
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
                                "Your budget data stays in local SQLite files on this device. "
                                "ML models (scikit-learn) also run fully locally — your spending "
                                "history is never sent anywhere for ML processing. "
                                "If you use cloud AI, only the prompt you send to the model goes over the internet.",
                                size=12,
                                color=ft.Colors.with_opacity(0.60, ft.Colors.ON_SURFACE),
                            ),
                        ],
                    ),
                )
            ),
        ],
    )
