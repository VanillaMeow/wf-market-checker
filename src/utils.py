from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from colorama import Fore
from discord import Embed
from discord.utils import utcnow
from yarl import URL

from src.constants import (
    ASSETS_BASE_URL,
    ITEMS_BASE_URL,
    PING_DISCORD_IDS_FMT,
    PROFILE_BASE_URL,
    WH_EMBED_COLOR,
)

from .config import DO_AUDIO_NOTIFICATION

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any

    from .models import Item as ItemModel, OrderWithUser


if sys.platform == 'win32':
    import msvcrt

    get_ch: Callable[None, str] = msvcrt.getwch
else:
    import termios
    import tty

    def get_ch() -> str:
        """Read a single character from standard input."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clear_line() -> None:
    """Clears the current line in the terminal."""
    sys.stdout.write('\x1b[2K\r')
    sys.stdout.flush()


def error(message: str, /) -> None:
    """Prints an error message to the console."""
    clear_line()
    print(f'\r{Fore.RED}{message}{Fore.RESET}', flush=True)


def play_sound(sound: Path, /) -> None:
    """Play a sound when a suitable order is found."""
    if not DO_AUDIO_NOTIFICATION:
        return

    subprocess.Popen(
        f'cvlc --play-and-exit --gain 0.1 {sound}',
        shell=True,
        stderr=subprocess.DEVNULL,
    )


def format_buy_message(order: OrderWithUser, item: ItemModel) -> str:
    item_name = item.i18n['en'].name

    # Make format
    rank_fmt = f' (rank {order.rank})' if order.rank is not None else ''
    return (
        f'/w {order.user.ingame_name} Hi! '
        f'I want to buy: "{item_name}{rank_fmt}" '
        f'for {order.platinum} platinum. (warframe.market)'
    )


def create_webhook_data(item: ItemModel, order: OrderWithUser) -> dict[str, Any]:
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
