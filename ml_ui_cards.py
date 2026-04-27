"""
ml_ui_cards.py
==============
ML-powered UI cards for the Budget Guardian dashboard.

HOW THIS WORKS (junior explanation):
-------------------------------------
ml_engine.py is the BRAIN  — it trains models, runs predictions, returns raw data.
ml_ui_cards.py is the FACE — it takes that raw data and renders it as Flet cards.

This file contains two cards:

  1. _forecast_card()    — "Next Month Forecast" bar chart + table
                           Shows predicted spending per category using
                           LinearRegression results from ml_engine.

  2. _anomaly_card()     — "Flagged Transactions" table
                           Shows transactions IsolationForest marked as suspicious,
                           sorted from most to least anomalous.

HOW TO PLUG THIS INTO dashboard_screen.py:
-------------------------------------------
Step 1 — Add this import near the top of dashboard_screen.py:
    from ml_ui_cards import build_ml_forecast_card, build_ml_anomaly_card

Step 2 — Add this near the top of the dashboard_screen() function,
         AFTER the existing db calls (after line where `balance = db.get_balance()`):

    import ml_engine
    ml_engine.check_and_retrain()          # retrain if schedule says it's time
    ml_forecast = ml_engine.get_forecast_summary()
    ml_anomalies = ml_engine.detect_anomalies()

Step 3 — Add the two cards to the `sections` list, before the last cashflow table.
         Find this block near the bottom of dashboard_screen():

    ft.ResponsiveRow(
        controls=[
            ft.Container(
                col={"xs": 12},
                content=_cashflow_table_card(monthly_cashflow, peso),
            ),
        ],
    ),

    And ADD ABOVE it:

    ft.ResponsiveRow(
        controls=[
            ft.Container(
                col={"xs": 12, "md": 6},
                content=build_ml_forecast_card(ml_forecast, peso),
            ),
            ft.Container(
                col={"xs": 12, "md": 6},
                content=build_ml_anomaly_card(ml_anomalies, peso),
            ),
        ],
    ),

That's it. Three changes, ~10 lines total.
"""

from __future__ import annotations

import base64
from io import BytesIO

import flet as ft
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ── Shared palette (matches your existing dashboard palette) ──────────────────
_PALETTE = [
    "#38bdf8", "#818cf8", "#fb923c", "#34d399", "#f472b6",
    "#fbbf24", "#a78bfa", "#22d3ee", "#4ade80", "#f87171",
]
_CARD_CONTENT_HEIGHT = 260  # matches dashboard_screen.py constant


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _fig_to_b64(fig) -> str:
    """Convert a matplotlib figure to base64 PNG string for Flet Image."""
    buf = BytesIO()
    fig.savefig(
        buf, format="png", dpi=130, bbox_inches="tight",
        facecolor=fig.get_facecolor(), transparent=False,
    )
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _section_card(
    title: str,
    subtitle: str,
    *,
    icon,
    accent_color: str,
    content: ft.Control,
    header_action: ft.Control | None = None,
) -> ft.Control:
    """
    Matches the _section_card() helper in dashboard_screen.py exactly.
    Duplicated here so this file is self-contained and importable on its own.
    """
    return ft.Card(
        elevation=2,
        content=ft.Container(
            padding=ft.Padding(left=16, right=16, top=14, bottom=14),
            border_radius=16,
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[
                    ft.Colors.with_opacity(0.08, accent_color),
                    ft.Colors.with_opacity(0.015, ft.Colors.BLACK),
                ],
            ),
            border=ft.border.all(1, ft.Colors.with_opacity(0.10, accent_color)),
            content=ft.Column(
                spacing=12,
                expand=True,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                expand=True,
                                controls=[
                                    ft.Container(
                                        width=34, height=34, border_radius=17,
                                        bgcolor=ft.Colors.with_opacity(0.14, accent_color),
                                        alignment=ft.Alignment(0, 0),
                                        content=ft.Icon(icon, size=18, color=accent_color),
                                    ),
                                    ft.Column(
                                        spacing=2, expand=True,
                                        controls=[
                                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                                            ft.Text(
                                                subtitle, size=11,
                                                color=ft.Colors.with_opacity(0.48, ft.Colors.ON_SURFACE),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            *( [header_action] if header_action is not None else [] ),
                        ],
                    ),
                    content,
                ],
            ),
        ),
    )


# =============================================================================
# CARD 1: SPENDING FORECAST
# =============================================================================

def _build_forecast_chart(forecast_summary: list[dict]) -> str | None:
    """
    Build a horizontal bar chart of predicted next-month spending.

    Each bar is colored by trend direction:
      🔴 Red   = spending is trending UP   (you'll likely spend more)
      🟢 Green = spending is trending DOWN  (you'll likely spend less)
      🔵 Blue  = spending is STABLE

    This makes it instantly obvious which categories need attention.
    """
    if not forecast_summary:
        return None

    # Show top 8 categories by predicted amount
    top = forecast_summary[:8]
    labels = [item["category"] for item in top]
    values = [item["predicted_amount"] for item in top]
    trends = [item["trend"] for item in top]

    # Color by trend
    trend_colors = {
        "up":     "#f87171",  # red — spending going up, warning
        "down":   "#4ade80",  # green — spending going down, good
        "stable": "#38bdf8",  # blue — stable, neutral
    }
    colors = [trend_colors.get(t, "#38bdf8") for t in trends]

    # Shorten long labels
    short_labels = [lb[:22] + "…" if len(lb) > 22 else lb for lb in labels]

    bg = "#0f172a"
    fig, ax = plt.subplots(
        figsize=(5.4, max(2.8, len(top) * 0.44)),
        facecolor=bg,
    )
    ax.set_facecolor(bg)

    y_pos = np.arange(len(top))
    bars = ax.barh(y_pos, values, color=colors, height=0.55, edgecolor="none", zorder=2)

    # Value labels
    max_val = max(values) if values else 1
    for bar, val, color in zip(bars, values, colors):
        label_x = bar.get_width() + max_val * 0.02
        ax.text(
            label_x, bar.get_y() + bar.get_height() / 2,
            f"{val:,.0f}",
            va="center", ha="left",
            color=color, fontsize=8, fontweight="bold",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(short_labels, color="#cbd5e1", fontsize=8.5)
    ax.invert_yaxis()
    ax.tick_params(axis="x", colors="#475569", labelsize=7.5, length=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max_val * 1.35)
    ax.grid(axis="x", alpha=0.10, color="#334155", linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Legend for trend colors
    legend_handles = [
        mpatches.Patch(color="#f87171", label="Trending Up ↑"),
        mpatches.Patch(color="#4ade80", label="Trending Down ↓"),
        mpatches.Patch(color="#38bdf8", label="Stable →"),
    ]
    ax.legend(
        handles=legend_handles, loc="lower right",
        frameon=False, fontsize=7, labelcolor="white",
        handlelength=1.0,
    )

    ax.set_title(
        "Predicted Spending — Next Month",
        color="white", fontsize=11, fontweight="bold", pad=10,
    )
    fig.tight_layout(pad=1.2)

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def build_ml_forecast_card(
    forecast_summary: list[dict],
    peso_fn,
    *,
    header_action: ft.Control | None = None,
) -> ft.Control:
    """
    Build the "Next Month Forecast" section card for the dashboard.

    Shows:
    - A matplotlib bar chart (colored by trend)
    - A compact table below with category, predicted amount, and trend arrow

    If the model hasn't been trained yet (not enough data),
    shows a friendly "not enough data" placeholder instead.
    """
    # ── No model yet ──────────────────────────────────────────────────────────
    if not forecast_summary:
        empty_body = ft.Container(
            height=_CARD_CONTENT_HEIGHT,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Text("🔮", size=32),
                    ft.Text(
                        "Forecast unavailable",
                        size=13, weight=ft.FontWeight.W_600,
                        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    ),
                    ft.Text(
                        "Keep logging expenses for 3+ months\nand the ML model will predict\nyour future spending here.",
                        size=11,
                        color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )
        return _section_card(
            "Next Month Forecast",
            "ML prediction — needs 3+ months of history",
            icon=ft.Icons.AUTO_GRAPH_ROUNDED,
            accent_color="#a78bfa",
            content=empty_body,
            header_action=header_action,
        )

    # ── Chart ─────────────────────────────────────────────────────────────────
    chart_b64 = _build_forecast_chart(forecast_summary)

    # ── Mini table below chart ────────────────────────────────────────────────
    # Show top 5 categories with trend arrows
    TREND_ICON  = {"up": "↑", "down": "↓", "stable": "→"}
    TREND_COLOR = {
        "up":     ft.Colors.RED_300,
        "down":   ft.Colors.GREEN_300,
        "stable": ft.Colors.BLUE_300,
    }

    table_rows: list[ft.Control] = []
    for item in forecast_summary[:5]:
        trend = item["trend"]
        table_rows.append(
            ft.Row(
                controls=[
                    ft.Container(
                        expand=5,
                        content=ft.Text(
                            item["category"], size=11,
                            weight=ft.FontWeight.W_500,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ),
                    ft.Container(
                        expand=3,
                        alignment=ft.Alignment(1, 0),
                        content=ft.Text(
                            peso_fn(item["predicted_amount"]),
                            size=11, weight=ft.FontWeight.W_600,
                        ),
                    ),
                    ft.Container(
                        expand=2,
                        alignment=ft.Alignment(1, 0),
                        content=ft.Text(
                            TREND_ICON.get(trend, "→"),
                            size=13, weight=ft.FontWeight.BOLD,
                            color=TREND_COLOR.get(trend, ft.Colors.BLUE_300),
                        ),
                    ),
                ],
            )
        )

    body = ft.Column(
        spacing=10,
        controls=[
            # Chart
            ft.Container(
                alignment=ft.Alignment(0, 0),
                content=ft.Image(
                    src=f"data:image/png;base64,{chart_b64}",
                    fit=ft.BoxFit.FIT_WIDTH,
                    expand=True,
                ) if chart_b64 else ft.Container(),
            ),
            # Table header
            ft.Row(controls=[
                ft.Container(expand=5, content=ft.Text(
                    "Category", size=10, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                )),
                ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(
                    "Predicted", size=10, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                )),
                ft.Container(expand=2, alignment=ft.Alignment(1, 0), content=ft.Text(
                    "Trend", size=10, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                )),
            ]),
            ft.Column(spacing=6, controls=table_rows),
        ],
    )

    return _section_card(
        "Next Month Forecast",
        "LinearRegression prediction based on your spending history.",
        icon=ft.Icons.AUTO_GRAPH_ROUNDED,
        accent_color="#a78bfa",
        content=body,
        header_action=header_action,
    )


# =============================================================================
# CARD 2: ANOMALY DETECTOR
# =============================================================================

def _suspicion_level(score: float) -> tuple[str, ft.Colors]:
    """
    Convert a raw IsolationForest anomaly score to a human-readable label.

    IsolationForest scores are negative — more negative = more anomalous.
    We bucket them into three levels so the user doesn't need to understand
    the raw numbers.

    Thresholds chosen empirically for typical personal finance data:
      < -0.20 = High suspicion (really isolated from normal patterns)
      < -0.10 = Medium suspicion
      else    = Low suspicion (borderline, just flagged)
    """
    if score < -0.20:
        return "High ⚠️", ft.Colors.RED_400
    elif score < -0.10:
        return "Medium 🟠", ft.Colors.ORANGE_300
    else:
        return "Low 🔵", ft.Colors.BLUE_300


def build_ml_anomaly_card(
    anomalies: list[dict],
    peso_fn,
    *,
    header_action: ft.Control | None = None,
) -> ft.Control:
    """
    Build the "Flagged Transactions" section card for the dashboard.

    Shows a table of transactions the IsolationForest model found unusual,
    sorted from most to least suspicious.

    Each row shows:
    - Date
    - Category
    - Amount
    - Suspicion level (High / Medium / Low)

    If no anomalies were detected, shows a positive "all looks normal" message.
    If the model isn't trained yet, shows a placeholder.
    """
    # ── Model not ready ───────────────────────────────────────────────────────
    if anomalies is None:
        # detect_anomalies() returns [] when model not ready — this branch
        # is here for safety in case None is passed
        anomalies = []

    # ── No anomalies found ────────────────────────────────────────────────────
    if not anomalies:
        # Two different messages depending on whether the model is trained
        try:
            import ml_engine
            model_ready = ml_engine._model_path("anomaly_detector").exists()
        except Exception:
            model_ready = False

        if model_ready:
            body_content = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Text("✅", size=32),
                    ft.Text(
                        "All transactions look normal",
                        size=13, weight=ft.FontWeight.W_600,
                        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    ),
                    ft.Text(
                        "The anomaly detector didn't find\nany unusual transactions this period.",
                        size=11,
                        color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            )
        else:
            body_content = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Text("🔍", size=32),
                    ft.Text(
                        "Anomaly detection not ready yet",
                        size=13, weight=ft.FontWeight.W_600,
                        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    ),
                    ft.Text(
                        f"Log at least 30 expense transactions\nand the model will learn what\n'normal' looks like for you.",
                        size=11,
                        color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            )

        return _section_card(
            "Flagged Transactions",
            "IsolationForest anomaly detection",
            icon=ft.Icons.POLICY_ROUNDED,
            accent_color="#f472b6",
            content=ft.Container(
                height=_CARD_CONTENT_HEIGHT,
                alignment=ft.Alignment(0, 0),
                content=body_content,
            ),
            header_action=header_action,
        )

    # ── Anomalies found — build table ─────────────────────────────────────────
    header = ft.Row(controls=[
        ft.Container(expand=2, content=ft.Text(
            "Date", size=10, weight=ft.FontWeight.BOLD,
            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
        )),
        ft.Container(expand=4, content=ft.Text(
            "Category", size=10, weight=ft.FontWeight.BOLD,
            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
        )),
        ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(
            "Amount", size=10, weight=ft.FontWeight.BOLD,
            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
        )),
        ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(
            "Suspicion", size=10, weight=ft.FontWeight.BOLD,
            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
        )),
    ])

    table_rows: list[ft.Control] = []
    for txn in anomalies:
        level_label, level_color = _suspicion_level(txn["anomaly_score"])
        # Format date: "2025-03-14" → "Mar 14"
        try:
            from datetime import date as _date
            d = _date.fromisoformat(txn["txn_date"])
            date_str = d.strftime("%b %d")
        except Exception:
            date_str = txn["txn_date"][:7]

        table_rows.append(
            ft.Container(
                padding=ft.Padding(left=10, right=10, top=9, bottom=9),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                content=ft.Row(controls=[
                    ft.Container(expand=2, content=ft.Text(
                        date_str, size=11,
                        color=ft.Colors.with_opacity(0.65, ft.Colors.ON_SURFACE),
                    )),
                    ft.Container(expand=4, content=ft.Text(
                        txn["category"], size=11,
                        weight=ft.FontWeight.W_500,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    )),
                    ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(
                        peso_fn(txn["amount"]),
                        size=11, weight=ft.FontWeight.W_600,
                        color=ft.Colors.RED_300,
                    )),
                    ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(
                        level_label, size=10, color=level_color,
                    )),
                ]),
            )
        )

    body = ft.Column(
        spacing=0,
        controls=[
            ft.Row(
                controls=[
                    ft.Text(
                        f"⚠️ {len(anomalies)} unusual transaction(s) found",
                        size=12,
                        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                    ),
                ],
            ),
            ft.Container(height=8),
            header,
            ft.Container(height=6),
            ft.Column(
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                height=_CARD_CONTENT_HEIGHT - 44,
                controls=table_rows,
            ),
        ],
    )

    return _section_card(
        "Flagged Transactions",
        "IsolationForest anomaly detection — sorted by suspicion level.",
        icon=ft.Icons.POLICY_ROUNDED,
        accent_color="#f472b6",
        content=body,
        header_action=header_action,
    )
