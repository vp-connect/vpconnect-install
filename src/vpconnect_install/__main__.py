"""
Запуск: ``python -m vpconnect_install`` (CLI) или ``python -m vpconnect_install gui`` (Tkinter).

Делегирует в пакеты :mod:`cli` и :mod:`gui`.
"""

import sys


def main() -> None:
    """Передать управление GUI при первом аргументе ``gui``, иначе — CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from gui.gui_tk import main as gui_main

        gui_main()
        return
    from cli.main import main as cli_main

    raise SystemExit(cli_main())


if __name__ == "__main__":
    main()
