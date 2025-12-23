"""
This script monitors warframe.market for items listed below a specified price threshold.
When a suitable order is found, it plays a sound, copies a whisper message to the clipboard,
and prints the message to the console.
"""

from __future__ import annotations

import asyncio
import traceback
from typing import TYPE_CHECKING

import aiohttp
import pyperclip
from aiohttp import ClientTimeout
from aiolimiter import AsyncLimiter
from colorama import Fore

from . import utils
from .config import (
    CHECK_INTERVAL,
    ITEMS,
    SOUND,
    WEBHOOK_URL,
)
from .constants import (
    BASE_URL,
    HEADERS,
    WH_HEADERS,
)
from .models import Item as ItemModel
from .models import Order, OrderWithUser
from .responses import ItemResponse, OrdersItemTopResponse

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

    from .types import Item


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

    async def run(self) -> None:
        async with (
            aiohttp.ClientSession(
                base_url=BASE_URL, headers=HEADERS, timeout=ClientTimeout(total=10)
            ) as session,
            aiohttp.ClientSession(
                headers=WH_HEADERS,
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
                utils.clear_line()
                print(f'\r{Fore.RED}Exiting...{Fore.RESET}', end='\n', flush=True)

            finally:
                # Cancel all tasks
                for task in self.order_tasks:
                    task.cancel()

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
        request = f'orders/item/{item.name}/top'
        found_order: OrderWithUser | None = None

        params: dict[str, int | str] = {}

        # Add rank if specified
        if item.rank is not None:
            params['rank'] = item.rank

        # Main loop
        while True:
            # Get the list of orders
            try:
                async with (
                    self.rate_limiter,
                    self.session.get(request, params=params) as r,
                ):
                    if not r.ok:
                        continue
                    orders_resp = OrdersItemTopResponse.model_validate(await r.json())
            except asyncio.TimeoutError:
                utils.error(f'Request timed out for {item}. Continuing.')
                continue

            self.total += 1

            # Handle no data
            if not orders_resp.data:
                utils.error(f'No data for {item.name}.')
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
                self.found_orders_ids.add(found_order.id)
                await self.accept_order(found_order)
                break

            # Wait before checking again
            try:
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break

        # For easier chaining
        return item

    def predicate_order(self, order: OrderWithUser, item: Item) -> bool:
        """The predicate to check if an order is suitable.

        Returns
        -------
        bool
            `True` if the order is suitable, `False` otherwise.
        """
        return (
            order.id not in self.found_orders_ids
            and order.platinum <= item.price_threshold
            and order.quantity >= item.quantity_min
            and order.user.status == 'ingame'
        )

    async def accept_order(self, order: OrderWithUser) -> None:
        """The routine to preform when an order is accepted as suitable.

        Parameters
        ----------
        order : OrderWithUser
            The accepted order.
        """
        # An extra api request is needed to get the item name
        # so we will schedule that in the background while we do other things
        item_model_task = asyncio.create_task(self.request_item_from_order(order))

        utils.play_sound(SOUND)

        item_model = await item_model_task

        # Probably can't happen
        if item_model is None:
            utils.error('Bad data (invalid item).')
            return

        # Send webhook and copy to clipboard
        fmt = self.format_buy_message(order, item_model)
        asyncio.create_task(self.notify_webhook(order, item_model))
        pyperclip.copy(fmt)

        print(f'\r{fmt}', flush=True)

    async def request_item_from_order(self, order: Order, /) -> ItemModel | None:
        async with self.rate_limiter, self.session.get(f'item/{order.item_id}') as r:
            r.raise_for_status()
            item_resp = ItemResponse.model_validate(await r.json())

        if not item_resp.data or not item_resp.data.i18n.get('en'):
            return None

        return item_resp.data

    async def notify_webhook(self, order: OrderWithUser, item: ItemModel, /) -> None:
        """Send a webhook notification when a suitable order is found."""
        if not WEBHOOK_URL:
            return

        data = utils.create_webhook_data(order=order, item=item)

        try:
            async with self.wh_session.post(WEBHOOK_URL, json=data) as r:
                r.raise_for_status()
        except aiohttp.ServerDisconnectedError as e:
            # Happens when quitting the script while the webhook is being sent
            pass
        except aiohttp.ClientError as e:
            fmt = ''.join(traceback.format_tb(e.__traceback__))
            print(f'\rFailed to send webhook: {e}\n{fmt}')

    def format_buy_message(self, order: OrderWithUser, item: ItemModel) -> str:
        item_name = item.i18n['en'].name

        # Make format
        rank_fmt = f' (rank {order.rank})' if order.rank is not None else ''
        fmt = (
            f'/w {order.user.ingame_name} Hi! '
            f'I want to buy: "{item_name}{rank_fmt}" '
            f'for {order.platinum} platinum. (warframe.market)'
        )
        return fmt

    def print_number_of_attempts(self) -> None:
        r_fmt = f'\rTotal requests: {Fore.CYAN}{self.total}{Fore.RESET}'
        print(r_fmt, end='', flush=True)


async def init_checks() -> None:
    pass


async def main() -> None:
    async with OrderChecker() as checker:
        await checker.run()


if __name__ == '__main__':
    asyncio.run(main())
