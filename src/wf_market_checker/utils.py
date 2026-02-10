from __future__ import annotations

import asyncio
import sys
import textwrap
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from colorama import Fore

if TYPE_CHECKING:
    from collections.abc import Callable


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


async def sleep_until_dt(dt: datetime, /, *, now: datetime | None = None) -> None:
    """Sleep until the given datetime."""
    now = now or datetime.now(UTC)
    delay = (dt - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)


def indent(text: str, /, *, level: int = 1) -> str:
    """Indent text by the given level (each level = 2 spaces)."""
    return textwrap.indent(text, '  ' * level)


def round2(n: float, /) -> str:
    """Round to 2 decimal places, stripping trailing zeros."""
    return f'{round(n, 2):g}'


def clear_line() -> None:
    """Clears the current line in the terminal."""
    sys.stdout.write('\x1b[2K\r')
    sys.stdout.flush()


def error(message: str, /) -> None:
    """Prints an error message to the console."""
    clear_line()
    print(f'\r{Fore.RED}{message}{Fore.RESET}', flush=True)
