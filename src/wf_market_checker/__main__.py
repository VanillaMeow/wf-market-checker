"""
This script monitors warframe.market for items listed below a specified price threshold.
When a suitable order is found, it sends a discord webhook notification,
copies a whisper message to the clipboard and prints the message to the console.
"""

from __future__ import annotations

import asyncio

from .bootstrap import init_checks
from .order_checker import OrderChecker


def main() -> None:
    asyncio.run(_main())


async def _main() -> None:
    await init_checks()

    async with OrderChecker() as checker:
        await checker.run()


if __name__ == '__main__':
    main()
