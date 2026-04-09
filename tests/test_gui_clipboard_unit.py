"""Буфер обмена Tk: разбор клавиш и установка обработчиков."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

tkinter = pytest.importorskip("tkinter")
from tkinter import ttk

from vpconnect_install.gui_clipboard import (
    clipboard_action_from_key_event,
    install_text_clipboard_and_context_menu,
    install_ttk_entry_clipboard_and_context_menu,
)


def test_clipboard_action_win32_virtual_keys() -> None:
    with patch.object(sys, "platform", "win32"):
        assert clipboard_action_from_key_event(SimpleNamespace(keycode=86, keysym="", char="")) == "paste"
        assert clipboard_action_from_key_event(SimpleNamespace(keycode=67, keysym="", char="")) == "copy"
        assert clipboard_action_from_key_event(SimpleNamespace(keycode=88, keysym="", char="")) == "cut"
        assert clipboard_action_from_key_event(SimpleNamespace(keycode=65, keysym="", char="")) == "all"


def test_clipboard_action_keysyms() -> None:
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="v", char="")) == "paste"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="c", char="")) == "copy"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="x", char="")) == "cut"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="a", char="")) == "all"


def test_clipboard_action_cyrillic_unicode_chars() -> None:
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="", char="\u043c")) == "paste"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="", char="\u0441")) == "copy"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="", char="\u0447")) == "cut"
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="", char="\u0444")) == "all"


def test_clipboard_action_unknown_returns_none() -> None:
    assert clipboard_action_from_key_event(SimpleNamespace(keycode=0, keysym="z", char="")) is None


@pytest.mark.skipif(sys.platform == "win32", reason="Tk synthetic Ctrl+V not reliable on Windows")
def test_install_ttk_entry_clipboard_paste_via_event() -> None:
    try:
        root = tkinter.Tk()
    except tkinter.TclError as e:
        pytest.skip(f"Tk unavailable: {e}")
    root.withdraw()
    try:
        install_ttk_entry_clipboard_and_context_menu(root)
        e = ttk.Entry(root)
        e.pack()
        root.clipboard_clear()
        root.clipboard_append("pasted-value")
        e.focus_set()
        e.event_generate("<Control-KeyPress>", keysym="v", state=0x4)
        root.update_idletasks()
        root.update()
        assert "pasted-value" in e.get()
    finally:
        root.destroy()


def test_install_ttk_entry_context_menu_rmb() -> None:
    try:
        root = tkinter.Tk()
    except tkinter.TclError as e:
        pytest.skip(f"Tk unavailable: {e}")
    root.withdraw()
    try:
        install_ttk_entry_clipboard_and_context_menu(root)
        e = ttk.Entry(root)
        e.pack()
        with patch.object(tkinter.Menu, "tk_popup", lambda self, x, y: None):
            e.event_generate("<Button-3>", x=1, y=1, rootx=10, rooty=10)
        root.update()
    finally:
        root.destroy()


@pytest.mark.skipif(sys.platform == "win32", reason="Tk clipboard selection unreliable in this environment")
def test_install_text_clipboard_copy() -> None:
    try:
        root = tkinter.Tk()
    except tkinter.TclError as e:
        pytest.skip(f"Tk unavailable: {e}")
    root.withdraw()
    try:
        install_text_clipboard_and_context_menu(root)
        t = tkinter.Text(root, height=3, width=20)
        t.pack()
        t.insert("1.0", "select me")
        t.tag_add(tkinter.SEL, "1.0", "end-1c")
        if sys.platform == "win32":
            t.event_generate("<KeyPress>", keycode=67, state=0x4)
        else:
            t.event_generate("<Control-KeyPress>", keysym="c", state=0x4)
        root.update()
        assert root.clipboard_get() == "select me"
    finally:
        root.destroy()


@patch.object(sys, "platform", "darwin")
def test_install_entry_binds_command_on_macos() -> None:
    root = MagicMock()
    install_ttk_entry_clipboard_and_context_menu(root)
    assert root.bind_class.called


@patch.object(sys, "platform", "darwin")
def test_install_text_binds_command_on_macos() -> None:
    root = MagicMock()
    install_text_clipboard_and_context_menu(root)
    assert root.bind_class.called
