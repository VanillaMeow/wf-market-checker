"""Module for creating webhook data."""

from __future__ import annotations

__all__ = ('create_webhook_data',)

from typing import TYPE_CHECKING

from discord import Embed
from discord.utils import utcnow
from yarl import URL

from .constants import (
    ASSETS_BASE_URL,
    ITEMS_BASE_URL,
    PING_DISCORD_IDS_FMT,
    PROFILE_BASE_URL,
    WH_EMBED_COLOR,
)

if TYPE_CHECKING:
    from typing import TypedDict

    from discord.types.embed import Embed as EmbedData

    from .models import Item as ItemModel, OrderWithUser

    class _WebhookData(TypedDict):
        content: str | None
        embeds: list[EmbedData] | None


def create_webhook_data(item: ItemModel, order: OrderWithUser) -> _WebhookData:
    """Creates the data to be sent to the webhook, including the embed.

    Parameters
    ----------
    item : ItemModel
        The item model.
    order : OrderWithUser
        The order.

    Returns
    -------
    dict[str, Any]
        The data to be sent to the webhook.
    """

    item_en = item.i18n['en']

    rank_fmt = f'(rank {order.rank})' if order.rank is not None else ''
    title = f'{item_en.name} {rank_fmt}'
    icon_url = ASSETS_BASE_URL.join(
        URL(order.user.avatar or 'user/default-avatar.webp')
    )

    embed = (
        Embed(
            title=title,
            url=ITEMS_BASE_URL / item.slug % {'type': order.type},
            color=WH_EMBED_COLOR,
            timestamp=utcnow(),
        )
        .set_thumbnail(url=ASSETS_BASE_URL / item_en.icon)
        .set_author(
            name=order.user.ingame_name,
            url=PROFILE_BASE_URL / order.user.slug,
            icon_url=icon_url,
        )
    )

    embed.add_field(name='Platinum', value=order.platinum, inline=True)

    if order.quantity > 1:
        embed.add_field(name='Quantity', value=order.quantity, inline=True)

    return {
        'content': PING_DISCORD_IDS_FMT,
        'embeds': [embed.to_dict()],
    }
