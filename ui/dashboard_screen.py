from __future__ import annotations

import base64
import threading
from datetime import date
from io import BytesIO

import flet as ft
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt

# Background AI responses keyed by session_id.
# When the chat dialog is closed while AI is still working, the worker
# deposits its reply here so it can be re-displayed if the session is reopened.
_bg_results: dict[int, str] = {}
_bg_lock = threading.Lock()

# Tracks sessions that currently have a worker thread in flight.
# Used by newly-opened dialogs to show a typing indicator for in-progress requests.
_pending_sessions: set[int] = set()

# Maps session_id -> "deliver reply" callable for whichever dialog is currently open.
# Replaces the old dlg.open check so the worker can reach the *current* dialog even
# when the user closed and reopened (or navigated to history and back).
_active_callbacks: dict[int, callable] = {}

_sessions_meta_lock = threading.Lock()
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


def _user_bubble(text: str, bubble_w: int, on_edit=None, on_copy=None) -> ft.Control:
    """User chat bubble with optional Edit (fills input) and Copy (clipboard) buttons."""
    btn_color = ft.Colors.with_opacity(0.45, ft.Colors.WHITE)
    btn_style = ft.ButtonStyle(padding=ft.padding.only(left=0, right=2, top=0, bottom=0))

    action_btns: list[ft.Control] = []
    if on_edit:
        action_btns.append(
            ft.TextButton(
                content=ft.Row(
                    spacing=3,
                    controls=[
                        ft.Icon(ft.Icons.EDIT_OUTLINED, size=11, color=btn_color),
                        ft.Text("Edit", size=10, color=btn_color),
                    ],
                ),
                on_click=lambda _: on_edit(text),
                style=btn_style,
                tooltip="Copy to input to re-ask",
            )
        )
    if on_copy:
        action_btns.append(
            ft.TextButton(
                content=ft.Row(
                    spacing=3,
                    controls=[
                        ft.Icon(ft.Icons.COPY_OUTLINED, size=11, color=btn_color),
                        ft.Text("Copy", size=10, color=btn_color),
                    ],
                ),
                on_click=lambda _: on_copy(text),
                style=btn_style,
                tooltip="Copy message text",
            )
        )

    action_row = ft.Row(
        spacing=0,
        alignment=ft.MainAxisAlignment.END,
        controls=action_btns,
    ) if action_btns else ft.Container(height=0)

    return ft.Row(
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.END,
        controls=[
            ft.Container(expand=True),
            ft.Column(
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END,
                controls=[
                    ft.Container(
                        width=bubble_w,
                        content=ft.Text(text, selectable=True, size=13, color=ft.Colors.WHITE),
                        padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                        bgcolor="#0369a1",
                        border_radius=ft.BorderRadius(
                            top_left=14, top_right=4,
                            bottom_left=14, bottom_right=14,
                        ),
                        margin=ft.Margin(bottom=2, top=0, left=0, right=0),
                    ),
                    action_row,
                ],
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
    # True when a static welcome bubble was injected (new chats only).
    # Needed to compute the DB offset when truncating after an inline edit.
    _has_welcome = [not bool(history)]
    # (history_index, outer_row) — used by _edit_and_resend for truncation
    bubble_map: list[tuple[int, ft.Control]] = []
    # Set to True when the user presses the stop button.
    # The worker checks this after its blocking API call returns and discards
    # the reply if True (it cannot interrupt the network call itself).
    _stop_requested = [False]

    messages_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True, auto_scroll=True)

    def _edit_and_resend(hist_idx: int, bubble_row: ft.Control, new_text: str) -> None:
        """Truncate conversation from hist_idx onward, then resend with new_text."""
        if is_typing[0]:
            return

        # Remove this bubble and everything after it from the UI
        try:
            bubble_pos = messages_col.controls.index(bubble_row)
        except ValueError:
            return
        messages_col.controls = messages_col.controls[:bubble_pos]

        # Slice in-memory history — drop the old user message and all replies after it
        conv_history[:] = conv_history[:hist_idx]

        # Keep bubble_map in sync
        bubble_map[:] = [(i, c) for (i, c) in bubble_map if i < hist_idx]

        # Trim persisted messages so the DB matches the truncated history.
        # The welcome message (index 0) is never written to the DB, so we subtract 1
        # for fresh chats.
        if current_session[0] is not None:
            db_keep = hist_idx - (1 if _has_welcome[0] else 0)
            db.truncate_chat_messages_after_index(current_session[0], db_keep)

        page.update()
        _send(new_text)

    def _add_user_bubble(text: str, hist_idx: int) -> None:
        """Append a user bubble with inline edit-and-resend support."""
        current_text = [text]

        msg_col = ft.Column(
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.END,
        )
        outer_row = ft.Row(
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[ft.Container(expand=True), msg_col],
        )

        btn_color = ft.Colors.with_opacity(0.45, ft.Colors.WHITE)
        btn_style = ft.ButtonStyle(padding=ft.padding.only(left=0, right=2, top=0, bottom=0))

        def _render_view() -> None:
            msg_col.controls = [
                ft.Container(
                    width=bubble_w,
                    content=ft.Text(
                        current_text[0], selectable=True, size=13, color=ft.Colors.WHITE
                    ),
                    padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                    bgcolor="#0369a1",
                    border_radius=ft.BorderRadius(
                        top_left=14, top_right=4, bottom_left=14, bottom_right=14
                    ),
                    margin=ft.Margin(bottom=2, top=0, left=0, right=0),
                ),
                ft.Row(
                    spacing=0,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.TextButton(
                            content=ft.Row(
                                spacing=3,
                                controls=[
                                    ft.Icon(ft.Icons.EDIT_OUTLINED, size=11, color=btn_color),
                                    ft.Text("Edit", size=10, color=btn_color),
                                ],
                            ),
                            on_click=lambda _: _render_edit(),
                            style=btn_style,
                            tooltip="Edit and resend",
                        ),
                        ft.TextButton(
                            content=ft.Row(
                                spacing=3,
                                controls=[
                                    ft.Icon(ft.Icons.COPY_OUTLINED, size=11, color=btn_color),
                                    ft.Text("Copy", size=10, color=btn_color),
                                ],
                            ),
                            on_click=lambda _: _do_copy(),
                            style=btn_style,
                            tooltip="Copy message",
                        ),
                    ],
                ),
            ]
            page.update()

        def _render_edit() -> None:
            if is_typing[0]:
                return

            ef = ft.TextField(
                value=current_text[0],
                multiline=True,
                min_lines=1,
                max_lines=6,
                text_size=13,
                autofocus=True,
                border_radius=12,
                border_color="#334155",
                focused_border_color="#0ea5e9",
                expand=True,
            )

            def _confirm(_=None) -> None:
                new_text = (ef.value or "").strip()
                if not new_text:
                    return
                current_text[0] = new_text
                _render_view()
                _edit_and_resend(hist_idx, outer_row, new_text)

            ef.on_submit = lambda e: _confirm()

            msg_col.controls = [
                ft.Container(
                    width=bubble_w,
                    bgcolor="#0f172a",
                    border_radius=12,
                    padding=ft.padding.all(8),
                    border=ft.border.all(1, "#334155"),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ef,
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=6,
                                controls=[
                                    ft.TextButton(
                                        "Cancel",
                                        on_click=lambda _: _render_view(),
                                        style=ft.ButtonStyle(
                                            color=ft.Colors.with_opacity(0.6, ft.Colors.WHITE)
                                        ),
                                    ),
                                    ft.FilledButton(
                                        "Send edit",
                                        icon=ft.Icons.SEND_ROUNDED,
                                        on_click=_confirm,
                                        style=ft.ButtonStyle(
                                            bgcolor="#0369a1",
                                            color=ft.Colors.WHITE,
                                            shape=ft.RoundedRectangleBorder(radius=10),
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            ]
            page.update()
            ef.focus()

        def _do_copy() -> None:
            page.set_clipboard(current_text[0])
            page.snack_bar = ft.SnackBar(ft.Text("Message copied!"), duration=1500)
            page.snack_bar.open = True
            page.update()

        _render_view()
        bubble_map.append((hist_idx, outer_row))
        messages_col.controls.append(outer_row)

    def _add_ai_bubble(text: str) -> None:
        messages_col.controls.append(_ai_bubble(text, bubble_w))

    # Pre-populate existing history (for resumed chats)
    for idx, msg in enumerate(conv_history):
        if msg["role"] == "assistant":
            _add_ai_bubble(msg["content"])
        else:
            _add_user_bubble(msg["content"], idx)

    # ── Handle sessions that have (or had) a running worker ───────────────────
    if session_id is not None:
        # Register callback first so the worker can find us if it finishes
        # *after* we've initialised (the key race condition we're fixing).
        _register_callback(session_id)

        # Check if a completed reply was parked while no dialog was open.
        with _bg_lock:
            pending_reply = _bg_results.pop(session_id, None)

        if pending_reply is not None:
            # Guard: only show if not already the last message in history
            already_there = (
                conv_history
                and conv_history[-1].get("role") == "assistant"
                and conv_history[-1].get("content") == pending_reply
            )
            if not already_there:
                conv_history.append({"role": "assistant", "content": pending_reply})
                _add_ai_bubble(pending_reply)
        else:
            # Check if a worker is still in flight for this session.
            with _sessions_meta_lock:
                worker_running = session_id in _pending_sessions
            if worker_running:
                # Show typing indicator — the worker will deliver via callback.
                is_typing[0] = True
                _set_input_enabled(False)
                if typing_ind not in messages_col.controls:
                    messages_col.controls.append(typing_ind)

    # For brand-new chats show a static welcome
    if not conv_history:
        welcome_msg = "Hi! How can I help you today with your budget?"
        _add_ai_bubble(welcome_msg)
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

    stop_btn = ft.IconButton(
        icon=ft.Icons.STOP_CIRCLE_OUTLINED,
        icon_color="#f87171",
        icon_size=22,
        tooltip="Stop responding",
        visible=False,
        on_click=lambda _: _stop_thinking(),
    )

    typing_ind = _typing_bubble()

    def _update_stop_btn_visibility() -> None:
        stop_btn.visible = is_typing[0]
        send_btn.visible = not is_typing[0]

    def _set_input_enabled(enabled: bool) -> None:
        input_field.disabled = not enabled
        _update_stop_btn_visibility()

    def _stop_thinking() -> None:
        """User pressed stop — signal the worker to discard its reply."""
        if not is_typing[0]:
            return
        _stop_requested[0] = True
        # Reset UI immediately so the user knows we heard them
        is_typing[0] = False
        _set_input_enabled(True)
        if typing_ind in messages_col.controls:
            messages_col.controls.remove(typing_ind)
        page.update()

    # ------------------------------------------------------------------
    # Session / callback helpers
    # ------------------------------------------------------------------

    def _register_callback(sid: int) -> None:
        """Register this dialog as the delivery target for sid's reply."""
        def _deliver(reply: str) -> None:
            # Guard: if already in conv_history (fast-path DB read beat us), skip.
            if (conv_history
                    and conv_history[-1].get("role") == "assistant"
                    and conv_history[-1].get("content") == reply):
                return
            conv_history.append({"role": "assistant", "content": reply})
            is_typing[0] = False
            _set_input_enabled(True)
            if typing_ind in messages_col.controls:
                messages_col.controls.remove(typing_ind)
            if dlg.open:
                _add_ai_bubble(reply)
                page.update()
            else:
                # Dialog was closed again before the reply arrived — park it.
                with _bg_lock:
                    _bg_results[sid] = reply

        with _sessions_meta_lock:
            _active_callbacks[sid] = _deliver

    def _unregister_callback(sid: int) -> None:
        with _sessions_meta_lock:
            _active_callbacks.pop(sid, None)

    def _ensure_session() -> int:
        if current_session[0] is None:
            current_session[0] = db.create_chat_session("New Chat")
            _register_callback(current_session[0])
        return current_session[0]

    def _send(text: str) -> None:
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

        # Show typing indicator and disable input
        is_typing[0] = True
        _stop_requested[0] = False
        _set_input_enabled(False)
        with _sessions_meta_lock:
            _pending_sessions.add(sid)
        if typing_ind not in messages_col.controls:
            messages_col.controls.append(typing_ind)
        page.update()

        def _worker():
            reply = chat_with_ai(list(conv_history), financial_context, api_key)

            # ── Remove from in-flight set ──────────────────────────────────
            with _sessions_meta_lock:
                _pending_sessions.discard(sid)
                callback = _active_callbacks.get(sid)

            # ── Check stop ─────────────────────────────────────────────────
            if _stop_requested[0]:
                _stop_requested[0] = False
                # UI was already reset by _stop_thinking; nothing more to do.
                return

            # ── Persist ────────────────────────────────────────────────────
            db.save_chat_message(sid, "assistant", reply)

            # Auto-title on first real user message
            user_messages = [m for m in conv_history if m["role"] == "user"]
            if len(user_messages) == 1:
                title = _generate_session_title(user_messages[0]["content"], reply)
                db.update_chat_session_title(sid, title)

            # ── Deliver ─────────────────────────────────────────────────────
            # If a dialog is open for this session (could be a *new* dialog the
            # user opened after closing the original one), deliver via callback.
            # Otherwise park in _bg_results for the next open.
            if callback:
                callback(reply)
            else:
                with _bg_lock:
                    _bg_results[sid] = reply

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
                        content=ft.Row(
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[input_field, stop_btn, send_btn],
                        ),
                    ),
                ],
            ),
        ),
        actions=[],
    )

    def _close():
        dlg.open = False
        # Unregister so the worker falls back to _bg_results if it finishes after close.
        if current_session[0] is not None:
            _unregister_callback(current_session[0])
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

    # -----------------------------------------------------------------------
    # Build enriched AI context
    # -----------------------------------------------------------------------
    today = date.today()
    today_str = today.isoformat()

    # --- Budgets with full date / duration info ---
    budget_limits = db.get_budget_limits()
    budget_lines: list[str] = []
    for budget in budget_limits:
        category = budget.category
        limit = budget.monthly_limit
        spent = expense_map.get(category, 0.0)
        remaining_money = limit - spent
        pct = (spent / limit * 100) if limit > 0 else 0

        if pct >= 100:
            status = "Exceeded"
        elif pct >= 80:
            status = "Warning"
        elif pct >= 50:
            status = "On Track"
        else:
            status = "Good"

        # Duration / date details
        # Priority: explicit end_date > month-end calculation > start + duration_days
        import calendar as _cal
        from datetime import timedelta as _td
        duration_desc: str
        days_left_desc: str

        start_str = budget.start_date or today_str

        if budget.end_date:
            # --- Case 1: explicit end date always wins, regardless of duration_type ---
            try:
                end = date.fromisoformat(budget.end_date)
                start = date.fromisoformat(start_str)
                total_days = (end - start).days
                days_left = (end - today).days
                duration_desc = (
                    f"{total_days}-day period "
                    f"({start_str} → {budget.end_date})"
                )
                if days_left > 0:
                    days_left_desc = (
                        f"{days_left} day(s) left (ends {budget.end_date})"
                    )
                elif days_left == 0:
                    days_left_desc = f"ends TODAY ({budget.end_date})"
                else:
                    days_left_desc = f"ended on {budget.end_date}"
            except ValueError:
                duration_desc = f"custom ({start_str} → {budget.end_date})"
                days_left_desc = "unknown days left"

        elif budget.duration_type == "month":
            # --- Case 2: monthly budget — end is last day of the start month ---
            try:
                sd = date.fromisoformat(start_str)
                last_day = _cal.monthrange(sd.year, sd.month)[1]
                end = date(sd.year, sd.month, last_day)
                days_left = (end - today).days
                duration_desc = f"monthly (started {start_str}, resets end of {sd.strftime('%b %Y')})"
                if days_left > 0:
                    days_left_desc = (
                        f"{days_left} day(s) left in budget period (ends {end.isoformat()})"
                    )
                elif days_left == 0:
                    days_left_desc = f"ends TODAY ({end.isoformat()})"
                else:
                    days_left_desc = "budget period has ended"
            except ValueError:
                duration_desc = "monthly"
                days_left_desc = "unknown days left"

        else:
            # --- Case 3: fixed custom duration — compute end from start + days ---
            try:
                start = date.fromisoformat(start_str)
                end = start + _td(days=max(1, budget.duration_days))
                days_left = (end - today).days
                duration_desc = (
                    f"{budget.duration_days}-day period "
                    f"(started {start_str}, ends {end.isoformat()})"
                )
                if days_left > 0:
                    days_left_desc = f"{days_left} day(s) left (ends {end.isoformat()})"
                elif days_left == 0:
                    days_left_desc = f"ends TODAY ({end.isoformat()})"
                else:
                    days_left_desc = f"ended on {end.isoformat()}"
            except ValueError:
                duration_desc = f"{budget.duration_days}-day custom"
                days_left_desc = "unknown days left"

        budget_lines.append(
            f"  • {category}: limit={peso(limit)}, spent={peso(spent)}, "
            f"remaining={peso(remaining_money)}, {pct:.0f}% used, status={status}, "
            f"duration={duration_desc}, {days_left_desc}"
        )

    budgets_section = (
        "\n".join(budget_lines) if budget_lines else "  (no budgets set)"
    )

    # --- Recent transactions (last 20) ---
    recent_txns = db.get_transactions()[:20]
    txn_lines: list[str] = []
    for t in recent_txns:
        sign = "+" if t.txn_type == "income" else "-"
        desc = f" ({t.description})" if t.description else ""
        txn_lines.append(
            f"  • [{t.txn_date}] {sign}{peso(t.amount)} | {t.category}{desc}"
        )
    txns_section = "\n".join(txn_lines) if txn_lines else "  (no transactions yet)"

    # --- Recurring transactions with next-occurrence details ---
    recurring = db.get_recurring_transactions()
    rec_lines: list[str] = []
    for r in recurring:
        active_label = "active" if r.active else "paused"
        try:
            next_d = date.fromisoformat(r.next_date)
            days_until = (next_d - today).days
            if days_until < 0:
                timing = f"overdue since {r.next_date} ({abs(days_until)} day(s) ago)"
            elif days_until == 0:
                timing = "due TODAY"
            elif days_until == 1:
                timing = "due TOMORROW"
            else:
                timing = f"next on {r.next_date} ({days_until} day(s) from now)"
        except ValueError:
            timing = f"next on {r.next_date}"

        freq_label = r.frequency
        if r.frequency == "custom":
            freq_label = f"every {r.frequency_days} day(s)"

        sign = "+" if r.txn_type == "income" else "-"
        desc = f" ({r.description})" if r.description else ""
        rec_lines.append(
            f"  • {r.category}{desc}: {sign}{peso(r.amount)}, "
            f"{freq_label}, {timing}, started {r.start_date}, [{active_label}]"
        )
    rec_section = "\n".join(rec_lines) if rec_lines else "  (no recurring transactions)"

    # --- Settings summary ---
    starting_balance = db.get_starting_balance()
    api_key_set = bool(db.get_anthropic_api_key())
    settings_section = (
        f"  Currency: {currency_code}\n"
        f"  Starting balance: {peso(starting_balance)}\n"
        f"  Anthropic API key configured: {'Yes' if api_key_set else 'No'}"
    )

    # --- Assemble full context ---
    financial_context = (
        f"Today's date: {today_str}\n"
        f"Currency: {currency_code}\n"
        f"Current month: {month}\n\n"
        f"=== BALANCE & CASHFLOW ===\n"
        f"Current balance: {peso(balance)}\n"
        f"Starting balance: {peso(starting_balance)}\n"
        f"Income this month: {peso(month_income)}\n"
        f"Spent this month: {peso(month_total)}\n"
        f"Net cashflow this month: {peso(net_cashflow)}\n"
        f"Biggest spending category: {biggest_category} ({peso(biggest_value)})\n\n"
        f"=== SPENDING BY CATEGORY (this month) ===\n"
        + "\n".join(
            f"  • {cat}: {peso(amt)}" for cat, amt in expense_map.items()
        ) + "\n\n"
        f"=== BUDGET LIMITS & TRACKING ===\n"
        f"{budgets_section}\n\n"
        f"=== RECENT TRANSACTIONS (last 20) ===\n"
        f"{txns_section}\n\n"
        f"=== RECURRING TRANSACTIONS ===\n"
        f"{rec_section}\n\n"
        f"=== APP SETTINGS ===\n"
        f"{settings_section}"
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