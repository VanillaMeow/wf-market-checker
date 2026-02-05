"""Console UI output for the order checker."""

from __future__ import annotations

__all__ = ('ConsoleUI',)

import sys
from typing import TYPE_CHECKING

from colorama import Fore

from . import utils

if TYPE_CHECKING:
    from collections.abc import Callable

    from .app_types import WatchedItem


class ConsoleUI:
    """Handles all console output for the order checker."""

    if TYPE_CHECKING:

        @staticmethod
        def clear_line() -> None: ...
    else:
        clear_line: Callable[[], None] = staticmethod(utils.clear_line)

    @staticmethod
    def show_progress(total: int) -> None:
        """Display the current request count.

        Parameters
        ----------
        total : int
            The total number of requests made.
        """
        fmt = f'\rTotal requests: {Fore.CYAN}{total}{Fore.RESET}\r'
        sys.stdout.write(fmt)
        sys.stdout.flush()

    @staticmethod
    def show_price_update(item: WatchedItem, new_price: int) -> None:
        """Display a price threshold update notification.

        Parameters
        ----------
        item : WatchedItem
            The item whose price was updated.
        new_price : int
            The new price threshold.
        """
        m = (
            f'\r{Fore.BLUE}[AutoPrice]{Fore.RESET} Updated price threshold for '
            f'{Fore.CYAN}{item.name}{Fore.RESET} '
            f'to {Fore.MAGENTA}{new_price}{Fore.RESET} '
            f'({Fore.LIGHTBLACK_EX}{item.profit_margin_percent}% profit margin{Fore.RESET}).'
        )
        utils.clear_line()
        print(m)

    @staticmethod
    def show_order_found(message: str) -> None:
        """Display a found order message.

        Parameters
        ----------
        message : str
            The formatted buy message.
        """
        print(f'\r{message}', flush=True)

    @staticmethod
    def show_caching_item(item_id: str) -> None:
        """Display a caching progress message.

        Parameters
        ----------
        item_id : str
            The item ID being cached.
        """
        print(f'\rCaching item {Fore.CYAN}{item_id}{Fore.RESET}.', end='', flush=True)

    @staticmethod
    def show_exiting() -> None:
        """Display an exit message."""
        utils.clear_line()
        print(f'\r{Fore.RED}Exiting...{Fore.RESET}', end='\n', flush=True)
