import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        from vpconnect_install.gui_tk import main as gui_main

        gui_main()
        return
    from vpconnect_install.cli import main as cli_main

    raise SystemExit(cli_main())


if __name__ == "__main__":
    main()
