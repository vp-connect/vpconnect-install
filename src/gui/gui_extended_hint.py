"""
Многострочные всплывающие подсказки для Tk: общий текст на группу виджетов (подпись + поле).

Показ с задержкой, скрытие с задержкой — чтобы при переходе курсора с подписи на поле подсказка не мигала.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable

SHOW_DELAY_MS = 450
HIDE_DELAY_MS = 200
WRAP_LENGTH_PX = 440


class ExtendedHintGroup:
    """Один и тот же текст подсказки для нескольких виджетов (например, подпись и Entry)."""

    def __init__(self, root: tk.Misc, widgets: Iterable[tk.Misc], text: str) -> None:
        self._root = root.winfo_toplevel()
        self._text = text.strip()
        self._show_id: str | None = None
        self._hide_id: str | None = None
        self._tip: tk.Toplevel | None = None
        for w in widgets:
            w.bind("<Enter>", self._on_enter, add=True)
            w.bind("<Leave>", self._on_leave, add=True)

    def _cancel_show(self) -> None:
        if self._show_id is not None:
            self._root.after_cancel(self._show_id)
            self._show_id = None

    def _cancel_hide(self) -> None:
        if self._hide_id is not None:
            self._root.after_cancel(self._hide_id)
            self._hide_id = None

    def _on_enter(self, event: tk.Event) -> None:
        self._cancel_hide()
        self._cancel_show()
        w = event.widget
        self._show_id = self._root.after(SHOW_DELAY_MS, lambda wi=w: self._show(wi))

    def _on_leave(self, _event: tk.Event) -> None:
        self._cancel_show()
        self._hide_id = self._root.after(HIDE_DELAY_MS, self._destroy_tip)

    def _destroy_tip(self) -> None:
        self._hide_id = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    def _show(self, anchor_widget: tk.Misc) -> None:
        self._show_id = None
        if self._tip is not None or not self._text:
            return
        tw = tk.Toplevel(self._root)
        self._tip = tw
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        label = tk.Label(
            tw,
            text=self._text,
            justify=tk.LEFT,
            wraplength=WRAP_LENGTH_PX,
            relief=tk.SOLID,
            borderwidth=1,
            background="#ffffe0",
            padx=10,
            pady=8,
        )
        label.pack()
        tw.update_idletasks()
        x = anchor_widget.winfo_rootx() + 8
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
        sw = tw.winfo_screenwidth()
        sh = tw.winfo_screenheight()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()
        if x + tw_w > sw - 8:
            x = max(8, sw - tw_w - 8)
        if y + tw_h > sh - 8:
            y = max(8, anchor_widget.winfo_rooty() - tw_h - 4)
        tw.geometry(f"+{x}+{y}")
        label.bind("<Enter>", self._tip_enter, add=True)
        label.bind("<Leave>", self._tip_leave, add=True)

    def _tip_enter(self, _event: tk.Event) -> None:
        self._cancel_hide()

    def _tip_leave(self, _event: tk.Event) -> None:
        self._hide_id = self._root.after(HIDE_DELAY_MS, self._destroy_tip)


def bind_extended_hint(root: tk.Misc, widgets: Iterable[tk.Misc], text: str) -> None:
    """Повесить одну подсказку ``text`` на все виджеты из ``widgets``."""
    if not text.strip():
        return
    ExtendedHintGroup(root, widgets, text)
