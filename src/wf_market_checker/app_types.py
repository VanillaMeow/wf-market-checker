from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class AutoPrice(StrEnum):
    TWELVE_HOUR = '12h'
    SIX_HOUR = '6h'
    TWO_HOUR = '2h'


# TODO(leah): make automatic and make agnostic
AUTO_PRICE_TO_SECONDS_MAP: dict[AutoPrice, int] = {
    AutoPrice.TWELVE_HOUR: 12 * 60 * 60,
    AutoPrice.SIX_HOUR: 6 * 60 * 60,
    AutoPrice.TWO_HOUR: 2 * 60 * 60,
}


class WatchedItem(BaseModel):
    name: str
    price_threshold: int
    quantity_min: int = -1
    rank: int | None = None
    profit_margin_percent: int = 30
