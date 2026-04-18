"""
Привязки буфера обмена и контекстного меню для Tk: ttk.Entry и tk.Text/ScrolledText.

Поддержка Ctrl+C/V/X/A и русской раскладки (keysym/Unicode), Windows virtual keycodes, macOS Cmd.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

_WIN_KEYCODE_ACTION: dict[int, str] = {86: "paste", 67: "copy", 88: "cut", 65: "all"}
_SYM_ACTION: dict[str, str] = {
    "v": "paste",
    "cyrillic_em": "paste",
    "c": "copy",
    "cyrillic_es": "copy",
    "x": "cut",
    "cyrillic_che": "cut",
    "a": "all",
    "cyrillic_ef": "all",
}
_ORD_ACTION: dict[int, str] = {
    0x043C: "paste",
    0x041C: "paste",
    0x0441: "copy",
    0x0421: "copy",
    0x0447: "cut",
    0x0427: "cut",
    0x0444: "all",
    0x0424: "all",
}


def clipboard_action_from_key_event(event: tk.Event) -> str | None:
    """
    По событию клавиши вернуть действие буфера: 'paste' | 'copy' | 'cut' | 'all', иначе None.

    Учитываются keycode (Windows), keysym и одиночный символ (в т.ч. кириллица).
    """
    if sys.platform == "win32":
        kc = int(getattr(event, "keycode", 0) or 0)
        if kc:
            act = _WIN_KEYCODE_ACTION.get(kc)
            if act:
                return act
    sym = (event.keysym or "").lower()
    act = _SYM_ACTION.get(sym)
    if act:
        return act
    ch = event.char or ""
    if len(ch) != 1:
        return None
    return _ORD_ACTION.get(ord(ch))


def _widget_top(w: tk.Widget) -> tk.Toplevel | tk.Tk:
    return w.winfo_toplevel()


def _ttk_entry_paste(w: ttk.Entry) -> None:
    try:
        clip = _widget_top(w).clipboard_get()
    except tk.TclError:
        return
    try:
        w.delete("sel.first", "sel.last")
    except tk.TclError:
        pass
    w.insert("insert", clip)


def _ttk_entry_copy(w: ttk.Entry) -> None:
    try:
        if w.selection_present():
            t = _widget_top(w)
            t.clipboard_clear()
            t.clipboard_append(w.selection_get())
    except tk.TclError:
        pass


def _ttk_entry_cut(w: ttk.Entry) -> None:
    try:
        if w.selection_present():
            t = _widget_top(w)
            t.clipboard_clear()
            t.clipboard_append(w.selection_get())
            w.delete("sel.first", "sel.last")
    except tk.TclError:
        pass


def _ttk_entry_select_all(w: ttk.Entry) -> None:
    w.select_range(0, "end")
    w.icursor("end")


def _ttk_apply_action(w: ttk.Entry, act: str | None) -> str:
    if act == "paste":
        _ttk_entry_paste(w)
        return "break"
    if act == "copy":
        _ttk_entry_copy(w)
        return "break"
    if act == "cut":
        _ttk_entry_cut(w)
        return "break"
    if act == "all":
        _ttk_entry_select_all(w)
        return "break"
    return ""


def _ttk_on_shift_insert_paste(event: tk.Event) -> str:
    w = event.widget
    if isinstance(w, ttk.Entry):
        _ttk_entry_paste(w)
    return "break"


def _ttk_on_control_keypress(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, ttk.Entry) or not (event.state & 0x4):
        return ""
    return _ttk_apply_action(w, clipboard_action_from_key_event(event))


def _ttk_on_command_keypress(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, ttk.Entry):
        return ""
    return _ttk_apply_action(w, clipboard_action_from_key_event(event))


def _ttk_on_button3(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, ttk.Entry):
        return ""
    menu = tk.Menu(w, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: _ttk_entry_cut(w))
    menu.add_command(label="Копировать", command=lambda: _ttk_entry_copy(w))
    menu.add_command(label="Вставить", command=lambda: _ttk_entry_paste(w))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: _ttk_entry_select_all(w))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        try:
            menu.grab_release()
        except tk.TclError:
            pass
    return "break"


def install_ttk_entry_clipboard_and_context_menu(root: tk.Misc) -> None:
    """Повесить на класс TEntry горячие клавиши и ПКМ (Вырезать/Копировать/Вставить/Выделить всё)."""
    cls = "TEntry"
    root.bind_class(cls, "<Control-KeyPress>", _ttk_on_control_keypress)
    root.bind_class(cls, "<Shift-Insert>", _ttk_on_shift_insert_paste)
    root.bind_class(cls, "<Button-3>", _ttk_on_button3)
    if sys.platform == "darwin":
        root.bind_class(cls, "<Button-2>", _ttk_on_button3)
        root.bind_class(cls, "<Command-KeyPress>", _ttk_on_command_keypress)


def _text_is_editable(w: tk.Text) -> bool:
    return str(w.cget("state")) == tk.NORMAL


def _text_copy(w: tk.Text) -> None:
    try:
        if w.tag_ranges(tk.SEL):
            t = _widget_top(w)
            t.clipboard_clear()
            t.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
    except tk.TclError:
        pass


def _text_paste(w: tk.Text) -> None:
    if not _text_is_editable(w):
        return
    try:
        clip = _widget_top(w).clipboard_get()
    except tk.TclError:
        return
    try:
        w.delete(tk.SEL_FIRST, tk.SEL_LAST)
    except tk.TclError:
        pass
    w.insert(tk.INSERT, clip)


def _text_cut(w: tk.Text) -> None:
    if not _text_is_editable(w):
        return
    try:
        if w.tag_ranges(tk.SEL):
            t = _widget_top(w)
            t.clipboard_clear()
            t.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
            w.delete(tk.SEL_FIRST, tk.SEL_LAST)
    except tk.TclError:
        pass


def _text_select_all(w: tk.Text) -> None:
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


def _text_apply_action(w: tk.Text, act: str | None) -> str:
    if act == "paste":
        _text_paste(w)
        return "break"
    if act == "copy":
        _text_copy(w)
        return "break"
    if act == "cut":
        _text_cut(w)
        return "break"
    if act == "all":
        _text_select_all(w)
        return "break"
    return ""


def _text_on_control_keypress(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, tk.Text) or not (event.state & 0x4):
        return ""
    return _text_apply_action(w, clipboard_action_from_key_event(event))


def _text_on_command_keypress(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, tk.Text):
        return ""
    return _text_apply_action(w, clipboard_action_from_key_event(event))


def _text_on_button3(event: tk.Event) -> str:
    w = event.widget
    if not isinstance(w, tk.Text):
        return ""
    menu = tk.Menu(w, tearoff=0)
    ed = _text_is_editable(w)
    if ed:
        menu.add_command(label="Вырезать", command=lambda: _text_cut(w))
    menu.add_command(label="Копировать", command=lambda: _text_copy(w))
    if ed:
        menu.add_command(label="Вставить", command=lambda: _text_paste(w))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: _text_select_all(w))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        try:
            menu.grab_release()
        except tk.TclError:
            pass
    return "break"


def install_text_clipboard_and_context_menu(root: tk.Misc) -> None:
    """
    То же для tk.Text / ScrolledText.

    В состоянии disabled вставка и вырезание не выполняются; копирование и «выделить всё» работают.
    """
    cls = "Text"
    root.bind_class(cls, "<Control-KeyPress>", _text_on_control_keypress)
    root.bind_class(cls, "<Button-3>", _text_on_button3)
    if sys.platform == "darwin":
        root.bind_class(cls, "<Button-2>", _text_on_button3)
        root.bind_class(cls, "<Command-KeyPress>", _text_on_command_keypress)
