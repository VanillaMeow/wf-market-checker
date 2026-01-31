from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple

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


class Item(BaseModel):
    name: str
    price_threshold: int
    quantity_min: int = -1
    rank: int | None = None


# TODO(leah): implement later to allow for invaliding orders that changed price
class FoundOrder(NamedTuple):
    id: str
    price: int
