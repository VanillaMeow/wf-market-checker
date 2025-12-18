from __future__ import annotations

from typing import NamedTuple


class Item(NamedTuple):
    name: str
    price_threshold: int
    rank: int = 5
