"""The main orchestration logic for order checking."""

from __future__ import annotations

__all__ = ('OrderChecker',)

import asyncio
from copy import copy
from typing import TYPE_CHECKING

import aiohttp
from cachetools import TTLCache

from . import utils
from .api_client import WFMarketClient
from .app_types import AutoPrice, WatchedItem
from .auto_price import AutoPriceUpdater
from .config import config
from .notifications import Notifications
from .ui import ConsoleUI

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

    from .v2_models import OrderWithUser


class OrderChecker:
    """Main order checker that orchestrates all components."""

    def __init__(self) -> None:
        self._order_tasks: set[asyncio.Task[WatchedItem]] = set()
        self._auto_price_tasks: set[asyncio.Task[None]] = set()
        self._found_orders: TTLCache[str, int] = TTLCache(maxsize=1000, ttl=43200)
        self._started: bool = False
        self._total_req: int = 0

        # Components
        self._client = WFMarketClient()
        self._ui = ConsoleUI()
        self._notifications = Notifications(self._client, self._ui)
        self._auto_price = AutoPriceUpdater(self._client, self._ui)

    async def __aenter__(self) -> Self:
        await self.start()
        self._started = True
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        """Start the order checker."""
        if self._started:
            m = 'OrderChecker already started. Call stop() before start().'
            raise RuntimeError(m)

        await self._client.start()

    async def stop(self) -> None:
        """Stop the order checker."""
        if not self._started:
            m = 'OrderChecker not started. Call start() before stop().'
            raise RuntimeError(m)

        await self._client.stop()
        self._started = False

    async def run(self) -> None:
        """Run the order checker."""
        if not self._started:
            m = 'OrderChecker not started. Call start() before run().'
            raise RuntimeError(m)

        item_names = [item.name for item in config.items]
        self._ui.show_caching_item('items')
        await self._client.warmup_item_cache(item_names)
        self._ui.clear_line()

        try:
            await self._schedule_tasks()
        except (asyncio.CancelledError, KeyboardInterrupt):
            self._ui.show_exiting()
        finally:
            for task in self._order_tasks:
                task.cancel()
            for task in self._auto_price_tasks:
                task.cancel()
            for task in self._notifications.bg_tasks:
                task.cancel()

    async def _schedule_tasks(self) -> None:
        """Schedule async tasks for checking orders.

        Each task continuously checks one individual item from the config.
        When an individual task finds a suitable order, it returns and is
        rescheduled to continue monitoring.
        """
        # Create initial tasks
        for config_item in config.items:
            item = WatchedItem(
                name=config_item.name,
                price_threshold=0,  # We will populate this later
                quantity_min=config_item.quantity_min,
                rank=config_item.rank,
                profit_margin_percent=config_item.profit_margin_percent,
            )

            config_price = config_item.price_threshold
            if isinstance(config_price, AutoPrice):
                item.auto_price = copy(config_price)
                self._add_auto_price_task(item)
            else:
                item.price_threshold = config_price

            self._add_order_task(item)

        # Schedule loop
        while self._order_tasks:
            done, _pending = await asyncio.wait(
                self._order_tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                item = await task
                self._add_order_task(item)

    def _add_order_task(self, item: WatchedItem) -> None:
        """Add an order checking task for an item."""
        task = asyncio.create_task(self._check_orders(item))
        task.add_done_callback(self._order_tasks.discard)
        self._order_tasks.add(task)

    def _add_auto_price_task(self, item: WatchedItem) -> None:
        """Add an auto-price update task for an item."""
        task = asyncio.create_task(self._auto_price.start(item))
        task.add_done_callback(self._auto_price_tasks.discard)
        self._auto_price_tasks.add(task)

    async def _check_orders(self, item: WatchedItem) -> WatchedItem:
        """Check current orders for the specified item.

        Parameters
        ----------
        item : WatchedItem
            The item to check orders for.

        Returns
        -------
        WatchedItem
            The same item that was passed in.
        """

        while True:
            try:
                orders_resp = await self._client.get_item_orders(item.name, item.rank)
            except aiohttp.ClientError as e:
                utils.error(f'Failed to get orders for {item}: {e}')
                continue
            except TimeoutError:
                utils.error(f'Request timed out for {item}. Continuing.')
                continue

            self._total_req += 1

            if not orders_resp.data:
                utils.error(f'No data for {item.name}.')
                continue

            self._ui.show_progress(self._total_req)

            # Selection logic
            found_orders: list[OrderWithUser] = [
                order
                for order in orders_resp.data.sell
                if self._is_order_suitable(order, item)
            ]

            # Completion logic
            if found_orders:
                for order in found_orders:
                    self._found_orders[order.id] = order.platinum
                await self._accept_orders(found_orders)

            try:
                await asyncio.sleep(config.check_interval)
            except asyncio.CancelledError:
                break

        return item

    def _is_order_suitable(self, order: OrderWithUser, item: WatchedItem) -> bool:
        """Check if an order meets the criteria.

        Parameters
        ----------
        order : OrderWithUser
            The order to check.
        item : WatchedItem
            The item criteria.

        Returns
        -------
        bool
            True if the order is suitable.
        """
        cached_price = self._found_orders.get(order.id)
        is_new_or_price_dropped = cached_price is None or order.platinum < cached_price

        return (
            is_new_or_price_dropped
            and order.platinum <= item.price_threshold
            and order.quantity >= item.quantity_min
            and order.user.status == 'ingame'
        )

    async def _accept_orders(self, orders: list[OrderWithUser]) -> None:
        """Handle an accepted order.

        Parameters
        ----------
        order : OrderWithUser
            The accepted order.
        """

        for order in orders:
            item_model = await self._client.get_item(order.item_id)

            if item_model is None:
                utils.error('Bad data (invalid item).')
                return

            await self._notifications.notify_order_found(order, item_model)
