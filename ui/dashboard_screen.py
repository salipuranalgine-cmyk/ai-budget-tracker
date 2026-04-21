from __future__ import annotations

import base64
import threading
from io import BytesIO

import flet as ft
import matplotlib.pyplot as plt
import pandas as pd

import database as db
from ai_insights import chat_with_ai
from ui.constants import now_month, make_peso


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


# ---------------------------------------------------------------------------
# Chat bubble helpers
# bubble_w = pixel width passed in from dialog so Text wraps correctly
# ---------------------------------------------------------------------------

def _ai_bubble(text: str, bubble_w: int) -> ft.Control:
    return ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[
            ft.Text("🤖", size=18),
            ft.Container(
                width=bubble_w,
                content=ft.Text(text, selectable=True, size=13, color=ft.Colors.WHITE),
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                bgcolor="#1e293b",
                border_radius=ft.BorderRadius(top_left=4, top_right=14, bottom_left=14, bottom_right=14),
                margin=ft.Margin(bottom=10, top=0, left=6, right=0),
            ),
        ],
    )


def _user_bubble(text: str, bubble_w: int) -> ft.Control:
    return ft.Row(
        alignment=ft.MainAxisAlignment.END,
        controls=[
            ft.Container(expand=True),   # left spacer — keeps bubble from stretching
            ft.Container(
                width=bubble_w,
                content=ft.Text(text, selectable=True, size=13, color=ft.Colors.WHITE),
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                bgcolor="#0369a1",
                border_radius=ft.BorderRadius(top_left=14, top_right=4, bottom_left=14, bottom_right=14),
                margin=ft.Margin(bottom=10, top=0, left=0, right=0),
            ),
        ],
    )


def _generate_session_title(user_message: str, ai_reply: str) -> str:
    """Generate a smart session title based on conversation content."""
    user_lower = user_message.lower()
    ai_lower = ai_reply.lower()
    
    # Common conversation types and budget topics
    topics = {
        # Greetings and General Conversations
        "Casual Greeting": ["hello", "hi", "hey", "how are you", "good morning", "good afternoon", "good evening"],
        "Introduction": ["my name is", "i'm", "i am", "introduction", "about me"],
        "Small Talk": ["how's your day", "what's up", "what are you doing", "nice to meet you"],
        
        # Budget Topics
        "Budget Planning": ["budget", "plan", "planning", "create budget", "monthly budget"],
        "Savings Goals": ["save", "saving", "goal", "goals", "set aside", "emergency fund"],
        "Expense Analysis": ["spending", "expenses", "expense", "where did i spend", "track expenses"],
        "Income Questions": ["income", "salary", "earn", "revenue", "make money"],
        "Investment": ["invest", "investment", "stocks", "crypto", "portfolio"],
        "Debt Management": ["debt", "loan", "credit card", "pay off", "borrow"],
        "Monthly Review": ["month", "review", "summary", "report", "overview"],
        "Category Spending": ["category", "food", "transport", "utilities", "entertainment"],
        "Financial Advice": ["advice", "help", "should i", "recommend", "suggest"],
        
        # Help and Support
        "Help Request": ["help", "can you", "how do i", "what is", "explain", "tell me"],
        "Questions": ["question", "what", "when", "where", "why", "how", "which"],
        "General Chat": ["chat", "talk", "conversation", "discuss"],
    }
    
    # Check for topic matches in user message
    for topic, keywords in topics.items():
        if any(keyword in user_lower for keyword in keywords):
            # Extract key info for more specific title
            if topic == "Category Spending":
                for category in ["food", "transport", "utilities", "entertainment", "shopping", "bills"]:
                    if category in user_lower:
                        return f"{category.title()} Spending"
            elif topic == "Monthly Review":
                # Try to extract month info
                months = ["january", "february", "march", "april", "may", "june",
                         "july", "august", "september", "october", "november", "december"]
                for month in months:
                    if month in user_lower:
                        return f"{month.title()} Review"
            return topic
    
    # Fallback: use first meaningful words from user message
    words = user_message.split()
    if len(words) >= 3:
        title = " ".join(words[:3])
    else:
        title = user_message
    
    return title[:55].rstrip() + ("..." if len(title) > 55 else "")


def _typing_bubble() -> ft.Control:
    return ft.Row(
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text("🤖", size=18),
            ft.Container(
                content=ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.ProgressRing(width=12, height=12, stroke_width=2),
                        ft.Text("AI is thinking…", size=12, italic=True,
                                color=ft.Colors.with_opacity(0.6, ft.Colors.WHITE)),
                    ],
                ),
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                bgcolor="#1e293b",
                border_radius=ft.BorderRadius(top_left=4, top_right=14, bottom_left=14, bottom_right=14),
                margin=ft.Margin(bottom=10, top=0, left=6, right=0),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# History dialog
# ---------------------------------------------------------------------------

def _open_history_dialog(page: ft.Page, financial_context: str, api_key: str) -> None:
    sessions_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=6)
    storage_text = ft.Text("", size=11, color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE))

    # Multi-select state
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
            width=520,
            height=480,
            content=ft.Column(
                expand=True,
                spacing=8,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        storage_text,
                        ft.Row(spacing=4, controls=[
                            ft.TextButton("+ New Chat", icon=ft.Icons.ADD, on_click=lambda _: _new_chat()),
                            ft.TextButton(
                                "🗑️ Clear All",
                                icon=ft.Icons.DELETE_FOREVER,
                                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                                on_click=lambda _: _confirm_clear_all(),
                            ),
                        ]),
                    ]),
                    ft.Divider(height=1),
                    ft.Container(expand=True, content=sessions_col),
                    # Bulk actions row
                    ft.Row(
                        visible=False,
                        controls=[
                            ft.TextButton("Select All", on_click=lambda _: _select_all()),
                            ft.TextButton("Deselect All", on_click=lambda _: _deselect_all()),
                            ft.ElevatedButton(          # still using ElevatedButton for now (warning is harmless)
                                "Delete Selected",
                                icon=ft.Icons.DELETE,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                                on_click=lambda _: _confirm_delete_selected(),
                            ),
                        ],
                        key="bulk_actions_row",
                    ),
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
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("No conversations yet.\nStart a new chat!", 
                                    text_align=ft.TextAlign.CENTER,
                                    color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                )
            )
            _update_bulk_visibility()
            page.update()
            return

        for s in sessions:
            sid = s["id"]
            preview = (s["preview"] or "No messages yet")[:85]

            checkbox = ft.Checkbox(value=False, on_change=lambda e, sid=sid: _toggle_select(sid, e.control.value))

            card = ft.Card(
                content=ft.Container(
                    padding=12,
                    content=ft.Row(
                        controls=[
                            checkbox,
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.Text(s["title"], weight=ft.FontWeight.W_600, size=13, expand=True),
                                            ft.IconButton(
                                                icon=ft.Icons.EDIT,
                                                icon_size=16,
                                                icon_color=ft.Colors.BLUE_300,
                                                tooltip="Edit title",
                                                on_click=lambda _, sid=sid, current_title=s["title"]: _edit_title(sid, current_title),
                                            ),
                                        ],
                                    ),
                                    ft.Text(preview, size=11, color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)),
                                    ft.Text(f"{s['created_at'][:16]} · {s['msg_count']} messages",
                                            size=10, color=ft.Colors.with_opacity(0.4, ft.Colors.ON_SURFACE)),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_300,
                                tooltip="Delete this chat",
                                on_click=lambda _, sid=sid, title=s["title"]: _confirm_delete(sid, title),
                            ),
                        ],
                    ),
                    on_click=lambda _, sid=sid: _resume(sid),
                )
            )
            session_cards[sid] = card
            sessions_col.controls.append(card)

        _update_bulk_visibility()
        page.update()

    def _toggle_select(sid: int, checked: bool):
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
        bulk_row = next((c for c in dlg.content.content.controls if getattr(c, "key", None) == "bulk_actions_row"), None)
        if bulk_row:
            bulk_row.visible = len(selected_ids) > 0

    def _confirm_delete(sid: int, title: str):
        def _do_delete():
            db.delete_chat_session(sid)
            _refresh()

        confirm = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete conversation?"),
            content=ft.Text(f'"{title}" and all its messages will be permanently deleted.'),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Delete", style=ft.ButtonStyle(color=ft.Colors.RED_400),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(), _do_delete())),
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
            modal=True,
            title=ft.Text("Delete selected chats?"),
            content=ft.Text(f"{count} conversation(s) and all messages will be permanently deleted."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Delete All Selected",
                              style=ft.ButtonStyle(color=ft.Colors.RED_400),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(), _do_bulk_delete())),
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
            modal=True,
            title=ft.Text("🗑️ Wipe ALL chat history?"),
            content=ft.Text("This will permanently delete EVERY conversation and all messages.\n\nThis cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: (setattr(confirm, "open", False), page.update())),
                ft.TextButton("Yes, Clear Everything",
                              style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400, color=ft.Colors.WHITE),
                              on_click=lambda _: (setattr(confirm, "open", False), page.update(), _do_clear_all())),
            ],
        )
        page.overlay.append(confirm)
        confirm.open = True
        page.update()

    def _do_clear_all():
        db.delete_all_chat_sessions()
        _refresh()

    def _edit_title(session_id: int, current_title: str):
        title_field = ft.TextField(
            label="Session Title",
            value=current_title,
            autofocus=True,
            max_length=60,
        )
        
        edit_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Session Title", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=400,
                content=ft.Column(
                    tight=True,
                    spacing=14,
                    controls=[
                        ft.Text("Give your conversation a memorable name:", size=13),
                        title_field,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_edit_dialog()),
                ft.ElevatedButton(
                    "Save",
                    icon=ft.Icons.SAVE,
                    on_click=lambda _: _save_title(),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        def _close_edit_dialog():
            edit_dlg.open = False
            page.update()
        
        def _save_title():
            new_title = title_field.value.strip()
            if not new_title:
                page.snack_bar = ft.SnackBar(ft.Text("Title cannot be empty!"))
                page.snack_bar.open = True
                page.update()
                return
            
            db.update_chat_session_title(session_id, new_title)
            _close_edit_dialog()
            _refresh()
            
            page.snack_bar = ft.SnackBar(ft.Text("Title updated successfully!"))
            page.snack_bar.open = True
            page.update()
        
        page.overlay.append(edit_dlg)
        edit_dlg.open = True
        page.update()

    # Show the dialog
    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    _refresh()


# ---------------------------------------------------------------------------
# Main chat dialog
# ---------------------------------------------------------------------------

def _open_ai_chat(
    page: ft.Page,
    financial_context: str,
    api_key: str,
    session_id: int | None,
    history: list,
) -> None:
    # Auto-size dialog
    win_w = getattr(page, "window_width", None) or getattr(page, "width", None) or 900
    win_h = getattr(page, "window_height", None) or getattr(page, "height", None) or 700
    dlg_w = max(400, min(720, int(win_w * 0.82)))
    dlg_h = max(440, min(700, int(win_h * 0.80)))
    bubble_w = dlg_w - 90

    current_session = [session_id]
    conv_history = list(history)
    is_typing = [False]

    messages_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, auto_scroll=True)

    # Pre-populate existing history (for resumed chats)
    for msg in conv_history:
        if msg["role"] == "assistant":
            messages_col.controls.append(_ai_bubble(msg["content"], bubble_w))
        else:
            messages_col.controls.append(_user_bubble(msg["content"], bubble_w))

    # === NEW: For brand new chats, show friendly static welcome ===
    if not conv_history:
        welcome_msg = "Hi! How can I help you today with your budget?"
        messages_col.controls.append(_ai_bubble(welcome_msg, bubble_w))
        conv_history.append({"role": "assistant", "content": welcome_msg})

    input_field = ft.TextField(
        hint_text="Ask anything about your budget…",
        border_radius=24,
        border_color="#334155",
        focused_border_color="#0ea5e9",
        text_size=13,
        expand=True,
        multiline=False,
        on_submit=lambda e: _send(e.control.value),
    )

    send_btn = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED, icon_color="#0ea5e9",
        icon_size=22, tooltip="Send",
        on_click=lambda _: _send(input_field.value),
    )

    typing_ind = _typing_bubble()

    def _set_busy(busy: bool) -> None:
        is_typing[0] = busy
        send_btn.disabled = busy
        input_field.disabled = busy
        if busy:
            if typing_ind not in messages_col.controls:
                messages_col.controls.append(typing_ind)
        else:
            if typing_ind in messages_col.controls:
                messages_col.controls.remove(typing_ind)
        page.update()

    def _ensure_session() -> int:
        if current_session[0] is None:
            current_session[0] = db.create_chat_session("New Chat")
        return current_session[0]

    def _send(text: str) -> None:
        if is_typing[0]:
            return
        text = (text or "").strip()
        if not text:
            return

        input_field.value = ""
        messages_col.controls.append(_user_bubble(text, bubble_w))
        conv_history.append({"role": "user", "content": text})
        sid = _ensure_session()
        db.save_chat_message(sid, "user", text)
        _set_busy(True)

        def _worker():
            reply = chat_with_ai(list(conv_history), financial_context, api_key)
            conv_history.append({"role": "assistant", "content": reply})
            db.save_chat_message(sid, "assistant", reply)

            # Auto-update session title with smart naming on first real reply
            # Check if this is the first real user message (not counting welcome message)
            user_messages = [msg for msg in conv_history if msg["role"] == "user"]
            if len(user_messages) == 1:  # first real user message
                # Get the first user message (not the welcome)
                first_user_msg = user_messages[0]["content"]
                title = _generate_session_title(first_user_msg, reply)
                db.update_chat_session_title(sid, title)

            _set_busy(False)
            messages_col.controls.append(_ai_bubble(reply, bubble_w))
            page.update()

        threading.Thread(target=_worker, daemon=True).start()

    def _open_history(_):
        _close()
        _open_history_dialog(page, financial_context, api_key)

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(spacing=8, expand=True, controls=[
                    ft.Text("🤖", size=22),
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
            width=dlg_w,
            height=dlg_h,
            content=ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    ft.Container(expand=True, content=messages_col,
                                 padding=ft.Padding(left=4, right=4, top=4, bottom=4)),
                    ft.Divider(height=1, color="#1e293b"),
                    ft.Container(
                        padding=ft.Padding(left=8, right=8, top=8, bottom=8),
                        content=ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                       controls=[input_field, send_btn]),
                    ),
                ],
            ),
        ),
        actions=[],
    )

    def _close():
        dlg.open = False
        page.update()

    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ---------------------------------------------------------------------------
# Dashboard screen
# ---------------------------------------------------------------------------

def dashboard_screen(page: ft.Page, on_data_changed) -> ft.Control:
    db.init_chat_tables()  # idempotent

    currency_code = db.get_currency()
    peso = make_peso(currency_code)
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

    financial_context = (
        f"Currency: {currency_code}\n"
        f"Month: {month}\n"
        f"Current balance: {peso(balance)}\n"
        f"Total spent this month: {peso(month_total)}\n"
        f"Income this month: {peso(month_income)}\n"
        f"Net cashflow: {peso(net_cashflow)}\n"
        f"Biggest spending category: {biggest_category} ({peso(biggest_value)})\n"
        f"Full category breakdown: {expense_map}"
    )

    def open_ai_chat(_):
        _open_ai_chat(page, financial_context, db.get_anthropic_api_key(), None, [])

    def open_history(_):
        _open_history_dialog(page, financial_context, db.get_anthropic_api_key())

    def open_add_income(_):
        from ui.transactions_screen import _income_dialog
        _income_dialog(page, lambda **_: on_data_changed())

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Card(
                content=ft.Container(
                    padding=16, border_radius=20,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                        colors=["#0ea5e9", "#6366f1"],
                    ),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Column(spacing=4, controls=[
                                ft.Text("Current Balance", color=ft.Colors.WHITE_70, size=14),
                                ft.Text(peso(balance), color=ft.Colors.WHITE, size=34,
                                        weight=ft.FontWeight.BOLD),
                            ]),
                            ft.FilledButton(
                                "+ Income", icon=ft.Icons.ADD_CIRCLE,
                                on_click=open_add_income,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE),
                                    color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                ),
                            ),
                        ],
                    ),
                )
            ),
            ft.ResponsiveRow(controls=[
                ft.Container(col={"xs": 12, "md": 6}, content=ft.Card(content=ft.Container(
                    padding=14, content=ft.Column(controls=[
                        ft.Text("Spent This Month", size=13),
                        ft.Text(peso(month_total), size=22, weight=ft.FontWeight.W_700,
                                color=ft.Colors.ORANGE_300),
                    ])))),
                ft.Container(col={"xs": 12, "md": 6}, content=ft.Card(content=ft.Container(
                    padding=14, content=ft.Column(controls=[
                        ft.Text("Biggest Category", size=13),
                        ft.Text(f"{biggest_category} ({peso(biggest_value)})", size=20,
                                weight=ft.FontWeight.W_700),
                    ])))),
                ft.Container(col={"xs": 12, "md": 6}, content=ft.Card(content=ft.Container(
                    padding=14, content=ft.Column(controls=[
                        ft.Text("Income This Month", size=13),
                        ft.Text(peso(month_income), size=22, weight=ft.FontWeight.W_700,
                                color=ft.Colors.GREEN_400),
                    ])))),
                ft.Container(col={"xs": 12, "md": 6}, content=ft.Card(content=ft.Container(
                    padding=14, content=ft.Column(controls=[
                        ft.Text("Net Cashflow", size=13),
                        ft.Text(
                            ("+" if net_cashflow >= 0 else "") + peso(net_cashflow),
                            size=22, weight=ft.FontWeight.W_700,
                            color=ft.Colors.GREEN_400 if net_cashflow >= 0 else ft.Colors.RED_400,
                        ),
                        ft.Text("income minus expenses", size=11,
                                color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
                    ])))),
            ]),
            # AI card — new chat + history
            ft.Card(content=ft.Container(
                padding=16,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Column(spacing=4, expand=True, controls=[
                            ft.Text("AI Finance Advisor", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text("Chat with AI or browse past conversations.", size=12,
                                    color=ft.Colors.with_opacity(0.55, ft.Colors.ON_SURFACE)),
                        ]),
                        ft.Row(spacing=6, controls=[
                            ft.IconButton(icon=ft.Icons.HISTORY, icon_color="#94a3b8",
                                          tooltip="Chat History", on_click=open_history),
                            ft.FilledButton(
                                "Chat with AI", icon=ft.Icons.AUTO_AWESOME,
                                on_click=open_ai_chat,
                                style=ft.ButtonStyle(
                                    bgcolor="#0ea5e9", color=ft.Colors.WHITE,
                                    shape=ft.RoundedRectangleBorder(radius=12),
                                ),
                            ),
                        ]),
                    ],
                ),
            )),
            ft.Card(content=ft.Container(padding=8, content=(
                ft.Image(src=f"data:image/png;base64,{pie_b64}", fit=ft.BoxFit.CONTAIN)
                if pie_b64 else ft.Text("No expenses yet for this month.")
            ))),
            ft.Card(content=ft.Container(padding=8, content=(
                ft.Image(src=f"data:image/png;base64,{line_b64}", fit=ft.BoxFit.CONTAIN)
                if line_b64 else ft.Text("No trend data yet.")
            ))),
        ],
    )