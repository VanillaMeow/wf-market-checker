from __future__ import annotations

import sys


def clear_line() -> None:
    """Clears the current line in the terminal."""
    sys.stdout.write('\x1b[2K')


def hex_to_embed_color(hex_color: str) -> int:
    """Converts a hex color to an embed color."""
    return int(hex_color.lstrip('#'), 16)
