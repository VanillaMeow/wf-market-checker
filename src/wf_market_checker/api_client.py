"""HTTP client for the Warframe Market API."""

# ruff: noqa: PLC2701, SLF001
# pyright: reportPrivateUsage=false

from __future__ import annotations

__all__ = ('WFMarketClient',)

import asyncio
from collections.abc import Mapping
from functools import _make_key
from types import TracebackType
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import ClientTimeout
from aiolimiter import AsyncLimiter
from async_lru import (
    _CacheItem,
    alru_cache,
)
from discord import Webhook

from .constants import BASE_URL, BASE_URL_V1, HEADERS, WH_HEADERS
from .v1_responses import StatisticsResponse
from .v2_responses import ItemResponse, OrdersItemTopResponse

if TYPE_CHECKING:
    from typing import Self

    from .v2_models import Item as ItemModel


class WFMarketClient:
    """Handles all HTTP communication with the Warframe Market API."""

    v1_session: aiohttp.ClientSession
    v2_session: aiohttp.ClientSession
    wh_session: aiohttp.ClientSession
    rate_limiter: AsyncLimiter

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
        """Initialize HTTP sessions."""
        self.v1_session = aiohttp.ClientSession(
            base_url=BASE_URL_V1, headers=HEADERS, timeout=ClientTimeout(total=10)
        )
        self.v2_session = aiohttp.ClientSession(
            base_url=BASE_URL, headers=HEADERS, timeout=ClientTimeout(total=10)
        )
        self.wh_session = aiohttp.ClientSession(
            headers=WH_HEADERS, timeout=ClientTimeout(total=10)
        )
        self.rate_limiter = AsyncLimiter(max_rate=3, time_period=1)

    async def stop(self) -> None:
        """Close HTTP sessions."""
        await self.v1_session.close()
        await self.v2_session.close()
        await self.wh_session.close()

    async def get_item_orders(
        self, item_name: str, rank: int | None = None
    ) -> OrdersItemTopResponse:
        """Fetch top orders for an item.

        Parameters
        ----------
        item_name : str
            The item slug/name.
        rank : int | None
            Optional mod rank filter.

        Returns
        -------
        OrdersItemTopResponse
            The API response containing buy/sell orders.

        Raises
        ------
        aiohttp.ClientError
            If the request fails.
        TimeoutError
            If the request times out.
        """
        request = f'orders/item/{item_name}/top'
        params: dict[str, int | str] = {}

        if rank is not None:
            params['rank'] = rank

        async with (
            self.rate_limiter,
            self.v2_session.get(request, params=params) as r,
        ):
            r.raise_for_status()
            return OrdersItemTopResponse.model_validate_json(await r.read())

    @alru_cache(maxsize=None)
    async def get_item(self, item_id: str, /) -> ItemModel | None:
        """Fetch item details by ID, with caching.

        Parameters
        ----------
        item_id : str
            The item ID or slug.

        Returns
        -------
        ItemModel | None
            The item model, or None if not found/invalid.
        """
        async with self.rate_limiter, self.v2_session.get(f'item/{item_id}') as r:
            r.raise_for_status()
            item_resp = ItemResponse.model_validate_json(await r.read())

        data = item_resp.data
        if not data or not data.i18n.get('en'):
            return None

        return data

    @alru_cache(maxsize=None, ttl=5)
    async def get_statistics(self, item_name: str) -> StatisticsResponse:
        """Fetch item statistics from the v1 API.

        Parameters
        ----------
        item_name : str
            The item slug/name.

        Returns
        -------
        StatisticsResponse
            The API response containing statistics.

        Raises
        ------
        aiohttp.ClientError
            If the request fails.
        TimeoutError
            If the request times out.
        """
        request = f'items/{item_name}/statistics'

        async with (
            self.rate_limiter,
            self.v1_session.get(request) as r,
        ):
            r.raise_for_status()
            return StatisticsResponse.model_validate_json(await r.read())

    async def post_webhook(self, url: str, data: Mapping[str, Any]) -> None:
        """Send a webhook POST request.

        Parameters
        ----------
        url : str
            The webhook URL.
        data : Mapping[str, Any]
            The JSON payload.

        Raises
        ------
        discord.HTTPException
            If the request fails.
        """
        webhook = Webhook.from_url(url, session=self.wh_session)
        await webhook.send(**data)

    async def warmup_item_cache(self, item_names: list[str]) -> None:
        """Pre-populate the item cache for the given item names.

        Parameters
        ----------
        item_names : list[str]
            List of item slugs to cache.
        """
        loop = asyncio.get_running_loop()

        # Fetch items by slug (bypassing cache)
        tasks = [
            loop.create_task(self.get_item.__wrapped__(self, name))
            for name in item_names
        ]

        items = await asyncio.gather(*tasks)

        # Access the underlying cache (through name-mangled attributes)
        wrapper = self.get_item._LRUCacheWrapperInstanceMethod__wrapper  # type: ignore[]
        cache = wrapper._LRUCacheWrapper__cache  # type: ignore[]

        # Manually populate cache by ID
        for item_model in items:
            if item_model is not None:
                # Key must include self since alru_cache prepends instance for methods
                key = _make_key((self, item_model.id), {}, typed=False)

                # Create a completed future with the result
                fut: asyncio.Future[ItemModel | None] = loop.create_future()
                fut.set_result(item_model)

                cache[key] = _CacheItem(fut, None)
