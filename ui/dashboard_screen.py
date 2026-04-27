from __future__ import annotations
from ml_ui_cards import build_ml_forecast_card, build_ml_anomaly_card

import ml_engine
import asyncio
import base64
import threading
from datetime import date, timedelta
from io import BytesIO

import flet as ft
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

_bg_results: dict[int, str] = {}
_bg_lock = threading.Lock()
_pending_sessions: set[int] = set()
_active_callbacks: dict[int, callable] = {}
_sessions_meta_lock = threading.Lock()

import pandas as pd
import database as db
import notifications as notif
from ai_insights import chat_with_ai
from ui.constants import now_month, make_peso


# ---------------------------------------------------------------------------
# AI [NOTIFY:] tag parser
# ---------------------------------------------------------------------------

def _parse_notify_tag(reply: str) -> tuple[str, str | None, str | None]:
    """
    Strip a trailing [NOTIFY: title | message] tag from an AI reply.
    Returns (clean_reply, title_or_None, message_or_None).
    """
    import re
    pattern = r'\[NOTIFY:\s*(.+?)\s*\|\s*(.+?)\s*\]\s*$'
    m = re.search(pattern, reply, re.MULTILINE | re.IGNORECASE)
    if m:
        clean = reply[:m.start()].rstrip()
        return clean, m.group(1).strip(), m.group(2).strip()
    return reply, None, None


# ---------------------------------------------------------------------------
# Chart helpers — professional dark-theme matplotlib charts
# ---------------------------------------------------------------------------

_PALETTE = ["#38bdf8", "#818cf8", "#fb923c", "#34d399", "#f472b6",
            "#fbbf24", "#a78bfa", "#22d3ee", "#4ade80", "#f87171"]


def _fig_to_b64(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor(), transparent=False)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _build_donut_chart(expense_map: dict[str, float]) -> str | None:
    if not expense_map:
        return None

    # Keep top 7, group rest as "Others"
    sorted_items = sorted(expense_map.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_items) > 7:
        top = sorted_items[:7]
        others = sum(v for _, v in sorted_items[7:])
        top.append(("Others", others))
        sorted_items = top

    labels = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    total = sum(values)
    colors = _PALETTE[:len(labels)]

    bg = "#0f172a"
    fig, ax = plt.subplots(figsize=(5.2, 3.6), facecolor=bg)
    ax.set_facecolor(bg)

    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        wedgeprops=dict(width=0.55, edgecolor=bg, linewidth=2),
    )

    # Center label
    ax.text(0, 0.08, "Total", ha="center", va="center",
            color="#94a3b8", fontsize=9, fontweight="normal")
    ax.text(0, -0.18, f"{total:,.0f}", ha="center", va="center",
            color="white", fontsize=13, fontweight="bold")

    # Legend on right
    legend_items = [
        mpatches.Patch(color=colors[i], label=f"{labels[i][:18]}  {values[i]/total*100:.0f}%")
        for i in range(len(labels))
    ]
    ax.legend(
        handles=legend_items,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=7.5,
        frameon=False,
        labelcolor="white",
        handlelength=1.2,
        handleheight=1.0,
    )

    ax.set_title("Spending by Category", color="white", fontsize=11,
                 fontweight="bold", pad=10)
    fig.subplots_adjust(left=0.02, right=0.72)

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def _build_area_line_chart(points: list[tuple[str, float]]) -> str | None:
    if not points:
        return None

    df = pd.DataFrame(points, columns=["date", "amount"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    bg = "#0f172a"
    fig, ax = plt.subplots(figsize=(5.4, 2.9), facecolor=bg)
    ax.set_facecolor(bg)

    x = np.arange(len(df))
    y = df["amount"].values

    # Smooth gradient fill
    ax.fill_between(x, y, alpha=0.25, color="#38bdf8")
    ax.fill_between(x, y, alpha=0.10, color="#818cf8")
    ax.plot(x, y, color="#38bdf8", linewidth=2.2, zorder=3)
    ax.scatter(x, y, color="#38bdf8", s=28, zorder=4, edgecolors=bg, linewidths=1.5)

    # Highlight max point
    if len(y) > 0:
        max_idx = int(np.argmax(y))
        ax.scatter([x[max_idx]], [y[max_idx]], color="#f472b6", s=55, zorder=5,
                   edgecolors=bg, linewidths=1.5)
        ax.annotate(f"{y[max_idx]:,.0f}",
                    (x[max_idx], y[max_idx]),
                    textcoords="offset points", xytext=(0, 10),
                    color="#f472b6", fontsize=7.5, ha="center", fontweight="bold")

    # X-axis ticks — show every ~5th date
    step = max(1, len(df) // 6)
    tick_positions = x[::step]
    tick_labels = [df["date"].iloc[i].strftime("%b %d") for i in range(0, len(df), step)]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, color="#64748b", fontsize=7.5, rotation=0)
    ax.tick_params(axis="y", colors="#64748b", labelsize=7.5)
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", length=0)

    ax.set_facecolor(bg)
    ax.grid(axis="y", alpha=0.12, color="#334155", linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title("Daily Spending — Last 30 Days", color="white", fontsize=11,
                 fontweight="bold", pad=10)

    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def _build_bar_chart(expense_map: dict[str, float]) -> str | None:
    if not expense_map:
        return None

    sorted_items = sorted(expense_map.items(), key=lambda x: x[1], reverse=True)[:8]
    labels = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]

    # Shorten long labels
    short_labels = [lb[:20] + "…" if len(lb) > 20 else lb for lb in labels]

    bg = "#0f172a"
    fig, ax = plt.subplots(figsize=(5.4, max(2.6, len(labels) * 0.42)), facecolor=bg)
    ax.set_facecolor(bg)

    y_pos = np.arange(len(labels))
    bar_colors = _PALETTE[:len(labels)]

    bars = ax.barh(y_pos, values, color=bar_colors, height=0.55,
                   edgecolor="none", zorder=2)

    # Value labels inside bars
    max_val = max(values) if values else 1
    for bar, val, color in zip(bars, values, bar_colors):
        label_x = bar.get_width() + max_val * 0.02
        ax.text(label_x, bar.get_y() + bar.get_height() / 2,
                f"{val:,.0f}", va="center", ha="left",
                color=color, fontsize=8, fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(short_labels, color="#cbd5e1", fontsize=8.5)
    ax.invert_yaxis()
    ax.tick_params(axis="x", colors="#475569", labelsize=7.5, length=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max_val * 1.32)
    ax.grid(axis="x", alpha=0.10, color="#334155", linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title("Top Spending Categories", color="white", fontsize=11,
                 fontweight="bold", pad=10)

    fig.tight_layout(pad=1.2)
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


# ---------------------------------------------------------------------------
# Clipboard helper — works across Flet versions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Chat bubble helpers
# ---------------------------------------------------------------------------

def _ai_bubble(text: str, bubble_w: int = 0) -> ft.Control:
    return ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Container(
                width=34, height=34, border_radius=17,
                bgcolor="#1e3a5f",
                alignment=ft.Alignment(0, 0),
                content=ft.Text("🤖", size=16),
            ),
            ft.Container(
                expand=True,
                content=ft.Text(text, selectable=True, size=13, color=ft.Colors.WHITE),
                padding=ft.Padding(left=14, right=14, top=10, bottom=10),
                bgcolor="#1e293b",
                border_radius=ft.BorderRadius(top_left=4, top_right=16, bottom_left=16, bottom_right=16),
                margin=ft.Margin(bottom=10, top=0, left=8, right=0),
            ),
        ],
    )


def _typing_bubble() -> ft.Control:
    return ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                width=34, height=34, border_radius=17,
                bgcolor="#1e3a5f",
                alignment=ft.Alignment(0, 0),
                content=ft.Text("🤖", size=16),
            ),
            ft.Container(
                expand=True,
                margin=ft.Margin(left=8, bottom=10, top=0, right=0),
                content=ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.ProgressRing(width=12, height=12, stroke_width=2, color="#38bdf8"),
                        ft.Text("AI is thinking…", size=12, italic=True,
                                color=ft.Colors.with_opacity(0.6, ft.Colors.WHITE)),
                    ],
                ),
                padding=ft.Padding(left=14, right=14, top=10, bottom=10),
                bgcolor="#1e293b",
                border_radius=ft.BorderRadius(top_left=4, top_right=16, bottom_left=16, bottom_right=16),
            ),
        ],
    )


def _generate_session_title(user_message: str, ai_reply: str) -> str:
    user_lower = user_message.lower()
    topics = {
        "Budget Planning": ["budget", "plan", "planning", "monthly budget"],
        "Savings Goals": ["save", "saving", "goal", "emergency fund"],
        "Expense Analysis": ["spending", "expenses", "expense", "track expenses"],
        "Income Questions": ["income", "salary", "earn", "revenue"],
        "Investment": ["invest", "investment", "stocks", "crypto"],
        "Debt Management": ["debt", "loan", "credit card", "pay off"],
        "Monthly Review": ["month", "review", "summary", "report"],
        "Category Spending": ["category", "food", "transport", "utilities"],
        "Financial Advice": ["advice", "help", "should i", "recommend"],
        "Questions": ["what", "when", "where", "why", "how"],
    }
    for topic, keywords in topics.items():
        if any(keyword in user_lower for keyword in keywords):
            if topic == "Category Spending":
                for cat in ["food", "transport", "utilities", "entertainment", "shopping"]:
                    if cat in user_lower:
                        return f"{cat.title()} Spending"
            return topic
    words = user_message.split()
    title = " ".join(words[:4]) if len(words) >= 4 else user_message
    return title[:55].rstrip() + ("…" if len(title) > 55 else "")


# ---------------------------------------------------------------------------
# History dialog
# ---------------------------------------------------------------------------

def _open_history_dialog(page: ft.Page, financial_context: str, api_key: str) -> None:
    sessions_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=6)
    storage_text = ft.Text("", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))
    selected_ids: list[int] = []
    session_cards: dict[int, ft.Card] = {}

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Text("💬", size=20),
                    ft.Text("Chat History", weight=ft.FontWeight.BOLD, size=16),
                ]),
                ft.IconButton(icon=ft.Icons.CLOSE, icon_size=20, on_click=lambda _: _close()),
            ],
        ),
        content=ft.Container(
            width=520, height=480,
            content=ft.Column(
                expand=True, spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        storage_text,
                        ft.Row(spacing=4, controls=[
                            ft.TextButton("+ New Chat", icon=ft.Icons.ADD, on_click=lambda _: _new_chat()),
                            ft.TextButton("🗑️ Clear All", icon=ft.Icons.DELETE_FOREVER,
                                          style=ft.ButtonStyle(color=ft.Colors.RED_400),
                                          on_click=lambda _: _confirm_clear_all()),
                        ]),
                    ]),
                    ft.Divider(height=1),
                    ft.Container(expand=True, content=sessions_col),
                    ft.Row(visible=False, controls=[
                        ft.TextButton("Select All", on_click=lambda _: _select_all()),
                        ft.TextButton("Deselect All", on_click=lambda _: _deselect_all()),
                        ft.ElevatedButton("Delete Selected", icon=ft.Icons.DELETE,
                                          style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                                          on_click=lambda _: _confirm_delete_selected()),
                    ], key="bulk_actions_row"),
                ],
            ),
        ),
        actions=[],
    )

    def _close():
        dlg.open = False
        page.update()

    def _new_chat():
        _close()
        _open_ai_chat(page, financial_context, api_key, None, [])

    def _resume(session_id: int):
        history = db.get_chat_messages(session_id)
        _close()
        _open_ai_chat(page, financial_context, api_key, session_id, history)

    def _refresh():
        sessions = db.get_chat_sessions()
        kb = db.get_chat_storage_kb()
        storage_text.value = f"💾 Storage used: {kb} KB"
        sessions_col.controls.clear()
        selected_ids.clear()
        session_cards.clear()

        if not sessions:
            sessions_col.controls.append(
                ft.Container(padding=40, alignment=ft.Alignment(0, 0),
                             content=ft.Text("No conversations yet.\nStart a new chat!",
                                             text_align=ft.TextAlign.CENTER,
                                             color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)))
            )
            _update_bulk_visibility()
            page.update()
            return

        for s in sessions:
            sid = s["id"]
            preview = (s["preview"] or "No messages yet")[:85]
            checkbox = ft.Checkbox(value=False,
                                   on_change=lambda e, sid=sid: _toggle_select(sid, e.control.value))
            card = ft.Card(content=ft.Container(
                padding=12,
                content=ft.Row(controls=[
                    checkbox,
                    ft.Column(expand=True, spacing=2, controls=[
                        ft.Row(spacing=4, controls=[
                            ft.Text(s["title"], weight=ft.FontWeight.W_600, size=13, expand=True),
                            ft.IconButton(icon=ft.Icons.EDIT, icon_size=16,
                                          icon_color=ft.Colors.BLUE_300, tooltip="Edit title",
                                          on_click=lambda _, sid=sid, t=s["title"]: _edit_title(sid, t)),
                        ]),
                        ft.Text(preview, size=11,
                                color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)),
                        ft.Text(f"{s['created_at'][:16]} · {s['msg_count']} messages",
                                size=10, color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)),
                    ]),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300,
                                  tooltip="Delete",
                                  on_click=lambda _, sid=sid, title=s["title"]: _confirm_delete(sid, title)),
                ]),
                on_click=lambda _, sid=sid: _resume(sid),
            ))
            session_cards[sid] = card
            sessions_col.controls.append(card)

        _update_bulk_visibility()
        page.update()

    def _toggle_select(sid, checked):
        if checked and sid not in selected_ids:
            selected_ids.append(sid)
        elif not checked and sid in selected_ids:
            selected_ids.remove(sid)
        _update_bulk_visibility()

    def _select_all():
        selected_ids[:] = list(session_cards.keys())
        _refresh_checkboxes()

    def _deselect_all():
        selected_ids.clear()
        _refresh_checkboxes()

    def _refresh_checkboxes():
        for sid, card in session_cards.items():
            for child in card.content.content.controls:
                if isinstance(child, ft.Checkbox):
                    child.value = sid in selected_ids
        _update_bulk_visibility()
        page.update()

    def _update_bulk_visibility():
        bulk_row = next((c for c in dlg.content.content.controls
                         if getattr(c, "key", None) == "bulk_actions_row"), None)
        if bulk_row:
            bulk_row.visible = len(selected_ids) > 0

    def _confirm_delete(sid, title):
        confirm = ft.AlertDialog(
            modal=True, title=ft.Text("Delete conversation?"),
            content=ft.Text(f'"{title}" will be permanently deleted.'),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Delete", style=ft.ButtonStyle(color=ft.Colors.RED_400),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(),
                                                  db.delete_chat_session(sid), _refresh())),
            ],
        )
        page.overlay.append(confirm)
        confirm.open = True
        page.update()

    def _confirm_delete_selected():
        if not selected_ids:
            return
        count = len(selected_ids)
        confirm = ft.AlertDialog(
            modal=True, title=ft.Text("Delete selected chats?"),
            content=ft.Text(f"{count} conversation(s) will be permanently deleted."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Delete All Selected", style=ft.ButtonStyle(color=ft.Colors.RED_400),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(),
                                                  _do_bulk_delete())),
            ],
        )
        page.overlay.append(confirm)
        confirm.open = True
        page.update()

    def _do_bulk_delete():
        for sid in list(selected_ids):
            db.delete_chat_session(sid)
        selected_ids.clear()
        _refresh()

    def _confirm_clear_all():
        confirm = ft.AlertDialog(
            modal=True, title=ft.Text("🗑️ Wipe ALL chat history?"),
            content=ft.Text("This will permanently delete EVERY conversation.\n\nThis cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Yes, Clear Everything",
                              style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(),
                                                  db.delete_all_chat_sessions(), _refresh())),
            ],
        )
        page.overlay.append(confirm)
        confirm.open = True
        page.update()

    def _edit_title(session_id, current_title):
        title_field = ft.TextField(label="Session Title", value=current_title,
                                   autofocus=True, max_length=60)

        def _save():
            new_title = title_field.value.strip()
            if not new_title:
                return
            db.update_chat_session_title(session_id, new_title)
            edit_dlg.open = False
            page.update()
            _refresh()

        edit_dlg = ft.AlertDialog(
            modal=True, title=ft.Text("Edit Session Title", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=400,
                                 content=ft.Column(tight=True, spacing=14,
                                                   controls=[ft.Text("Give this conversation a name:", size=13),
                                                             title_field])),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(edit_dlg, "open", False), page.update())),
                ft.ElevatedButton("Save", icon=ft.Icons.SAVE, on_click=lambda _: _save(),
                                  style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(edit_dlg)
        edit_dlg.open = True
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    _refresh()


# ---------------------------------------------------------------------------
# Main chat dialog
# ---------------------------------------------------------------------------

def _open_ai_chat(page, financial_context, api_key, session_id, history):
    win_w = getattr(page, "window_width", None) or getattr(page, "width", None) or 900
    win_h = getattr(page, "window_height", None) or getattr(page, "height", None) or 700
    dlg_w = max(320, min(720, int(win_w * 0.92)))
    dlg_h = max(440, min(700, int(win_h * 0.88)))

    current_session = [session_id]
    conv_history = list(history)
    is_typing = [False]
    _has_welcome = [not bool(history)]
    bubble_map: list[tuple[int, ft.Control]] = []
    _stop_requested = [False]

    messages_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, auto_scroll=True)

    def _edit_and_resend(hist_idx, bubble_row, new_text):
        if is_typing[0]:
            return
        try:
            bubble_pos = messages_col.controls.index(bubble_row)
        except ValueError:
            return
        messages_col.controls = messages_col.controls[:bubble_pos]
        conv_history[:] = conv_history[:hist_idx]
        bubble_map[:] = [(i, c) for (i, c) in bubble_map if i < hist_idx]
        if current_session[0] is not None:
            db_keep = hist_idx - (1 if _has_welcome[0] else 0)
            db.truncate_chat_messages_after_index(current_session[0], db_keep)
        page.update()
        _send(new_text)

    def _add_user_bubble(text, hist_idx):
        current_text = [text]
        msg_col = ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END, expand=True)
        outer_row = ft.Row(
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[ft.Container(width=48), msg_col],
        )
        btn_color = ft.Colors.with_opacity(0.45, ft.Colors.WHITE)
        btn_style = ft.ButtonStyle(padding=ft.padding.only(left=0, right=2, top=0, bottom=0))

        def _render_view():
            msg_col.controls = [
                ft.Container(
                    expand=True,
                    content=ft.Text(current_text[0], selectable=True, size=13, color=ft.Colors.WHITE),
                    padding=ft.Padding(left=14, right=14, top=10, bottom=10),
                    bgcolor="#0369a1",
                    border_radius=ft.BorderRadius(top_left=16, top_right=4, bottom_left=16, bottom_right=16),
                    margin=ft.Margin(bottom=2, top=0, left=0, right=0),
                ),
                ft.Row(spacing=0, alignment=ft.MainAxisAlignment.END, controls=[
                    ft.TextButton(
                        content=ft.Row(spacing=3, controls=[
                            ft.Icon(ft.Icons.EDIT_OUTLINED, size=11, color=btn_color),
                            ft.Text("Edit", size=10, color=btn_color),
                        ]),
                        on_click=lambda _: _render_edit(), style=btn_style, tooltip="Edit and resend",
                    ),
                ]),
            ]
            page.update()

        def _render_edit():
            if is_typing[0]:
                return
            ef = ft.TextField(
                value=current_text[0], multiline=True, min_lines=1, max_lines=6,
                text_size=13, autofocus=True, border_radius=12,
                border_color="#334155", focused_border_color="#0ea5e9", expand=True,
            )

            def _confirm(_=None):
                new_text = (ef.value or "").strip()
                if not new_text:
                    return
                current_text[0] = new_text
                _render_view()
                _edit_and_resend(hist_idx, outer_row, new_text)

            ef.on_submit = lambda e: _confirm()
            msg_col.controls = [
                ft.Container(
                    expand=True, bgcolor="#0f172a", border_radius=12,
                    padding=ft.padding.all(8), border=ft.border.all(1, "#334155"),
                    content=ft.Column(spacing=6, controls=[
                        ef,
                        ft.Row(alignment=ft.MainAxisAlignment.END, spacing=6, controls=[
                            ft.TextButton("Cancel", on_click=lambda _: _render_view(),
                                          style=ft.ButtonStyle(color=ft.Colors.with_opacity(0.6, ft.Colors.WHITE))),
                            ft.FilledButton("Send edit", icon=ft.Icons.SEND_ROUNDED, on_click=_confirm,
                                            style=ft.ButtonStyle(bgcolor="#0369a1", color=ft.Colors.WHITE,
                                                                 shape=ft.RoundedRectangleBorder(radius=10))),
                        ]),
                    ]),
                )
            ]
            page.update()
            ef.focus()

        _render_view()
        bubble_map.append((hist_idx, outer_row))
        messages_col.controls.append(outer_row)

    def _add_ai_bubble(text):
        messages_col.controls.append(_ai_bubble(text))

    for idx, msg in enumerate(conv_history):
        if msg["role"] == "assistant":
            _add_ai_bubble(msg["content"])
        else:
            _add_user_bubble(msg["content"], idx)

    if not conv_history:
        welcome_msg = "Hi! How can I help you today with your budget?"
        _add_ai_bubble(welcome_msg)
        conv_history.append({"role": "assistant", "content": welcome_msg})

    input_field = ft.TextField(
        hint_text="Ask anything about your budget…",
        border_radius=24, border_color="#334155", focused_border_color="#0ea5e9",
        text_size=13, expand=True, multiline=False,
        on_submit=lambda e: _send(e.control.value),
    )
    send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color="#0ea5e9",
                             icon_size=22, tooltip="Send",
                             on_click=lambda _: _send(input_field.value))
    stop_btn = ft.IconButton(icon=ft.Icons.STOP_CIRCLE_OUTLINED, icon_color="#f87171",
                             icon_size=22, tooltip="Stop", visible=False,
                             on_click=lambda _: _stop_thinking())
    typing_ind = _typing_bubble()

    def _update_stop_btn():
        stop_btn.visible = is_typing[0]
        send_btn.visible = not is_typing[0]

    def _set_input_enabled(enabled):
        input_field.disabled = not enabled
        _update_stop_btn()

    def _stop_thinking():
        if not is_typing[0]:
            return
        _stop_requested[0] = True
        is_typing[0] = False
        _set_input_enabled(True)
        if typing_ind in messages_col.controls:
            messages_col.controls.remove(typing_ind)
        page.update()

    def _register_callback(sid):
        def _deliver(reply):
            if (conv_history and conv_history[-1].get("role") == "assistant"
                    and conv_history[-1].get("content") == reply):
                return
            conv_history.append({"role": "assistant", "content": reply})
            is_typing[0] = False
            _set_input_enabled(True)
            if typing_ind in messages_col.controls:
                messages_col.controls.remove(typing_ind)
            try:
                if dlg.open:
                    _add_ai_bubble(reply)
                    page.update()
                else:
                    with _bg_lock:
                        _bg_results[sid] = reply
            except Exception:
                with _bg_lock:
                    _bg_results[sid] = reply
        with _sessions_meta_lock:
            _active_callbacks[sid] = _deliver

    def _unregister_callback(sid):
        with _sessions_meta_lock:
            _active_callbacks.pop(sid, None)

    def _ensure_session():
        if current_session[0] is None:
            current_session[0] = db.create_chat_session("New Chat")
            _register_callback(current_session[0])
        return current_session[0]

    def _send(text):
        if is_typing[0]:
            return
        text = (text or "").strip()
        if not text:
            return
        hist_idx = len(conv_history)
        input_field.value = ""
        conv_history.append({"role": "user", "content": text})
        _add_user_bubble(text, hist_idx)
        sid = _ensure_session()
        db.save_chat_message(sid, "user", text)
        is_typing[0] = True
        _stop_requested[0] = False
        _set_input_enabled(False)
        with _sessions_meta_lock:
            _pending_sessions.add(sid)
        if typing_ind not in messages_col.controls:
            messages_col.controls.append(typing_ind)
        page.update()

        async def _worker():
            raw_reply = await asyncio.to_thread(
                chat_with_ai,
                list(conv_history),
                financial_context,
                api_key,
            )
            # Strip any [NOTIFY: title | message] tag before saving/displaying
            reply, notif_title, notif_msg = _parse_notify_tag(raw_reply)
            if notif_title and notif_msg:
                # AI explicitly flagged something — add it directly
                notif.add_ai_insight(notif_title, notif_msg)
            else:
                # Fallback: keyword-scan the reply for financial alerts
                notif.scan_ai_reply(reply)
            with _sessions_meta_lock:
                _pending_sessions.discard(sid)
                callback = _active_callbacks.get(sid)
            if _stop_requested[0]:
                _stop_requested[0] = False
                return
            await asyncio.to_thread(db.save_chat_message, sid, "assistant", reply)
            user_msgs = [m for m in conv_history if m["role"] == "user"]
            if len(user_msgs) == 1:
                title = _generate_session_title(user_msgs[0]["content"], reply)
                await asyncio.to_thread(db.update_chat_session_title, sid, title)
            if callback:
                try:
                    callback(reply)
                except Exception:
                    with _bg_lock:
                        _bg_results[sid] = reply
            else:
                with _bg_lock:
                    _bg_results[sid] = reply

        page.run_task(_worker)

    def _open_history(_):
        _close()
        _open_history_dialog(page, financial_context, api_key)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=8, expand=True, controls=[
                    ft.Container(width=28, height=28, border_radius=14,
                                 bgcolor="#1e3a5f", alignment=ft.Alignment(0, 0),
                                 content=ft.Text("🤖", size=14)),
                    ft.Text("AI Finance Advisor", weight=ft.FontWeight.BOLD, size=15, expand=True),
                ]),
                ft.Row(spacing=0, controls=[
                    ft.IconButton(icon=ft.Icons.HISTORY, icon_size=20,
                                  tooltip="Chat History", on_click=_open_history),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_size=20,
                                  tooltip="Close", on_click=lambda _: _close()),
                ]),
            ],
        ),
        content=ft.Container(
            width=dlg_w, height=dlg_h,
            content=ft.Column(spacing=0, expand=True, controls=[
                ft.Container(expand=True, content=messages_col,
                             padding=ft.Padding(left=4, right=4, top=4, bottom=4)),
                ft.Divider(height=1, color="#1e293b"),
                ft.Container(
                    padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                    content=ft.Row(spacing=6,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                   controls=[input_field, stop_btn, send_btn]),
                ),
            ]),
        ),
        actions=[],
    )

    def _close():
        dlg.open = False
        if current_session[0] is not None:
            _unregister_callback(current_session[0])
        page.update()

    if session_id is not None:
        _register_callback(session_id)
        with _bg_lock:
            pending_reply = _bg_results.pop(session_id, None)
        if pending_reply is not None:
            already_there = (conv_history and conv_history[-1].get("role") == "assistant"
                             and conv_history[-1].get("content") == pending_reply)
            if not already_there:
                conv_history.append({"role": "assistant", "content": pending_reply})
                _add_ai_bubble(pending_reply)
        else:
            with _sessions_meta_lock:
                worker_running = session_id in _pending_sessions
            if worker_running:
                is_typing[0] = True
                _set_input_enabled(False)
                if typing_ind not in messages_col.controls:
                    messages_col.controls.append(typing_ind)

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ---------------------------------------------------------------------------
# Dashboard screen — professional redesign
# ---------------------------------------------------------------------------

def _stat_card(label: str, value: str, subtitle: str = "",
               value_color=ft.Colors.WHITE, icon: str = "",
               accent_color: str = "#334155") -> ft.Control:
    """A polished stat tile with icon accent strip."""
    controls = [
        ft.Row(spacing=8, controls=[
            ft.Text(icon, size=18) if icon else ft.Container(),
            ft.Text(label, size=12, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
        ]),
        ft.Text(value, size=21, weight=ft.FontWeight.BOLD, color=value_color),
    ]
    if subtitle:
        controls.append(
            ft.Text(subtitle, size=10, color=ft.Colors.with_opacity(0.42, ft.Colors.ON_SURFACE))
        )
    return ft.Card(
        elevation=2,
        content=ft.Container(
            padding=ft.Padding(left=14, right=14, top=12, bottom=12),
            content=ft.Column(spacing=4, controls=controls),
            border=ft.border.Border(left=ft.BorderSide(3, accent_color)),
        ),
    )


def _budget_progress_row(category: str, spent: float, limit: float,
                         peso_fn) -> ft.Control:
    """A single budget progress bar item."""
    pct = min(spent / limit, 1.0) if limit > 0 else 0.0
    pct_display = pct * 100

    if pct_display >= 100:
        bar_color = ft.Colors.RED_400
        status_icon = "🔴"
    elif pct_display >= 80:
        bar_color = ft.Colors.ORANGE_400
        status_icon = "🟠"
    elif pct_display >= 50:
        bar_color = ft.Colors.YELLOW_400
        status_icon = "🟡"
    else:
        bar_color = ft.Colors.GREEN_400
        status_icon = "🟢"

    return ft.Column(spacing=5, controls=[
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=6, controls=[
                    ft.Text(status_icon, size=12, color=bar_color),
                    ft.Text(category[:28], size=12, weight=ft.FontWeight.W_500),
                ]),
                ft.Text(f"{peso_fn(spent)} / {peso_fn(limit)}",
                        size=11, color=ft.Colors.with_opacity(0.62, ft.Colors.ON_SURFACE)),
            ],
        ),
        ft.ProgressBar(
            value=pct,
            color=bar_color,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            border_radius=5,
            height=8,
        ),
    ])


def _section_card(
    title: str,
    subtitle: str,
    *,
    icon,
    accent_color: str,
    content: ft.Control,
) -> ft.Control:
    return ft.Card(
        elevation=2,
        content=ft.Container(
            padding=ft.Padding(left=16, right=16, top=14, bottom=14),
            border_radius=18,
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
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=17,
                                bgcolor=ft.Colors.with_opacity(0.14, accent_color),
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(icon, size=18, color=accent_color),
                            ),
                            ft.Column(
                                spacing=2,
                                expand=True,
                                controls=[
                                    ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        subtitle,
                                        size=11,
                                        color=ft.Colors.with_opacity(0.48, ft.Colors.ON_SURFACE),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    content,
                ],
            ),
        ),
    )


def _build_cashflow_chart(monthly_rows: list[tuple[str, float, float]]) -> str | None:
    if not monthly_rows:
        return None

    labels = [label for label, _, _ in monthly_rows]
    income = [inc for _, inc, _ in monthly_rows]
    expense = [exp for _, _, exp in monthly_rows]
    net = [inc - exp for inc, exp in zip(income, expense)]
    x = np.arange(len(labels))

    bg = "#0f172a"
    fig, ax = plt.subplots(figsize=(5.2, 3.2), facecolor=bg)
    ax.set_facecolor(bg)

    width = 0.34
    ax.bar(x - width / 2, income, width=width, color="#22c55e", label="Income", zorder=3)
    ax.bar(x + width / 2, expense, width=width, color="#fb923c", label="Spend", zorder=3)
    ax.plot(x, net, color="#e2e8f0", marker="o", linewidth=1.8, label="Net", zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="#94a3b8", fontsize=8)
    ax.tick_params(axis="y", colors="#64748b", labelsize=7.5, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", alpha=0.10, color="#334155", linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.legend(loc="upper left", frameon=False, fontsize=7.5, labelcolor="white")
    ax.set_title("Income vs Spend", color="white", fontsize=11, fontweight="bold", pad=10)

    fig.tight_layout(pad=1.1)
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def _build_weekday_chart(weekday_rows: list[tuple[str, float]]) -> str | None:
    if not weekday_rows or not any(value > 0 for _, value in weekday_rows):
        return None

    labels = [label for label, _ in weekday_rows]
    values = [value for _, value in weekday_rows]
    x = np.arange(len(labels))
    peak_idx = int(np.argmax(values))

    bg = "#0f172a"
    fig, ax = plt.subplots(figsize=(5.0, 2.9), facecolor=bg)
    ax.set_facecolor(bg)

    colors = ["#38bdf8" if idx != peak_idx else "#f59e0b" for idx in range(len(labels))]
    ax.bar(x, values, color=colors, width=0.56, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="#94a3b8", fontsize=8)
    ax.tick_params(axis="y", colors="#64748b", labelsize=7.5, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", alpha=0.10, color="#334155", linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title("Spending Rhythm by Weekday", color="white", fontsize=11, fontweight="bold", pad=10)

    fig.tight_layout(pad=1.0)
    b64 = _fig_to_b64(fig)
    plt.close(fig)
    return b64


def _chart_card(
    title: str,
    subtitle: str,
    *,
    icon,
    accent_color: str,
    b64: str | None,
    placeholder: str,
    image_height: int = 220,
) -> ft.Control:
    return _section_card(
        title,
        subtitle,
        icon=icon,
        accent_color=accent_color,
        content=(
            ft.Container(
                height=image_height,
                alignment=ft.Alignment(0, 0),
                content=ft.Image(
                    src=f"data:image/png;base64,{b64}",
                    fit=ft.BoxFit.FIT_WIDTH,
                    expand=True,
                ),
            )
            if b64 else
            ft.Container(
                height=image_height,
                alignment=ft.Alignment(0, 0),
                content=ft.Text(
                    placeholder,
                    size=13,
                    color=ft.Colors.with_opacity(0.46, ft.Colors.ON_SURFACE),
                    text_align=ft.TextAlign.CENTER,
                ),
            )
        ),
    )


_CARD_CONTENT_HEIGHT = 260  # Fixed height for all card body areas


def _leaderboard_card(expense_map: dict[str, float], month_total: float, peso_fn) -> ft.Control:
    rows = sorted(expense_map.items(), key=lambda item: item[1], reverse=True)
    if not rows:
        body = ft.Container(
            height=_CARD_CONTENT_HEIGHT,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(
                "Add a few expenses to unlock the spending leaderboard.",
                size=12,
                color=ft.Colors.with_opacity(0.46, ft.Colors.ON_SURFACE),
                text_align=ft.TextAlign.CENTER,
            ),
        )
    else:
        header = ft.Row(
            controls=[
                ft.Container(expand=1, content=ft.Text("Rank", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=5, content=ft.Text("Category", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=2, alignment=ft.Alignment(1, 0), content=ft.Text("Share", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text("Amount", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
            ],
        )
        table_rows: list[ft.Control] = []
        for idx, (category, amount) in enumerate(rows, start=1):
            share = (amount / month_total * 100) if month_total else 0.0
            table_rows.append(
                ft.Container(
                    padding=ft.Padding(left=10, right=10, top=10, bottom=10),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    content=ft.Row(
                        controls=[
                            ft.Container(expand=1, content=ft.Text(f"{idx}", size=12, weight=ft.FontWeight.W_600, color="#38bdf8")),
                            ft.Container(expand=5, content=ft.Text(category, size=12, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                            ft.Container(expand=2, alignment=ft.Alignment(1, 0), content=ft.Text(f"{share:.0f}%", size=11, color=ft.Colors.with_opacity(0.66, ft.Colors.ON_SURFACE))),
                            ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(peso_fn(amount), size=12, weight=ft.FontWeight.W_600)),
                        ],
                    ),
                )
            )
        body = ft.Column(
            spacing=0,
            controls=[
                header,
                ft.Container(height=8),
                ft.Column(
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    height=_CARD_CONTENT_HEIGHT - 28,
                    controls=table_rows,
                ),
            ],
        )

    return _section_card(
        "Spending Leaderboard",
        "A table view of the categories driving this month.",
        icon=ft.Icons.TABLE_ROWS_ROUNDED,
        accent_color="#38bdf8",
        content=body,
    )


def _cashflow_table_card(monthly_rows: list[tuple[str, float, float]], peso_fn) -> ft.Control:
    if not monthly_rows:
        body = ft.Container(
            height=_CARD_CONTENT_HEIGHT,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(
                "Cashflow history will appear after you log a few weeks of activity.",
                size=12,
                color=ft.Colors.with_opacity(0.46, ft.Colors.ON_SURFACE),
                text_align=ft.TextAlign.CENTER,
            ),
        )
    else:
        header = ft.Row(
            controls=[
                ft.Container(expand=2, content=ft.Text("Month", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text("Income", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text("Spend", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
                ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text("Net", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE))),
            ],
        )
        data_rows: list[ft.Control] = []
        for label, income, expense in monthly_rows:
            net = income - expense
            data_rows.append(
                ft.Container(
                    padding=ft.Padding(left=10, right=10, top=10, bottom=10),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                    content=ft.Row(
                        controls=[
                            ft.Container(expand=2, content=ft.Text(label, size=12, weight=ft.FontWeight.W_500)),
                            ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(peso_fn(income), size=12, color=ft.Colors.GREEN_300)),
                            ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(peso_fn(expense), size=12, color=ft.Colors.ORANGE_300)),
                            ft.Container(expand=3, alignment=ft.Alignment(1, 0), content=ft.Text(peso_fn(net), size=12, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_300 if net >= 0 else ft.Colors.RED_300)),
                        ],
                    ),
                )
            )
        body = ft.Column(
            spacing=0,
            controls=[
                header,
                ft.Container(height=8),
                ft.Column(
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    height=_CARD_CONTENT_HEIGHT - 28,
                    controls=data_rows,
                ),
            ],
        )

    return _section_card(
        "Cashflow Table",
        "Month-by-month income, spending, and net summary.",
        icon=ft.Icons.GRID_VIEW_ROUNDED,
        accent_color="#22c55e",
        content=body,
    )


def dashboard_screen(page: ft.Page, on_data_changed) -> ft.Control:
    db.init_chat_tables()

    currency_code = db.get_currency()
    peso = make_peso(currency_code)
    month = now_month()
    today = date.today()
    balance = db.get_balance()
    ml_engine.check_and_retrain()          # retrain if schedule says it's time
    ml_forecast = ml_engine.get_forecast_summary()
    ml_anomalies = ml_engine.detect_anomalies()
    expense_map = db.get_month_expense_summary(month)
    month_total = sum(expense_map.values())
    month_income = db.get_month_income_total(month)
    net_cashflow = month_income - month_total
    biggest_category = max(expense_map, key=lambda k: expense_map[k]) if expense_map else "No category yet"
    biggest_value = expense_map.get(biggest_category, 0.0)
    savings_rate = (net_cashflow / month_income * 100) if month_income > 0 else 0.0

    # Budget limits for progress bars
    budget_limits = db.get_budget_limits()

    # Upcoming recurring bills — all active recurring, sorted by next_date
    upcoming = db.get_upcoming_recurring(days=365 * 10)

    recent_transactions = db.get_transactions(date_from=(today - timedelta(days=210)).isoformat())
    analytics_rows = [
        {
            "date": txn.txn_date,
            "txn_type": txn.txn_type,
            "amount": txn.amount,
            "category": txn.category,
        }
        for txn in recent_transactions
    ]
    analytics_df = pd.DataFrame(analytics_rows)
    monthly_cashflow: list[tuple[str, float, float]] = []
    weekday_spend: list[tuple[str, float]] = []

    if not analytics_df.empty:
        analytics_df["date"] = pd.to_datetime(analytics_df["date"])
        analytics_df["month"] = analytics_df["date"].dt.to_period("M").astype(str)
        month_anchor = pd.Timestamp(today.replace(day=1))
        month_order = [
            (month_anchor - pd.DateOffset(months=offset)).strftime("%Y-%m")
            for offset in range(5, -1, -1)
        ]
        grouped = analytics_df.pivot_table(
            index="month",
            columns="txn_type",
            values="amount",
            aggfunc="sum",
            fill_value=0.0,
        ).reindex(month_order, fill_value=0.0)

        for month_key in month_order:
            label = pd.to_datetime(f"{month_key}-01").strftime("%b")
            income_val = float(grouped.loc[month_key].get("income", 0.0)) if month_key in grouped.index else 0.0
            expense_val = float(grouped.loc[month_key].get("expense", 0.0)) if month_key in grouped.index else 0.0
            monthly_cashflow.append((label, income_val, expense_val))

        expense_df = analytics_df[analytics_df["txn_type"] == "expense"].copy()
        if not expense_df.empty:
            expense_df["weekday"] = expense_df["date"].dt.dayofweek
            weekday_totals = expense_df.groupby("weekday")["amount"].sum()
            weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            weekday_spend = [
                (weekday_labels[idx], float(weekday_totals.get(idx, 0.0)))
                for idx in range(7)
            ]

    # Charts — generated once
    donut_b64 = _build_donut_chart(expense_map)
    line_b64 = _build_area_line_chart(db.get_expenses_last_days(30))
    bar_b64 = _build_bar_chart(expense_map)
    cashflow_b64 = _build_cashflow_chart(monthly_cashflow)
    weekday_b64 = _build_weekday_chart(weekday_spend)

    # ── Build AI financial context ──────────────────────────────────────────
    today_str = today.isoformat()

    budget_lines: list[str] = []
    for budget in budget_limits:
        spent = expense_map.get(budget.category, 0.0)
        pct = (spent / budget.monthly_limit * 100) if budget.monthly_limit > 0 else 0
        status = ("Exceeded" if pct >= 100 else "Warning" if pct >= 80
                  else "On Track" if pct >= 50 else "Good")
        budget_lines.append(
            f"  • {budget.category}: limit={peso(budget.monthly_limit)}, "
            f"spent={peso(spent)}, {pct:.0f}% used, status={status}"
        )

    recent_txns = db.get_transactions()[:20]
    txn_lines = [
        f"  • [{t.txn_date}] {'+' if t.txn_type=='income' else '-'}{peso(t.amount)} | {t.category}"
        for t in recent_txns
    ]
    recurring = db.get_recurring_transactions()
    rec_lines = [
        f"  • {r.category}: {'+' if r.txn_type=='income' else '-'}{peso(r.amount)}, "
        f"{r.frequency}, next {r.next_date}, {'active' if r.active else 'paused'}"
        for r in recurring
    ]
    starting_balance = db.get_starting_balance()
    api_key = db.get_anthropic_api_key()

    financial_context = (
        f"Today: {today_str} | Currency: {currency_code}\n"
        f"Balance: {peso(balance)} | Starting: {peso(starting_balance)}\n"
        f"Income this month: {peso(month_income)} | Spent: {peso(month_total)} | Net: {peso(net_cashflow)}\n\n"
        f"=== SPENDING BY CATEGORY ===\n"
        + "\n".join(f"  • {cat}: {peso(amt)}" for cat, amt in expense_map.items())
        + f"\n\n=== BUDGET LIMITS ===\n{chr(10).join(budget_lines) or '  (none)'}\n"
        f"\n=== RECENT TRANSACTIONS ===\n{chr(10).join(txn_lines) or '  (none)'}\n"
        f"\n=== RECURRING ===\n{chr(10).join(rec_lines) or '  (none)'}"
    )

    def open_ai_chat(_):
        _open_ai_chat(page, financial_context, api_key, None, [])

    def open_history(_):
        _open_history_dialog(page, financial_context, api_key)

    def open_add_income(_):
        from ui.transactions_screen import _income_dialog
        _income_dialog(page, lambda **_: on_data_changed())

    # ── BALANCE HERO CARD ───────────────────────────────────────────────────
    balance_card = ft.Card(
        elevation=6,
        content=ft.Container(
            padding=ft.Padding(left=20, right=20, top=18, bottom=18),
            border_radius=22,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=["#082f49", "#0f766e", "#0284c7"],
            ),
            content=ft.Column(spacing=0, controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(spacing=6, controls=[
                            ft.Text("Current Balance", color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                                    size=13, weight=ft.FontWeight.W_500),
                            ft.Text(peso(balance), color=ft.Colors.WHITE, size=36,
                                    weight=ft.FontWeight.BOLD),
                        ]),
                        ft.FilledButton(
                            "+ Income", icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                            on_click=open_add_income,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.WHITE),
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=12),
                            ),
                        ),
                    ],
                ),
                ft.Container(height=14),
                ft.Row(spacing=0, controls=[
                    ft.Container(
                        expand=True,
                        content=ft.Column(spacing=2, controls=[
                            ft.Text("↑ Income", size=11,
                                    color=ft.Colors.with_opacity(0.65, ft.Colors.WHITE)),
                            ft.Text(peso(month_income), size=14, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE),
                        ]),
                    ),
                    ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(left=16, right=0, top=0, bottom=0),
                        content=ft.Column(spacing=2, controls=[
                            ft.Text("↓ Spent", size=11,
                                    color=ft.Colors.with_opacity(0.65, ft.Colors.WHITE)),
                            ft.Text(peso(month_total), size=14, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE),
                        ]),
                    ),
                    ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding(left=16, right=0, top=0, bottom=0),
                        content=ft.Column(spacing=2, controls=[
                            ft.Text("Savings Rate", size=11,
                                    color=ft.Colors.with_opacity(0.65, ft.Colors.WHITE)),
                            ft.Text(f"{savings_rate:.0f}%", size=14,
                                    weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ]),
                    ),
                ]),
            ]),
        ),
    )

    # ── STAT TILES ──────────────────────────────────────────────────────────
    stat_row = ft.ResponsiveRow(spacing=8, controls=[
        ft.Container(col={"xs": 6, "md": 3}, content=_stat_card(
            "Net Cashflow",
            ("+" if net_cashflow >= 0 else "") + peso(net_cashflow),
            "income minus expenses",
            value_color=ft.Colors.GREEN_400 if net_cashflow >= 0 else ft.Colors.RED_400,
            icon="💹", accent_color="#22c55e" if net_cashflow >= 0 else "#ef4444",
        )),
        ft.Container(col={"xs": 6, "md": 3}, content=_stat_card(
            "This Month's Spend",
            peso(month_total),
            "total expenses",
            value_color=ft.Colors.ORANGE_300,
            icon="💸", accent_color="#f97316",
        )),
        ft.Container(col={"xs": 6, "md": 3}, content=_stat_card(
            "Top Category",
            biggest_category[:15],
            peso(biggest_value),
            value_color=ft.Colors.CYAN_300,
            icon="📊", accent_color="#38bdf8",
        )),
        ft.Container(col={"xs": 6, "md": 3}, content=_stat_card(
            "Budget Limits",
            str(len(budget_limits)),
            f"{sum(1 for b in budget_limits if expense_map.get(b.category, 0) >= b.monthly_limit)} exceeded",
            value_color=ft.Colors.PURPLE_300,
            icon="🎯", accent_color="#a78bfa",
        )),
    ])

    # ── AI ADVISOR CARD ──────────────────────────────────────────────────────
    ai_card = ft.Card(
        elevation=3,
        content=ft.Container(
            padding=ft.Padding(left=16, right=12, top=14, bottom=14),
            border_radius=14,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                colors=[ft.Colors.with_opacity(0.12, "#38bdf8"),
                        ft.Colors.with_opacity(0.04, "#14b8a6")],
            ),
            border=ft.border.all(1, ft.Colors.with_opacity(0.15, "#38bdf8")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(spacing=12, expand=True, controls=[
                        ft.Container(
                            width=42, height=42, border_radius=21,
                            gradient=ft.LinearGradient(
                                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                                colors=["#0ea5e9", "#14b8a6"],
                            ),
                            alignment=ft.Alignment(0, 0),
                            content=ft.Text("AI", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ),
                        ft.Column(spacing=2, expand=True, controls=[
                            ft.Text("AI Finance Advisor", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text("Ask anything about your spending & savings",
                                    size=11, color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)),
                        ]),
                    ]),
                    ft.Row(spacing=6, controls=[
                        ft.IconButton(icon=ft.Icons.HISTORY, icon_color="#94a3b8",
                                      tooltip="Chat History", on_click=open_history),
                        ft.FilledButton(
                            "Chat", icon=ft.Icons.AUTO_AWESOME,
                            on_click=open_ai_chat,
                            style=ft.ButtonStyle(
                                bgcolor="#0ea5e9", color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                        ),
                    ]),
                ],
            ),
        ),
    )

    # ── BUDGET PROGRESS SECTION ──────────────────────────────────────────────
    budget_controls: list[ft.Control] = []
    for b in budget_limits[:5]:
        spent = expense_map.get(b.category, 0.0)
        limit = b.monthly_limit
        pct = min(spent / limit, 1.0) if limit > 0 else 0.0
        pct_pct = pct * 100

        if pct_pct >= 100:
            bar_color = "#ef4444"; status_icon = "🔴"
        elif pct_pct >= 80:
            bar_color = "#f97316"; status_icon = "🟠"
        elif pct_pct >= 50:
            bar_color = "#facc15"; status_icon = "🟡"
        else:
            bar_color = "#22c55e"; status_icon = "🟢"

        budget_controls.append(
            ft.Column(spacing=4, controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Text(status_icon, size=12),
                        ft.Text(b.category[:24], size=12, weight=ft.FontWeight.W_500),
                    ]),
                    ft.Text(f"{peso(spent)} / {peso(limit)}",
                            size=11, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)),
                ]),
                ft.Stack(controls=[
                    ft.Container(height=7, border_radius=4,
                                 bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                    ft.Container(height=7, border_radius=4, bgcolor=bar_color,
                                 expand=False),
                ]),
                ft.Container(
                    ft.Stack(controls=[
                        ft.Container(height=7, border_radius=4,
                                     bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                        ft.Container(height=7, border_radius=4, bgcolor=bar_color,
                                     width=None),
                    ]),
                ),
            ])
        )

    # Simpler, reliable budget progress bar using ProgressBar
    budget_section_controls: list[ft.Control] = []
    for b in budget_limits:
        spent = expense_map.get(b.category, 0.0)
        limit = b.monthly_limit
        pct = min(spent / limit, 1.0) if limit > 0 else 0.0
        pct_pct = pct * 100

        if pct_pct >= 100:
            bar_color = ft.Colors.RED_400; status_icon = "🔴"
        elif pct_pct >= 80:
            bar_color = ft.Colors.ORANGE_400; status_icon = "🟠"
        elif pct_pct >= 50:
            bar_color = ft.Colors.YELLOW_400; status_icon = "🟡"
        else:
            bar_color = ft.Colors.GREEN_400; status_icon = "🟢"

        budget_section_controls.append(
            ft.Column(spacing=5, controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Row(spacing=5, controls=[
                        ft.Text(status_icon, size=11),
                        ft.Text(b.category[:26], size=12, weight=ft.FontWeight.W_500),
                    ]),
                    ft.Text(f"{peso(spent)} / {peso(limit)}",
                            size=11, color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)),
                ]),
                ft.ProgressBar(value=pct, color=bar_color,
                               bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
                               border_radius=4, height=7),
            ])
        )

    budget_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=ft.Padding(left=16, right=16, top=14, bottom=14),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=8, controls=[
                                ft.Text("🎯", size=16),
                                ft.Text("Budget Progress", weight=ft.FontWeight.BOLD, size=14),
                            ]),
                            ft.Text(f"{len(budget_limits)} limits",
                                    size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                        ],
                    ),
                    ft.Column(
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                        height=_CARD_CONTENT_HEIGHT,
                        controls=budget_section_controls if budget_section_controls else [
                            ft.Text("No budget limits set yet. Add them in the Budgets tab.",
                                    size=12, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))
                        ],
                    ),
                ],
            ),
        ),
    ) if budget_limits else None

    # ── UPCOMING BILLS ──────────────────────────────────────────────────────
    upcoming_controls: list[ft.Control] = []
    for u in upcoming:
        days_away = u["days_away"]
        if days_away < 0:
            chip_color = ft.Colors.RED_400; chip_text = "OVERDUE"
        elif days_away == 0:
            chip_color = ft.Colors.ORANGE_400; chip_text = "TODAY"
        elif days_away == 1:
            chip_color = ft.Colors.YELLOW_600; chip_text = "TOMORROW"
        else:
            chip_color = ft.Colors.BLUE_400; chip_text = f"in {days_away}d"

        sign = "+" if u["txn_type"] == "income" else "-"
        upcoming_controls.append(
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(spacing=1, expand=True, controls=[
                        ft.Text(u["category"][:24], size=12, weight=ft.FontWeight.W_500),
                        ft.Text(u["description"][:30] if u["description"] else u["frequency"],
                                size=10, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    ]),
                    ft.Row(spacing=8, controls=[
                        ft.Text(f"{sign}{peso(u['amount'])}", size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_400 if u["txn_type"] == "income" else ft.Colors.ORANGE_300),
                        ft.Container(
                            padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.18, chip_color),
                            content=ft.Text(chip_text, size=10, weight=ft.FontWeight.BOLD,
                                            color=chip_color),
                        ),
                    ]),
                ],
            )
        )

    upcoming_card = ft.Card(
        elevation=2,
        content=ft.Container(
            padding=ft.Padding(left=16, right=16, top=14, bottom=14),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text("📅", size=16),
                        ft.Text("Upcoming Bills", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(f"({len(upcoming_controls)} active)",
                                size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    ]),
                    ft.Column(
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                        height=_CARD_CONTENT_HEIGHT,
                        controls=upcoming_controls if upcoming_controls else [
                            ft.Text("No active recurring bills found. 🎉",
                                    size=12, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))
                        ],
                    ),
                ],
            ),
        ),
    ) if True else None  # always show

    # ── CHART CARDS ──────────────────────────────────────────────────────────
    def _legacy_chart_card(b64: str | None, title: str, placeholder: str) -> ft.Control:
        return ft.Card(
            elevation=2,
            content=ft.Container(
                padding=ft.Padding(left=12, right=12, top=12, bottom=8),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Image(src=f"data:image/png;base64,{b64}",
                                 fit=ft.BoxFit.CONTAIN, expand=True)
                        if b64 else
                        ft.Container(
                            height=120,
                            alignment=ft.Alignment(0, 0),
                            content=ft.Text(placeholder, size=13,
                                            color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE),
                                            text_align=ft.TextAlign.CENTER),
                        )
                    ],
                ),
            ),
        )

    # ── ASSEMBLE DASHBOARD ───────────────────────────────────────────────────
    sections: list[ft.Control] = [
        balance_card,
        stat_row,
        ai_card,
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12, "lg": 7},
                    content=_chart_card(
                        "Daily Spending Trend",
                        "The last 30 days of expense activity.",
                        icon=ft.Icons.SHOW_CHART_ROUNDED,
                        accent_color="#38bdf8",
                        b64=line_b64,
                        placeholder="No trend data yet.",
                        image_height=240,
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "lg": 5},
                    content=_chart_card(
                        "Cashflow Pulse",
                        "Income, spending, and net movement across recent months.",
                        icon=ft.Icons.INSIGHTS_ROUNDED,
                        accent_color="#22c55e",
                        b64=cashflow_b64,
                        placeholder="No cashflow history yet.",
                        image_height=240,
                    ),
                ),
            ],
        ),
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=_chart_card(
                        "Spending by Category",
                        "A distribution view of where the month is going.",
                        icon=ft.Icons.DONUT_LARGE_ROUNDED,
                        accent_color="#8b5cf6",
                        b64=donut_b64,
                        placeholder="No expense data yet.",
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=_chart_card(
                        "Weekday Rhythm",
                        "See which days tend to attract the most spending.",
                        icon=ft.Icons.CALENDAR_VIEW_WEEK_ROUNDED,
                        accent_color="#f59e0b",
                        b64=weekday_b64,
                        placeholder="Need more expense history to map your weekday rhythm.",
                    ),
                ),
            ],
        ),
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=_chart_card(
                        "Top Categories",
                        "Your highest-spend categories at a glance.",
                        icon=ft.Icons.BAR_CHART_ROUNDED,
                        accent_color="#06b6d4",
                        b64=bar_b64,
                        placeholder="No expense data yet.",
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=_leaderboard_card(expense_map, month_total, peso),
                ),
            ],
        ),
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=budget_card or ft.Container(),
                ),
                ft.Container(
                    col={"xs": 12, "md": 6},
                    content=upcoming_card or ft.Container(),
                ),
            ],
        ),
        
        # Add your ML cards here
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

        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    col={"xs": 12},
                    content=_cashflow_table_card(monthly_cashflow, peso),
                ),
            ],
        ),
    ]

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=sections,
    )
