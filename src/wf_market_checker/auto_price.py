"""Auto-price updating functionality."""

from __future__ import annotations

__all__ = ('AutoPriceUpdater',)

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import aiohttp

from . import utils
from .app_types import AUTO_PRICE_TO_SECONDS_MAP

if TYPE_CHECKING:
    from .api_client import WFMarketClient
    from .app_types import WatchedItem
    from .ui import ConsoleUI


ONE_HOUR = 60 * 60


class AutoPriceUpdater:
    """Periodically updates item price thresholds based on market statistics."""

    def __init__(self, client: WFMarketClient, ui: ConsoleUI) -> None:
        self._client: WFMarketClient = client
        self._ui: ConsoleUI = ui

    async def start(self, item: WatchedItem) -> None:
        """Start the auto-price update loop for an item.

        Parameters
        ----------
        item : WatchedItem
            The item to update prices for.
        """
        time_window_seconds = AUTO_PRICE_TO_SECONDS_MAP[item.auto_price]

        while True:
            new_price = await self._calculate_price(item, time_window_seconds)
            if new_price is not None:
                item.price_threshold = new_price
                self._ui.show_price_update(item, new_price)

            try:
                await asyncio.sleep(ONE_HOUR)
            except asyncio.CancelledError:
                break

    async def _calculate_price(
        self, item: WatchedItem, time_window_seconds: int
    ) -> int | None:
        """Fetch statistics and calculate the average price for the time window.

        Parameters
        ----------
        item : WatchedItem
            The item to calculate price for.
        time_window_seconds : int
            The time window in seconds.

        Returns
        -------
        int | None
            The calculated price, or None if unavailable.
        """
        try:
            statistics_resp = await self._client.get_statistics(item.name)
        except aiohttp.ClientError as e:
            utils.error(f'Failed to get statistics for {item.name}: {e}')
            return None
        except TimeoutError:
            utils.error(f'Statistics request timed out for {item.name}.')
            return None

        # Filter entries within the time window
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=time_window_seconds)

        # Use live sell statistics from the 48h window
        statistics = statistics_resp.payload.statistics_closed

        entries = statistics.get_ranked_entries(
            statistics.hours_48,
            mod_rank=item.rank or 0,
        )

        # Filter to entries within our time window
        filtered = [e for e in entries if e.datetime >= cutoff]

        if not filtered:
            utils.error(f'No statistics entries found for {item.name} in time window.')
            return None

        # Calculate average from moving_avg
        avg = sum(e.moving_avg for e in filtered) / len(filtered)

        return round(avg * (1 - item.profit_margin_percent / 100))
