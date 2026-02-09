"""Notification services for order alerts."""

from __future__ import annotations

__all__ = ('Notifications',)

import asyncio
import subprocess
import traceback
from typing import TYPE_CHECKING

import discord
import pyperclip

from . import utils, webhook_builder
from .config import SOUND, config
from .ui import ConsoleUI

if TYPE_CHECKING:
    from pathlib import Path

    from .api_client import WFMarketClient
    from .v2_models import Item as ItemModel, OrderWithUser


class Notifications:
    """Handles all notifications when a suitable order is found."""

    def __init__(self, client: WFMarketClient, ui: ConsoleUI) -> None:
        self._client: WFMarketClient = client
        self._ui: ConsoleUI = ui

        self.bg_tasks: set[asyncio.Task[None]] = set()

    @staticmethod
    def format_buy_message(order: OrderWithUser, item: ItemModel) -> str:
        item_name = item.i18n['en'].name

        # Make format
        rank_fmt = f' (rank {order.rank})' if order.rank is not None else ''
        return (
            f'/w {order.user.ingame_name} Hi! '
            f'I want to buy: "{item_name}{rank_fmt}" '
            f'for {order.platinum} platinum. (warframe.market)'
        )

    @staticmethod
    def play_sound(sound: Path, /) -> None:
        """Play a sound when a suitable order is found."""
        subprocess.Popen(
            f'cvlc --play-and-exit --gain 0.1 {sound}',
            shell=True,
            stderr=subprocess.DEVNULL,
        )

    async def notify_order_found(self, order: OrderWithUser, item: ItemModel) -> None:
        """Send all notifications for a found order.

        Parameters
        ----------
        order : OrderWithUser
            The found order.
        item : ItemModel
            The item model.
        """
        if config.do_audio_notification:
            self.play_sound(SOUND)

        fmt = self.format_buy_message(order, item)
        pyperclip.copy(fmt)
        self._ui.show_order_found(fmt)

        task = asyncio.create_task(self._send_webhook(order, item))
        self.bg_tasks.add(task)
        task.add_done_callback(self.bg_tasks.discard)

    async def _send_webhook(self, order: OrderWithUser, item: ItemModel) -> None:
        """Send a webhook notification.

        Parameters
        ----------
        order : OrderWithUser
            The found order.
        item : ItemModel
            The item model.
        """
        if not config.webhook_url:
            return

        data = webhook_builder.create_webhook_data(order=order, item=item)

        try:
            await self._client.post_webhook(config.webhook_url, data)
        except discord.HTTPException as e:
            fmt = ''.join(traceback.format_tb(e.__traceback__))
            utils.error(f'Failed to send webhook: {e}\n{fmt}')
