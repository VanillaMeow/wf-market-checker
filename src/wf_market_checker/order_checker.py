"""
The main logic of the script.
"""

from __future__ import annotations

__all__ = ('OrderChecker',)


import asyncio
import sys
import traceback
from copy import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp
import pyperclip
from aiohttp import ClientTimeout
from aiolimiter import AsyncLimiter
from async_lru import alru_cache
from colorama import Fore

from . import utils
from .app_types import AUTO_PRICE_TO_SECONDS_MAP, AutoPrice, Item
from .config import (
    CHECK_INTERVAL,
    ITEMS,
    SOUND,
    WEBHOOK_URL,
)
from .constants import (
    BASE_URL,
    BASE_URL_V1,
    HEADERS,
    WH_HEADERS,
)
from .responses import ItemResponse, OrdersItemTopResponse
from .v1_responses import StatisticsResponse

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

    from .models import Item as ItemModel, OrderWithUser


class OrderChecker:
    wh_session: aiohttp.ClientSession
    session: aiohttp.ClientSession
    v1_session: aiohttp.ClientSession
    rate_limiter: AsyncLimiter

    def __init__(self):
        self.order_tasks: set[asyncio.Task[Item]] = set()
        self.auto_price_tasks: set[asyncio.Task[None]] = set()
        self.total: int = 0

        # This memory leaks out the wazoo
        self.found_orders_ids: set[str] = set()

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(
            base_url=BASE_URL, headers=HEADERS, timeout=ClientTimeout(total=10)
        )
        self.v1_session = aiohttp.ClientSession(
            base_url=BASE_URL_V1, headers=HEADERS, timeout=ClientTimeout(total=10)
        )
        self.wh_session = aiohttp.ClientSession(
            headers=WH_HEADERS, timeout=ClientTimeout(total=10)
        )
        self.rate_limiter = AsyncLimiter(max_rate=3, time_period=1)

    async def stop(self) -> None:
        await self.session.close()
        await self.v1_session.close()
        await self.wh_session.close()

    async def run(self) -> None:
        await self._warmup_item_cache()

        try:
            await self.schedule_tasks()
        except asyncio.CancelledError, KeyboardInterrupt:
            utils.clear_line()
            print(f'\r{Fore.RED}Exiting...{Fore.RESET}', end='\n', flush=True)

        finally:
            # Cancel all tasks
            for task in self.order_tasks:
                task.cancel()

    async def check_auto_price(self, item: Item, auto_price: AutoPrice) -> None:
        """Periodically updates item.price_threshold based on market statistics.

        Fetches statistics from the v1 API and calculates the average price
        from entries within the specified time window.
        """
        time_window_seconds = AUTO_PRICE_TO_SECONDS_MAP[auto_price]

        while True:
            new_price = await self._fetch_auto_price(item, time_window_seconds)
            if new_price is None:
                continue

            item.price_threshold = new_price
            m = (
                f'\r{Fore.BLUE}⚠️{Fore.RESET} Updated price threshold for {Fore.CYAN}{item.name}{Fore.RESET} '
                f'to {Fore.MAGENTA}{new_price}{Fore.RESET}.'
            )
            utils.clear_line()
            print(m)

            try:
                await asyncio.sleep(time_window_seconds)
            except asyncio.CancelledError:
                break

    async def schedule_tasks(self) -> None:
        """Schedules async tasks for checking orders.

        Each task continuously checks one individual item from the global `ITEMS` list.
        When an individual task finds a suitable order,it returns out and is considered
        finished. We then rescheduled the same item in another task to continue
        monitoring it.
        """

        def add_auto_price_task(item: Item, auto_price: AutoPrice) -> None:
            task = asyncio.create_task(self.check_auto_price(item, auto_price))
            task.add_done_callback(self.auto_price_tasks.discard)
            self.auto_price_tasks.add(task)

        def add_order_task(item: Item) -> None:
            task = asyncio.create_task(self.check_orders(item))
            task.add_done_callback(self.order_tasks.discard)
            self.order_tasks.add(task)

        # Create initial tasks
        for config_item in ITEMS:
            # First we need to convert from CofigItem to Item
            i = Item(
                name=config_item.name,
                price_threshold=0,  # We'll set this later
                quantity_min=config_item.quantity_min,
                rank=config_item.rank,
            )

            # Check if we are using AutoPrice
            config_price = config_item.price_threshold
            if isinstance(config_price, AutoPrice):
                auto_price = copy(config_price)
                add_auto_price_task(i, auto_price)  # type: ignore[]
            else:
                i.price_threshold = config_price

            # Finally we can add the task
            add_order_task(i)

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
                add_order_task(item)

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
                    r.raise_for_status()
                    orders_resp = OrdersItemTopResponse.model_validate_json(
                        await r.read()
                    )

            except aiohttp.ClientError as e:
                utils.error(f'Failed to get orders for {item}: {e}')
                continue
            except TimeoutError:
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
        loop = asyncio.get_running_loop()

        # An extra api request is needed to get the item name
        # But we already have it pre-cached on startup so let's use that
        item_model = await self.request_item_from_id(order.item_id)

        # Probably can't happen
        if item_model is None:
            utils.error('Bad data (invalid item).')
            return

        # Send webhook and copy to clipboard
        utils.play_sound(SOUND)
        fmt = utils.format_buy_message(order, item_model)
        loop.create_task(self.notify_webhook(order, item_model))
        pyperclip.copy(fmt)

        print(f'\r{fmt}', flush=True)

    @alru_cache(maxsize=None)
    async def request_item_from_id(self, item_id: str, /) -> ItemModel | None:
        print(f'\rCaching item {Fore.CYAN}{item_id}{Fore.RESET}.', end='', flush=True)

        async with self.rate_limiter, self.session.get(f'item/{item_id}') as r:
            r.raise_for_status()
            item_resp = ItemResponse.model_validate_json(await r.read())

        data = item_resp.data
        if not data or not data.i18n.get('en'):
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
        except aiohttp.ServerDisconnectedError:
            # Happens when quitting the script while the webhook is being sent
            return
        except aiohttp.ClientError as e:
            fmt = ''.join(traceback.format_tb(e.__traceback__))
            print(f'\rFailed to send webhook: {e}\n{fmt}')
        except TimeoutError:
            utils.error('Webhook notification request timed out.')

    def print_number_of_attempts(self) -> None:
        fmt = f'\rTotal requests: {Fore.CYAN}{self.total}{Fore.RESET}\r'
        sys.stdout.write(fmt)
        sys.stdout.flush()

    async def _fetch_auto_price(
        self, item: Item, time_window_seconds: int
    ) -> int | None:
        """Fetch statistics and calculate the average price for the time window.

        Returns the calculated price as an integer, or None if unavailable.
        """
        request = f'items/{item.name}/statistics'

        try:
            async with (
                self.rate_limiter,
                self.v1_session.get(request) as r,
            ):
                r.raise_for_status()
                statistics_resp = StatisticsResponse.model_validate_json(await r.read())

        except aiohttp.ClientError as e:
            utils.error(f'Failed to get statistics for {item.name}: {e}')
            return None
        except TimeoutError:
            utils.error(f'Statistics request timed out for {item.name}.')
            return None

        # Filter entries within the time window
        now = datetime.now(UTC)
        cutoff = now.timestamp() - time_window_seconds

        # Use live sell statistics from the 48h window
        statistics = statistics_resp.payload.statistics_closed

        entries = statistics.get_ranked_entries(
            statistics.hours_48,
            mod_rank=item.rank or 0,
        )

        # Filter to entries within our time window
        filtered = [e for e in entries if e.datetime.timestamp() >= cutoff]

        if not filtered:
            utils.error(f'No statistics entries found for {item.name} in time window.')
            return None

        # Calculate average from avg_price
        avg = sum(e.moving_avg for e in filtered) / len(filtered)

        # TODO(leah): make configurable
        profit_margin_percent = 30
        return round(avg * (1 - profit_margin_percent / 100))

    async def _warmup_item_cache(self) -> None:
        loop = asyncio.get_running_loop()

        # First we need to convert from ItemModel.slug to ItemModel.id
        # Item.name is equivalent to ItemModel.slug
        tasks = [
            loop.create_task(self.request_item_from_id.__wrapped__(self, item.name))
            for item in ITEMS
        ]

        item_ids: list[str] = [
            item_model.id
            for item_model in await asyncio.gather(*tasks)
            if item_model is not None
        ]

        # Finally we can warm up the cache
        tasks = [
            loop.create_task(self.request_item_from_id(item_id)) for item_id in item_ids
        ]
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        utils.clear_line()  # Prevent overlap
