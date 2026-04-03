"""
Привязки буфера обмена и контекстного меню для Tk: ttk.Entry и tk.Text/ScrolledText.

Поддержка Ctrl+C/V/X/A и русской раскладки (keysym/Unicode), Windows virtual keycodes, macOS Cmd.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk


def clipboard_action_from_key_event(event: tk.Event) -> str | None:
    """
    По событию клавиши вернуть действие буфера: 'paste' | 'copy' | 'cut' | 'all', иначе None.

    Учитываются keycode (Windows), keysym и одиночный символ (в т.ч. кириллица).
    """
    _VK_A, _VK_C, _VK_V, _VK_X = 65, 67, 86, 88
    _SYM_PASTE = frozenset({"v", "cyrillic_em"})
    _SYM_COPY = frozenset({"c", "cyrillic_es"})
    _SYM_CUT = frozenset({"x", "cyrillic_che"})
    _SYM_ALL = frozenset({"a", "cyrillic_ef"})
    _U_PASTE = frozenset({0x043C, 0x041C})
    _U_COPY = frozenset({0x0441, 0x0421})
    _U_CUT = frozenset({0x0447, 0x0427})
    _U_ALL = frozenset({0x0444, 0x0424})

    kc = int(getattr(event, "keycode", 0) or 0)
    if sys.platform == "win32" and kc:
        if kc == _VK_V:
            return "paste"
        if kc == _VK_C:
            return "copy"
        if kc == _VK_X:
            return "cut"
        if kc == _VK_A:
            return "all"
    sym = (event.keysym or "").lower()
    if sym in _SYM_PASTE:
        return "paste"
    if sym in _SYM_COPY:
        return "copy"
    if sym in _SYM_CUT:
        return "cut"
    if sym in _SYM_ALL:
        return "all"
    ch = event.char or ""
    if len(ch) == 1:
        o = ord(ch)
        if o in _U_PASTE:
            return "paste"
        if o in _U_COPY:
            return "copy"
        if o in _U_CUT:
            return "cut"
        if o in _U_ALL:
            return "all"
    return None


def install_ttk_entry_clipboard_and_context_menu(root: tk.Misc) -> None:
    """Повесить на класс TEntry горячие клавиши и ПКМ (Вырезать/Копировать/Вставить/Выделить всё)."""

    def _top(w: tk.Widget) -> tk.Toplevel | tk.Tk:
        return w.winfo_toplevel()

    def _paste_widget(w: ttk.Entry) -> None:
        try:
            clip = _top(w).clipboard_get()
        except tk.TclError:
            return
        try:
            w.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        w.insert("insert", clip)

    def _copy_widget(w: ttk.Entry) -> None:
        try:
            if w.selection_present():
                t = _top(w)
                t.clipboard_clear()
                t.clipboard_append(w.selection_get())
        except tk.TclError:
            pass

    def _cut_widget(w: ttk.Entry) -> None:
        try:
            if w.selection_present():
                t = _top(w)
                t.clipboard_clear()
                t.clipboard_append(w.selection_get())
                w.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _select_all_widget(w: ttk.Entry) -> None:
        w.select_range(0, "end")
        w.icursor("end")

    def _on_shift_insert_paste(event: tk.Event) -> str:
        w = event.widget
        if isinstance(w, ttk.Entry):
            _paste_widget(w)
        return "break"

    def _apply_clip_action(w: ttk.Entry, act: str | None) -> str:
        if act == "paste":
            _paste_widget(w)
            return "break"
        if act == "copy":
            _copy_widget(w)
            return "break"
        if act == "cut":
            _cut_widget(w)
            return "break"
        if act == "all":
            _select_all_widget(w)
            return "break"
        return ""

    def _on_control_keypress(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, ttk.Entry):
            return ""
        if not (event.state & 0x4):
            return ""
        return _apply_clip_action(w, clipboard_action_from_key_event(event))

    def _on_command_keypress(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, ttk.Entry):
            return ""
        return _apply_clip_action(w, clipboard_action_from_key_event(event))

    def _on_button3(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, ttk.Entry):
            return ""
        menu = tk.Menu(w, tearoff=0)
        menu.add_command(label="Вырезать", command=lambda: _cut_widget(w))
        menu.add_command(label="Копировать", command=lambda: _copy_widget(w))
        menu.add_command(label="Вставить", command=lambda: _paste_widget(w))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: _select_all_widget(w))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    cls = "TEntry"
    root.bind_class(cls, "<Control-KeyPress>", _on_control_keypress)
    root.bind_class(cls, "<Shift-Insert>", _on_shift_insert_paste)
    root.bind_class(cls, "<Button-3>", _on_button3)
    if sys.platform == "darwin":
        root.bind_class(cls, "<Button-2>", _on_button3)
        root.bind_class(cls, "<Command-KeyPress>", _on_command_keypress)


def install_text_clipboard_and_context_menu(root: tk.Misc) -> None:
    """
    То же для tk.Text / ScrolledText.

    В состоянии disabled вставка и вырезание не выполняются; копирование и «выделить всё» работают.
    """

    def _top(w: tk.Widget) -> tk.Toplevel | tk.Tk:
        return w.winfo_toplevel()

    def _is_editable(w: tk.Text) -> bool:
        return str(w.cget("state")) == tk.NORMAL

    def _copy_text(w: tk.Text) -> None:
        try:
            if w.tag_ranges(tk.SEL):
                t = _top(w)
                t.clipboard_clear()
                t.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
        except tk.TclError:
            pass

    def _paste_text(w: tk.Text) -> None:
        if not _is_editable(w):
            return
        try:
            clip = _top(w).clipboard_get()
        except tk.TclError:
            return
        try:
            w.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass
        w.insert(tk.INSERT, clip)

    def _cut_text(w: tk.Text) -> None:
        if not _is_editable(w):
            return
        try:
            if w.tag_ranges(tk.SEL):
                t = _top(w)
                t.clipboard_clear()
                t.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
                w.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass

    def _select_all_text(w: tk.Text) -> None:
        st = w.cget("state")
        try:
            w.configure(state=tk.NORMAL)
            w.tag_remove(tk.SEL, "1.0", tk.END)
            if w.get("1.0", "end-1c"):
                w.tag_add(tk.SEL, "1.0", "end-1c")
                w.mark_set(tk.INSERT, tk.END)
        except tk.TclError:
            pass
        finally:
            w.configure(state=st)

    def _apply_text_action(w: tk.Text, act: str | None) -> str:
        if act == "paste":
            _paste_text(w)
            return "break"
        if act == "copy":
            _copy_text(w)
            return "break"
        if act == "cut":
            _cut_text(w)
            return "break"
        if act == "all":
            _select_all_text(w)
            return "break"
        return ""

    def _on_control_keypress(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, tk.Text):
            return ""
        if not (event.state & 0x4):
            return ""
        return _apply_text_action(w, clipboard_action_from_key_event(event))

    def _on_command_keypress(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, tk.Text):
            return ""
        return _apply_text_action(w, clipboard_action_from_key_event(event))

    def _on_button3(event: tk.Event) -> str:
        w = event.widget
        if not isinstance(w, tk.Text):
            return ""
        menu = tk.Menu(w, tearoff=0)
        ed = _is_editable(w)
        if ed:
            menu.add_command(label="Вырезать", command=lambda: _cut_text(w))
        menu.add_command(label="Копировать", command=lambda: _copy_text(w))
        if ed:
            menu.add_command(label="Вставить", command=lambda: _paste_text(w))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: _select_all_text(w))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    cls = "Text"
    root.bind_class(cls, "<Control-KeyPress>", _on_control_keypress)
    root.bind_class(cls, "<Button-3>", _on_button3)
    if sys.platform == "darwin":
        root.bind_class(cls, "<Button-2>", _on_button3)
        root.bind_class(cls, "<Command-KeyPress>", _on_command_keypress)
