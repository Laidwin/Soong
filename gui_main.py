"""Desktop entry point: start the PySide6 application.

    python gui_main.py
"""

from __future__ import annotations

import sys

try:
    from dotenv import load_dotenv

    load_dotenv()  # reads GENIUS_ACCESS_TOKEN from .env when present
except ImportError:
    pass

from soong.config import Config
from soong.gui.app import run


def main() -> int:
    return run(Config.load())


if __name__ == "__main__":
    sys.exit(main())
