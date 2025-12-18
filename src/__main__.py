#!/usr/bin/env -S uv run

"""
This script monitors warframe.market for items listed below a specified price threshold.
When a suitable order is found, it plays a sound, copies a whisper message to the clipboard,
and prints the message to the console.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

import aiohttp
import pyperclip
from aiohttp import ClientTimeout
from aiolimiter import AsyncLimiter
from colorama import Fore

from .config import (
    CHECK_INTERVAL,
    DO_AUDIO_NOTIFICATION,
    ITEMS,
    PING_DISCORD_IDS,
    SOUND,
    WEBHOOK_URL,
)
from .models import OrderWithUser
from .responses import ItemResponse, OrdersItemTopResponse
from .types import Item
from .utils import clear_line, hex_to_embed_color

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Self


# Constants
BASE_URL = 'https://api.warframe.market/v2/'
HEADERS = {'accept': 'application/json', 'platform': 'pc'}
WH_HEADERS = {'accept': 'application/json'}
WH_EMBED_COLOR = hex_to_embed_color('#e362ab')


class OrderChecker:
    wh_session: aiohttp.ClientSession
    session: aiohttp.ClientSession
    rate_limiter: AsyncLimiter

    def __init__(self):
        self.order_tasks: set[asyncio.Task[Item]] = set()
        self.total: int = 0

        # This memory leaks out the wazoo
        self.found_orders_ids: set[str] = set()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        return None

    @staticmethod
    def play_sound() -> None:
        """Play a sound when a suitable order is found."""
        if not DO_AUDIO_NOTIFICATION:
            return

        subprocess.Popen(
            f'cvlc --play-and-exit --gain 0.1 {SOUND}',
            shell=True,
            stderr=subprocess.DEVNULL,
        )

    async def notify_webhook(
        self, order: OrderWithUser, /, *, description: str = ''
    ) -> None:
        """Send a webhook notification when a suitable order is found."""
        if not WEBHOOK_URL:
            return

        quantity = order.quantity

        quantity_fmt = f'\n Quantity: {quantity}' if quantity > 1 else ''
        content_fmt = ' '.join(f'<@{id}>' for id in PING_DISCORD_IDS)
        description += quantity_fmt

        data: dict[str, Any] = {
            'content': content_fmt,
            'embeds': [
                {
                    'title': 'Warframe Market Bot',
                    'description': description,
                    'color': WH_EMBED_COLOR,
                }
            ],
        }

        async with self.wh_session.post(WEBHOOK_URL, json=data) as r:
            r.raise_for_status()

    def print_number_of_attempts(self) -> None:
        r_fmt = f'\rTotal requests: {Fore.CYAN}{self.total}{Fore.RESET}'
        print(r_fmt, end='', flush=True)

    async def format_buy_message(self, order: OrderWithUser) -> str:
        # Get item name
        async with self.rate_limiter:
            async with self.session.get(f'item/{order.item_id}') as r:
                r.raise_for_status()
                item_resp = ItemResponse.model_validate(await r.json())

        if not item_resp.data or not item_resp.data.i18n:
            return 'MISSING'

        item_name = item_resp.data.i18n['en'].name

        # Make format
        fmt = (
            f'/w {order.user.ingame_name} Hi! '
            f'I want to buy: "{item_name} (rank {order.rank})" '
            f'for {order.platinum} platinum. (warframe.market)'
        )
        return fmt

    async def accept_order(self, order: OrderWithUser) -> None:
        """The routine to preform when an order is accepted as suitable.

        Parameters
        ----------
        order : OrderWithUser
            The accepted order.
        """
        # An extra api request is needed to get the item name
        # so we will schedule that in the background while we do other things
        fmt_task = asyncio.create_task(self.format_buy_message(order))

        self.found_orders_ids.add(order.id)
        self.play_sound()

        fmt = await fmt_task

        # Send webhook and copy to clipboard
        asyncio.create_task(self.notify_webhook(order, description=fmt))
        pyperclip.copy(fmt)

        print(f'\r{fmt}', flush=True)

    def predicate_order(self, order: OrderWithUser, item: Item) -> bool:
        return (
            order.platinum <= item.price_threshold
            and order.user.status == 'ingame'
            and order.id not in self.found_orders_ids
        )

    async def check_orders(self, item: Item) -> Item:
        """The individual task that checks current orders for the specified item.

        Parameters
        ----------
        item : Item
            The item to check orders for.

        Returns
        -------
        Item
            The same item that was passed in.
        """
        request = f'orders/item/{item.name}/top?rank={item.rank}'
        found_order: OrderWithUser | None = None

        # Main loop
        while True:
            # Get the list of orders
            async with self.rate_limiter:
                async with self.session.get(request) as r:
                    r.raise_for_status()
                    orders_resp = OrdersItemTopResponse.model_validate(await r.json())

            self.total += 1

            # Handle no data
            if not orders_resp.data:
                clear_line()
                print(f'\r{Fore.RED}No data.{Fore.RESET}', end='')
                continue

            # Notify user
            self.print_number_of_attempts()

            # Check orders
            for order in orders_resp.data.sell:
                if self.predicate_order(order, item):
                    found_order = order
                    break

            # Completion logic
            if found_order:
                await self.accept_order(found_order)
                break

            # Wait before checking again
            try:
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break

        # For easier chaining
        return item

    async def schedule_tasks(self) -> None:
        """Schedules async tasks for checking orders.

        Each task continuously checks one individual item from the global `ITEMS` list.
        When an individual task finds a suitable order, it returns out and is considered finished.
        We then rescheduled the same item in another task to continue monitoring it.
        """

        def add_task(item: Item) -> None:
            task = asyncio.create_task(self.check_orders(item))
            task.add_done_callback(self.order_tasks.discard)
            self.order_tasks.add(task)

        # Create initial tasks
        for item in ITEMS:
            add_task(item)

        # Schedule loop
        while self.order_tasks:
            done, _pending = await asyncio.wait(
                self.order_tasks, return_when=asyncio.FIRST_COMPLETED
            )

            # Reschedule the same item
            # This reschedule logic might seems a little convoluted but
            # it is done to potentially allow more control about what tasks are repeated
            for task in done:
                item = await task
                add_task(item)

    async def run(self) -> None:
        async with (
            aiohttp.ClientSession(
                base_url=BASE_URL, headers=HEADERS, timeout=ClientTimeout(total=10)
            ) as session,
            aiohttp.ClientSession(
                # headers=WEBHOOK_HEADERS,
                timeout=ClientTimeout(total=10),
            ) as wh_session,
        ):
            self.session = session
            self.wh_session = wh_session
            self.rate_limiter = AsyncLimiter(max_rate=3, time_period=1)

            try:
                await self.schedule_tasks()
            except (asyncio.CancelledError, KeyboardInterrupt):
                # Notify user
                clear_line()
                print(f'\r{Fore.RED}Exiting...{Fore.RESET}', end='\n', flush=True)

            finally:
                # Cancel all tasks
                for task in self.order_tasks:
                    task.cancel()


async def init_assets() -> None:
    pass


async def main() -> None:
    async with OrderChecker() as checker:
        await checker.run()


if __name__ == '__main__':
    asyncio.run(main())
