from __future__ import annotations

from pathlib import Path

from .app_types import Item

DO_AUDIO_NOTIFICATION = False
CHECK_INTERVAL: float = 5
ITEMS: set[Item] = {
    Item(name='arcane_camisado', price_threshold=50, rank=5),
}

WEBHOOK_URL: str | None = 'https://discord.com/api/webhooks/REPLACE_WITH_ACTUAL_WEBHOOK'
PING_DISCORD_IDS: set[int] = {
    150560836971266048,
}

SRC_PATH = Path(__file__).parent.absolute()
SOUND = SRC_PATH / 'assets' / 'cash.ogg'
