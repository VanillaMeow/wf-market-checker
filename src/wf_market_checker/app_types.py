from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AutoPrice(StrEnum):
    LATEST = 'latest'
    TWELVE_HOUR_LOW = '12h-low'
    SIX_HOUR_AVG = '6h-avg'
    NONE = 'None'


@dataclass(slots=True)
class WatchedItem:
    name: str
    price_threshold: int
    quantity_min: int = -1
    rank: int | None = None
    profit_margin_percent: int = 30
    auto_price: AutoPrice = AutoPrice.NONE
