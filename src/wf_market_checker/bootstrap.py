from __future__ import annotations

import sys

from colorama import Fore

from . import utils
from .config import CONFIG_PATH, config


async def init_checks() -> None:
    url = config.webhook_url
    if url and url.endswith('REPLACE_WITH_ACTUAL_WEBHOOK'):
        m = (
            f'{Fore.RED}Missing webhook url. {Fore.RESET}'
            f'Please set it in {Fore.MAGENTA}{CONFIG_PATH}{Fore.RESET}.\n'
            f'{Fore.LIGHTBLACK_EX}Press any key to exit...{Fore.RESET}'
        )
        print(m)
        utils.get_ch()  # Block until a key is pressed
        sys.exit(1)
