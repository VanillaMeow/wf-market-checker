from __future__ import annotations

from yarl import URL

from .config import config

BASE_URL = URL('https://api.warframe.market/v2/')
BASE_URL_V1 = URL('https://api.warframe.market/v1/')
ASSETS_BASE_URL = URL('https://warframe.market/static/assets/')
PROFILE_BASE_URL = URL('https://warframe.market/profile/')
ITEMS_BASE_URL = URL('https://warframe.market/items/')

# The API rejects aiohttp's default User-Agent with a 403 response
HEADERS = {
    'accept': 'application/json',
    'platform': 'pc',
    'crossplay': 'true',
    'user-agent': 'wf-market-checker/0.1.0',
}
WH_HEADERS = {'accept': 'application/json'}

WH_EMBED_COLOR = int('#e362ab'.lstrip('#'), 16)
PING_DISCORD_IDS_FMT = ' '.join(
    f'<@{discord_id}>' for discord_id in config.ping_discord_ids
)
