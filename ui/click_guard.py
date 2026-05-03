from __future__ import annotations

from time import monotonic

import flet as ft


def allow_page_action(page: ft.Page, key: str, cooldown: float = 0.45) -> bool:
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


def begin_modal(page: ft.Page, key: str, cooldown: float = 0.45) -> bool:
    if not allow_page_action(page, key, cooldown):
        return False
    open_modals = getattr(page, "_open_modal_keys", None)
    if open_modals is None:
        open_modals = set()
        setattr(page, "_open_modal_keys", open_modals)
    if key in open_modals:
        return False
    open_modals.add(key)
    return True


def end_modal(page: ft.Page, key: str) -> None:
    open_modals = getattr(page, "_open_modal_keys", None)
    if open_modals is not None:
        open_modals.discard(key)
