"""Notification services for order alerts."""

from __future__ import annotations

import subprocess

__all__ = ('Notifications',)

import traceback
from typing import TYPE_CHECKING

import aiohttp
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
        self._client = client
        self._ui = ui

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

        await self._send_webhook(order, item)

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
        except aiohttp.ServerDisconnectedError:
            # Happens when quitting the script while the webhook is being sent
            return
        except aiohttp.ClientError as e:
            fmt = ''.join(traceback.format_tb(e.__traceback__))
            print(f'\rFailed to send webhook: {e}\n{fmt}')
        except TimeoutError:
            utils.error('Webhook notification request timed out.')
