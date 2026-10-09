"""Entry point used only by the standalone Windows build."""

from multiprocessing import freeze_support

from whaledriver.cli import main

if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
