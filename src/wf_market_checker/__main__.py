"""
This script monitors warframe.market for items listed below a specified price threshold.
When a suitable order is found, it sends a discord webhook notification,
copies a whisper message to the clipboard and prints the message to the console.
"""

from __future__ import annotations

import asyncio

from wf_market_checker.bootstrap import init_checks
from wf_market_checker.order_checker import OrderChecker


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        # For some reason, when built by PyInstaller, KeyboardInterrupt propagates to the asyncio runner
        # despite being caught in the main `OrderChecker` loop.
        # This is just to silence the traceback since by this point we've already handled it.
        pass


async def _main() -> None:
    await init_checks()

    async with OrderChecker() as checker:
        await checker.run()


if __name__ == '__main__':
    main()
