from __future__ import annotations

from yarl import URL

from .config import PING_DISCORD_IDS

BASE_URL = URL('https://api.warframe.market/v2/')
ASSETS_BASE_URL = URL('https://warframe.market/static/assets/')
PROFILE_BASE_URL = URL('https://warframe.market/profile/')
ITEMS_BASE_URL = URL('https://warframe.market/items/')

HEADERS = {'accept': 'application/json', 'platform': 'pc', 'crossplay': 'true'}
WH_HEADERS = {'accept': 'application/json'}

WH_EMBED_COLOR = int('#e362ab'.lstrip('#'), 16)
PING_DISCORD_IDS_FMT = ' '.join(f'<@{id}>' for id in PING_DISCORD_IDS)
