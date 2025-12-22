from __future__ import annotations

from typing import NamedTuple


class Item(NamedTuple):
    name: str
    price_threshold: int
    quantity_min: int = -1
    rank: int | None = 5

class FoundOrder(NamedTuple):
    id: str
    price: int
