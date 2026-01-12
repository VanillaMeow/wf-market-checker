"""
This script monitors warframe.market for items listed below a specified price threshold.
When a suitable order is found, it sends a discord webhook notification,
copies a whisper message to the clipboard and prints the message to the console.
"""

from __future__ import annotations

import asyncio
import sys

from colorama import Fore

from . import utils
from .config import WEBHOOK_URL
from .order_checker import OrderChecker


async def init_checks() -> None:
    if WEBHOOK_URL and WEBHOOK_URL.endswith('REPLACE_WITH_ACTUAL_WEBHOOK'):
        m = (
            f'{Fore.RED}Missing webhook url. {Fore.RESET}'
            f'Please set it in {Fore.MAGENTA}src/config.py{Fore.RESET}.\n'
            f'{Fore.LIGHTBLACK_EX}Press any key to exit...{Fore.RESET}'
        )
        print(m)
        utils.get_ch()  # Block until a key is pressed
        sys.exit(1)


async def _main() -> None:
    await init_checks()

    async with OrderChecker() as checker:
        await checker.run()


def main() -> None:
    asyncio.run(_main())


if __name__ == '__main__':
    main()
