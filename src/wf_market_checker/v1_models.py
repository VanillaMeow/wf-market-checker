from __future__ import annotations

__all__ = (
    'Statistics',
    'StatisticsClosed',
    'StatisticsClosedEntry',
    'StatisticsLive',
    'StatisticsLiveEntry',
)

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StatisticsLiveEntry(BaseModel):
    """Individual statistics entry for a time period."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    datetime: datetime
    volume: int
    min_price: int
    max_price: int
    avg_price: float
    wa_price: float
    median: float
    id: str
    mod_rank: int
    order_type: Literal['sell', 'buy'] | None = None


class StatisticsClosedEntry(BaseModel):
    """Individual statistics entry for a time period."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    datetime: datetime
    volume: int
    min_price: int
    max_price: int
    avg_price: float
    wa_price: float
    median: float
    id: str
    mod_rank: int

    open_price: int
    closed_price: int
    moving_avg: float
    donch_top: int
    donch_bot: int


class StatisticsClosed(BaseModel):
    """Closed (historical) market statistics."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    hours_48: list[StatisticsClosedEntry] = Field(
        alias='48hours', default_factory=list[StatisticsClosedEntry]
    )
    days_90: list[StatisticsClosedEntry] = Field(
        alias='90days', default_factory=list[StatisticsClosedEntry]
    )

    def get_ranked_entries(
        self,
        entries: list[StatisticsClosedEntry],
        mod_rank: int = 0,
    ) -> list[StatisticsClosedEntry]:
        """Get entries filtered by mod_rank and optionally order_type, sorted by datetime."""
        filtered = [entry for entry in entries if entry.mod_rank == mod_rank]
        return sorted(filtered, key=lambda x: x.datetime, reverse=True)


class StatisticsLive(BaseModel):
    """Live (current) market statistics with buy/sell orders."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    hours_48: list[StatisticsLiveEntry] = Field(
        alias='48hours', default_factory=list[StatisticsLiveEntry]
    )
    days_90: list[StatisticsLiveEntry] = Field(
        alias='90days', default_factory=list[StatisticsLiveEntry]
    )

    def get_ranked_entries(
        self,
        entries: list[StatisticsLiveEntry],
        mod_rank: int = 0,
        order_type: Literal['sell', 'buy'] | None = None,
    ) -> list[StatisticsLiveEntry]:
        """Get entries filtered by mod_rank and optionally order_type, sorted by datetime."""
        filtered = [
            entry
            for entry in entries
            if entry.mod_rank == mod_rank
            and (order_type is None or entry.order_type == order_type)
        ]
        return sorted(filtered, key=lambda x: x.datetime, reverse=True)


class Statistics(BaseModel):
    """Complete statistics data including closed and live markets."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    statistics_closed: StatisticsClosed
    statistics_live: StatisticsLive
