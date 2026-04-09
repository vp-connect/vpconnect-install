from __future__ import annotations

from vpconnect_install.configure_bootstrap import (
    parse_configure_install_path,
    parse_configure_result_line,
    parse_result_line_field,
)


def test_parse_success_with_branch() -> None:
    out = "result:success; message:OK; branch:debian\n"
    st, msg, br, line1 = parse_configure_result_line(out)
    assert st == "success"
    assert msg == "OK"
    assert br == "debian"
    assert "result:success" in line1


def test_parse_error() -> None:
    out = "result:error; message:failed\n"
    st, msg, _, _ = parse_configure_result_line(out)
    assert st == "error"
    assert msg == "failed"


def test_parse_unknown_empty() -> None:
    st, _, _, _ = parse_configure_result_line("")
    assert st == "unknown"


def test_parse_success_after_apt_noise_on_stdout() -> None:
    """apt-get пишет Hit:/Get: в stdout; итоговая строка result — в конце."""
    out = (
        "Hit:1 http://deb.debian.org/debian bookworm InRelease\n"
        "Get:2 http://deb.debian.org/debian-security bookworm-security InRelease [48.0 kB]\n"
        "result:success; message:git установлен; version:git version 2.39.5\n"
    )
    st, msg, _, line1 = parse_configure_result_line(out)
    assert st == "success"
    assert "git" in msg
    assert line1.startswith("result:success")


def test_parse_result_line_field() -> None:
    out = "result:success; message:OK; mtproxy_secret_path:/var/lib/secret.txt; mtproxy_port:443\n"
    assert parse_result_line_field(out, "mtproxy_secret_path") == "/var/lib/secret.txt"
    assert parse_result_line_field(out, "path") is None
    out2 = "result:success; message:OK; password:secret123\n"
    assert parse_result_line_field(out2, "password") == "secret123"


def test_parse_install_path_from_03_output() -> None:
    out = (
        "result:success; message:репозиторий готов; path:/root/vpconnect-configure; "
        "branch:debian; commit:abc1234; remote:https://github.com/vp-connect/vpconnect-configure.git\n"
    )
    assert parse_configure_install_path(out) == "/root/vpconnect-configure"
