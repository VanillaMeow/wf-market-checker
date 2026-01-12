from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemI18n(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    icon: str
    thumb: str
    description: str | None = None
    wiki_link: str | None = Field(None, alias='wikiLink')
    sub_icon: str | None = Field(None, alias='subIcon')


class Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    slug: str
    game_ref: str = Field(alias='gameRef')

    tags: list[str] = Field(default_factory=list)
    set_root: bool | None = Field(None, alias='setRoot')
    set_parts: list[str] | None = Field(None, alias='setParts')
    quantity_in_set: int | None = Field(None, alias='quantityInSet')
    rarity: str | None = None
    bulk_tradable: bool | None = Field(None, alias='bulkTradable')
    subtypes: list[str] | None = None
    max_rank: int | None = Field(None, alias='maxRank')
    max_charges: int | None = Field(None, alias='maxCharges')
    max_amber_stars: int | None = Field(None, alias='maxAmberStars')
    max_cyan_stars: int | None = Field(None, alias='maxCyanStars')
    base_endo: int | None = Field(None, alias='baseEndo')
    endo_multiplier: float | None = Field(None, alias='endoMultiplier')
    ducats: int | None = None
    vosfor: int | None = None
    req_mastery_rank: int | None = Field(None, alias='reqMasteryRank')
    vaulted: bool | None = None
    trading_tax: int | None = Field(None, alias='tradingTax')
    tradable: bool | None = None
    i18n: dict[str, ItemI18n] = Field(default_factory=dict, alias='i18n')


class ItemShort(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    slug: str
    game_ref: str = Field(alias='gameRef')
    tags: list[str] = Field(default_factory=list)
    i18n: dict[str, ItemI18n]

    max_rank: int | None = Field(None, alias='maxRank')
    max_charges: int | None = Field(None, alias='maxCharges')
    vaulted: bool | None = None
    ducats: int | None = None
    amber_stars: int | None = Field(None, alias='amberStars')
    cyan_stars: int | None = Field(None, alias='cyanStars')
    base_endo: int | None = Field(None, alias='baseEndo')
    endo_multiplier: float | None = Field(None, alias='endoMultiplier')
    subtypes: list[str] | None = None


class Activity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    details: str | None = None
    started_at: datetime | None = Field(None, alias='startedAt')


class UserShort(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    ingame_name: str = Field(alias='ingameName')
    avatar: str | None = None
    slug: str = ''
    reputation: int
    locale: str
    platform: str
    crossplay: bool
    status: str
    activity: Activity | None = None
    last_seen: datetime = Field(alias='lastSeen')


class Order(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    platinum: int
    quantity: int
    visible: bool
    item_id: str = Field(alias='itemId')

    group: str | None = None
    per_trade: int | None = Field(None, alias='perTrade')
    rank: int | None = None
    charges: int | None = None
    subtype: str | None = None
    amber_stars: int | None = Field(None, alias='amberStars')
    cyan_stars: int | None = Field(None, alias='cyanStars')
    vosfor: int | None = None


class OrderWithUser(Order):
    user: UserShort
