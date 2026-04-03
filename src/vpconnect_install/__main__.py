"""
Запуск пакета: ``python -m vpconnect_install`` (CLI) или ``python -m vpconnect_install gui``.
"""

import sys


def main() -> None:
    """Передать управление GUI при первом аргументе ``gui``, иначе — CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from vpconnect_install.gui_tk import main as gui_main

        gui_main()
        return
    from vpconnect_install.cli import main as cli_main

    raise SystemExit(cli_main())


if __name__ == "__main__":
    main()
