from __future__ import annotations

import sys
from typing import NoReturn

from colorama import Fore

from . import utils
from .config import CONFIG_PATH, config

README_URL = 'https://github.com/VanillaMeow/wf-market-checker#configuration'


def _exit_with_message(msg: str, exit_code: int = 0) -> NoReturn:
    """Print a message, wait for a keypress, then exit."""
    print(msg)
    utils.get_ch()
    sys.exit(exit_code)


async def init_checks() -> None:
    url = config.webhook_url
    if url and url.endswith('REPLACE_WITH_ACTUAL_WEBHOOK'):
        _exit_with_message(
            f'{Fore.YELLOW}A config file has been generated at '
            f'{Fore.MAGENTA}{CONFIG_PATH}{Fore.YELLOW}.{Fore.RESET}\n'
            f'To use Discord notifications, set {Fore.CYAN}webhook-url{Fore.RESET} '
            f'to your webhook URL.\n'
            f'To silence this message, set {Fore.CYAN}webhook-url{Fore.RESET} '
            f'to an empty string ({Fore.LIGHTBLACK_EX}""{Fore.RESET}).\n'
            f'See {Fore.BLUE}{README_URL}{Fore.RESET} for setup help.'
        )

    if not config.items:
        _exit_with_message(
            f'{Fore.YELLOW}No items configured.{Fore.RESET} '
            f'Add {Fore.CYAN}[[items]]{Fore.RESET} entries in '
            f'{Fore.MAGENTA}{CONFIG_PATH}{Fore.RESET}.\n'
            f'See {Fore.BLUE}{README_URL}{Fore.RESET} for setup help.'
        )

    # All checks passed
    print(f'{Fore.LIGHTBLACK_EX}Config: {CONFIG_PATH}{Fore.RESET}')
