from __future__ import annotations

__all__ = (
    'CHECK_INTERVAL',
    'DO_AUDIO_NOTIFICATION',
    'ITEMS',
    'PING_DISCORD_IDS',
    'SOUND',
    'WEBHOOK_URL',
    'Config',
)

from pathlib import Path
from typing import TYPE_CHECKING, Self

import tomlkit
from pydantic import BaseModel, ConfigDict, Field

from .app_types import Item

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping
    from typing import Any

    type JsonValue = (
        str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
    )


# Config static
SRC_PATH = Path(__file__).parent.absolute()
CONFIG_PATH = SRC_PATH / 'config.toml'
SOUND = SRC_PATH / 'assets' / 'cash.ogg'

# Constants
SCHEMA_COMMENT = '#:schema ./config.schema.json\n\n'
PLACEHOLDER_WH_URL = 'https://discord.com/api/webhooks/REPLACE_WITH_ACTUAL_WEBHOOK'


class Config(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    do_audio_notification: bool = Field(default=False, alias='do-audio-notification')
    check_interval: float = Field(default=1.0, alias='check-interval')
    webhook_url: str = Field(default=PLACEHOLDER_WH_URL, alias='webhook-url')
    ping_discord_ids: set[int] = Field(
        default_factory=set[int], alias='ping-discord-ids'
    )
    items: set[Item] = Field(default_factory=set[Item])

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> Self:
        """Load config from TOML, merge with defaults, and write back if changed."""
        defaults = cls()

        if not path.exists():
            defaults.save(path)
            return defaults

        text = path.read_text(encoding='utf-8')
        doc = tomlkit.parse(text)
        existing = doc.unwrap()

        defaults_data = defaults.model_dump(mode='json', by_alias=True)
        merged = cls._merge_with_defaults(defaults_data, existing)
        config = cls.model_validate(merged, by_alias=True)

        # Write back if schema changed (new/removed keys)
        if existing != merged:
            config.save(path, doc)

        return config

    @staticmethod
    def _merge_with_defaults(
        defaults: dict[str, Any], existing: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        """Merge existing config into defaults, preserving existing values."""
        result = defaults.copy()

        for key, value in existing.items():
            if key not in result:
                continue

            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = Config._merge_with_defaults(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def _sync_doc(doc: MutableMapping[str, Any], data: Mapping[str, Any]) -> None:
        """Sync document keys with data, preserving tomlkit formatting."""
        keys_to_remove = set(doc) - set(data)
        for key in keys_to_remove:
            del doc[key]

        for key, value in data.items():
            doc[key] = value

    def save(
        self, path: Path = CONFIG_PATH, doc: tomlkit.TOMLDocument | None = None
    ) -> None:
        """Save config to TOML, preserving existing formatting if possible."""
        data = self.model_dump(mode='json', by_alias=True)

        if doc is None:
            doc = tomlkit.document()

        self._sync_doc(doc, data)

        content = doc.as_string()
        if not content.startswith('#:schema'):
            content = SCHEMA_COMMENT + content

        path.write_text(content, encoding='utf-8')


def load_config() -> Config:
    return Config.load()


_config = load_config()

# Export typed config values
DO_AUDIO_NOTIFICATION: bool = _config.do_audio_notification
CHECK_INTERVAL: float = _config.check_interval
WEBHOOK_URL: str = _config.webhook_url
PING_DISCORD_IDS: set[int] = _config.ping_discord_ids
ITEMS: set[Item] = _config.items
