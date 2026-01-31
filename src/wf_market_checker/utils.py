from __future__ import annotations

import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

from colorama import Fore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .models import Item as ItemModel, OrderWithUser


if sys.platform == 'win32':
    import msvcrt

    get_ch: Callable[None, str] = msvcrt.getwch
    if TYPE_CHECKING:
        get_ch.__doc__ = 'Read a single character from standard input.'
else:
    import termios
    import tty

    def get_ch() -> str:
        """Read a single character from standard input."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def indent(text: str, /, *, level: int = 1) -> str:
    """Indent text by the given level (each level = 2 spaces)."""
    return textwrap.indent(text, '  ' * level)


def clear_line() -> None:
    """Clears the current line in the terminal."""
    sys.stdout.write('\x1b[2K\r')
    sys.stdout.flush()


def error(message: str, /) -> None:
    """Prints an error message to the console."""
    clear_line()
    print(f'\r{Fore.RED}{message}{Fore.RESET}', flush=True)


def play_sound(sound: Path, /) -> None:
    """Play a sound when a suitable order is found."""
    subprocess.Popen(
        f'cvlc --play-and-exit --gain 0.1 {sound}',
        shell=True,
        stderr=subprocess.DEVNULL,
    )


def format_buy_message(order: OrderWithUser, item: ItemModel) -> str:
    item_name = item.i18n['en'].name

    # Make format
    rank_fmt = f' (rank {order.rank})' if order.rank is not None else ''
    return (
        f'/w {order.user.ingame_name} Hi! '
        f'I want to buy: "{item_name}{rank_fmt}" '
        f'for {order.platinum} platinum. (warframe.market)'
    )
