"""Юнит-тесты gui_extended_hint без полноценного GUI (моки tk)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import vpconnect_install.gui_extended_hint as geh


def test_bind_extended_hint_skips_blank_text() -> None:
    root = MagicMock()
    w = MagicMock()
    geh.bind_extended_hint(root, [w], "   \n\t")
    w.bind.assert_not_called()


def test_extended_hint_group_binds_enter_leave() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    geh.ExtendedHintGroup(root, [w], "  hint  ")
    assert w.bind.call_count == 2
    assert w.bind.call_args_list[0][0][0] == "<Enter>"
    assert w.bind.call_args_list[1][0][0] == "<Leave>"


def test_extended_hint_on_enter_cancels_and_schedules_show() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "h")
    g._hide_id = "pending-hide"
    g._show_id = "pending-show"
    enter = w.bind.call_args_list[0][0][1]
    top.after.return_value = "job-show"
    ev = SimpleNamespace(widget=w)
    enter(ev)
    assert top.after_cancel.call_count >= 2
    top.after.assert_called_with(geh.SHOW_DELAY_MS, ANY)


def test_extended_hint_on_leave_schedules_destroy() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "h")
    leave = w.bind.call_args_list[1][0][1]
    top.after.return_value = "job-hide"
    leave(SimpleNamespace())
    top.after.assert_called_with(geh.HIDE_DELAY_MS, g._destroy_tip)


def test_destroy_tip_swallows_tcl_error() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "h")
    tip = MagicMock()
    tip.destroy.side_effect = geh.tk.TclError("gone")
    g._tip = tip
    g._destroy_tip()
    assert g._tip is None


def test_show_noop_when_text_empty_after_strip() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "x")
    g._text = ""
    g._show(w)
    top.after.assert_not_called()


def test_show_noop_when_tip_already_exists() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "body")
    g._tip = MagicMock()
    with patch.object(geh.tk, "Toplevel") as mock_top:
        g._show(w)
    mock_top.assert_not_called()


@patch.object(geh.tk, "Label")
@patch.object(geh.tk, "Toplevel")
def test_show_positions_tip_and_binds_label(mock_toplevel: MagicMock, mock_label: MagicMock) -> None:
    tw = MagicMock()
    mock_toplevel.return_value = tw
    mock_label.return_value = MagicMock()
    tw.winfo_screenwidth.return_value = 2000
    tw.winfo_screenheight.return_value = 1000
    tw.winfo_reqwidth.return_value = 80
    tw.winfo_reqheight.return_value = 40

    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    anchor = MagicMock()
    anchor.winfo_rootx.return_value = 100
    anchor.winfo_rooty.return_value = 50
    anchor.winfo_height.return_value = 20

    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "tooltip text")
    g._show(anchor)
    mock_toplevel.assert_called_once_with(top)
    tw.geometry.assert_called_once()
    tw.wm_overrideredirect.assert_called_once_with(True)


@patch.object(geh.tk, "Label")
@patch.object(geh.tk, "Toplevel")
def test_show_repositions_when_off_bottom_edge(mock_toplevel: MagicMock, mock_label: MagicMock) -> None:
    tw = MagicMock()
    mock_toplevel.return_value = tw
    mock_label.return_value = MagicMock()
    tw.winfo_screenwidth.return_value = 400
    tw.winfo_screenheight.return_value = 120
    tw.winfo_reqwidth.return_value = 100
    tw.winfo_reqheight.return_value = 100

    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    anchor = MagicMock()
    anchor.winfo_rootx.return_value = 10
    anchor.winfo_rooty.return_value = 80
    anchor.winfo_height.return_value = 30

    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "tall tip")
    g._show(anchor)
    geo = tw.geometry.call_args[0][0]
    _, y = geo.split("+", 1)[1].split("+")
    assert int(y) < anchor.winfo_rooty.return_value + anchor.winfo_height.return_value + 4


def test_tip_enter_cancels_hide_timer() -> None:
    top = MagicMock()
    root = MagicMock()
    root.winfo_toplevel.return_value = top
    w = MagicMock()
    g = geh.ExtendedHintGroup(root, [w], "h")
    g._hide_id = "pending"
    g._tip_enter(SimpleNamespace())
    top.after_cancel.assert_called_once_with("pending")
    assert g._hide_id is None
