"""Auto-price updating functionality."""

from __future__ import annotations

__all__ = ('AutoPriceUpdater',)

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, NamedTuple

import aiohttp

from . import utils
from .app_types import AutoPrice

if TYPE_CHECKING:
    from .api_client import WFMarketClient
    from .app_types import WatchedItem
    from .order_checker import OrderChecker
    from .ui import ConsoleUI
    from .v1_models import StatisticsClosedEntry


API_UPDATE_BUFFER_DT = timedelta(minutes=2)

_TWELVE_HOURS = timedelta(hours=12)
_SIX_HOURS = timedelta(hours=6)


def _next_hour_dt(now: datetime | None = None) -> datetime:
    """Get the next beginning of an hour."""
    now = now or datetime.now(UTC)
    return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


class PriceUpdate(NamedTuple):
    """The calculated price update."""

    final_price: int
    base_price: float
    margined_price: float


class AutoPriceUpdater:
    """Periodically updates an item's price threshold based on market statistics."""

    __slots__ = (
        '_client',
        '_item',
        '_order_checker',
        '_ui',
        'is_ready',
    )

    def __init__(self, item: WatchedItem, *, order_checker: OrderChecker) -> None:
        self._order_checker: OrderChecker = order_checker
        self._item: WatchedItem = item
        self.is_ready: asyncio.Event = asyncio.Event()

        # Aliases
        self._client: WFMarketClient = order_checker.client
        self._ui: ConsoleUI = order_checker.ui

    async def start(self) -> None:
        """Start the auto-price update loop."""
        while True:
            await self.fetch_price()

            # Wait until the next beginning of an hour + a couple minutes
            # This is when the warframe.market API will update the statistics
            dt: datetime = _next_hour_dt() + API_UPDATE_BUFFER_DT
            try:
                await utils.sleep_until_dt(dt)
            except asyncio.CancelledError:
                break

    async def fetch_price(self) -> None:
        """Updates the price threshold."""
        price_update = await self._calculate_price()
        if price_update is not None:
            self._item.price_threshold = price_update.final_price
            self.is_ready.set()
            self._ui.show_price_update(self._item, price_update)

    async def _calculate_price(self) -> PriceUpdate | None:
        """Fetch statistics and calculate a price threshold for the item.

        Returns
        -------
        PriceUpdate | None
            The calculated price update, or None if unavailable.
        """
        item = self._item

        try:
            statistics_resp = await self._client.get_statistics(item.name)
        except aiohttp.ClientError as e:
            utils.error(f'Failed to get statistics for {item.name}: {e}')
            return None
        except TimeoutError:
            utils.error(f'Statistics request timed out for {item.name}.')
            return None

        # Use closed sell statistics from the 48h window
        statistics = statistics_resp.payload.statistics_closed
        entries = statistics.get_ranked_entries(
            statistics.hours_48,
            mod_rank=item.rank or 0,
        )

        if not entries:
            utils.error(f'No statistics entries found for {item.name}.')
            return None

        base = self._compute_base_price(entries)
        if base is None:
            return None

        margined = base * (1 - item.profit_margin_percent / 100)
        return PriceUpdate(
            final_price=round(margined),
            base_price=base,
            margined_price=margined,
        )

    def _compute_base_price(
        self,
        entries: list[StatisticsClosedEntry],
    ) -> float | None:
        """Compute the base price before profit margin is applied.

        Parameters
        ----------
        entries : list[StatisticsClosedEntry]
            Ranked entries sorted newest-first.

        Returns
        -------
        float | None
            The base price, or None if unavailable.
        """
        strategy = self._item.auto_price

        if strategy == AutoPrice.LATEST:
            return entries[0].moving_avg

        if strategy == AutoPrice.TWELVE_HOUR_LOW:
            return self._windowed_min(entries, _TWELVE_HOURS)

        if strategy == AutoPrice.SIX_HOUR_AVG:
            return self._windowed_avg(entries, _SIX_HOURS)

        return None

    def _windowed_min(
        self,
        entries: list[StatisticsClosedEntry],
        window_delta: timedelta,
    ) -> float | None:
        """Get the minimum median within a time window."""
        filtered = self._filter_to_window(entries, window_delta)
        if not filtered:
            return None
        return min(e.median for e in filtered)

    def _windowed_avg(
        self,
        entries: list[StatisticsClosedEntry],
        window_delta: timedelta,
    ) -> float | None:
        """Get the average moving_avg within a time window."""
        filtered = self._filter_to_window(entries, window_delta)
        if not filtered:
            return None
        return sum(e.moving_avg for e in filtered) / len(filtered)

    def _filter_to_window(
        self,
        entries: list[StatisticsClosedEntry],
        window_delta: timedelta,
    ) -> list[StatisticsClosedEntry]:
        """Filter entries to those within a time window, with fallback logic."""
        item = self._item
        cutoff = entries[0].datetime - window_delta
        filtered = [e for e in entries if e.datetime >= cutoff]

        if not filtered:
            utils.error(f'No statistics entries found for {item.name} in time window.')

            # price_threshold is 0 when initially setting auto-price
            if item.price_threshold <= 0:
                max_len = min(4, len(entries))
                filtered = entries[:max_len]
                utils.error(f'Falling back to latest {max_len} entries.')

        return filtered
