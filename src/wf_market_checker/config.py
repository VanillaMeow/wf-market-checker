from __future__ import annotations

__all__ = (
    'CONFIG_PATH',
    'SOUND',
    'config',
)

import sys
from multiprocessing import current_process
from pathlib import Path
from typing import TYPE_CHECKING, Self

import platformdirs
import tomlkit
from colorama import Fore
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tomlkit.exceptions import TOMLKitError

from .app_types import AutoPrice
from .utils import indent

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping
    from typing import Any

    type JsonValue = (
        str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
    )


# Config static
SRC_PATH = Path(__file__).parent.absolute()
TEMPLATES_DIR = SRC_PATH / 'templates'
CONFIG_DIR = Path(platformdirs.user_config_dir('wf-market-checker'))
CONFIG_PATH = CONFIG_DIR / 'config.toml'
SOUND = SRC_PATH / 'assets' / 'cash.ogg'

# Constants
PLACEHOLDER_WH_URL = 'https://discord.com/api/webhooks/REPLACE_WITH_ACTUAL_WEBHOOK'


class ConfigItem(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    name: str
    price_threshold: int | AutoPrice = Field(alias='price-threshold')
    quantity_min: int = Field(default=-1, alias='quantity-min')
    rank: int | None = None
    profit_margin_percent: int = Field(default=30, alias='profit-margin-percent')


class Config(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    do_audio_notification: bool = Field(default=False, alias='do-audio-notification')
    check_interval: float = Field(default=1.0, alias='check-interval')
    webhook_url: str = Field(default=PLACEHOLDER_WH_URL, alias='webhook-url')
    ping_discord_ids: set[int] = Field(
        default_factory=set[int], alias='ping-discord-ids'
    )
    items: list[ConfigItem] = Field(default_factory=list[ConfigItem])

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> Self:
        """Load config from TOML, merge with defaults, and write back if changed."""
        defaults = cls()

        # Copy all templates if config doesn't exist
        if not path.exists():
            cls._copy_templates(path.parent)
        else:
            # Restore any missing template files
            cls._copy_missing_templates(path.parent)

        # Read and parse config
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
    def _copy_templates(dest: Path) -> None:
        """Copy all template files to the config directory."""
        dest.mkdir(parents=True, exist_ok=True)
        for template in TEMPLATES_DIR.iterdir():
            template.copy_into(dest)

    @staticmethod
    def _copy_missing_templates(dest: Path) -> None:
        """Copy any missing template files to the config directory."""
        for template in TEMPLATES_DIR.iterdir():
            dest_file = dest / template.name
            if not dest_file.exists():
                template.copy_into(dest)

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

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc.as_string(), encoding='utf-8')


def _format_validation_errors(err: ValidationError) -> str:
    """Format pydantic validation errors into a readable message."""
    lines: list[str] = []

    for error in err.errors():
        loc = '.'.join(str(part) for part in error['loc'])
        msg = error['msg']

        lines.append(f'{Fore.YELLOW}{loc}{Fore.RESET}: {msg}')
        if 'input' in error:
            lines.append(
                indent(f'{Fore.LIGHTBLACK_EX}Got: {error["input"]!r}{Fore.RESET}')
            )

    error_block = indent('\n'.join(lines))
    return (
        f'{Fore.RED}Configuration error in {Fore.MAGENTA}{CONFIG_PATH}{Fore.RESET}.\n\n'
        f'{error_block}\n\n'
        f'{Fore.LIGHTBLACK_EX}Please fix the config file and try again.{Fore.RESET}'
    )


def _format_toml_error(err: TOMLKitError) -> str:
    """Format TOML parsing errors into a readable message."""
    return ''.join(
        (
            f'{Fore.RED}TOML syntax error in {Fore.MAGENTA}{CONFIG_PATH}{Fore.RESET}.\n\n',
            indent(f'{Fore.YELLOW}{err}{Fore.RESET}\n\n'),
            f'{Fore.LIGHTBLACK_EX}Please fix the config file and try again.{Fore.RESET}',
        )
    )


def load_config() -> Config:
    """
    Load and validate the application configuration.

    Returns a default Config in subprocess workers to avoid redundant file I/O.
    In the main process, loads from disk and exits on validation or syntax errors.

    Returns
    -------
    Config
        The loaded configuration, or a default instance in worker processes.
    """

    if current_process().name != 'MainProcess':
        return Config()

    try:
        return Config.load()
    except ValidationError as e:
        print(_format_validation_errors(e))
        sys.exit(1)
    except TOMLKitError as e:
        print(_format_toml_error(e))
        sys.exit(1)


config = load_config()
