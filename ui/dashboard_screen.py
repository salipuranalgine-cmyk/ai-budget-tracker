from __future__ import annotations

import base64
from io import BytesIO

import flet as ft
import matplotlib.pyplot as plt
import pandas as pd

import database as db
from ai_insights import get_ai_insight
from ui.constants import now_month, peso, make_peso


def _fig_to_b64() -> str:
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#111827")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _build_pie_chart(expense_map: dict[str, float]) -> str | None:
    if not expense_map:
        return None
    df = pd.DataFrame(
        [{"category": k, "amount": v} for k, v in expense_map.items()],
        columns=["category", "amount"],
    )
    fig, ax = plt.subplots(figsize=(4.5, 3.2), facecolor="#111827")
    ax.pie(
        df["amount"],
        labels=df["category"],
        autopct="%1.0f%%",
        startangle=140,
        textprops={"color": "white", "fontsize": 8},
    )
    ax.set_title("Monthly Category Breakdown", color="white", fontsize=10)
    b64 = _fig_to_b64()
    plt.close(fig)
    return b64


def _build_line_chart(points: list[tuple[str, float]]) -> str | None:
    if not points:
        return None
    df = pd.DataFrame(points, columns=["date", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    fig, ax = plt.subplots(figsize=(4.8, 2.8), facecolor="#111827")
    ax.plot(df["date"], df["amount"], linewidth=2.2, marker="o", color="#38bdf8")
    ax.set_title("Spending Trend (Last 30 Days)", color="white", fontsize=10)
    ax.tick_params(colors="white", labelsize=7)
    ax.set_facecolor("#111827")
    ax.grid(alpha=0.25)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    b64 = _fig_to_b64()
    plt.close(fig)
    return b64


def dashboard_screen(page: ft.Page, on_data_changed) -> ft.Control:
    currency_code = db.get_currency()
    peso = make_peso(currency_code)  # dynamic currency
    month = now_month()
    balance = db.get_balance()
    expense_map = db.get_month_expense_summary(month)
    month_total = sum(expense_map.values())
    month_income = db.get_month_income_total(month)
    net_cashflow = month_income - month_total

    biggest_category = max(expense_map, key=lambda k: expense_map[k]) if expense_map else "N/A"
    biggest_value = expense_map.get(biggest_category, 0.0)

    pie_b64 = _build_pie_chart(expense_map)
    line_b64 = _build_line_chart(db.get_expenses_last_days(30))
    insight_text = ft.Text(
        "Tap Ask AI for smart budget tips, bro-style.",
        selectable=True,
        size=13,
    )

    def ask_ai(_):
        context = (
            f"Currency: {currency_code}\n"
            f"Month: {month}\n"
            f"Current balance: {peso(balance)}\n"
            f"Total spent this month: {peso(month_total)}\n"
            f"Biggest category: {biggest_category} ({peso(biggest_value)})\n"
            f"Category map: {expense_map}"
        )
        api_key = db.get_anthropic_api_key()
        insight_text.value = get_ai_insight(context, api_key=api_key)
        page.update()

    # --- Quick Add Income dialog (inline, minimal) ---
    def open_add_income(_):
        from ui.transactions_screen import _income_dialog

        def done(**_kwargs):
            on_data_changed()

        _income_dialog(page, done)

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            # Balance card with "Add Income" button
            ft.Card(
                content=ft.Container(
                    padding=16,
                    border_radius=20,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=["#0ea5e9", "#6366f1"],
                    ),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                controls=[
                                    ft.Column(
                                        spacing=4,
                                        controls=[
                                            ft.Text(
                                                "Current Balance",
                                                color=ft.Colors.WHITE70,
                                                size=14,
                                            ),
                                            ft.Text(
                                                peso(balance),
                                                color=ft.Colors.WHITE,
                                                size=34,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ],
                                    ),
                                    ft.ElevatedButton(
                                        "+ Income",
                                        icon=ft.Icons.ADD_CIRCLE,
                                        on_click=open_add_income,
                                        style=ft.ButtonStyle(
                                            bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE),
                                            color=ft.Colors.WHITE,
                                            shadow_color=ft.Colors.TRANSPARENT,
                                            overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
                                            shape=ft.RoundedRectangleBorder(radius=12),
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ft.Card(
                            content=ft.Container(
                                padding=14,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Spent This Month", size=13),
                                        ft.Text(
                                            peso(month_total),
                                            size=22,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ORANGE_300,
                                        ),
                                    ]
                                ),
                            )
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ft.Card(
                            content=ft.Container(
                                padding=14,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Biggest Category", size=13),
                                        ft.Text(
                                            f"{biggest_category} ({peso(biggest_value)})",
                                            size=20,
                                            weight=ft.FontWeight.W_700,
                                        ),
                                    ]
                                ),
                            )
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ft.Card(
                            content=ft.Container(
                                padding=14,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Income This Month", size=13),
                                        ft.Text(
                                            peso(month_income),
                                            size=22,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.GREEN_400,
                                        ),
                                    ]
                                ),
                            )
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 6},
                        content=ft.Card(
                            content=ft.Container(
                                padding=14,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Net Cashflow", size=13),
                                        ft.Text(
                                            ("+" if net_cashflow >= 0 else "") + peso(net_cashflow),
                                            size=22,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.GREEN_400 if net_cashflow >= 0 else ft.Colors.RED_400,
                                        ),
                                        ft.Text(
                                            "income minus expenses",
                                            size=11,
                                            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                                        ),
                                    ]
                                ),
                            )
                        ),
                    ),
                ]
            ),
            ft.Card(
                content=ft.Container(
                    padding=14,
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("AI Warning & Insights", weight=ft.FontWeight.BOLD),
                                    ft.ElevatedButton(
                                        "Ask AI",
                                        icon=ft.Icons.AUTO_AWESOME,
                                        on_click=ask_ai,
                                    ),
                                ],
                            ),
                            insight_text,
                        ]
                    ),
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=8,
                    content=(
                        ft.Image(src=f"data:image/png;base64,{pie_b64}", fit=ft.BoxFit.CONTAIN)
                        if pie_b64
                        else ft.Text("No expenses yet for this month.")
                    ),
                )
            ),
            ft.Card(
                content=ft.Container(
                    padding=8,
                    content=(
                        ft.Image(src=f"data:image/png;base64,{line_b64}", fit=ft.BoxFit.CONTAIN)
                        if line_b64
                        else ft.Text("No trend data yet.")
                    ),
                )
            ),
        ],
    )